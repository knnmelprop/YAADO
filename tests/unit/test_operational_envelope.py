# MELprop-IADE | tests.unit.test_operational_envelope | v0.1.0
"""Unit tests for analyses.mission.operational_envelope.

Covers the standalone ISA helper, the full Mach x altitude sweep, the
Night-3 nominal cruise consistency check, and the CSV schema.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

from analyses.mission.operational_envelope import (
    NIGHT3_ALTITUDE_M,
    NIGHT3_MACH,
    STATUS_SUSTAINED,
    EnvelopePoint,
    compute_envelope_grid,
    isa_atmosphere,
    night3_reference_point,
    reference_area_m2,
    write_csv,
)

RESULTS_CSV_PATH = (
    Path(__file__).resolve().parents[2]
    / "analyses"
    / "mission"
    / "results"
    / "operational_envelope.csv"
)


def test_isa_atmosphere_sea_level_density_within_1_percent() -> None:
    """ISA density at H=0 should match the textbook 1.225 kg/m^3 within 1%."""
    rho_kg_m3, _t_K, _p_Pa, _a_m_s = isa_atmosphere(0.0)
    assert rho_kg_m3 == pytest.approx(1.225, rel=0.01)


def test_isa_atmosphere_sea_level_speed_of_sound_within_1_percent() -> None:
    """ISA speed of sound at H=0 should match the textbook 340.3 m/s within 1%."""
    _rho, _t_K, _p_Pa, a_m_s = isa_atmosphere(0.0)
    assert a_m_s == pytest.approx(340.3, rel=0.01)


def test_isa_atmosphere_rejects_negative_altitude() -> None:
    """isa_atmosphere raises ValueError for altitude_m < 0."""
    with pytest.raises(ValueError, match="altitude_m"):
        isa_atmosphere(-100.0)


def test_isa_atmosphere_rejects_above_tropopause() -> None:
    """isa_atmosphere raises ValueError above the 11 km tropopause."""
    with pytest.raises(ValueError, match="tropopause"):
        isa_atmosphere(12000.0)


def test_isa_atmosphere_density_decreases_with_altitude() -> None:
    """Density is monotonically decreasing with altitude in the troposphere."""
    rho_0, *_ = isa_atmosphere(0.0)
    rho_5000, *_ = isa_atmosphere(5000.0)
    rho_10000, *_ = isa_atmosphere(10000.0)
    assert rho_0 > rho_5000 > rho_10000


def test_envelope_grid_has_thirty_points() -> None:
    """The default 5-Mach x 6-altitude grid produces 30 EnvelopePoints."""
    points = compute_envelope_grid()
    assert len(points) == 30
    assert all(isinstance(p, EnvelopePoint) for p in points)


def test_sustained_region_is_not_empty() -> None:
    """At least one grid point sustains positive net thrust (Th2 > drag)."""
    points = compute_envelope_grid()
    sustained = [p for p in points if p.status == STATUS_SUSTAINED]
    assert len(sustained) >= 1


def test_status_matches_net_thrust_sign() -> None:
    """status is SUSTAINED iff net_thrust_N > 0, for every grid point."""
    points = compute_envelope_grid()
    for p in points:
        expected = STATUS_SUSTAINED if p.net_thrust_N > 0.0 else "UNABLE_TO_SUSTAIN"
        assert p.status == expected
        assert p.net_thrust_N == pytest.approx(p.Th2_N - p.drag_N)


def test_reference_area_matches_body_diameter_0p250m() -> None:
    """Aref = pi*d^2/4 with the Fusion-verified body diameter 0.250 m."""
    aref_m2 = reference_area_m2()
    expected_m2 = math.pi * 0.250**2 / 4.0
    assert aref_m2 == pytest.approx(expected_m2, rel=1e-6)


def test_night3_net_thrust_consistent_with_default_inlet_model() -> None:
    """Grid Th2 (MIL-E-5007D eta_d) vs Night-3-style Th2 (multi-cone eta_inlet).

    ``workflows.ramp_staged_mission`` wires the cruise segment's thrust
    from ``GrzywkaCombustorNozzleAnalysis`` using ITS DEFAULT eta_inlet
    resolution (the 4-cone multi-shock preset chain), not the
    MIL-E-5007D standard formula this module's grid sweep uses. The two
    drag models also differ (this module's flat-plate CD0=0.35 estimate
    vs. no drag term at all in ramp_staged_mission's design-point
    wiring), so a net-thrust comparison is not meaningful; instead this
    test checks Th2-vs-Th2 consistency at the Night-3 nominal cruise
    condition (Mach 2.5 / 6000 m), which IS meaningful because both
    eta_inlet sources (MIL-E-5007D standard vs. multi-cone chain) are
    expected to be close at Mach 2.5 -- the multi-cone inlet was
    specifically angle-optimized to clear the MIL-E-5007D standard at
    that Mach (see analyses/propulsion/inlet_performance.py's confirmed-
    result table).
    """
    points = compute_envelope_grid()
    grid_point = next(
        p for p in points if p.mach == NIGHT3_MACH and p.altitude_m == NIGHT3_ALTITUDE_M
    )
    night3 = night3_reference_point()

    assert grid_point.Th2_N == pytest.approx(night3["Th2_N"], rel=0.05)


def test_night3_reference_point_thrust_is_positive() -> None:
    """The Night-3 nominal cruise Th2 (default multi-cone inlet) is positive."""
    night3 = night3_reference_point()
    assert night3["Th2_N"] > 0.0
    assert 0.0 < night3["eta_inlet"] <= 1.0


def test_csv_has_exactly_seven_columns(tmp_path: Path) -> None:
    """The written CSV has exactly the 7 required columns, in order."""
    points = compute_envelope_grid()
    csv_path = tmp_path / "operational_envelope.csv"
    write_csv(points, csv_path)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)

    assert header == [
        "mach",
        "altitude_m",
        "eta_d",
        "Th2_N",
        "drag_N",
        "net_thrust_N",
        "status",
    ]


def test_csv_row_count_matches_grid_size(tmp_path: Path) -> None:
    """The CSV has one data row per grid point (30 rows + header)."""
    points = compute_envelope_grid()
    csv_path = tmp_path / "operational_envelope.csv"
    write_csv(points, csv_path)

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert len(rows) == len(points) + 1


def test_committed_results_csv_exists_and_is_well_formed() -> None:
    """The committed results/operational_envelope.csv has the 7-column schema.

    Skips if the results artifact has not been generated yet (run
    ``python3 analyses/mission/operational_envelope.py`` first).
    """
    if not RESULTS_CSV_PATH.exists():
        pytest.skip("operational_envelope.csv not generated yet")

    with open(RESULTS_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == [
            "mach",
            "altitude_m",
            "eta_d",
            "Th2_N",
            "drag_N",
            "net_thrust_N",
            "status",
        ]
        rows = list(reader)
    assert len(rows) == 30
