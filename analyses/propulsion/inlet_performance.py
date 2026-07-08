# MELprop-IADE | analyses.propulsion.inlet_performance | v0.1.0
"""Low-order axisymmetric conical-spike inlet performance analysis.

Models the Project B stage-2 ramjet intake (Fusion Assembly v6: conical
spike, cone length 0.293 m / base diameter 0.150 m, capture area
0.04909 m^2) at a design condition of Mach 2.5, 10,000 m ISA cruise
altitude.

Shock chain (design/on-cone-axis approximation):
    1. Oblique shock at the spike, solved from the theta-beta-Mach
       relation for the WEAK shock angle beta given the cone half-angle
       theta = delta and the freestream Mach M1 (Anderson, *Modern
       Compressible Flow*, 3rd ed., Ch. 4).
    2. A single terminating normal shock at the cowl lip, bringing the
       flow subsonic before the subsonic diffuser.
    3. A fixed subsonic-diffuser efficiency ``eta_diffuser`` (assumed)
       applied as an additional total-pressure multiplier.

Approximation note (IMPORTANT): using the 2-D wedge theta-beta-Mach
relation with theta = the cone half-angle is a standard low-order
stand-in for the true axisymmetric Taylor-Maccoll conical-shock
solution. For a given half-angle and Mach number the conical shock
angle is slightly SMALLER and the conical shock slightly WEAKER than
the wedge solution, so this module's pressure recovery is slightly
CONSERVATIVE (pessimistic) relative to the true conical spike. This is
stated explicitly in the results metadata and JSON ``assumptions``.

If the wedge shock is geometrically detached (theta exceeds the local
maximum deflection angle theta_max(M1)), the oblique stage is replaced
by a single normal (bow) shock at the freestream Mach — again a
conservative low-order fallback, not a true bow-shock solution.

References:
    Anderson, J. D., *Modern Compressible Flow: With Historical
    Perspective*, 3rd ed., McGraw-Hill, 2003 — Ch. 4 (oblique shocks,
    theta-beta-M relation) and Ch. 3 (normal shock relations).
    MIL-E-5007D, *Military Specification: Engines, Aircraft, Turbojet
    and Turbofan* — total-pressure-recovery standard
    ``eta_std = 1 - 0.075*(M - 1)^1.35`` for M > 1.
    U.S. Standard Atmosphere, 1976 (ISA troposphere/lower-stratosphere
    model) for the freestream state at the design altitude.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scipy.optimize import brentq, minimize_scalar

if __package__ in (None, ""):
    # Allow `python3 analyses/propulsion/inlet_performance.py` direct
    # execution by putting the repository root (three levels up) on
    # sys.path so the `core` package resolves, mirroring conftest.py's
    # behavior for pytest runs.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.component_base import AnalysisResults, BaseAnalysis, FidelityLevel

# --------------------------------------------------------------------------
# Physical / model constants (SI units)
# --------------------------------------------------------------------------

#: Ratio of specific heats for air.
GAMMA: float = 1.4

#: Specific gas constant for dry air [J/(kg*K)].
R_AIR: float = 287.05

#: Standard gravity [m/s^2].
G0: float = 9.80665

#: ISA sea-level temperature [K].
T0_ISA: float = 288.15

#: ISA sea-level pressure [Pa].
P0_ISA: float = 101325.0

#: ISA tropospheric lapse rate [K/m], valid 0-11 km.
LAPSE_RATE: float = 0.0065

#: Altitude of the tropopause [m] (ISA).
TROPOPAUSE_ALTITUDE_M: float = 11000.0

#: MIL-E-5007D total-pressure-recovery standard coefficients:
#: eta_std = 1 - MIL_E_5007_COEFF * (M - 1) ** MIL_E_5007_EXP  (M > 1).
MIL_E_5007_COEFF: float = 0.075
MIL_E_5007_EXP: float = 1.35

# --------------------------------------------------------------------------
# Fusion Assembly v6 geometry (vehicles/ramjet_rocket/vehicle_config.yaml,
# cfd_notes.ramjet_inlet_note; fusion_extraction_v6.yaml ramjet.inlet_system)
# --------------------------------------------------------------------------

#: Conical spike cone length [m].
SPIKE_CONE_LENGTH_M: float = 0.293

#: Conical spike base diameter [m].
SPIKE_BASE_DIAMETER_M: float = 0.150

#: Inlet capture area [m^2] = pi/4 * cowl_diameter^2, cowl diameter 0.250 m
#: (inlet_Mk1 diameter, fusion_extraction_v6.yaml ramjet.inlet_system).
CAPTURE_AREA_M2: float = 0.04909

#: Assumed subsonic-diffuser total-pressure efficiency (not yet measured).
ETA_DIFFUSER: float = 0.92

#: Design (cruise) Mach number, vehicle_config.yaml stage_2.design_mach.
MACH_DESIGN: float = 2.5

#: Assumed design/cruise altitude [m] (typical ramjet cruise band).
DESIGN_ALTITUDE_M: float = 10_000.0


@dataclass
class AtmosphereState:
    """Freestream atmospheric state at a given altitude (ISA model).

    Attributes:
        altitude_m: Geometric altitude [m].
        temperature_K: Static temperature [K].
        pressure_Pa: Static pressure [Pa].
        density_kg_m3: Density [kg/m^3].
        speed_of_sound_m_s: Speed of sound [m/s].
    """

    altitude_m: float
    temperature_K: float
    pressure_Pa: float
    density_kg_m3: float
    speed_of_sound_m_s: float


def isa_atmosphere(altitude_m: float) -> AtmosphereState:
    """Compute the ISA (1976) atmospheric state at a given altitude.

    Uses the linear-lapse troposphere model below 11 km and the
    isothermal lower-stratosphere model above (not needed for the
    10 km design point but kept general for reuse).

    Args:
        altitude_m: Geometric altitude above sea level [m], >= 0.

    Returns:
        AtmosphereState with temperature, pressure, density and speed
        of sound in SI units.

    Raises:
        ValueError: If altitude_m is negative.
    """
    if altitude_m < 0.0:
        raise ValueError(f"altitude_m must be >= 0, got {altitude_m}")

    if altitude_m <= TROPOPAUSE_ALTITUDE_M:
        temperature_K = T0_ISA - LAPSE_RATE * altitude_m
        exponent = G0 / (R_AIR * LAPSE_RATE)
        pressure_Pa = P0_ISA * (temperature_K / T0_ISA) ** exponent
    else:
        t11 = T0_ISA - LAPSE_RATE * TROPOPAUSE_ALTITUDE_M
        exponent = G0 / (R_AIR * LAPSE_RATE)
        p11 = P0_ISA * (t11 / T0_ISA) ** exponent
        temperature_K = t11
        pressure_Pa = p11 * math.exp(
            -G0 * (altitude_m - TROPOPAUSE_ALTITUDE_M) / (R_AIR * t11)
        )

    density_kg_m3 = pressure_Pa / (R_AIR * temperature_K)
    speed_of_sound_m_s = math.sqrt(GAMMA * R_AIR * temperature_K)

    return AtmosphereState(
        altitude_m=altitude_m,
        temperature_K=temperature_K,
        pressure_Pa=pressure_Pa,
        density_kg_m3=density_kg_m3,
        speed_of_sound_m_s=speed_of_sound_m_s,
    )


def spike_half_angle_rad(
    cone_length_m: float = SPIKE_CONE_LENGTH_M,
    base_diameter_m: float = SPIKE_BASE_DIAMETER_M,
) -> float:
    """Compute the conical-spike half-angle from cone geometry.

    delta = arctan((base_diameter / 2) / cone_length).

    Args:
        cone_length_m: Axial length of the spike cone [m].
        base_diameter_m: Base (max) diameter of the spike cone [m].

    Returns:
        Spike half-angle [rad].
    """
    return math.atan((base_diameter_m / 2.0) / cone_length_m)


def _theta_from_beta(mach1: float, beta_rad: float, gamma: float = GAMMA) -> float:
    """Evaluate the theta-beta-Mach relation for a given shock angle.

    ``tan(theta) = 2*cot(beta) * (M1^2*sin^2(beta) - 1)
    / (M1^2*(gamma + cos(2*beta)) + 2)`` (Anderson, Eq. 4.17).

    Args:
        mach1: Upstream Mach number.
        beta_rad: Oblique shock angle [rad].
        gamma: Ratio of specific heats.

    Returns:
        Flow deflection angle theta [rad] (may be negative/zero outside
        the physical shock-angle range).
    """
    sin_b = math.sin(beta_rad)
    cos_2b = math.cos(2.0 * beta_rad)
    numerator = mach1**2 * sin_b**2 - 1.0
    denominator = mach1**2 * (gamma + cos_2b) + 2.0
    tan_theta = 2.0 * (1.0 / math.tan(beta_rad)) * numerator / denominator
    return math.atan(tan_theta)


def theta_max_rad(mach1: float, gamma: float = GAMMA) -> tuple[float, float]:
    """Find the maximum deflection angle and corresponding shock angle.

    Locates the peak of theta(beta) between the Mach angle and beta =
    pi/2; beyond this deflection the oblique shock detaches into a bow
    shock.

    Args:
        mach1: Upstream Mach number (must be > 1).
        gamma: Ratio of specific heats.

    Returns:
        Tuple ``(beta_at_theta_max_rad, theta_max_rad)``.
    """
    mu = math.asin(1.0 / mach1)
    result = minimize_scalar(
        lambda b: -_theta_from_beta(mach1, b, gamma),
        bounds=(mu + 1e-9, math.pi / 2.0 - 1e-9),
        method="bounded",
    )
    beta_star = float(result.x)
    theta_max = -float(result.fun)
    return beta_star, theta_max


def oblique_shock_beta_rad(
    mach1: float,
    theta_rad: float,
    gamma: float = GAMMA,
    weak: bool = True,
) -> float | None:
    """Solve the theta-beta-Mach relation for the shock angle beta.

    Args:
        mach1: Upstream Mach number (must be > 1).
        theta_rad: Required flow deflection angle [rad] (>= 0).
        gamma: Ratio of specific heats.
        weak: If True, return the weak-shock root; otherwise the
            strong-shock root.

    Returns:
        Shock angle beta [rad], or None if the deflection exceeds
        theta_max (shock detaches — no attached oblique solution).
    """
    mu = math.asin(1.0 / mach1)
    beta_star, theta_max = theta_max_rad(mach1, gamma)
    if theta_rad > theta_max:
        return None

    f = lambda b: _theta_from_beta(mach1, b, gamma) - theta_rad  # noqa: E731
    lo, hi = (mu + 1e-9, beta_star) if weak else (beta_star, math.pi / 2.0 - 1e-9)
    try:
        return brentq(f, lo, hi)
    except ValueError:
        return None


def normal_shock_mach2(mach1n: float, gamma: float = GAMMA) -> float:
    """Downstream Mach number (or normal component) across a normal shock.

    ``M2^2 = (1 + (gamma-1)/2 * M1^2) / (gamma*M1^2 - (gamma-1)/2)``
    (Anderson, Eq. 3.51).

    Args:
        mach1n: Upstream Mach number, or upstream normal-Mach component
            for an oblique shock (must be >= 1).
        gamma: Ratio of specific heats.

    Returns:
        Downstream Mach number (or normal component) M2n.
    """
    numerator = 1.0 + 0.5 * (gamma - 1.0) * mach1n**2
    denominator = gamma * mach1n**2 - 0.5 * (gamma - 1.0)
    return math.sqrt(numerator / denominator)


def normal_shock_total_pressure_ratio(mach1n: float, gamma: float = GAMMA) -> float:
    """Total-pressure ratio p02/p01 across a normal shock (Anderson, Eq. 3.57).

    Args:
        mach1n: Upstream Mach number, or upstream normal-Mach component
            for an oblique shock (must be >= 1).
        gamma: Ratio of specific heats.

    Returns:
        Total-pressure ratio p02/p01 (<= 1).
    """
    term1 = (
        (gamma + 1.0) * mach1n**2 / ((gamma - 1.0) * mach1n**2 + 2.0)
    ) ** (gamma / (gamma - 1.0))
    term2 = (
        (gamma + 1.0) / (2.0 * gamma * mach1n**2 - (gamma - 1.0))
    ) ** (1.0 / (gamma - 1.0))
    return term1 * term2


def mil_e_5007_eta_std(mach: float) -> float:
    """MIL-E-5007D standard total-pressure-recovery target.

    ``eta_std = 1 - 0.075 * (M - 1)^1.35`` for M > 1; 1.0 for M <= 1.

    Args:
        mach: Freestream Mach number.

    Returns:
        Standard total-pressure recovery (dimensionless, <= 1).
    """
    if mach <= 1.0:
        return 1.0
    return 1.0 - MIL_E_5007_COEFF * (mach - 1.0) ** MIL_E_5007_EXP


def inlet_recovery_chain(
    mach1: float,
    theta_rad: float,
    eta_diffuser: float,
    gamma: float = GAMMA,
) -> dict[str, Any]:
    """Run the oblique-shock + normal-shock + diffuser recovery chain.

    Args:
        mach1: Freestream Mach number (must be > 1).
        theta_rad: Spike half-angle (deflection angle) [rad].
        eta_diffuser: Assumed subsonic-diffuser total-pressure efficiency.
        gamma: Ratio of specific heats.

    Returns:
        Dict with ``beta_rad``, ``mach_post_oblique``, ``mach_post_normal``,
        ``pressure_recovery_oblique``, ``pressure_recovery_normal``,
        ``eta_inlet`` and ``detached`` (bool, True if the wedge oblique
        shock has no attached solution at this Mach and the fallback
        single-normal-shock approximation was used instead).
    """
    beta_rad = oblique_shock_beta_rad(mach1, theta_rad, gamma, weak=True)

    if beta_rad is None:
        # Detached shock: conservative fallback is a single normal
        # (bow) shock standing at the freestream Mach.
        detached = True
        mach_post_oblique = mach1
        pressure_recovery_oblique = 1.0
    else:
        detached = False
        m1n = mach1 * math.sin(beta_rad)
        m2n = normal_shock_mach2(m1n, gamma)
        mach_post_oblique = m2n / math.sin(beta_rad - theta_rad)
        pressure_recovery_oblique = normal_shock_total_pressure_ratio(m1n, gamma)

    if mach_post_oblique > 1.0:
        mach_post_normal = normal_shock_mach2(mach_post_oblique, gamma)
        pressure_recovery_normal = normal_shock_total_pressure_ratio(
            mach_post_oblique, gamma
        )
    else:
        mach_post_normal = mach_post_oblique
        pressure_recovery_normal = 1.0

    eta_inlet = pressure_recovery_oblique * pressure_recovery_normal * eta_diffuser

    return {
        "beta_rad": beta_rad,
        "detached": detached,
        "mach_post_oblique": mach_post_oblique,
        "mach_post_normal": mach_post_normal,
        "pressure_recovery_oblique": pressure_recovery_oblique,
        "pressure_recovery_normal": pressure_recovery_normal,
        "eta_inlet": eta_inlet,
    }


class InletPerformanceAnalysis(BaseAnalysis):
    """Low-order conical-spike supersonic inlet performance analysis.

    Wraps the oblique-shock + normal-shock + diffuser recovery chain
    (see module docstring) as a :class:`BaseAnalysis`. Analytical /
    closed-form shock relations -> ``FidelityLevel.LEVEL_0``.

    Example:
        >>> analysis = InletPerformanceAnalysis()
        >>> analysis.setup(mach_design=2.5, altitude_m=10_000.0)
        >>> results = analysis.execute()
        >>> results["eta_inlet"]  # doctest: +SKIP
    """

    fidelity = FidelityLevel.LEVEL_0

    def __init__(self, name: str = "conical_spike_inlet_performance") -> None:
        super().__init__(name)
        self._mach_design = MACH_DESIGN
        self._altitude_m = DESIGN_ALTITUDE_M
        self._cone_length_m = SPIKE_CONE_LENGTH_M
        self._base_diameter_m = SPIKE_BASE_DIAMETER_M
        self._capture_area_m2 = CAPTURE_AREA_M2
        self._eta_diffuser = ETA_DIFFUSER

    def setup(
        self,
        mach_design: float = MACH_DESIGN,
        altitude_m: float = DESIGN_ALTITUDE_M,
        cone_length_m: float = SPIKE_CONE_LENGTH_M,
        base_diameter_m: float = SPIKE_BASE_DIAMETER_M,
        capture_area_m2: float = CAPTURE_AREA_M2,
        eta_diffuser: float = ETA_DIFFUSER,
    ) -> None:
        """Bind the analysis to a design point and inlet geometry.

        Args:
            mach_design: Design (cruise) freestream Mach number (> 1).
            altitude_m: Design/cruise altitude [m], ISA.
            cone_length_m: Spike cone axial length [m].
            base_diameter_m: Spike cone base diameter [m].
            capture_area_m2: Inlet capture (cowl) area [m^2].
            eta_diffuser: Assumed subsonic-diffuser total-pressure
                efficiency (0-1].

        Raises:
            ValueError: If mach_design <= 1 or eta_diffuser outside (0, 1].
        """
        if mach_design <= 1.0:
            raise ValueError(f"mach_design must be > 1, got {mach_design}")
        if not (0.0 < eta_diffuser <= 1.0):
            raise ValueError(f"eta_diffuser must be in (0, 1], got {eta_diffuser}")

        self._mach_design = mach_design
        self._altitude_m = altitude_m
        self._cone_length_m = cone_length_m
        self._base_diameter_m = base_diameter_m
        self._capture_area_m2 = capture_area_m2
        self._eta_diffuser = eta_diffuser
        self._is_setup = True

    def execute(self) -> AnalysisResults:
        """Run the shock chain at the design point and return results.

        Returns:
            AnalysisResults with the design-point shock chain, total
            pressure recovery, mass flow and MIL-E-5007 comparison.

        Raises:
            RuntimeError: If called before :meth:`setup`.
        """
        if not self._is_setup:
            raise RuntimeError(
                "InletPerformanceAnalysis.execute() called before setup()"
            )

        delta_rad = spike_half_angle_rad(self._cone_length_m, self._base_diameter_m)
        atmosphere = isa_atmosphere(self._altitude_m)
        velocity_m_s = self._mach_design * atmosphere.speed_of_sound_m_s
        mdot_kg_s = (
            atmosphere.density_kg_m3 * velocity_m_s * self._capture_area_m2
        )

        chain = inlet_recovery_chain(
            self._mach_design, delta_rad, self._eta_diffuser
        )
        eta_std = mil_e_5007_eta_std(self._mach_design)
        margin = chain["eta_inlet"] - eta_std
        verdict = "PASS" if margin >= 0.0 else "FAIL"

        beta_deg = (
            math.degrees(chain["beta_rad"]) if chain["beta_rad"] is not None else float("nan")
        )

        data = {
            "spike_half_angle_deg": math.degrees(delta_rad),
            "shock_angle_beta_deg": beta_deg,
            "mach_post_oblique": chain["mach_post_oblique"],
            "mach_post_normal": chain["mach_post_normal"],
            "pressure_recovery_oblique": chain["pressure_recovery_oblique"],
            "pressure_recovery_normal": chain["pressure_recovery_normal"],
            "eta_inlet": chain["eta_inlet"],
            "eta_diffuser": self._eta_diffuser,
            "mil_e_5007_eta_std": eta_std,
            "margin": margin,
            "capture_area_m2": self._capture_area_m2,
            "mdot_design_kg_per_s": mdot_kg_s,
            "design_altitude_m": self._altitude_m,
            "mach_design": self._mach_design,
        }
        metadata = {
            "verdict": verdict,
            "shock_detached": chain["detached"],
            "freestream": {
                "mach": self._mach_design,
                "altitude_m": self._altitude_m,
                "temperature_K": atmosphere.temperature_K,
                "pressure_Pa": atmosphere.pressure_Pa,
                "density_kg_m3": atmosphere.density_kg_m3,
                "speed_of_sound_m_s": atmosphere.speed_of_sound_m_s,
                "velocity_m_s": velocity_m_s,
            },
            "assumptions": [
                "ISA 1976 atmosphere at the design altitude (typical ramjet "
                "cruise band; not a trajectory-optimized value).",
                "Diffuser total-pressure efficiency eta_diffuser=0.92 is an "
                "assumed placeholder pending duct-loss/CFD data.",
                "Full mass-flow capture assumed at the design Mach "
                "(no spillage, mdot = rho_inf * V_inf * A_capture).",
                "Oblique shock solved from the 2-D wedge theta-beta-Mach "
                "relation using theta = spike half-angle, as a standard "
                "low-order stand-in for the true axisymmetric "
                "Taylor-Maccoll conical shock. This under-predicts the "
                "true conical total-pressure recovery slightly (the wedge "
                "shock is marginally stronger than the true conical "
                "shock for the same half-angle and Mach), i.e. the "
                "reported eta_inlet is slightly CONSERVATIVE.",
                "A single terminating normal shock at the cowl lip is "
                "assumed (no additional oblique reflections / "
                "multi-shock spike); this is the classical single-cone "
                "spike idealization.",
                "If the wedge oblique shock is geometrically detached at "
                "a given Mach, a single normal (bow) shock at the "
                "freestream Mach is substituted as a conservative "
                "low-order fallback (flagged via shock_detached).",
            ],
            "verdict_note": (
                "A single-cone (one oblique shock + one terminating "
                "normal shock) spike is a minimum-part-count design; "
                "failing MIL-E-5007 at M=2.5 is a known limitation of "
                "single-shock spikes at this Mach and motivates a "
                "multi-shock (2- or 3-cone) or isentropic spike for a "
                "production inlet."
            ),
        }

        results = AnalysisResults(
            name=self.name, fidelity=self.fidelity, data=data, metadata=metadata
        )
        if not self.validate_results(results):
            raise RuntimeError(
                f"Inlet performance results failed physical validation: {results.data}"
            )
        return results

    def validate_results(self, results: AnalysisResults) -> bool:
        """Sanity-check the shock-chain results.

        Checks: 0 < eta_inlet <= eta_diffuser (compression can only lose
        total pressure), post-normal-shock Mach < 1, and spike half-angle
        matches the expected ~14.36 deg for the Fusion v6 geometry.

        Args:
            results: Results to validate.

        Returns:
            True if all physical sanity checks pass.
        """
        required = {
            "eta_inlet",
            "eta_diffuser",
            "mach_post_normal",
            "spike_half_angle_deg",
        }
        if not required.issubset(results.data):
            return False
        if not (0.0 < results["eta_inlet"] <= results["eta_diffuser"] + 1e-9):
            return False
        if not (results["mach_post_normal"] < 1.0):
            return False
        if not (10.0 < results["spike_half_angle_deg"] < 20.0):
            return False
        return True


def sweep_eta_inlet(
    mach_range: list[float],
    cone_length_m: float = SPIKE_CONE_LENGTH_M,
    base_diameter_m: float = SPIKE_BASE_DIAMETER_M,
    eta_diffuser: float = ETA_DIFFUSER,
) -> dict[str, list[float]]:
    """Evaluate eta_inlet and the MIL-E-5007 standard over a Mach sweep.

    Args:
        mach_range: List of freestream Mach numbers to evaluate (> 1).
        cone_length_m: Spike cone axial length [m] (fixed geometry).
        base_diameter_m: Spike cone base diameter [m] (fixed geometry).
        eta_diffuser: Assumed subsonic-diffuser total-pressure efficiency.

    Returns:
        Dict with lists ``mach``, ``eta_inlet`` and ``eta_std`` (all
        same length as ``mach_range``).
    """
    delta_rad = spike_half_angle_rad(cone_length_m, base_diameter_m)
    eta_inlet_values: list[float] = []
    eta_std_values: list[float] = []
    for mach in mach_range:
        chain = inlet_recovery_chain(mach, delta_rad, eta_diffuser)
        eta_inlet_values.append(chain["eta_inlet"])
        eta_std_values.append(mil_e_5007_eta_std(mach))
    return {"mach": list(mach_range), "eta_inlet": eta_inlet_values, "eta_std": eta_std_values}


def _build_output_dict(results: AnalysisResults) -> dict[str, Any]:
    """Flatten an AnalysisResults into the JSON schema requested for output."""
    out: dict[str, Any] = dict(results.data)
    out["verdict"] = results.metadata["verdict"]
    out["freestream"] = results.metadata["freestream"]
    out["assumptions"] = results.metadata["assumptions"]
    out["shock_detached"] = results.metadata["shock_detached"]
    out["verdict_note"] = results.metadata["verdict_note"]
    out["fidelity"] = results.fidelity.name
    return out


def _plot_recovery_sweep(output_path: Path) -> None:
    """Plot eta_inlet vs Mach (1.5-4.0) against the MIL-E-5007 standard.

    Args:
        output_path: Destination PNG path.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    mach_values = np.linspace(1.5, 4.0, 200).tolist()
    sweep = sweep_eta_inlet(mach_values)

    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    ax.plot(
        sweep["mach"],
        sweep["eta_inlet"],
        color="#1f77b4",
        linewidth=2.0,
        label="Conical spike (oblique + normal shock + diffuser)",
    )
    ax.plot(
        sweep["mach"],
        sweep["eta_std"],
        color="#d62728",
        linewidth=2.0,
        linestyle="--",
        label="MIL-E-5007D standard",
    )
    ax.axvline(
        MACH_DESIGN, color="gray", linewidth=1.0, linestyle=":", label="Design Mach 2.5"
    )
    ax.set_xlabel("Freestream Mach number [-]")
    ax.set_ylabel("Total pressure recovery, $\\eta_{inlet}$ [-]")
    ax.set_title("Conical-spike inlet total-pressure recovery vs Mach")
    ax.set_xlim(1.5, 4.0)
    ax.set_ylim(0.0, 1.0)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower left", fontsize=9)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    """Run the design-point analysis, save JSON, and generate the sweep plot."""
    analysis = InletPerformanceAnalysis()
    analysis.setup(mach_design=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M)
    results = analysis.execute()
    output = _build_output_dict(results)

    module_dir = Path(__file__).resolve().parent
    json_path = module_dir / "inlet_results.json"
    png_path = module_dir / "inlet_recovery.png"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    _plot_recovery_sweep(png_path)

    print("=== Conical-spike inlet performance (design point) ===")
    print(f"Design Mach: {MACH_DESIGN}")
    print(f"Design altitude: {DESIGN_ALTITUDE_M} m ISA")
    print(f"Spike half-angle delta: {output['spike_half_angle_deg']:.3f} deg")
    print(f"Oblique shock angle beta: {output['shock_angle_beta_deg']:.3f} deg")
    print(f"Mach post-oblique shock: {output['mach_post_oblique']:.4f}")
    print(f"Mach post-normal shock: {output['mach_post_normal']:.4f}")
    print(f"Pressure recovery (oblique): {output['pressure_recovery_oblique']:.4f}")
    print(f"Pressure recovery (normal): {output['pressure_recovery_normal']:.4f}")
    print(f"eta_diffuser (assumed): {output['eta_diffuser']:.4f}")
    print(f"eta_inlet: {output['eta_inlet']:.4f}")
    print(f"MIL-E-5007D eta_std: {output['mil_e_5007_eta_std']:.4f}")
    print(f"Margin (eta_inlet - eta_std): {output['margin']:.4f}")
    print(f"Verdict: {output['verdict']}")
    print(f"Capture area: {output['capture_area_m2']:.5f} m^2")
    print(f"mdot (design): {output['mdot_design_kg_per_s']:.4f} kg/s")
    print(f"Freestream: {output['freestream']}")
    print(f"\nJSON written to: {json_path}")
    print(f"Plot written to: {png_path}")


if __name__ == "__main__":
    main()
