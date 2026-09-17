"""Tests for :mod:`YAADO_Core.Foundation.vehicle_factory`."""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import YAADO_Core.modules.suave_compat  # noqa: F401

# isort: split
import SUAVE

from YAADO_Core.ComponentStore import AxisymmetricBody, TurbojetEngine, Wings
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.Foundation.vehicle_factory import VehicleFactory

REPO_ROOT = Path(__file__).resolve().parents[3]
HARPOON_TOML = REPO_ROOT / "Hangar" / "examples" / "AGM-84_HARPOON" / "AGM-84_HARPOON.toml"
ALVRJ_TOML = REPO_ROOT / "Hangar" / "examples" / "ALVRJ" / "ALVRJ.toml"


def make_generic_vehicle_config() -> BaseVehicleConfig:
    """Build a minimal valid vehicle config with wing, engine, and fuselage."""
    wing = Wings(
        aspect_ratio=8.0,
        sweep=5.0,
        taper_ratio=0.5,
        span=10.0,
        dihedral=3.0,
        airfoil_root="NACA2412",
    )
    engine = TurbojetEngine(
        name="generic-turbojet",
        thrust=5000.0,
        sfc=2.0e-5,
        mach_range=(0.0, 0.9),
    )
    body = AxisymmetricBody(
        length=6.0,
        diameter=0.5,
    )
    return BaseVehicleConfig(
        name="generic-test-vehicle",
        propulsion={"main_engine": engine},
        aero_surfaces={"main_wing": wing},
        bodies={"fuselage": body},
    )


def test_build_generic_vehicle() -> None:
    """VehicleFactory.build() should translate wing, propulsion, and fuselage into SUAVE."""
    factory = VehicleFactory()
    config = make_generic_vehicle_config()

    result = factory.build(config)

    assert result.tag == "generic-test-vehicle"

    assert "main_wing" in result.wings
    wing = result.wings["main_wing"]
    assert wing.aspect_ratio == pytest.approx(8.0)
    assert wing.spans.projected == pytest.approx(10.0)
    assert wing.sweeps.quarter_chord == pytest.approx(math.radians(5.0))
    assert wing.taper == pytest.approx(0.5)

    assert "main_engine" in result.networks
    engine = result.networks["main_engine"]
    assert isinstance(engine, SUAVE.Components.Energy.Networks.Turbojet_Super)
    assert engine.thrust_N == pytest.approx(5000.0)
    assert engine.sfc_kg_per_Ns == pytest.approx(2.0e-5)

    assert "fuselage" in result.fuselages
    fuse = result.fuselages["fuselage"]
    assert isinstance(fuse, SUAVE.Components.Fuselages.Fuselage)
    assert fuse.lengths.total == pytest.approx(6.0)
    assert fuse.width == pytest.approx(0.5)
    assert fuse.heights.maximum == pytest.approx(0.5)


def test_build_agm84_harpoon() -> None:
    """Build Harpoon missile from real TOML reference configuration."""
    assert HARPOON_TOML.is_file(), f"Harpoon TOML not found at {HARPOON_TOML}"
    config = BaseVehicleConfig.from_toml(HARPOON_TOML)

    factory = VehicleFactory()
    suave_vehicle = factory.build(config)

    assert suave_vehicle.tag == "AGM-84_HARPOON"

    # Propulsion networks: turbojet sustainer + solid rocket booster
    assert "sustainer" in suave_vehicle.networks
    assert "launch_booster" in suave_vehicle.networks
    sustainer = suave_vehicle.networks["sustainer"]
    booster = suave_vehicle.networks["launch_booster"]

    assert isinstance(sustainer, SUAVE.Components.Energy.Networks.Turbojet_Super)
    assert sustainer.thrust_N == pytest.approx(2940.0)
    assert sustainer.sfc_kg_per_Ns == pytest.approx(3.25e-5)

    assert isinstance(booster, SUAVE.Components.Energy.Networks.Network)
    assert booster.thrust_N == pytest.approx(53000.0)
    assert booster.isp_s == pytest.approx(230.0)
    assert booster.burn_time_s == pytest.approx(2.9)

    # Aero surfaces: mid-body fins, aft control fins, planar equivalent wing
    assert "mid_body_wings" in suave_vehicle.wings
    assert "aft_control_fins" in suave_vehicle.wings
    assert "planar_equivalent" in suave_vehicle.wings

    mid_fins = suave_vehicle.wings["mid_body_wings"]
    assert mid_fins.vertical is True
    assert mid_fins.spans.projected == pytest.approx(0.285)

    planar_wing = suave_vehicle.wings["planar_equivalent"]
    assert planar_wing.aspect_ratio == pytest.approx(2.3)
    assert planar_wing.spans.projected == pytest.approx(0.914)

    # Body
    assert "fuselage" in suave_vehicle.fuselages
    fuse = suave_vehicle.fuselages["fuselage"]
    assert fuse.lengths.total == pytest.approx(3.84)
    assert fuse.width == pytest.approx(0.343)


