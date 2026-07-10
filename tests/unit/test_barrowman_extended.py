# MELprop-IADE | tests.unit.test_barrowman_extended | v0.1.0
"""Unit tests for analyses.aero.barrowman_extended.

Covers the extended (Galejs body-lift + reused Prandtl-Glauert/Ackeret)
Barrowman fin-span sensitivity analysis for the ramP rocket (Project B).
All geometry is loaded from the real, read-only
``vehicles/ramjet_rocket/vehicle_config.yaml`` via
``analyses.stability.barrowman_stability.load_geometry`` -- this test
file never modifies that YAML.
"""

from __future__ import annotations

import csv
import math

import pytest

from analyses.aero.barrowman_extended import (
    CSV_COLUMNS,
    COMPARISON_MACH,
    CSV_PATH,
    TELTIK_CFD_SM_CAL,
    SM_REVIEW_THRESHOLD_CAL,
    BarrowmanExtendedAnalysis,
    compute_extended_stability_at_mach,
    evaluate_span,
    find_neutral_span_m,
    fin_span_sweep,
    galejs_body_cn_alpha_and_cp,
    run,
    static_margin_cal,
)
from analyses.stability.barrowman_stability import (
    compute_stability_at_mach,
    fin_mach_correction_factor,
    load_geometry,
)
from core.component_base import FidelityLevel


@pytest.fixture(scope="module")
def geometry():
    """Load the real (read-only) ramP rocket geometry from YAML."""
    return load_geometry()


@pytest.fixture(scope="module")
def sweep_rows(geometry):
    """Run the fin-span sweep once and share it across tests."""
    return fin_span_sweep(geometry)


def test_sm_decreases_monotonically_as_fin_span_decreases(sweep_rows) -> None:
    """SM_cal (both basic and extended) must be monotonically increasing
    in fin span -- equivalently, decreasing as fin span shrinks -- since
    larger fins add more aft-of-CG normal-force authority.

    ``sweep_rows`` is sorted by increasing ``fin_span_factor``.
    """
    basic = [r.sm_cal_basic for r in sweep_rows]
    extended = [r.sm_cal_extended for r in sweep_rows]

    assert all(b2 > b1 for b1, b2 in zip(basic, basic[1:]))
    assert all(e2 > e1 for e1, e2 in zip(extended, extended[1:]))


def test_galejs_body_lift_shifts_cp_forward(geometry) -> None:
    """The Galejs body-lift correction moves the *combined* CP forward
    (destabilizing), not aft.

    Physical direction check: in isolation, the Galejs body-lift CP
    (the planform-area centroid of the whole body) sits well *aft* of
    the nose/transition CPs, near the middle of the long cylindrical
    afterbody. But once its CN_alpha is folded into the CN_alpha-weighted
    combined CP alongside the much-larger-magnitude, further-aft fin
    term, adding the body term *dilutes* the fins' dominance of the
    weighted average -- pulling the combined CP toward the more-forward
    nose/transition/body cluster and away from the far-aft fin CP. The
    net, measurable effect at this vehicle's actual geometry is
    therefore a **forward** shift of the combined CP and a **lower**
    (less positive) static margin, which is what this test asserts.
    """
    basic = compute_stability_at_mach(geometry, mach=COMPARISON_MACH)
    extended = compute_extended_stability_at_mach(geometry, mach=COMPARISON_MACH)

    # Forward shift: extended combined CP is upstream (smaller x) of the
    # basic (nose+transition+fin-only) combined CP.
    assert extended.x_cp_extended_m < basic.x_cp_m

    sm_basic = static_margin_cal(basic.x_cp_m, geometry.cg_from_nose_m, geometry.d_ref_m)
    sm_extended = static_margin_cal(
        extended.x_cp_extended_m, geometry.cg_from_nose_m, geometry.d_ref_m
    )
    assert sm_extended < sm_basic

    # The body-lift CN_alpha itself must be a positive normal-force-curve
    # slope (a sign error here would silently subtract rather than add).
    cn_body, x_body = galejs_body_cn_alpha_and_cp(geometry)
    assert cn_body > 0.0
    assert 0.0 < x_body < geometry.total_length_m


