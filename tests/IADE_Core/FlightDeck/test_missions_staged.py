# MELprop-IADE | tests.unit.test_missions_staged | v0.1.0
"""Unit tests for workflows.ramp_staged_mission and booster trajectory fix."""

import math
from pathlib import Path

import pytest

from IADE_Core.FlightDeck.mission_builder import MissionBuilder
from IADE_Core.FlightDeck.ramp_staged_mission import BurnoutState, build_ramp_staged_mission


def test_mission_builder_rejects_duplicate_segment_names() -> None:
    """MissionBuilder raises ValueError if a segment name is reused."""
    builder = MissionBuilder("test_mission")
    builder.add_segment("seg1", "climb", altitude_end_m=1000.0)
    with pytest.raises(ValueError, match="already defined"):
        builder.add_segment("seg1", "cruise", mach=0.3)


def test_mission_builder_fluent_chaining() -> None:
    """MissionBuilder returns self on add_segment for fluent chaining."""
    builder = MissionBuilder("test_mission")
    result = builder.add_segment("seg1", "climb", altitude_end_m=1000.0)
    assert result is builder


def test_mission_builder_build_returns_segment_list() -> None:
    """MissionBuilder.build() returns an ordered list of MissionSegment."""
    mission = (
        MissionBuilder("test_mission")
        .add_segment("climb", "climb", altitude_end_m=1000.0)
        .add_segment("cruise", "cruise", mach=0.3)
        .build()
    )
    assert len(mission) == 2
    assert mission[0].name == "climb"
    assert mission[0].segment_type == "climb"
    assert mission[1].name == "cruise"
    assert mission[1].segment_type == "cruise"


def test_ramp_staged_mission_has_three_segments() -> None:
    """The two-stage ramjet mission has boost + staging_event + cruise segments."""
    burnout = BurnoutState(
        time_s=6.0,
        mass_kg=280.0,
        velocity_ms=400.0,
        velocity_x_ms=50.0,
        velocity_h_ms=395.0,
        altitude_m=1200.0,
        range_m=150.0,
        mach=1.2,
        dynamic_pressure_pa=90000.0,
    )
    mission = build_ramp_staged_mission(burnout)
    assert len(mission) == 3
    assert mission[0].name == "boost_stage_1"
    assert mission[0].segment_type == "boost"
    assert mission[1].name == "staging_event"
    assert mission[1].segment_type == "staging_event"
    assert mission[2].name == "cruise_stage_2_ramjet"
    assert mission[2].segment_type == "cruise"


def test_staging_event_receives_burnout_state_as_initial_conditions() -> None:
    """The staging_event segment parameters include the booster burnout state."""
    burnout = BurnoutState(
        time_s=6.0,
        mass_kg=280.02,
        velocity_ms=413.5,
        velocity_x_ms=57.3,
        velocity_h_ms=409.5,
        altitude_m=1289.3,
        range_m=167.5,
        mach=1.23,
        dynamic_pressure_pa=92362.7,
    )
    mission = build_ramp_staged_mission(burnout)
    staging_seg = mission[1]
    params = staging_seg.parameters

    assert params["event_type"] == "booster_burnout_to_ramjet_ignition"
    assert params["initial_mass_kg"] == pytest.approx(280.02, abs=0.01)
    assert params["initial_velocity_ms"] == pytest.approx(413.5, abs=0.1)
    assert params["initial_altitude_m"] == pytest.approx(1289.3, abs=0.1)
    assert params["initial_mach"] == pytest.approx(1.23, abs=0.01)


