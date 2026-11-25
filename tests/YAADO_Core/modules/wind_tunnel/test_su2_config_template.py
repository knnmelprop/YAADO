"""Tests for the SU2 Euler configuration decks."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

from YAADO_Core.Foundation.atmosphere import isa_atmosphere
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.wind_tunnel.methods.su2.su2_config_template import (
    SOLVER_SETTINGS,
    SU2ConfigGeneration,
    build_su2_config,
    su2_config_filename,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
HARPOON_PATH = REPO_ROOT / "Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml"
SU2_CONFIG_SOURCE = REPO_ROOT / "external/su2/Common/src/CConfig.cpp"


def _deck_values(text: str) -> dict[str, str]:
    """``KEY= value`` pairs of a deck, without comments."""
    pairs = {}
    for line in text.splitlines():
        if line.startswith("%") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        pairs[key.strip()] = value.split("%")[0].strip()
    return pairs


def _deck(mach: float = 2.0, alpha: float = 4.0, altitude: float = 10000.0) -> str:
    return build_su2_config(
        "Test", mach, alpha, altitude, isa_atmosphere(altitude),
        ref_area=0.0924, ref_length=0.343, moment_origin_x=2.05,
        filename=su2_config_filename(mach, alpha),
    )


def test_deck_carries_the_case_and_the_isa_freestream() -> None:
    """ISA at 10 km geometric (US Standard Atmosphere 1976): 223.252 K, 26 499.9 Pa."""
    values = _deck_values(_deck())
    assert float(values["MACH_NUMBER"]) == 2.0
    assert float(values["AOA"]) == 4.0
    assert float(values["FREESTREAM_TEMPERATURE"]) == pytest.approx(223.252, abs=0.01)
    assert float(values["FREESTREAM_PRESSURE"]) == pytest.approx(26499.9, rel=1e-4)
    assert float(values["REF_AREA"]) == pytest.approx(0.0924)
    assert float(values["REF_LENGTH"]) == pytest.approx(0.343)
    assert float(values["REF_ORIGIN_MOMENT_X"]) == pytest.approx(2.05)
    assert values["RESTART_FILENAME"] == "restart_su2_mach2p00_aoa4p00.dat"
    assert values["CONV_FILENAME"] == "history_su2_mach2p00_aoa4p00"


@pytest.mark.skipif(not SU2_CONFIG_SOURCE.is_file(), reason="SU2 submodule not checked out")
def test_every_deck_option_exists_in_su2() -> None:
    """An unknown option stops SU2_CFD, so every key must be declared in CConfig.cpp."""
    source = SU2_CONFIG_SOURCE.read_text(encoding="utf-8", errors="replace")
    declared = set(re.findall(r'add\w*Option\(\s*"(\w+)"', source))
    assert set(_deck_values(_deck())) <= declared


def test_a_half_model_halves_the_reference_area_and_adds_the_symmetry_plane() -> None:
    def deck(half: bool) -> dict[str, str]:
        return _deck_values(
            build_su2_config(
                "Test", 2.0, 0.0, 0.0, isa_atmosphere(0.0), ref_area=0.1, ref_length=0.3,
                moment_origin_x=1.0, filename="case.cfg", half_model=half,
            )
        )

    assert deck(True)["MARKER_SYM"] == "( symmetry )"
    assert float(deck(True)["REF_AREA"]) == pytest.approx(0.05)
    assert "MARKER_SYM" not in deck(False)
    assert float(deck(False)["REF_AREA"]) == pytest.approx(0.1)
    if SU2_CONFIG_SOURCE.is_file():
        assert '"MARKER_SYM"' in SU2_CONFIG_SOURCE.read_text(encoding="utf-8", errors="replace")


def test_filenames_encode_mach_and_signed_angle() -> None:
    assert su2_config_filename(2.5, 0.0) == "su2_mach2p50_aoa0p00.cfg"
    assert su2_config_filename(0.8, -2.0) == "su2_mach0p80_aoam2p00.cfg"


def test_solver_settings_are_an_euler_case() -> None:
    settings = dict(SOLVER_SETTINGS)
    assert settings["SOLVER"] == "EULER"
    assert settings["MARKER_EULER"] == "( airframe, base )"
    assert settings["MARKER_FAR"] == "( farfield )"


def test_analysis_on_the_harpoon_builds_a_mach_alpha_grid() -> None:
    vehicle = BaseVehicleConfig.from_toml(HARPOON_PATH)
    analysis = SU2ConfigGeneration()
    analysis.setup(vehicle, enable_logging=False, mach_list=(0.8, 1.5, 2.5),
                   alpha_list_deg=(-2.0, 0.0, 4.0), altitude_m=10000.0)
    results = analysis.execute()

    assert results.n_configs == 9
    assert [(c.mach, c.alpha) for c in results.cases[:3]] == [(0.8, -2.0), (0.8, 0.0), (0.8, 4.0)]
    # Harpoon body diameter 0.343 m; CG 2.05 m from mass_properties
    assert results.ref_area == pytest.approx(math.pi / 4.0 * 0.343**2)
    assert results.ref_length == 0.343
    assert results.moment_origin_x == pytest.approx(vehicle.mass_properties.cg_from_nose)
    assert results.freestream_density == pytest.approx(0.41351, rel=1e-4)
    assert results.units()["ref_area"] == "m^2"
    assert len(results.assumptions) == 1


def test_overrides_replace_the_body_references_and_cg() -> None:
    vehicle = BaseVehicleConfig.from_toml(HARPOON_PATH)
    analysis = SU2ConfigGeneration()
    analysis.setup(vehicle, enable_logging=False, ref_area=0.363, ref_length=0.456,
                   cg_from_nose=1.9, mach_list=(0.5,))
    results = analysis.execute()
    assert (results.ref_area, results.ref_length, results.moment_origin_x) == (0.363, 0.456, 1.9)


def test_a_vehicle_without_body_or_cg_needs_references() -> None:
    bare = BaseVehicleConfig(name="Glider")
    with pytest.raises(ValueError, match="no component matching"):
        SU2ConfigGeneration().setup(bare, enable_logging=False)

    analysis = SU2ConfigGeneration()
    analysis.setup(bare, enable_logging=False, ref_area=1.2, ref_length=0.3, mach_list=(0.7,))
    results = analysis.execute()
    assert results.moment_origin_x == 0.0
    assert any("nose tip" in note for note in results.assumptions)


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"mach_list": ()}, "at least one"),
        ({"mach_list": (0.0,)}, "positive"),
        ({"mach_list": (1.501, 1.504)}, "two decimals"),
        ({"ref_area": -1.0, "ref_length": 1.0}, "positive"),
        ({"bogus": 1}, "Unknown settings"),
    ],
)
def test_setup_rejects_bad_settings(settings: dict[str, object], message: str) -> None:
    vehicle = BaseVehicleConfig.from_toml(HARPOON_PATH)
    with pytest.raises((ValueError, TypeError), match=message):
        SU2ConfigGeneration().setup(vehicle, enable_logging=False, **settings)


def test_logged_run_writes_decks_and_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vehicle = BaseVehicleConfig.from_toml(HARPOON_PATH)
    monkeypatch.chdir(tmp_path)
    analysis = SU2ConfigGeneration()
    analysis.setup(vehicle, mach_list=(1.5, 2.5), alpha_list_deg=(0.0,))
    results = analysis.execute()

    artifacts = tmp_path / analysis.logger.artifacts_dir
    decks = sorted(p.name for p in artifacts.glob("*.cfg"))
    assert decks == ["su2_mach1p50_aoa0p00.cfg", "su2_mach2p50_aoa0p00.cfg"]
    manifest = json.loads((artifacts / "run_manifest.json").read_text())
    assert [entry["filename"] for entry in manifest] == [c.filename for c in results.cases]
