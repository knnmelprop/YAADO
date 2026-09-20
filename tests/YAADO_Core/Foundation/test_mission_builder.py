"""Tests for :mod:`YAADO_Core.Foundation.mission_builder`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from YAADO_Core.ComponentStore import SolidMotor
from YAADO_Core.Foundation.flight_logger import YaadoJSONEncoder
from YAADO_Core.Foundation.mission_builder import (
    BoostSegment,
    ClimbSegment,
    CruiseSegment,
    DescentSegment,
    MissionBuilder,
    StagingSegment,
)
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig, ComponentNotFoundError

REPO_ROOT = Path(__file__).resolve().parents[3]
HARPOON_TOML = REPO_ROOT / "Hangar" / "examples" / "AGM-84_HARPOON" / "AGM-84_HARPOON.toml"


def test_mission_builder_standalone() -> None:
    """Build a complete standalone mission profile without vehicle binding."""
    builder = MissionBuilder("benchmark_mission")

    profile = (
        builder
        .add_segment(BoostSegment(name="rail_launch", launch_angle=85.0, azimuth=45.0, rail_length=5.0))
        .add_segment(StagingSegment(name="booster_sep", duration=0.8))
        .add_segment(ClimbSegment(name="ingress_climb", target_altitude=5000.0, target_mach=0.75, climb_rate=30.0))
        .add_segment(CruiseSegment(name="cruise_outbound", altitude=5000.0, mach=0.8, distance=150000.0))
        .add_segment(DescentSegment(name="terminal_dive", target_altitude=0.0, descent_rate=40.0))
        .build()
    )

    assert profile.name == "benchmark_mission"
    assert profile.vehicle_name is None
    assert len(profile.segments) == 5

    assert isinstance(profile.segments[0], BoostSegment)
    assert profile.segments[0].name == "rail_launch"
    assert profile.segments[0].launch_angle == 85.0
    assert profile.segments[0].azimuth == 45.0
    assert profile.segments[0].rail_length == 5.0

    assert isinstance(profile.segments[1], StagingSegment)
    assert profile.segments[1].duration == 0.8

    assert isinstance(profile.segments[2], ClimbSegment)
    assert profile.segments[2].target_altitude == 5000.0
    assert profile.segments[2].target_mach == 0.75

    assert isinstance(profile.segments[3], CruiseSegment)
    assert profile.segments[3].altitude == 5000.0
    assert profile.segments[3].distance == 150000.0

    assert isinstance(profile.segments[4], DescentSegment)
    assert profile.segments[4].target_altitude == 0.0
    assert profile.segments[4].descent_rate == 40.0


def test_mission_profile_structure() -> None:
    """Verify MissionProfile segment tuple access and structure."""
    profile = (
        MissionBuilder("structure_test")
        .add_segment(BoostSegment(name="boost", launch_angle=80.0))
        .add_segment(CruiseSegment(name="cruise", altitude=1000.0, mach=0.5, duration=60.0))
        .build()
    )

    assert len(profile.segments) == 2
    assert profile.segments[0].name == "boost"
    assert profile.segments[1].name == "cruise"


def test_mission_profile_immutability() -> None:
    """MissionProfile and segments must be immutable."""
    profile = (
        MissionBuilder("immutability_test")
        .add_segment(BoostSegment(name="boost", launch_angle=80.0))
        .build()
    )

    with pytest.raises((AttributeError, TypeError)):
        profile.name = "mutated"  # type: ignore[misc]

    with pytest.raises(ValidationError):
        profile.segments[0].name = "mutated"  # type: ignore[misc]


def test_mission_builder_with_vehicle_validation() -> None:
    """Build a profile bound to a real vehicle configuration (AGM-84 Harpoon)."""
    assert HARPOON_TOML.is_file(), f"Harpoon TOML not found at {HARPOON_TOML}"
    vehicle = BaseVehicleConfig.from_toml(HARPOON_TOML)

    builder = MissionBuilder("harpoon_sea_skim", vehicle=vehicle)

    profile = (
        builder
        .add_segment(BoostSegment(name="booster_fire", launch_angle=83.0, active_propulsion="launch_booster"))
        .add_segment(StagingSegment(name="booster_jettison", duration=0.5, jettison_component="launch_booster"))
        .add_segment(ClimbSegment(name="sea_skim_transition", target_altitude=15.0, target_mach=0.8, active_propulsion="sustainer"))
        .add_segment(CruiseSegment(name="sea_skim_dash", altitude=15.0, mach=0.85, distance=120000.0, active_propulsion="sustainer"))
        .add_segment(DescentSegment(name="terminal_dive", target_altitude=0.0, target_mach=0.85, active_propulsion="sustainer"))
        .build()
    )

    assert profile.vehicle_name == "AGM-84_HARPOON"
    assert len(profile.segments) == 5

    # Should pass validation against the same vehicle
    profile.validate_against_vehicle(vehicle)


def test_validation_errors() -> None:
    """Verify strict validation and loud error handling in MissionBuilder."""
    # Empty mission name
    with pytest.raises(ValueError, match="mission_name cannot be empty"):
        MissionBuilder("")

    with pytest.raises(ValueError, match="mission_name cannot be empty"):
        MissionBuilder("   ")

    builder = MissionBuilder("validation_test")

    # Duplicate segment name
    builder.add_segment(BoostSegment(name="phase_1", launch_angle=45.0))
    with pytest.raises(ValueError, match="already defined in mission"):
        builder.add_segment(BoostSegment(name="phase_1", launch_angle=50.0))

    # Empty profile build
    empty_builder = MissionBuilder("empty_mission")
    with pytest.raises(ValueError, match="must contain at least one segment"):
        empty_builder.build()


def test_vehicle_component_validation_errors() -> None:
    """Verify ComponentNotFoundError when active_propulsion or jettison is missing."""
    booster = SolidMotor(
        isp_vacuum=250.0,
        isp_sl=220.0,
        propellant_mass=50.0,
        burn_time=2.0,
        thrust_mean=40000.0,
        thrust_peak=45000.0,
        propellant_density=1700.0,
    )
    vehicle = BaseVehicleConfig(
        name="test_missile",
        propulsion={"booster": booster},
    )

    builder = MissionBuilder("mismatch_test", vehicle=vehicle)

    # Nonexistent propulsion
    with pytest.raises(ComponentNotFoundError, match="active_propulsion='nonexistent'"):
        builder.add_segment(BoostSegment(name="boost", launch_angle=80.0, active_propulsion="nonexistent"))

    # Nonexistent jettison component
    with pytest.raises(ComponentNotFoundError, match="jettison_component='ghost_wing'"):
        builder.add_segment(StagingSegment(name="sep", duration=1.0, jettison_component="ghost_wing"))

    # Standalone profile validated against incompatible vehicle
    standalone_profile = (
        MissionBuilder("incompatible_profile")
        .add_segment(BoostSegment(name="boost", launch_angle=80.0, active_propulsion="missing_booster"))
        .build()
    )
    with pytest.raises(ComponentNotFoundError, match="references active_propulsion='missing_booster'"):
        standalone_profile.validate_against_vehicle(vehicle)


def test_segment_model_validators() -> None:
    """Verify Pydantic validators on individual segment models."""
    # Cruise requires at least one of distance or duration
    with pytest.raises(ValidationError, match="requires at least one termination criteria"):
        CruiseSegment(name="cruise", altitude=1000.0, mach=0.5)

    # Cruise requires at least one of mach or velocity
    with pytest.raises(ValidationError, match="requires at least one speed specification"):
        CruiseSegment(name="cruise", altitude=1000.0, distance=10000.0)

    # Climb requires at least one rate or speed parameter
    with pytest.raises(ValidationError, match="requires at least one rate or speed parameter"):
        ClimbSegment(name="climb", target_altitude=2000.0)

    # Descent requires at least one rate or speed parameter
    with pytest.raises(ValidationError, match="requires at least one rate or speed parameter"):
        DescentSegment(name="descent", target_altitude=0.0)


def test_serialization_yaado_json_encoder() -> None:
    """MissionProfile must serialize cleanly with YaadoJSONEncoder."""
    profile = (
        MissionBuilder("json_test")
        .add_segment(BoostSegment(name="boost", launch_angle=80.0, azimuth=90.0))
        .add_segment(CruiseSegment(name="cruise", altitude=3000.0, mach=0.6, distance=40000.0))
        .build()
    )

    encoded = json.dumps(profile, cls=YaadoJSONEncoder)
    decoded = json.loads(encoded)

    assert decoded["name"] == "json_test"
    assert len(decoded["segments"]) == 2
    assert decoded["segments"][0]["type"] == "boost"
    assert decoded["segments"][0]["launch_angle"] == 80.0
    assert decoded["segments"][1]["type"] == "cruise"
    assert decoded["segments"][1]["mach"] == 0.6