def test_booster_trajectory_survives_to_nominal_burnout() -> None:
    """The fixed 83-degree launch angle allows the booster to reach nominal burnout.

    This test verifies that the trajectory fix (LAUNCH_ANGLE_DEG = 83.0)
    prevents premature ground impact before the nominal
    ``stage_1.propulsion.burn_time_s``. The test reads the
    burnout_state.json produced by booster_burnout.py.

    2026-07-11: the nominal burn time changed from the SZACOWANY 6.0 s to
    the real PRD-240 static-test curve's 5.18 s (vehicle_config.yaml
    updated to the real archived thrust curve -- see docs/decision-log.md
    "Real PRD-240 booster thrust curve found in archive"). Updated the
    expected value to match; the ground-impact and launch-angle checks are
    unaffected by this change.
    """
    this_dir = Path(__file__).resolve().parent
    burnout_json = this_dir.parents[2] / "IADE_Core" / "modules" / "trajectory" / "burnout_state.json"

    if not burnout_json.exists():
        pytest.skip(
            "burnout_state.json not found; run "
            "analyses/trajectory/booster_burnout.py first"
        )

    import json

    data = json.loads(burnout_json.read_text(encoding="utf-8"))

    # Check that the trajectory did NOT hit the ground before burnout
    assert not data["metadata"]["ground_impact_before_burnout"], (
        "Booster hit ground before burnout; launch angle fix failed"
    )

    # Check that burnout occurred at the nominal 5.18 s (real PRD-240 curve, not cut short)
    assert data["burnout_time_s"] == pytest.approx(5.18, abs=0.01)

    # Check that the launch angle was indeed updated to 83 deg
    assert data["metadata"]["launch_angle_deg"] == pytest.approx(83.0, abs=0.1)

    # Sanity-check the burnout state: Mach > 1.0, altitude > 0
    assert data["burnout_mach"] > 1.0, "Booster should reach supersonic by burnout"
    assert data["burnout_altitude_m"] > 0.0, "Booster altitude should be > 0 at burnout"


def test_booster_burnout_state_is_supersonic() -> None:
    """The booster reaches Mach > 1.0 by burnout (typical small rocket performance).

    History (both changes 2026-07-11, see docs/decision-log.md): updating
    stage_1.propulsion to the real PRD-240 thrust curve alone (lower total
    impulse, 56.38 vs the placeholder's implied ~152 kN*s) made this
    subsonic at the then-current 355.02 kg vehicle mass, so this test was
    briefly renamed/inverted to assert Mach < 1.0. Separately correcting
    mass_properties.total_mass_kg (355.02 -> 100.0 kg; the Fusion
    physics-engine mass estimate is considered wrong/oversized, the
    archive's own reference mass is the real target) brings burnout back
    above Mach 1.0 (~1.69 at the nominal 83deg launch angle). Reverted to
    the original supersonic assertion, now backed by real data on both
    the motor and mass axes.
    """
    this_dir = Path(__file__).resolve().parent
    burnout_json = this_dir.parents[2] / "IADE_Core" / "modules" / "trajectory" / "burnout_state.json"

    if not burnout_json.exists():
        pytest.skip("burnout_state.json not found")

    import json

    data = json.loads(burnout_json.read_text(encoding="utf-8"))
    assert data["burnout_mach"] > 1.0


def _sample_burnout_state() -> BurnoutState:
    """Build a representative BurnoutState for cruise-segment tests."""
    return BurnoutState(
        time_s=6.0,
        mass_kg=280.02,
        velocity_ms=413.5,
        velocity_x_ms=57.3,
        velocity_h_ms=409.5,
        altitude_m=1289.3,
        range_m=167.5,
        mach=1.23,
        dynamic_pressure_pa=92362.7,
    )


def test_cruise_segment_has_positive_thrust_from_grzywka_cycle_model() -> None:
    """The cruise segment's thrust_N comes from the L2 Grzywka cycle model.

    This asserts the design point is populated by
    analyses.propulsion.combustor_nozzle_cycle.GrzywkaCombustorNozzleAnalysis
    rather than the old fixed-guess stub (thrust_N == 0.0 would indicate
    the fallback stub path was taken), and that the top-level thrust_N
    mirrors the nominal Th1 (combustor-loss-only, non-ideal) scenario --
    Night-3 Phase 2 switched the nominal from Th2 to Th1; Thi and Th2
    remain always-present explicit upper/lower bounds.
    """
    mission = build_ramp_staged_mission(_sample_burnout_state())
    cruise_params = mission[2].parameters

    assert cruise_params["thrust_N"] > 0.0
    scenarios = cruise_params["thrust_scenarios"]
    assert cruise_params["thrust_N"] == pytest.approx(scenarios["Th1"]["thrust_N"])
    # All three scenarios always present as explicit bounds (verification gate).
    assert cruise_params["thrust_upper_bound_N"] == pytest.approx(
        scenarios["Thi"]["thrust_N"]
    )
    assert cruise_params["thrust_lower_bound_N"] == pytest.approx(
        scenarios["Th2"]["thrust_N"]
    )


