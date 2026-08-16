# MELprop-IADE | tests.unit.test_gamma_sensitivity | v0.1.0
"""Gate tests for the Heiser & Pratt cycle rebuild and gamma sweep (Stage 2).

Gate (2026-07-11 rerun): V3 > 0 for all gamma, V3 monotonic with gamma,
combustor exit hotter than inlet (T3 > T2), and the three-thrust hierarchy
Thi >= Th1 >= Th2 holds. Numbers are reported by the model, not asserted to a
particular "answer" — only physical-consistency invariants are gated.
"""

from __future__ import annotations

import math

from IADE_Core.modules.powerplant.cycle_methods.heiser_pratt import (
    GAMMA_SWEEP,
    CycleInputs,
    area_ratio_from_mach,
    evaluate_cycle,
    supersonic_mach_from_area_ratio,
)
from FlightLogs.Studies.propulsion_validation.gamma_sensitivity import run_sweep


def test_v3_positive_for_all_gamma() -> None:
    """Exit velocity must be positive across the whole gamma sweep."""
    for row in run_sweep():
        assert row["v3_m_s"] > 0.0, row


def test_v3_monotonic_with_gamma() -> None:
    """V3 must be monotonic in gamma (sign of the trend is not prescribed)."""
    v3 = [row["v3_m_s"] for row in run_sweep(GAMMA_SWEEP)]
    increasing = all(b >= a for a, b in zip(v3, v3[1:]))
    decreasing = all(b <= a for a, b in zip(v3, v3[1:]))
    assert increasing or decreasing, v3


def test_combustor_exit_hotter_than_inlet() -> None:
    """T3 > T2: heat addition raises temperature (exit static > inlet total)."""
    res = evaluate_cycle(CycleInputs())
    assert res.t_exit_K > res.extras["tt2_K"]
    assert res.extras["tt4_K"] > res.extras["tt2_K"]


def test_thrust_hierarchy_holds() -> None:
    """Ideal >= combustor-loss >= real thrust, for every gamma."""
    for g in GAMMA_SWEEP:
        res = evaluate_cycle(CycleInputs(gamma_hot=g))
        assert res.thrust_ideal_N >= res.thrust_cc_loss_N >= res.thrust_real_N


def test_nozzle_underexpanded_on_corrected_geometry() -> None:
    """AR=1.317 at 10 km is under-expanded (couples to Stage 3 nozzle check)."""
    res = evaluate_cycle(CycleInputs())
    assert res.p_exit_Pa > res.p0_Pa
    assert res.mach_exit > 1.0


def test_area_mach_relation_roundtrips() -> None:
    """Supersonic area-Mach solver inverts the area-ratio function."""
    for gamma in (1.20, 1.30, 1.40):
        m = supersonic_mach_from_area_ratio(1.317, gamma)
        assert math.isclose(area_ratio_from_mach(m, gamma), 1.317, rel_tol=1e-6)
