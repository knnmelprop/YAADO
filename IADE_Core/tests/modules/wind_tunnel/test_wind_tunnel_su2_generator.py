# MELprop-IADE | tests.unit.test_cfd_su2_generator | v0.1.0
"""Tests for the Mach x AoA grid API of analyses.cfd.su2_config_template.

Covers the SU2ConfigGenerator(BaseAnalysis) grid interface added on top
of the existing Mach-only sweep (see test_cfd_su2_config.py): file
count for a small grid, run_manifest.json consistency, correct Mach/AoA
injection into the .cfg text, and idempotent regeneration. SU2 itself
is never invoked (file-generation-only contract, same as the rest of
this module).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from IADE_Core.modules.wind_tunnel.methods.su2.su2_config_template import (
    VEHICLE_CONFIG_PATH,
    RUN_MANIFEST_FILENAME,
    SU2ConfigGenerator,
    load_rocket_config,
    su2_config_filename_grid,
    write_mach_aoa_grid,
)
from IADE_Core.Foundation.component_base import FidelityLevel
from Hangar.ramjet_rocket.rocket_schema import RocketConfig


@pytest.fixture()
def rocket_config() -> RocketConfig:
    """Load the committed ramjet-rocket configuration."""
    return load_rocket_config(VEHICLE_CONFIG_PATH)


def test_grid_produces_cartesian_combinations(
    rocket_config: RocketConfig, tmp_path: Path
) -> None:
    """A 2 Mach x 2 AoA grid writes 4 files (grid, not zip)."""
    mach_list = (0.8, 2.0)
    aoa_list = (0.0, 4.0)

    paths = write_mach_aoa_grid(rocket_config, mach_list, aoa_list, output_dir=tmp_path)

    assert len(paths) == 4
    expected_names = {
        su2_config_filename_grid(m, a) for m in mach_list for a in aoa_list
    }
    assert {p.name for p in paths} == expected_names
    for path in paths:
        assert path.exists()

    written_cfgs = sorted(tmp_path.glob("*.cfg"))
    assert len(written_cfgs) == 4


def test_manifest_json_valid_and_consistent_with_files(
    rocket_config: RocketConfig, tmp_path: Path
) -> None:
    """run_manifest.json lists exactly the generated files with matching fields."""
    mach_list = (0.8, 1.5)
    aoa_list = (0.0, 2.0)

    paths = write_mach_aoa_grid(rocket_config, mach_list, aoa_list, output_dir=tmp_path)

    manifest_path = tmp_path / RUN_MANIFEST_FILENAME
    assert manifest_path.exists()

    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(entries, list)
    assert len(entries) == len(paths) == 4

    manifest_paths = {entry["config_path"] for entry in entries}
    assert manifest_paths == {str(p) for p in paths}

    manifest_combinations = {(entry["mach"], entry["aoa_deg"]) for entry in entries}
    expected_combinations = {(m, a) for m in mach_list for a in aoa_list}
    assert manifest_combinations == expected_combinations

    for entry in entries:
        assert entry["ref_length_m"] > 0.0
        assert entry["ref_area_m2"] > 0.0


def test_mach_and_aoa_injected_into_config_text(
    rocket_config: RocketConfig, tmp_path: Path
) -> None:
    """Each generated .cfg carries its own Mach/AoA, not a shared default."""
    mach_list = (1.5, 2.5)
    aoa_list = (0.0, 6.0)

    paths = write_mach_aoa_grid(rocket_config, mach_list, aoa_list, output_dir=tmp_path)

    seen: set[tuple[float, float]] = set()
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert f"MACH_NUMBER= {_extract_value(text, 'MACH_NUMBER')}" in text
        mach_val = float(_extract_value(text, "MACH_NUMBER"))
        aoa_val = float(_extract_value(text, "AOA"))
        assert mach_val in mach_list
        assert aoa_val in aoa_list
        seen.add((mach_val, aoa_val))
        # % TO RUN comment header + Euler solver directive, per the SU2
        # EULER template convention used across this module (SU2 7.x
        # renamed the legacy PHYSICAL_PROBLEM key to SOLVER).
        assert f"# TO RUN: su2_CFD {path.name}" in text
        assert "SOLVER= EULER" in text
        assert "REF_LENGTH=" in text
        assert "REF_AREA=" in text

    assert seen == {(m, a) for m in mach_list for a in aoa_list}


def _extract_value(text: str, key: str) -> str:
    """Pull the raw value string for a ``KEY= value`` line in a .cfg text."""
    for line in text.splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().split()[0]
    raise AssertionError(f"{key}= not found in config text")


def test_regeneration_is_idempotent_and_clears_stale_files(
    rocket_config: RocketConfig, tmp_path: Path
) -> None:
    """Re-generating the same grid overwrites cleanly; a shrinking grid drops stale files."""
    large_mach = (0.8, 1.5, 2.0)
    large_aoa = (0.0, 4.0)

    first_paths = write_mach_aoa_grid(
        rocket_config, large_mach, large_aoa, output_dir=tmp_path
    )
    assert len(first_paths) == 6
    assert len(list(tmp_path.glob("*.cfg"))) == 6

    # Regenerate the identical grid: same file set, same manifest count.
    second_paths = write_mach_aoa_grid(
        rocket_config, large_mach, large_aoa, output_dir=tmp_path
    )
    assert {p.name for p in second_paths} == {p.name for p in first_paths}
    assert len(list(tmp_path.glob("*.cfg"))) == 6

    # Regenerate a smaller grid: stale .cfg files from the larger grid
    # must not linger, and the manifest must only list current files.
    small_mach = (0.8,)
    small_aoa = (0.0,)
    third_paths = write_mach_aoa_grid(
        rocket_config, small_mach, small_aoa, output_dir=tmp_path
    )
    assert len(third_paths) == 1
    remaining_cfgs = sorted(tmp_path.glob("*.cfg"))
    assert len(remaining_cfgs) == 1
    assert remaining_cfgs[0] == third_paths[0]

    manifest_path = tmp_path / RUN_MANIFEST_FILENAME
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(entries) == 1
    assert entries[0]["config_path"] == str(third_paths[0])


def test_su2_config_generator_analysis_contract(
    rocket_config: RocketConfig, tmp_path: Path
) -> None:
    """SU2ConfigGenerator follows the BaseAnalysis setup/generate/execute contract."""
    analysis = SU2ConfigGenerator()
    with pytest.raises(RuntimeError):
        analysis.generate(mach_list=(0.8,), aoa_list=(0.0,))
    with pytest.raises(RuntimeError):
        analysis.execute()

    analysis.setup(rocket_config, output_dir=tmp_path)

    paths = analysis.generate(mach_list=(0.8, 1.5), aoa_list=(0.0, 3.0))
    assert len(paths) == 4

    results = analysis.execute()
    assert results.fidelity == FidelityLevel.LEVEL_2
    assert analysis.validate_results(results)
    assert results["n_configs"] == len(analysis.DEFAULT_MACH_LIST) * len(
        analysis.DEFAULT_AOA_LIST
    )
    assert Path(results.metadata["manifest_path"]).exists()
