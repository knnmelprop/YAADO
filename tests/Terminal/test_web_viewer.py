"""Tests for the static web vehicle viewer in ``Terminal/web_viewer/``."""

from __future__ import annotations

from pathlib import Path

from YAADO_Core.ComponentStore import AxisymmetricBody
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig

VIEWER_DIR = Path("Terminal") / "web_viewer"


def test_sample_vehicle_json_matches_schemas() -> None:
    """The sample vehicle must validate, so the viewer sample stays in sync with the schemas."""
    text = (VIEWER_DIR / "sample_vehicle.json").read_text(encoding="utf-8")
    config = BaseVehicleConfig.model_validate_json(text)
    assert config.name
    assert config.get_components_by_type(AxisymmetricBody)


def test_viewer_files_exist() -> None:
    """The page, its script and the README ship together."""
    for name in ("index.html", "viewer.js", "README.md"):
        assert (VIEWER_DIR / name).is_file()
