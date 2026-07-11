# MELprop-IADE | tests.unit.test_trajectory_coldflow_prd240 | v0.1.0
"""Unit tests for analyses.trajectory.coldflow_boost_prd240 (real PRD-240 curve)."""

import numpy as np
import pytest

from analyses.trajectory.coldflow_boost_prd240 import (
    ARCHIVE_REFERENCE_MASS_KG,
    load_thrust_curve,
    mass_at_time_real_curve,
    run_case,
)
from analyses.trajectory.booster_burnout import load_booster_params
from analyses.trajectory.coldflow_boost_prd240 import COLDFLOW_VEHICLE_CONFIG_PATH


def test_thrust_curve_loads_real_positive_data() -> None:
    """The extracted CSV parses to a real, physically sane thrust curve."""
    t_s, thrust_N, cum_impulse, total_impulse = load_thrust_curve()
    assert len(t_s) > 10
    assert (thrust_N >= 0.0).all()
    assert thrust_N.max() == pytest.approx(17250.0, rel=1e-3)
    # Real archive total impulse, matches the source sheet's own "Sum" cell.
    assert total_impulse == pytest.approx(56377.0, rel=1e-3)
    assert cum_impulse[-1] == pytest.approx(total_impulse)
    assert (np.diff(cum_impulse) >= -1e-9).all()  # monotonically non-decreasing


def test_coldflow_config_loads_and_differs_from_official() -> None:
    """The separate cold-flow config has the real PRD-240 propulsion values."""
    params = load_booster_params(config_path=COLDFLOW_VEHICLE_CONFIG_PATH)
    assert params.thrust_mean_yaml_N == pytest.approx(10878.0)
    # Real motor burn is much shorter and lighter than the SZACOWANY placeholder.
    assert params.burn_time_s == pytest.approx(5.18)
    assert params.propellant_mass_kg == pytest.approx(27.01)


def test_mass_at_time_real_curve_depletes_monotonically() -> None:
    """Mass strictly decreases (or holds) as cumulative impulse is delivered."""
    t_s, thrust_N, cum_impulse, total_impulse = load_thrust_curve()
    params = load_booster_params(config_path=COLDFLOW_VEHICLE_CONFIG_PATH)
    masses = [
        mass_at_time_real_curve(t, params, t_s, cum_impulse, total_impulse)
        for t in np.linspace(0.0, float(t_s[-1]), 20)
    ]
    assert all(m2 <= m1 + 1e-9 for m1, m2 in zip(masses, masses[1:]))
    # Small tolerance: the archive curve includes a few pre-ignition (t<0)
    # samples with tiny near-zero thrust readings (sensor bias, ~3.6 N),
    # which contribute a negligible sliver of "impulse" before t=0.
    assert masses[0] == pytest.approx(params.launch_mass_kg, rel=1e-4)
    assert masses[-1] == pytest.approx(
        params.launch_mass_kg - params.propellant_mass_kg, rel=1e-6
    )


def test_archive_mass_case_reaches_higher_mach_than_full_vehicle() -> None:
    """Real PRD-240 curve: the light archive-reference mass goes supersonic;
    the full 355 kg vehicle (ramjet stage present but cold) does not.

    This is the real, physical finding this module exists to surface --
    not asserted as a design verdict, only as the module's own consistent
    output (see docs/decision-log.md for the human-flagged interpretation).
    """
    archive_case = run_case("ARCHIVE100", ARCHIVE_REFERENCE_MASS_KG, launch_angle_deg=50.0)
    full_case = run_case("FULL355", None, launch_angle_deg=50.0)

    assert archive_case["burnout_mach"] > full_case["burnout_mach"]
    assert archive_case["launch_mass_kg"] == pytest.approx(ARCHIVE_REFERENCE_MASS_KG)
    assert full_case["launch_mass_kg"] == pytest.approx(355.02)
    # Both must be physically sane (positive altitude gain, no NaNs).
    for case in (archive_case, full_case):
        assert case["burnout_altitude_m"] > 0.0
        assert case["burnout_velocity_ms"] > 0.0
        assert not case["ground_impact_before_burnout"]


def test_run_case_cross_checks_against_archive_separation_event() -> None:
    """ARCHIVE100 @ t=5.0s should be in the same ballpark as the archive's
    own reported Separation altitude (1177 m @ 50deg) -- different drag
    models mean this is a sanity cross-check, not an exact match."""
    case = run_case("ARCHIVE100", ARCHIVE_REFERENCE_MASS_KG, launch_angle_deg=50.0)
    s = case["_samples"]
    idx = int(np.argmin(np.abs(s["t_s"] - 5.0)))
    altitude_at_5s = s["h_m"][idx]
    archive_reported_altitude_m = 1177.08
    # Within a factor of 1.5 -- different drag correlations, same order of
    # magnitude confirms the integration isn't fundamentally wrong.
    assert archive_reported_altitude_m / 1.5 < altitude_at_5s < archive_reported_altitude_m * 1.5
