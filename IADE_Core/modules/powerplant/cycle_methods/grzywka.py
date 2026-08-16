# MELprop-IADE | analyses.propulsion.combustor_nozzle_cycle | v0.1.0
"""Grzywka-station combustor + nozzle cycle model (stations 1-2-21-3).

Complementary — NOT a replacement — to
:mod:`analyses.propulsion.ramjet_cycle`. Where ``ramjet_cycle`` uses the
classical Mattingly ramjet station numbering (0-2-4-9) with a burner
total-pressure ratio ``pi_b`` and dual (matched / cylindrical) nozzle
reporting, this module reproduces the station numbering, loss
coefficients and three-thrust-model reporting of Grzywka's ramjet
combustor/nozzle analysis (Grzywka, *Analiza numeryczna komory spalania
i dyszy silnika strumieniowego*, dyplom/praca, Politechnika Warszawska,
2022 — the project's primary combustor/nozzle reference, cited here the
same way ``ramjet_cycle`` cites Mattingly / Hill & Peterson).

Grzywka station numbering used throughout:

    1  -> combustor inlet (post-diffuser; the inlet total-pressure
          recovery ``eta_inlet`` is ALREADY applied here, so this is the
          same physical plane as ``ramjet_cycle`` station 2). Adiabatic
          up to this point: ``Tt1 = Tt0``.
    2  -> combustor exit (post heat-addition to ``combustor_exit_temp_K``,
          with the combustion-chamber total-pressure ratio ``pi_CC``:
          ``pt2 = pi_CC * pt1``).
    21 -> nozzle throat. **Choked, ``Ma_21 = 1`` ALWAYS**, with a
          **DYNAMIC** cross-sectional area ``A21`` solved from continuity
          (``mdot = rho*A*u`` at sonic conditions) for the current cycle
          mass flow and station-2 total conditions. ``A21`` is therefore
          a function of flight speed ``V`` and altitude ``H`` and is NEVER
          hard-coded to a fixed diameter.
    3  -> nozzle exit. Isentropic expansion of the hot gas to ambient
          static pressure ``p0`` (fully expanded), with the nozzle-duct
          total-pressure loss ``pi_nozzle`` applied on top of the
          isentropic expansion (``pt3_eff = pi_nozzle * pt2``).

Three thrust models (Grzywka Sec. 6.2.2), the standard
ideal / combustor-loss / real hierarchy — ALL THREE ARE ALWAYS
REPORTED, never collapsed to a single number:

    Thi -- IDEAL thrust. No combustor or nozzle total-pressure losses
           (``pi_CC = 1``, ``pi_nozzle = 1``); fully-expanded isentropic
           1-D reference. Upper bound.
    Th1 -- thrust with the COMBUSTOR total-pressure loss ``pi_CC``
           included, but the nozzle still idealized (``pi_nozzle = 1``,
           fully expanded).
    Th2 -- REAL thrust with BOTH ``pi_CC`` and ``pi_nozzle`` losses
           included. Most conservative; this is the field consumed as
           the nominal by later cruise-wiring work (Phase 3b).

The three share identical mass flow, ``Tt1``, ``Tt2`` and fuel-air ratio
(only the delivered nozzle total pressure differs), so the physical
hierarchy ``Thi >= Th1 >= Th2`` MUST hold and is asserted both in
:meth:`GrzywkaCombustorNozzleAnalysis.validate_results` and in the unit
tests.

Fidelity: this is a 1-D station cycle (closed-form compressible-flow
relations with a continuity-solved sonic throat) — the same rung as
``ramjet_cycle``. It is kept at ``FidelityLevel.LEVEL_2`` deliberately:
the extra throat station (21) is finer station granularity, NOT a
higher-fidelity method class (LEVEL_3 is reserved for RANS CFD / FEM per
:class:`IADE_Core.component_base.FidelityLevel`).

Cross-checks surfaced (not hidden) in metadata, matching this repo's
convention of quantifying method discrepancies:
    * Brayton T2 cross-check -- an independently-coded, single-gas
      (cold-cp) Brayton heat-addition estimate of the station-2 total
      temperature, compared with the station model's ``Tt2``. Flagged
      (logged, NOT failed) if the delta exceeds 5%.
    * V3 vs Teltik 2024 CFD (~1047 m/s at Mach 2.5 / 6000 m, docs/
      assumptions.md A15) -- logged as a delta, agreement NOT forced.
    * Implied nozzle area ratio A3/A21 vs vehicle_config.yaml
      ``nozzle_area_ratio`` = 4.0 (design intent) AND the Fusion v6 CAD
      cylindrical stub (``expansion_ratio`` = 1.0) -- both logged, the
      CAD-vs-design gap quantified rather than silently resolved.

References:
    Grzywka, *Analiza numeryczna komory spalania i dyszy silnika
    strumieniowego*, Politechnika Warszawska, 2022 -- station numbering
    (1-2-21-3), loss coefficients ``pi_CC`` / ``pi_nozzle``, and the
    Thi / Th1 / Th2 three-thrust decomposition (Sec. 6.2.2).
    Mattingly, J. D., *Elements of Gas Turbine Propulsion*, 2nd ed.,
    AIAA, 2006 -- Ch. 3, 9 (ramjet cycle, choked-nozzle relations).
    Hill, P. G. & Peterson, C. R., *Mechanics and Thermodynamics of
    Propulsion*, 2nd ed., Addison-Wesley, 1992 -- Ch. 5, 11.
    Anderson, J. D., *Modern Compressible Flow*, 3rd ed., McGraw-Hill,
    2003 -- Ch. 3 (isentropic / choked / stagnation relations).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    # Allow `python3 analyses/propulsion/combustor_nozzle_cycle.py` direct
    # execution by putting the repository root (three levels up) on
    # sys.path so the `core` package resolves, mirroring conftest.py.
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from IADE_Core.modules.powerplant.inlet_methods.wedge import (
    CAPTURE_AREA_M2,
    DEFAULT_N_CONES_M25,
    DESIGN_ALTITUDE_M,
    G0,
    GAMMA as GAMMA_COLD,
    MACH_DESIGN,
    MultiConeInletPerformanceAnalysis,
    isa_atmosphere,
)
from IADE_Core.modules.powerplant.cycle_methods.mattingly import (
    CP_COLD,
    CP_HOT,
    ETA_B_DEFAULT,
    GAMMA_HOT,
    KEROSENE_H_PR,
    NOZZLE_AREA_RATIO_CYLINDRICAL,
    NOZZLE_AREA_RATIO_DESIGN,
    R_HOT,
    TT4_DEFAULT_K,
    stagnation_pressure_Pa,
    stagnation_temperature_K,
)
from IADE_Core.Foundation.component_base import AnalysisResults, BaseAnalysis, FidelityLevel

# --------------------------------------------------------------------------
# Grzywka 2022 loss coefficients (SI / dimensionless)
# --------------------------------------------------------------------------

#: Combustion-chamber total-pressure ratio pt2/pt1 (station 1->2),
#: Grzywka 2022 (docs/assumptions.md A13).
PI_CC: float = 0.8924

#: Nozzle total-pressure ratio pt3/pt2 (station 2->3), the nozzle-duct
#: loss applied on top of the isentropic expansion, Grzywka 2022
#: (docs/assumptions.md A13).
PI_NOZZLE: float = 0.97

#: Combustor-exit total temperature Tt2 [K] -- placeholder from
#: Hangar/ramjet_rocket/vehicle_config.yaml stage_2.combustor_temp_K
#: (TBD; deliberately BELOW the ~2400 K flame-holder risk figure, see the
#: combustor risk baseline shared with ramjet_cycle / assumptions A4).
COMBUSTOR_EXIT_TEMP_DEFAULT_K: float = TT4_DEFAULT_K

#: Material total-temperature ceiling used as a sanity bound on the
#: combustor exit temperature [K]. TODO_PHYSICAL_PARAM: the ~2400 K
#: flame-holder cavity figure (assumptions A4) is the governing risk
#: number; 2500 K here is a loose upper sanity bound, not a cleared
#: material limit.
COMBUSTOR_TEMP_CEILING_K: float = 2500.0

# --------------------------------------------------------------------------
# Teltik 2024 CFD reference point (docs/assumptions.md A15)
# --------------------------------------------------------------------------

#: Teltik 2024 CFD nozzle-exit velocity [m/s] at the reference condition.
TELTIK_V3_M_S: float = 1047.0

#: Teltik 2024 CFD reference Mach number.
TELTIK_MACH: float = 2.5

#: Teltik 2024 CFD reference altitude [m].
TELTIK_ALTITUDE_M: float = 6000.0


def choked_throat_area_m2(
    mdot_kg_s: float,
    tt2_K: float,
    pt2_Pa: float,
    gamma_t: float,
    r_t: float,
) -> dict[str, float]:
    """Solve the sonic (choked, Ma=1) nozzle-throat area from continuity.

    The throat (Grzywka station 21) is choked at ALL flight conditions.
    Its area is therefore not a fixed geometric constant but the area
    required to pass the current cycle mass flow at sonic conditions for
    the given station-2 total state (``mdot = rho*A*u`` with ``u = a``,
    ``Ma = 1``; Anderson, *Modern Compressible Flow*, 3rd ed., Ch. 3
    critical/choked relations):

        T21 = Tt2 * 2/(gamma+1)
        p21 = pt2 * (2/(gamma+1))^(gamma/(gamma-1))
        a21 = sqrt(gamma*R*T21)             (= u21, since Ma21 = 1)
        rho21 = p21/(R*T21)
        A21 = mdot / (rho21 * a21)

    Args:
        mdot_kg_s: Nozzle mass flow (combustor exit, air + fuel) [kg/s].
        tt2_K: Combustor-exit (station 2) total temperature [K].
        pt2_Pa: Combustor-exit (station 2) total pressure [Pa].
        gamma_t: Hot-gas ratio of specific heats.
        r_t: Hot-gas specific gas constant [J/(kg*K)].

    Returns:
        Dict with ``A21_m2``, ``D21_m`` (equivalent circular diameter),
        ``T21_K``, ``p21_Pa``, ``u21_m_s`` (= sonic speed), ``rho21_kg_m3``
        and ``Ma21`` (== 1.0).
    """
    critical_ratio = 2.0 / (gamma_t + 1.0)
    t21_K = tt2_K * critical_ratio
    p21_Pa = pt2_Pa * critical_ratio ** (gamma_t / (gamma_t - 1.0))
    a21_m_s = math.sqrt(gamma_t * r_t * t21_K)
    rho21_kg_m3 = p21_Pa / (r_t * t21_K)
    a21_area_m2 = mdot_kg_s / (rho21_kg_m3 * a21_m_s)
    d21_m = math.sqrt(4.0 * a21_area_m2 / math.pi)
    return {
        "A21_m2": a21_area_m2,
        "D21_m": d21_m,
        "T21_K": t21_K,
        "p21_Pa": p21_Pa,
        "u21_m_s": a21_m_s,
        "rho21_kg_m3": rho21_kg_m3,
        "Ma21": 1.0,
    }


def fully_expanded_exit(
    tt2_K: float,
    pt_nozzle_Pa: float,
    p0_Pa: float,
    mdot_kg_s: float,
    gamma_t: float,
    cp_t: float,
    r_t: float,
) -> dict[str, float]:
    """Isentropically expand the hot gas to ambient static pressure.

    Fully-expanded (``p3 = p0``) nozzle exit (Grzywka station 3). The
    delivered nozzle total pressure ``pt_nozzle_Pa`` is what encodes the
    loss level of a given thrust model (``pt1``, ``pi_CC*pt1`` or
    ``pi_nozzle*pi_CC*pt1``); a lower total pressure yields a higher exit
    static temperature and thus a lower exit velocity (Anderson Ch. 3
    isentropic relations; Mattingly Ch. 9):

        T3 = Tt2 * (p0/pt_nozzle)^((gamma-1)/gamma)
        V3 = sqrt(2*cp*(Tt2 - T3))

    Args:
        tt2_K: Combustor-exit total temperature [K].
        pt_nozzle_Pa: Total pressure delivered to the nozzle [Pa].
        p0_Pa: Ambient (freestream) static pressure [Pa].
        mdot_kg_s: Nozzle mass flow [kg/s].
        gamma_t: Hot-gas ratio of specific heats.
        cp_t: Hot-gas specific heat at constant pressure [J/(kg*K)].
        r_t: Hot-gas specific gas constant [J/(kg*K)].

    Returns:
        Dict with ``T3_K``, ``p3_Pa`` (== p0_Pa), ``V3_m_s``,
        ``rho3_kg_m3``, ``A3_m2`` and ``Ma3``.
    """
    t3_K = tt2_K * (p0_Pa / pt_nozzle_Pa) ** ((gamma_t - 1.0) / gamma_t)
    v3_m_s = math.sqrt(2.0 * cp_t * (tt2_K - t3_K))
    rho3_kg_m3 = p0_Pa / (r_t * t3_K)
    a3_area_m2 = mdot_kg_s / (rho3_kg_m3 * v3_m_s)
    a3_speed_m_s = math.sqrt(gamma_t * r_t * t3_K)
    return {
        "T3_K": t3_K,
        "p3_Pa": p0_Pa,
        "V3_m_s": v3_m_s,
        "rho3_kg_m3": rho3_kg_m3,
        "A3_m2": a3_area_m2,
        "Ma3": v3_m_s / a3_speed_m_s,
    }


def brayton_t2_estimate_K(
    tt1_K: float,
    f_fuel_air: float,
    eta_b: float,
    h_PR: float,
    cp_cold: float,
) -> float:
    """Independent single-gas Brayton estimate of the combustor-exit Tt2.

    Deliberately a SEPARATE code path from the station model (it does not
    call :func:`choked_throat_area_m2` / :func:`fully_expanded_exit`): a
    constant-``cp`` Brayton heat-addition to the COLD-gas specific heat
    (Hill & Peterson Ch. 5 ideal-cycle heat addition):

        Tt2_brayton = Tt1 + f*eta_b*h_PR / (cp_cold*(1 + f))

    The station model instead uses the HOT-gas ``cp_t`` and a different
    algebraic sink term, so the two are expected to disagree; the delta
    is surfaced in metadata (flagged if > 5%) rather than forced to
    match, per this repo's method-discrepancy convention.

    Args:
        tt1_K: Combustor-inlet total temperature [K].
        f_fuel_air: Fuel-air ratio [-].
        eta_b: Combustion efficiency [-].
        h_PR: Fuel lower heating value [J/kg].
        cp_cold: Cold-gas specific heat at constant pressure [J/(kg*K)].

    Returns:
        Brayton-estimated combustor-exit total temperature [K].
    """
    return tt1_K + f_fuel_air * eta_b * h_PR / (cp_cold * (1.0 + f_fuel_air))


class GrzywkaCombustorNozzleAnalysis(BaseAnalysis):
    """Grzywka-station combustor+nozzle cycle (stations 1-2-21-3).

    Reports the three-thrust decomposition (``Thi`` / ``Th1`` / ``Th2``)
    with a dynamically-solved choked throat area ``A21`` (see the module
    docstring). 1-D station cycle -> ``FidelityLevel.LEVEL_2`` (the extra
    throat station is finer granularity, not a higher method class; see
    the module docstring for the LEVEL_2-vs-LEVEL_3 justification).

    Example:
        >>> analysis = GrzywkaCombustorNozzleAnalysis()
        >>> analysis.setup(mach0=2.5, altitude_m=10_000.0)
        >>> results = analysis.execute()
        >>> results["Thi_N"] >= results["Th1_N"] >= results["Th2_N"]  # doctest: +SKIP
    """

    fidelity = FidelityLevel.LEVEL_2

    def __init__(self, name: str = "grzywka_combustor_nozzle_cycle") -> None:
        super().__init__(name)
        self._mach0 = MACH_DESIGN
        self._altitude_m = DESIGN_ALTITUDE_M
        self._tt2_K = COMBUSTOR_EXIT_TEMP_DEFAULT_K
        self._eta_inlet: float | None = None
        self._pi_cc = PI_CC
        self._pi_nozzle = PI_NOZZLE
        self._eta_b = ETA_B_DEFAULT
        self._h_PR = KEROSENE_H_PR
        self._gamma_t = GAMMA_HOT
        self._cp_t = CP_HOT
        self._r_t = R_HOT
        self._cp_cold = CP_COLD
        self._gamma_cold = GAMMA_COLD
        self._capture_area_m2 = CAPTURE_AREA_M2

    def setup(
        self,
        mach0: float = MACH_DESIGN,
        altitude_m: float = DESIGN_ALTITUDE_M,
        combustor_exit_temp_K: float = COMBUSTOR_EXIT_TEMP_DEFAULT_K,
        eta_inlet: float | None = None,
        pi_cc: float = PI_CC,
        pi_nozzle: float = PI_NOZZLE,
        eta_b: float = ETA_B_DEFAULT,
        h_PR: float = KEROSENE_H_PR,
        gamma_t: float = GAMMA_HOT,
        cp_t: float = CP_HOT,
        cp_cold: float = CP_COLD,
        capture_area_m2: float = CAPTURE_AREA_M2,
    ) -> None:
        """Bind the analysis to a design point and Grzywka loss set.

        Args:
            mach0: Freestream Mach number (must be > 1).
            altitude_m: ISA altitude [m].
            combustor_exit_temp_K: Station-2 total temperature Tt2 [K]
                (placeholder default 2000 -- see the combustor risk
                baseline in ramjet_cycle / assumptions A4).
            eta_inlet: Inlet total-pressure recovery override. If ``None``
                (default), computed from the 4-cone preset chain of
                :class:`MultiConeInletPerformanceAnalysis` at (``mach0``,
                ``altitude_m``), exactly as ``ramjet_cycle`` does.
            pi_cc: Combustion-chamber total-pressure ratio pt2/pt1
                (Grzywka, default 0.8924).
            pi_nozzle: Nozzle-duct total-pressure ratio pt3/pt2 (Grzywka,
                default 0.97).
            eta_b: Combustion efficiency (placeholder, default 0.95 --
                shared with ramjet_cycle).
            h_PR: Fuel lower heating value [J/kg] (default kerosene).
            gamma_t: Hot-gas ratio of specific heats.
            cp_t: Hot-gas specific heat at constant pressure [J/(kg*K)].
            cp_cold: Cold-gas specific heat (for the Brayton cross-check).
            capture_area_m2: Inlet capture area [m^2] (full-capture
                assumption, as in inlet_performance / ramjet_cycle).

        Raises:
            ValueError: If mach0 <= 1; pi_cc, pi_nozzle, eta_b or (when
                given) eta_inlet outside (0, 1]; or combustor_exit_temp_K
                does not exceed the recovered combustor-inlet total
                temperature Tt1 (= Tt0).
        """
        if mach0 <= 1.0:
            raise ValueError(f"mach0 must be > 1, got {mach0}")
        for label, value in (
            ("pi_cc", pi_cc),
            ("pi_nozzle", pi_nozzle),
            ("eta_b", eta_b),
        ):
            if not (0.0 < value <= 1.0):
                raise ValueError(f"{label} must be in (0, 1], got {value}")
        if eta_inlet is not None and not (0.0 < eta_inlet <= 1.0):
            raise ValueError(f"eta_inlet must be in (0, 1], got {eta_inlet}")

        atmosphere = isa_atmosphere(altitude_m)
        tt1_preview_K = stagnation_temperature_K(
            atmosphere.temperature_K, mach0, self._gamma_cold
        )
        if combustor_exit_temp_K <= tt1_preview_K:
            raise ValueError(
                f"combustor_exit_temp_K ({combustor_exit_temp_K}) must exceed "
                f"the combustor-inlet total temperature Tt1=Tt0 "
                f"({tt1_preview_K:.2f} K) at mach0={mach0}, altitude_m={altitude_m}"
            )

        self._mach0 = mach0
        self._altitude_m = altitude_m
        self._tt2_K = combustor_exit_temp_K
        self._eta_inlet = eta_inlet
        self._pi_cc = pi_cc
        self._pi_nozzle = pi_nozzle
        self._eta_b = eta_b
        self._h_PR = h_PR
        self._gamma_t = gamma_t
        self._cp_t = cp_t
        self._r_t = cp_t * (gamma_t - 1.0) / gamma_t
        self._cp_cold = cp_cold
        self._capture_area_m2 = capture_area_m2
        self._is_setup = True

    def _resolve_eta_inlet(
        self, mach0: float, altitude_m: float
    ) -> tuple[float, str]:
        """Resolve the inlet recovery, computing it if not overridden.

        Args:
            mach0: Freestream Mach number.
            altitude_m: ISA altitude [m].

        Returns:
            Tuple ``(eta_inlet, source)``; ``source`` records whether the
            value was a caller override or the 4-cone preset chain.
        """
        if self._eta_inlet is not None:
            return self._eta_inlet, "user_override"

        inlet_analysis = MultiConeInletPerformanceAnalysis()
        inlet_analysis.setup(
            mach_design=mach0,
            altitude_m=altitude_m,
            n_cones=DEFAULT_N_CONES_M25,
            optimize_angles=False,
        )
        return inlet_analysis.execute()["eta_inlet"], "multi_cone_4preset_chain"

    def _run_condition(self, mach0: float, altitude_m: float) -> dict[str, Any]:
        """Evaluate the full 1-2-21-3 cycle at a single (V, H) condition.

        Factored out so the design point and the Teltik-CFD comparison
        point (Mach 2.5 / 6000 m) share exactly the same station math.

        Args:
            mach0: Freestream Mach number.
            altitude_m: ISA altitude [m].

        Returns:
            Dict with the three thrust models, throat solution, exit
            solutions, mass flows and fuel-air ratio for this condition.
        """
        eta_inlet, eta_inlet_source = self._resolve_eta_inlet(mach0, altitude_m)

        atmosphere = isa_atmosphere(altitude_m)
        p0_Pa = atmosphere.pressure_Pa
        a0_m_s = atmosphere.speed_of_sound_m_s
        u0_m_s = mach0 * a0_m_s

        tt1_K = stagnation_temperature_K(atmosphere.temperature_K, mach0, self._gamma_cold)
        pt0_Pa = stagnation_pressure_Pa(p0_Pa, mach0, self._gamma_cold)
        pt1_Pa = eta_inlet * pt0_Pa

        # Fuel-air ratio from the steady-flow energy balance (hot gas),
        # shared definition with ramjet_cycle (Mattingly Eq. 2.15 /
        # Hill & Peterson Eq. 11.19). Common to all three thrust models.
        f_fuel_air = (
            self._cp_t
            * (self._tt2_K - tt1_K)
            / (self._eta_b * self._h_PR - self._cp_t * self._tt2_K)
        )

        mdot_air_kg_s = atmosphere.density_kg_m3 * u0_m_s * self._capture_area_m2
        mdot_fuel_kg_s = f_fuel_air * mdot_air_kg_s
        mdot_exit_kg_s = mdot_air_kg_s * (1.0 + f_fuel_air)

        # Combustor exit total pressure (real, with the pi_CC loss).
        pt2_real_Pa = self._pi_cc * pt1_Pa

        # Dynamic choked throat (station 21) from the REAL combustor-exit
        # total state -- the physical engine throat.
        throat = choked_throat_area_m2(
            mdot_exit_kg_s, self._tt2_K, pt2_real_Pa, self._gamma_t, self._r_t
        )

        # Three thrust models differ ONLY in the nozzle total pressure.
        def _thrust(pt_nozzle_Pa: float) -> dict[str, float]:
            exit_state = fully_expanded_exit(
                self._tt2_K,
                pt_nozzle_Pa,
                p0_Pa,
                mdot_exit_kg_s,
                self._gamma_t,
                self._cp_t,
                self._r_t,
            )
            thrust_N = mdot_exit_kg_s * exit_state["V3_m_s"] - mdot_air_kg_s * u0_m_s
            return {**exit_state, "thrust_N": thrust_N}

        thi = _thrust(pt1_Pa)  # pi_CC = 1, pi_nozzle = 1
        th1 = _thrust(self._pi_cc * pt1_Pa)  # pi_CC only
        th2 = _thrust(self._pi_nozzle * self._pi_cc * pt1_Pa)  # both losses

        brayton_t2_K = brayton_t2_estimate_K(
            tt1_K, f_fuel_air, self._eta_b, self._h_PR, self._cp_cold
        )

        return {
            "mach0": mach0,
            "altitude_m": altitude_m,
            "eta_inlet": eta_inlet,
            "eta_inlet_source": eta_inlet_source,
            "p0_Pa": p0_Pa,
            "u0_m_s": u0_m_s,
            "tt1_K": tt1_K,
            "pt1_Pa": pt1_Pa,
            "tt2_K": self._tt2_K,
            "pt2_real_Pa": pt2_real_Pa,
            "f_fuel_air": f_fuel_air,
            "mdot_air_kg_s": mdot_air_kg_s,
            "mdot_fuel_kg_s": mdot_fuel_kg_s,
            "mdot_exit_kg_s": mdot_exit_kg_s,
            "throat": throat,
            "Thi": thi,
            "Th1": th1,
            "Th2": th2,
            "brayton_t2_K": brayton_t2_K,
        }

    def execute(self) -> AnalysisResults:
        """Run the design-point cycle and return results.

        Returns:
            AnalysisResults with the three thrust models, dynamic choked
            throat, exit states, the Brayton T2 / Teltik V3 / nozzle
            area-ratio cross-checks and the full station table.

        Raises:
            RuntimeError: If called before :meth:`setup`, or if the
                results fail :meth:`validate_results`.
        """
        if not self._is_setup:
            raise RuntimeError(
                "GrzywkaCombustorNozzleAnalysis.execute() called before setup()"
            )

        cycle = self._run_condition(self._mach0, self._altitude_m)

        thi_N = cycle["Thi"]["thrust_N"]
        th1_N = cycle["Th1"]["thrust_N"]
        th2_N = cycle["Th2"]["thrust_N"]

        # Isp from the REAL (Th2) thrust and the fuel flow.
        isp_real_s = th2_N / (cycle["mdot_fuel_kg_s"] * G0)

        # Brayton T2 cross-check (independent code path).
        brayton_t2_K = cycle["brayton_t2_K"]
        brayton_delta_frac = (brayton_t2_K - cycle["tt2_K"]) / cycle["tt2_K"]
        brayton_flag = abs(brayton_delta_frac) > 0.05

        # V3 (real, Th2) vs Teltik 2024 CFD at ITS reference condition
        # (Mach 2.5 / 6000 m), not the design point.
        teltik_cycle = self._run_condition(TELTIK_MACH, TELTIK_ALTITUDE_M)
        v3_teltik_model_m_s = teltik_cycle["Th2"]["V3_m_s"]
        v3_teltik_delta_frac = (v3_teltik_model_m_s - TELTIK_V3_M_S) / TELTIK_V3_M_S

        # Implied nozzle area ratio A3(real)/A21 at the design point.
        area_ratio_model = cycle["Th2"]["A3_m2"] / cycle["throat"]["A21_m2"]

        station_table = [
            {
                "station": "1_combustor_inlet",
                "total_temperature_K": cycle["tt1_K"],
                "total_pressure_Pa": cycle["pt1_Pa"],
            },
            {
                "station": "2_combustor_exit",
                "total_temperature_K": cycle["tt2_K"],
                "total_pressure_Pa": cycle["pt2_real_Pa"],
            },
            {
                "station": "21_nozzle_throat_choked",
                "mach": cycle["throat"]["Ma21"],
                "static_temperature_K": cycle["throat"]["T21_K"],
                "static_pressure_Pa": cycle["throat"]["p21_Pa"],
                "velocity_m_s": cycle["throat"]["u21_m_s"],
                "area_m2": cycle["throat"]["A21_m2"],
                "diameter_m": cycle["throat"]["D21_m"],
            },
            {
                "station": "3_nozzle_exit_real_Th2",
                "mach": cycle["Th2"]["Ma3"],
                "static_temperature_K": cycle["Th2"]["T3_K"],
                "static_pressure_Pa": cycle["Th2"]["p3_Pa"],
                "velocity_m_s": cycle["Th2"]["V3_m_s"],
                "area_m2": cycle["Th2"]["A3_m2"],
            },
        ]

        data: dict[str, Any] = {
            "Thi_N": thi_N,
            "Th1_N": th1_N,
            "Th2_N": th2_N,
            "thrust_nominal_N": th2_N,
            "V3i_m_s": cycle["Thi"]["V3_m_s"],
            "V3_1_m_s": cycle["Th1"]["V3_m_s"],
            "V3_2_m_s": cycle["Th2"]["V3_m_s"],
            "V3_m_s": cycle["Th2"]["V3_m_s"],
            "A21_throat_m2": cycle["throat"]["A21_m2"],
            "D21_throat_m": cycle["throat"]["D21_m"],
            "A3_exit_m2": cycle["Th2"]["A3_m2"],
            "Ma21": cycle["throat"]["Ma21"],
            "Ma3": cycle["Th2"]["Ma3"],
            "f_fuel_air": cycle["f_fuel_air"],
            "isp_s": isp_real_s,
            "mdot_air_kg_s": cycle["mdot_air_kg_s"],
            "mdot_fuel_kg_s": cycle["mdot_fuel_kg_s"],
            "mdot_exit_kg_s": cycle["mdot_exit_kg_s"],
            "tt1_K": cycle["tt1_K"],
            "tt2_K": cycle["tt2_K"],
            "pt1_Pa": cycle["pt1_Pa"],
            "pt2_Pa": cycle["pt2_real_Pa"],
            "eta_inlet": cycle["eta_inlet"],
            "pi_cc": self._pi_cc,
            "pi_nozzle": self._pi_nozzle,
            "eta_b": self._eta_b,
            "mach0": self._mach0,
            "altitude_m": self._altitude_m,
            "nozzle_area_ratio_model": area_ratio_model,
            "nozzle_area_ratio_design_yaml": NOZZLE_AREA_RATIO_DESIGN,
            "nozzle_area_ratio_cad_cylindrical": NOZZLE_AREA_RATIO_CYLINDRICAL,
        }

        metadata: dict[str, Any] = {
            "eta_inlet_source": cycle["eta_inlet_source"],
            "station_table": station_table,
            "thrust_model_hierarchy": {
                "Thi_N": thi_N,
                "Th1_N": th1_N,
                "Th2_N": th2_N,
                "note": (
                    "Grzywka Sec. 6.2.2 three-thrust decomposition. "
                    "Thi: ideal, no losses (pi_CC=pi_nozzle=1), fully "
                    "expanded. Th1: combustor loss pi_CC only. Th2: real, "
                    "both pi_CC and pi_nozzle (nominal for downstream "
                    "cruise wiring). Hierarchy Thi>=Th1>=Th2 holds by "
                    "construction (same mdot/Tt1/Tt2/f; only the delivered "
                    "nozzle total pressure differs)."
                ),
            },
            "brayton_t2_cross_check": {
                "station_model_tt2_K": cycle["tt2_K"],
                "brayton_estimate_tt2_K": brayton_t2_K,
                "delta_frac": brayton_delta_frac,
                "exceeds_5pct": brayton_flag,
                "note": (
                    "Independently-coded single-gas (cold-cp) Brayton "
                    "heat-addition estimate of Tt2 vs the station model's "
                    "Tt2. Delta driven mainly by cold-cp vs hot-cp choice. "
                    "Logged as an OPEN ITEM if >5%; NOT a validation "
                    "failure (repo method-discrepancy convention)."
                ),
            },
            "teltik_v3_cross_check": {
                "model_v3_m_s": v3_teltik_model_m_s,
                "teltik_cfd_v3_m_s": TELTIK_V3_M_S,
                "condition": f"Mach {TELTIK_MACH} / {TELTIK_ALTITUDE_M:.0f} m",
                "delta_frac": v3_teltik_delta_frac,
                "note": (
                    "Model V3 is the fully-expanded 1-D isentropic exit "
                    "velocity (Th2, real losses); Teltik 2024 CFD "
                    "~1047 m/s (assumptions A15) reflects the actual "
                    "(near-cylindrical, expansion_ratio 1.0) geometry, so "
                    "the 1-D fully-expanded value is expected to be higher. "
                    "Delta quantified, agreement NOT forced (cf. "
                    "assumptions A3: CFD vs MATLAB 20-30% open discrepancy)."
                ),
            },
            "nozzle_area_ratio_note": (
                "Model implies A3/A21 ~ "
                f"{area_ratio_model:.2f} (fully-expanded real Th2 exit over "
                "the dynamic choked throat). vehicle_config.yaml "
                "nozzle_area_ratio=4.0 is the DESIGN INTENT; the Fusion v6 "
                "CAD nozzle is a cylindrical exit stub (expansion_ratio "
                "1.0, 'full ramjet engine NOT modeled'). All three are "
                "logged so the CAD-vs-design gap is quantified, not "
                "silently resolved (assumptions A10)."
            ),
            "combustor_risk_baseline": (
                "Tt2=2000 K is a PLACEHOLDER chosen BELOW the ~2400 K "
                "flame-holder cavity risk figure (assumptions A4); "
                "combustor design is BLOCKED pending flame-holder "
                "relocation / injector atomization redesign. Fusion v6 "
                "lists the flame_holder material as STEEL, contradicting "
                "the 'aluminium' risk note -- flagged for human review, "
                "NOT resolved here."
            ),
            "reference_model_disclosure": (
                "Grzywka 2022 station model (1-2-21-3, pi_CC=0.8924, "
                "pi_nozzle=0.97). Complementary to the Mattingly-style "
                "ramjet_cycle (0-2-4-9) model; single-method L2 result "
                "pending CFD/MATLAB dual-check (assumptions A3)."
            ),
            "assumptions": [
                f"Grzywka loss coefficients pi_CC={self._pi_cc}, "
                f"pi_nozzle={self._pi_nozzle} (assumptions A13).",
                f"Combustion efficiency eta_b={self._eta_b} is a "
                "placeholder shared with ramjet_cycle.",
                "Nozzle throat (station 21) choked (Ma=1) at all "
                "conditions; A21 solved dynamically from continuity, "
                "never hard-coded.",
                "All three thrust models fully expand to ambient p0 "
                "(p3=p0); loss level enters only via the delivered nozzle "
                "total pressure.",
                "Full mass-flow capture at the design Mach "
                "(mdot_air=rho0*u0*A_capture), consistent with "
                "inlet_performance / ramjet_cycle.",
                "Two-gas calorically-perfect model (cold/hot cp,gamma); "
                "no dissociation or variable-cp beyond the two fixed sets.",
            ],
        }

        results = AnalysisResults(
            name=self.name, fidelity=self.fidelity, data=data, metadata=metadata
        )
        if not self.validate_results(results):
            raise RuntimeError(
                f"Grzywka combustor/nozzle results failed physical validation: "
                f"{results.data}"
            )
        return results

    def validate_results(self, results: AnalysisResults) -> bool:
        """Sanity-check the Grzywka cycle results.

        Checks: the three thrust models are all positive and obey the
        physical hierarchy ``Thi >= Th1 >= Th2``; the choked throat area
        and exit area are positive; ``Ma21 == 1``; the fuel-air ratio is
        in a physically sensible kerosene-air range (0, 0.15); Isp in the
        broad hydrocarbon band per project rules; and the combustor exit
        temperature stays below the material sanity ceiling.

        Args:
            results: Results to validate.

        Returns:
            True if all physical sanity checks pass.
        """
        required = {
            "Thi_N",
            "Th1_N",
            "Th2_N",
            "A21_throat_m2",
            "A3_exit_m2",
            "Ma21",
            "f_fuel_air",
            "isp_s",
            "tt2_K",
        }
        if not required.issubset(results.data):
            return False
        thi, th1, th2 = results["Thi_N"], results["Th1_N"], results["Th2_N"]
        if not (thi > 0.0 and th1 > 0.0 and th2 > 0.0):
            return False
        # Core physical hierarchy (1e-6 N slack for float noise).
        if not (thi >= th1 - 1e-6 and th1 >= th2 - 1e-6):
            return False
        if not (results["A21_throat_m2"] > 0.0 and results["A3_exit_m2"] > 0.0):
            return False
        if abs(results["Ma21"] - 1.0) > 1e-9:
            return False
        if not (0.0 < results["f_fuel_air"] < 0.15):
            return False
        if not (400.0 < results["isp_s"] < 3000.0):
            return False
        if not (0.0 < results["tt2_K"] < COMBUSTOR_TEMP_CEILING_K):
            return False
        return True


def _build_output_dict(results: AnalysisResults) -> dict[str, Any]:
    """Flatten an AnalysisResults into a JSON-serializable output dict."""
    out: dict[str, Any] = dict(results.data)
    out["eta_inlet_source"] = results.metadata["eta_inlet_source"]
    out["station_table"] = results.metadata["station_table"]
    out["thrust_model_hierarchy"] = results.metadata["thrust_model_hierarchy"]
    out["brayton_t2_cross_check"] = results.metadata["brayton_t2_cross_check"]
    out["teltik_v3_cross_check"] = results.metadata["teltik_v3_cross_check"]
    out["nozzle_area_ratio_note"] = results.metadata["nozzle_area_ratio_note"]
    out["reference_model_disclosure"] = results.metadata["reference_model_disclosure"]
    out["assumptions"] = results.metadata["assumptions"]
    out["fidelity"] = results.fidelity.name
    return out


def main() -> None:
    """Run the design-point Grzywka cycle, save JSON and print a summary."""
    analysis = GrzywkaCombustorNozzleAnalysis()
    analysis.setup(mach0=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M)
    results = analysis.execute()
    output = _build_output_dict(results)

    module_dir = Path(__file__).resolve().parent
    json_path = module_dir / "combustor_nozzle_cycle_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("=== Grzywka combustor+nozzle cycle (stations 1-2-21-3) ===")
    print(f"Design Mach: {MACH_DESIGN}, altitude: {DESIGN_ALTITUDE_M} m ISA")
    print(f"eta_inlet: {output['eta_inlet']:.4f} (source: {output['eta_inlet_source'] if 'eta_inlet_source' in output else 'n/a'})")
    print(f"pi_CC: {output['pi_cc']}, pi_nozzle: {output['pi_nozzle']}")
    print(f"Tt1: {output['tt1_K']:.2f} K, Tt2: {output['tt2_K']:.2f} K, f: {output['f_fuel_air']:.4f}")
    print(f"Thi (ideal):           {output['Thi_N']:.1f} N")
    print(f"Th1 (pi_CC):           {output['Th1_N']:.1f} N")
    print(f"Th2 (pi_CC+pi_nozzle): {output['Th2_N']:.1f} N  <- nominal")
    print(f"Dynamic throat A21: {output['A21_throat_m2']:.5f} m^2 (D21 {output['D21_throat_m']:.4f} m, Ma21 {output['Ma21']:.1f})")
    print(f"Exit A3: {output['A3_exit_m2']:.5f} m^2, V3(real): {output['V3_m_s']:.1f} m/s, Isp: {output['isp_s']:.1f} s")
    b = output["brayton_t2_cross_check"]
    print(f"Brayton T2 cross-check: {b['brayton_estimate_tt2_K']:.1f} K vs {b['station_model_tt2_K']:.1f} K (delta {b['delta_frac']*100:+.1f}%, >5%={b['exceeds_5pct']})")
    t = output["teltik_v3_cross_check"]
    print(f"V3 vs Teltik CFD ({t['condition']}): {t['model_v3_m_s']:.1f} vs {t['teltik_cfd_v3_m_s']:.1f} m/s (delta {t['delta_frac']*100:+.1f}%)")
    print(f"Nozzle area ratio A3/A21 model: {output['nozzle_area_ratio_model']:.2f} | YAML design {output['nozzle_area_ratio_design_yaml']:.3f} | CAD cylindrical {output['nozzle_area_ratio_cad_cylindrical']:.2f}")
    print(f"\nJSON written to: {json_path}")


if __name__ == "__main__":
    main()
