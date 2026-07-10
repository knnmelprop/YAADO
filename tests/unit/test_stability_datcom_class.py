# MELprop-IADE | tests.unit.test_stability_datcom_class | v0.1.0
"""Unit tests for DATCOM-class supersonic stability and Ackeret fin check.

Covers:
  - analyses.stability.datcom_class_sweep (supersonic component buildup)
  - analyses.stability.ackeret_fin_check (independent fin cross-check)

Both modules are tested against the ramjet rocket geometry from
vehicles/ramjet_rocket/vehicle_config.yaml (read-only).
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

from analyses.stability.ackeret_fin_check import (
    ackeret_fin_cn_alpha_and_cp,
    run_ackeret_check,
)
from analyses.stability.barrowman_stability import load_geometry
from analyses.stability.datcom_class_sweep import (
    CG_FROM_NOSE_MIN,
    CG_FROM_NOSE_MAX,
    MACH_SUPERSONIC_MIN,
    DATCOMClassAnalysis,
    compute_datcom_at_mach_cg,
    run_datcom_sweep,
)


@pytest.fixture(scope="module")
def geometry():
    """Load the real (read-only) ramP rocket geometry from YAML."""
    return load_geometry()


def test_datcom_csv_produced_and_has_correct_columns(geometry, tmp_path) -> None:
    """The DATCOM sweep must produce a CSV with the 8 required columns."""
    csv_out = tmp_path / "datcom_test.csv"
    png_out = tmp_path / "datcom_test.png"

    results = run_datcom_sweep(geometry, csv_path=csv_out, png_path=png_out)

    assert csv_out.exists()
    assert png_out.exists()
    assert len(results) > 0

    with csv_out.open("r", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)

    expected_columns = [
        "mach",
        "cg_m",
        "cn_alpha_body",
        "cn_alpha_fins",
        "cn_alpha_total",
        "x_cp_m",
        "static_margin_cal",
        "regime_flag",
    ]
    assert tuple(header) == tuple(expected_columns)


def test_datcom_cn_alpha_total_positive_and_finite_at_mach_25(geometry) -> None:
    """At Mach 2.5 for a mid-sweep CG, CN_alpha_total must be > 0 and finite."""
    cg_mid = (CG_FROM_NOSE_MIN + CG_FROM_NOSE_MAX) / 2.0
    result = compute_datcom_at_mach_cg(geometry, mach=2.5, cg_m=cg_mid)

    assert math.isfinite(result.cn_alpha_total)
    assert result.cn_alpha_total > 0.0
    assert result.regime_flag == "VALID"


def test_datcom_static_margin_is_finite_and_reported_as_range(geometry) -> None:
    """Static margin at Mach 2.5 must be finite across the CG sweep,
    and the min/max across the sweep must differ (not a single value).
    """
    results = run_datcom_sweep(geometry)

    mach_25_results = [r for r in results if abs(r.mach - 2.5) < 0.01]
    assert len(mach_25_results) > 1

    sm_vals = [r.static_margin_cal for r in mach_25_results]
    assert all(math.isfinite(sm) for sm in sm_vals)

    sm_min = min(sm_vals)
    sm_max = max(sm_vals)
    assert sm_min != sm_max  # Range exists.


def test_ackeret_and_datcom_agree_in_sign_at_mach_25_nominal_cg(geometry) -> None:
    """At Mach 2.5, CG=1.6084, both methods must produce static margins
    with the same SIGN (both positive or both negative).
    """
    cg_nominal = 1.6084

    # DATCOM.
    datcom_result = compute_datcom_at_mach_cg(geometry, mach=2.5, cg_m=cg_nominal)
    sm_datcom = datcom_result.static_margin_cal

    # Ackeret.
    ackeret_result = run_ackeret_check(geometry, mach=2.5, cg_m=cg_nominal)
    sm_ackeret = ackeret_result["static_margin_cal"]

    # Sign agreement.
    assert math.isfinite(sm_datcom)
    assert math.isfinite(sm_ackeret)
    assert (sm_datcom > 0) == (sm_ackeret > 0)  # Same sign.


def test_beta_ar_e_clamp_does_not_produce_negative_cn_alpha(geometry) -> None:
    """At low Mach (M < 1.2) where beta*AR_e < 1, the fin CN_alpha must
    not go negative (the clamp ensures the tip correction >= 0).
    """
    for mach in [0.5, 0.8, 1.0]:
        result = compute_datcom_at_mach_cg(geometry, mach=mach, cg_m=1.6)
        # The fin term should be clamped to zero at low Mach.
        assert result.cn_alpha_fins >= 0.0
        # But the body term is always positive.
        assert result.cn_alpha_body > 0.0
        assert result.regime_flag == "OUT_OF_METHOD_REGIME"


def test_ackeret_fin_check_produces_markdown(geometry, tmp_path) -> None:
    """The Ackeret fin check must produce a markdown file."""
    md_out = tmp_path / "ackeret_test.md"
    result = run_ackeret_check(geometry, md_path=md_out)

    assert md_out.exists()
    assert result["cn_alpha_total"] > 0.0
    assert math.isfinite(result["static_margin_cal"])


def test_ackeret_requires_supersonic_mach(geometry) -> None:
    """ackeret_fin_cn_alpha_and_cp must raise ValueError for Mach <= 1."""
    with pytest.raises(ValueError, match="Mach > 1"):
        ackeret_fin_cn_alpha_and_cp(geometry, mach=0.8)

    with pytest.raises(ValueError, match="Mach > 1"):
        ackeret_fin_cn_alpha_and_cp(geometry, mach=1.0)


def test_datcom_analysis_base_analysis_contract(geometry) -> None:
    """DATCOMClassAnalysis must inherit BaseAnalysis and return a
    validated AnalysisResults.
    """
    analysis = DATCOMClassAnalysis()
    analysis.setup()
    results = analysis.execute()

    assert results.name == "datcom_class_sweep"
    assert "static_margin_range_cal" in results.data
    sm_range = results.data["static_margin_range_cal"]
    assert isinstance(sm_range, tuple)
    assert len(sm_range) == 2
    assert sm_range[0] < sm_range[1]  # min < max

    assert results.metadata["method"] == "datcom_class_supersonic_buildup"
    assert analysis.validate_results(results)


def test_datcom_execute_before_setup_raises_runtime_error() -> None:
    """Calling execute() before setup() must raise RuntimeError."""
    analysis = DATCOMClassAnalysis()
    with pytest.raises(RuntimeError, match="called before setup"):
        analysis.execute()
