# MELprop-IADE | tests.unit.test_inlet_actuation | v0.1.0
"""Unit tests for analyses.propulsion.inlet_actuation.

Uses a coarse Mach step (0.5) in every test to keep runtime sane -- the
Nelder-Mead angle optimizer in inlet_performance.py is run once per Mach
point per test, and the full production sweep (step 0.1, 26 points) is
reserved for main().
"""

import csv

import pytest

from IADE_Core.modules.propulsion.inlet_actuation import (
    ConeActuationScheduleAnalysis,
    actuation_range_per_cone_deg,
    build_actuation_schedule,
    mach_band_meeting_mil,
)
from IADE_Core.modules.propulsion.inlet_performance import DEFAULT_N_CONES_M25
from IADE_Core.FlightDeck.component_base import FidelityLevel

COARSE_MACH_STEP = 0.5  # -> Ma = 1.0, 1.5, 2.0, 2.5, 3.0, 3.5 (6 points)


def test_execute_before_setup_raises() -> None:
    """execute() before setup() must raise RuntimeError."""
    analysis = ConeActuationScheduleAnalysis()
    with pytest.raises(RuntimeError):
        analysis.execute()


def test_eta_threshold_pass_at_mach_2p5() -> None:
    """At Ma 2.5 the 4-cone optimum should clear MIL-E-5007D (~eta 0.874)."""
    schedule = build_actuation_schedule(
        mach_min=1.0, mach_max=3.5, mach_step=COARSE_MACH_STEP
    )
    row_2p5 = next(r for r in schedule if r["mach"] == pytest.approx(2.5))
    assert row_2p5["eta_inlet"] == pytest.approx(0.874, abs=0.01)
    assert row_2p5["eta_std"] == pytest.approx(0.8703, abs=0.001)
    assert row_2p5["meets_mil_flag"] is True


def test_low_mach_fails_and_high_mach_can_fail() -> None:
    """Ma <= 1 always FAILS (eta_std saturates at 1.0); report honestly."""
    schedule = build_actuation_schedule(
        mach_min=1.0, mach_max=3.5, mach_step=COARSE_MACH_STEP
    )
    row_sonic = next(r for r in schedule if r["mach"] == pytest.approx(1.0))
    assert row_sonic["eta_std"] == pytest.approx(1.0)
    assert row_sonic["meets_mil_flag"] is False
    assert row_sonic["eta_inlet"] < 1.0


def test_angles_positive_and_bounded_supersonic() -> None:
    """Per-shock incremental deflections and cumulative half-angles are sane.

    Each PER-SHOCK incremental deflection (the actual oblique-shock
    turning angle solved from theta-beta-Mach) must be positive and below
    the ~45 deg detachment ballpark for a gamma=1.4 attached weak
    oblique shock. The CUMULATIVE physical cone half-angle (sum of
    increments up to that stage) is only required to be positive and
    non-decreasing -- it legitimately exceeds 45 deg at the aft stages of
    a high-Mach multi-cone spike (Oswatitsch-style design), since it is a
    geometric surface angle, not a single shock's turning angle, so no
    upper bound is imposed on it here (never tune physics to fit an
    arbitrary bound).

    Ma <= 1.0 rows are excluded (degenerate zero-angle fallback, see
    :func:`_schedule_row`) and rows where the optimizer's seeds all
    detach at that Mach (an expected low-supersonic-Mach failure mode for
    a 4-cone design, ``detached is True``) are excluded from the
    incremental-angle bound check since those angles are leftover seed
    values, not a converged physical optimum.
    """
    schedule = build_actuation_schedule(
        mach_min=1.0, mach_max=3.5, mach_step=COARSE_MACH_STEP
    )
    for row in schedule:
        if row["mach"] <= 1.0:
            continue
        angles = row["theta_half_angles_deg"]
        assert len(angles) == DEFAULT_N_CONES_M25
        for angle in angles:
            assert angle > 0.0
        # Cumulative half-angles must be non-decreasing across cone index.
        assert angles == sorted(angles)

        if row["detached"]:
            continue
        for increment in row["theta_increments_deg"]:
            assert increment > 0.0
            assert increment < 45.0


