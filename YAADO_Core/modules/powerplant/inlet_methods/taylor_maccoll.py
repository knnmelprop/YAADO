"""Single-cone external-compression inlet with the Taylor-Maccoll conical shock.

Chain at one flight Mach number:

    1. Attached conical shock on the spike, from the Taylor-Maccoll equation
       (Anderson, *Modern Compressible Flow*, 3rd ed., Ch. 10).
    2. Terminal normal shock at the Mach number just behind the conical shock.
       The flow compresses further toward the cone surface, so this is the
       conservative end of the conical flow field.
    3. Subsonic-diffuser total-pressure loss.

A spike too blunt for an attached shock at the flight Mach number is bounded by a
normal (bow) shock at the flight Mach number. The recovery is compared with the
MIL-E-5007D reference ``1 - 0.075 (M - 1)^1.35``.
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import astuple, fields
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq, minimize_scalar

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from YAADO_Core.ComponentStore import RAMJET_COMPONENTS
from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.constants import GAMMA_AIR
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.powerplant.containers import (
    ConicalInletResults,
    ConicalShock,
    InletMachPoint,
)

#: Smallest and largest offsets of the shock-angle scan from the Mach angle [rad].
#: The cone angle grows roughly with the square root of the offset, so a
#: geometric scan resolves thin cones (about 1 deg at Mach 2 for 1e-6 rad).
_SCAN_OFFSET_MIN: float = 1e-6
_SCAN_GEOMETRIC_POINTS: int = 25
_SCAN_LINEAR_POINTS: int = 60
_SCAN_SPLIT_OFFSET: float = 0.02
_SHOCK_ANGLE_MAX: float = math.radians(89.0)


def mil_e_5007d_recovery(mach: float) -> float:
    """MIL-E-5007D reference total-pressure recovery (1 for ``mach <= 1``)."""
    if mach <= 1.0:
        return 1.0
    return 1.0 - 0.075 * (mach - 1.0) ** 1.35


def _theta_from_beta(mach1: float, beta_rad: float, gamma: float) -> float:
    """theta-beta-Mach flow deflection for an oblique shock."""
    s = math.sin(beta_rad)
    num = mach1 * mach1 * s * s - 1.0
    den = mach1 * mach1 * (gamma + math.cos(2.0 * beta_rad)) + 2.0
    return math.atan(2.0 / math.tan(beta_rad) * num / den)


def _pt_ratio_normal(mach_n: float, gamma: float) -> float:
    """Total-pressure ratio across a normal shock of upstream normal Mach ``mach_n``."""
    m2 = mach_n * mach_n
    return (
        ((gamma + 1.0) * m2 / ((gamma - 1.0) * m2 + 2.0)) ** (gamma / (gamma - 1.0))
        * ((gamma + 1.0) / (2.0 * gamma * m2 - (gamma - 1.0))) ** (1.0 / (gamma - 1.0))
    )


def _mach_behind_normal(mach_n: float, gamma: float) -> float:
    """Normal Mach number behind a normal shock."""
    m2 = mach_n * mach_n
    return math.sqrt((1.0 + 0.5 * (gamma - 1.0) * m2) / (gamma * m2 - 0.5 * (gamma - 1.0)))


def oblique_shock(mach1: float, beta_rad: float, gamma: float) -> tuple[float, float, float]:
    """Oblique-shock deflection [rad], downstream Mach and total-pressure ratio."""
    m1n = mach1 * math.sin(beta_rad)
    delta = _theta_from_beta(mach1, beta_rad, gamma)
    mach2 = _mach_behind_normal(m1n, gamma) / math.sin(beta_rad - delta)
    return delta, mach2, _pt_ratio_normal(m1n, gamma)


def normal_shock(mach: float, gamma: float) -> tuple[float, float]:
    """Normal-shock downstream Mach and total-pressure ratio (no shock for ``mach <= 1``)."""
    if mach <= 1.0:
        return mach, 1.0
    return _mach_behind_normal(mach, gamma), _pt_ratio_normal(mach, gamma)


def _mach_from_speed(speed: float, gamma: float) -> float:
    """Mach number from the speed ``V / V_max``."""
    return math.sqrt(2.0 / (gamma - 1.0) * speed * speed / (1.0 - speed * speed))


def _tm_rhs(theta: float, y: np.ndarray, gamma: float) -> list[float]:
    """Taylor-Maccoll equation in ``V_r``, ``V_theta`` (speeds over ``V_max``)."""
    v_r, v_t = y
    a2 = 0.5 * (gamma - 1.0) * (1.0 - v_r * v_r - v_t * v_t)
    dv_t = (v_r * v_t * v_t - a2 * (2.0 * v_r + v_t / math.tan(theta))) / (a2 - v_t * v_t)
    return [v_t, dv_t]


def cone_for_shock_angle(
    mach1: float, beta_rad: float, gamma: float
) -> tuple[float, float] | None:
    """Cone half-angle [rad] and cone-surface Mach for a given conical-shock angle.

    Integrates the Taylor-Maccoll equation from the shock toward the axis until
    ``V_theta = 0``, where the flow is parallel to the cone surface.

    Returns:
        ``(cone_half_angle, mach_cone_surface)``, or None if the flow never turns
        parallel before the axis.
    """
    delta, mach2, _ = oblique_shock(mach1, beta_rad, gamma)
    speed = 1.0 / math.sqrt(1.0 + 2.0 / ((gamma - 1.0) * mach2 * mach2))
    y0 = [speed * math.cos(beta_rad - delta), -speed * math.sin(beta_rad - delta)]

    def parallel_flow(theta: float, y: np.ndarray, gamma: float) -> float:
        return float(y[1])

    setattr(parallel_flow, "terminal", True)  # noqa: B010
    setattr(parallel_flow, "direction", 1)  # noqa: B010
    sol = solve_ivp(
        _tm_rhs, [beta_rad, 1e-6], y0, args=(gamma,), events=parallel_flow,
        max_step=0.02, rtol=1e-8, atol=1e-11,
    )
    if sol.t_events[0].size == 0:
        return None
    return float(sol.t_events[0][0]), _mach_from_speed(float(sol.y_events[0][0][0]), gamma)


def _shock_angle_scan(mach1: float) -> np.ndarray:
    """Shock angles from just above the Mach angle to 89 deg, dense near the Mach angle."""
    mach_angle = math.asin(1.0 / mach1)
    near = mach_angle + np.geomspace(_SCAN_OFFSET_MIN, _SCAN_SPLIT_OFFSET, _SCAN_GEOMETRIC_POINTS)
    far = np.linspace(mach_angle + _SCAN_SPLIT_OFFSET, _SHOCK_ANGLE_MAX, _SCAN_LINEAR_POINTS)
    return np.concatenate([near[:-1], far])


def max_attached_cone_half_angle(mach1: float, gamma: float = GAMMA_AIR) -> float:
    """Largest cone half-angle [rad] with an attached conical shock at ``mach1``."""
    betas = _shock_angle_scan(mach1)
    cones = [cone_for_shock_angle(mach1, float(b), gamma) for b in betas]
    angles = [-1.0 if c is None else c[0] for c in cones]
    i = int(np.argmax(angles))
    lo, hi = float(betas[max(i - 1, 0)]), float(betas[min(i + 1, len(betas) - 1)])

    def negative_cone_angle(beta: float) -> float:
        cone = cone_for_shock_angle(mach1, beta, gamma)
        return 0.0 if cone is None else -cone[0]

    best = minimize_scalar(negative_cone_angle, bounds=(lo, hi), method="bounded",
                           options={"xatol": 1e-7})
    return max(angles[i], -float(best.fun))


def solve_conical_shock(
    mach1: float, cone_half_angle_rad: float, gamma: float = GAMMA_AIR
) -> ConicalShock | None:
    """Weak attached conical shock on a cone of the given half-angle.

    The scan starts just above the Mach angle, so the first crossing is the weak
    solution, also for thin cones.

    Args:
        mach1: Freestream Mach number (> 1).
        cone_half_angle_rad: Cone half-angle [rad].
        gamma: Ratio of specific heats.

    Returns:
        The shock, or None if no attached shock exists (detached bow shock).
    """
    def gap(beta: float) -> float:
        cone = cone_for_shock_angle(mach1, beta, gamma)
        return (-1.0 if cone is None else cone[0]) - cone_half_angle_rad

    betas = _shock_angle_scan(mach1)
    previous: tuple[float, float] | None = None
    for b in betas:
        beta = float(b)
        value = gap(beta)
        if previous is not None and -1.0 < value < previous[1]:
            return None  # past the largest attached cone without a crossing
        if previous is not None and previous[1] < 0.0 <= value:
            root = brentq(gap, previous[0], beta, xtol=1e-10)
            surface = cone_for_shock_angle(mach1, root, gamma)
            _, mach2, pt_ratio = oblique_shock(mach1, root, gamma)
            return ConicalShock(
                shock_angle=math.degrees(root),
                mach_behind_shock=mach2,
                mach_cone_surface=mach2 if surface is None else surface[1],
                pt_ratio=pt_ratio,
            )
        previous = (beta, value)
    return None


def inlet_recovery(
    mach: float, cone_half_angle_deg: float, pt_diffuser: float, gamma: float = GAMMA_AIR
) -> tuple[ConicalShock | None, float, float]:
    """Inlet recovery chain at one flight Mach number.

    Returns:
        The conical shock (None if detached), the normal-shock total-pressure
        ratio, and the overall recovery pt2/pt0.
    """
    shock = solve_conical_shock(mach, math.radians(cone_half_angle_deg), gamma)
    if shock is None:
        _, pt_normal = normal_shock(mach, gamma)
        return None, pt_normal, pt_normal * pt_diffuser
    _, pt_normal = normal_shock(shock.mach_behind_shock, gamma)
    return shock, pt_normal, shock.pt_ratio * pt_normal * pt_diffuser


def run_mach_sweep(results: ConicalInletResults) -> list[InletMachPoint]:
    """Recovery of the run's spike from ``SWEEP_MACH_MIN`` to 1.5 times the run Mach."""
    machs = np.linspace(
        ConicalInletAnalysis.SWEEP_MACH_MIN,
        max(1.5 * results.mach, ConicalInletAnalysis.SWEEP_MACH_MIN + 1.0),
        ConicalInletAnalysis.SWEEP_POINTS,
    )
    points = []
    for m in machs:
        mach = float(m)
        shock, _, recovery = inlet_recovery(mach, results.cone_half_angle, results.pt_diffuser)
        points.append(InletMachPoint(mach, recovery, mil_e_5007d_recovery(mach), shock is not None))
    return points


