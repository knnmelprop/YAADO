# MELprop-IADE | tests.unit.test_aero_drag_polar | v0.1.0
"""Unit tests for analyses.aero.drag_polar (ramP supersonic drag buildup)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from analyses.aero.drag_polar import (
    MACH_GRID,
    MIN_MACH_ABSOLUTE,
    DragPolarAnalysis,
    base_drag_cd,
    body_wave_drag_cd,
    compute_drag_polar_grid,
    compute_drag_polar_point,
    fin_wave_drag_cd,
    main as drag_polar_main,
    skin_friction_cd,
    teltik_validation,
    write_csv,
)
from analyses.mission.operational_envelope import (
    NIGHT3_ALTITUDE_M,
    TELTIK_CFD_DRAG_N_REF,
    reference_area_m2,
)
from core.component_base import FidelityLevel


AREF_M2 = reference_area_m2()


def test_components_positive_and_total_equals_sum() -> None:
    """All four components at Ma 2.5 are positive and sum to cd0_total."""
    point = compute_drag_polar_point(2.5, NIGHT3_ALTITUDE_M, AREF_M2)

    assert point.cd_body_wave > 0.0
    assert point.cd_friction > 0.0
    assert point.cd_fin_wave > 0.0
    assert point.cd_base > 0.0

    component_sum = (
        point.cd_body_wave + point.cd_friction + point.cd_fin_wave + point.cd_base
    )
    assert point.cd0_total == pytest.approx(component_sum, rel=1e-12)


def test_cd0_decreasing_over_mach_sweep() -> None:
    """CD0_total decreases monotonically as Mach increases 1.5 -> 3.5."""
    points = compute_drag_polar_grid(MACH_GRID, NIGHT3_ALTITUDE_M, AREF_M2)
    totals = [p.cd0_total for p in points]

    assert len(totals) == len(MACH_GRID)
    for i in range(len(totals) - 1):
        assert totals[i] >= totals[i + 1], (
            f"CD0 not decreasing at index {i}: {totals[i]} -> {totals[i + 1]}"
        )
    assert totals[0] > totals[-1]


def test_teltik_delta_present_and_not_tuned() -> None:
    """Teltik validation reports drag_N, implied CD0, and honest deltas."""
    validation = teltik_validation(AREF_M2)

    assert validation["mach"] == 2.5
    assert validation["teltik_drag_N_ref"] == TELTIK_CFD_DRAG_N_REF
    assert "delta_drag_N" in validation
    assert "delta_drag_pct" in validation
    assert "teltik_implied_cd0" in validation
    assert "delta_cd0_buildup_vs_teltik" in validation
    assert "delta_cd0_placeholder_vs_teltik" in validation
    assert isinstance(validation["note"], str) and len(validation["note"]) > 0

    # drag_N_buildup must be internally consistent with cd0_buildup.
    assert validation["drag_N_buildup"] > 0.0
    # Teltik-implied CD0 must be a sane positive drag coefficient.
    assert 0.0 < validation["teltik_implied_cd0"] < 5.0


def test_mach_at_or_below_1_05_raises_value_error() -> None:
    """All supersonic correlations reject Mach <= MIN_MACH_ABSOLUTE (1.05)."""
    with pytest.raises(ValueError, match="Mach"):
        body_wave_drag_cd(MIN_MACH_ABSOLUTE, AREF_M2)
    with pytest.raises(ValueError, match="Mach"):
        fin_wave_drag_cd(1.0, AREF_M2)
    with pytest.raises(ValueError, match="Mach"):
        base_drag_cd(0.9)
    with pytest.raises(ValueError, match="Mach"):
        compute_drag_polar_point(1.0, NIGHT3_ALTITUDE_M, AREF_M2)

    analysis = DragPolarAnalysis()
    with pytest.raises(ValueError, match="Mach"):
        analysis.setup(mach_values=(1.0, 2.0))


def test_skin_friction_positive_and_finite() -> None:
    """Skin-friction coefficient is a small positive finite number."""
    cf_cd = skin_friction_cd(2.5, NIGHT3_ALTITUDE_M, AREF_M2)
    assert 0.0 < cf_cd < 1.0
    assert math.isfinite(cf_cd)


def test_csv_created_with_required_columns(tmp_path: Path) -> None:
    """write_csv() creates a CSV with the 6 required columns."""
    points = compute_drag_polar_grid(MACH_GRID, NIGHT3_ALTITUDE_M, AREF_M2)
    csv_path = tmp_path / "drag_polar.csv"
    write_csv(points, csv_path)

    assert csv_path.exists()
    header = csv_path.read_text(encoding="utf-8").splitlines()[0]
    expected_columns = {
        "mach",
        "cd_body_wave",
        "cd_friction",
        "cd_fin_wave",
        "cd_base",
        "cd0_total",
    }
    assert set(header.split(",")) == expected_columns


def test_drag_polar_analysis_setup_execute_validate() -> None:
    """DragPolarAnalysis runs end-to-end and self-validates."""
    analysis = DragPolarAnalysis()
    analysis.setup()
    results = analysis.execute()

    assert results.fidelity == FidelityLevel.LEVEL_1
    assert analysis.validate_results(results)
    assert "cd0_at_teltik_point" in results.data
    assert len(results.metadata["grid"]) == len(MACH_GRID)


def test_execute_before_setup_raises() -> None:
    """execute() without setup() must raise RuntimeError."""
    with pytest.raises(RuntimeError):
        DragPolarAnalysis().execute()


def test_main_writes_csv_and_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """main() writes CSV, JSON and PNG outputs."""
    import analyses.aero.drag_polar as drag_polar_module

    csv_path = tmp_path / "drag_polar.csv"
    json_path = tmp_path / "drag_polar.json"
    png_path = tmp_path / "drag_polar.png"
    monkeypatch.setattr(drag_polar_module, "OUTPUT_CSV_PATH", csv_path)
    monkeypatch.setattr(drag_polar_module, "OUTPUT_JSON_PATH", json_path)
    monkeypatch.setattr(drag_polar_module, "OUTPUT_PNG_PATH", png_path)
    monkeypatch.setattr(drag_polar_module, "RESULTS_DIR", tmp_path)

    output = drag_polar_main()

    assert csv_path.exists()
    assert json_path.exists()
    assert png_path.exists()
    assert "data" in output and "metadata" in output