def test_build_alvrj() -> None:
    """Build ALVRJ ramjet missile from real TOML reference configuration."""
    assert ALVRJ_TOML.is_file(), f"ALVRJ TOML not found at {ALVRJ_TOML}"
    config = BaseVehicleConfig.from_toml(ALVRJ_TOML)

    factory = VehicleFactory()
    suave_vehicle = factory.build(config)

    assert suave_vehicle.tag == "ALVRJ"

    # Propulsion networks: ramjet sustainer + solid integral booster
    assert "sustainer" in suave_vehicle.networks
    assert "integral_booster" in suave_vehicle.networks

    sustainer = suave_vehicle.networks["sustainer"]
    assert isinstance(sustainer, SUAVE.Components.Energy.Networks.Ramjet)
    assert sustainer.design_mach == pytest.approx(2.6)
    assert sustainer.combustor_temp_K == pytest.approx(2150.0)
    assert sustainer.nozzle_area_ratio == pytest.approx(2.25)

    booster = suave_vehicle.networks["integral_booster"]
    assert isinstance(booster, SUAVE.Components.Energy.Networks.Network)
    assert booster.thrust_N == pytest.approx(125000.0)
    assert booster.isp_s == pytest.approx(235.0)
    assert booster.burn_time_s == pytest.approx(5.0)

    # Aero surfaces: aft control fins + intake strakes (wing)
    assert "aft_control_fins" in suave_vehicle.wings
    assert "intake_strakes" in suave_vehicle.wings

    strakes = suave_vehicle.wings["intake_strakes"]
    assert strakes.aspect_ratio == pytest.approx(1.8)
    assert strakes.spans.projected == pytest.approx(0.94)

    # Body
    assert "fuselage" in suave_vehicle.fuselages
    fuse = suave_vehicle.fuselages["fuselage"]
    assert fuse.lengths.total == pytest.approx(4.57)
    assert fuse.width == pytest.approx(0.381)


def test_unsupported_propulsion_type_raises_type_error() -> None:
    """Unknown propulsion component types must raise TypeError."""
    factory = VehicleFactory()
    fake_comp = SimpleNamespace(type="nuclear_reactor")

    with pytest.raises(TypeError, match="No SUAVE translation known for propulsion"):
        factory._translate_propulsion(fake_comp, tag="reactor")  # type: ignore[arg-type]


def test_unsupported_aero_type_raises_type_error() -> None:
    """Unknown aero surface component types must raise TypeError."""
    factory = VehicleFactory()
    fake_comp = SimpleNamespace(type="solar_sail")

    with pytest.raises(TypeError, match="No SUAVE translation known for aero"):
        factory._translate_aero_surface(fake_comp, tag="sail")  # type: ignore[arg-type]


def test_unsupported_body_type_raises_type_error() -> None:
    """Unknown body component types must raise TypeError."""
    factory = VehicleFactory()
    fake_comp = SimpleNamespace(type="flying_saucer")

    with pytest.raises(TypeError, match="No SUAVE translation known for body"):
        factory._translate_body(fake_comp, tag="saucer")  # type: ignore[arg-type]
