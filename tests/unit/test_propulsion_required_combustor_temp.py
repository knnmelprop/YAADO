# MELprop-IADE | tests.unit.test_propulsion_required_combustor_temp | v0.1.0
"""Unit tests for analyses.propulsion.cycle_v2.required_combustor_temp."""

import pytest

from analyses.propulsion.cycle_v2.hp_stream_thrust_cycle import CycleInputs, evaluate_cycle
from analyses.propulsion.cycle_v2.required_combustor_temp import (
    TELTIK_DRAG_N,
    real_drag_at_condition_N,
    run_case,
    solve_required_tt4_K,
    thrust_at_tt4_N,
)


def test_thrust_at_tt4_is_monotonically_increasing() -> None:
    """More heat release (higher Tt4) must give strictly more thrust.

    This monotonicity is what makes the root-find in solve_required_tt4_K
    well-posed -- verify it holds over a realistic bracket before trusting
    the solver's result.
    """
    mach0, altitude_m = 2.5, 10_000.0
    temps = [800.0, 1200.0, 1600.0, 2000.0, 2400.0]
    thrusts = [thrust_at_tt4_N(t, mach0, altitude_m) for t in temps]
    assert all(t2 > t1 for t1, t2 in zip(thrusts, thrusts[1:]))


def test_solve_required_tt4_recovers_thrust_at_solution() -> None:
    """The solved Tt4, fed back into the forward model, reproduces the target thrust."""
    mach0, altitude_m = 2.5, 10_000.0
    target_thrust_N = 5000.0
    required_tt4_K, result = solve_required_tt4_K(target_thrust_N, mach0, altitude_m)
    assert result.thrust_real_N == pytest.approx(target_thrust_N, rel=1e-5)
    assert 600.0 < required_tt4_K < 3000.0


def test_solve_required_tt4_matches_default_at_default_thrust() -> None:
    """Solving for the thrust the DEFAULT Tt4=2000K produces should recover Tt4=2000K."""
    mach0, altitude_m = 2.5, 10_000.0
    default_result = evaluate_cycle(CycleInputs(mach0=mach0, altitude_m=altitude_m))
    required_tt4_K, _ = solve_required_tt4_K(default_result.thrust_real_N, mach0, altitude_m)
    assert required_tt4_K == pytest.approx(2000.0, rel=1e-4)


def test_real_drag_polar_condition_gives_positive_finite_drag() -> None:
    """The real drag buildup at the cruise design point is a sane positive number."""
    drag_N = real_drag_at_condition_N(2.5, 10_000.0)
    assert drag_N > 0.0
    assert drag_N < 50_000.0  # sanity upper bound, not a tight physical limit


def test_run_case_reports_required_tt4_below_assumed_for_both_drag_estimates() -> None:
    """Both real drag estimates require LESS heat than the assumed 2000K design point.

    This is the real finding this module surfaces: the vehicle's assumed
    combustor design point (2000K) exceeds what either independent drag
    estimate (drag_polar.py's real buildup, or the Teltik CFD reference)
    actually requires for steady, unaccelerated cruise -- i.e., there is
    thrust margin at the design condition under both estimates. Reported
    as a repo-consistent finding, not asserted as a design verdict.
    """
    real_drag_N = real_drag_at_condition_N(2.5, 10_000.0)
    case_real = run_case("real_drag_polar", real_drag_N, 2.5, 10_000.0)
    case_teltik = run_case("teltik_cfd_reference", TELTIK_DRAG_N, 2.5, 10_000.0)

    for case in (case_real, case_teltik):
        assert case["required_tt4_K"] < case["assumed_tt4_K"]
        assert case["required_f_fuel_air"] > 0.0
        assert case["required_f_fuel_air"] < case["assumed_f_fuel_air"]


def test_solve_required_tt4_raises_outside_bracket() -> None:
    """An unreachable target thrust (far outside the bracket) raises, not silently clamps."""
    with pytest.raises(ValueError):
        solve_required_tt4_K(1.0e9, 2.5, 10_000.0)
