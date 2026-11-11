"""Supersonic fin check with linearized (Ackeret) thin-airfoil theory.

An independent supersonic estimate of each fin set, used to check the Barrowman
build-up above Mach 1. For each fin set:

    a_2D      = 4 / sqrt(M^2 - 1)                     Ackeret section slope
    slope     = a_2D / (1 + 2 / AR),  AR = s / c_mean  finite-span factor
    CN_alpha  = K_fb * (N / 2) * slope * A_panel / A_ref,  K_fb = 1 + R / (s + R)
    CP        = planform centroid (uniform supersonic loading)

``N / 2`` is the number of panels that carry load at any roll angle
(``sum sin^2(phi_i) = N / 2`` for ``N >= 3``). The nose and shoulder use the
slender-body terms of the Barrowman build-up. The finite-span factor is the
classical low-aspect-ratio downwash correction; it is not a supersonic tip-cone
correction, so treat the result as a cross-check, not as a design value.
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import fields
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.stability_control.containers import (
    AckeretFinResults,
    AckeretFinSlope,
    AckeretSweepPoint,
    ComponentContribution,
    FinSetGeometry,
    RocketGeometry,
)
from YAADO_Core.modules.stability_control.methods.barrowman.barrowman_stability import (
    compute_stability_at_mach,
    geometry_assumptions,
    geometry_from_vehicle,
    nose_cn_alpha_and_cp,
    transition_cn_alpha_and_cp,
)


def ackeret_fin_set(
    fins: FinSetGeometry, mach: float, body_radius: float, reference_area: float
) -> AckeretFinSlope:
    """Ackeret normal-force slope and CP of one fin set.

    Args:
        fins: Fin set geometry.
        mach: Freestream Mach number (> 1).
        body_radius: Body radius at the fins [m].
        reference_area: Area the slope refers to [m^2].

    Returns:
        The fin-set slope and its CP.

    Raises:
        ValueError: If ``mach <= 1``.
    """
    if mach <= 1.0:
        raise ValueError(f"Ackeret theory needs a supersonic Mach number, got {mach}")

    slope_2d = 4.0 / math.sqrt(mach**2 - 1.0)
    aspect_ratio = fins.span / fins.mean_chord
    k_fb = 1.0 + body_radius / (fins.span + body_radius)
    cn_alpha = (
        k_fb
        * (fins.count / 2.0)
        * slope_2d
        / (1.0 + 2.0 / aspect_ratio)
        * fins.panel_area
        / reference_area
    )

    cr, ct = fins.root_chord, fins.tip_chord
    x_centroid = (fins.sweep_length * (cr + 2.0 * ct) + cr**2 + cr * ct + ct**2) / (3.0 * (cr + ct))
    return AckeretFinSlope(
        name=fins.name,
        slope_2d=slope_2d,
        panel_aspect_ratio=aspect_ratio,
        cn_alpha=cn_alpha,
        x_cp=fins.root_le_x + x_centroid,
        normal_mach_le=mach * math.cos(math.radians(fins.sweep)),
    )


def ackeret_build_up(
    geometry: RocketGeometry, mach: float
) -> tuple[tuple[AckeretFinSlope, ...], tuple[ComponentContribution, ...]]:
    """Fin-set slopes and the whole-vehicle build-up with Ackeret fins."""
    fin_sets = tuple(
        ackeret_fin_set(f, mach, geometry.body_radius, geometry.reference_area)
        for f in geometry.fin_sets
    )
    cn_nose, x_nose = nose_cn_alpha_and_cp(geometry)
    components = [ComponentContribution("nose", cn_nose, x_nose)]
    cn_shoulder, x_shoulder = transition_cn_alpha_and_cp(geometry)
    if cn_shoulder > 0.0:
        components.append(ComponentContribution("shoulder", cn_shoulder, x_shoulder))
    components.extend(ComponentContribution(f.name, f.cn_alpha, f.x_cp) for f in fin_sets)
    return fin_sets, tuple(components)


def _cp(components: tuple[ComponentContribution, ...]) -> tuple[float, float]:
    """Total slope and slope-weighted CP of a build-up."""
    cn_alpha = sum(c.cn_alpha for c in components)
    return cn_alpha, sum(c.cn_alpha * c.x_cp for c in components) / cn_alpha


def run_mach_sweep(geometry: RocketGeometry, mach_max: float) -> list[AckeretSweepPoint]:
    """Compare Ackeret and Barrowman from ``SWEEP_MACH_MIN`` to ``mach_max``."""
    machs = np.linspace(
        AckeretFinAnalysis.SWEEP_MACH_MIN, mach_max, AckeretFinAnalysis.SWEEP_POINTS
    )
    points: list[AckeretSweepPoint] = []
    for m in machs:
        mach = float(m)
        fin_sets, components = ackeret_build_up(geometry, mach)
        barrowman = compute_stability_at_mach(geometry, mach)
        tail_name = geometry.tail_fins.name
        _, cp = _cp(components)
        points.append(
            AckeretSweepPoint(
                mach=mach,
                ackeret_fin_cn_alpha=fin_sets[-1].cn_alpha,
                barrowman_fin_cn_alpha=next(
                    c.cn_alpha for c in barrowman.components if c.name == tail_name
                ),
                ackeret_static_margin=(cp - geometry.cg_from_nose) / geometry.d_ref,
                barrowman_static_margin=barrowman.static_margin,
            )
        )
    return points


def format_mach_sweep_csv(points: list[AckeretSweepPoint]) -> str:
    """CSV text of the Ackeret-Barrowman comparison sweep."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(f.name for f in fields(AckeretSweepPoint))
    writer.writerows(
        (p.mach, p.ackeret_fin_cn_alpha, p.barrowman_fin_cn_alpha,
         p.ackeret_static_margin, p.barrowman_static_margin)
        for p in points
    )
    return buffer.getvalue()


