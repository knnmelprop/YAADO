"""Tests for Hangar reference example vehicle TOML configurations.

Verifies that all vehicle files in Hangar/examples/ (e.g. AGM-84 Harpoon and ALVRJ)
parse and validate cleanly using BaseVehicleConfig, and can round-trip through serialization.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig


def get_hangar_example_toml_paths() -> list[Path]:
    """Retrieve all TOML file paths in Hangar/examples."""
    hangar_dir = Path("Hangar") / "examples"
    if not hangar_dir.exists():
        return []
    return sorted(hangar_dir.glob("*/*.toml"))


def test_hangar_has_example_configs() -> None:
    """Verify that Hangar/examples contains at least one reference vehicle."""
    assert len(get_hangar_example_toml_paths()) > 0


@pytest.mark.parametrize("toml_path", get_hangar_example_toml_paths(), ids=lambda p: p.name)
def test_hangar_example_loads_successfully(toml_path: Path) -> None:
    """Test that each Hangar reference vehicle parses and validates cleanly."""
    config = BaseVehicleConfig.from_toml(toml_path)
    assert isinstance(config, BaseVehicleConfig)
    assert len(config.name) > 0
    total_components = len(config.bodies) + len(config.aero_surfaces) + len(config.propulsion)
    assert total_components > 0
    if config.mass_properties is not None:
        assert config.mass_properties.total_mass is not None
        assert config.mass_properties.total_mass > 0.0


@pytest.mark.parametrize("toml_path", get_hangar_example_toml_paths(), ids=lambda p: p.name)
def test_hangar_example_roundtrip_serialization(toml_path: Path, tmp_path: Path) -> None:
    """Test that saving and re-loading a reference vehicle produces identical configuration data."""
    original = BaseVehicleConfig.from_toml(toml_path)
    temp_toml = tmp_path / f"copy_{toml_path.name}"
    original.to_toml(temp_toml)

    reloaded = BaseVehicleConfig.from_toml(temp_toml)
    assert original.model_dump() == reloaded.model_dump()
