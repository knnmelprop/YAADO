"""Unit tests for the FlightLogger subsystem."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytest

from YAADO_Core.Foundation.analysis_base import AnalysisResults, FidelityLevel
from YAADO_Core.Foundation.flight_logger import (
    FlightLogger,
    YaadoJSONEncoder,
)


@pytest.fixture
def clean_test_flight_logger(tmp_path, monkeypatch):
    """Fixture providing a FlightLogger rooted in a temporary directory."""
    monkeypatch.setattr(
        "YAADO_Core.Foundation.flight_logger.Path",
        lambda *args: (
            tmp_path / args[1] / args[2]
            if len(args) == 3 and args[0] == "FlightLogs"
            else Path(*args)
        ),
    )
    # Alternatively, create a logger and point output_dir to tmp_path
    loggers_to_close: list[FlightLogger] = []

    def _factory(vehicle_name="test_rocket", analysis_name="test_aero", **kwargs):
        logger = FlightLogger(vehicle_name=vehicle_name, analysis_name=analysis_name, **kwargs)
        # Override output_dir paths to use tmp_path
        logger.output_dir = tmp_path / vehicle_name / logger.run_folder_name
        logger.figures_dir = logger.output_dir / "figures"
        logger.artifacts_dir = logger.output_dir / "artifacts"
        logger.log_file_path = logger.output_dir / "execution.log"
        if logger.enabled:
            logger._setup_directories()
            logger._setup_logging()
        loggers_to_close.append(logger)
        return logger

    yield _factory

    for l in loggers_to_close:
        l.close()


def test_first_class_units_in_analysis_results():
    """Verify first-class units metadata and legacy inference in AnalysisResults."""
    # Explicit units
    res = AnalysisResults(
        name="test",
        fidelity=FidelityLevel.LEVEL_1,
        data={"thrust": 450.0, "CL": 0.35},
        units={"thrust": "N", "CL": "-"},
    )
    assert res.get_unit("thrust") == "N"
    assert res.get_unit("CL") == "-"
    assert res.to_dict()["units"] == {"thrust": "N", "CL": "-"}

    # Unannotated data cleanly defaults to "-" without guessing or string manipulation
    unannotated_res = AnalysisResults(
        name="unannotated",
        fidelity=FidelityLevel.LEVEL_0,
        data={"thrust_N": 500.0, "isp_s": 1200.0, "mach": 2.0},
    )
    assert unannotated_res.units == {}
    assert unannotated_res.get_unit("thrust_N") == "-"
    assert unannotated_res.get_unit("isp_s") == "-"
    assert unannotated_res.get_unit("mach") == "-"


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
    """Verify saving results.json and summary.csv and reloading AnalysisResults."""
    logger = clean_test_flight_logger()

    results = AnalysisResults(
        name="test_aero",
        fidelity=FidelityLevel.LEVEL_1,
        data={
            "thrust": 450.0,
            "isp": 1850.5,
            "CL": 0.35,
        },
        units={
            "thrust": "N",
            "isp": "s",
            "CL": "-",
        },
        metadata={"solver": "test_vlm", "iterations": 10},
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

    assert meta_rows[0] == ["metadata", "value", "unit"]
    meta_dict = {row[0]: (row[1], row[2]) for row in meta_rows[1:]}
    assert meta_dict["solver"] == ("test_vlm", "-")
    assert meta_dict["iterations"] == ("10", "-")
    assert meta_dict["vehicle"] == ("test_rocket", "-")
    assert meta_dict["analysis"] == ("test_aero", "-")

    # Verify load_results roundtrip
    loaded = logger.load_results()
    assert loaded.name == "test_aero"
    assert loaded.fidelity == FidelityLevel.LEVEL_1
    assert loaded.data["thrust"] == 450.0
    assert loaded.data["isp"] == 1850.5
    assert loaded.units["thrust"] == "N"
    assert loaded.units["isp"] == "s"
    assert loaded.units["CL"] == "-"
    assert loaded.metadata["solver"] == "test_vlm"


def test_yaado_json_encoder_numpy():
    """Verify YaadoJSONEncoder safely serializes NumPy types."""
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
    assert decoded["fidelity"] == 2
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

    sample_res = AnalysisResults(
        name="test_disabled",
        fidelity=FidelityLevel.LEVEL_0,
        data={"x": 1.0},
    )
    saved_res = logger.save_results(sample_res)
    assert saved_res is None
    assert not logger.output_dir.exists()

    saved_art = logger.save_artifact("test.txt", "content")
    assert saved_art is None
    assert not logger.output_dir.exists()


def test_save_results_rejects_dict_or_invalid_type(clean_test_flight_logger):
    """Verify save_results strictly requires an AnalysisResults instance."""
    logger = clean_test_flight_logger()
    with pytest.raises(TypeError, match="AnalysisResults"):
        logger.save_results({"data": {"x": 1}})  # type: ignore[arg-type]


def test_load_results_rejects_missing_or_invalid_fidelity(clean_test_flight_logger):
    """Verify load_results fails loudly on missing or invalid fidelity."""
    logger = clean_test_flight_logger()

    # Missing fidelity key
    bad_checkpoint_1 = logger.output_dir / "missing_fidelity.json"
    bad_checkpoint_1.write_text(json.dumps({"data": {"x": 1}}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing 'fidelity' key"):
        logger.load_results("missing_fidelity.json")

    # Invalid fidelity integer
    bad_checkpoint_2 = logger.output_dir / "invalid_fidelity.json"
    bad_checkpoint_2.write_text(json.dumps({"fidelity": 99, "data": {"x": 1}}), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid fidelity level"):
        logger.load_results("invalid_fidelity.json")
