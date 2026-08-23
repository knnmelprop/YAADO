"""Unit tests for analyses.propulsion.combustor_nozzle_cycle (Grzywka)."""

import math

import pytest

from IADE_Core.modules.powerplant.cycle_methods.grzywka import (
    COMBUSTOR_EXIT_TEMP_DEFAULT_K,
    PI_CC,
    PI_NOZZLE,
    TELTIK_ALTITUDE_M,
    TELTIK_MACH,
    TELTIK_V3_M_S,
    GrzywkaCombustorNozzleAnalysis,
    brayton_t2_estimate_K,
    choked_throat_area_m2,
    fully_expanded_exit,
)
from IADE_Core.modules.powerplant.inlet_methods.wedge import DESIGN_ALTITUDE_M, MACH_DESIGN
from IADE_Core.modules.powerplant.cycle_methods.mattingly import (
    CP_HOT,
    GAMMA_HOT,
    R_HOT,
    RamjetCycleAnalysis,
)
from IADE_Core.Foundation.component_base import AnalysisResults, FidelityLevel


# --------------------------------------------------------------------------
# Component-level function tests
# --------------------------------------------------------------------------


def test_grzywka_loss_coefficients_match_assumptions_a13() -> None:
    """pi_CC / pi_nozzle are the documented Grzywka 2022 values (A13)."""
    assert PI_CC == pytest.approx(0.8924)
    assert PI_NOZZLE == pytest.approx(0.97)


def test_choked_throat_is_sonic_and_dynamic() -> None:
    """Throat is choked (Ma=1) and its area scales with mass flow."""
    low = choked_throat_area_m2(10.0, 2000.0, 3.5e5, GAMMA_HOT, R_HOT)
    high = choked_throat_area_m2(20.0, 2000.0, 3.5e5, GAMMA_HOT, R_HOT)
    assert low["Ma21"] == pytest.approx(1.0)
    # Sonic throat: u21 must equal the local speed of sound.
    a21 = math.sqrt(GAMMA_HOT * R_HOT * low["T21_K"])
    assert low["u21_m_s"] == pytest.approx(a21, rel=1e-9)
    # Dynamic area: doubling mdot doubles the required throat area.
    assert high["A21_m2"] == pytest.approx(2.0 * low["A21_m2"], rel=1e-9)
    assert high["A21_m2"] > low["A21_m2"]


def test_choked_throat_area_from_continuity_hand_calc() -> None:
    """A21 = mdot / (rho21 * a21) reproduced independently."""
    mdot, tt2, pt2 = 15.85, 2000.0, 3.52e5
    res = choked_throat_area_m2(mdot, tt2, pt2, GAMMA_HOT, R_HOT)
    cr = 2.0 / (GAMMA_HOT + 1.0)
    t21 = tt2 * cr
    p21 = pt2 * cr ** (GAMMA_HOT / (GAMMA_HOT - 1.0))
    a21 = math.sqrt(GAMMA_HOT * R_HOT * t21)
    rho21 = p21 / (R_HOT * t21)
    assert res["A21_m2"] == pytest.approx(mdot / (rho21 * a21), rel=1e-9)


def test_lower_nozzle_total_pressure_gives_lower_exit_velocity() -> None:
    """A larger total-pressure loss must reduce the fully-expanded V3."""
    ideal = fully_expanded_exit(2000.0, 4.0e5, 2.6e4, 15.85, GAMMA_HOT, CP_HOT, R_HOT)
    lossy = fully_expanded_exit(2000.0, 3.0e5, 2.6e4, 15.85, GAMMA_HOT, CP_HOT, R_HOT)
    assert lossy["V3_m_s"] < ideal["V3_m_s"]
    assert ideal["p3_Pa"] == pytest.approx(2.6e4)  # fully expanded to p0


def test_brayton_estimate_increases_with_fuel_air_ratio() -> None:
    """More fuel -> higher Brayton combustor-exit temperature."""
    low = brayton_t2_estimate_K(500.0, 0.03, 0.95, 43.1e6, 1004.5)
    high = brayton_t2_estimate_K(500.0, 0.05, 0.95, 43.1e6, 1004.5)
    assert high > low > 500.0


# --------------------------------------------------------------------------
# Analysis-level tests
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def design_results() -> AnalysisResults:
    """Design-point (Mach 2.5 / 10 km) Grzywka cycle results."""
    analysis = GrzywkaCombustorNozzleAnalysis()
    analysis.setup(mach0=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M)
    return analysis.execute()


def test_fidelity_is_level_2(design_results: AnalysisResults) -> None:
    assert design_results.fidelity is FidelityLevel.LEVEL_2


def test_three_thrust_models_all_reported(design_results: AnalysisResults) -> None:
    """All three thrust models are present and positive."""
    for key in ("Thi_N", "Th1_N", "Th2_N"):
        assert key in design_results
        assert design_results[key] > 0.0


def test_thrust_hierarchy_thi_ge_th1_ge_th2(design_results: AnalysisResults) -> None:
    """MANDATORY physical hierarchy: Thi >= Th1 >= Th2."""
    thi = design_results["Thi_N"]
    th1 = design_results["Th1_N"]
    th2 = design_results["Th2_N"]
    assert thi >= th1 >= th2
    # Losses must actually cost thrust (strict, not merely equal).
    assert thi > th1 > th2


def test_th2_is_the_nominal_thrust(design_results: AnalysisResults) -> None:
    """The exposed nominal thrust must be the conservative Th2."""
    assert design_results["thrust_nominal_N"] == pytest.approx(
        design_results["Th2_N"]
    )


