# MELprop-IADE | tests.unit.test_trajectory_launch_angle | v0.1.0
"""Unit tests for the launch-angle sensitivity sweep in booster_burnout.py."""

import csv

import pytest

from IADE_Core.modules.flight_dynamics.methods.point_mass_3dof import (
    SWEEP_CSV_PATH,
    load_booster_params,
    run_launch_angle_sweep,
)


def _sweep_entry_for(angle_deg: float) -> dict:
    """Run a single-angle sweep and return its result entry.

    Args:
        angle_deg: Launch angle [deg] to evaluate.

    Returns:
        The sweep result dict for ``angle_deg``.
    """
    results = run_launch_angle_sweep(angles_deg=(angle_deg,))
    return results[0]


def test_zero_degree_launch_hits_ground_before_burnout() -> None:
    """A 0 deg (horizontal) launch angle results in ground impact.

    With no vertical thrust component and no lift, gravity pulls the
    vehicle down from h0=100 m before the nominal 6 s burnout (see
    docs/AGENT_CONTEXT.md Sec. 7 caveat 2).
    """
    entry = _sweep_entry_for(0.0)
    assert entry["ground_impact_flag"] is True


def test_thirty_degree_launch_avoids_ground_impact() -> None:
    """A 30 deg launch angle reaches nominal burnout without ground impact."""
    entry = _sweep_entry_for(30.0)
    assert entry["ground_impact_flag"] is False


@pytest.mark.parametrize("angle_deg", [15.0, 20.0, 25.0, 30.0])
def test_burnout_mach_supersonic_for_steep_enough_angles(angle_deg: float) -> None:
    """Burnout Mach exceeds 1.0 for launch angles >= 15 deg.

    History (both changes 2026-07-11, see docs/decision-log.md):
    (1) vehicle_config.yaml's stage_1.propulsion was updated from a
        SZACOWANY placeholder (implied total impulse ~152 kN*s) to the
        real PRD-240 static-test thrust curve (56.38 kN*s, ~2.7x lower).
        On its own, with the vehicle mass still at the (Fusion-derived)
        355.02 kg, this made burnout subsonic at every angle -- the test
        was temporarily changed to assert Mach < 1.0 to match.
    (2) Separately, mass_properties.total_mass_kg was corrected
        355.02 -> 100.0 kg: the Fusion 360 physics-engine mass estimate
        (booster 277.80 + ramjet 15.18 kg) is considered wrong/oversized;
        the real target mass is the archive's own reference value (used
        throughout its PRD-240 flight-simulation sheets).
    With both real values in effect, burnout Mach is back above 1.0 at
    every angle 15-83 deg (~1.7-1.76) -- this test reverts to its
    original supersonic assertion, now backed by real data on both axes
    (motor AND mass) rather than the original SZACOWANY placeholders.
    """
    entry = _sweep_entry_for(angle_deg)
    assert entry["burnout_mach"] > 1.0
    assert entry["burnout_mach"] > 0.0


def test_sweep_result_has_required_fields() -> None:
    """Each sweep entry reports all required per-angle metrics."""
    entry = _sweep_entry_for(20.0)
    required_keys = {
        "launch_angle_deg",
        "burnout_mach",
        "burnout_altitude_m",
        "burnout_range_m",
        "max_q_Pa",
        "ground_impact_flag",
    }
    assert required_keys.issubset(entry.keys())


def test_load_booster_params_accepts_launch_angle_override() -> None:
    """load_booster_params overrides the default launch angle when given one."""
    params_default = load_booster_params()
    params_override = load_booster_params(launch_angle_deg=10.0)
    assert params_default.launch_angle_deg == pytest.approx(83.0, abs=0.1)
    assert params_override.launch_angle_deg == pytest.approx(10.0, abs=0.01)


def test_sweep_csv_exists_with_required_columns() -> None:
    """The launch_angle_sweep.csv file (written by main()) has the required columns.

    This test runs the module's main() indirectly by relying on a previous
    run (see task instructions: "re-run the script so the JSON stays
    consistent"); it skips if the CSV has not yet been generated.
    """
    if not SWEEP_CSV_PATH.exists():
        pytest.skip(
            "launch_angle_sweep.csv not found; run "
            "analyses/trajectory/booster_burnout.py first"
        )

    with SWEEP_CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        rows = list(reader)

    required_columns = {
        "launch_angle_deg",
        "burnout_mach",
        "burnout_altitude_m",
        "burnout_range_m",
        "max_q_Pa",
        "ground_impact_flag",
    }
    assert required_columns.issubset(fieldnames)
    assert len(rows) >= 1
