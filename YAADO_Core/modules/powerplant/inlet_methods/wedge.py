"""Multi-ramp (2-D) external-compression inlet: oblique shocks, then a normal shock.

Chain at one flight Mach number (Anderson, *Modern Compressible Flow*, Ch. 3-4):

    1. ``n`` weak oblique shocks, each turning the flow by one ramp increment.
    2. A terminal normal shock at the Mach number after the last ramp.
    3. A subsonic-diffuser total-pressure loss.

The relations are exact for planar ramps and a conservative approximation for a
multi-cone spike. Without given ramp angles the analysis uses the Oswatitsch
optimum: every oblique shock has the same normal Mach number, chosen for the
highest recovery (Oswatitsch, NACA TM 1140; Seddon and Goldsmith, *Intake
Aerodynamics*, Sec. 4.3).
"""

from __future__ import annotations

import csv
import io
import math
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np
from scipy.optimize import brentq, minimize_scalar

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from YAADO_Core.ComponentStore import RAMJET_COMPONENTS
from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.constants import GAMMA_AIR
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.powerplant.containers import MultiShockInletResults, ShockChain
from YAADO_Core.modules.powerplant.inlet_methods.taylor_maccoll import (
    mil_e_5007d_recovery,
    normal_shock,
    oblique_shock,
)


def _theta_from_beta(mach1: float, beta_rad: float, gamma: float) -> float:
    """theta-beta-Mach relation (Anderson, Eq. 4.17)."""
    s = math.sin(beta_rad)
    num = mach1 * mach1 * s * s - 1.0
    den = mach1 * mach1 * (gamma + math.cos(2.0 * beta_rad)) + 2.0
    return math.atan(2.0 / math.tan(beta_rad) * num / den)


def theta_max_rad(mach1: float, gamma: float = GAMMA_AIR) -> tuple[float, float]:
    """Largest attached deflection and its shock angle at ``mach1``.

    Returns:
        ``(beta_at_theta_max, theta_max)`` [rad].
    """
    mu = math.asin(1.0 / mach1)
    result = minimize_scalar(
        lambda b: -_theta_from_beta(mach1, b, gamma),
        bounds=(mu + 1e-9, math.pi / 2.0 - 1e-9),
        method="bounded",
        options={"xatol": 1e-10},
    )
    return float(result.x), -float(result.fun)


def oblique_shock_beta_rad(
    mach1: float, theta_rad: float, gamma: float = GAMMA_AIR, weak: bool = True
) -> float | None:
    """Shock angle [rad] that turns the flow by ``theta_rad``.

    Returns:
        The weak (or strong) root, or None if ``theta_rad`` exceeds the attached limit.
    """
    beta_star, theta_max = theta_max_rad(mach1, gamma)
    if theta_rad > theta_max:
        return None
    mu = math.asin(1.0 / mach1)
    lo, hi = (mu + 1e-12, beta_star) if weak else (beta_star, math.pi / 2.0 - 1e-12)
    root: float = brentq(lambda b: _theta_from_beta(mach1, b, gamma) - theta_rad, lo, hi,
                         xtol=1e-12)
    return root


def shock_chain(
    mach: float, deflections_deg: tuple[float, ...], pi_diffuser: float, gamma: float = GAMMA_AIR
) -> ShockChain:
    """Recovery chain for given ramp deflections.

    A stage without an attached oblique shock ends the oblique compression; the
    normal shock then stands at that stage's Mach number.
    """
    current = mach
    stages = [mach]
    deflections: list[float] = []
    betas: list[float] = []
    pt_oblique: list[float] = []
    detached = False
    for theta in deflections_deg:
        beta = oblique_shock_beta_rad(current, math.radians(theta), gamma) if current > 1.0 else None
        if beta is None:
            detached = True
            break
        _, current, pt_ratio = oblique_shock(current, beta, gamma)
        deflections.append(theta)
        betas.append(math.degrees(beta))
        pt_oblique.append(pt_ratio)
        stages.append(current)
    _, pt_normal = normal_shock(current, gamma)
    return ShockChain(
        deflections=tuple(deflections),
        shock_angles=tuple(betas),
        mach_stages=tuple(stages),
        pt_oblique=tuple(pt_oblique),
        pt_normal=pt_normal,
        pt_diffuser=pi_diffuser,
        recovery=math.prod(pt_oblique) * pt_normal * pi_diffuser,
        detached=detached,
    )


