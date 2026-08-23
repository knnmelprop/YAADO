"""Unit tests for analyses.propulsion.inlet_performance."""

import math

import pytest

from IADE_Core.modules.powerplant.inlet_methods.wedge import (
    DEFAULT_INLET_ACTUATION,
    DEFAULT_N_CONES_M25,
    ETA_DIFFUSER,
    GAMMA,
    MACH_SPIKE_DESIGN,
    MULTI_CONE_THETA_DEG_4CONE,
    MULTI_CONE_THETA_DEG_5CONE,
    InletPerformanceAnalysis,
    MovableInletActuation,
    MultiConeInletPerformanceAnalysis,
    compute_transition_sequence,
    isa_atmosphere,
    mil_e_5007_eta_std,
    multi_cone_recovery_chain,
    normal_shock_mach2,
    normal_shock_total_pressure_ratio,
    oblique_shock_beta_rad,
    optimize_multi_cone_angles,
    spike_half_angle_rad,
)
from IADE_Core.Foundation.component_base import FidelityLevel


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
    """isa_atmosphere raises ValueError for negative altitude."""
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
    """mil_e_5007_eta_std returns 1.0 for subsonic Mach."""
    assert mil_e_5007_eta_std(0.8) == 1.0


def test_mil_e_5007_eta_std_at_mach_2p5() -> None:
    """mil_e_5007_eta_std at Mach 2.5 returns ~0.8703, the MIL-E-5007 standard."""
    eta_std = mil_e_5007_eta_std(2.5)
    assert eta_std == pytest.approx(0.8703, abs=0.001)


def test_inlet_performance_analysis_execute_before_setup_raises() -> None:
    """InletPerformanceAnalysis.execute() raises RuntimeError if called before setup()."""
    analysis = InletPerformanceAnalysis()
    with pytest.raises(RuntimeError):
        analysis.execute()


def test_inlet_performance_analysis_setup_rejects_subsonic_design_mach() -> None:
    """InletPerformanceAnalysis.setup() raises ValueError for subsonic design Mach."""
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


# ---------------------------------------------------------------------------
# Multi-cone (multi-shock) spike inlet — Phase 1 redesign
# ---------------------------------------------------------------------------


def test_default_n_cones_is_four() -> None:
    """The Mach-2.5 default is 4 cones — the minimum meeting MIL-E-5007."""
    assert DEFAULT_N_CONES_M25 == 4
    analysis = MultiConeInletPerformanceAnalysis()
    assert analysis._n_cones == 4


def test_multi_cone_chain_single_shock_matches_single_cone_relations() -> None:
    """A 1-element chain must reduce to the classic oblique+normal result."""
    theta_rad = math.radians(14.358)
    chain = multi_cone_recovery_chain(2.5, [theta_rad], ETA_DIFFUSER)
    assert chain["detached"] is False
    assert chain["eta_inlet"] == pytest.approx(0.6606, abs=0.001)


def test_optimize_multi_cone_angles_2cone_cannot_meet_mil_e_5007() -> None:
    """CONFIRMED physics (Seddon & Goldsmith 1999 Sec 4.3): 2 cones top out
    at eta ~0.799 at M 2.5 — below the 0.8703 standard. Do not 'fix' this."""
    _, eta = optimize_multi_cone_angles(2.5, 2)
    assert eta == pytest.approx(0.799, abs=0.005)
    assert eta < mil_e_5007_eta_std(2.5)


def test_optimize_multi_cone_angles_3cone_cannot_meet_mil_e_5007() -> None:
    """CONFIRMED physics: 3 cones top out at eta ~0.849 at M 2.5 — FAIL."""
    _, eta = optimize_multi_cone_angles(2.5, 3)
    assert eta == pytest.approx(0.849, abs=0.005)
    assert eta < mil_e_5007_eta_std(2.5)


def test_optimize_multi_cone_angles_4cone_meets_mil_e_5007() -> None:
    """4 optimized cones give eta ~0.874 — a thin PASS margin at M 2.5."""
    theta_rad, eta = optimize_multi_cone_angles(2.5, 4)
    assert len(theta_rad) == 4
    assert eta == pytest.approx(0.8741, abs=0.002)
    assert eta >= mil_e_5007_eta_std(2.5)


def test_optimize_multi_cone_angles_5cone_meets_mil_e_5007() -> None:
    """5 optimized cones give eta ~0.888 — a comfortable PASS at M 2.5."""
    theta_rad, eta = optimize_multi_cone_angles(2.5, 5)
    assert len(theta_rad) == 5
    assert eta == pytest.approx(0.8883, abs=0.002)
    assert eta >= mil_e_5007_eta_std(2.5) + 0.01


