"""Barrowman static stability of a slender finned rocket.

Component build-up of the normal-force-curve slope ``CN_alpha`` and the center of
pressure (CP), after Barrowman and Barrowman, *The Theoretical Prediction of the
Center of Pressure*, NARAM-8, 1966:

    nose      CN_alpha = 2 * (d_base / d_ref)^2,   CP = k_nose * L_nose
    shoulder  CN_alpha = 2 * (1 - (d_base / d_ref)^2), at the nose base (a step)
    fins      CN_alpha = K_fb * 4 N (s/d)^2 / (1 + sqrt(1 + (2 l_F / (C_r + C_t))^2))
              K_fb = 1 + R / (s + R), l_F = length of the fin mid-chord line

Every fin set of the vehicle contributes, so canards and mid-body wings shift the
CP forward. Only the fin slope depends on Mach: Prandtl-Glauert below Mach 0.8,
linearized supersonic theory above Mach 1.2 and a linear bridge in between. The
method is validated for subsonic flight; supersonic values are estimates only.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from YAADO_Core.ComponentStore import AERO_COMPONENTS, BODY_COMPONENTS, FIN_COMPONENTS
from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.stability_control.containers import (
    BarrowmanStabilityResults,
    ComponentContribution,
    FinSetGeometry,
    NoseType,
    RocketGeometry,
    StabilityResult,
)


def geometry_from_vehicle(
    vehicle: BaseVehicleConfig,
    *,
    body_name: str | None = None,
    cg_from_nose: float | None = None,
) -> RocketGeometry:
    """Build the Barrowman geometry from a vehicle configuration.

    Every fin set takes part. A fin set without ``root_le_from_nose`` sits flush
    with the aft end of the body; at most one fin set may rely on that.

    Args:
        vehicle: Vehicle with one axisymmetric body and at least one fin set.
        body_name: Body to use if the vehicle has more than one.
        cg_from_nose: Center of gravity [m]. Defaults to ``vehicle.mass_properties``,
            then to the body's own mass properties.

    Returns:
        The rocket geometry.

    Raises:
        ValueError: If a component or field the method needs is missing, if the
            nose base is wider than the body, or if the body is too stubby for
            slender-body theory.
    """
    body = vehicle.find_single_component(BODY_COMPONENTS, body_name)
    if body.nose_length is None:
        raise ValueError(f"Vehicle '{vehicle.name}': set nose_length on the body.")
    nose_base_diameter = body.diameter if body.nose_diameter is None else body.nose_diameter
    if nose_base_diameter > body.diameter:
        raise ValueError(
            f"Vehicle '{vehicle.name}': nose_diameter {nose_base_diameter} m is wider than "
            f"the body ({body.diameter} m); a flare is not modeled."
        )
    if body.length / body.diameter < BarrowmanStabilityAnalysis.MIN_FINENESS_RATIO:
        raise ValueError(
            f"Vehicle '{vehicle.name}': length/diameter {body.length / body.diameter:.1f} is "
            f"below {BarrowmanStabilityAnalysis.MIN_FINENESS_RATIO:g}; slender-body theory "
            "does not apply."
        )

    if cg_from_nose is None:
        mass = vehicle.mass_properties if vehicle.mass_properties is not None else body.mass
        if mass is None:
            raise ValueError(
                f"Vehicle '{vehicle.name}': set [mass_properties] cg_from_nose or pass cg_from_nose."
            )
        cg_from_nose = mass.cg_from_nose

    fin_components = vehicle.get_components_by_type(FIN_COMPONENTS)
    if not fin_components:
        raise ValueError(f"Vehicle '{vehicle.name}' has no fin set; Barrowman needs one.")
    unplaced = sorted(n for n, f in fin_components.items() if f.root_le_from_nose is None)
    if len(unplaced) > 1:
        raise ValueError(
            f"Vehicle '{vehicle.name}': set root_le_from_nose on fin sets {', '.join(unplaced)}; only "
            "one fin set can default to the aft end of the body."
        )

    fin_sets: list[FinSetGeometry] = []
    for name, fins in fin_components.items():
        if fins.chord_root is None or fins.chord_tip is None:
            raise ValueError(f"Vehicle '{vehicle.name}': set chord_root and chord_tip on '{name}'.")
        root_le_x = (
            body.length - fins.chord_root
            if fins.root_le_from_nose is None
            else fins.root_le_from_nose
        )
        if not 0.0 <= root_le_x < body.length:
            raise ValueError(
                f"Vehicle '{vehicle.name}': fin set '{name}' root leading edge at {root_le_x} m "
                f"is outside the body (0 to {body.length} m)."
            )
        fin_sets.append(
            FinSetGeometry(
                name=name,
                count=fins.count,
                span=fins.span,
                root_chord=fins.chord_root,
                tip_chord=fins.chord_tip,
                sweep=fins.sweep,
                root_le_x=root_le_x,
            )
        )

    return RocketGeometry(
        d_ref=body.diameter,
        nose_type=body.nose_type,
        nose_length=body.nose_length,
        nose_base_diameter=nose_base_diameter,
        total_length=body.length,
        cg_from_nose=cg_from_nose,
        fin_sets=tuple(sorted(fin_sets, key=lambda f: f.root_le_x)),
    )


def nose_cn_alpha_and_cp(geometry: RocketGeometry) -> tuple[float, float]:
    """Nose ``CN_alpha`` [1/rad] and CP [m from the nose tip]."""
    cn_alpha = 2.0 * (geometry.nose_base_diameter / geometry.d_ref) ** 2
    x_cp = BarrowmanStabilityAnalysis.NOSE_CP_FACTORS[geometry.nose_type] * geometry.nose_length
    return cn_alpha, x_cp


def transition_cn_alpha_and_cp(geometry: RocketGeometry) -> tuple[float, float]:
    """Shoulder ``CN_alpha`` [1/rad] and CP [m] for a nose base narrower than the body.

    The shoulder is a step at the nose base, the zero-length limit of Barrowman's
    conical transition. A nose as wide as the body gives zero.
    """
    cn_alpha = 2.0 * (1.0 - (geometry.nose_base_diameter / geometry.d_ref) ** 2)
    return cn_alpha, geometry.nose_length


def fin_set_cn_alpha_and_cp(
    fins: FinSetGeometry, body_radius: float, d_ref: float
) -> tuple[float, float]:
    """Incompressible fin-set ``CN_alpha`` [1/rad] and CP [m from the nose tip].

    Args:
        fins: Fin set geometry.
        body_radius: Body radius at the fins [m].
        d_ref: Reference diameter [m].

    Returns:
        Tuple of (CN_alpha including body interference, x_cp).
    """
    s, cr, ct, x_r = fins.span, fins.root_chord, fins.tip_chord, fins.sweep_length
    mid_chord_line = math.hypot(s, x_r + 0.5 * ct - 0.5 * cr)

    k_fb = 1.0 + body_radius / (s + body_radius)
    cn_alpha = (
        k_fb
        * 4.0
        * fins.count
        * (s / d_ref) ** 2
        / (1.0 + math.sqrt(1.0 + (2.0 * mid_chord_line / (cr + ct)) ** 2))
    )
    x_from_root_le = x_r * (cr + 2.0 * ct) / (3.0 * (cr + ct)) + (
        cr + ct - cr * ct / (cr + ct)
    ) / 6.0
    return cn_alpha, fins.root_le_x + x_from_root_le


def fin_mach_correction_factor(mach: float) -> float:
    """Multiplier on the incompressible fin ``CN_alpha`` at a given Mach number.

    Prandtl-Glauert ``1/sqrt(1 - M^2)`` below ``MACH_SUBSONIC_LIMIT``; linearized
    supersonic ``(4/sqrt(M^2 - 1)) / (2 pi)`` above ``MACH_SUPERSONIC_LIMIT``; linear
    interpolation in between.

    Raises:
        ValueError: If ``mach`` is negative.
    """
    if mach < 0.0:
        raise ValueError(f"mach must be >= 0, got {mach}")

    lower = BarrowmanStabilityAnalysis.MACH_SUBSONIC_LIMIT
    upper = BarrowmanStabilityAnalysis.MACH_SUPERSONIC_LIMIT

    def subsonic(m: float) -> float:
        return 1.0 / math.sqrt(1.0 - m**2)

    def supersonic(m: float) -> float:
        return 4.0 / math.sqrt(m**2 - 1.0) / (2.0 * math.pi)

    if mach < lower:
        return subsonic(mach)
    if mach > upper:
        return supersonic(mach)
    frac = (mach - lower) / (upper - lower)
    return subsonic(lower) + frac * (supersonic(upper) - subsonic(lower))


def compute_stability_at_mach(geometry: RocketGeometry, mach: float) -> StabilityResult:
    """Total ``CN_alpha``, CP and static margin at one Mach number.

    Args:
        geometry: Rocket geometry.
        mach: Freestream Mach number (>= 0).

    Returns:
        The component build-up and its totals.
    """
    cn_nose, x_nose = nose_cn_alpha_and_cp(geometry)
    components = [ComponentContribution("nose", cn_nose, x_nose)]

    cn_shoulder, x_shoulder = transition_cn_alpha_and_cp(geometry)
    if cn_shoulder > 0.0:
        components.append(ComponentContribution("shoulder", cn_shoulder, x_shoulder))

    mach_factor = fin_mach_correction_factor(mach)
    for fins in geometry.fin_sets:
        cn_fin, x_fin = fin_set_cn_alpha_and_cp(fins, geometry.body_radius, geometry.d_ref)
        components.append(ComponentContribution(fins.name, cn_fin * mach_factor, x_fin))

    cn_alpha_total = sum(c.cn_alpha for c in components)
    x_cp = sum(c.cn_alpha * c.x_cp for c in components) / cn_alpha_total
    return StabilityResult(
        mach=mach,
        components=tuple(components),
        cn_alpha_total=cn_alpha_total,
        x_cp=x_cp,
        static_margin=(x_cp - geometry.cg_from_nose) / geometry.d_ref,
    )


def run_mach_sweep(geometry: RocketGeometry, mach_max: float) -> list[StabilityResult]:
    """Evaluate the build-up from Mach 0 to ``mach_max``."""
    machs = np.linspace(0.0, mach_max, BarrowmanStabilityAnalysis.SWEEP_POINTS)
    return [compute_stability_at_mach(geometry, float(m)) for m in machs]


def format_mach_sweep_csv(points: list[StabilityResult]) -> str:
    """CSV text of the Mach sweep: Mach, total ``CN_alpha``, CP and static margin."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["mach", "cn_alpha_total_per_rad", "x_cp_m", "static_margin_cal"])
    writer.writerows((p.mach, p.cn_alpha_total, p.x_cp, p.static_margin) for p in points)
    return buffer.getvalue()


