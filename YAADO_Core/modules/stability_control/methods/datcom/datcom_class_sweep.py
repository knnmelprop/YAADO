"""DATCOM-class supersonic static stability by component build-up.

An in-house build-up in the style of Missile DATCOM, not a wrapper around the
USAF Digital DATCOM program. All slopes refer to ``A_ref = pi d^2 / 4``.

Body: slender-body nose and shoulder terms, which do not depend on Mach number
(nose ``CN_alpha = 2 (d_base/d)^2`` with the CP for its shape). The viscous
cross-flow term grows with ``alpha^2`` and adds nothing to the slope at
``alpha = 0``.

Each fin set: the two exposed panels joined at the root form the exposed wing,
of aspect ratio ``AR = 2 s / c_mean``.

    a_2D      = 4 / beta,  beta = sqrt(M^2 - 1)            Ackeret section slope
    eta       = max(1/2, 1 - 1 / (2 beta AR))               Puckett rectangular tip loss
    CN_alpha  = K_fb * (N / 2) * a_2D * eta * A_panel / A_ref,  K_fb = 1 + R / (s + R)
    CP        = planform centroid, i.e. half the MAC at the MAC station

The slope is the supersonic slope of the Barrowman build-up; this method differs
by its supersonic fin CP and by staying in supersonic flow. The tip-loss factor
is exact for a rectangular wing with ``beta AR >= 1``; for swept or tapered
panels it is an approximation.
"""

from __future__ import annotations

import csv
import io
import math
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.stability_control.containers import (
    ComponentContribution,
    DatcomFinSlope,
    DatcomStabilityResults,
    FinSetGeometry,
    RocketGeometry,
)
from YAADO_Core.modules.stability_control.methods.barrowman.barrowman_stability import (
    BarrowmanStabilityAnalysis,
    geometry_assumptions,
    geometry_from_vehicle,
    nose_cn_alpha_and_cp,
    supersonic_fin_cn_alpha,
    supersonic_tip_loss,
    transition_cn_alpha_and_cp,
)


def datcom_fin_set(
    fins: FinSetGeometry, mach: float, body_radius: float, reference_area: float
) -> DatcomFinSlope:
    """Supersonic normal-force slope and CP of one fin set.

    The slope is the supersonic slope of the Barrowman build-up; the CP is the
    planform centroid instead of Barrowman's subsonic fin CP.

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
        raise ValueError(f"The DATCOM-class method needs a supersonic Mach number, got {mach}")

    tip_loss = supersonic_tip_loss(fins, mach)
    floor = BarrowmanStabilityAnalysis.TIP_LOSS_FLOOR
    cr, ct = fins.root_chord, fins.tip_chord
    mac = (2.0 / 3.0) * (cr + ct - cr * ct / (cr + ct))
    y_mac = (fins.span / 3.0) * (cr + 2.0 * ct) / (cr + ct)
    return DatcomFinSlope(
        name=fins.name,
        slope_2d=4.0 / math.sqrt(mach**2 - 1.0),
        exposed_aspect_ratio=2.0 * fins.span / fins.mean_chord,
        tip_loss_factor=max(floor, tip_loss),
        tip_loss_limited=tip_loss < floor,
        cn_alpha=supersonic_fin_cn_alpha(fins, body_radius, reference_area, mach),
        x_cp=fins.root_le_x + y_mac * math.tan(math.radians(fins.sweep)) + 0.5 * mac,
    )


def datcom_build_up(
    geometry: RocketGeometry, mach: float
) -> tuple[tuple[DatcomFinSlope, ...], tuple[ComponentContribution, ...]]:
    """Fin-set slopes and the whole-vehicle build-up at one Mach number."""
    fin_sets = tuple(
        datcom_fin_set(f, mach, geometry.body_radius, geometry.reference_area)
        for f in geometry.fin_sets
    )
    cn_nose, x_nose = nose_cn_alpha_and_cp(geometry)
    components = [ComponentContribution("nose", cn_nose, x_nose)]
    cn_shoulder, x_shoulder = transition_cn_alpha_and_cp(geometry)
    if cn_shoulder > 0.0:
        components.append(ComponentContribution("shoulder", cn_shoulder, x_shoulder))
    components.extend(ComponentContribution(f.name, f.cn_alpha, f.x_cp) for f in fin_sets)
    return fin_sets, tuple(components)


def total_cp(components: tuple[ComponentContribution, ...]) -> tuple[float, float]:
    """Total slope and slope-weighted CP of a build-up."""
    cn_alpha = sum(c.cn_alpha for c in components)
    return cn_alpha, sum(c.cn_alpha * c.x_cp for c in components) / cn_alpha


def run_mach_sweep(geometry: RocketGeometry, mach_max: float) -> list[tuple[float, float, float]]:
    """Total slope and CP from ``SWEEP_MACH_MIN`` to ``mach_max``.

    Returns:
        ``(mach, cn_alpha, x_cp)`` per point.
    """
    machs = np.linspace(
        DatcomStabilityAnalysis.SWEEP_MACH_MIN, mach_max, DatcomStabilityAnalysis.SWEEP_POINTS
    )
    points = []
    for m in machs:
        cn_alpha, x_cp = total_cp(datcom_build_up(geometry, float(m))[1])
        points.append((float(m), cn_alpha, x_cp))
    return points


def format_mach_sweep_csv(points: list[tuple[float, float, float]], geometry: RocketGeometry) -> str:
    """CSV text of the Mach sweep, with the static margin at the geometry's CG."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["mach", "cn_alpha_total_per_rad", "x_cp_m", "static_margin_cal"])
    writer.writerows(
        (m, cn, x, (x - geometry.cg_from_nose) / geometry.d_ref) for m, cn, x in points
    )
    return buffer.getvalue()


