# MELprop-IADE | analyses.propulsion.cycle_v2.hp_stream_thrust_cycle | v0.1.0
"""Heiser & Pratt stream-thrust ramjet cycle with station-wise gamma.

Rebuild of the RamP ramjet thermodynamic cycle motivated by the
2026-07-11 research finding (``docs/references/ramp_analysis_plan_2026-07-11.md``,
Section 2): the legacy Grzywka MATLAB model's **constant gamma = 1.4** is
the primary suspect for the +40.8 % V3 gap (1474 m/s model vs 1047 m/s
Teltik CFD), alongside the nozzle geometry (now corrected to the real
drawing value ``nozzle_area_ratio = 1.317``, throat 0.210 m / exit 0.241 m).

This module keeps the two legacy cycle modules untouched and adds an
independent station model that

  * carries a **cold** ratio of specific heats through the inlet/diffuser
    (air, ~1.40) and a **hot** ratio through combustor + nozzle
    (kerosene-air products, ~1.25-1.30, CEA-class), and
  * expands the nozzle through the **real, finite** area ratio A_exit/A_throat
    = 1.317 rather than assuming full expansion to ambient. Because 1.317
    is a modest supersonic area ratio, the exit is **under-expanded**
    (p_exit > p0), so a pressure-thrust term ``(p_exit - p0) * A_exit`` is
    retained explicitly in the thrust bookkeeping (it was implicitly zero
    in the legacy fully-expanded model).

Station numbering (Heiser & Pratt style, mapped to the RamP stations):

    0  -> freestream (flight condition, cold gamma).
    2  -> diffuser exit / combustor inlet. Adiabatic: ``Tt2 = Tt0``;
          total-pressure recovery ``pt2 = eta_inlet * pt0``. Cold gamma.
    4  -> combustor exit. Heat addition to ``Tt4`` with combustor
          total-pressure ratio ``pi_CC``: ``pt4 = pi_CC * pt2``. Gamma
          switches to the HOT (products) value here.
    e  -> nozzle exit. The throat (station t) is choked (``Ma_t = 1``); the
          exit Mach follows from the area ratio ``A_e/A_t = 1.317`` on the
          supersonic branch. Nozzle total-pressure loss ``pi_nozzle`` is
          applied to the expansion total pressure. Hot gamma.

Three thrust models mirror the Grzywka / classical ideal-loss hierarchy so
the new model stays comparable to the legacy one (all three ALWAYS
reported, never collapsed):

    Thi -- ideal: pi_CC = pi_nozzle = 1.
    Th1 -- combustor loss pi_CC only (pi_nozzle = 1).
    Th2 -- real: both pi_CC and pi_nozzle. Nominal for downstream use.

Fidelity: 1-D calorically-perfect two-gas station cycle
(``FidelityLevel.LEVEL_2``) -- same rung as the legacy models; the value
added is the corrected geometry + station gamma, not a higher method class.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scipy.optimize import brentq  # noqa: E402

# --------------------------------------------------------------------------
# Physical constants and PROVISIONAL cycle inputs.
# --------------------------------------------------------------------------

#: Specific gas constant of air [J/(kg*K)].
R_AIR: float = 287.05

#: Specific gas constant of the kerosene-air combustion products
#: [J/(kg*K)]. Near stoichiometric the mean molar mass is close to air's,
#: so R changes by < 1 %; kept equal to air here as a documented
#: simplification (the dominant lever this session is gamma, not R).
R_PRODUCTS: float = 287.05

#: Cold (inlet-air) ratio of specific heats [-]. Air below ~600 K.
GAMMA_COLD: float = 1.40

#: PROVISIONAL default hot (post-combustion) ratio of specific heats [-].
#: source: CEA-class kerosene-air equilibrium products at ~2000-2400 K
#: (assumptions.md A19); replace with a real NASA-CEA run once the team
#: confirms fuel and equivalence ratio.
GAMMA_HOT_DEFAULT: float = 1.28

#: Kerosene lower heating value [J/kg].
#: PROVISIONAL default: 43.0e6 J/kg, source: standard Jet-A/kerosene LHV
#: (43.0-43.2 MJ/kg); replace when the team confirms the actual fuel.
FUEL_LHV_J_KG: float = 43.0e6

#: Sea-level ISA reference values for the standard-troposphere model.
_ISA_T0_K: float = 288.15
_ISA_P0_PA: float = 101325.0
_ISA_LAPSE_K_M: float = 0.0065

#: Gamma sweep requested by the 2026-07-11 research finding (Section 2).
GAMMA_SWEEP: tuple[float, ...] = (1.20, 1.25, 1.30, 1.35, 1.40)

#: Legacy / reference V3 values for delta reporting [m/s].
V3_LEGACY_MATLAB_M_S: float = 1474.0  # old constant-gamma / implied AR~2.44
V3_TELTIK_CFD_M_S: float = 1047.0     # deprioritized CFD reference (A15)


def isa_atmosphere(altitude_m: float) -> tuple[float, float, float]:
    """Standard-troposphere temperature, pressure and density.

    Valid to 11 000 m (assumptions.md A20). No wind/turbulence.

    Args:
        altitude_m: Geometric altitude [m].

    Returns:
        Tuple ``(T [K], p [Pa], rho [kg/m^3])``.
    """
    t = _ISA_T0_K - _ISA_LAPSE_K_M * altitude_m
    p = _ISA_P0_PA * (t / _ISA_T0_K) ** (9.80665 / (_ISA_LAPSE_K_M * R_AIR))
    rho = p / (R_AIR * t)
    return t, p, rho


def area_ratio_from_mach(mach: float, gamma: float) -> float:
    """Isentropic area ratio ``A/A*`` for a given Mach and gamma.

    Args:
        mach: Local Mach number (> 0).
        gamma: Ratio of specific heats.

    Returns:
        ``A/A*`` [-].
    """
    g = gamma
    return (1.0 / mach) * (
        (2.0 / (g + 1.0)) * (1.0 + 0.5 * (g - 1.0) * mach * mach)
    ) ** ((g + 1.0) / (2.0 * (g - 1.0)))


def supersonic_mach_from_area_ratio(area_ratio: float, gamma: float) -> float:
    """Supersonic Mach number for a given isentropic area ratio ``A/A*``.

    Solves the area-Mach relation on the supersonic branch (M > 1).

    Args:
        area_ratio: ``A/A*`` (>= 1).
        gamma: Ratio of specific heats.

    Returns:
        Supersonic Mach number [-].

    Raises:
        ValueError: If ``area_ratio < 1`` (no supersonic solution).
    """
    if area_ratio < 1.0:
        raise ValueError(f"area_ratio {area_ratio} < 1: no supersonic solution")
    if math.isclose(area_ratio, 1.0, rel_tol=1e-9):
        return 1.0
    return brentq(
        lambda m: area_ratio_from_mach(m, gamma) - area_ratio,
        1.0 + 1e-9,
        50.0,
        xtol=1e-10,
    )


@dataclass
class CycleInputs:
    """Inputs to the Heiser & Pratt stream-thrust ramjet cycle.

    Attributes:
        mach0: Flight Mach number [-].
        altitude_m: Flight altitude [m] (ISA).
        eta_inlet: Inlet total-pressure recovery pt2/pt0 [-]. Upstream
            result from the 4-cone inlet chain (analyses.propulsion).
        tt4_K: Combustor-exit total temperature [K].
        pi_cc: Combustor total-pressure ratio pt4/pt2 [-].
        pi_nozzle: Nozzle total-pressure ratio [-].
        eta_b: Combustion efficiency [-].
        nozzle_area_ratio: A_exit / A_throat [-] (real drawing value 1.317).
        mdot_air_kg_s: Captured air mass flow [kg/s].
        gamma_hot: Post-combustion ratio of specific heats [-].
        gamma_cold: Inlet-air ratio of specific heats [-].
        fuel_lhv_J_kg: Fuel lower heating value [J/kg].
    """

    mach0: float = 2.5
    altitude_m: float = 10000.0
    eta_inlet: float = 0.8740657315001767  # 4-cone chain (A9); PROVISIONAL upstream
    tt4_K: float = 2000.0                    # combustor_temp_K (config); PROVISIONAL
    pi_cc: float = 0.8924                    # Grzywka A13
    pi_nozzle: float = 0.97                  # Grzywka A13
    eta_b: float = 0.95                      # placeholder, shared with legacy
    nozzle_area_ratio: float = 1.317         # drawing (241/210)^2; CONFIRMED geometry
    mdot_air_kg_s: float = 15.167490506864516
    gamma_hot: float = GAMMA_HOT_DEFAULT
    gamma_cold: float = GAMMA_COLD
    fuel_lhv_J_kg: float = FUEL_LHV_J_KG


@dataclass
class CycleResult:
    """Result of one stream-thrust cycle evaluation.

    Velocities/temperatures/pressures are static unless the name says total
    (``tt``/``pt``). Thrusts in newtons.
    """

    inputs: CycleInputs
    t0_K: float
    p0_Pa: float
    v0_m_s: float
    tt0_K: float
    pt0_Pa: float
    pt2_Pa: float
    pt4_Pa: float
    f_fuel_air: float
    mach_exit: float
    t_exit_K: float
    p_exit_Pa: float
    v_exit_m_s: float
    a_throat_m2: float
    a_exit_m2: float
    thrust_ideal_N: float
    thrust_cc_loss_N: float
    thrust_real_N: float
    momentum_thrust_N: float
    pressure_thrust_N: float
    extras: dict[str, Any] = field(default_factory=dict)


def _choked_throat_area(
    mdot_kg_s: float, pt_Pa: float, tt_K: float, gamma: float, r_gas: float
) -> float:
    """Throat area for choked (Ma=1) flow from continuity.

    Args:
        mdot_kg_s: Mass flow through the throat [kg/s].
        pt_Pa: Total pressure at the throat [Pa].
        tt_K: Total temperature at the throat [K].
        gamma: Ratio of specific heats.
        r_gas: Specific gas constant [J/(kg*K)].

    Returns:
        Throat cross-sectional area [m^2].
    """
    g = gamma
    mdot_flux = (
        pt_Pa
        * math.sqrt(g / (r_gas * tt_K))
        * (2.0 / (g + 1.0)) ** ((g + 1.0) / (2.0 * (g - 1.0)))
    )
    return mdot_kg_s / mdot_flux


def evaluate_cycle(inputs: CycleInputs) -> CycleResult:
    """Evaluate the Heiser & Pratt stream-thrust ramjet cycle.

    Args:
        inputs: Cycle inputs (flight condition, losses, geometry, gammas).

    Returns:
        A :class:`CycleResult` with exit state and the three thrust models.
    """
    gc = inputs.gamma_cold
    gh = inputs.gamma_hot
    rc = R_AIR
    rh = R_PRODUCTS

    # --- Station 0: freestream -------------------------------------------
    t0, p0, _rho0 = isa_atmosphere(inputs.altitude_m)
    a0 = math.sqrt(gc * rc * t0)
    v0 = inputs.mach0 * a0
    tt0 = t0 * (1.0 + 0.5 * (gc - 1.0) * inputs.mach0 ** 2)
    pt0 = p0 * (1.0 + 0.5 * (gc - 1.0) * inputs.mach0 ** 2) ** (gc / (gc - 1.0))

    # --- Station 2: diffuser exit (adiabatic, recovery) ------------------
    tt2 = tt0
    pt2 = inputs.eta_inlet * pt0

    # --- Station 4: combustor exit ---------------------------------------
    tt4 = inputs.tt4_K
    pt4 = inputs.pi_cc * pt2
    cp_cold = gc * rc / (gc - 1.0)
    cp_hot = gh * rh / (gh - 1.0)
    # Fuel-air ratio from the burner energy balance.
    denom = inputs.eta_b * inputs.fuel_lhv_J_kg - cp_hot * tt4
    f = (cp_hot * tt4 - cp_cold * tt2) / denom
    mdot_air = inputs.mdot_air_kg_s
    mdot_exit = mdot_air * (1.0 + f)

    def _thrust_for_nozzle_pt(pt_throat: float, pt_exit_total: float) -> dict[str, float]:
        """Thrust bookkeeping for a given throat/exit total pressure."""
        a_throat = _choked_throat_area(mdot_exit, pt_throat, tt4, gh, rh)
        a_exit = inputs.nozzle_area_ratio * a_throat
        mach_e = supersonic_mach_from_area_ratio(inputs.nozzle_area_ratio, gh)
        t_e = tt4 / (1.0 + 0.5 * (gh - 1.0) * mach_e ** 2)
        p_e = pt_exit_total / (1.0 + 0.5 * (gh - 1.0) * mach_e ** 2) ** (gh / (gh - 1.0))
        a_e = math.sqrt(gh * rh * t_e)
        v_e = mach_e * a_e
        momentum = mdot_exit * v_e - mdot_air * v0
        pressure = (p_e - p0) * a_exit
        return {
            "a_throat": a_throat,
            "a_exit": a_exit,
            "mach_e": mach_e,
            "t_e": t_e,
            "p_e": p_e,
            "v_e": v_e,
            "momentum": momentum,
            "pressure": pressure,
            "thrust": momentum + pressure,
        }

    # Th2 (real): both losses. pt at throat = pt4; expansion total pressure
    # carries the nozzle loss pi_nozzle.
    real = _thrust_for_nozzle_pt(pt4, inputs.pi_nozzle * pt4)
    # Th1: combustor loss only, ideal nozzle (pi_nozzle = 1).
    cc_only = _thrust_for_nozzle_pt(pt4, pt4)
    # Thi (ideal): no combustor loss either -> pt4_ideal = pt2.
    pt4_ideal = pt2
    ideal = _thrust_for_nozzle_pt(pt4_ideal, pt4_ideal)

    return CycleResult(
        inputs=inputs,
        t0_K=t0,
        p0_Pa=p0,
        v0_m_s=v0,
        tt0_K=tt0,
        pt0_Pa=pt0,
        pt2_Pa=pt2,
        pt4_Pa=pt4,
        f_fuel_air=f,
        mach_exit=real["mach_e"],
        t_exit_K=real["t_e"],
        p_exit_Pa=real["p_e"],
        v_exit_m_s=real["v_e"],
        a_throat_m2=real["a_throat"],
        a_exit_m2=real["a_exit"],
        thrust_ideal_N=ideal["thrust"],
        thrust_cc_loss_N=cc_only["thrust"],
        thrust_real_N=real["thrust"],
        momentum_thrust_N=real["momentum"],
        pressure_thrust_N=real["pressure"],
        extras={
            "tt2_K": tt2,
            "tt4_K": tt4,
            "cp_cold": cp_cold,
            "cp_hot": cp_hot,
            "mdot_exit_kg_s": mdot_exit,
            "underexpanded": real["p_e"] > p0,
            "p_exit_over_p0": real["p_e"] / p0,
            "v3_delta_vs_matlab": (real["v_e"] - V3_LEGACY_MATLAB_M_S) / V3_LEGACY_MATLAB_M_S,
            "v3_delta_vs_teltik": (real["v_e"] - V3_TELTIK_CFD_M_S) / V3_TELTIK_CFD_M_S,
        },
    )


if __name__ == "__main__":
    res = evaluate_cycle(CycleInputs())
    print(f"gamma_hot           = {res.inputs.gamma_hot}")
    print(f"V3 (exit velocity)  = {res.v_exit_m_s:8.2f} m/s")
    print(f"  vs MATLAB 1474    = {res.extras['v3_delta_vs_matlab']*100:+6.1f} %")
    print(f"  vs Teltik 1047    = {res.extras['v3_delta_vs_teltik']*100:+6.1f} %")
    print(f"Mach_exit           = {res.mach_exit:8.3f}")
    print(f"p_exit/p0           = {res.extras['p_exit_over_p0']:8.3f} "
          f"({'under' if res.extras['underexpanded'] else 'over'}-expanded)")
    print(f"Thi/Th1/Th2 [N]     = {res.thrust_ideal_N:8.1f} / "
          f"{res.thrust_cc_loss_N:8.1f} / {res.thrust_real_N:8.1f}")
    print(f"  momentum / pressure thrust [N] = "
          f"{res.momentum_thrust_N:8.1f} / {res.pressure_thrust_N:8.1f}")
    print(f"f_fuel_air          = {res.f_fuel_air:8.5f}")
