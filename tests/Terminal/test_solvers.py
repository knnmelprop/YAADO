"""Tests for the UI-free solver catalog: parameter parsing and shared solver execution."""

from __future__ import annotations

from pathlib import Path

import pytest

from Terminal.solvers import REPAIRED_SOLVERS, SolverParam, execute_solver
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.flight_dynamics.containers import PointMassBoostResults

HARPOON_PATH = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")


def _param(
    param_type: type, min_value: float | None = None, max_value: float | None = None
) -> SolverParam:
    return SolverParam(
        name="p",
        label="P",
        symbol="p",
        unit="-",
        param_type=param_type,
        default=0,
        min_value=min_value,
        max_value=max_value,
    )


def test_solver_param_parse_numbers_and_bounds() -> None:
    """Verify numeric parsing honors the declared type and min/max bounds."""
    angle = _param(float, min_value=0.0, max_value=90.0)
    assert angle.parse(" 45.5 ") == 45.5
    assert _param(int).parse("7") == 7
    with pytest.raises(ValueError, match="<= 90.0"):
        angle.parse("95")
    with pytest.raises(ValueError, match=">= 0.0"):
        angle.parse("-1")
    with pytest.raises(ValueError):
        angle.parse("abc")


def test_solver_param_parse_bool() -> None:
    """Verify boolean parsing accepts true/false spellings and rejects anything else."""
    flag = _param(bool)
    assert flag.parse("True") is True
    assert flag.parse("no") is False
    with pytest.raises(ValueError, match="true or false"):
        flag.parse("maybe")


def test_execute_solver_merges_defaults_without_logging() -> None:
    """Verify overrides merge over catalog defaults and a non-logged run has no output dir."""
    vehicle = BaseVehicleConfig.from_toml(HARPOON_PATH)
    desc = REPAIRED_SOLVERS[0]

    run = execute_solver(desc, vehicle, {"launch_angle_deg": 45.0}, enable_logging=False)

    assert isinstance(run.results, PointMassBoostResults)
    assert run.output_dir is None
    assert run.params["launch_angle_deg"] == 45.0
    assert run.params["altitude_m"] == desc.default_params["altitude_m"]
    assert run.params["fins_name"] == "aft_control_fins"


def test_execute_solver_rejects_incompatible_vehicle() -> None:
    """Verify an incompatible vehicle raises instead of failing inside the solver."""
    with pytest.raises(ValueError, match="booster propulsion"):
        execute_solver(REPAIRED_SOLVERS[0], BaseVehicleConfig(name="EmptyRocket"))


def test_execute_solver_skips_sweep_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify run_sweep=False still logs results and figures but writes no sweep files."""
    vehicle = BaseVehicleConfig.from_toml(HARPOON_PATH)
    monkeypatch.chdir(tmp_path)

    run = execute_solver(REPAIRED_SOLVERS[0], vehicle, run_sweep=False)

    assert run.output_dir is not None
    run_dir = tmp_path / run.output_dir
    assert (run_dir / "results.json").is_file()
    assert (run_dir / "figures" / "boost_phase.png").is_file()
    assert not (run_dir / "figures" / "launch_angle_sweep.png").exists()
    assert not (run_dir / "artifacts" / "launch_angle_sweep.csv").exists()
