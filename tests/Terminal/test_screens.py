"""Tests for Terminal screen components and presentation mappings.

Verifies that all registered vehicle components have their declared HEADLINE_FIELDS
fully covered by FIELD_SYMBOLS in Terminal.screens.hangar so that UI parameter
summaries remain concise, complete, and strictly typed.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from Terminal.Assembly import VehicleTemplateGenerator
from Terminal.screens.hangar import (
    FIELD_SYMBOLS,
    HangarView,
    _abbreviate_field,
    _format_compact_value_and_unit,
)
from YAADO_Core.ComponentStore import ALL_COMPONENTS


@pytest.mark.parametrize("comp_cls", ALL_COMPONENTS)
def test_all_component_headline_fields_covered_by_field_symbols(
    comp_cls: type[BaseModel],
) -> None:
    """Verify that every headline field of every component is mapped in FIELD_SYMBOLS.

    If a developer introduces a new component or adds new headline fields without
    providing a canonical aerospace symbol or abbreviation in FIELD_SYMBOLS,
    this test will fail.
    """
    assert hasattr(comp_cls, "HEADLINE_FIELDS"), f"{comp_cls.__name__} missing HEADLINE_FIELDS ClassVar"
    headline_fields = getattr(comp_cls, "HEADLINE_FIELDS")  # noqa: B009
    assert isinstance(headline_fields, tuple), f"{comp_cls.__name__}.HEADLINE_FIELDS must be a tuple"
    assert len(headline_fields) > 0, f"{comp_cls.__name__}.HEADLINE_FIELDS must not be empty"

    uncovered_fields = [f for f in headline_fields if f not in FIELD_SYMBOLS]
    assert not uncovered_fields, (
        f"{comp_cls.__name__} headline field(s) {uncovered_fields} not covered by "
        f"Terminal.screens.hangar.FIELD_SYMBOLS. Add canonical aerospace symbols to FIELD_SYMBOLS."
    )


def test_uncovered_headline_field_fails_contract() -> None:
    """Simulate a component schema with an unmapped headline field to verify contract enforcement."""
    from typing import ClassVar

    class DummyComponent(BaseModel):
        HEADLINE_FIELDS: ClassVar[tuple[str, ...]] = ("unmapped_propulsion_parameter",)

    headline_fields = getattr(DummyComponent, "HEADLINE_FIELDS")  # noqa: B009
    uncovered = [f for f in headline_fields if f not in FIELD_SYMBOLS]
    assert "unmapped_propulsion_parameter" in uncovered


@pytest.mark.parametrize("comp_cls", ALL_COMPONENTS)
def test_format_headline_specs_renders_for_all_components(
    comp_cls: type[BaseModel],
) -> None:
    """Verify that _format_headline_specs renders non-empty compact badges for all components."""
    hangar = HangarView()
    comp_instance = VehicleTemplateGenerator.prefill_component_values(comp_cls)
    specs_str = hangar._format_headline_specs(comp_instance)

    # All components define headline fields, so prefilled instance specs must not be empty
    assert specs_str != "", f"Empty specs string for prefilled {comp_cls.__name__}"

    # Verify that the mapped symbol for each headline field (except 'name') is present
    headline_fields = getattr(comp_cls, "HEADLINE_FIELDS")  # noqa: B009
    for f in headline_fields:
        if f == "name":
            continue
        sym = FIELD_SYMBOLS[f]
        assert f"{sym}=" in specs_str, f"Symbol '{sym}=' not found in rendered specs: '{specs_str}'"


def test_compact_value_and_unit_formatting() -> None:
    """Verify unit scaling and compact representation logic."""
    # Force scaling
    val, unit = _format_compact_value_and_unit(53000.0, "N")
    assert val == "53"
    assert unit == "kN"

    val_mn, unit_mn = _format_compact_value_and_unit(1500000.0, "N")
    assert val_mn == "1.5"
    assert unit_mn == "MN"

    # Angle scaling
    val_deg, unit_deg = _format_compact_value_and_unit(45.0, "deg")
    assert val_deg == "45"
    assert unit_deg == "°"

    # Pressure scaling
    val_p, unit_p = _format_compact_value_and_unit(101325.0, "Pa")
    assert val_p == "101.33"
    assert unit_p == "kPa"

    # Non-numeric fallback
    val_str, unit_str = _format_compact_value_and_unit("kerosene", "")
    assert val_str == "kerosene"
    assert unit_str == ""


def test_abbreviate_field_fallback() -> None:
    """Verify fallback behavior for fields not in FIELD_SYMBOLS."""
    assert _abbreviate_field("length") == "L"
    assert _abbreviate_field("custom_thrust_coefficient") == "CTC"
    assert _abbreviate_field("temperature") == "temp"
