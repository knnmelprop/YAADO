# MELprop-IADE | tests.unit.test_mission_cruise_grzywka | v0.1.0
"""Unit tests for the Night-3 Phase 2 Th1-nominal cruise wiring.

Covers :mod:`workflows.ramp_staged_mission`'s switch of the ramjet-cruise
nominal design point from ``Th2`` (real, most conservative) to ``Th1``
(combustor-loss-only, non-ideal), the always-present Thi/Th1/Th2
verification-gate bounds, the net-thrust-margin computation against the
0-order ``CD0*q*Aref`` drag estimate and the Teltik 2024 CFD drag point,
and off-design physical sanity of the underlying
:class:`analyses.propulsion.combustor_nozzle_cycle.GrzywkaCombustorNozzleAnalysis`
cycle at Mach 2.0 and 3000 m (away from the Mach 2.5 / 10,000 m design
point).
"""

from __future__ import annotations

import math

import pytest

from analyses.propulsion.combustor_nozzle_cycle import (
    GrzywkaCombustorNozzleAnalysis,
)
from analyses.propulsion.inlet_performance import DESIGN_ALTITUDE_M, MACH_DESIGN
from workflows.ramp_staged_mission import BurnoutState, build_ramp_staged_mission


def _sample_burnout_state() -> BurnoutState:
    """Build a representative BurnoutState for cruise-segment tests."""
    return BurnoutState(
        time_s=6.0,
        mass_kg=280.02,
        velocity_ms=413.5,
        velocity_x_ms=57.3,
        velocity_h_ms=409.5,
        altitude_m=1289.3,
        range_m=167.5,
        mach=1.23,
        dynamic_pressure_pa=92362.7,
    )


def test_nominal_cruise_reports_th1_as_nominal_with_all_three_bounds() -> None:
    """The nominal cruise design point mirrors Th1, with Thi/Th1/Th2 all present.

    Per the project verification gate, all three Grzywka thrust scenarios
    must always be present -- never collapsed to a single number -- even
    though the top-level ``thrust_N`` now mirrors Th1 (Night-3 Phase 2
    switch from Th2).
    """
    mission = build_ramp_staged_mission(_sample_burnout_state())
    cruise_params = mission[2].parameters

    assert "thrust_scenarios" in cruise_params
    scenarios = cruise_params["thrust_scenarios"]
    assert set(scenarios.keys()) == {"Thi", "Th1", "Th2"}

    # Nominal top-level thrust mirrors Th1.
    assert cruise_params["thrust_N"] == pytest.approx(scenarios["Th1"]["thrust_N"])
    assert cruise_params["thrust_N"] > 0.0

    # Upper/lower bounds always present and consistent with Thi/Th2.
    assert cruise_params["thrust_upper_bound_N"] == pytest.approx(
        scenarios["Thi"]["thrust_N"]
    )
    assert cruise_params["thrust_lower_bound_N"] == pytest.approx(
        scenarios["Th2"]["thrust_N"]
    )
    assert (
        cruise_params["thrust_upper_bound_N"]
        >= cruise_params["thrust_N"]
        >= cruise_params["thrust_lower_bound_N"]
    )


def test_nominal_cruise_net_thrust_margin_is_computed_against_both_drags() -> None:
    """net_thrust_margin_N = Th1 - drag_estimate_N, logged against both drags.

    Both the 0-order CD0*q*Aref placeholder drag and the independent
    Teltik 2024 CFD drag point (2451.95 N) must be present and finite,
    with the corresponding margins each equal to Th1 minus that drag.
    """
    mission = build_ramp_staged_mission(_sample_burnout_state())
    cruise_params = mission[2].parameters

    assert "drag_estimates" in cruise_params
    drag = cruise_params["drag_estimates"]
    assert math.isfinite(drag["cd0_placeholder_N"])
    assert drag["cd0_placeholder_N"] > 0.0
    assert drag["teltik_cfd_N"] == pytest.approx(2451.95)

    assert "net_thrust_margins_N" in cruise_params
    margins = cruise_params["net_thrust_margins_N"]
    thrust_th1_N = cruise_params["thrust_N"]

    assert margins["vs_cd0_placeholder_N"] == pytest.approx(
        thrust_th1_N - drag["cd0_placeholder_N"]
    )
    assert margins["vs_teltik_cfd_N"] == pytest.approx(
        thrust_th1_N - drag["teltik_cfd_N"]
    )
    # Top-level net_thrust_margin_N mirrors the CD0-placeholder margin.
    assert cruise_params["net_thrust_margin_N"] == pytest.approx(
        margins["vs_cd0_placeholder_N"]
    )


def test_off_design_mach_2p0_thrust_hierarchy_holds() -> None:
    """At off-design Mach 2.0 (design altitude), thrust is positive and ordered.

    Thi >= Th1 >= Th2 must hold by construction (same mdot/Tt1/Tt2/f;
    only the delivered nozzle total pressure differs -- see
    combustor_nozzle_cycle module docstring), away from the Mach 2.5
    design point.
    """
    analysis = GrzywkaCombustorNozzleAnalysis()
    analysis.setup(mach0=2.0, altitude_m=DESIGN_ALTITUDE_M)
    results = analysis.execute()

    thi_N, th1_N, th2_N = results["Thi_N"], results["Th1_N"], results["Th2_N"]
    assert thi_N > 0.0 and th1_N > 0.0 and th2_N > 0.0
    assert thi_N >= th1_N >= th2_N


def test_off_design_altitude_3000m_thrust_hierarchy_holds() -> None:
    """At off-design altitude 3000 m (design Mach), thrust is positive and ordered.

    Same hierarchy check as the off-design Mach case, but sweeping
    altitude instead, away from the 10,000 m design altitude.
    """
    analysis = GrzywkaCombustorNozzleAnalysis()
    analysis.setup(mach0=MACH_DESIGN, altitude_m=3000.0)
    results = analysis.execute()

    thi_N, th1_N, th2_N = results["Thi_N"], results["Th1_N"], results["Th2_N"]
    assert thi_N > 0.0 and th1_N > 0.0 and th2_N > 0.0
    assert thi_N >= th1_N >= th2_N
