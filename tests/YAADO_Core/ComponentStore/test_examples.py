"""Tests for schema examples validity in ComponentStore.

Verifies that all components provide valid, self-consistent baseline examples
and that nested subcomponents (mass, control surfaces) validate cleanly into their models.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from YAADO_Core.ComponentStore import (
    AERO_COMPONENTS,
    ALL_COMPONENTS,
    BODY_COMPONENTS,
    PROPULSION_COMPONENTS,
    ControlSurface,
    MassProperties,
)


def test_component_store_registries_invariants() -> None:
    """Verify registry consistency without hardcoding specific component lists."""
    # 1. ALL_COMPONENTS is the union of all subsystem categories + MassProperties
    expected_all = (MassProperties,) + AERO_COMPONENTS + BODY_COMPONENTS + PROPULSION_COMPONENTS
    assert ALL_COMPONENTS == expected_all

    # 2. No duplicate components across categories
    assert len(set(ALL_COMPONENTS)) == len(ALL_COMPONENTS)

    # 3. Every registered component is a BaseModel with a discriminator 'type'
    for comp_cls in ALL_COMPONENTS:
        assert issubclass(comp_cls, BaseModel)
        assert "type" in comp_cls.model_fields


@pytest.mark.parametrize("comp_cls", ALL_COMPONENTS + (ControlSurface,))
def test_all_fields_have_examples(comp_cls: type[BaseModel]) -> None:
    """Every non-type field must define a non-empty examples list."""
    for field_name, field_info in comp_cls.model_fields.items():
        if field_name == "type":
            continue
        assert field_info.examples is not None, f"{comp_cls.__name__}.{field_name} missing examples attribute"
        assert len(field_info.examples) > 0, f"{comp_cls.__name__}.{field_name} has empty examples list"


@pytest.mark.parametrize("comp_cls", ALL_COMPONENTS + (ControlSurface,))
def test_schema_examples_produce_valid_instance(comp_cls: type[BaseModel]) -> None:
    """Instantiating a component with its schema examples must pass validation."""
    kwargs = {
        name: info.examples[0]
        for name, info in comp_cls.model_fields.items()
        if name != "type"
    }
    instance = comp_cls(**kwargs)
    assert isinstance(instance, comp_cls)


def test_nested_mass_properties_examples_are_typed() -> None:
    """Any component defining a 'mass' field must resolve its example to a MassProperties instance."""
    models_with_mass = [cls for cls in ALL_COMPONENTS if "mass" in cls.model_fields]
    assert len(models_with_mass) > 0

    for comp_cls in models_with_mass:
        kwargs = {
            name: info.examples[0]
            for name, info in comp_cls.model_fields.items()
            if name != "type"
        }
        instance = comp_cls(**kwargs)
        mass_obj = getattr(instance, "mass")
        assert mass_obj is not None, f"{comp_cls.__name__}.mass should have a prefilled example"
        assert isinstance(mass_obj, MassProperties), f"{comp_cls.__name__}.mass must be a MassProperties instance"
        assert mass_obj.total_mass_kg is not None
        assert mass_obj.total_mass_kg > 0.0


def test_nested_control_surfaces_examples_are_typed() -> None:
    """Any component with control surfaces in its examples must resolve to ControlSurface instances."""
    models_with_controls = [cls for cls in ALL_COMPONENTS if "control_surfaces" in cls.model_fields]
    assert len(models_with_controls) > 0

    for comp_cls in models_with_controls:
        kwargs = {
            name: info.examples[0]
            for name, info in comp_cls.model_fields.items()
            if name != "type"
        }
        instance = comp_cls(**kwargs)
        for cs in instance.control_surfaces:
            assert isinstance(cs, ControlSurface)