def test_multi_cone_inlet_analysis_design_point_meets_mil_e_5007() -> None:
    """End-to-end default (4-cone, optimized) design point PASSES MIL-E-5007."""
    analysis = MultiConeInletPerformanceAnalysis()
    analysis.setup(mach_design=2.5, altitude_m=10_000.0, n_cones=4)
    results = analysis.execute()

    assert results.fidelity == FidelityLevel.LEVEL_0
    assert results["n_cones"] == 4
    assert results["mach_post_normal"] < 1.0
    assert results["eta_inlet"] >= results["mil_e_5007_eta_std"]
    assert results["eta_inlet"] == pytest.approx(0.8741, abs=0.002)
    assert results.metadata["verdict"] == "PASS"
    assert results.metadata["shock_detached"] is False
    # Same freestream/capture as the single-cone analysis -> same mdot.
    assert results["mdot_design_kg_per_s"] == pytest.approx(15.17, abs=0.05)


def test_multi_cone_inlet_analysis_4cone_design() -> None:
    """Fixed Mach-2.5 4-cone preset (optimize_angles=False) also PASSES."""
    analysis = MultiConeInletPerformanceAnalysis()
    analysis.setup(
        mach_design=2.5, altitude_m=10_000.0, n_cones=4, optimize_angles=False
    )
    results = analysis.execute()

    assert results["theta_increments_deg"] == pytest.approx(
        list(MULTI_CONE_THETA_DEG_4CONE), abs=1e-9
    )
    assert results["eta_inlet"] >= results["mil_e_5007_eta_std"]
    assert results.metadata["verdict"] == "PASS"
    assert results.metadata["angle_source"] == "fixed_mach_2p5_preset"


def test_multi_cone_inlet_analysis_5cone_preset_design() -> None:
    """Fixed Mach-2.5 5-cone preset gives a comfortable PASS margin."""
    analysis = MultiConeInletPerformanceAnalysis()
    analysis.setup(
        mach_design=2.5, altitude_m=10_000.0, n_cones=5, optimize_angles=False
    )
    results = analysis.execute()

    assert results["theta_increments_deg"] == pytest.approx(
        list(MULTI_CONE_THETA_DEG_5CONE), abs=1e-9
    )
    assert results["margin"] >= 0.01
    assert results.metadata["verdict"] == "PASS"


def test_multi_cone_inlet_analysis_rejects_preset_for_2_and_3_cones() -> None:
    """No fixed presets exist for cone counts that cannot meet MIL-E-5007."""
    for n_cones in (2, 3):
        analysis = MultiConeInletPerformanceAnalysis()
        with pytest.raises(ValueError):
            analysis.setup(n_cones=n_cones, optimize_angles=False)


def test_multi_cone_inlet_analysis_execute_before_setup_raises() -> None:
    """MultiConeInletPerformanceAnalysis.execute() raises RuntimeError if called before setup()."""
    analysis = MultiConeInletPerformanceAnalysis()
    with pytest.raises(RuntimeError):
        analysis.execute()


def test_multi_cone_inlet_analysis_setup_rejects_bad_inputs() -> None:
    """MultiConeInletPerformanceAnalysis.setup() rejects subsonic Mach, invalid n_cones, and eta_diffuser <= 0."""
    analysis = MultiConeInletPerformanceAnalysis()
    with pytest.raises(ValueError):
        analysis.setup(mach_design=0.8)
    with pytest.raises(ValueError):
        analysis.setup(n_cones=0)
    with pytest.raises(ValueError):
        analysis.setup(eta_diffuser=0.0)


# ---------------------------------------------------------------------------
# Movable (translating-centerbody) spike inlet — actuation model (Phase 4b)
# ---------------------------------------------------------------------------


def test_movable_inlet_actuation_todo_physical_params_are_flagged() -> None:
    """All four actuation fields are TODO_PHYSICAL_PARAM placeholders — assert
    they are clearly flagged with a documented range in metadata (we have no
    ground truth for their magnitudes, only that they must be marked)."""
    meta = DEFAULT_INLET_ACTUATION.metadata()
    todo = meta["todo_physical_params"]
    for field in (
        "screw_lead_mm",
        "motor_torque_Nm",
        "cone_travel_mm",
        "transition_time_s",
    ):
        assert field in todo
        assert todo[field].startswith("TODO_PHYSICAL_PARAM")
        assert "typical" in todo[field]
        # The field is still present with a (placeholder) numeric value.
        assert isinstance(meta[field], float)
    assert "No Grzywka MATLAB actuator data" in meta["source"]