def plot_cp_vs_mach(points: list[StabilityResult], geometry: RocketGeometry) -> Figure:
    """Plot the CP, the CG and the static margin against Mach number.

    Args:
        points: Output of :func:`run_mach_sweep`.
        geometry: Geometry the sweep used.

    Returns:
        The matplotlib Figure instance.
    """
    import matplotlib.pyplot as plt

    machs = [p.mach for p in points]
    lower = BarrowmanStabilityAnalysis.MACH_SUBSONIC_LIMIT
    upper = BarrowmanStabilityAnalysis.MACH_SUPERSONIC_LIMIT

    fig, (ax_cp, ax_sm) = plt.subplots(2, 1, figsize=(8.0, 7.0), sharex=True)

    ax_cp.plot(machs, [p.x_cp for p in points], color="tab:blue", lw=2.0, label="CP")
    ax_cp.axhline(geometry.cg_from_nose, color="tab:red", ls="--", label="CG")
    ax_cp.set_ylim(0.0, geometry.total_length)
    ax_cp.invert_yaxis()
    ax_cp.set_ylabel("Position from nose tip [m]")
    ax_cp.set_title("Center of pressure and center of gravity")

    ax_sm.plot(machs, [p.static_margin for p in points], color="tab:green", lw=2.0)
    ax_sm.axhline(0.0, color="k", lw=0.8)
    ax_sm.set_xlabel("Mach number [-]")
    ax_sm.set_ylabel("Static margin [cal]")
    ax_sm.set_title("Static margin (positive is stable)")

    for ax in (ax_cp, ax_sm):
        ax.axvspan(lower, upper, color="grey", alpha=0.15, label="Transonic bridge")
        if machs[-1] > upper:
            ax.axvspan(upper, machs[-1], color="tab:orange", alpha=0.08, label="Supersonic estimate")
        ax.set_xlim(0.0, machs[-1])
        ax.grid(True, alpha=0.3)
    ax_cp.legend(loc="best", fontsize=8)

    fig.tight_layout()
    return fig


