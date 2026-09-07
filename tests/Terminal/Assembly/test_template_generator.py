"""Tests for Terminal.Assembly.template_generator.

Verifies pre-filling components from schema examples, assembly of vehicle configurations,
and generation of vehicle TOML templates.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from Terminal.Assembly import VehicleTemplateGenerator
from YAADO_Core.ComponentStore import (
    AERO_COMPONENTS,
    ALL_COMPONENTS,
    BODY_COMPONENTS,
    PROPULSION_COMPONENTS,
    ControlSurface,
    MassProperties,
)
from YAADO_Core.Foundation import BaseVehicleConfig


@pytest.mark.parametrize("comp_cls", ALL_COMPONENTS + (ControlSurface,))
def test_prefill_component_values_valid(comp_cls: type[BaseModel]) -> None:
    """Test that prefill_component_values instantiates every schema cleanly."""
    comp = VehicleTemplateGenerator.prefill_component_values(comp_cls)
    assert isinstance(comp, comp_cls)
    for field_name, field_info in comp_cls.model_fields.items():
        if field_name == "type":
            continue
        assert getattr(comp, field_name) is not None or field_info.examples[0] is None


@pytest.mark.parametrize("comp_cls", ALL_COMPONENTS + (ControlSurface,))
def test_get_field_example_all_components(comp_cls: type[BaseModel]) -> None:
    """Test that get_field_example correctly retrieves baseline examples for all registered schemas."""
    for field_name, field_info in comp_cls.model_fields.items():
        if field_name == "type":
            continue
        example = VehicleTemplateGenerator.get_field_example(comp_cls, field_name)
        if field_info.examples:
            assert example == field_info.examples[0]


def test_get_field_example_unknown_field_raises_key_error() -> None:
    """Test that get_field_example raises KeyError when querying an unrecognised field."""
    with pytest.raises(KeyError, match="Field 'nonexistent_param' not found"):
        VehicleTemplateGenerator.get_field_example(ALL_COMPONENTS[0], "nonexistent_param")


def test_get_field_example_missing_examples_raises_value_error() -> None:
    """Test that get_field_example raises ValueError when a field has no schema examples."""
    class IncompleteComponent(BaseModel):
        field_without_example: float

    with pytest.raises(ValueError, match="has no schema examples defined"):
        VehicleTemplateGenerator.get_field_example(IncompleteComponent, "field_without_example")


def test_assemble_vehicle_subsystem_routing() -> None:
    """Test that assemble_vehicle routes components into their respective subsystems."""
    components = [VehicleTemplateGenerator.prefill_component_values(cls) for cls in ALL_COMPONENTS]
    vehicle = VehicleTemplateGenerator.assemble_vehicle("test_vehicle", components)

    assert isinstance(vehicle, BaseVehicleConfig)
    assert vehicle.name == "test_vehicle"

    for comp in components:
        if isinstance(comp, AERO_COMPONENTS):
            assert comp in vehicle.aero_surfaces.values()
        elif isinstance(comp, BODY_COMPONENTS):
            assert comp in vehicle.bodies.values()
        elif isinstance(comp, PROPULSION_COMPONENTS):
            assert comp in vehicle.propulsion.values()
        elif isinstance(comp, MassProperties):
            assert vehicle.mass_properties == comp


def test_assemble_vehicle_unrecognized_component_raises_type_error() -> None:
    """Test that assemble_vehicle rejects unsupported object instances."""
    class CustomFakeComponent(BaseModel):
        val: int = 1

    with pytest.raises(TypeError, match="Unknown component"):
        VehicleTemplateGenerator.assemble_vehicle("invalid", [CustomFakeComponent()])


def test_generate_template_prefilled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test generating a pre-filled, simulation-ready vehicle template TOML file."""
    monkeypatch.chdir(tmp_path)

    classes = list(ALL_COMPONENTS)
    VehicleTemplateGenerator.generate_template("demo_vehicle", classes, pre_filled=True)

    out_file = tmp_path / "Hangar" / "demo_vehicle" / "demo_vehicle.toml"
    assert out_file.exists()

    loaded = BaseVehicleConfig.from_toml(out_file)
    assert loaded.name == "demo_vehicle"
    total_loaded = (
        len(loaded.bodies)
        + len(loaded.aero_surfaces)
        + len(loaded.propulsion)
        + (1 if loaded.mass_properties else 0)
    )
    assert total_loaded == len(classes)


def test_generate_template_skeleton(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test generating an unpopulated blueprint skeleton."""
    monkeypatch.chdir(tmp_path)

    classes = list(ALL_COMPONENTS)
    VehicleTemplateGenerator.generate_template("skeleton_vehicle", classes, pre_filled=False)

    out_file = tmp_path / "Hangar" / "skeleton_vehicle" / "skeleton_vehicle.toml"
    assert out_file.exists()
    assert len(out_file.read_text(encoding="utf-8")) > 0
