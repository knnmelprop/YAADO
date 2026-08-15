# MELprop-IADE | tests.unit.test_trajectory_coldflow_prd240 | v0.1.0
"""Unit tests for analyses.trajectory.coldflow_boost_prd240 (real PRD-240 curve)."""

import numpy as np
import pytest

from IADE_Core.modules.trajectory.coldflow_boost_prd240 import (
    ARCHIVE_REFERENCE_MASS_KG,
    load_thrust_curve,
    mass_at_time_real_curve,
    run_case,
)
from IADE_Core.modules.trajectory.booster_burnout import load_booster_params
from IADE_Core.modules.trajectory.coldflow_boost_prd240 import COLDFLOW_VEHICLE_CONFIG_PATH


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


def test_coldflow_config_matches_official_prd240_and_mass_values() -> None:
    """The cold-flow config's propulsion + mass now match the official config.

    2026-07-11: originally this config was kept deliberately separate from
    (and different in value from) the official vehicle_config.yaml pending
    confirmation of the PRD-240 motor identity. That identity is now
    confirmed and the same real data was promoted into the official
    config, including the mass_properties.total_mass_kg correction
    (355.02 -> 100.0 kg). This test now checks the two configs agree,
    not that they differ -- the cold-flow config is kept for its
    real-time-varying-thrust integrator and ARCHIVE100 cross-validation
    case, not because its values are unique anymore.
    """
    params = load_booster_params(config_path=COLDFLOW_VEHICLE_CONFIG_PATH)
    assert params.thrust_mean_yaml_N == pytest.approx(10878.0)
    assert params.burn_time_s == pytest.approx(5.18)
    assert params.propellant_mass_kg == pytest.approx(27.01)
    assert params.launch_mass_kg == pytest.approx(100.0)

    official_params = load_booster_params()
    assert params.thrust_mean_yaml_N == pytest.approx(official_params.thrust_mean_yaml_N)
    assert params.launch_mass_kg == pytest.approx(official_params.launch_mass_kg)


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


def test_both_cases_reach_supersonic_with_real_mass_and_motor() -> None:
    """Real PRD-240 curve + corrected 100 kg mass: both launch-angle cases
    go supersonic by burnout.

    2026-07-11: was ``test_archive_mass_case_reaches_higher_mach_than_
    full_vehicle`` -- asserted the light 100 kg archive mass goes
    supersonic while the (then-official) 355.02 kg vehicle does not.
    After mass_properties.total_mass_kg was corrected to 100.0 kg in
    both configs (Fusion physics-engine estimate considered wrong/
    oversized), both cases now use the same real mass and differ only by
    launch angle (ARCHIVE100 @ 50deg vs OFFICIAL100 @ 83deg) -- this is
    the real, physical finding this module now surfaces (see
    docs/decision-log.md for the full reasoning).
    """
    archive_case = run_case("ARCHIVE100", ARCHIVE_REFERENCE_MASS_KG, launch_angle_deg=50.0)
    official_case = run_case("OFFICIAL100", None, launch_angle_deg=83.0)

    assert archive_case["launch_mass_kg"] == pytest.approx(100.0)
    assert official_case["launch_mass_kg"] == pytest.approx(100.0)
    # Both must be physically sane and supersonic (positive altitude gain, no NaNs).
    for case in (archive_case, official_case):
        assert case["burnout_mach"] > 1.0
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