class BarrowmanStabilityAnalysis(BaseAnalysis[BarrowmanStabilityResults]):
    """Barrowman center of pressure and static margin at one Mach number.

    Example:
        analysis = BarrowmanStabilityAnalysis()
        analysis.setup(vehicle, mach=0.5)
        results = analysis.execute()
        stable = results.static_margin > 0.0
    """

    fidelity = FidelityLevel.LEVEL_0

    #: Nose CP as a fraction of the nose length (Barrowman; the hemisphere value
    #: is the slender-body volume result ``L - V/A_base``).
    NOSE_CP_FACTORS: ClassVar[Mapping[NoseType, float]] = {
        "conical": 2.0 / 3.0,
        "ogive": 0.466,
        "hemispherical": 1.0 / 3.0,
    }

    #: Edges of the transonic bridge on the fin slope [-].
    MACH_SUBSONIC_LIMIT: ClassVar[float] = 0.8
    MACH_SUPERSONIC_LIMIT: ClassVar[float] = 1.2

    #: Below this length/diameter, slender-body theory is not valid [-].
    MIN_FINENESS_RATIO: ClassVar[float] = 5.0

    #: Design rule: static margin of at least this fraction of the body length.
    SM_REQUIRED_LENGTH_FRACTION: ClassVar[float] = 0.10

    DEFAULT_MACH: ClassVar[float] = 0.3

    #: Mach sweep for the CP-vs-Mach figure.
    SWEEP_MACH_MAX: ClassVar[float] = 2.0
    SWEEP_POINTS: ClassVar[int] = 81

    def __init__(self, name: str = "barrowman_stability") -> None:
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
            mach: Evaluation Mach number.
            cg_from_nose: Center of gravity [m]. Defaults to the vehicle's.
            sm_required: Required static margin [cal]. Defaults to
                ``SM_REQUIRED_LENGTH_FRACTION`` of the body length.
            **kwargs: Not accepted; present for the ``BaseAnalysis`` signature.

        Raises:
            TypeError: If an unknown setting is passed.
            ValueError: If the vehicle lacks what the method needs or a setting is
                out of range.
        """
        if kwargs:
            raise TypeError(f"Unknown settings for '{self.name}': {sorted(kwargs)}")
        if mach < 0.0:
            raise ValueError(f"mach must be >= 0, got {mach}")

        geometry = geometry_from_vehicle(vehicle, body_name=body_name, cg_from_nose=cg_from_nose)
        self._geometry = geometry
        self._mach = mach
        self._sm_required = (
            self.SM_REQUIRED_LENGTH_FRACTION * geometry.fineness_ratio
            if sm_required is None
            else sm_required
        )
        self._assumptions = self._list_assumptions(vehicle, geometry, mach)
        self.logger.info(
            "Configured Barrowman stability for vehicle '%s' (M=%.2f, CG=%.3f m, fin sets: %s)",
            vehicle.name,
            mach,
            geometry.cg_from_nose,
            ", ".join(f.name for f in geometry.fin_sets),
        )
        for assumption in self._assumptions:
            self.logger.warning(assumption)

    def _list_assumptions(
        self, vehicle: BaseVehicleConfig, geometry: RocketGeometry, mach: float
    ) -> tuple[str, ...]:
        """Modeling assumptions that this vehicle and Mach number need."""
        assumptions: list[str] = []
        fins = vehicle.get_components_by_type(FIN_COMPONENTS)
        for name, fin in fins.items():
            if fin.root_le_from_nose is None:
                assumptions.append(
                    f"Fin set '{name}' has no root_le_from_nose: placed flush with the aft end."
                )
        other_surfaces = sorted(set(vehicle.get_components_by_type(AERO_COMPONENTS)) - set(fins))
        if other_surfaces:
            assumptions.append(
                f"Lifting surfaces other than fins are ignored: {', '.join(other_surfaces)}."
            )
        if geometry.nose_base_diameter < geometry.d_ref:
            assumptions.append("Nose base narrower than the body: shoulder modeled as a step.")
        if mach > self.MACH_SUBSONIC_LIMIT:
            assumptions.append(
                f"Mach {mach:g} is above {self.MACH_SUBSONIC_LIMIT:g}: Barrowman is a subsonic "
                "method, so the result is an estimate."
            )
        return tuple(assumptions)

    def _compute(self, **kwargs: Any) -> BarrowmanStabilityResults:
        """Evaluate the build-up at the evaluation Mach number."""
        geometry = self.geometry
        point = compute_stability_at_mach(geometry, self._mach)
        results = BarrowmanStabilityResults(
            name=self.name,
            fidelity=self.fidelity,
            geometry=geometry,
            mach=self._mach,
            cn_alpha=point.cn_alpha_total,
            cp=point.x_cp,
            cg=geometry.cg_from_nose,
            static_margin=point.static_margin,
            sm_required=self._sm_required,
            margin=point.static_margin - self._sm_required,
            fineness_ratio=geometry.fineness_ratio,
            components=point.components,
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

    def validate_results(self, results: BarrowmanStabilityResults) -> bool:
        """Check that the slopes are positive and the CP lies on the vehicle.

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        if not all(math.isfinite(value) for value in results.scalars().values()):
            return False
        if results.cn_alpha <= 0.0 or any(c.cn_alpha < 0.0 for c in results.components):
            return False
        aft_end = max(
            results.geometry.total_length,
            *(f.root_le_x + f.sweep_length + f.tip_chord for f in results.geometry.fin_sets),
        )
        return 0.0 <= results.cp <= aft_end
