# MELprop-IADE | tests.unit.test_inlet_nozzle_v2 | v0.1.0
"""Stage 3 tests: Taylor-Maccoll inlet_v2 and nozzle expansion check.

Keeps the expensive Taylor-Maccoll matrix out of the suite: validates the
solver on one textbook case, the closed-form shock/recovery helpers, and the
key detached-shock finding, plus the nozzle over/under-expansion classifier.
"""

from __future__ import annotations

import math

from IADE_Core.modules.propulsion.cycle_v2.hp_stream_thrust_cycle import GAMMA_COLD
from IADE_Core.modules.propulsion.inlet_performance_v2 import (
    evaluate_inlet,
    max_attached_cone_half_angle,
    mil_e_5007d_recovery,
    normal_shock,
    solve_conical_shock,
)
from IADE_Core.modules.propulsion.nozzle_expansion_check import (
    classify_expansion,
    matched_area_ratio,
    run_band,
)


def test_taylor_maccoll_textbook_case() -> None:
    """M1=2.0, 20 deg cone -> shock angle beta ~ 37.8 deg (Anderson tables)."""
    sol = solve_conical_shock(2.0, math.radians(20.0), GAMMA_COLD)
    assert sol is not None
    beta, _mach_behind, ptr = sol
    assert abs(math.degrees(beta) - 37.8) < 0.5
    assert 0.98 < ptr <= 1.0  # weak conical shock, small total-pressure loss


def test_cone_tolerates_more_than_wedge() -> None:
    """Conical attached limit at M2.5 (~46 deg) >> 2-D wedge limit (~29.8 deg)."""
    theta_max = math.degrees(max_attached_cone_half_angle(2.5, GAMMA_COLD))
    assert 44.0 < theta_max < 48.0


def test_42deg_cone_detaches_at_m2() -> None:
    """The as-drawn 42 deg cone detaches at M2.0 (off-design starting limit)."""
    res = evaluate_inlet(2.0, 42.0)
    assert res.attached is False
    assert any("DETACHED_SHOCK" in f for f in res.failure_modes)


def test_42deg_cone_attached_but_below_mil_at_m25() -> None:
    """At M2.5 the 42 deg cone is attached but falls below the MIL-E-5007D goal."""
    res = evaluate_inlet(2.5, 42.0)
    assert res.attached is True
    assert res.overall_recovery is not None and res.overall_recovery < res.mil_e_5007d_reference
    assert res.meets_reference_goal is False
    # no-bleed limitation is always disclosed
    assert any("NO_BLEED" in f for f in res.failure_modes)


def test_mil_e_5007d_reference() -> None:
    """MIL-E-5007D reference recovery ~0.866 at Mach 2.5."""
    assert abs(mil_e_5007d_recovery(2.5) - 0.8703) < 1e-3
    assert mil_e_5007d_recovery(1.0) == 1.0


def test_normal_shock_subsonic_downstream() -> None:
    """Normal shock yields subsonic downstream Mach and pt loss."""
    m2, ptr = normal_shock(2.0, GAMMA_COLD)
    assert m2 < 1.0
    assert 0.0 < ptr < 1.0


def test_nozzle_underexpanded_across_band() -> None:
    """AR=1.317 at M2.5 is under-expanded across the whole altitude band."""
    rows = run_band()
    assert all(r["expansion_state"] == "under-expanded" for r in rows)
    # matched area ratio needed is larger than the actual 1.317
    assert all(r["matched_area_ratio_needed"] > 1.317 for r in rows)


def test_expansion_classifier() -> None:
    """Expansion classifier basic branches."""
    assert classify_expansion(2.0, 1.0) == "under-expanded"
    assert classify_expansion(0.5, 1.0) == "over-expanded"
    assert classify_expansion(1.0, 1.0) == "matched"


def test_matched_area_ratio_reasonable() -> None:
    """Matched AR for a modestly under-expanded nozzle is a sane supersonic value."""
    ar = matched_area_ratio(300000.0, 26000.0, 1.28)
    assert 1.0 < ar < 10.0