def test_eta_generally_declines_with_mach_at_fixed_geometry_trend() -> None:
    """Optimized eta_inlet should show the expected downward trend with Mach.

    The MIL-E-5007D standard itself falls monotonically with Mach for
    M > 1; check the achieved eta_inlet is not wildly non-monotone (a
    physically-optimized recovery should broadly track the same trend
    even though a per-cone optimum is re-solved at each Mach). The sweep
    starts at Mach 2.0 here (not 1.5) because at Mach 1.5 the 4-cone
    optimizer's seeds detach (an expected, honestly-reported physical
    failure mode for this cone count at low supersonic Mach -- see
    test_low_mach_fails_and_high_mach_can_fail's neighbor case), which
    would otherwise contaminate a monotonic-trend check with a
    non-physical degenerate eta value.
    """
    schedule = build_actuation_schedule(
        mach_min=2.0, mach_max=3.5, mach_step=COARSE_MACH_STEP
    )
    etas = [r["eta_inlet"] for r in schedule]
    # Not strictly monotone is acceptable, but the endpoints must show the
    # expected overall decline from low to high supersonic Mach.
    assert etas[0] > etas[-1]
    eta_std_values = [r["eta_std"] for r in schedule]
    assert eta_std_values == sorted(eta_std_values, reverse=True)


def test_actuation_range_per_cone_and_mil_band() -> None:
    """Delta_theta per cone is positive; MIL band is a subset of the sweep."""
    schedule = build_actuation_schedule(
        mach_min=1.0, mach_max=3.5, mach_step=COARSE_MACH_STEP
    )
    deltas = actuation_range_per_cone_deg(schedule, supersonic_only=True)
    assert len(deltas) == DEFAULT_N_CONES_M25
    for delta in deltas:
        assert delta >= 0.0

    band = mach_band_meeting_mil(schedule)
    assert band is not None
    mach_values = [r["mach"] for r in schedule]
    assert min(mach_values) <= band[0] <= band[1] <= max(mach_values)


def test_geometry_bounds_match_inlet_performance_constants() -> None:
    """Analysis reports the fixed capture area / base diameter it consumed."""
    from IADE_Core.modules.propulsion.inlet_performance import (
        CAPTURE_AREA_M2,
        SPIKE_BASE_DIAMETER_M,
    )

    analysis = ConeActuationScheduleAnalysis()
    analysis.setup(mach_min=1.0, mach_max=2.0, mach_step=COARSE_MACH_STEP)
    results = analysis.execute()
    assert results.data["capture_area_m2"] == pytest.approx(CAPTURE_AREA_M2)
    assert results.data["base_diameter_m"] == pytest.approx(SPIKE_BASE_DIAMETER_M)
    assert results.fidelity == FidelityLevel.LEVEL_0


def test_class_execute_matches_function_and_builds_metadata() -> None:
    """ConeActuationScheduleAnalysis.execute() wraps build_actuation_schedule."""
    analysis = ConeActuationScheduleAnalysis()
    analysis.setup(mach_min=1.0, mach_max=3.5, mach_step=COARSE_MACH_STEP)
    results = analysis.execute()
    assert results.metadata["n_rows"] == len(results.metadata["schedule"])
    assert results.data["n_cones"] == DEFAULT_N_CONES_M25
    assert len(results.data["delta_theta_deg"]) == DEFAULT_N_CONES_M25


def test_setup_validates_inputs() -> None:
    """setup() rejects invalid Mach range / cone count / diffuser efficiency."""
    analysis = ConeActuationScheduleAnalysis()
    with pytest.raises(ValueError):
        analysis.setup(mach_min=-1.0)
    with pytest.raises(ValueError):
        analysis.setup(mach_min=2.0, mach_max=1.0)
    with pytest.raises(ValueError):
        analysis.setup(mach_step=0.0)
    with pytest.raises(ValueError):
        analysis.setup(n_cones=0)
    with pytest.raises(ValueError):
        analysis.setup(eta_diffuser=1.5)


def test_csv_output_created_with_required_columns(tmp_path) -> None:
    """CSV output has the mach/theta*/eta_inlet/eta_std/meets_mil_flag columns."""
    from IADE_Core.modules.propulsion.inlet_actuation import _write_schedule_csv

    schedule = build_actuation_schedule(
        mach_min=1.0, mach_max=2.0, mach_step=COARSE_MACH_STEP
    )
    csv_path = tmp_path / "inlet_actuation_schedule.csv"
    _write_schedule_csv(schedule, csv_path)

    assert csv_path.exists()
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    expected_cols = {
        "mach",
        "theta1_deg",
        "theta2_deg",
        "theta3_deg",
        "theta4_deg",
        "eta_inlet",
        "eta_std",
        "meets_mil_flag",
    }
    assert expected_cols.issubset(set(fieldnames))
    assert len(rows) == len(schedule)
