# MELprop-IADE | tests.unit.test_propulsion_inlet | v0.1.0
"""Unit tests for analyses.propulsion.inlet_performance."""

import math

import pytest

from analyses.propulsion.inlet_performance import (
    GAMMA,
    InletPerformanceAnalysis,
    isa_atmosphere,
    mil_e_5007_eta_std,
    normal_shock_mach2,
    normal_shock_total_pressure_ratio,
    oblique_shock_beta_rad,
    spike_half_angle_rad,
)
from core.component_base import FidelityLevel


def test_spike_half_angle_matches_fusion_v6_geometry() -> None:
    """Cone length 0.293 m / base diameter 0.150 m -> ~14.36 deg."""
    delta_deg = math.degrees(spike_half_angle_rad(0.293, 0.150))
    assert delta_deg == pytest.approx(14.358, abs=0.01)


def test_isa_atmosphere_10km_matches_standard_values() -> None:
    """ISA at 10,000 m: T ~ 223.15 K, p ~ 26.5 kPa (US Std Atmosphere 1976)."""
    state = isa_atmosphere(10_000.0)
    assert state.temperature_K == pytest.approx(223.15, abs=0.01)
    assert state.pressure_Pa == pytest.approx(26436.0, rel=0.01)
    assert state.density_kg_m3 == pytest.approx(0.4127, rel=0.01)
    assert state.speed_of_sound_m_s == pytest.approx(299.5, rel=0.01)


def test_isa_atmosphere_rejects_negative_altitude() -> None:
    with pytest.raises(ValueError):
        isa_atmosphere(-1.0)


def test_oblique_shock_weak_solution_at_mach_2p5() -> None:
    """Weak-shock beta for M=2.5, theta=14.358 deg is ~36.25 deg."""
    theta_rad = math.radians(14.358)
    beta_rad = oblique_shock_beta_rad(2.5, theta_rad)
    assert beta_rad is not None
    assert math.degrees(beta_rad) == pytest.approx(36.249, abs=0.05)


def test_oblique_shock_detaches_at_low_mach_for_this_geometry() -> None:
    """At M=1.3 the 14.36 deg half-angle exceeds theta_max -> detached (None)."""
    theta_rad = math.radians(14.358)
    beta_rad = oblique_shock_beta_rad(1.3, theta_rad)
    assert beta_rad is None


def test_normal_shock_relations_mach_1_are_identity() -> None:
    """A trivial M=1 'shock' should leave Mach and total pressure unchanged."""
    assert normal_shock_mach2(1.0, GAMMA) == pytest.approx(1.0, abs=1e-6)
    assert normal_shock_total_pressure_ratio(1.0, GAMMA) == pytest.approx(1.0, abs=1e-6)


def test_normal_shock_total_pressure_ratio_decreases_with_mach() -> None:
    """Stronger normal shocks lose more total pressure."""
    r1 = normal_shock_total_pressure_ratio(1.5, GAMMA)
    r2 = normal_shock_total_pressure_ratio(2.5, GAMMA)
    assert 0.0 < r2 < r1 < 1.0


def test_mil_e_5007_eta_std_subsonic_is_unity() -> None:
    assert mil_e_5007_eta_std(0.8) == 1.0


def test_mil_e_5007_eta_std_at_mach_2p5() -> None:
    eta_std = mil_e_5007_eta_std(2.5)
    assert eta_std == pytest.approx(0.8703, abs=0.001)


def test_inlet_performance_analysis_execute_before_setup_raises() -> None:
    analysis = InletPerformanceAnalysis()
    with pytest.raises(RuntimeError):
        analysis.execute()


def test_inlet_performance_analysis_setup_rejects_subsonic_design_mach() -> None:
    analysis = InletPerformanceAnalysis()
    with pytest.raises(ValueError):
        analysis.setup(mach_design=0.8)


def test_inlet_performance_analysis_design_point_mach_2p5() -> None:
    """End-to-end design-point run: FidelityLevel.LEVEL_0, physically valid,
    and matches the hand-derived shock chain (eta_inlet ~ 0.6606, FAIL vs
    MIL-E-5007 at eta_std ~ 0.8703 for this single-cone spike)."""
    analysis = InletPerformanceAnalysis()
    analysis.setup(mach_design=2.5, altitude_m=10_000.0)
    results = analysis.execute()

    assert results.fidelity == FidelityLevel.LEVEL_0
    assert results["spike_half_angle_deg"] == pytest.approx(14.358, abs=0.01)
    assert results["mach_post_normal"] < 1.0
    assert 0.0 < results["eta_inlet"] < results["eta_diffuser"]
    assert results["eta_inlet"] == pytest.approx(0.6606, abs=0.001)
    assert results["mil_e_5007_eta_std"] == pytest.approx(0.8703, abs=0.001)
    assert results.metadata["verdict"] == "FAIL"
    assert results.metadata["shock_detached"] is False
    assert results["mdot_design_kg_per_s"] == pytest.approx(15.17, abs=0.05)


def test_inlet_performance_analysis_mass_flow_scales_with_capture_area() -> None:
    analysis = InletPerformanceAnalysis()
    analysis.setup(mach_design=2.5, altitude_m=10_000.0, capture_area_m2=0.1)
    results = analysis.execute()
    assert results["mdot_design_kg_per_s"] == pytest.approx(
        results["capture_area_m2"]
        / 0.04909
        * 15.167490506864516,
        rel=0.01,
    )
