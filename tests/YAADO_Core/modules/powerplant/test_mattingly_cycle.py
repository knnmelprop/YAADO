"""Tests for the Mattingly parametric real-ramjet cycle."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest

from YAADO_Core.Foundation.analysis_base import FidelityLevel
from YAADO_Core.Foundation.atmosphere import isa_atmosphere
from YAADO_Core.Foundation.constants import R_AIR
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.powerplant.containers import (
    RamjetCycleInputs,
    RamjetCycleResults,
)
from YAADO_Core.modules.powerplant.cycle_methods.heiser_pratt import (
    HeiserPrattCycleAnalysis,
)
from YAADO_Core.modules.powerplant.cycle_methods.mattingly import (
    MattinglyCycleAnalysis,
    evaluate_cycle,
    format_mach_sweep_csv,
    ideal_ramjet_specific_thrust,
    plot_mach_sweep,
    ram_recovery,
    run_mach_sweep,
    stagnation_pressure,
    stagnation_temperature,
)

ALVRJ_PATH = Path("Hangar/examples/ALVRJ/ALVRJ.toml")


def _inputs(**overrides: float) -> RamjetCycleInputs:
    inputs = RamjetCycleInputs(
        mach=2.0,
        altitude=11000.0,
        tt4=2000.0,
        pi_d_max=1.0,
        pi_b=1.0,
        pi_n=1.0,
        eta_b=1.0,
        p0_over_p9=1.0,
        gamma_c=1.4,
        gamma_t=1.4,
        fuel_lhv=43.2e6,
    )
    return replace(inputs, **overrides)


def test_stagnation_relations() -> None:
    """Isentropic total temperature and pressure at Mach 2 (NACA 1135: 1.8 and 7.8244)."""
    assert stagnation_temperature(216.65, 2.0, 1.4) == pytest.approx(216.65 * 1.8)
    assert stagnation_pressure(22632.0, 2.0, 1.4) / 22632.0 == pytest.approx(7.8244, abs=1e-4)


def test_ram_recovery_branches() -> None:
    """MIL-E-5007D: 1 subsonic, 1 - 0.075 (M - 1)^1.35 to Mach 5, 800/(M^4 + 935) above."""
    assert ram_recovery(0.8) == 1.0
    assert ram_recovery(2.0) == pytest.approx(0.925)
    assert ram_recovery(5.0) == pytest.approx(1.0 - 0.075 * 4.0**1.35)  # = 0.5127
    assert ram_recovery(6.0) == pytest.approx(800.0 / (1296.0 + 935.0))  # = 0.3586


def test_ideal_ramjet_closed_form_by_hand() -> None:
    """Mach 2, 11 km, Tt4 = 2000 K: F/m0 = a0 M0 (sqrt(tau_lambda / tau_r) - 1)."""
    a0 = math.sqrt(1.4 * R_AIR * 216.65)  # = 295.07 m/s
    expected = a0 * 2.0 * (math.sqrt((2000.0 / 216.65) / 1.8) - 1.0)  # = 746.3 N s/kg
    assert ideal_ramjet_specific_thrust(2.0, 216.65, 2000.0) == pytest.approx(expected)
    assert expected == pytest.approx(746.3, abs=0.2)


def test_lossless_one_gas_cycle_matches_the_ideal_ramjet() -> None:
    """With one gas and no losses, V9 = V0 sqrt(tau_lambda / tau_r) and F/m0 keeps (1 + f)."""
    results = evaluate_cycle(_inputs())
    t0 = isa_atmosphere(11000.0).temperature
    a0 = math.sqrt(1.4 * R_AIR * t0)
    cp = 1.4 * R_AIR / 0.4
    tau_r, tau_lambda = 1.8, 2000.0 / t0
    f = (tau_lambda - tau_r) / (43.2e6 / (cp * t0) - tau_lambda)
    assert results.fuel_air_ratio == pytest.approx(f, rel=1e-12)
    assert results.lossless_specific_thrust == pytest.approx(
        a0 * 2.0 * ((1.0 + f) * math.sqrt(tau_lambda / tau_r) - 1.0), rel=1e-10
    )
    # Real run: the only loss left is the MIL-E-5007D shock term in pi_d
    assert results.pi_d == pytest.approx(0.925)
    assert results.specific_thrust < results.lossless_specific_thrust


def test_two_gas_energy_balance() -> None:
    """f = (cp_t Tt4 - cp_c Tt0) / (eta_b h - cp_t Tt4): air enthalpy uses cp_c."""
    results = evaluate_cycle(_inputs(gamma_t=1.3, eta_b=0.95))
    cp_c, cp_t = 1.4 * R_AIR / 0.4, 1.3 * R_AIR / 0.3
    tt0 = results.tt0
    assert results.fuel_air_ratio == pytest.approx(
        (cp_t * 2000.0 - cp_c * tt0) / (0.95 * 43.2e6 - cp_t * 2000.0), rel=1e-12
    )


def test_losses_lower_the_specific_thrust() -> None:
    """Inlet, combustor and nozzle losses lower F/m0 below the lossless value."""
    real = evaluate_cycle(_inputs(pi_d_max=0.95, pi_b=0.95, pi_n=0.97, eta_b=0.95))
    assert real.pi_d == pytest.approx(0.95 * 0.925)  # MIL-E-5007D at Mach 2
    assert real.specific_thrust < real.lossless_specific_thrust
    assert 0.0 < real.overall_efficiency == pytest.approx(
        real.thermal_efficiency * real.propulsive_efficiency
    )
    assert real.tsfc == pytest.approx(real.fuel_air_ratio / real.specific_thrust)


def test_underexpanded_nozzle_adds_pressure_thrust() -> None:
    """P0/P9 < 1 keeps some pressure thrust, but perfect expansion is best."""
    matched = evaluate_cycle(_inputs())
    underexpanded = evaluate_cycle(_inputs(p0_over_p9=0.5))
    assert underexpanded.mach_exit < matched.mach_exit
    assert underexpanded.specific_thrust < matched.specific_thrust


def test_cold_combustor_is_an_error() -> None:
    """Tt4 at or below the freestream total temperature adds no heat, for any gamma_t."""
    with pytest.raises(ValueError, match="adds no heat"):
        evaluate_cycle(_inputs(mach=6.0, tt4=1500.0))
    # cp_t > cp_c would pass an enthalpy-only check although Tt4 < Tt0 (1782 K)
    with pytest.raises(ValueError, match="adds no heat"):
        evaluate_cycle(_inputs(mach=6.0, tt4=1700.0, gamma_t=1.28))


def test_cycle_without_net_thrust_is_an_error() -> None:
    """A combustor barely hotter than the flight total temperature gives no net thrust."""
    with pytest.raises(ValueError, match="No net thrust"):
        evaluate_cycle(_inputs(mach=5.0, tt4=1350.0, pi_d_max=0.9, pi_b=0.9))  # Tt0 = 1300 K


def _run(**settings: float) -> RamjetCycleResults:
    analysis = MattinglyCycleAnalysis()
    analysis.setup(BaseVehicleConfig.from_toml(ALVRJ_PATH), enable_logging=False, **settings)
    return analysis.execute()


def test_analysis_on_alvrj_matches_heiser_pratt_fuel_air_ratio() -> None:
    """Both cycle solvers use the same energy balance and placeholder losses."""
    results = _run()
    heiser = HeiserPrattCycleAnalysis()
    heiser.setup(BaseVehicleConfig.from_toml(ALVRJ_PATH), enable_logging=False)
    assert results.fidelity == FidelityLevel.LEVEL_2
    assert results.inputs.mach == 2.6
    assert results.inputs.tt4 == 2150.0
    assert results.fuel_air_ratio == pytest.approx(heiser.execute().fuel_air_ratio, rel=1e-3)
    assert "combustion_efficiency" in results.assumed


def test_analysis_reads_inlet_recovery_as_pi_d_at_design_mach() -> None:
    """inlet_recovery on the ramjet becomes pi_d at design_mach."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_PATH)
    vehicle.propulsion["sustainer"].inlet_recovery = 0.85
    analysis = MattinglyCycleAnalysis()
    analysis.setup(vehicle, enable_logging=False)
    results = analysis.execute()
    assert results.pi_d == pytest.approx(0.85)
    assert "inlet_recovery" not in results.assumed


def test_analysis_settings_and_errors() -> None:
    """Settings override the TOML; bad values and unknown settings fail."""
    results = _run(mach=3.0, tt4=2200.0, pi_b=0.9, altitude_m=15000.0)
    assert results.inputs.mach == 3.0
    assert results.inputs.pi_b == 0.9
    with pytest.raises(ValueError, match="pi_b"):
        _run(pi_b=1.2)
    with pytest.raises(TypeError, match="Unknown settings"):
        _run(eta_inlet=0.9)


def test_mach_sweep_csv_and_figure() -> None:
    """The sweep spans 1.2 to 5 and the figure has four panels."""
    results = _run()
    points = run_mach_sweep(results)
    assert points[0].mach == pytest.approx(1.2)
    assert points[-1].mach == pytest.approx(5.0)
    lines = format_mach_sweep_csv(points).strip().splitlines()
    assert lines[0].startswith("mach,specific_thrust,tsfc")
    assert len(lines) == len(points) + 1
    assert len(plot_mach_sweep(points, results).axes) == 4
