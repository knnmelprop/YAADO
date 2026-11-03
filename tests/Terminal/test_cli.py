"""Tests for the ``yaado`` entry point and its bare (``-b``) one-liner mode."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from Terminal.app import YaadoApp
from Terminal.cli import main

HARPOON_PATH = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml").resolve()
BARE_RUN = ["-b", "--vehicle", str(HARPOON_PATH), "--solver", "point_mass_3dof_boost"]


def _exit_code(argv: list[str]) -> int | str | None:
    with pytest.raises(SystemExit) as exc_info:
        main(argv)
    return exc_info.value.code


def test_bare_list_solvers(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify --list-solvers prints each solver with its tunable parameters."""
    assert _exit_code(["-b", "--list-solvers"]) == 0
    out = capsys.readouterr().out
    assert "point_mass_3dof_boost" in out
    assert "launch_angle_deg" in out
    assert "deg" in out


def test_bare_text_output_without_logging(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify the default output lists headline metrics and omits the log line with --no-log."""
    assert _exit_code([*BARE_RUN, "--no-log"]) == 0
    lines = capsys.readouterr().out.splitlines()
    rows = {line.split()[0]: line.split()[1:] for line in lines}
    assert rows["vehicle"] == ["AGM-84_HARPOON"]
    assert rows["burnout_velocity"][1] == "m/s"
    assert float(rows["burnout_mach"][0]) > 0.8
    assert "flightlog" not in rows


def test_bare_json_output_applies_overrides(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify --json prints parseable results and --set overrides reach the solver."""
    argv = [*BARE_RUN, "--no-log", "--json", "--set", "launch_angle_deg=45", "--set", "stop_at_burnout=false"]
    assert _exit_code(argv) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["solver"] == "point_mass_3dof_boost"
    assert payload["params"]["launch_angle_deg"] == 45.0
    assert payload["params"]["stop_at_burnout"] is False
    assert payload["flightlog"] is None
    assert payload["units"]["apogee_altitude"] == "m"
    assert payload["results"]["flight_time"] > payload["results"]["burnout_time"]


def test_bare_logged_run_matches_flight_deck_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify a logged bare run writes the same artifacts as a Flight Deck run."""
    monkeypatch.chdir(tmp_path)
    assert _exit_code(BARE_RUN) == 0

    flightlog_line = capsys.readouterr().out.splitlines()[-1]
    assert flightlog_line.startswith("flightlog")
    run_dir = tmp_path / flightlog_line.split()[1]
    for artifact in (
        "results.json",
        "summary.csv",
        "execution.log",
        "figures/boost_phase.png",
        "figures/launch_angle_sweep.png",
        "artifacts/launch_angle_sweep.csv",
    ):
        assert (run_dir / artifact).is_file(), artifact


@pytest.mark.parametrize(
    "argv",
    [
        ["-b"],
        ["-b", "--vehicle", str(HARPOON_PATH)],
        [*BARE_RUN, "--set", "launch_angle_deg=95"],
        [*BARE_RUN, "--set", "unknown=1"],
        [*BARE_RUN, "--set", "launch_angle_deg"],
        ["--vehicle", str(HARPOON_PATH), "--solver", "point_mass_3dof_boost"],
    ],
)
def test_bare_usage_errors_exit_2(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    """Verify missing, malformed, or out-of-range arguments are rejected before running."""
    assert _exit_code(argv) == 2
    assert "error:" in capsys.readouterr().err


def test_bare_runtime_errors_exit_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify an unreadable vehicle and an incompatible vehicle both exit 1 with a message."""
    missing = tmp_path / "missing.toml"
    assert _exit_code(["-b", "--vehicle", str(missing), "--solver", "point_mass_3dof_boost"]) == 1
    assert "not found" in capsys.readouterr().err

    no_booster = tmp_path / "no_booster.toml"
    no_booster.write_text('name = "NoBooster"\n')
    assert _exit_code(["-b", "--vehicle", str(no_booster), "--solver", "point_mass_3dof_boost"]) == 1
    assert "booster propulsion" in capsys.readouterr().err


def test_no_arguments_launches_cockpit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify plain ``yaado`` still starts the Textual app."""
    launched: list[YaadoApp] = []
    monkeypatch.setattr(YaadoApp, "run", lambda self: launched.append(self))
    assert _exit_code([]) is None
    assert len(launched) == 1
