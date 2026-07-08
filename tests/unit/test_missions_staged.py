# MELprop-IADE | tests.unit.test_missions_staged | v0.1.0
"""Unit tests for workflows.ramp_staged_mission and booster trajectory fix."""

import math
from pathlib import Path

import pytest

from core.mission_builder import MissionBuilder
from workflows.ramp_staged_mission import BurnoutState, build_ramp_staged_mission


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
    """The fixed 83-degree launch angle allows the booster to reach 6 s burnout.

    This test verifies that the trajectory fix (LAUNCH_ANGLE_DEG = 83.0)
    prevents premature ground impact before the nominal burn_time_s = 6.0 s.
    The test reads the burnout_state.json produced by booster_burnout.py.
    """
    this_dir = Path(__file__).resolve().parent
    burnout_json = this_dir.parents[1] / "analyses" / "trajectory" / "burnout_state.json"

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

    # Check that burnout occurred at the nominal 6.0 s (not cut short)
    assert data["burnout_time_s"] == pytest.approx(6.0, abs=0.01)

    # Check that the launch angle was indeed updated to 83 deg
    assert data["metadata"]["launch_angle_deg"] == pytest.approx(83.0, abs=0.1)

    # Sanity-check the burnout state: Mach > 1.0, altitude > 0
    assert data["burnout_mach"] > 1.0, "Booster should reach supersonic by burnout"
    assert data["burnout_altitude_m"] > 0.0, "Booster altitude should be > 0 at burnout"


def test_booster_burnout_state_is_supersonic() -> None:
    """The booster reaches Mach > 1.0 by burnout (typical small rocket performance)."""
    this_dir = Path(__file__).resolve().parent
    burnout_json = this_dir.parents[1] / "analyses" / "trajectory" / "burnout_state.json"

    if not burnout_json.exists():
        pytest.skip("burnout_state.json not found")

    import json

    data = json.loads(burnout_json.read_text(encoding="utf-8"))
    assert data["burnout_mach"] > 1.0


def test_booster_burnout_altitude_is_positive_and_reasonable() -> None:
    """Burnout altitude should be in the range [500, 3000] m for this booster."""
    this_dir = Path(__file__).resolve().parent
    burnout_json = this_dir.parents[1] / "analyses" / "trajectory" / "burnout_state.json"

    if not burnout_json.exists():
        pytest.skip("burnout_state.json not found")

    import json

    data = json.loads(burnout_json.read_text(encoding="utf-8"))
    h_burnout = data["burnout_altitude_m"]
    assert 500.0 < h_burnout < 3000.0, (
        f"Burnout altitude {h_burnout:.1f} m is outside expected range [500, 3000] m"
    )