def test_prandtl_glauert_ackeret_correction_supersonic_finite_positive() -> None:
    """The fin compressibility correction for Ma > 1.2 must be finite
    and strictly positive.

    Per task instruction, this module reuses
    ``barrowman_stability.fin_mach_correction_factor`` rather than
    re-deriving the Prandtl-Glauert/Ackeret correction, to avoid
    double-applying it. This test exercises that reused function
    directly at the module's own comparison condition (Ma 2.5) and at a
    couple of other supersonic points, confirming the values Feeding
    into :func:`compute_extended_stability_at_mach` are physically sane.
    """
    for mach in (1.21, 2.0, COMPARISON_MACH, 3.5):
        factor = fin_mach_correction_factor(mach)
        assert math.isfinite(factor)
        assert factor > 0.0


def test_neutral_span_found_finite_and_less_than_yaml_span(geometry) -> None:
    """A neutral-stability (SM_cal = 0) fin span must exist, be finite,
    and be smaller than the current YAML fin span (0.550 m as of
    2026-07-10) -- i.e. the rocket would need *less* fin than currently
    specified to reach neutral stability at Ma 2.5.

    2026-07-10: body diameter dropped from 0.250 m (Fusion) to 0.200 m
    (drawing-verified, see vehicle_config.yaml cfd_notes), which changes
    the body's CN_alpha/CP per Barrowman theory and therefore legitimately
    changes this result -- NOT a code bug. The old cross-check value
    (~0.1391 m) came from docs/ramP/stability_reconciliation.md, computed
    under the old 0.250 m geometry via the same compute_stability_at_mach()
    code path; that doc is now stale and needs re-running, not this test.
    """
    neutral_span_m, variant = find_neutral_span_m(geometry)

    assert math.isfinite(neutral_span_m)
    assert neutral_span_m > 0.0
    assert neutral_span_m < geometry.fin_span_m
    assert isinstance(variant, str) and len(variant) > 0

    # Cross-check: recomputed under the 2026-07-10 geometry update
    # (body diameter 0.200 m). Old value under 0.250 m was ~0.1391 m.
    assert neutral_span_m == pytest.approx(0.1151, rel=0.02)


def test_csv_output_has_all_ten_required_columns(geometry, tmp_path) -> None:
    """The written CSV must have exactly the ten specified columns, in
    order, after skipping the ``#``-prefixed header comment lines.
    """
    csv_out = tmp_path / "SM_sensitivity_fin_span_test.csv"
    png_out = tmp_path / "SM_sensitivity_fin_span_test.png"
    output = run(geometry=geometry, csv_path=csv_out, png_path=png_out)

    assert output["csv_path"] == csv_out
    assert csv_out.exists()
    assert png_out.exists()

    with csv_out.open("r", encoding="utf-8") as fh:
        lines = [line for line in fh if not line.startswith("#")]
    reader = csv.reader(lines)
    header = next(reader)

    assert tuple(header) == CSV_COLUMNS
    assert len(header) == 10

    data_rows = list(reader)
    assert len(data_rows) == 9  # FIN_SPAN_SWEEP_POINTS
    for data_row in data_rows:
        assert len(data_row) == 10


def test_yaml_geometry_flags_stability_review_needed(geometry) -> None:
    """At the current YAML fin span, SM_extended is still well above the
    +2 cal review threshold, so the committed CSV must carry the
    ``# STABILITY_REVIEW_NEEDED`` marker line (task item 6) and
    ``BarrowmanExtendedAnalysis`` must surface the same flag in metadata.
    """
    row = evaluate_span(geometry, geometry.fin_span_m)
    assert row.sm_cal_extended > SM_REVIEW_THRESHOLD_CAL

    with CSV_PATH.open("r", encoding="utf-8") as fh:
        header_lines = [line for line in fh if line.startswith("#")]
    assert any("STABILITY_REVIEW_NEEDED" in line for line in header_lines)
    assert any(f"{TELTIK_CFD_SM_CAL:.2f}" in line for line in header_lines)


def test_analysis_wraps_base_analysis_contract() -> None:
    """BarrowmanExtendedAnalysis must inherit BaseAnalysis and return a
    validated AnalysisResults with the key summary scalars.
    """
    analysis = BarrowmanExtendedAnalysis()
    analysis.setup()
    results = analysis.execute()

    assert results.fidelity == FidelityLevel.LEVEL_0
    assert results["sm_extended_cal"] < results["sm_basic_cal"]
    assert results["neutral_span_m"] < results["fin_span_yaml_m"]
    assert results.metadata["review_needed"] is True
