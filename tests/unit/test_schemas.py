# MELprop-IADE | tests.unit.test_schemas | v0.1.0
"""Unit tests for src.schemas.vehicle_schema."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.schemas.vehicle_schema import (
    BaseVehicleConfig,
    RocketConfig,
    UAVConfig,
    WingConfig,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

VALID_UAV = {
    "name": "TestUAV",
    "vehicle_type": "UAV",
    "description": "unit-test drone",
    "wing": {
        "aspect_ratio": 8.0,
        "sweep_deg": 5.0,
        "taper_ratio": 0.7,
        "span_m": 2.5,
        "airfoil_root": "NACA2412",
        "airfoil_tip": "NACA2412",
    },
    "propulsion": {
        "type": "turbojet",
        "name": "GTM-140",
        "thrust_N": 140.0,
        "sfc_kg_per_Ns": 2.8e-5,
        "mass_kg": 1.2,
        "mach_range": (0.0, 0.8),
    },
}

VALID_ROCKET = {
    "name": "TestRocket",
    "vehicle_type": "Rocket",
    "description": "unit-test rocket",
    "stage_1": {
        "type": "solid_rocket",
        "isp_s": 220.0,
        "propellant_mass_kg": 15.0,
        "burn_time_s": 5.0,
        "thrust_N": 10000.0,
    },
    "stage_2": {
        "type": "ramjet",
        "design_mach": 2.5,
        "fuel_type": "kerosene",
        "combustor_temp_K": 2000.0,
        "nozzle_area_ratio": 4.0,
    },
    "body": {"length_m": 3.0, "diameter_m": 0.2, "nose_type": "ogive"},
    "fins": {"count": 4, "span_m": 0.15, "sweep_deg": 45.0},
}


def test_valid_uav_config() -> None:
    """A physically sensible UAV config validates without errors."""
    uav = UAVConfig.model_validate(VALID_UAV)
    assert uav.vehicle_type == "UAV"
    assert uav.wing.aspect_ratio == pytest.approx(8.0)
    assert uav.propulsion.mach_range == (0.0, 0.8)


def test_valid_rocket_config() -> None:
    """A physically sensible two-stage rocket config validates."""
    rocket = RocketConfig.model_validate(VALID_ROCKET)
    assert rocket.vehicle_type == "Rocket"
    assert rocket.stage_1.isp_s == pytest.approx(220.0)
    assert rocket.stage_2.design_mach == pytest.approx(2.5)
    assert rocket.body.length_m / rocket.body.diameter_m >= 5.0


def test_negative_aspect_ratio_rejected() -> None:
    """aspect_ratio <= 0 must raise a ValidationError."""
    with pytest.raises(ValidationError):
        WingConfig(
            aspect_ratio=-2.0,
            sweep_deg=5.0,
            taper_ratio=0.7,
            span_m=2.5,
            airfoil_root="NACA2412",
            airfoil_tip="NACA2412",
        )


def test_sweep_out_of_range_rejected() -> None:
    """sweep_deg outside -10..70 must raise a ValidationError."""
    bad = dict(VALID_UAV["wing"], sweep_deg=80.0)
    with pytest.raises(ValidationError):
        WingConfig.model_validate(bad)


def test_yaml_round_trip(tmp_path: Path) -> None:
    """schema -> YAML -> schema preserves every field."""
    original = UAVConfig.model_validate(VALID_UAV)
    yaml_path = tmp_path / "uav.yaml"
    original.to_yaml(yaml_path)
    restored = BaseVehicleConfig.from_yaml(yaml_path)
    assert isinstance(restored, UAVConfig)
    assert restored == original


def test_from_yaml_gtm140_repo_config() -> None:
    """Integration: the committed GTM-140 config loads and validates."""
    path = REPO_ROOT / "vehicles" / "gtm140_drone" / "vehicle_config.yaml"
    uav = BaseVehicleConfig.from_yaml(path)
    assert isinstance(uav, UAVConfig)
    assert uav.name == "MELprop-GTM140-Drone"
    assert uav.propulsion.name == "GTM-140"


def test_from_yaml_ramjet_repo_config() -> None:
    """Integration: the committed ramjet rocket config loads and validates."""
    path = REPO_ROOT / "vehicles" / "ramjet_rocket" / "vehicle_config.yaml"
    rocket = BaseVehicleConfig.from_yaml(path)
    assert isinstance(rocket, RocketConfig)
    assert rocket.fins.count == 4


def test_inconsistent_solid_rocket_thrust_rejected() -> None:
    """thrust_N wildly inconsistent with mdot*Isp*g0 must be rejected."""
    bad = dict(VALID_ROCKET["stage_1"], thrust_N=500000.0)
    with pytest.raises(ValidationError):
        RocketConfig.model_validate(dict(VALID_ROCKET, stage_1=bad))
