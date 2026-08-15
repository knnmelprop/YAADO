# MELprop-IADE | tests.unit.test_schemas | v0.1.0
"""Unit tests for src.schemas.vehicle_schema."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from IADE_Core.Inspectors.vehicle_schema import (
    BaseVehicleConfig,
    RamjetConfig,
    RocketConfig,
    UAVConfig,
    WingConfig,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

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
        "mass_flow_kg_per_s": 0.35,
        "compression_ratio": 2.8,
        "egt_K": 973.15,
        "diameter_m": 0.110,
        "length_m": 0.265,
        "max_rpm": 120000.0,
    },
}

VALID_ROCKET = {
    "name": "TestRocket",
    "vehicle_type": "Rocket",
    "description": "unit-test rocket",
    "stage_1": {
        "type": "solid_rocket",
        "geometry": {
            "assembly_diameter_m": 0.250,
            "assembly_diameter_body_m": 0.250,
            "assembly_diameter_bbox_m": 1.809,
            "wings_halfspan_est_m": 0.780,
        },
        "propulsion": {
            "isp_vacuum_s": 230.0,
            "isp_sl_s": 207.0,
            "thrust_peak_N": 29000.0,
            "thrust_mean_N": 25375.0,
            "burn_time_s": 6.0,
            "propellant_mass_kg": 75.0,
            "propellant_density_kg_m3": 1750.0,
            "note": "estimate",
        },
    },
    "stage_2": {
        "type": "ramjet",
        "design_mach": 2.5,
        "fuel_type": "kerosene",
        "combustor_temp_K": 2000.0,
        "nozzle_area_ratio": 4.0,
    },
    "body": {"length_m": 4.084, "diameter_m": 0.250, "nose_type": "conical"},
    "fins": {"count": 4, "span_m": 0.6685, "sweep_deg": 0.0},
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
    assert rocket.stage_1.propulsion.isp_vacuum_s == pytest.approx(230.0)
    assert rocket.stage_1.geometry.assembly_diameter_m == pytest.approx(0.250)
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
    path = REPO_ROOT / "Hangar" / "gtm140_drone" / "vehicle_config.yaml"
    uav = BaseVehicleConfig.from_yaml(path)
    assert isinstance(uav, UAVConfig)
    assert uav.name == "MELprop-GTM140-Drone"
    assert uav.propulsion.name == "GTM-140"


def test_from_yaml_ramjet_repo_config() -> None:
    """Integration: the committed ramjet rocket config loads and validates."""
    path = REPO_ROOT / "Hangar" / "ramjet_rocket" / "vehicle_config.yaml"
    rocket = BaseVehicleConfig.from_yaml(path)
    assert isinstance(rocket, RocketConfig)
    assert rocket.fins.count == 4


def test_ramjet_repo_config_nozzle_diameters_from_drawing() -> None:
    """Committed config's nozzle throat/exit diameters and area_ratio match
    the "CFD Simplified Single Rocket Model" drawing (Aleks Czernicki,
    2026-07-10): throat 0.210 m, exit 0.241 m, area_ratio = (241/210)**2.
    """
    path = REPO_ROOT / "Hangar" / "ramjet_rocket" / "vehicle_config.yaml"
    rocket = BaseVehicleConfig.from_yaml(path)
    assert rocket.stage_2.nozzle_throat_diameter_m == pytest.approx(0.210)
    assert rocket.stage_2.nozzle_exit_diameter_m == pytest.approx(0.241)
    assert rocket.stage_2.nozzle_area_ratio == pytest.approx(
        (0.241 / 0.210) ** 2, rel=1e-3
    )


def test_ramjet_nozzle_diameters_consistent_with_area_ratio() -> None:
    """Throat/exit diameters implying the same area_ratio validate fine."""
    ramjet = RamjetConfig(
        design_mach=2.5,
        fuel_type="kerosene",
        combustor_temp_K=2000.0,
        nozzle_area_ratio=1.317,
        nozzle_throat_diameter_m=0.210,
        nozzle_exit_diameter_m=0.241,
    )
    assert ramjet.nozzle_throat_diameter_m == pytest.approx(0.210)


def test_ramjet_nozzle_diameters_inconsistent_with_area_ratio_rejected() -> None:
    """Throat/exit diameters implying a different area_ratio are rejected."""
    with pytest.raises(ValidationError):
        RamjetConfig(
            design_mach=2.5,
            fuel_type="kerosene",
            combustor_temp_K=2000.0,
            nozzle_area_ratio=4.0,
            nozzle_throat_diameter_m=0.210,
            nozzle_exit_diameter_m=0.241,
        )


def test_inconsistent_solid_rocket_thrust_rejected() -> None:
    """SolidRocketConfig thrust_N inconsistent with mdot*Isp*g0 is rejected.

    The standalone SolidRocketConfig retains the thrust-consistency
    cross-check used as a unit-mistake guard for flat motor definitions.
    """
    from IADE_Core.Inspectors.vehicle_schema import SolidRocketConfig

    with pytest.raises(ValidationError):
        SolidRocketConfig(
            isp_s=220.0,
            propellant_mass_kg=15.0,
            burn_time_s=5.0,
            thrust_N=500000.0,
        )


def test_solid_rocket_propulsion_peak_below_mean_rejected() -> None:
    """SolidRocketPropulsion rejects thrust_peak_N < thrust_mean_N.

    Regression for the resolved stage-1 inconsistency: a listed
    thrust_peak_N=12000 was below the impulse-consistent mean of
    ~25.4 kN, which is physically impossible (peak >= mean always).
    """
    from IADE_Core.Inspectors.vehicle_schema import SolidRocketPropulsion

    base = dict(VALID_ROCKET["stage_1"]["propulsion"])
    base["thrust_peak_N"] = 12000.0
    with pytest.raises(ValidationError):
        SolidRocketPropulsion.model_validate(base)


def test_solid_rocket_propulsion_mean_inconsistent_with_isp_rejected() -> None:
    """SolidRocketPropulsion rejects thrust_mean_N far from Isp*mdot*g0."""
    from IADE_Core.Inspectors.vehicle_schema import SolidRocketPropulsion

    base = dict(VALID_ROCKET["stage_1"]["propulsion"])
    base["thrust_peak_N"] = 500000.0
    base["thrust_mean_N"] = 500000.0
    with pytest.raises(ValidationError):
        SolidRocketPropulsion.model_validate(base)


def test_solid_rocket_propulsion_valid_peak_and_mean() -> None:
    """A physically consistent peak/mean pair validates and exposes both."""
    from IADE_Core.Inspectors.vehicle_schema import SolidRocketPropulsion

    propulsion = SolidRocketPropulsion.model_validate(
        VALID_ROCKET["stage_1"]["propulsion"]
    )
    assert propulsion.thrust_peak_N >= propulsion.thrust_mean_N
    assert propulsion.total_impulse_Ns == pytest.approx(
        propulsion.thrust_mean_N * propulsion.burn_time_s
    )