def plot_method_comparison(points: list[AckeretSweepPoint], run_mach: float) -> Figure:
    """Plot tail-fin slope and static margin of both methods against Mach number.

    Args:
        points: Output of :func:`run_mach_sweep`.
        run_mach: Mach number of the run, marked on both panels.

    Returns:
        The matplotlib Figure instance.
    """
    import matplotlib.pyplot as plt

    machs = [p.mach for p in points]
    fig, (ax_cn, ax_sm) = plt.subplots(2, 1, figsize=(8.0, 7.0), sharex=True)

    ax_cn.plot(machs, [p.ackeret_fin_cn_alpha for p in points], lw=2.0, label="Ackeret")
    ax_cn.plot(machs, [p.barrowman_fin_cn_alpha for p in points], lw=2.0, ls="--", label="Barrowman")
    ax_cn.set_ylim(bottom=0.0)
    ax_cn.set_ylabel("Tail fin CN_alpha [1/rad]")
    ax_cn.set_title("Tail fin normal-force slope")

    ax_sm.plot(machs, [p.ackeret_static_margin for p in points], lw=2.0, label="Ackeret")
    ax_sm.plot(machs, [p.barrowman_static_margin for p in points], lw=2.0, ls="--", label="Barrowman")
    ax_sm.axhline(0.0, color="k", lw=0.8)
    ax_sm.set_xlabel("Mach number [-]")
    ax_sm.set_ylabel("Static margin [cal]")
    ax_sm.set_title("Static margin (positive is stable)")

    for ax in (ax_cn, ax_sm):
        ax.axvline(run_mach, color="tab:gray", lw=0.8, ls=":", label="Run Mach")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)

    fig.tight_layout()
    return fig


