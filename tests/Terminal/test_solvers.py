"""Tests for the UI-free solver catalog: parameter parsing and shared solver execution."""

from __future__ import annotations

from pathlib import Path

import pytest

from Terminal.solvers import (
    REPAIRED_SOLVERS,
    SolverDescriptor,
    SolverParam,
    check_solver_compatibility,
    execute_solver,
)
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.flight_dynamics.containers import PointMassBoostResults
from YAADO_Core.modules.powerplant.containers import HeiserPrattResults
from YAADO_Core.modules.stability_control.containers import BarrowmanStabilityResults

HARPOON_PATH = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")
ALVRJ_PATH = Path("Hangar/examples/ALVRJ/ALVRJ.toml").resolve()


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


def test_solver_param_parse_blank_only_for_optional() -> None:
    """Verify blank text means None for an optional parameter and is invalid otherwise."""
    optional = SolverParam(
        name="p", label="P", symbol="p", unit="-", param_type=float, default=None, min_value=1.0
    )
    assert optional.parse("  ") is None
    assert optional.parse("2.5") == 2.5
    with pytest.raises(ValueError, match=">= 1.0"):
        optional.parse("0.5")
    with pytest.raises(ValueError):
        _param(float).parse("")


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


def _ramjet_descriptor() -> SolverDescriptor:
    return next(d for d in REPAIRED_SOLVERS if d.solver_id == "heiser_pratt_cycle")


def test_execute_ramjet_saves_figures_and_mach_sweep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a logged ramjet run saves both figures, the sweep CSV and the results."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_PATH)
    monkeypatch.chdir(tmp_path)

    run = execute_solver(_ramjet_descriptor(), vehicle)

    assert isinstance(run.results, HeiserPrattResults)
    assert run.output_dir is not None
    run_dir = tmp_path / run.output_dir
    assert (run_dir / "results.json").is_file()
    assert (run_dir / "figures" / "cycle_stations.png").is_file()
    assert (run_dir / "figures" / "mach_sweep.png").is_file()
    assert (run_dir / "artifacts" / "mach_sweep.csv").is_file()


def test_execute_ramjet_skips_sweep_but_keeps_station_figure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify run_sweep=False removes only the sweep artifacts."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_PATH)
    monkeypatch.chdir(tmp_path)

    run = execute_solver(_ramjet_descriptor(), vehicle, run_sweep=False)

    assert run.output_dir is not None
    run_dir = tmp_path / run.output_dir
    assert (run_dir / "figures" / "cycle_stations.png").is_file()
    assert not (run_dir / "figures" / "mach_sweep.png").exists()
    assert not (run_dir / "artifacts" / "mach_sweep.csv").exists()


def test_execute_ramjet_warns_until_every_loss_is_set() -> None:
    """Verify the run names placeholder losses and stops when all are given."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_PATH)
    desc = _ramjet_descriptor()

    run = execute_solver(desc, vehicle, {"eta_inlet": 0.8}, enable_logging=False)
    assert len(run.warnings) == 1
    assert "combustor_pressure_ratio" in run.warnings[0]
    assert "inlet_recovery" not in run.warnings[0]

    params = {"eta_inlet": 0.8, "pi_cc": 0.9, "pi_nozzle": 0.95, "eta_b": 0.9}
    assert execute_solver(desc, vehicle, params, enable_logging=False).warnings == ()



def _stability_descriptor() -> SolverDescriptor:
    return next(d for d in REPAIRED_SOLVERS if d.solver_id == "barrowman_stability")


def test_stability_compatibility_reports_the_method_error() -> None:
    """Verify the readiness check reuses the geometry validation of the method."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_PATH)
    ready, message = check_solver_compatibility(_stability_descriptor(), vehicle)
    assert ready
    assert "aft_control_fins" in message

    vehicle.aero_surfaces.pop("aft_control_fins")
    ready, message = check_solver_compatibility(_stability_descriptor(), vehicle)
    assert not ready
    assert "no fin set" in message


def test_execute_stability_saves_cp_sweep_and_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a logged stability run saves the CP sweep and flags a low margin."""
    vehicle = BaseVehicleConfig.from_toml(HARPOON_PATH.resolve())
    monkeypatch.chdir(tmp_path)

    run = execute_solver(_stability_descriptor(), vehicle, {"mach": 0.5})

    assert isinstance(run.results, BarrowmanStabilityResults)
    assert run.results.mach == 0.5
    assert run.output_dir is not None
    run_dir = tmp_path / run.output_dir
    assert (run_dir / "results.json").is_file()
    assert (run_dir / "figures" / "cp_vs_mach.png").is_file()
    assert (run_dir / "artifacts" / "cp_vs_mach.csv").is_file()
    assert any("below the required" in w for w in run.warnings)


def test_execute_stability_flags_an_unstable_vehicle() -> None:
    """Verify a CG behind the CP gives an instability warning."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_PATH)
    run = execute_solver(
        _stability_descriptor(), vehicle, {"cg_from_nose": 4.0}, enable_logging=False
    )
    assert run.results.static_margin < 0.0
    assert any("Statically unstable" in w for w in run.warnings)