def format_mach_sweep_csv(points: list[InletMachPoint]) -> str:
    """CSV text of the recovery sweep."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(f.name for f in fields(InletMachPoint))
    writer.writerows(astuple(p) for p in points)
    return buffer.getvalue()


def plot_recovery_vs_mach(points: list[InletMachPoint], results: ConicalInletResults) -> Figure:
    """Plot inlet recovery and the MIL-E-5007D reference against Mach number.

    Args:
        points: Output of :func:`run_mach_sweep`.
        results: Results of the run, marked on the plot.

    Returns:
        The matplotlib Figure instance.
    """
    import matplotlib.pyplot as plt

    machs = [p.mach for p in points]
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.plot(machs, [p.recovery for p in points], lw=2.0,
            label=f"{results.cone_half_angle:g} deg spike")
    ax.plot(machs, [p.mil_e_5007d_recovery for p in points], ls="--", label="MIL-E-5007D")
    detached = [p.mach for p in points if not p.attached]
    if detached:
        ax.axvspan(min(detached), max(detached), color="tab:red", alpha=0.1,
                   label="Detached shock (normal-shock bound)")
    ax.plot(results.mach, results.recovery, "o", color="k", label="Run")
    ax.set_ylim(0.0, 1.05)
    ax.set_xlabel("Flight Mach number [-]")
    ax.set_ylabel("Total-pressure recovery pt2/pt0 [-]")
    ax.set_title("Single-cone inlet recovery")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


class ConicalInletAnalysis(BaseAnalysis[ConicalInletResults]):
    """Recovery of a single-cone external-compression ramjet inlet.

    Example:
        analysis = ConicalInletAnalysis()
        analysis.setup(vehicle, cone_half_angle_deg=21.0)
        results = analysis.execute()
        recovery = results.recovery
    """

    fidelity = FidelityLevel.LEVEL_0

    #: Placeholder subsonic-diffuser total-pressure ratio; results flag its use.
    DEFAULT_PI_DIFFUSER: ClassVar[float] = 0.97

    #: Margin to shock detachment below which the run warns [deg].
    DETACHMENT_MARGIN_WARNING_DEG: ClassVar[float] = 6.0

    SWEEP_MACH_MIN: ClassVar[float] = 1.2
    SWEEP_POINTS: ClassVar[int] = 17

    def __init__(self, name: str = "conical_inlet") -> None:
        super().__init__(name)
        self._mach = 0.0
        self._cone_half_angle = 0.0
        self._pi_diffuser = self.DEFAULT_PI_DIFFUSER
        self._assumptions: list[str] = []

    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        engine_name: str | None = None,
        mach: float | None = None,
        cone_half_angle_deg: float | None = None,
        pi_diffuser: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Resolve the ramjet's spike and the flight condition.

        Args:
            vehicle: Vehicle with a ramjet propulsion component.
            engine_name: Ramjet to use if the vehicle has more than one.
            mach: Flight Mach number (> 1). Defaults to the ramjet's ``design_mach``.
            cone_half_angle_deg: Spike half-angle [deg]. Defaults to the ramjet's
                ``spike_half_angle``.
            pi_diffuser: Subsonic-diffuser total-pressure ratio. Defaults to a
                placeholder that the results flag.
            **kwargs: Not accepted; present for the ``BaseAnalysis`` signature.

        Raises:
            TypeError: If an unknown setting is passed.
            ValueError: If the vehicle has no ramjet, no spike angle is known, or a
                setting is out of range.
        """
        if kwargs:
            raise TypeError(f"Unknown settings for '{self.name}': {sorted(kwargs)}")
        engine = vehicle.find_single_component(RAMJET_COMPONENTS, engine_name)

        cone = engine.spike_half_angle if cone_half_angle_deg is None else cone_half_angle_deg
        if cone is None:
            raise ValueError(
                f"Vehicle '{vehicle.name}': set spike_half_angle on the ramjet or pass "
                "cone_half_angle_deg."
            )
        if not 0.0 < cone < 90.0:
            raise ValueError(f"cone_half_angle_deg must be in (0, 90), got {cone}")
        flight_mach = engine.design_mach if mach is None else mach
        if flight_mach <= 1.0:
            raise ValueError(f"The conical shock needs a supersonic Mach number, got {flight_mach}")

        assumptions: list[str] = []
        if pi_diffuser is None:
            pi_diffuser = self.DEFAULT_PI_DIFFUSER
            assumptions.append(
                f"Subsonic-diffuser pressure ratio is a placeholder ({pi_diffuser:g})."
            )
        elif not 0.0 < pi_diffuser <= 1.0:
            raise ValueError(f"pi_diffuser must be in (0, 1], got {pi_diffuser}")

        self._mach = flight_mach
        self._cone_half_angle = cone
        self._pi_diffuser = pi_diffuser
        self._assumptions = assumptions
        self.logger.info(
            "Configured conical inlet for vehicle '%s' (M=%.2f, spike half-angle=%.1f deg)",
            vehicle.name,
            flight_mach,
            cone,
        )

    def _compute(self, **kwargs: Any) -> ConicalInletResults:
        """Solve the shock chain at the flight Mach number."""
        shock, pt_normal, recovery = inlet_recovery(
            self._mach, self._cone_half_angle, self._pi_diffuser
        )
        max_angle = math.degrees(max_attached_cone_half_angle(self._mach))
        reference = mil_e_5007d_recovery(self._mach)

        assumptions = list(self._assumptions)
        if shock is None:
            assumptions.append(
                f"Detached shock: the {self._cone_half_angle:g} deg spike exceeds the attached "
                f"limit of {max_angle:.1f} deg at Mach {self._mach:g}; recovery is the "
                "normal-shock bound, and the inlet will spill and may buzz."
            )
        elif max_angle - self._cone_half_angle < self.DETACHMENT_MARGIN_WARNING_DEG:
            assumptions.append(
                f"Only {max_angle - self._cone_half_angle:.1f} deg from shock detachment: "
                "strong conical shock, sensitive to Mach and angle of attack."
            )
        if recovery < reference:
            assumptions.append(
                f"Recovery {recovery:.3f} is below the MIL-E-5007D reference {reference:.3f}."
            )

        results = ConicalInletResults(
            name=self.name,
            fidelity=self.fidelity,
            mach=self._mach,
            cone_half_angle=self._cone_half_angle,
            max_attached_half_angle=max_angle,
            shock=shock,
            pt_normal_shock=pt_normal,
            pt_diffuser=self._pi_diffuser,
            recovery=recovery,
            mil_e_5007d_recovery=reference,
            recovery_margin=recovery - reference,
            assumptions=tuple(assumptions),
        )
        self.logger.info(
            "Recovery %.4f (MIL-E-5007D %.4f), shock angle %s deg",
            recovery,
            reference,
            "detached" if shock is None else f"{shock.shock_angle:.2f}",
        )
        return results

    def validate_results(self, results: ConicalInletResults) -> bool:
        """Check that every pressure ratio lies in (0, 1] and the shock is weak.

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        ratios = [results.pt_normal_shock, results.pt_diffuser, results.recovery]
        if results.shock is not None:
            ratios.append(results.shock.pt_ratio)
            if results.shock.mach_behind_shock <= 1.0:
                return False
        return all(0.0 < r <= 1.0 + 1e-12 for r in ratios)
