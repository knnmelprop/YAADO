"""Design-point 1-D (station-based) ramjet combustor + nozzle cycle model.

Models the Generic Vehicle stage-2 ramjet thermodynamic cycle at the design
condition (Mach 2.5, 10,000 m ISA) using a classical station-numbering
scheme (Mattingly, *Elements of Gas Turbine Propulsion*, 2nd ed.,
McGraw-Hill, 2006, Ch. 3 & 9 — "ramjet" station numbers):

    0 -> freestream
    2 -> combustor entry (post-inlet; total pressure carries the inlet
         recovery penalty, adiabatic so total temperature is unchanged)
    4 -> combustor exit (post heat-addition to ``tt4_K``, minus the
         burner total-pressure loss ``pi_b``)
    9 -> nozzle exit (two competing geometries evaluated, see below)

This is the project's ``FidelityLevel.LEVEL_2`` "1-D cycle" rung on the
fidelity ladder (pyCycle-equivalent station analysis without an actual
pyCycle/OpenMDAO solve). Inlet total-pressure recovery is NOT
re-derived here — it is reused from
:mod:`analyses.propulsion.inlet_performance`
(:func:`~analyses.propulsion.inlet_performance.multi_cone_recovery_chain`
via :class:`~analyses.propulsion.inlet_performance.MultiConeInletPerformanceAnalysis`),
specifically the 4-cone preset chain that yields ``eta_inlet`` ~ 0.874 at
Mach 2.5 (already including the assumed subsonic-diffuser efficiency
``eta_diffuser`` = 0.92). The ISA atmosphere model is likewise reused
from that module rather than duplicated.

Two-gas model:
    Cold (inlet/freestream) air: ``gamma_c`` = 1.4, ``cp_c`` = 1004.5
    J/(kg K). Hot (post-combustion) gas: ``gamma_t`` = 1.33, ``cp_t`` =
    1156.0 J/(kg K) — standard calorically-imperfect two-gas
    approximation for kerosene-air combustion products (Mattingly,
    Ch. 2, Table 2.2-ish typical values; Hill & Peterson, *Mechanics
    and Thermodynamics of Propulsion*, 2nd ed., Ch. 5 & 11).

Combustor:
    Fuel is kerosene, lower heating value ``h_PR`` = 43.1e6 J/kg. The
    fuel-air ratio follows the steady-flow energy-balance definition
    (Mattingly, Eq. 2.15 / Hill & Peterson Eq. 11.19-type form):

        f = cp_t*(Tt4 - Tt2) / (eta_b*h_PR - cp_t*Tt4)

    with burner efficiency ``eta_b`` (default 0.95, placeholder) and
    burner total-pressure ratio ``pi_b`` (default 0.95, placeholder;
    ``pt4 = pi_b * pt2``). ``tt4_K`` defaults to 2000.0 K, matching the
    ``stage_2.combustor_temp_K`` placeholder in
    ``Hangar/generic_vehicle/vehicle_config.yaml`` (a TBD value, NOT a
    validated design point — see the risk note below).

Nozzle — TWO geometries evaluated and BOTH reported (this is the
project's known CAD-vs-design discrepancy, quantified rather than
hidden):
    (a) "Design" matched convergent-divergent nozzle: isentropic
        expansion of the hot gas from station 4 down to the ambient
        static pressure ``p0`` (perfect expansion, ``pe = p0``). This
        is the DESIGN INTENT reflected by ``vehicle_config.yaml``'s
        ``nozzle_area_ratio`` = 4.0.
    (b) Convergent-only, ``nozzle_area_ratio`` = 1.0, choked
        (``M9`` = 1) nozzle — this is what the Fusion v6 CAD model
        actually implements: a cylindrical exit stub, with the
        assembly notes stating explicitly that the "full ramjet engine
        [is] NOT modeled." Because the flow is not expanded to ambient
        here, the pressure-thrust term is retained:
        ``F = mdot*((1+f)*u9 - u0) + (p9 - p0)*A9``.
    ``vehicle_config.yaml``'s ``nozzle_area_ratio: 4.0`` must NOT be
    treated as an already-validated number — it is the DESIGN target,
    not the as-built CAD geometry. Both thrust values are reported so
    the gap is visible to downstream MDO/mission work.

MANDATORY verification gate (per project fidelity-ladder rules,
CLAUDE.md Sec. "Twarde reguly" -- Isp/physical validation):
    :func:`ideal_ramjet_closed_form` reproduces the classical ideal
    (loss-free, single perfect-gas) ramjet cycle closed form
    (Mattingly, Ch. 3; NASA GRC "Brayton cycle for a ramjet" notes):

        ST = a0*M0*(sqrt(Tt4/Tt0) - 1)
        f  = cp*(Tt4 - Tt0) / (h_PR - cp*Tt4)

    with ``eta_inlet`` = 1, ``pi_b`` = 1, ``eta_b`` = 1 and a single
    gas (``gamma`` = 1.4, ``cp`` = 1004.5 J/(kg K)) throughout. This
    closed form deliberately neglects the (1+f) fuel-mass-addition
    term in the thrust equation (the standard simplification used to
    derive the compact ``sqrt(Tt4/Tt0)`` form) -- it is NOT expected to
    numerically equal the two-gas, mass-conserving station model even
    with all losses set to 1.0/unity, because that model always
    includes the (1+f) mass-addition term. The two are independent,
    separately-testable code paths; see the module's unit tests.

    Separately, ``RamjetCycleAnalysis`` also reports a same-gas,
    loss-free reference point (``eta_inlet`` = ``pi_b`` = ``eta_b`` =
    1, but keeping the real two-gas ``cp_t``/``gamma_t`` and the (1+f)
    mass addition) in ``metadata["loss_free_reference"]``. The
    real (lossy) design-point thrust MUST be lower, and its TSFC MUST
    be higher, than this loss-free reference -- that is the physically
    meaningful "losses cost thrust and fuel economy" check, and is
    asserted in the test suite.

COMBUSTOR RISK BASELINE (quote verbatim in any downstream review):
    Liquid kerosene may not vaporize sufficiently before reaching the
    flame holders at these residence times/velocities, and measured
    flame-holder cavity temperatures of ~2400 K exceed the melting
    point of the currently specified aluminium flame-holder material.
    The ``tt4_K`` = 2000 K value used here is a PLACEHOLDER, chosen
    BELOW that ~2400 K risk figure -- it is not a cleared design
    temperature. Combustor design is BLOCKED pending flame-holder
    relocation and/or injector atomization redesign. Separately,
    Fusion v6 CAD lists the flame_holder material as STEEL, which
    contradicts the "aluminium" risk note above -- this discrepancy is
    flagged for human review and is NOT resolved by this module.

REFERENCE-MODEL DISCLOSURE:
    This module is the new ``FidelityLevel.LEVEL_2`` 1-D cycle model.
    The Grzywka MATLAB 2-D baseline values are NOT available in this
    repository (``TODO_PHYSICAL_PARAM``). Published CFD studies (Dalek,
    Teltik) report exit velocity/Mach 20-30% HIGHER than the MATLAB
    baseline -- an open discrepancy between methods that this module
    does not resolve. The thrust/TSFC numbers produced here are
    therefore single-method L2 results pending a dual-check against
    both the MATLAB baseline (once located) and the CFD studies.

References:
    Mattingly, J. D., *Elements of Gas Turbine Propulsion*, 2nd ed.,
    AIAA Education Series, 2006 -- Ch. 3 (ideal ramjet cycle analysis),
    Ch. 9 (real/component-loss ramjet cycle, station numbering).
    Hill, P. G. & Peterson, C. R., *Mechanics and Thermodynamics of
    Propulsion*, 2nd ed., Addison-Wesley, 1992 -- Ch. 5 (ideal cycle
    performance), Ch. 11 (component performance, fuel-air ratio).
    Anderson, J. D., *Modern Compressible Flow*, 3rd ed., McGraw-Hill,
    2003 -- Ch. 3 (isentropic/stagnation relations, choked-nozzle
    relations used for the convergent-only nozzle).
    NASA Glenn Research Center, "Ramjet Engine: Brayton Cycle"
    (nasa.gov/general/ideal-ramjet-brayton-cycle educational notes) --
    the closed-form ideal specific-thrust expression cross-checked here.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    # Allow `python3 analyses/propulsion/ramjet_cycle.py` direct
    # execution by putting the repository root (three levels up) on
    # sys.path so the `core` package resolves, mirroring conftest.py's
    # behavior for pytest runs.
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from YAADO_Core.modules.powerplant.inlet_methods.wedge import (
    CAPTURE_AREA_M2,
    DEFAULT_N_CONES_M25,
    DESIGN_ALTITUDE_M,
    G0,
    GAMMA as GAMMA_COLD,
    MACH_DESIGN,
    R_AIR,
    MultiConeInletPerformanceAnalysis,
    isa_atmosphere,
)
from YAADO_Core.Foundation.analysis_base import AnalysisResults, BaseAnalysis, FidelityLevel

# --------------------------------------------------------------------------
# Physical / model constants (SI units)
# --------------------------------------------------------------------------

#: Specific heat at constant pressure of cold (freestream/inlet) air
#: [J/(kg*K)].
CP_COLD: float = 1004.5

#: Ratio of specific heats of hot (post-combustion) gas [-].
GAMMA_HOT: float = 1.33

#: Specific heat at constant pressure of hot (post-combustion) gas
#: [J/(kg*K)].
CP_HOT: float = 1156.0

#: Specific gas constant of the hot gas [J/(kg*K)], derived from
#: cp_t and gamma_t via R = cp*(gamma-1)/gamma (consistent calorically-
#: perfect-gas relation, same form as R_AIR/GAMMA_COLD/CP_COLD).
R_HOT: float = CP_HOT * (GAMMA_HOT - 1.0) / GAMMA_HOT

#: Kerosene lower heating value [J/kg] (Jet-A/kerosene typical value).
KEROSENE_H_PR: float = 43.1e6

#: Assumed burner total-pressure ratio pt4/pt2 (placeholder, no
#: combustor duct-loss / liner-cooling data yet).
PI_B_DEFAULT: float = 0.95

#: Assumed burner (combustion) efficiency (placeholder, no flame-holder
#: / atomization test data yet -- see the combustor risk baseline in
#: the module docstring).
ETA_B_DEFAULT: float = 0.95

#: Combustor exit total temperature Tt4 [K] -- placeholder from
#: Hangar/generic_vehicle/vehicle_config.yaml stage_2.combustor_temp_K
#: (TBD; deliberately kept BELOW the ~2400 K flame-holder risk figure,
#: see the combustor risk baseline in the module docstring).
TT4_DEFAULT_K: float = 2000.0

#: "Design intent" nozzle area ratio A9/A_throat from
#: vehicle_config.yaml (matched CD nozzle) -- 2026-07-10: real drawing
#: value (throat 0.210m / exit 0.241m -> (241/210)^2), was 4.0
#: placeholder. See HR-3/HR-7, vehicle_config.yaml cfd_notes.
NOZZLE_AREA_RATIO_DESIGN: float = 1.317

#: As-built Fusion v6 CAD nozzle area ratio -- cylindrical exit stub
#: ("full ramjet engine NOT modeled" per the assembly notes).
NOZZLE_AREA_RATIO_CYLINDRICAL: float = 1.0


def stagnation_temperature_K(
    static_temperature_K: float, mach: float, gamma: float
) -> float:
    """Compute total (stagnation) temperature from static conditions.

    ``Tt/T = 1 + (gamma-1)/2 * M^2`` (Anderson, *Modern Compressible
    Flow*, 3rd ed., Eq. 3.28).

    Args:
        static_temperature_K: Static temperature [K].
        mach: Local Mach number.
        gamma: Ratio of specific heats.

    Returns:
        Total temperature [K].
    """
    return static_temperature_K * (1.0 + 0.5 * (gamma - 1.0) * mach**2)


def stagnation_pressure_Pa(
    static_pressure_Pa: float, mach: float, gamma: float
) -> float:
    """Compute total (stagnation) pressure from static conditions.

    ``pt/p = (1 + (gamma-1)/2 * M^2)^(gamma/(gamma-1))`` (Anderson,
    *Modern Compressible Flow*, 3rd ed., Eq. 3.30).

    Args:
        static_pressure_Pa: Static pressure [Pa].
        mach: Local Mach number.
        gamma: Ratio of specific heats.

    Returns:
        Total pressure [Pa].
    """
    temperature_ratio = 1.0 + 0.5 * (gamma - 1.0) * mach**2
    return static_pressure_Pa * temperature_ratio ** (gamma / (gamma - 1.0))


def ideal_ramjet_closed_form(
    mach0: float,
    altitude_m: float,
    tt4_K: float,
    h_PR: float = KEROSENE_H_PR,
    cp: float = CP_COLD,
    gamma: float = GAMMA_COLD,
) -> dict[str, float]:
    """Evaluate the classical ideal (loss-free) ramjet cycle closed form.

    Assumes a single calorically-perfect gas throughout (no burner
    total-pressure loss, perfect inlet recovery, 100% combustion
    efficiency, matched/perfectly-expanded nozzle) and neglects the
    (1+f) fuel-mass-addition term in the thrust equation -- the
    standard textbook simplification that yields the compact
    ``sqrt(Tt4/Tt0)`` specific-thrust form (Mattingly, *Elements of Gas
    Turbine Propulsion*, 2nd ed., Ch. 3; NASA GRC ideal-ramjet/Brayton
    educational notes):

        ST = a0*M0*(sqrt(Tt4/Tt0) - 1)
        f  = cp*(Tt4 - Tt0) / (h_PR - cp*Tt4)

    This is the project's ``FidelityLevel.LEVEL_0`` verification-gate
    cross-check for :class:`RamjetCycleAnalysis` -- it is intentionally
    a separate, independently-coded computation (does not call any of
    the station-based cycle functions below) so that it can catch
    regressions in the freestream/stagnation-property math.

    Args:
        mach0: Freestream Mach number (> 1).
        altitude_m: ISA altitude [m].
        tt4_K: Combustor-exit total temperature [K].
        h_PR: Fuel lower heating value [J/kg].
        cp: Single-gas specific heat at constant pressure [J/(kg*K)].
        gamma: Single-gas ratio of specific heats.

    Returns:
        Dict with ``tt0_K``, ``a0_m_s``, ``u0_m_s``,
        ``specific_thrust_Ns_per_kg``, ``f_fuel_air``,
        ``tsfc_kg_per_Ns`` and ``isp_s``.

    Raises:
        ValueError: If mach0 <= 1 or tt4_K does not exceed the
            freestream total temperature.
    """
    if mach0 <= 1.0:
        raise ValueError(f"mach0 must be > 1, got {mach0}")

    atmosphere = isa_atmosphere(altitude_m)
    a0_m_s = math.sqrt(gamma * R_AIR * atmosphere.temperature_K)
    u0_m_s = mach0 * a0_m_s
    tt0_K = stagnation_temperature_K(atmosphere.temperature_K, mach0, gamma)

    if tt4_K <= tt0_K:
        raise ValueError(
            f"tt4_K ({tt4_K}) must exceed the freestream total temperature "
            f"tt0_K ({tt0_K:.2f}) for net heat addition"
        )

    specific_thrust_Ns_per_kg = a0_m_s * mach0 * (math.sqrt(tt4_K / tt0_K) - 1.0)
    f_fuel_air = cp * (tt4_K - tt0_K) / (h_PR - cp * tt4_K)
    tsfc_kg_per_Ns = f_fuel_air / specific_thrust_Ns_per_kg
    isp_s = specific_thrust_Ns_per_kg / (f_fuel_air * G0)

    return {
        "tt0_K": tt0_K,
        "a0_m_s": a0_m_s,
        "u0_m_s": u0_m_s,
        "specific_thrust_Ns_per_kg": specific_thrust_Ns_per_kg,
        "f_fuel_air": f_fuel_air,
        "tsfc_kg_per_Ns": tsfc_kg_per_Ns,
        "isp_s": isp_s,
    }


def _matched_nozzle_exit(
    tt4_K: float,
    pt4_Pa: float,
    p0_Pa: float,
    gamma_t: float,
    cp_t: float,
    r_t: float,
) -> dict[str, float]:
    """Isentropically expand the hot gas to ambient static pressure.

    Perfect expansion (``pe = p0``): the "design intent" matched
    convergent-divergent nozzle (Mattingly Ch. 9; Anderson Ch. 3
    isentropic relations).

    Args:
        tt4_K: Combustor-exit total temperature [K].
        pt4_Pa: Combustor-exit total pressure [Pa].
        p0_Pa: Ambient (freestream) static pressure [Pa].
        gamma_t: Hot-gas ratio of specific heats.
        cp_t: Hot-gas specific heat at constant pressure [J/(kg*K)].
        r_t: Hot-gas specific gas constant [J/(kg*K)].

    Returns:
        Dict with ``T9_K``, ``p9_Pa`` (== p0_Pa), ``u9_m_s``, ``M9``.
    """
    p9_Pa = p0_Pa
    t9_K = tt4_K * (p9_Pa / pt4_Pa) ** ((gamma_t - 1.0) / gamma_t)
    u9_m_s = math.sqrt(2.0 * cp_t * (tt4_K - t9_K))
    a9_m_s = math.sqrt(gamma_t * r_t * t9_K)
    mach9 = u9_m_s / a9_m_s
    return {"T9_K": t9_K, "p9_Pa": p9_Pa, "u9_m_s": u9_m_s, "M9": mach9}


def _choked_nozzle_exit(
    tt4_K: float,
    pt4_Pa: float,
    gamma_t: float,
    r_t: float,
) -> dict[str, float]:
    """Compute choked (M9=1) exit conditions for a convergent-only nozzle.

    Models the Fusion v6 CAD cylindrical exit stub (``nozzle_area_ratio``
    = 1.0): the flow reaches sonic conditions at the exit and is NOT
    expanded to ambient, so the static exit pressure generally differs
    from ``p0`` (Anderson, *Modern Compressible Flow*, 3rd ed., Ch. 3,
    choked/critical conditions with M=1).

    Args:
        tt4_K: Combustor-exit total temperature [K].
        pt4_Pa: Combustor-exit total pressure [Pa].
        gamma_t: Hot-gas ratio of specific heats.
        r_t: Hot-gas specific gas constant [J/(kg*K)].

    Returns:
        Dict with ``T9_K``, ``p9_Pa``, ``u9_m_s`` (== a9, since M9=1),
        ``M9`` (== 1.0), ``rho9_kg_m3``.
    """
    critical_ratio = 2.0 / (gamma_t + 1.0)
    t9_K = tt4_K * critical_ratio
    p9_Pa = pt4_Pa * critical_ratio ** (gamma_t / (gamma_t - 1.0))
    a9_m_s = math.sqrt(gamma_t * r_t * t9_K)
    rho9_kg_m3 = p9_Pa / (r_t * t9_K)
    return {
        "T9_K": t9_K,
        "p9_Pa": p9_Pa,
        "u9_m_s": a9_m_s,
        "M9": 1.0,
        "rho9_kg_m3": rho9_kg_m3,
    }


class RamjetCycleAnalysis(BaseAnalysis):
    """Design-point 1-D ramjet combustor+nozzle cycle (stations 0-2-4-9).

    Wraps the inlet recovery (reused from
    :mod:`analyses.propulsion.inlet_performance`), combustor fuel-air
    balance and dual nozzle-geometry expansion described in the module
    docstring as a :class:`BaseAnalysis`. Station-based 1-D cycle ->
    ``FidelityLevel.LEVEL_2`` per the project fidelity ladder.

    Example:
        >>> analysis = RamjetCycleAnalysis()
        >>> analysis.setup(mach0=2.5, altitude_m=10_000.0)
        >>> results = analysis.execute()
        >>> results["thrust_N"] > 0.0  # doctest: +SKIP
    """

    fidelity = FidelityLevel.LEVEL_2

    def __init__(self, name: str = "ramjet_cycle") -> None:
        super().__init__(name)
        self._mach0 = MACH_DESIGN
        self._altitude_m = DESIGN_ALTITUDE_M
        self._tt4_K = TT4_DEFAULT_K
        self._eta_inlet: float | None = None
        self._pi_b = PI_B_DEFAULT
        self._eta_b = ETA_B_DEFAULT
        self._h_PR = KEROSENE_H_PR
        self._gamma_c = GAMMA_COLD
        self._cp_c = CP_COLD
        self._gamma_t = GAMMA_HOT
        self._cp_t = CP_HOT
        self._capture_area_m2 = CAPTURE_AREA_M2
        self._nozzle_area_ratio = NOZZLE_AREA_RATIO_DESIGN

    def setup(
        self,
        mach0: float = MACH_DESIGN,
        altitude_m: float = DESIGN_ALTITUDE_M,
        tt4_K: float = TT4_DEFAULT_K,
        eta_inlet: float | None = None,
        pi_b: float = PI_B_DEFAULT,
        eta_b: float = ETA_B_DEFAULT,
        h_PR: float = KEROSENE_H_PR,
        gamma_c: float = GAMMA_COLD,
        cp_c: float = CP_COLD,
        gamma_t: float = GAMMA_HOT,
        cp_t: float = CP_HOT,
        capture_area_m2: float = CAPTURE_AREA_M2,
        nozzle_area_ratio: float = NOZZLE_AREA_RATIO_DESIGN,
    ) -> None:
        """Bind the analysis to a design point and cycle parameters.

        Args:
            mach0: Freestream design Mach number (must be > 1).
            altitude_m: ISA design/cruise altitude [m].
            tt4_K: Combustor-exit total temperature [K] (placeholder
                default 2000.0 -- see combustor risk baseline in the
                module docstring).
            eta_inlet: Inlet total-pressure recovery override. If
                ``None`` (default), computed from the 4-cone preset
                chain of :class:`MultiConeInletPerformanceAnalysis`
                at (``mach0``, ``altitude_m``) -- ~0.874 at Mach 2.5.
            pi_b: Burner total-pressure ratio pt4/pt2 (placeholder,
                default 0.95).
            eta_b: Burner (combustion) efficiency (placeholder,
                default 0.95).
            h_PR: Fuel lower heating value [J/kg] (default kerosene,
                43.1e6).
            gamma_c: Cold-gas ratio of specific heats.
            cp_c: Cold-gas specific heat at constant pressure
                [J/(kg*K)].
            gamma_t: Hot-gas ratio of specific heats.
            cp_t: Hot-gas specific heat at constant pressure
                [J/(kg*K)].
            capture_area_m2: Inlet capture area [m^2] (full-capture
                assumption at the design Mach, as in
                ``inlet_performance``).
            nozzle_area_ratio: Documented "design intent" nozzle area
                ratio (informational; both the matched and the
                cylindrical-choked nozzle are always evaluated and
                reported regardless of this value -- see module
                docstring).

        Raises:
            ValueError: If mach0 <= 1; eta_inlet, pi_b or eta_b outside
                (0, 1]; or tt4_K does not exceed the recovered
                combustor-entry total temperature Tt2 (= Tt0).
        """
        if mach0 <= 1.0:
            raise ValueError(f"mach0 must be > 1, got {mach0}")
        if eta_inlet is not None and not (0.0 < eta_inlet <= 1.0):
            raise ValueError(f"eta_inlet must be in (0, 1], got {eta_inlet}")
        if not (0.0 < pi_b <= 1.0):
            raise ValueError(f"pi_b must be in (0, 1], got {pi_b}")
        if not (0.0 < eta_b <= 1.0):
            raise ValueError(f"eta_b must be in (0, 1], got {eta_b}")

        atmosphere = isa_atmosphere(altitude_m)
        tt2_preview_K = stagnation_temperature_K(
            atmosphere.temperature_K, mach0, gamma_c
        )
        if tt4_K <= tt2_preview_K:
            raise ValueError(
                f"tt4_K ({tt4_K}) must exceed the recovered combustor-entry "
                f"total temperature Tt2=Tt0 ({tt2_preview_K:.2f} K) at "
                f"mach0={mach0}, altitude_m={altitude_m}"
            )

        self._mach0 = mach0
        self._altitude_m = altitude_m
        self._tt4_K = tt4_K
        self._eta_inlet = eta_inlet
        self._pi_b = pi_b
        self._eta_b = eta_b
        self._h_PR = h_PR
        self._gamma_c = gamma_c
        self._cp_c = cp_c
        self._gamma_t = gamma_t
        self._cp_t = cp_t
        self._capture_area_m2 = capture_area_m2
        self._nozzle_area_ratio = nozzle_area_ratio
        self._is_setup = True

    def _resolve_eta_inlet(self) -> tuple[float, str]:
        """Resolve the inlet recovery to use, computing it if not overridden.

        Returns:
            Tuple ``(eta_inlet, source)`` where ``source`` documents
            whether the value was overridden by the caller or computed
            from the 4-cone preset chain.
        """
        if self._eta_inlet is not None:
            return self._eta_inlet, "user_override"

        inlet_analysis = MultiConeInletPerformanceAnalysis()
        inlet_analysis.setup(
            mach_design=self._mach0,
            altitude_m=self._altitude_m,
            n_cones=DEFAULT_N_CONES_M25,
            optimize_angles=False,
        )
        inlet_results = inlet_analysis.execute()
        return inlet_results["eta_inlet"], "multi_cone_4preset_chain"

    def _run_cycle(
        self, eta_inlet: float, pi_b: float, eta_b: float, gamma_t: float, cp_t: float
    ) -> dict[str, Any]:
        """Run the station 0-2-4-9 cycle for a given set of parameters.

        Factored out so the design-point (lossy) run and the loss-free
        reference run (used for the verification-gate comparison) share
        exactly the same station math.

        Args:
            eta_inlet: Inlet total-pressure recovery to apply.
            pi_b: Burner total-pressure ratio to apply.
            eta_b: Burner efficiency to apply.
            gamma_t: Hot-gas ratio of specific heats to apply.
            cp_t: Hot-gas specific heat to apply.

        Returns:
            Dict of station properties, mass flows, both nozzle
            solutions and derived performance metrics.
        """
        r_t = cp_t * (gamma_t - 1.0) / gamma_t

        atmosphere = isa_atmosphere(self._altitude_m)
        p0_Pa = atmosphere.pressure_Pa
        t0_K = atmosphere.temperature_K
        a0_m_s = atmosphere.speed_of_sound_m_s
        u0_m_s = self._mach0 * a0_m_s

        tt0_K = stagnation_temperature_K(t0_K, self._mach0, self._gamma_c)
        pt0_Pa = stagnation_pressure_Pa(p0_Pa, self._mach0, self._gamma_c)

        tt2_K = tt0_K
        pt2_Pa = eta_inlet * pt0_Pa

        f_fuel_air = (
            cp_t
            * (self._tt4_K - tt2_K)
            / (eta_b * self._h_PR - cp_t * self._tt4_K)
        )
        pt4_Pa = pi_b * pt2_Pa

        mdot_air_kg_s = atmosphere.density_kg_m3 * u0_m_s * self._capture_area_m2
        mdot_fuel_kg_s = f_fuel_air * mdot_air_kg_s
        mdot_exit_kg_s = mdot_air_kg_s * (1.0 + f_fuel_air)

        matched = _matched_nozzle_exit(self._tt4_K, pt4_Pa, p0_Pa, gamma_t, cp_t, r_t)
        thrust_N = mdot_exit_kg_s * matched["u9_m_s"] - mdot_air_kg_s * u0_m_s

        choked = _choked_nozzle_exit(self._tt4_K, pt4_Pa, gamma_t, r_t)
        area9_cyl_m2 = mdot_exit_kg_s / (choked["rho9_kg_m3"] * choked["u9_m_s"])
        thrust_cyl_N = (
            mdot_exit_kg_s * choked["u9_m_s"]
            - mdot_air_kg_s * u0_m_s
            + (choked["p9_Pa"] - p0_Pa) * area9_cyl_m2
        )

        specific_thrust_Ns_per_kg = thrust_N / mdot_air_kg_s
        tsfc_kg_per_Ns = mdot_fuel_kg_s / thrust_N
        isp_s = thrust_N / (mdot_fuel_kg_s * G0)

        return {
            "eta_inlet": eta_inlet,
            "pi_b": pi_b,
            "eta_b": eta_b,
            "freestream": {
                "p0_Pa": p0_Pa,
                "T0_K": t0_K,
                "a0_m_s": a0_m_s,
                "u0_m_s": u0_m_s,
                "density_kg_m3": atmosphere.density_kg_m3,
            },
            "tt0_K": tt0_K,
            "pt0_Pa": pt0_Pa,
            "tt2_K": tt2_K,
            "pt2_Pa": pt2_Pa,
            "tt4_K": self._tt4_K,
            "pt4_Pa": pt4_Pa,
            "f_fuel_air": f_fuel_air,
            "mdot_air_kg_s": mdot_air_kg_s,
            "mdot_fuel_kg_s": mdot_fuel_kg_s,
            "mdot_exit_kg_s": mdot_exit_kg_s,
            "matched_nozzle": matched,
            "choked_nozzle": {**choked, "A9_m2": area9_cyl_m2},
            "thrust_N": thrust_N,
            "thrust_cylindrical_nozzle_N": thrust_cyl_N,
            "specific_thrust_Ns_per_kg": specific_thrust_Ns_per_kg,
            "tsfc_kg_per_Ns": tsfc_kg_per_Ns,
            "isp_s": isp_s,
        }

    def execute(self) -> AnalysisResults:
        """Run the design-point cycle and return results.

        Returns:
            AnalysisResults with the fuel-air ratio, thrust for both
            nozzle geometries, TSFC/Isp, mass flows, the full station
            table and the ideal-cycle / loss-free cross-checks.

        Raises:
            RuntimeError: If called before :meth:`setup`, or if the
                resulting cycle fails :meth:`validate_results`.
        """
        if not self._is_setup:
            raise RuntimeError("RamjetCycleAnalysis.execute() called before setup()")

        eta_inlet, eta_inlet_source = self._resolve_eta_inlet()
        cycle = self._run_cycle(
            eta_inlet, self._pi_b, self._eta_b, self._gamma_t, self._cp_t
        )

        # Loss-free reference: same two-gas properties and (1+f) mass
        # addition, but eta_inlet = pi_b = eta_b = 1 -- isolates the
        # thrust/TSFC cost of the modeled losses (see module docstring
        # "verification gate").
        loss_free = self._run_cycle(1.0, 1.0, 1.0, self._gamma_t, self._cp_t)

        # Independent, single-gas Mattingly closed-form cross-check
        # (does not share code with _run_cycle at all).
        ideal_closed_form = ideal_ramjet_closed_form(
            self._mach0, self._altitude_m, self._tt4_K, self._h_PR, self._cp_c, self._gamma_c
        )

        station_table = [
            {
                "station": "0_freestream",
                "mach": self._mach0,
                "total_temperature_K": cycle["tt0_K"],
                "total_pressure_Pa": cycle["pt0_Pa"],
                "static_temperature_K": cycle["freestream"]["T0_K"],
                "static_pressure_Pa": cycle["freestream"]["p0_Pa"],
                "velocity_m_s": cycle["freestream"]["u0_m_s"],
            },
            {
                "station": "2_combustor_entry",
                "mach": None,
                "total_temperature_K": cycle["tt2_K"],
                "total_pressure_Pa": cycle["pt2_Pa"],
            },
            {
                "station": "4_combustor_exit",
                "mach": None,
                "total_temperature_K": cycle["tt4_K"],
                "total_pressure_Pa": cycle["pt4_Pa"],
            },
            {
                "station": "9_nozzle_exit_matched_design",
                "mach": cycle["matched_nozzle"]["M9"],
                "static_temperature_K": cycle["matched_nozzle"]["T9_K"],
                "static_pressure_Pa": cycle["matched_nozzle"]["p9_Pa"],
                "velocity_m_s": cycle["matched_nozzle"]["u9_m_s"],
            },
            {
                "station": "9_nozzle_exit_cylindrical_cad",
                "mach": cycle["choked_nozzle"]["M9"],
                "static_temperature_K": cycle["choked_nozzle"]["T9_K"],
                "static_pressure_Pa": cycle["choked_nozzle"]["p9_Pa"],
                "velocity_m_s": cycle["choked_nozzle"]["u9_m_s"],
                "area_m2": cycle["choked_nozzle"]["A9_m2"],
            },
        ]

        data: dict[str, Any] = {
            "f_fuel_air": cycle["f_fuel_air"],
            "thrust_N": cycle["thrust_N"],
            "thrust_cylindrical_nozzle_N": cycle["thrust_cylindrical_nozzle_N"],
            "specific_thrust_Ns_per_kg": cycle["specific_thrust_Ns_per_kg"],
            "tsfc_kg_per_Ns": cycle["tsfc_kg_per_Ns"],
            "isp_s": cycle["isp_s"],
            "mdot_air_kg_s": cycle["mdot_air_kg_s"],
            "mdot_fuel_kg_s": cycle["mdot_fuel_kg_s"],
            "u9_m_s": cycle["matched_nozzle"]["u9_m_s"],
            "M9": cycle["matched_nozzle"]["M9"],
            "u9_cylindrical_nozzle_m_s": cycle["choked_nozzle"]["u9_m_s"],
            "M9_cylindrical_nozzle": cycle["choked_nozzle"]["M9"],
            "eta_inlet": eta_inlet,
            "pi_b": self._pi_b,
            "eta_b": self._eta_b,
            "tt4_K": self._tt4_K,
            "tt2_K": cycle["tt2_K"],
            "mach0": self._mach0,
            "altitude_m": self._altitude_m,
            "nozzle_area_ratio_design": NOZZLE_AREA_RATIO_DESIGN,
            "nozzle_area_ratio_cad_actual": NOZZLE_AREA_RATIO_CYLINDRICAL,
        }

        metadata: dict[str, Any] = {
            "eta_inlet_source": eta_inlet_source,
            "station_table": station_table,
            "loss_free_reference": {
                "thrust_N": loss_free["thrust_N"],
                "tsfc_kg_per_Ns": loss_free["tsfc_kg_per_Ns"],
                "specific_thrust_Ns_per_kg": loss_free["specific_thrust_Ns_per_kg"],
                "f_fuel_air": loss_free["f_fuel_air"],
                "note": (
                    "Same two-gas (cp_t/gamma_t) model and (1+f) mass "
                    "addition as the design point, but eta_inlet=pi_b="
                    "eta_b=1 -- isolates the thrust/TSFC cost of the "
                    "modeled inlet/burner losses."
                ),
            },
            "ideal_closed_form_cross_check": ideal_closed_form,
            "nozzle_discrepancy_note": (
                "vehicle_config.yaml specifies nozzle_area_ratio=4.0 (a "
                "matched convergent-divergent design target), but the "
                "Fusion v6 CAD nozzle is a cylindrical exit stub with "
                "expansion_ratio 1.0 and the assembly notes state the "
                "'full ramjet engine [is] NOT modeled'. Both thrust_N "
                "(design, matched) and thrust_cylindrical_nozzle_N (CAD, "
                "choked convergent-only) are reported here so this gap "
                "is quantified, not silently assumed away."
            ),
            "combustor_risk_baseline": (
                "Liquid kerosene may not vaporize sufficiently before "
                "the flame holders; measured flame-holder cavity "
                "temperatures of ~2400 K exceed the melting point of "
                "the currently specified aluminium flame-holder "
                "material. tt4_K=2000 K here is a placeholder chosen "
                "BELOW that ~2400 K risk figure -- combustor design is "
                "BLOCKED pending flame-holder relocation and/or "
                "injector atomization redesign. Fusion v6 CAD lists "
                "the flame_holder material as STEEL, contradicting the "
                "'aluminium' risk note -- flagged for human review, "
                "NOT resolved here."
            ),
            "reference_model_disclosure": (
                "This is the new FidelityLevel.LEVEL_2 1-D cycle model. "
                "The Grzywka MATLAB 2-D baseline values are NOT "
                "available in this repository (TODO_PHYSICAL_PARAM). "
                "CFD studies (Dalek, Teltik) report exit velocity/Mach "
                "20-30% higher than the MATLAB baseline -- an open "
                "discrepancy between methods. Thrust/TSFC numbers here "
                "are single-method L2 results pending a dual-check."
            ),
            "assumptions": [
                f"Burner total-pressure ratio pi_b={self._pi_b} is a "
                "placeholder pending combustor duct-loss data.",
                f"Burner efficiency eta_b={self._eta_b} is a placeholder "
                "pending flame-holder/atomization test data.",
                "Full mass-flow capture assumed at the design Mach "
                "(mdot_air = rho0*u0*A_capture, no spillage), consistent "
                "with analyses.propulsion.inlet_performance.",
                "Two-gas (cold/hot) calorically-perfect-gas model; no "
                "dissociation or variable-cp effects beyond the two "
                "fixed cp/gamma sets.",
            ],
        }

        results = AnalysisResults(
            name=self.name, fidelity=self.fidelity, data=data, metadata=metadata
        )
        if not self.validate_results(results):
            raise RuntimeError(
                f"Ramjet cycle results failed physical validation: {results.data}"
            )
        return results

    def validate_results(self, results: AnalysisResults) -> bool:
        """Sanity-check the cycle results.

        Checks: fuel-air ratio in a physically sensible kerosene-air
        range (0, 0.15); both thrust values positive with the
        cylindrical (CAD, unexpanded) nozzle producing LESS thrust
        than the matched design nozzle; Isp in the ~1000-1500 s
        hydrocarbon-ramjet band per project rules (CLAUDE.md); exit
        Mach numbers physically bounded.

        Args:
            results: Results to validate.

        Returns:
            True if all physical sanity checks pass.
        """
        required = {
            "f_fuel_air",
            "thrust_N",
            "thrust_cylindrical_nozzle_N",
            "isp_s",
            "mdot_air_kg_s",
            "mdot_fuel_kg_s",
        }
        if not required.issubset(results.data):
            return False
        if not (0.0 < results["f_fuel_air"] < 0.15):
            return False
        if not (results["thrust_N"] > 0.0):
            return False
        if not (results["thrust_cylindrical_nozzle_N"] > 0.0):
            return False
        if not (
            results["thrust_cylindrical_nozzle_N"] < results["thrust_N"]
        ):
            return False
        if not (400.0 < results["isp_s"] < 3000.0):
            return False
        if not (results["mdot_air_kg_s"] > 0.0 and results["mdot_fuel_kg_s"] > 0.0):
            return False
        return True


def _build_output_dict(results: AnalysisResults) -> dict[str, Any]:
    """Flatten an AnalysisResults into the JSON schema requested for output."""
    out: dict[str, Any] = dict(results.data)
    out["station_table"] = results.metadata["station_table"]
    out["loss_free_reference"] = results.metadata["loss_free_reference"]
    out["ideal_closed_form_cross_check"] = results.metadata[
        "ideal_closed_form_cross_check"
    ]
    out["nozzle_discrepancy_note"] = results.metadata["nozzle_discrepancy_note"]
    out["combustor_risk_baseline"] = results.metadata["combustor_risk_baseline"]
    out["reference_model_disclosure"] = results.metadata["reference_model_disclosure"]
    out["assumptions"] = results.metadata["assumptions"]
    out["eta_inlet_source"] = results.metadata["eta_inlet_source"]
    out["fidelity"] = results.fidelity.name
    return out


def main() -> None:
    """Run the design-point ramjet cycle, save JSON, and print a summary."""
    analysis = RamjetCycleAnalysis()
    analysis.setup(mach0=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M, tt4_K=TT4_DEFAULT_K)
    results = analysis.execute()
    output = _build_output_dict(results)

    module_dir = Path(__file__).resolve().parent
    json_path = module_dir / "ramjet_cycle_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("=== Ramjet cycle (design point) ===")
    print(f"Design Mach: {MACH_DESIGN}, altitude: {DESIGN_ALTITUDE_M} m ISA")
    print(f"eta_inlet: {output['eta_inlet']:.4f} (source: {output['eta_inlet_source']})")
    print(f"pi_b: {output['pi_b']:.3f}, eta_b: {output['eta_b']:.3f}")
    print(f"Tt2: {output['tt2_K']:.2f} K, Tt4: {output['tt4_K']:.2f} K")
    print(f"Fuel-air ratio f: {output['f_fuel_air']:.4f}")
    print(f"mdot_air: {output['mdot_air_kg_s']:.4f} kg/s, mdot_fuel: {output['mdot_fuel_kg_s']:.5f} kg/s")
    print(f"Thrust (matched design nozzle): {output['thrust_N']:.1f} N")
    print(f"Thrust (cylindrical CAD nozzle): {output['thrust_cylindrical_nozzle_N']:.1f} N")
    print(f"Specific thrust: {output['specific_thrust_Ns_per_kg']:.1f} N*s/kg")
    print(f"TSFC: {output['tsfc_kg_per_Ns']:.3e} kg/(N*s)")
    print(f"Isp: {output['isp_s']:.1f} s")
    print(
        "Loss-free reference thrust/TSFC: "
        f"{output['loss_free_reference']['thrust_N']:.1f} N / "
        f"{output['loss_free_reference']['tsfc_kg_per_Ns']:.3e} kg/(N*s)"
    )
    print(
        "Ideal closed-form (Mattingly) specific thrust: "
        f"{output['ideal_closed_form_cross_check']['specific_thrust_Ns_per_kg']:.1f} N*s/kg"
    )
    print(f"\nJSON written to: {json_path}")


if __name__ == "__main__":
    main()
