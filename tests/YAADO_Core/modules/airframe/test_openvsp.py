"""Tests for the OpenVSP script and manifest geometry builders."""

from pathlib import Path

import pytest

from YAADO_Core.ComponentStore.aero_surfaces import Fins
from YAADO_Core.ComponentStore.body import AxisymmetricBody
from YAADO_Core.modules.airframe.generator_methods.openvsp import (
    _VehicleGeometryAdapter,
    build_manifest,
    build_vspscript,
)


@pytest.fixture
def geometry() -> _VehicleGeometryAdapter:
    """Build representative body and fin components using the public models."""
    body = AxisymmetricBody(
        length=4.0,
        diameter=0.3,
        nose_type="conical",
        nose_length=0.8,
        nose_diameter=0.3,
        total_length=4.2,
    )
    fins = Fins(
        count=4,
        span=0.5,
        sweep=25.0,
        chord_root=0.7,
        chord_tip=0.2,
    )
    return _VehicleGeometryAdapter(name="test_vehicle", body=body, fins=fins)


def test_build_vspscript_uses_component_geometry(geometry: _VehicleGeometryAdapter) -> None:
    """The generated script contains dimensions from the supplied components."""
    script = build_vspscript(geometry)

    assert "vehicle='test_vehicle'" in script
    assert "body.total_length_m   = 4.2000" in script
    assert "body.length_m (cyl.)  = 4.0000" in script
    assert "body.diameter_m       = 0.3000" in script
    assert "body.nose_length_m    = 0.8000" in script
    assert "fins.span_m           = 0.5000" in script
    assert "fins.chord_root_m     = 0.7000" in script
    assert "fins.chord_tip_m      = 0.2000" in script
    assert "fins.sweep_deg        = 25.00" in script


def test_build_manifest_uses_same_resolved_geometry(
    geometry: _VehicleGeometryAdapter,
) -> None:
    """The manifest records the same resolved dimensions used by the script."""
    manifest = build_manifest(geometry, Path("vehicle.vspscript"))

    assert manifest["geometry_m"] == {
        "body_total_length_m": 4.2,
        "body_length_m": 4.0,
        "body_diameter_m": 0.3,
        "body_nose_length_m": 0.8,
        "body_nose_diameter_m": 0.3,
        "body_nose_type": "conical",
        "fin_count": 4,
        "fin_span_m": 0.5,
        "fin_chord_root_m": 0.7,
        "fin_chord_tip_m": 0.2,
        "fin_sweep_deg": 25.0,
    }
    assert manifest["human_review"]["value_m"] == 0.5
