# MELprop-IADE | tests.unit.test_cfd_su2_config | v0.1.0
"""Smoke tests for analyses.cfd.su2_config_template.

Only checks file-generation behaviour (one ``.cfg`` per Mach number,
required geometry fields, the ``# TO RUN:`` hint) -- SU2 itself is never
invoked, matching the module's file-generation-only contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from IADE_Core.modules.cfd.su2_config_template import (
    MACH_SWEEP,
    VEHICLE_CONFIG_PATH,
    SU2ConfigGeneration,
    load_rocket_config,
    su2_config_filename,
    write_mach_sweep_configs,
)
from IADE_Core.FlightDeck.component_base import FidelityLevel
from IADE_Core.Inspectors.vehicle_schema import RocketConfig


@pytest.fixture()
def rocket_config() -> RocketConfig:
    """Load the committed ramjet-rocket configuration."""
    return load_rocket_config(VEHICLE_CONFIG_PATH)


def test_write_mach_sweep_configs_one_file_per_mach(
    rocket_config: RocketConfig, tmp_path: Path
) -> None:
    """One .cfg file is written per Mach number in MACH_SWEEP."""
    paths = write_mach_sweep_configs(rocket_config, output_dir=tmp_path)

    assert len(paths) == len(MACH_SWEEP)
    for mach, path in zip(MACH_SWEEP, paths):
        assert path.name == su2_config_filename(mach)
        assert path.exists()

    written_files = sorted(tmp_path.glob("*.cfg"))
    assert len(written_files) == len(MACH_SWEEP)


def test_generated_config_has_geometry_and_run_hint(
    rocket_config: RocketConfig, tmp_path: Path
) -> None:
    """Each config carries geometry pulled from the YAML plus the run hint."""
    paths = write_mach_sweep_configs(rocket_config, output_dir=tmp_path)

    d_ref = rocket_config.body.diameter_m
    fin_span = rocket_config.fins.span_m

    for path in paths:
        text = path.read_text(encoding="utf-8")

        # Required "how to run" hint for a human once SU2 is available.
        assert f"# TO RUN: su2_CFD {path.name}" in text

        # Geometry fields pulled from vehicle_config.yaml, not hard-coded.
        assert f"{d_ref:.4f}" in text
        assert f"{fin_span:.4f}" in text
        assert "MESH_FILENAME=" in text
        assert "REF_AREA=" in text
        assert "REF_LENGTH=" in text

        # Euler-only physics (no viscous / turbulence model keys).
        assert "SOLVER= EULER" in text
        assert "MACH_NUMBER=" in text


def test_never_invokes_su2_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                   rocket_config: RocketConfig) -> None:
    """Generation must not shell out to su2_CFD/gmsh (patch subprocess to fail loudly)."""
    import subprocess

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("su2_config_template must never invoke a subprocess")

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)

    paths = write_mach_sweep_configs(rocket_config, output_dir=tmp_path)
    assert len(paths) == len(MACH_SWEEP)


def test_su2_config_generation_analysis_execute(
    rocket_config: RocketConfig, tmp_path: Path
) -> None:
    """SU2ConfigGeneration follows the BaseAnalysis setup/execute contract."""
    analysis = SU2ConfigGeneration()
    with pytest.raises(RuntimeError):
        analysis.execute()

    analysis.setup(rocket_config, output_dir=tmp_path)
    results = analysis.execute()

    assert results.fidelity == FidelityLevel.LEVEL_2
    assert results["n_configs"] == len(MACH_SWEEP)
    assert analysis.validate_results(results)
    assert len(results.metadata["config_paths"]) == len(MACH_SWEEP)
