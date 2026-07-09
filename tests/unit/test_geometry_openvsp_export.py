# MELprop-IADE | tests.unit.test_geometry_openvsp_export | v0.1.0
"""Unit tests for analyses.geometry.openvsp_export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analyses.geometry.openvsp_export import (
    MANIFEST_FILENAME,
    SCRIPT_FILENAME,
    OpenVSPExporter,
    load_rocket_config,
    write_openvsp_export,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
VEHICLE_CONFIG_PATH = (
    REPO_ROOT / "vehicles" / "ramjet_rocket" / "vehicle_config.yaml"
)


@pytest.fixture()
def rocket_config():
    return load_rocket_config(VEHICLE_CONFIG_PATH)


def test_script_generated_contains_fuselage_and_wing_with_yaml_span(
    tmp_path, rocket_config
):
    """Script must contain AddGeom FUSELAGE and WING and the YAML fin span."""
    script_path, _manifest_path = write_openvsp_export(
        rocket_config, output_dir=tmp_path
    )
    assert script_path.is_file()
    text = script_path.read_text(encoding="utf-8")
    assert 'AddGeom( "FUSELAGE"' in text
    assert 'AddGeom( "WING"' in text
    expected_span_str = f"{rocket_config.fins.span_m:.6f}"
    assert expected_span_str in text
    # HR-1 review note must be embedded in the script comments.
    assert "HUMAN_REVIEW (HR-1)" in text
    assert "HR-1" in text


def test_manifest_json_valid_with_required_keys(tmp_path, rocket_config):
    """Manifest must be valid JSON with the documented required keys."""
    script_path, manifest_path = write_openvsp_export(
        rocket_config, output_dir=tmp_path
    )
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    required_keys = {
        "script_path",
        "vehicle_name",
        "generated_at_utc",
        "geometry_m",
        "human_review",
        "to_run",
        "note",
    }
    assert required_keys.issubset(manifest.keys())
    assert manifest["script_path"] == str(script_path)
    assert manifest["geometry_m"]["fin_span_m"] == rocket_config.fins.span_m
    assert "vsp -script" in manifest["to_run"]
    assert "HR-1" in manifest["human_review"]


def test_idempotent_regeneration_overwrites_cleanly(tmp_path, rocket_config):
    """Regenerating into the same output_dir overwrites both files cleanly."""
    script_path_1, manifest_path_1 = write_openvsp_export(
        rocket_config, output_dir=tmp_path
    )
    text_1 = script_path_1.read_text(encoding="utf-8")

    script_path_2, manifest_path_2 = write_openvsp_export(
        rocket_config, output_dir=tmp_path
    )
    text_2 = script_path_2.read_text(encoding="utf-8")

    assert script_path_1 == script_path_2
    assert manifest_path_1 == manifest_path_2
    # Script content is deterministic (byte-identical) across regeneration.
    assert text_1 == text_2
    # No stray duplicate files were left behind.
    vspscripts = list(tmp_path.glob("*.vspscript"))
    manifests = list(tmp_path.glob("*_manifest.json"))
    assert len(vspscripts) == 1
    assert len(manifests) == 1
    assert vspscripts[0].name == SCRIPT_FILENAME
    assert manifests[0].name == MANIFEST_FILENAME


def test_execute_before_setup_raises_runtime_error():
    """Calling execute() before setup() must raise RuntimeError."""
    analysis = OpenVSPExporter()
    with pytest.raises(RuntimeError):
        analysis.execute()


def test_setup_rejects_config_missing_body_or_fins():
    """setup() must reject a config object lacking body/fins attributes."""

    class _FakeConfig:
        body = None
        fins = None

    analysis = OpenVSPExporter()
    with pytest.raises(ValueError):
        analysis.setup(_FakeConfig())


def test_full_analysis_roundtrip_via_baseanalysis_interface(tmp_path, rocket_config):
    """setup() -> execute() -> validate_results() full BaseAnalysis contract."""
    analysis = OpenVSPExporter()
    analysis.setup(rocket_config, output_dir=tmp_path)
    results = analysis.execute()

    assert results.data["n_files"] == 2.0
    assert analysis.validate_results(results)
    assert Path(results.metadata["script_path"]).is_file()
    assert Path(results.metadata["manifest_path"]).is_file()
