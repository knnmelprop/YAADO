"""Unit tests for the FlightLogger subsystem."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytest

from YAADO_Core.Foundation.analysis_base import BaseAnalysisResults, FidelityLevel
from YAADO_Core.Foundation.flight_logger import (
    CheckpointPayload,
    FlightLogger,
    YaadoJSONEncoder,
)
from YAADO_Core.Foundation.units import Dimensionless, Newtons, Seconds


@dataclass(frozen=True)
class DummyResults(BaseAnalysisResults):
    """Dummy typed results for logger serialization tests."""

    thrust: Newtons
    isp: Seconds
    CL: Dimensionless
    solver: str = "test_vlm"
    iterations: int = 10


@pytest.fixture
def clean_test_flight_logger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Fixture providing a FlightLogger rooted in a temporary directory."""
    monkeypatch.chdir(tmp_path)
    loggers_to_close: list[FlightLogger] = []

    def _factory(vehicle_name="test_rocket", analysis_name="test_aero", **kwargs):
        logger = FlightLogger(vehicle_name=vehicle_name, analysis_name=analysis_name, **kwargs)
        loggers_to_close.append(logger)
        return logger

    yield _factory

    for l in loggers_to_close:
        l.close()


def test_flight_logger_directories_created(clean_test_flight_logger):
    """Verify that directories and execution.log are initialized."""
    logger = clean_test_flight_logger()
    assert logger.output_dir.is_dir()
    assert logger.figures_dir.is_dir()
    assert logger.artifacts_dir.is_dir()
    assert logger.log_file_path.is_file()


def test_diagnostic_logging(clean_test_flight_logger):
    """Verify messages are logged to execution.log."""
    logger = clean_test_flight_logger()
    logger.info("Test informational message")
    logger.warning("Test warning alert")
    logger.error("Test error failure")

    # Flush handlers
    logger.close()

    content = logger.log_file_path.read_text(encoding="utf-8")
    assert "[INFO]" in content
    assert "Test informational message" in content
    assert "[WARNING]" in content
    assert "Test warning alert" in content
    assert "[ERROR]" in content
    assert "Test error failure" in content


def test_save_figure(clean_test_flight_logger):
    """Verify figure saving, directory placement, and automatic closing."""
    logger = clean_test_flight_logger()
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])

    saved_path = logger.save_figure(fig, "test_polar.png", close=True)

    assert saved_path is not None
    assert saved_path.is_file()
    assert saved_path.name == "test_polar.png"
    assert saved_path.parent == logger.figures_dir
    # Ensure figure is closed
    assert fig.number not in plt.get_fignums()


def test_save_and_load_results(clean_test_flight_logger):
    """Verify saving results.json and summary.csv and reloading BaseAnalysisResults."""
    logger = clean_test_flight_logger()

    results = DummyResults(
        name="test_aero",
        fidelity=FidelityLevel.LEVEL_1,
        thrust=450.0,
        isp=1850.5,
        CL=0.35,
        solver="test_vlm",
        iterations=10,
    )

    json_path = logger.save_results(results)
    assert json_path is not None
    assert json_path.is_file()

    # Verify summary.csv exists and has correct unit separation
    csv_path = logger.output_dir / "summary.csv"
    assert csv_path.is_file()

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows[0] == ["metric", "value", "unit"]
    blank_idx = rows.index([])
    metric_rows = rows[1:blank_idx]
    meta_rows = rows[blank_idx + 1 :]

    data_dict = {row[0]: (row[1], row[2]) for row in metric_rows}
    assert data_dict["thrust"] == ("450", "N")
    assert data_dict["isp"] == ("1850.5", "s")
    assert data_dict["CL"] == ("0.35", "-")
    assert data_dict["iterations"] == ("10", "-")

    assert meta_rows[0] == ["metadata", "value", "unit"]
    meta_dict = {row[0]: (row[1], row[2]) for row in meta_rows[1:]}
    assert meta_dict["solver"] == ("test_vlm", "-")
    assert meta_dict["vehicle"] == ("test_rocket", "-")
    assert meta_dict["analysis"] == ("test_aero", "-")

    # Verify load_checkpoint returns strongly typed CheckpointPayload
    raw_payload = logger.load_checkpoint()
    assert isinstance(raw_payload, CheckpointPayload)
    assert raw_payload.analysis_name == "test_aero"
    assert raw_payload.fidelity == FidelityLevel.LEVEL_1
    assert raw_payload.data["thrust"] == 450.0
    assert raw_payload.data["isp"] == 1850.5
    assert raw_payload.units["thrust"] == "N"
    assert raw_payload.units["isp"] == "s"
    assert raw_payload.units["CL"] == "-"

    # Verify load_results strongly typed roundtrip
    loaded = logger.load_results(DummyResults)
    assert isinstance(loaded, DummyResults)
    assert loaded.name == "test_aero"
    assert loaded.fidelity == FidelityLevel.LEVEL_1
    assert loaded.thrust == 450.0
    assert loaded.isp == 1850.5
    assert loaded.CL == 0.35
    assert loaded.solver == "test_vlm"
    assert loaded.iterations == 10


def test_yaado_json_encoder_numpy():
    """Verify YaadoJSONEncoder safely serializes NumPy types and Enums as name strings."""
    data = {
        "float_val": np.float64(3.14159),
        "int_val": np.int64(42),
        "array_val": np.array([1.0, 2.0, 3.0]),
        "fidelity": FidelityLevel.LEVEL_2,
        "path": Path("/test/path"),
    }
    encoded = json.dumps(data, cls=YaadoJSONEncoder)
    decoded = json.loads(encoded)

    assert abs(decoded["float_val"] - 3.14159) < 1e-5
    assert decoded["int_val"] == 42
    assert decoded["array_val"] == [1.0, 2.0, 3.0]
    assert decoded["fidelity"] == "LEVEL_2"
    assert decoded["path"] == "/test/path"