def equal_normal_mach_deflections(
    mach: float, n_oblique: int, normal_mach: float, gamma: float = GAMMA_AIR
) -> tuple[float, ...] | None:
    """Ramp deflections [deg] for ``n_oblique`` weak shocks of the same normal Mach.

    Returns:
        The deflections, or None if a stage cannot carry a weak shock of that
        normal Mach number.
    """
    current = mach
    deflections = []
    for _ in range(n_oblique):
        if normal_mach >= current:
            return None
        beta = math.asin(normal_mach / current)
        beta_star, _ = theta_max_rad(current, gamma)
        if beta > beta_star:
            return None
        theta, current, _ = oblique_shock(current, beta, gamma)
        deflections.append(math.degrees(theta))
    return tuple(deflections)


def oswatitsch_chain(
    mach: float, n_oblique: int, pi_diffuser: float, gamma: float = GAMMA_AIR
) -> ShockChain:
    """Highest-recovery chain with ``n_oblique`` equal-normal-Mach oblique shocks."""
    if n_oblique == 0:
        return shock_chain(mach, (), pi_diffuser, gamma)

    def negative_recovery(normal_mach: float) -> float:
        deflections = equal_normal_mach_deflections(mach, n_oblique, normal_mach, gamma)
        if deflections is None:
            return 0.0
        return -shock_chain(mach, deflections, pi_diffuser, gamma).recovery

    grid = np.linspace(1.0 + 1e-6, mach - 1e-6, MultiShockInletAnalysis.OPTIMIZER_GRID_POINTS)
    values = [negative_recovery(float(m)) for m in grid]
    i = int(np.argmin(values))
    lo, hi = float(grid[max(i - 1, 0)]), float(grid[min(i + 1, len(grid) - 1)])
    best = minimize_scalar(negative_recovery, bounds=(lo, hi), method="bounded",
                           options={"xatol": 1e-8})
    best_mn = float(best.x) if best.fun <= values[i] else float(grid[i])
    deflections = equal_normal_mach_deflections(mach, n_oblique, best_mn, gamma)
    return shock_chain(mach, deflections or (), pi_diffuser, gamma)


def recovery_by_shock_count(
    mach: float, pi_diffuser: float, max_oblique: int
) -> list[tuple[int, float]]:
    """Optimum recovery for 0 to ``max_oblique`` oblique shocks at ``mach``."""
    return [(n, oswatitsch_chain(mach, n, pi_diffuser).recovery) for n in range(max_oblique + 1)]


def recovery_vs_mach(
    results: MultiShockInletResults,
) -> list[tuple[float, float, float]]:
    """Off-design recovery of the run's fixed ramps: ``(mach, recovery, MIL reference)``."""
    machs = np.linspace(
        MultiShockInletAnalysis.SWEEP_MACH_MIN,
        max(1.5 * results.mach, MultiShockInletAnalysis.SWEEP_MACH_MIN + 1.0),
        MultiShockInletAnalysis.SWEEP_POINTS,
    )
    chain = results.chain
    return [
        (float(m), shock_chain(float(m), chain.deflections, chain.pt_diffuser).recovery,
         mil_e_5007d_recovery(float(m)))
        for m in machs
    ]