def test_movable_inlet_actuation_defaults_within_documented_ranges() -> None:
    """Placeholder defaults sit inside the documented typical ranges (this
    checks the defaults are self-consistent, NOT that they are 'correct')."""
    a = DEFAULT_INLET_ACTUATION
    assert 1.0 <= a.screw_lead_mm <= 10.0
    assert 0.1 <= a.motor_torque_Nm <= 2.0
    assert 30.0 <= a.cone_travel_mm <= 90.0
    assert 1.0 <= a.transition_time_s <= 10.0
    assert a.slew_rate_mm_s == pytest.approx(
        a.cone_travel_mm / a.transition_time_s
    )


def test_cone_position_for_mach_endpoints_and_clamp() -> None:
    """Position schedule pins 0 mm at retracted Mach and full stroke at design
    Mach, and clamps above the design Mach."""
    a = MovableInletActuation()
    assert a.cone_position_for_mach(0.0) == pytest.approx(0.0)
    assert a.cone_position_for_mach(MACH_SPIKE_DESIGN) == pytest.approx(
        a.cone_travel_mm
    )
    # Beyond the design Mach the stroke is clamped, not extrapolated.
    assert a.cone_position_for_mach(3.5) == pytest.approx(a.cone_travel_mm)


def test_transition_sequence_startup_m0_to_m25() -> None:
    """Startup/acceleration M0 -> M2.5: monotonically INCREASING position from
    0 mm to full stroke, starting at t=0 and ending at the full-stroke time."""
    a = MovableInletActuation()
    seq = compute_transition_sequence(0.0, 2.5, velocity_m_s=0.0, altitude_m=0.0)

    times = [t for t, _ in seq]
    positions = [p for _, p in seq]

    # Correct start/end times.
    assert times[0] == pytest.approx(0.0)
    assert times[-1] == pytest.approx(a.transition_time_s)  # full stroke
    # Correct start/end positions.
    assert positions[0] == pytest.approx(0.0)
    assert positions[-1] == pytest.approx(a.cone_travel_mm)
    # Monotonic (non-decreasing) position and strictly increasing time.
    assert all(p2 >= p1 for p1, p2 in zip(positions, positions[1:]))
    assert all(t2 > t1 for t1, t2 in zip(times, times[1:]))
    # Every sampled position stays within the stroke limits.
    assert all(0.0 <= p <= a.cone_travel_mm + 1e-9 for p in positions)


def test_transition_sequence_shutdown_m25_to_m0() -> None:
    """Shutdown/deceleration M2.5 -> M0: monotonically DECREASING position from
    full stroke back to 0 mm, over the same full-stroke duration."""
    a = MovableInletActuation()
    seq = compute_transition_sequence(2.5, 0.0, velocity_m_s=740.0, altitude_m=10_000.0)

    times = [t for t, _ in seq]
    positions = [p for _, p in seq]

    assert times[0] == pytest.approx(0.0)
    assert times[-1] == pytest.approx(a.transition_time_s)
    assert positions[0] == pytest.approx(a.cone_travel_mm)
    assert positions[-1] == pytest.approx(0.0)
    # Monotonic (non-increasing) position.
    assert all(p2 <= p1 for p1, p2 in zip(positions, positions[1:]))
    assert all(0.0 <= p <= a.cone_travel_mm + 1e-9 for p in positions)


def test_transition_sequence_zero_move_returns_single_sample() -> None:
    """A no-op transition (identical Mach) returns one (0.0, position) point."""
    seq = compute_transition_sequence(2.5, 2.5, velocity_m_s=740.0, altitude_m=10_000.0)
    assert len(seq) == 1
    assert seq[0][0] == pytest.approx(0.0)
    assert seq[0][1] == pytest.approx(DEFAULT_INLET_ACTUATION.cone_travel_mm)


def test_transition_sequence_partial_move_duration_scales_with_delta() -> None:
    """A half-stroke move (M0 -> M1.25) takes half the full-stroke time."""
    a = MovableInletActuation()
    seq = compute_transition_sequence(
        0.0, MACH_SPIKE_DESIGN / 2.0, velocity_m_s=370.0, altitude_m=5000.0
    )
    assert seq[-1][0] == pytest.approx(a.transition_time_s / 2.0)
    assert seq[-1][1] == pytest.approx(a.cone_travel_mm / 2.0)


def test_transition_sequence_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError):
        compute_transition_sequence(0.0, 2.5, 0.0, 0.0, n_samples=1)
    with pytest.raises(ValueError):
        compute_transition_sequence(-0.5, 2.5, 0.0, 0.0)


def test_inlet_performance_analysis_mass_flow_scales_with_capture_area() -> None:
    """Design-point mass flow scales linearly with inlet capture area."""
    analysis = InletPerformanceAnalysis()
    analysis.setup(mach_design=2.5, altitude_m=10_000.0, capture_area_m2=0.1)
    results = analysis.execute()
    assert results["mdot_design_kg_per_s"] == pytest.approx(
        results["capture_area_m2"]
        / 0.04909
        * 15.167490506864516,
        rel=0.01,
    )
