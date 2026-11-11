"""Tests for the Grzywka combustor and nozzle sizing.

Expected values are evaluated from the isentropic, choked-flow and energy-balance
relations with explicit arithmetic, independently of the module.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest

from YAADO_Core.Foundation.analysis_base import FidelityLevel
from YAADO_Core.Foundation.atmosphere import isa_atmosphere
from YAADO_Core.Foundation.constants import R_AIR
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.powerplant.containers import GrzywkaCycleResults, GrzywkaInputs
from YAADO_Core.modules.powerplant.cycle_methods.grzywka import (
    GrzywkaNozzleAnalysis,
    evaluate_sizing,
    format_mach_sweep_csv,
    fully_expanded_exit,
    plot_mach_sweep,
    run_mach_sweep,
)
from YAADO_Core.modules.powerplant.cycle_methods.heiser_pratt import (
    HeiserPrattCycleAnalysis,
)

ALVRJ_PATH = Path("Hangar/examples/ALVRJ/ALVRJ.toml")


def _inputs(**overrides: float | None) -> GrzywkaInputs:
    inputs = GrzywkaInputs(
        mach=2.5,
        altitude=10000.0,
        tt4=2000.0,
        eta_inlet=0.9,
        pi_cc=0.9,
        pi_nozzle=0.97,
        eta_b=0.95,
        gamma_hot=1.3,
        gamma_cold=1.4,
        fuel_lhv=43.2e6,
        capture_area=0.05,
    )
    return replace(inputs, **overrides)  # type: ignore[arg-type]


def test_fully_expanded_exit_by_hand() -> None:
    """T3 = Tt (p0/pt)^((g-1)/g), V3 = sqrt(2 cp (Tt - T3)), M3 = V3 / sqrt(g R T3)."""
    t3, v3, m3 = fully_expanded_exit(2000.0, 500_000.0, 26_500.0, 1.3)
    expected_t3 = 2000.0 * (26_500.0 / 500_000.0) ** (0.3 / 1.3)  # = 1015.4 K
    cp = 1.3 * R_AIR / 0.3  # = 1243.9 J/(kg K)
    assert t3 == pytest.approx(expected_t3, rel=1e-12)
    assert v3 == pytest.approx(math.sqrt(2.0 * cp * (2000.0 - expected_t3)), rel=1e-12)
    assert m3 == pytest.approx(v3 / math.sqrt(1.3 * R_AIR * expected_t3), rel=1e-12)
    assert t3 == pytest.approx(1015.4, abs=0.1)
    with pytest.raises(ValueError, match="cannot expand"):
        fully_expanded_exit(2000.0, 20_000.0, 26_500.0, 1.3)


def test_flow_energy_balance_and_stations_by_hand() -> None:
    """Capture flow rho0 V0 Ac; f = (cp_t Tt4 - cp_c Tt0)/(eta_b h - cp_t Tt4); pt chain."""
    r = evaluate_sizing(_inputs())
    atm = isa_atmosphere(10000.0)
    v0 = 2.5 * math.sqrt(1.4 * R_AIR * atm.temperature)
    tt0 = atm.temperature * 2.25
    cp_c, cp_t = 1.4 * R_AIR / 0.4, 1.3 * R_AIR / 0.3
    assert r.mdot_air == pytest.approx(atm.density * v0 * 0.05, rel=1e-12)
    assert r.fuel_air_ratio == pytest.approx(
        (cp_t * 2000.0 - cp_c * tt0) / (0.95 * 43.2e6 - cp_t * 2000.0), rel=1e-12
    )
    assert r.pt_combustor_inlet == pytest.approx(0.9 * r.pt0)
    assert r.pt_combustor_exit == pytest.approx(0.81 * r.pt0)
    assert r.capture_area == pytest.approx(0.05)


def test_throat_passes_the_flow_choked_and_exit_satisfies_continuity() -> None:
    """A21 from the choked mass flux at pt2, Tt4; rho3 V3 A3 = mdot_exit at p3 = p0."""
    r = evaluate_sizing(_inputs())
    g = 1.3
    flux = r.pt_combustor_exit * math.sqrt(g / (R_AIR * 2000.0)) * (2.0 / (g + 1.0)) ** (
        (g + 1.0) / (2.0 * (g - 1.0))
    )
    assert r.throat_area == pytest.approx(r.mdot_exit / flux, rel=1e-12)
    assert r.throat_diameter == pytest.approx(math.sqrt(4.0 * r.throat_area / math.pi))
    rho3 = r.p0 / (R_AIR * r.t_exit)
    assert rho3 * r.v_exit * r.exit_area == pytest.approx(r.mdot_exit, rel=1e-12)
    assert r.area_ratio == pytest.approx(r.exit_area / r.throat_area)


def test_thrust_levels_follow_the_losses() -> None:
    """Ideal >= combustor loss >= real; without losses all three are equal."""
    r = evaluate_sizing(_inputs())
    assert r.thrust_ideal > r.thrust_cc_loss > r.thrust_real > 0.0
    lossless = evaluate_sizing(_inputs(pi_cc=1.0, pi_nozzle=1.0))
    assert lossless.thrust_ideal == pytest.approx(lossless.thrust_real)
    assert r.thrust_real == pytest.approx(r.mdot_exit * r.v_exit - r.mdot_air * r.v0)


def test_given_throat_sets_the_flow() -> None:
    """With a throat area as the source, the sized throat is that area."""
    r = evaluate_sizing(_inputs(capture_area=None, throat_area=0.03))
    assert r.throat_area == pytest.approx(0.03, rel=1e-12)


def test_input_errors() -> None:
    """Exactly one flow source; no heat, no choking and no thrust are errors."""
    with pytest.raises(ValueError, match="exactly one"):
        _inputs(mdot_air=10.0)
    with pytest.raises(ValueError, match="adds no heat"):
        evaluate_sizing(_inputs(mach=4.5, tt4=1100.0))
    with pytest.raises(ValueError, match="cannot choke"):
        evaluate_sizing(_inputs(mach=1.1, eta_inlet=0.5, pi_cc=0.6, pi_nozzle=0.6))


def _run(**settings: float) -> GrzywkaCycleResults:
    analysis = GrzywkaNozzleAnalysis()
    analysis.setup(BaseVehicleConfig.from_toml(ALVRJ_PATH), enable_logging=False, **settings)
    return analysis.execute()


def test_analysis_on_alvrj_matches_heiser_pratt_flow() -> None:
    """With the ALVRJ throat, flow and f match Heiser & Pratt; full expansion beats its nozzle."""
    results = _run()
    heiser = HeiserPrattCycleAnalysis()
    heiser.setup(BaseVehicleConfig.from_toml(ALVRJ_PATH), enable_logging=False)
    reference = heiser.execute()
    assert results.fidelity == FidelityLevel.LEVEL_2
    assert results.throat_diameter == pytest.approx(0.25)
    assert results.mdot_air == pytest.approx(reference.mdot_air, rel=1e-9)
    assert results.fuel_air_ratio == pytest.approx(reference.fuel_air_ratio, rel=1e-9)
    assert results.thrust_real >= reference.thrust_real
    assert "combustion_efficiency" in results.assumed_losses
    assert any("underexpands" in n for n in results.notes)


def test_analysis_capture_area_and_errors() -> None:
    """A capture area replaces the throat; bad combinations fail."""
    results = _run(capture_area=0.05, mach=3.0)
    assert results.capture_area == pytest.approx(0.05)
    assert results.notes == ()
    with pytest.raises(ValueError, match="exactly one"):
        _run(capture_area=0.05, mdot_air=10.0)
    with pytest.raises(TypeError, match="Unknown settings"):
        _run(capture_area_m2=0.05)


def test_analysis_without_flow_source_fails() -> None:
    """A ramjet without a throat needs a capture area or an air flow."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_PATH)
    vehicle.propulsion["sustainer"].nozzle_throat_diameter = None
    with pytest.raises(ValueError, match="capture_area or mdot_air"):
        GrzywkaNozzleAnalysis().setup(vehicle, enable_logging=False)


def test_mach_sweep_csv_and_figure() -> None:
    """The sweep covers 1.5 to 4 at the run's capture area and plots four panels."""
    results = _run()
    points = run_mach_sweep(results)
    assert points[0].mach == pytest.approx(1.5)
    assert points[-1].mach == pytest.approx(4.0)
    design = next(p for p in points if p.mach == pytest.approx(2.6))
    assert design.throat_diameter == pytest.approx(0.25, rel=1e-6)  # the run's own point
    assert points[-1].throat_diameter < points[0].throat_diameter  # higher pt, smaller throat
    assert points[-1].area_ratio > points[0].area_ratio
    lines = format_mach_sweep_csv(points).strip().splitlines()
    assert lines[0].startswith("mach,thrust_real,specific_impulse")
    assert len(lines) == len(points) + 1
    assert len(plot_mach_sweep(points, results).axes) == 4