def plot_cp_vs_mach(points: list[tuple[float, float, float]], geometry: RocketGeometry) -> Figure:
    """Plot the supersonic CP and static margin against Mach number.

    Args:
        points: Output of :func:`run_mach_sweep`.
        geometry: Geometry the sweep used.

    Returns:
        The matplotlib Figure instance.
    """
    import matplotlib.pyplot as plt

    machs = [p[0] for p in points]
    cps = [p[2] for p in points]
    fig, (ax_cp, ax_sm) = plt.subplots(2, 1, figsize=(8.0, 7.0), sharex=True)

    ax_cp.plot(machs, cps, color="tab:blue", lw=2.0, label="CP")
    ax_cp.axhline(geometry.cg_from_nose, color="tab:red", ls="--", label="CG")
    ax_cp.set_ylim(0.0, geometry.total_length)
    ax_cp.invert_yaxis()
    ax_cp.set_ylabel("Position from nose tip [m]")
    ax_cp.set_title("Center of pressure and center of gravity")
    ax_cp.legend(loc="best", fontsize=8)

    ax_sm.plot(machs, [(x - geometry.cg_from_nose) / geometry.d_ref for x in cps], color="tab:green", lw=2.0)
    ax_sm.axhline(0.0, color="k", lw=0.8)
    ax_sm.set_xlabel("Mach number [-]")
    ax_sm.set_ylabel("Static margin [cal]")
    ax_sm.set_title("Static margin (positive is stable)")

    for ax in (ax_cp, ax_sm):
        ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