class AckeretFinAnalysis(BaseAnalysis[AckeretFinResults]):
    """Supersonic static margin with Ackeret fins, compared with Barrowman.

    Example:
        analysis = AckeretFinAnalysis()
        analysis.setup(vehicle, mach=2.5)
        results = analysis.execute()
        gap = results.static_margin - results.barrowman_static_margin
    """

    fidelity = FidelityLevel.LEVEL_0

    DEFAULT_MACH: ClassVar[float] = 2.0

    #: Below this Mach number linear supersonic theory is poor [-].
    MIN_RELIABLE_MACH: ClassVar[float] = 1.2

    #: Tail-fin CP gap between the methods that the run reports [cal].
    CP_DIFFERENCE_WARNING: ClassVar[float] = 1.0

    #: Mach sweep for the comparison figure.
    SWEEP_MACH_MIN: ClassVar[float] = 1.2
    SWEEP_MACH_MAX: ClassVar[float] = 4.0
    SWEEP_POINTS: ClassVar[int] = 57

    def __init__(self, name: str = "ackeret_fin_check") -> None:
        super().__init__(name)
        self._geometry: RocketGeometry | None = None
        self._mach = self.DEFAULT_MACH
        self._assumptions: tuple[str, ...] = ()

    @property
    def geometry(self) -> RocketGeometry:
        """Geometry bound by :meth:`setup`.

        Raises:
            RuntimeError: Before :meth:`setup`.
        """
        if self._geometry is None:
            raise RuntimeError(f"Analysis '{self.name}' has not been setup yet.")
        return self._geometry

    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        body_name: str | None = None,
        mach: float = DEFAULT_MACH,
        cg_from_nose: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Resolve the geometry and the evaluation Mach number.

        Args:
            vehicle: Vehicle with one axisymmetric body and at least one fin set.
            body_name: Body to use if the vehicle has more than one.
            mach: Evaluation Mach number (> 1).
            cg_from_nose: Center of gravity [m]. Defaults to the vehicle's.
            **kwargs: Not accepted; present for the ``BaseAnalysis`` signature.

        Raises:
            TypeError: If an unknown setting is passed.
            ValueError: If ``mach <= 1`` or the vehicle lacks what the method needs.
        """
        if kwargs:
            raise TypeError(f"Unknown settings for '{self.name}': {sorted(kwargs)}")
        if mach <= 1.0:
            raise ValueError(f"Ackeret theory needs a supersonic Mach number, got {mach}")

        geometry = geometry_from_vehicle(vehicle, body_name=body_name, cg_from_nose=cg_from_nose)
        assumptions = geometry_assumptions(vehicle, geometry)
        if mach < self.MIN_RELIABLE_MACH:
            assumptions.append(
                f"Mach {mach:g} is below {self.MIN_RELIABLE_MACH:g}: linear supersonic theory "
                "is poor close to Mach 1."
            )
        for fins in geometry.fin_sets:
            normal_mach = mach * math.cos(math.radians(fins.sweep))
            if normal_mach < 1.0:
                assumptions.append(
                    f"Fin set '{fins.name}' has a subsonic leading edge (M cos(sweep) = "
                    f"{normal_mach:.2f}): 2-D Ackeret theory overpredicts its slope."
                )

        self._geometry = geometry
        self._mach = mach
        self._assumptions = tuple(assumptions)
        self.logger.info(
            "Configured Ackeret fin check for vehicle '%s' (M=%.2f, CG=%.3f m)",
            vehicle.name,
            mach,
            geometry.cg_from_nose,
        )
        for assumption in self._assumptions:
            self.logger.warning(assumption)

    def _compute(self, **kwargs: Any) -> AckeretFinResults:
        """Evaluate both build-ups at the evaluation Mach number."""
        geometry = self.geometry
        fin_sets, components = ackeret_build_up(geometry, self._mach)
        cn_alpha, cp = _cp(components)
        barrowman = compute_stability_at_mach(geometry, self._mach)
        barrowman_tail_cp = next(
            c.x_cp for c in barrowman.components if c.name == geometry.tail_fins.name
        )
        results = AckeretFinResults(
            name=self.name,
            fidelity=self.fidelity,
            geometry=geometry,
            mach=self._mach,
            fin_sets=fin_sets,
            components=components,
            cn_alpha=cn_alpha,
            cp=cp,
            cg=geometry.cg_from_nose,
            static_margin=(cp - geometry.cg_from_nose) / geometry.d_ref,
            barrowman_cp=barrowman.x_cp,
            barrowman_static_margin=barrowman.static_margin,
            tail_fin_cp_difference=(fin_sets[-1].x_cp - barrowman_tail_cp) / geometry.d_ref,
            assumptions=self._assumptions,
        )
        self.logger.info(
            "Ackeret: CN_alpha=%.3f /rad, CP=%.3f m, SM=%.2f cal; Barrowman: CP=%.3f m, SM=%.2f cal",
            results.cn_alpha,
            results.cp,
            results.static_margin,
            results.barrowman_cp,
            results.barrowman_static_margin,
        )
        return results

    def validate_results(self, results: AckeretFinResults) -> bool:
        """Check that the slopes are positive and the CP lies on the vehicle.

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        if not all(math.isfinite(value) for value in results.scalars().values()):
            return False
        if any(c.cn_alpha < 0.0 for c in results.components) or results.cn_alpha <= 0.0:
            return False
        aft_end = max(
            results.geometry.total_length,
            *(f.root_le_x + f.sweep_length + f.tip_chord for f in results.geometry.fin_sets),
        )
        return 0.0 <= results.cp <= aft_end
