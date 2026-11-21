"""Tests for the OpenVSP exporter, script builder and manifest builder."""

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from YAADO_Core.ComponentStore import MassProperties
from YAADO_Core.ComponentStore.aero_surfaces import Fins
from YAADO_Core.ComponentStore.body import AxisymmetricBody
from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.airframe.containers import (
    OpenVSPExportResults,
    OpenVSPGeometry,
)
from YAADO_Core.modules.airframe.generator_methods.openvsp import (
    OpenVSPExporter,
    build_manifest,
    build_vspscript,
    resolve_geometry,
)

HARPOON_TOML = (
    Path(__file__).resolve().parents[4]
    / "Hangar"
    / "examples"
    / "AGM-84_HARPOON"
    / "AGM-84_HARPOON.toml"
)


def _vehicle(nose_type: str = "conical") -> BaseVehicleConfig:
    """Build a small valid vehicle with one body and one fin set."""
    return BaseVehicleConfig(
        name="test_vehicle",
        bodies={
            "body": AxisymmetricBody(
                length=4.0,
                diameter=0.3,
                nose_type=nose_type,  # type: ignore[arg-type]
                nose_length=0.8,
                nose_diameter=0.3,
                total_length=4.2,
            )
        },
        aero_surfaces={
            "fins": Fins(count=4, span=0.5, sweep=25.0, chord_root=0.7, chord_tip=0.2)
        },
        mass_properties=MassProperties(cg_from_nose=2.0, total_mass=50.0),
    )


@pytest.fixture
def vehicle() -> BaseVehicleConfig:
    return _vehicle()


@pytest.fixture
def geometry(vehicle: BaseVehicleConfig) -> OpenVSPGeometry:
    return resolve_geometry(vehicle)


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep FlightLogger output out of the repository's FlightLogs/."""
    monkeypatch.chdir(tmp_path)


def test_resolve_geometry_reads_components(geometry: OpenVSPGeometry) -> None:
    assert geometry == OpenVSPGeometry(
        body_length=4.0,
        body_total_length=4.2,
        body_diameter=0.3,
        nose_length=0.8,
        nose_diameter=0.3,
        nose_type="conical",
        fin_count=4,
        fin_span=0.5,
        fin_chord_root=0.7,
        fin_chord_tip=0.2,
        fin_sweep=25.0,
    )


def test_resolve_geometry_rejects_non_conical_nose() -> None:
    with pytest.raises(ValueError, match="only 'conical'"):
        resolve_geometry(_vehicle(nose_type="ogive"))


def test_resolve_geometry_requires_fins() -> None:
    vehicle = replace_aero(_vehicle(), {})
    with pytest.raises(ValueError, match="no component matching"):
        resolve_geometry(vehicle)


def replace_aero(vehicle: BaseVehicleConfig, aero: dict) -> BaseVehicleConfig:  # type: ignore[type-arg]
    return vehicle.model_copy(update={"aero_surfaces": aero})


def test_resolve_geometry_real_toml_requires_fins_name() -> None:
    vehicle = BaseVehicleConfig.from_toml(HARPOON_TOML)
    with pytest.raises(ValueError, match="multiple components"):
        resolve_geometry(vehicle)
    # Explicit selection works; the ogive nose is then rejected clearly.
    with pytest.raises(ValueError, match="only 'conical'"):
        resolve_geometry(vehicle, fins_name="aft_control_fins")


def test_build_vspscript_uses_component_geometry(geometry: OpenVSPGeometry) -> None:
    script = build_vspscript(geometry, "test_vehicle")

    assert "vehicle='test_vehicle'" in script
    assert "body.total_length_m   = 4.2000" in script
    assert "body.length_m (cyl.)  = 4.0000" in script
    assert "body.diameter_m       = 0.3000" in script
    assert "body.nose_length_m    = 0.8000" in script
    assert "fins.span_m           = 0.5000" in script
    assert "fins.chord_root_m     = 0.7000" in script
    assert "fins.chord_tip_m      = 0.2000" in script
    assert "fins.sweep_deg        = 25.00" in script


def test_build_manifest_uses_same_resolved_geometry(geometry: OpenVSPGeometry) -> None:
    manifest = build_manifest(geometry, "test_vehicle", "vehicle.vspscript")

    assert manifest.geometry == geometry
    assert manifest.vehicle_name == "test_vehicle"
    assert manifest.human_review.value == 0.5
    assert manifest.script_path == "vehicle.vspscript"
    with pytest.raises(FrozenInstanceError):
        manifest.vehicle_name = "x"  # type: ignore[misc]


def test_exporter_is_typed_level_1_analysis() -> None:
    analysis = OpenVSPExporter()
    assert isinstance(analysis, BaseAnalysis)
    assert analysis.fidelity is FidelityLevel.LEVEL_1


def test_exporter_requires_setup() -> None:
    with pytest.raises(RuntimeError, match="before setup"):
        OpenVSPExporter().execute()


def test_exporter_writes_artifacts_via_logger(vehicle: BaseVehicleConfig) -> None:
    analysis = OpenVSPExporter()
    analysis.setup(vehicle)
    results = analysis.execute()
    analysis.logger.close()

    assert isinstance(results, OpenVSPExportResults)
    assert results.body_total_length == pytest.approx(4.2)
    assert results.fin_count == 4
    assert results.script_path is not None and results.manifest_path is not None
    assert Path(results.script_path).read_text(encoding="utf-8") == results.script
    manifest = json.loads(Path(results.manifest_path).read_text(encoding="utf-8"))
    assert manifest["geometry"]["fin_span"] == 0.5
    assert manifest["human_review"]["tag"] == "HR-1"
    assert results.units()["body_diameter"] == "m"
    assert results.scalars()["fin_count"] == 4.0


def test_exporter_without_logging_writes_no_files(
    vehicle: BaseVehicleConfig, tmp_path: Path
) -> None:
    analysis = OpenVSPExporter()
    analysis.setup(vehicle, enable_logging=False)
    results = analysis.execute()

    assert results.script_path is None and results.manifest_path is None
    assert "AddGeom" in results.script
    assert not (tmp_path / "FlightLogs").exists()


def test_validate_results_fails_for_empty_script(vehicle: BaseVehicleConfig) -> None:
    analysis = OpenVSPExporter()
    analysis.setup(vehicle, enable_logging=False)
    results = analysis.execute()
    assert not analysis.validate_results(replace(results, script=" "))