class DatcomStabilityAnalysis(BaseAnalysis[DatcomStabilityResults]):
    """DATCOM-class supersonic CP and static margin at one Mach number.

    Example:
        analysis = DatcomStabilityAnalysis()
        analysis.setup(vehicle, mach=2.5)
        results = analysis.execute()
        stable = results.static_margin > 0.0
    """

    fidelity = FidelityLevel.LEVEL_1

    DEFAULT_MACH: ClassVar[float] = 2.0

    #: Below this Mach number linear supersonic theory is poor [-].
    MIN_RELIABLE_MACH: ClassVar[float] = 1.2

    #: Design rule: static margin of at least this fraction of the body length.
    SM_REQUIRED_LENGTH_FRACTION: ClassVar[float] = 0.10

    #: Mach sweep for the CP-vs-Mach figure.
    SWEEP_MACH_MIN: ClassVar[float] = 1.2
    SWEEP_MACH_MAX: ClassVar[float] = 3.0
    SWEEP_POINTS: ClassVar[int] = 37

    def __init__(self, name: str = "datcom_class_stability") -> None:
        super().__init__(name)
        self._geometry: RocketGeometry | None = None
        self._mach = self.DEFAULT_MACH
        self._sm_required = 0.0
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
        sm_required: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Resolve the geometry and the evaluation settings.

        Args:
            vehicle: Vehicle with one axisymmetric body and at least one fin set.
            body_name: Body to use if the vehicle has more than one.
            mach: Evaluation Mach number (> 1).
            cg_from_nose: Center of gravity [m]. Defaults to the vehicle's.
            sm_required: Required static margin [cal]. Defaults to
                ``SM_REQUIRED_LENGTH_FRACTION`` of the body length.
            **kwargs: Not accepted; present for the ``BaseAnalysis`` signature.

        Raises:
            TypeError: If an unknown setting is passed.
            ValueError: If ``mach <= 1`` or the vehicle lacks what the method needs.
        """
        if kwargs:
            raise TypeError(f"Unknown settings for '{self.name}': {sorted(kwargs)}")
        if mach <= 1.0:
            raise ValueError(f"The DATCOM-class method needs a supersonic Mach number, got {mach}")

        geometry = geometry_from_vehicle(vehicle, body_name=body_name, cg_from_nose=cg_from_nose)
        assumptions = geometry_assumptions(vehicle, geometry)
        if mach < self.MIN_RELIABLE_MACH:
            assumptions.append(
                f"Mach {mach:g} is below {self.MIN_RELIABLE_MACH:g}: linear supersonic theory "
                "is poor close to Mach 1."
            )
        for fin in datcom_build_up(geometry, mach)[0]:
            if fin.tip_loss_limited:
                assumptions.append(
                    f"Fin set '{fin.name}': beta * AR < 1, so the tip-loss factor is held at "
                    f"{fin.tip_loss_factor:g} and its slope is approximate."
                )

        self._geometry = geometry
        self._mach = mach
        self._sm_required = (
            self.SM_REQUIRED_LENGTH_FRACTION * geometry.fineness_ratio
            if sm_required is None
            else sm_required
        )
        self._assumptions = tuple(assumptions)
        self.logger.info(
            "Configured DATCOM-class stability for vehicle '%s' (M=%.2f, CG=%.3f m)",
            vehicle.name,
            mach,
            geometry.cg_from_nose,
        )
        for assumption in self._assumptions:
            self.logger.warning(assumption)

    def _compute(self, **kwargs: Any) -> DatcomStabilityResults:
        """Evaluate the build-up at the evaluation Mach number."""
        geometry = self.geometry
        fin_sets, components = datcom_build_up(geometry, self._mach)
        cn_alpha, cp = total_cp(components)
        static_margin = (cp - geometry.cg_from_nose) / geometry.d_ref
        results = DatcomStabilityResults(
            name=self.name,
            fidelity=self.fidelity,
            geometry=geometry,
            mach=self._mach,
            fin_sets=fin_sets,
            components=components,
            cn_alpha=cn_alpha,
            cp=cp,
            cg=geometry.cg_from_nose,
            static_margin=static_margin,
            sm_required=self._sm_required,
            margin=static_margin - self._sm_required,
            assumptions=self._assumptions,
        )
        self.logger.info(
            "CN_alpha=%.3f /rad, CP=%.3f m, CG=%.3f m, static margin=%.2f cal (required %.2f)",
            results.cn_alpha,
            results.cp,
            results.cg,
            results.static_margin,
            results.sm_required,
        )
        return results

    def validate_results(self, results: DatcomStabilityResults) -> bool:
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