def test_cruise_segment_preserves_all_three_grzywka_thrust_scenarios() -> None:
    """Thi/Th1/Th2 are all preserved as separate named scenarios, never collapsed.

    Per Grzywka Sec. 6.2.2, the physical hierarchy Thi >= Th1 >= Th2 must
    hold since the three scenarios share identical mass flow, Tt1, Tt2
    and fuel-air ratio -- only the delivered nozzle total pressure
    differs (see analyses.propulsion.combustor_nozzle_cycle module
    docstring).
    """
    mission = build_ramp_staged_mission(_sample_burnout_state())
    cruise_params = mission[2].parameters

    assert "thrust_scenarios" in cruise_params
    scenarios = cruise_params["thrust_scenarios"]
    assert set(scenarios.keys()) == {"Thi", "Th1", "Th2"}

    thi, th1, th2 = (
        scenarios["Thi"]["thrust_N"],
        scenarios["Th1"]["thrust_N"],
        scenarios["Th2"]["thrust_N"],
    )
    assert thi > 0.0 and th1 > 0.0 and th2 > 0.0
    assert thi >= th1 >= th2


def test_cruise_segment_scenario_dicts_have_expected_fields() -> None:
    """Each thrust scenario carries its own TSFC, Isp, cruise time and range."""
    mission = build_ramp_staged_mission(_sample_burnout_state())
    scenarios = mission[2].parameters["thrust_scenarios"]

    for key in ("Thi", "Th1", "Th2"):
        scenario = scenarios[key]
        for field in (
            "thrust_N",
            "tsfc_kg_per_Ns",
            "isp_s",
            "mdot_fuel_kg_s",
            "cruise_time_s",
            "cruise_range_m",
            "description",
        ):
            assert field in scenario, f"scenario {key!r} missing {field!r}"
        assert scenario["thrust_N"] > 0.0
        assert scenario["tsfc_kg_per_Ns"] > 0.0
        assert scenario["isp_s"] > 0.0
        assert scenario["mdot_fuel_kg_s"] > 0.0
        assert math.isfinite(scenario["cruise_time_s"])
        assert scenario["cruise_time_s"] > 0.0
        assert math.isfinite(scenario["cruise_range_m"])
        assert scenario["cruise_range_m"] > 0.0


def test_cruise_segment_scenario_fuel_flow_is_invariant_across_thrust_models() -> None:
    """mdot_fuel_kg_s is identical across Thi/Th1/Th2 (Grzywka model property).

    The three thrust scenarios share the same combustor mass flow, Tt1,
    Tt2 and fuel-air ratio; only the delivered nozzle total pressure
    differs. tsfc_kg_per_Ns and isp_s, however, DO vary with thrust:
    higher thrust (Thi) means lower TSFC and higher Isp than the more
    conservative Th2.
    """
    mission = build_ramp_staged_mission(_sample_burnout_state())
    scenarios = mission[2].parameters["thrust_scenarios"]

    mdot_thi = scenarios["Thi"]["mdot_fuel_kg_s"]
    mdot_th1 = scenarios["Th1"]["mdot_fuel_kg_s"]
    mdot_th2 = scenarios["Th2"]["mdot_fuel_kg_s"]
    assert mdot_thi == pytest.approx(mdot_th1)
    assert mdot_th1 == pytest.approx(mdot_th2)

    # Higher thrust -> lower TSFC, higher Isp (same fuel flow, more thrust
    # per unit fuel).
    assert scenarios["Thi"]["tsfc_kg_per_Ns"] <= scenarios["Th2"]["tsfc_kg_per_Ns"]
    assert scenarios["Thi"]["isp_s"] >= scenarios["Th2"]["isp_s"]


def test_cruise_segment_scenario_range_and_endurance_computed_per_scenario() -> None:
    """cruise_time_s/cruise_range_m are derived per-scenario, not copy-pasted from Th2.

    Because mdot_fuel_kg_s is scenario-invariant (see
    test_cruise_segment_scenario_fuel_flow_is_invariant_across_thrust_models),
    cruise_time_s and cruise_range_m come out numerically equal across
    the three scenarios at this constant-cruise-Mach design point -- a
    documented physical property of the Grzywka model, not a shortcut
    that reused Th2's number without deriving it per scenario. Each
    scenario's own cruise_time_s must still be internally consistent
    with ITS OWN fuel_mass_kg / mdot_fuel_kg_s.
    """
    mission = build_ramp_staged_mission(_sample_burnout_state())
    cruise_params = mission[2].parameters
    scenarios = cruise_params["thrust_scenarios"]
    fuel_mass_kg = cruise_params["fuel_mass_kg"]

    for key in ("Thi", "Th1", "Th2"):
        scenario = scenarios[key]
        expected_time_s = fuel_mass_kg / scenario["mdot_fuel_kg_s"]
        assert scenario["cruise_time_s"] == pytest.approx(expected_time_s, rel=1e-6)

    assert scenarios["Thi"]["cruise_time_s"] == pytest.approx(
        scenarios["Th2"]["cruise_time_s"]
    )
    assert scenarios["Thi"]["cruise_range_m"] == pytest.approx(
        scenarios["Th2"]["cruise_range_m"]
    )


