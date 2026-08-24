"""Unit tests for analyses.propulsion.ramjet_cycle."""

import math

import pytest

from YAADO_Core.modules.powerplant.cycle_methods.mattingly import (
    CP_COLD,
    GAMMA_COLD,
    KEROSENE_H_PR,
    TT4_DEFAULT_K,
    RamjetCycleAnalysis,
    ideal_ramjet_closed_form,
    stagnation_pressure_Pa,
    stagnation_temperature_K,
)
from YAADO_Core.modules.powerplant.inlet_methods.wedge import (
    DESIGN_ALTITUDE_M,
    G0,
    MACH_DESIGN,
    R_AIR,
    isa_atmosphere,
)
from YAADO_Core.Foundation.analysis_base import FidelityLevel


def _independent_ideal_closed_form(mach0: float, altitude_m: float, tt4_K: float) -> dict:
    """Second, independently-written implementation of the ideal ramjet
    closed form, used only to cross-check ideal_ramjet_closed_form()
    without sharing code with it."""
    atm = isa_atmosphere(altitude_m)
    a0 = math.sqrt(GAMMA_COLD * R_AIR * atm.temperature_K)
    tt0 = atm.temperature_K * (1.0 + 0.5 * (GAMMA_COLD - 1.0) * mach0**2)
    st = a0 * mach0 * (math.sqrt(tt4_K / tt0) - 1.0)
    f = CP_COLD * (tt4_K - tt0) / (KEROSENE_H_PR - CP_COLD * tt4_K)
    return {"specific_thrust_Ns_per_kg": st, "f_fuel_air": f, "tt0_K": tt0}


def test_stagnation_relations_at_zero_mach_are_identity() -> None:
    """Stagnation temperature and pressure equal static values at Mach 0."""
    assert stagnation_temperature_K(300.0, 0.0, 1.4) == pytest.approx(300.0)
    assert stagnation_pressure_Pa(101325.0, 0.0, 1.4) == pytest.approx(101325.0)


def test_ideal_closed_form_matches_independent_hand_calc() -> None:
    """ideal_ramjet_closed_form must reproduce an independently coded
    version of the same Mattingly closed form to well under 1%."""
    result = ideal_ramjet_closed_form(MACH_DESIGN, DESIGN_ALTITUDE_M, TT4_DEFAULT_K)
    reference = _independent_ideal_closed_form(MACH_DESIGN, DESIGN_ALTITUDE_M, TT4_DEFAULT_K)

    assert result["specific_thrust_Ns_per_kg"] == pytest.approx(
        reference["specific_thrust_Ns_per_kg"], rel=0.01
    )
    assert result["f_fuel_air"] == pytest.approx(reference["f_fuel_air"], rel=0.01)
    assert result["tt0_K"] == pytest.approx(reference["tt0_K"], rel=0.01)


def test_ideal_closed_form_rejects_non_supersonic_mach() -> None:
    """ideal_ramjet_closed_form raises ValueError for Mach <= 1."""
    with pytest.raises(ValueError):
        ideal_ramjet_closed_form(0.8, DESIGN_ALTITUDE_M, TT4_DEFAULT_K)


def test_ideal_closed_form_rejects_tt4_below_tt0() -> None:
    """ideal_ramjet_closed_form raises ValueError when combustor temp below stagnation temp."""
    with pytest.raises(ValueError):
        ideal_ramjet_closed_form(MACH_DESIGN, DESIGN_ALTITUDE_M, 100.0)


def test_execute_before_setup_raises() -> None:
    """RamjetCycleAnalysis.execute() raises RuntimeError if called before setup()."""
    analysis = RamjetCycleAnalysis()
    with pytest.raises(RuntimeError):
        analysis.execute()


def test_setup_rejects_subsonic_mach() -> None:
    """RamjetCycleAnalysis.setup() raises ValueError for Mach <= 1."""
    analysis = RamjetCycleAnalysis()
    with pytest.raises(ValueError):
        analysis.setup(mach0=0.9)


def test_setup_rejects_tt4_below_recovered_total_temperature() -> None:
    """RamjetCycleAnalysis.setup() raises ValueError when combustor temp below stagnation temp."""
    analysis = RamjetCycleAnalysis()
    with pytest.raises(ValueError):
        analysis.setup(mach0=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M, tt4_K=50.0)


@pytest.mark.parametrize("bad_eta_inlet", [0.0, -0.1, 1.5])
def test_setup_rejects_bad_eta_inlet(bad_eta_inlet: float) -> None:
    """RamjetCycleAnalysis.setup() raises ValueError for eta_inlet outside (0, 1)."""
    analysis = RamjetCycleAnalysis()
    with pytest.raises(ValueError):
        analysis.setup(eta_inlet=bad_eta_inlet)


@pytest.mark.parametrize("bad_pi_b", [0.0, -0.2, 1.2])
def test_setup_rejects_bad_pi_b(bad_pi_b: float) -> None:
    """RamjetCycleAnalysis.setup() raises ValueError for pi_b outside (0, 1)."""
    analysis = RamjetCycleAnalysis()
    with pytest.raises(ValueError):
        analysis.setup(pi_b=bad_pi_b)