def test_save_artifact(clean_test_flight_logger):
    """Verify saving string and bytes artifacts."""
    logger = clean_test_flight_logger()

    txt_path = logger.save_artifact("sweep.csv", "time,alt\n0,0\n1,10\n")
    bin_path = logger.save_artifact("data.bin", b"\x00\x01\x02")

    assert txt_path is not None and txt_path.is_file()
    assert txt_path.read_text(encoding="utf-8") == "time,alt\n0,0\n1,10\n"

    assert bin_path is not None and bin_path.is_file()
    assert bin_path.read_bytes() == b"\x00\x01\x02"


def test_disabled_mode_zero_overhead(tmp_path):
    """Verify disabled mode does not touch the filesystem."""
    logger = FlightLogger("rocket", "test", enabled=False)
    # Repoint output_dir to tmp_path to verify it does NOT touch it
    logger.output_dir = tmp_path / "never_created"
    logger.figures_dir = logger.output_dir / "figures"
    logger.artifacts_dir = logger.output_dir / "artifacts"
    logger.log_file_path = logger.output_dir / "execution.log"

    assert not logger.output_dir.exists()

    fig, ax = plt.subplots()
    saved_fig = logger.save_figure(fig, "plot.png")
    assert saved_fig is None
    assert not logger.output_dir.exists()

    sample_res = DummyResults(
        name="test_disabled",
        fidelity=FidelityLevel.LEVEL_0,
        thrust=100.0,
        isp=200.0,
        CL=0.1,
    )
    saved_res = logger.save_results(sample_res)
    assert saved_res is None
    assert not logger.output_dir.exists()

    saved_art = logger.save_artifact("test.txt", "content")
    assert saved_art is None
    assert not logger.output_dir.exists()


def test_save_results_rejects_dict_or_invalid_type(clean_test_flight_logger):
    """Verify save_results strictly requires a BaseAnalysisResults instance."""
    logger = clean_test_flight_logger()
    with pytest.raises(TypeError, match="BaseAnalysisResults"):
        logger.save_results({"data": {"x": 1}})  # type: ignore[arg-type]


def test_load_checkpoint_rejects_missing_required_keys(clean_test_flight_logger):
    """Verify load_checkpoint fails loudly when required schema keys are missing."""
    logger = clean_test_flight_logger()

    bad_checkpoint = logger.output_dir / "missing_keys.json"
    bad_checkpoint.write_text(json.dumps({"data": {"x": 1}}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required key"):
        logger.load_checkpoint("missing_keys.json")


def test_load_checkpoint_rejects_non_string_or_invalid_fidelity(clean_test_flight_logger):
    """Verify load_checkpoint fails loudly on non-string or invalid fidelity."""
    logger = clean_test_flight_logger()

    base_checkpoint = {
        "vehicle_name": "test_rocket",
        "analysis_name": "test_aero",
        "timestamp": "2026-01-01_120000",
        "fidelity": "LEVEL_1",
        "data": {},
        "units": {},
        "details": {},
    }

    # Non-string fidelity (e.g. int) rejected by strict data contract
    bad_checkpoint_int = dict(base_checkpoint, fidelity=1)
    (logger.output_dir / "int_fidelity.json").write_text(
        json.dumps(bad_checkpoint_int), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="must be an enum string"):
        logger.load_checkpoint("int_fidelity.json")

    # Invalid fidelity enum string
    bad_checkpoint_invalid = dict(base_checkpoint, fidelity="LEVEL_UNKNOWN")
    (logger.output_dir / "invalid_fidelity.json").write_text(
        json.dumps(bad_checkpoint_invalid), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="invalid fidelity level"):
        logger.load_checkpoint("invalid_fidelity.json")


def test_load_results_rejects_invalid_fidelity_in_details(clean_test_flight_logger):
    """Verify load_results fails loudly when details contains invalid fidelity."""
    logger = clean_test_flight_logger()

    base_checkpoint = {
        "vehicle_name": "test_rocket",
        "analysis_name": "test_aero",
        "timestamp": "2026-01-01_120000",
        "fidelity": "LEVEL_1",
        "data": {},
        "units": {},
        "details": {"fidelity": "INVALID_NAME", "thrust": 100.0, "isp": 200.0, "CL": 0.5},
    }
    (logger.output_dir / "invalid_details.json").write_text(
        json.dumps(base_checkpoint), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Invalid fidelity name in details"):
        logger.load_results(DummyResults, "invalid_details.json")


def test_save_json_and_save_text(clean_test_flight_logger):
    """Verify save_json and save_text write artifacts cleanly."""
    logger = clean_test_flight_logger()

    json_path = logger.save_json({"sweep_values": [1.0, 2.0, 3.0]}, "sweep.json")
    assert json_path is not None
    assert json_path.is_file()
    assert json.loads(json_path.read_text(encoding="utf-8")) == {"sweep_values": [1.0, 2.0, 3.0]}

    text_path = logger.save_text("line1\nline2", "report.txt")
    assert text_path is not None
    assert text_path.is_file()
    assert text_path.read_text(encoding="utf-8") == "line1\nline2"


def test_context_manager_protocol(tmp_path: Path):
    """Verify FlightLogger cleanly operates as a context manager."""
    with FlightLogger("cm_vehicle", "cm_analysis", enabled=True) as logger:
        logger.output_dir = tmp_path / "cm_run"
        logger.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Inside context manager")
        assert len(logger.logger.handlers) > 0

    # Handlers flushed and removed on exit
    assert len(logger.logger.handlers) == 0