def test_throat_is_choked_and_dynamic(design_results: AnalysisResults) -> None:
    """Station 21 is sonic and its area is a positive solved quantity."""
    assert design_results["Ma21"] == pytest.approx(1.0)
    assert design_results["A21_throat_m2"] > 0.0
    assert design_results["D21_throat_m"] > 0.0


def test_throat_area_tracks_flight_condition() -> None:
    """Dynamic throat: a different (V, H) yields a different A21."""
    design = GrzywkaCombustorNozzleAnalysis()
    design.setup(mach0=2.5, altitude_m=10_000.0)
    a_design = design.execute()["A21_throat_m2"]

    other = GrzywkaCombustorNozzleAnalysis()
    other.setup(mach0=2.5, altitude_m=6_000.0)
    a_other = other.execute()["A21_throat_m2"]

    # The throat is solved from continuity at each (V, H): a different
    # altitude must change A21 (it is NOT a hard-coded constant). Both
    # mdot and the sonic throat density scale with the flight condition,
    # so only the fact that A21 moves is asserted, not its direction.
    assert a_other != pytest.approx(a_design, rel=1e-3)
    assert a_design > 0.0 and a_other > 0.0


def test_thi_within_15pct_of_ramjet_cycle_design_thrust(
    design_results: AnalysisResults,
) -> None:
    """Ideal/matched thrust within 15% of ramjet_cycle at the same point."""
    ramjet = RamjetCycleAnalysis()
    ramjet.setup(mach0=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M)
    ramjet_thrust_N = ramjet.execute()["thrust_N"]

    # Th1 (fully expanded + combustor loss) is the closest apples-to-apples
    # match to ramjet_cycle's matched-nozzle-with-pi_b thrust; Thi (ideal)
    # is the loss-free bound. Both must sit within 15%.
    for key in ("Thi_N", "Th1_N"):
        delta = abs(design_results[key] - ramjet_thrust_N) / ramjet_thrust_N
        assert delta < 0.15, f"{key} delta {delta:.3f} exceeds 15%"


def test_brayton_t2_cross_check_logged(design_results: AnalysisResults) -> None:
    """The Brayton T2 delta is quantified and flagged in metadata."""
    b = design_results.metadata["brayton_t2_cross_check"]
    assert b["station_model_tt2_K"] == pytest.approx(COMBUSTOR_EXIT_TEMP_DEFAULT_K)
    assert b["brayton_estimate_tt2_K"] > 0.0
    assert "delta_frac" in b
    assert isinstance(b["exceeds_5pct"], bool)


def test_teltik_v3_cross_check_logged(design_results: AnalysisResults) -> None:
    """V3-vs-Teltik delta evaluated at the CFD reference condition."""
    t = design_results.metadata["teltik_v3_cross_check"]
    assert t["teltik_cfd_v3_m_s"] == pytest.approx(TELTIK_V3_M_S)
    assert f"{TELTIK_MACH}" in t["condition"]
    assert f"{TELTIK_ALTITUDE_M:.0f}" in t["condition"]
    assert t["model_v3_m_s"] > 0.0


def test_nozzle_area_ratio_reports_all_three(
    design_results: AnalysisResults,
) -> None:
    """Model / YAML-design / CAD area ratios are all surfaced.

    2026-07-10: NOZZLE_AREA_RATIO_DESIGN updated 4.0 -> 1.317 (real
    drawing value, throat 0.210m / exit 0.241m). See HR-3/HR-7.
    """
    assert design_results["nozzle_area_ratio_model"] > 0.0
    assert design_results["nozzle_area_ratio_design_yaml"] == pytest.approx(1.317)
    assert design_results["nozzle_area_ratio_cad_cylindrical"] == pytest.approx(1.0)


def test_isp_in_hydrocarbon_ramjet_band(design_results: AnalysisResults) -> None:
    assert 400.0 < design_results["isp_s"] < 3000.0


def test_fuel_air_ratio_physical(design_results: AnalysisResults) -> None:
    assert 0.0 < design_results["f_fuel_air"] < 0.15


# --------------------------------------------------------------------------
# Guard / validation tests
# --------------------------------------------------------------------------


def test_execute_before_setup_raises() -> None:
    with pytest.raises(RuntimeError):
        GrzywkaCombustorNozzleAnalysis().execute()


def test_setup_rejects_subsonic_mach() -> None:
    with pytest.raises(ValueError):
        GrzywkaCombustorNozzleAnalysis().setup(mach0=0.8, altitude_m=10_000.0)


def test_setup_rejects_out_of_range_loss_coefficient() -> None:
    with pytest.raises(ValueError):
        GrzywkaCombustorNozzleAnalysis().setup(mach0=2.5, pi_cc=1.5)


def test_setup_rejects_combustor_temp_below_inlet_total() -> None:
    """Tt2 must exceed the recovered inlet total temperature."""
    with pytest.raises(ValueError):
        GrzywkaCombustorNozzleAnalysis().setup(
            mach0=2.5, altitude_m=10_000.0, combustor_exit_temp_K=300.0
        )


def test_validate_results_rejects_broken_hierarchy(
    design_results: AnalysisResults,
) -> None:
    """A hierarchy violation (Th2 > Th1) must fail validation."""
    analysis = GrzywkaCombustorNozzleAnalysis()
    analysis.setup(mach0=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M)
    bad = AnalysisResults(
        name="bad",
        fidelity=FidelityLevel.LEVEL_2,
        data=dict(design_results.data),
    )
    bad.data["Th2_N"] = bad.data["Th1_N"] + 1.0  # break the hierarchy
    assert analysis.validate_results(bad) is False