def format_design_csv(
    by_count: list[tuple[int, float]], by_mach: list[tuple[float, float, float]]
) -> str:
    """CSV text of both design curves, one block each."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["n_oblique_shocks", "optimum_recovery"])
    writer.writerows(by_count)
    writer.writerow([])
    writer.writerow(["mach", "recovery_fixed_ramps", "mil_e_5007d_recovery"])
    writer.writerows(by_mach)
    return buffer.getvalue()


def plot_design_curves(
    by_count: list[tuple[int, float]],
    by_mach: list[tuple[float, float, float]],
    results: MultiShockInletResults,
) -> Figure:
    """Plot optimum recovery against shock count and the run's ramps against Mach.

    Args:
        by_count: Output of :func:`recovery_by_shock_count`.
        by_mach: Output of :func:`recovery_vs_mach`.
        results: Results of the run.

    Returns:
        The matplotlib Figure instance.
    """
    import matplotlib.pyplot as plt

    fig, (ax_n, ax_m) = plt.subplots(1, 2, figsize=(12.0, 4.8))

    ax_n.plot([c for c, _ in by_count], [r for _, r in by_count], "o-", lw=2.0,
              label="Oswatitsch optimum")
    ax_n.axhline(results.mil_e_5007d_recovery, color="tab:red", ls="--", label="MIL-E-5007D")
    ax_n.set_xlabel("Number of oblique shocks [-]")
    ax_n.set_ylabel("Total-pressure recovery pt2/pt0 [-]")
    ax_n.set_title(f"Recovery vs. shock count at Mach {results.mach:g}")

    ax_m.plot([m for m, _, _ in by_mach], [r for _, r, _ in by_mach], lw=2.0, label="Run ramps")
    ax_m.plot([m for m, _, _ in by_mach], [ref for _, _, ref in by_mach], ls="--",
              color="tab:red", label="MIL-E-5007D")
    ax_m.plot(results.mach, results.recovery, "o", color="k", label="Run")
    ax_m.set_xlabel("Flight Mach number [-]")
    ax_m.set_title("Fixed ramps off design")

    for ax in (ax_n, ax_m):
        ax.set_ylim(0.0, 1.05)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


class MultiShockInletAnalysis(BaseAnalysis[MultiShockInletResults]):
    """Recovery of a multi-ramp external-compression inlet at one flight Mach number.

    Example:
        analysis = MultiShockInletAnalysis()
        analysis.setup(vehicle, n_oblique_shocks=3)
        results = analysis.execute()
        ramps = results.chain.deflections
    """

    fidelity = FidelityLevel.LEVEL_0

    #: Placeholder subsonic-diffuser total-pressure ratio; results flag its use.
    DEFAULT_PI_DIFFUSER: ClassVar[float] = 0.97
    DEFAULT_N_OBLIQUE: ClassVar[int] = 3
    MAX_N_OBLIQUE: ClassVar[int] = 8

    OPTIMIZER_GRID_POINTS: ClassVar[int] = 40
    SWEEP_MACH_MIN: ClassVar[float] = 1.2
    SWEEP_POINTS: ClassVar[int] = 25

    def __init__(self, name: str = "multi_shock_inlet") -> None:
        super().__init__(name)
        self._mach = 0.0
        self._n_oblique = self.DEFAULT_N_OBLIQUE
        self._deflections: tuple[float, ...] | None = None
        self._pi_diffuser = self.DEFAULT_PI_DIFFUSER
        self._assumptions: list[str] = []

    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        engine_name: str | None = None,
        mach: float | None = None,
        n_oblique_shocks: int = DEFAULT_N_OBLIQUE,
        deflections_deg: tuple[float, ...] | None = None,
        pi_diffuser: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Resolve the flight condition and the ramp schedule.

        Args:
            vehicle: Vehicle with a ramjet propulsion component.
            engine_name: Ramjet to use if the vehicle has more than one.
            mach: Flight Mach number (> 1). Defaults to the ramjet's ``design_mach``.
            n_oblique_shocks: Number of oblique shocks for the optimum schedule.
            deflections_deg: Given ramp deflections [deg]; replaces the optimum.
            pi_diffuser: Subsonic-diffuser total-pressure ratio. Defaults to a
                placeholder that the results flag.
            **kwargs: Not accepted; present for the ``BaseAnalysis`` signature.

        Raises:
            TypeError: If an unknown setting is passed.
            ValueError: If the vehicle has no ramjet or a setting is out of range.
        """
        if kwargs:
            raise TypeError(f"Unknown settings for '{self.name}': {sorted(kwargs)}")
        engine = vehicle.find_single_component(RAMJET_COMPONENTS, engine_name)
        flight_mach = engine.design_mach if mach is None else mach
        if flight_mach <= 1.0:
            raise ValueError(f"External compression needs a supersonic Mach number, got {flight_mach}")
        if not 0 <= n_oblique_shocks <= self.MAX_N_OBLIQUE:
            raise ValueError(
                f"n_oblique_shocks must be in [0, {self.MAX_N_OBLIQUE}], got {n_oblique_shocks}"
            )
        if deflections_deg is not None and any(not 0.0 < d < 45.0 for d in deflections_deg):
            raise ValueError(f"Each deflection must be in (0, 45) deg, got {deflections_deg}")

        assumptions: list[str] = []
        if pi_diffuser is None:
            pi_diffuser = self.DEFAULT_PI_DIFFUSER
            assumptions.append(
                f"Subsonic-diffuser pressure ratio is a placeholder ({pi_diffuser:g})."
            )
        elif not 0.0 < pi_diffuser <= 1.0:
            raise ValueError(f"pi_diffuser must be in (0, 1], got {pi_diffuser}")

        self._mach = flight_mach
        self._n_oblique = n_oblique_shocks
        self._deflections = deflections_deg
        self._pi_diffuser = pi_diffuser
        self._assumptions = assumptions
        self.logger.info(
            "Configured multi-shock inlet for vehicle '%s' (M=%.2f, %s)",
            vehicle.name,
            flight_mach,
            f"ramps {deflections_deg} deg" if deflections_deg else f"{n_oblique_shocks} optimum ramps",
        )

    def _compute(self, **kwargs: Any) -> MultiShockInletResults:
        """Evaluate the given ramps or find the optimum schedule."""
        optimized = self._deflections is None
        chain = (
            oswatitsch_chain(self._mach, self._n_oblique, self._pi_diffuser)
            if self._deflections is None
            else shock_chain(self._mach, self._deflections, self._pi_diffuser)
        )
        reference = mil_e_5007d_recovery(self._mach)
        assumptions = list(self._assumptions)
        if chain.detached:
            assumptions.append(
                "A ramp exceeds the attached-shock limit at its local Mach number: the "
                "remaining compression is a normal shock, and the inlet will spill."
            )
        if chain.recovery < reference:
            assumptions.append(
                f"Recovery {chain.recovery:.3f} is below the MIL-E-5007D reference {reference:.3f}."
            )
        results = MultiShockInletResults(
            name=self.name,
            fidelity=self.fidelity,
            mach=self._mach,
            chain=chain,
            optimized=optimized,
            recovery=chain.recovery,
            mil_e_5007d_recovery=reference,
            recovery_margin=chain.recovery - reference,
            total_turning=chain.total_turning,
            mach_before_normal=chain.mach_before_normal,
            assumptions=tuple(assumptions),
        )
        self.logger.info(
            "Recovery %.4f (MIL-E-5007D %.4f), ramps %s deg",
            chain.recovery,
            reference,
            ", ".join(f"{d:.2f}" for d in chain.deflections),
        )
        return results

    def validate_results(self, results: MultiShockInletResults) -> bool:
        """Check that every pressure ratio lies in (0, 1].

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        chain = results.chain
        ratios = [*chain.pt_oblique, chain.pt_normal, chain.pt_diffuser, chain.recovery]
        return all(0.0 < r <= 1.0 + 1e-12 for r in ratios)
