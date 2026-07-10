# MELprop-IADE | tests.unit.test_suave_baseline | v0.1.0
"""Unit tests for analyses.suave.ramp_suave_baseline.

Covers the common JSON schema, the Night-3 / P1-C cruise-thrust
consistency check, and the SUAVE-unavailable -> 0D-fallback trigger path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from analyses.suave import ramp_suave_baseline as suave_baseline

RESULTS_JSON_PATH = (
    Path(__file__).resolve().parents[2]
    / "analyses"
    / "suave"
    / "results"
    / "suave_baseline_mission.json"
)

NIGHT3_TH2_REFERENCE_N = 19107.4
"""Night-3 / P1-C operational-envelope Th2 at Mach 2.5 / 6000 m ISA
(analyses/mission/results/operational_envelope.csv)."""


def _sample_burnout_state() -> dict[str, Any]:
    """A representative burnout_state.json-shaped dict for isolated tests."""
    return {
        "burnout_time_s": 6.0,
        "burnout_velocity_ms": 413.4954681723758,
        "burnout_mach": 1.2331842209591797,
        "burnout_altitude_m": 1289.3437240001513,
        "range_at_burnout_m": 167.46366604857533,
        "metadata": {"thrust_used_N": 25374.706875},
    }


def test_fallback_mission_json_has_required_keys() -> None:
    """The fallback mission dict has mission_type, segments, total_range_m, notes."""
    mission_data = suave_baseline.build_mission_fallback(_sample_burnout_state())
    assert "mission_type" in mission_data
    assert "segments" in mission_data
    assert "total_range_m" in mission_data
    assert "notes" in mission_data
    assert isinstance(mission_data["segments"], list)
    assert len(mission_data["segments"]) == 2


def test_fallback_mission_total_range_is_positive() -> None:
    """total_range_m > 0 for the fallback baseline mission."""
    mission_data = suave_baseline.build_mission_fallback(_sample_burnout_state())
    assert mission_data["total_range_m"] > 0.0


def test_fallback_cruise_thrust_matches_night3_reference_within_5_percent() -> None:
    """Cruise segment thrust_N matches the Night-3 / P1-C Th2 (19107.4 N, ±5%).

    Reference: analyses/mission/results/operational_envelope.csv, row
    mach=2.5, altitude_m=6000.0 (Th2_N=19107.352...).
    """
    mission_data = suave_baseline.build_mission_fallback(_sample_burnout_state())
    cruise_segment = next(
        s for s in mission_data["segments"] if s["name"] == "cruise_stage_2_ramjet"
    )
    assert cruise_segment["thrust_N"] == pytest.approx(NIGHT3_TH2_REFERENCE_N, rel=0.05)


def test_fallback_cruise_drag_matches_night3_reference_within_5_percent() -> None:
    """Cruise segment drag_N matches the post-2026-07-10-geometry reference
    (2269.65 N, +/-5%).

    2026-07-10: body diameter dropped from 0.250 m (Fusion) to 0.200 m
    (drawing-verified), shrinking Aref by (0.200/0.250)^2 = 0.64. Drag
    scales directly with Aref (drag = 0.5*rho*V^2*Aref*CD0), so the old
    Night-3 reference (3546.3 N) * 0.64 = 2269.6 N -- matches the new
    computed value almost exactly, confirming this is a clean consequence
    of the confirmed diameter change, not a code bug.
    """
    mission_data = suave_baseline.build_mission_fallback(_sample_burnout_state())
    cruise_segment = next(
        s for s in mission_data["segments"] if s["name"] == "cruise_stage_2_ramjet"
    )
    assert cruise_segment["drag_N"] == pytest.approx(2269.65, rel=0.05)


def test_fallback_segment_names_and_order() -> None:
    """Segments are ordered boost_stage_1 then cruise_stage_2_ramjet."""
    mission_data = suave_baseline.build_mission_fallback(_sample_burnout_state())
    names = [s["name"] for s in mission_data["segments"]]
    assert names == ["boost_stage_1", "cruise_stage_2_ramjet"]


def test_segment_schema_fields_present_and_finite() -> None:
    """Every segment carries the 8 common-schema fields, all finite."""
    import math

    mission_data = suave_baseline.build_mission_fallback(_sample_burnout_state())
    required_fields = {
        "name",
        "duration_s",
        "range_m",
        "mach_start",
        "mach_end",
        "altitude_m",
        "thrust_N",
        "drag_N",
    }
    for seg in mission_data["segments"]:
        assert required_fields.issubset(seg.keys())
        assert math.isfinite(seg["duration_s"])
        assert math.isfinite(seg["range_m"])
        assert seg["duration_s"] > 0.0
        assert seg["range_m"] > 0.0


def test_probe_suave_available_is_false_in_this_container() -> None:
    """SUAVE_AVAILABLE is False: only an empty namespace-package stub exists.

    The repo root ships an empty ``SUAVE/version.py`` namespace-package
    stub that shadows the real ``trunk/SUAVE`` fork, so a plain
    ``import SUAVE`` succeeds but ``SUAVE.Analyses`` does not exist.
    """
    assert suave_baseline.SUAVE_AVAILABLE is False


def test_build_mission_suave_raises_not_implemented_when_unavailable() -> None:
    """build_mission_suave raises NotImplementedError when SUAVE is unavailable."""
    with pytest.raises(NotImplementedError):
        suave_baseline.build_mission_suave(_sample_burnout_state())


def test_run_baseline_mission_falls_back_when_suave_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_baseline_mission() falls back to 0D when SUAVE_AVAILABLE is False.

    Monkeypatches SUAVE_AVAILABLE to False (already the real value in this
    container, but pinned explicitly here so the test is meaningful even
    if a real SUAVE install is ever added to sys.path) and asserts the
    returned mission_type is the fallback tag, not the SUAVE-solve tag.
    """
    monkeypatch.setattr(suave_baseline, "SUAVE_AVAILABLE", False)
    mission_data = suave_baseline.run_baseline_mission(_sample_burnout_state())
    assert mission_data["mission_type"] == "ramp_suave_baseline_0D_fallback"


def test_run_baseline_mission_falls_back_when_suave_solve_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_baseline_mission() falls back to 0D if build_mission_suave raises.

    Simulates SUAVE being importable (SUAVE_AVAILABLE True) but the actual
    mission solve failing (e.g. a real trunk/SUAVE install with an
    incompatible dependency), asserting the NotImplementedError is caught
    and the 0D fallback is used instead of propagating.
    """

    def _raise_not_implemented(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("simulated SUAVE solve failure")

    monkeypatch.setattr(suave_baseline, "SUAVE_AVAILABLE", True)
    monkeypatch.setattr(suave_baseline, "build_mission_suave", _raise_not_implemented)
    mission_data = suave_baseline.run_baseline_mission(_sample_burnout_state())
    assert mission_data["mission_type"] == "ramp_suave_baseline_0D_fallback"


def test_committed_results_json_exists_and_matches_schema() -> None:
    """The committed results/suave_baseline_mission.json matches the schema.

    Skips if the results artifact has not been generated yet (run
    ``python3 analyses/suave/ramp_suave_baseline.py`` first).
    """
    if not RESULTS_JSON_PATH.exists():
        pytest.skip("suave_baseline_mission.json not generated yet")

    import json

    data = json.loads(RESULTS_JSON_PATH.read_text(encoding="utf-8"))
    assert {"mission_type", "segments", "total_range_m", "notes"}.issubset(data.keys())
    assert data["total_range_m"] > 0.0
