# MELprop-IADE | tests.unit.test_stability_datcom | v0.1.0
"""Unit tests for DATCOM-class supersonic stability and Ackeret fin check."""

import csv
import math
import sys
from pathlib import Path

import pytest

# Inject repo root onto sys.path for pytest (as tests/conftest.py does).
if sys.path[0] != str(Path(__file__).resolve().parents[4]):
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from IADE_Core.modules.stability.ackeret_fin_check import (
    CRUISE_MACH,
    ackeret_fin_cn_alpha_and_cp,
    compute_whole_vehicle_sm_ackeret,
)
from IADE_Core.modules.stability.datcom_class_sweep import (
    CG_FRACTIONS,
    MACH_SWEEP,
    CSV_PATH,
    compute_static_margin_datcom,
    fin_cn_alpha_and_cp_supersonic,
    load_geometry,
    nose_cone_cn_alpha_and_cp_supersonic,
    run_sweep,
)


@pytest.fixture(scope="module")
def geometry():
    """Load ramP geometry once for all tests."""
    return load_geometry()


def test_datcom_sweep_runs_full_grid(geometry):
    """Sweep covers full grid (6 Mach x 4 CG = 24 points)."""
    results = run_sweep(geometry, MACH_SWEEP, CG_FRACTIONS)
    assert len(results) == len(MACH_SWEEP) * len(CG_FRACTIONS)


def test_datcom_csv_has_required_columns():
    """CSV has all required columns."""
    assert CSV_PATH.exists(), f"CSV not found: {CSV_PATH}"
    with CSV_PATH.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        required = [
            "mach",
            "cg_frac",
            "cg_from_nose_m",
            "cn_alpha_total",
            "x_cp_m",
            "static_margin_cal",
            "stable_bool",
            "regime_flag",
        ]
        for field in required:
            assert field in fieldnames, f"Missing CSV column: {field}"


def test_datcom_sm_decreases_as_cg_moves_aft(geometry):
    """Static margin decreases monotonically as CG moves aft (at fixed Mach)."""
    mach = 2.5
    cg_fracs = sorted(CG_FRACTIONS)
    sm_values = []
    for cg_frac in cg_fracs:
        cg_from_nose_m = cg_frac * geometry.total_length_m
        res = compute_static_margin_datcom(geometry, mach, cg_from_nose_m)
        sm_values.append(res["static_margin_cal"])
    # SM should decrease as CG moves aft (CG approaches CP).
    for i in range(len(sm_values) - 1):
        assert (
            sm_values[i] > sm_values[i + 1]
        ), f"SM not monotonic: {sm_values[i]} vs {sm_values[i+1]}"


def test_datcom_beta_guard_at_mach_one(geometry):
    """Fin function raises ValueError at M=1.0 (beta=0)."""
    with pytest.raises(ValueError, match="mach > 1.0"):
        fin_cn_alpha_and_cp_supersonic(geometry, 1.0)


def test_datcom_subsonic_guard(geometry):
    """Fin function raises ValueError for M<1.0 (subsonic, out of regime)."""
    with pytest.raises(ValueError, match="mach > 1.0"):
        fin_cn_alpha_and_cp_supersonic(geometry, 0.8)


def test_datcom_nose_cp_is_cone_factor(geometry):
    """Nose CP uses 2/3 L_nose (cone supersonic factor, NOT 0.466 ogive)."""
    cn_alpha, x_cp = nose_cone_cn_alpha_and_cp_supersonic(geometry)
    expected_cp = (2.0 / 3.0) * geometry.nose_length_m
    assert math.isclose(x_cp, expected_cp, abs_tol=1e-9)


def test_datcom_components_positive_at_supersonic(geometry):
    """All component CN_alpha values are positive at supersonic Mach."""
    mach = 2.5
    cg_from_nose_m = geometry.cg_from_nose_m
    res = compute_static_margin_datcom(geometry, mach, cg_from_nose_m)
    assert res["cn_alpha_nose"] > 0
    assert res["cn_alpha_transition"] > 0
    assert res["cn_alpha_fins"] > 0
    assert res["cn_alpha_total"] > 0


def test_ackeret_fin_runs_at_cruise(geometry):
    """Ackeret fin check runs at cruise Mach without error."""
    cn_alpha, x_cp = ackeret_fin_cn_alpha_and_cp(geometry, CRUISE_MACH)
    assert cn_alpha > 0
    assert x_cp > 0


def test_ackeret_vs_datcom_fin_cp_within_one_caliber(geometry):
    """Ackeret fin CP agrees with DATCOM fin CP within one caliber at Ma 2.5."""
    mach = 2.5
    cn_datcom, x_datcom = fin_cn_alpha_and_cp_supersonic(geometry, mach)
    cn_ackeret, x_ackeret = ackeret_fin_cn_alpha_and_cp(geometry, mach)

    # Check CP location (should be byte-identical or very close).
    # In this implementation, both use the same 50% MAC + sweep formula, so expect exact match.
    assert math.isclose(x_datcom, x_ackeret, abs_tol=geometry.d_ref_m), (
        f"DATCOM fin CP {x_datcom:.6f} m vs Ackeret {x_ackeret:.6f} m "
        f"differ by more than one caliber ({geometry.d_ref_m:.4f} m)"
    )

    # Check CN_alpha sign (both should be positive, stabilizing).
    assert cn_datcom > 0
    assert cn_ackeret > 0


def test_ackeret_whole_vehicle_sm_positive_at_cruise(geometry):
    """Ackeret whole-vehicle SM is positive (stable) at cruise, config CG."""
    cg_from_nose_m = geometry.cg_from_nose_m
    res = compute_whole_vehicle_sm_ackeret(geometry, CRUISE_MACH, cg_from_nose_m)
    assert res["static_margin_cal"] > 0
    assert res["stable_bool"] is True


def test_ackeret_beta_guard_at_mach_one(geometry):
    """Ackeret fin function raises ValueError at M=1.0 (beta=0)."""
    with pytest.raises(ValueError, match="mach > 1.0"):
        ackeret_fin_cn_alpha_and_cp(geometry, 1.0)


# DO NOT hard-code a pass/fail verdict on vehicle stability — report numbers, don't force a conclusion.