def test_cruise_segment_tsfc_in_plausible_hydrocarbon_ramjet_band() -> None:
    """TSFC should fall in a physically plausible kerosene-ramjet range.

    A TSFC of roughly 3e-5 to 2.5e-4 kg/(N*s) corresponds to Isp of
    ~400-3400 s, consistent with the ~400-3000 s Isp band asserted by
    RamjetCycleAnalysis.validate_results() (Isp = 1/(tsfc*g0)).
    """
    mission = build_ramp_staged_mission(_sample_burnout_state())
    cruise_params = mission[2].parameters

    assert 3e-5 < cruise_params["tsfc_kg_per_Ns"] < 2.5e-4


def test_cruise_segment_time_derived_from_fuel_mass_and_mdot_fuel() -> None:
    """cruise_time_s must equal fuel_mass_kg / mdot_fuel_kg_s (derived, not guessed)."""
    mission = build_ramp_staged_mission(_sample_burnout_state())
    cruise_params = mission[2].parameters

    assert cruise_params["fuel_mass_kg"] == pytest.approx(15.0)
    assert cruise_params["mdot_fuel_kg_s"] > 0.0
    expected_cruise_time_s = (
        cruise_params["fuel_mass_kg"] / cruise_params["mdot_fuel_kg_s"]
    )
    assert cruise_params["cruise_time_s"] == pytest.approx(
        expected_cruise_time_s, rel=1e-6
    )
    assert math.isfinite(cruise_params["cruise_time_s"])
    assert cruise_params["cruise_time_s"] > 0.0


def test_cruise_segment_range_derived_from_cruise_time_and_velocity() -> None:
    """cruise_range_m must be finite and positive, consistent with a real design point."""
    mission = build_ramp_staged_mission(_sample_burnout_state())
    cruise_params = mission[2].parameters

    assert math.isfinite(cruise_params["cruise_range_m"])
    assert cruise_params["cruise_range_m"] > 0.0


def test_cruise_segment_note_discloses_reference_model() -> None:
    """The cruise segment note discloses the L2 cycle model and its open gaps.

    Per the project verification-gate rules, any segment fed by a
    single-method analysis must state the reference model, note the
    unavailable MATLAB baseline, and disclose the open CFD delta.
    """
    mission = build_ramp_staged_mission(_sample_burnout_state())
    note = mission[2].parameters["note"]

    assert "L2" in note
    assert "MATLAB baseline unavailable" in note
    assert "CFD delta" in note
    assert "quasi-steady design point" in note


def test_booster_burnout_altitude_is_positive_and_reasonable() -> None:
    """Burnout altitude should be in the range [500, 3000] m for this booster.

    2026-07-11: briefly narrowed to [200, 1000] m after the real PRD-240
    thrust curve (lower impulse) dropped burnout altitude to ~387 m at the
    then-current 355.02 kg vehicle mass. Reverted to the original [500,
    3000] m bound after mass_properties.total_mass_kg was separately
    corrected to 100.0 kg (the Fusion physics-engine estimate is
    considered wrong/oversized) -- real burnout altitude is now ~1520 m
    at the nominal 83deg launch angle, comfortably back in this range.
    See docs/decision-log.md for both changes.
    """
    this_dir = Path(__file__).resolve().parent
    burnout_json = this_dir.parents[2] / "IADE_Core" / "modules" / "trajectory" / "burnout_state.json"

    if not burnout_json.exists():
        pytest.skip("burnout_state.json not found")

    import json

    data = json.loads(burnout_json.read_text(encoding="utf-8"))
    h_burnout = data["burnout_altitude_m"]
    assert 500.0 < h_burnout < 3000.0, (
        f"Burnout altitude {h_burnout:.1f} m is outside expected range [500, 3000] m"
    )