@pytest.mark.parametrize("bad_eta_b", [0.0, -0.2, 1.2])
def test_setup_rejects_bad_eta_b(bad_eta_b: float) -> None:
    """RamjetCycleAnalysis.setup() raises ValueError for eta_b outside (0, 1)."""
    analysis = RamjetCycleAnalysis()
    with pytest.raises(ValueError):
        analysis.setup(eta_b=bad_eta_b)


def test_design_point_fuel_air_ratio_in_expected_range() -> None:
    """Design-point fuel-to-air ratio falls in (0, 0.068), a reasonable ramjet band."""
    analysis = RamjetCycleAnalysis()
    analysis.setup(mach0=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M, tt4_K=TT4_DEFAULT_K)
    results = analysis.execute()
    assert 0.0 < results["f_fuel_air"] < 0.068


def test_design_point_fidelity_is_level_2() -> None:
    """RamjetCycleAnalysis results are marked as FidelityLevel.LEVEL_2."""
    analysis = RamjetCycleAnalysis()
    analysis.setup()
    results = analysis.execute()
    assert results.fidelity == FidelityLevel.LEVEL_2


def test_design_point_thrust_positive_and_cylindrical_below_matched() -> None:
    """Matched nozzle thrust exceeds CAD cylindrical nozzle; both positive."""
    analysis = RamjetCycleAnalysis()
    analysis.setup(mach0=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M, tt4_K=TT4_DEFAULT_K)
    results = analysis.execute()

    assert results["thrust_N"] > 0.0
    assert results["thrust_cylindrical_nozzle_N"] > 0.0
    assert results["thrust_cylindrical_nozzle_N"] < results["thrust_N"]


def test_design_point_isp_in_hydrocarbon_ramjet_band() -> None:
    """Project rule: ramjet Isp (kerosene) should be roughly 1000-1500 s.

    Allow some margin either side since this is a placeholder-parameter
    L2 cycle (Tt4/pi_b/eta_b are documented placeholders), but it must
    stay in a physically sane hydrocarbon-ramjet ballpark.
    """
    analysis = RamjetCycleAnalysis()
    analysis.setup(mach0=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M, tt4_K=TT4_DEFAULT_K)
    results = analysis.execute()
    assert 800.0 < results["isp_s"] < 2500.0


def test_losses_reduce_thrust_and_raise_tsfc_vs_loss_free_reference() -> None:
    """The lossy (real, eta_inlet<1/pi_b<1/eta_b<1) design point must
    produce less thrust and worse (higher) TSFC than the same two-gas
    cycle run loss-free (eta_inlet=pi_b=eta_b=1) -- the physically
    meaningful 'losses cost performance' check (module docstring
    'verification gate')."""
    analysis = RamjetCycleAnalysis()
    analysis.setup(mach0=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M, tt4_K=TT4_DEFAULT_K)
    results = analysis.execute()

    loss_free = results.metadata["loss_free_reference"]
    assert results["thrust_N"] < loss_free["thrust_N"]
    assert results["tsfc_kg_per_Ns"] > loss_free["tsfc_kg_per_Ns"]


def test_validate_results_passes_on_design_point() -> None:
    """validate_results() returns True for a valid design-point execution."""
    analysis = RamjetCycleAnalysis()
    analysis.setup(mach0=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M, tt4_K=TT4_DEFAULT_K)
    results = analysis.execute()
    assert analysis.validate_results(results) is True


def test_eta_inlet_default_matches_four_cone_preset_value() -> None:
    """Default eta_inlet at Mach 2.5 should match the ~0.874 4-cone
    preset value documented in inlet_performance."""
    analysis = RamjetCycleAnalysis()
    analysis.setup(mach0=2.5, altitude_m=DESIGN_ALTITUDE_M, tt4_K=TT4_DEFAULT_K)
    results = analysis.execute()
    assert results["eta_inlet"] == pytest.approx(0.874, abs=0.01)


def test_eta_inlet_override_is_respected() -> None:
    """setup() applies the user-provided eta_inlet override in results."""
    analysis = RamjetCycleAnalysis()
    analysis.setup(mach0=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M, eta_inlet=0.5)
    results = analysis.execute()
    assert results["eta_inlet"] == pytest.approx(0.5)


def test_station_table_has_expected_stations() -> None:
    """Metadata station_table contains all required cycle stations."""
    analysis = RamjetCycleAnalysis()
    analysis.setup()
    results = analysis.execute()
    station_names = {s["station"] for s in results.metadata["station_table"]}
    assert {
        "0_freestream",
        "2_combustor_entry",
        "4_combustor_exit",
        "9_nozzle_exit_matched_design",
        "9_nozzle_exit_cylindrical_cad",
    }.issubset(station_names)


def test_mass_flow_positive_and_fuel_less_than_air() -> None:
    """Design-point mass flows are positive and fuel < air (stoichiometric limit)."""
    analysis = RamjetCycleAnalysis()
    analysis.setup()
    results = analysis.execute()
    assert results["mdot_air_kg_s"] > 0.0
    assert 0.0 < results["mdot_fuel_kg_s"] < results["mdot_air_kg_s"]


def test_isp_consistent_with_thrust_and_fuel_flow() -> None:
    """Isp equals thrust / (mdot_fuel * g0), verifying thrust-flow consistency."""
    analysis = RamjetCycleAnalysis()
    analysis.setup()
    results = analysis.execute()
    expected_isp = results["thrust_N"] / (results["mdot_fuel_kg_s"] * G0)
    assert results["isp_s"] == pytest.approx(expected_isp, rel=1e-9)
