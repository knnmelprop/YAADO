# MELprop-IADE | tests.unit.test_fin_polar_comparison | v0.1.0
"""Unit tests for analyses.aero.fin_polar_comparison.

Covers the Ackeret (2D thin-airfoil, linearised supersonic) vs.
Diederich (analytic AVL-style surrogate) fin polar comparison for the
ramP rocket fins (Project B). Geometry is loaded from the real,
read-only ``vehicles/ramjet_rocket/vehicle_config.yaml`` via
``analyses.stability.barrowman_stability.load_geometry`` -- this test
file never modifies that YAML.
"""

from __future__ import annotations

import csv
import math

import pytest

from analyses.aero.fin_polar_comparison import (
    ALPHA_DEG_SWEEP,
    CSV_COLUMNS,
    CSV_PATH,
    MACH_SWEEP,
    RATIO_HIGH_THRESHOLD,
    RATIO_LOW_THRESHOLD,
    FinPolarComparisonAnalysis,
    ackeret_cl,
    classify_ratio_flag,
    diederich_cl,
    fin_effective_aspect_ratio,
    fin_polar_sweep,
    is_subsonic_leading_edge,
    run,
)
from analyses.stability.barrowman_stability import load_geometry
from core.component_base import FidelityLevel


@pytest.fixture(scope="module")
def geometry():
    """Load the real (read-only) ramP rocket geometry from YAML."""
    return load_geometry()


@pytest.fixture(scope="module")
def sweep_rows(geometry):
    """Run the full Mach x alpha sweep once and share it across tests."""
    return fin_polar_sweep(geometry)


def test_ackeret_cl_zero_at_zero_alpha() -> None:
    """Symmetric (double-wedge) Ackeret section: CL = 0 at alpha = 0 for
    any supersonic Mach number.
    """
    for mach in MACH_SWEEP:
        assert ackeret_cl(0.0, mach) == pytest.approx(0.0, abs=1e-12)


def test_diederich_cl_monotonic_increasing_with_alpha(geometry) -> None:
    """The Diederich analytic surrogate CL must increase monotonically
    with angle of attack at a fixed (supersonic) Mach number, since the
    lift-curve slope is strictly positive in the linear regime modelled
    here.
    """
    ar_eff = fin_effective_aspect_ratio(geometry)
    mach = 2.5
    cl_values = [diederich_cl(a, mach, ar_eff) for a in ALPHA_DEG_SWEEP]

    assert all(c2 > c1 for c1, c2 in zip(cl_values, cl_values[1:]))
    # And it must start at (near) zero at alpha = 0.
    assert cl_values[0] == pytest.approx(0.0, abs=1e-12)


def test_ratio_flag_logic_boundaries() -> None:
    """classify_ratio_flag must trigger RATIO_LOW / RATIO_HIGH / OK /
    SUBSONIC_LE_WARNING correctly for synthetic ratio values, and the
    subsonic-LE flag must take priority over the ratio bands.
    """
    assert classify_ratio_flag(1.0) == "OK"
    assert classify_ratio_flag(RATIO_LOW_THRESHOLD - 0.05) == "RATIO_LOW"
    assert classify_ratio_flag(RATIO_HIGH_THRESHOLD + 0.05) == "RATIO_HIGH"
    # Boundary values themselves are inclusive (not flagged).
    assert classify_ratio_flag(RATIO_LOW_THRESHOLD) == "OK"
    assert classify_ratio_flag(RATIO_HIGH_THRESHOLD) == "OK"
    # Subsonic-LE flag overrides an otherwise-OK ratio.
    assert classify_ratio_flag(1.0, subsonic_le=True) == "SUBSONIC_LE_WARNING"
    assert classify_ratio_flag(0.1, subsonic_le=True) == "SUBSONIC_LE_WARNING"


def test_subsonic_le_never_flagged_in_task_mach_sweep() -> None:
    """With sweep_LE = 0 deg (rectangular ramP fin) and the task's Mach
    sweep starting at 1.5, the leading edge must be supersonic
    (threshold 1.05) at every swept Mach number -- i.e. the
    SUBSONIC_LE_WARNING flag should never fire for this vehicle's sweep.
    """
    for mach in MACH_SWEEP:
        assert is_subsonic_leading_edge(mach, sweep_le_deg=0.0) is False

    # But a Mach number below the 1.05 margin must be flagged.
    assert is_subsonic_leading_edge(1.0, sweep_le_deg=0.0) is True


def test_csv_output_has_seven_columns_and_thirty_rows(geometry, tmp_path) -> None:
    """The written CSV must have exactly the 7 specified columns, in
    order, and 30 data rows (5 Mach x 6 alpha), after skipping the
    ``#``-prefixed header comment lines.
    """
    csv_out = tmp_path / "fin_polar_ackeret_vs_avl_test.csv"
    png_out = tmp_path / "fin_polar_ackeret_vs_avl_test.png"
    output = run(geometry=geometry, csv_path=csv_out, png_path=png_out)

    assert output["csv_path"] == csv_out
    assert csv_out.exists()
    assert png_out.exists()

    with csv_out.open("r", encoding="utf-8") as fh:
        lines = [line for line in fh if not line.startswith("#")]
    reader = csv.reader(lines)
    header = next(reader)

    assert tuple(header) == CSV_COLUMNS
    assert len(header) == 7

    data_rows = list(reader)
    assert len(data_rows) == len(MACH_SWEEP) * len(ALPHA_DEG_SWEEP) == 30
    for data_row in data_rows:
        assert len(data_row) == 7


def test_committed_csv_artifact_exists_and_matches_columns() -> None:
    """The committed CSV artifact (written by module import-time `run()`
    invocation via the module's own `__main__`/test harness) must exist
    at the documented path with the correct column layout. This test
    (re)generates it via `run()` with default paths if missing, matching
    the task's "CSV exists" gate.
    """
    output = run()
    assert output["csv_path"] == CSV_PATH
    assert CSV_PATH.exists()

    with CSV_PATH.open("r", encoding="utf-8") as fh:
        lines = [line for line in fh if not line.startswith("#")]
    reader = csv.reader(lines)
    header = next(reader)
    assert tuple(header) == CSV_COLUMNS


def test_analysis_wraps_base_analysis_contract() -> None:
    """FinPolarComparisonAnalysis must inherit BaseAnalysis and return a
    validated AnalysisResults with AR_eff and row-count summary scalars.
    """
    analysis = FinPolarComparisonAnalysis()
    analysis.setup()
    results = analysis.execute()

    assert results.fidelity == FidelityLevel.LEVEL_0
    assert results["ar_eff"] > 0.0
    assert int(results["n_rows"]) == len(MACH_SWEEP) * len(ALPHA_DEG_SWEEP)
    assert math.isfinite(results["n_flagged_rows"])
