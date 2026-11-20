"""Tests for the parachute descent analysis (drogue and main) and its sizing helpers."""

from __future__ import annotations

import math

import matplotlib
import numpy as np
import pytest

from YAADO_Core.Foundation.atmosphere import isa_atmosphere
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.flight_dynamics.containers import (
    ParachuteConfig,
    ParachuteDescentResults,
    PointMassBoostResults,
)
from YAADO_Core.modules.flight_dynamics.methods.parachute_descent import (
    ParachuteDescentAnalysis,
    plot_descent,
    size_main_diameter,
    steady_descent_speed,
)
from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
    PointMass3DOFBoostAnalysis,
)

matplotlib.use("Agg")

MASS = 12.0  # burnout mass of the generic rocket: 20 kg minus 8 kg propellant
DROGUE_CD = 1.5
DROGUE_D = 0.6
MAIN_CD = 2.2
MAIN_ALT = 300.0
TARGET_SPEED = 6.0


def run_descent(
    vehicle: BaseVehicleConfig, flight: PointMassBoostResults, config: ParachuteConfig
) -> ParachuteDescentResults:
    """Run the parachute descent analysis for a vehicle, a full flight and a config."""
    analysis = ParachuteDescentAnalysis()
    analysis.setup(vehicle, flight=flight, parachutes=config, enable_logging=False)
    return analysis.execute()


@pytest.fixture(scope="module")
def main_diameter() -> float:
    """Main parachute diameter sized for the target landing speed at sea level."""
    return size_main_diameter(MASS, TARGET_SPEED, MAIN_CD)


@pytest.fixture(scope="module")
def config(main_diameter: float) -> ParachuteConfig:
    """Parachute inputs with a 7 m/s landing-speed limit."""
    return ParachuteConfig(
        drogue_cd=DROGUE_CD,
        drogue_diameter=DROGUE_D,
        main_cd=MAIN_CD,
        main_diameter=main_diameter,
        main_deployment_altitude=MAIN_ALT,
        descent_speed_limit=7.0,
    )


@pytest.fixture(scope="module")
def descent(
    generic_rocket: BaseVehicleConfig,
    full_flight: PointMassBoostResults,
    config: ParachuteConfig,
) -> ParachuteDescentResults:
    """Descent results of the generic rocket with the base parachute config."""
    return run_descent(generic_rocket, full_flight, config)


def test_steady_speed_formula() -> None:
    """v = sqrt(2 m g / (rho Cd A)) with the ISA density at the altitude."""
    rho = isa_atmosphere(1500.0).density
    area = math.pi / 4.0 * 1.2**2
    expected = math.sqrt(2.0 * 15.0 * 9.80665 / (rho * 1.8 * area))
    assert steady_descent_speed(15.0, 1.8, 1.2, 1500.0) == pytest.approx(
        expected, rel=1e-12
    )


def test_simulated_speeds_match_steady_speed(
    descent: ParachuteDescentResults, main_diameter: float
) -> None:
    """The speeds under the drogue and the main match the steady speed at their altitude."""
    drogue_expected = steady_descent_speed(MASS, DROGUE_CD, DROGUE_D, MAIN_ALT)
    main_expected = steady_descent_speed(MASS, MAIN_CD, main_diameter, 0.0)
    assert descent.drogue_descent_speed == pytest.approx(drogue_expected, rel=0.01)
    assert descent.main_descent_speed == pytest.approx(main_expected, rel=0.005)


def test_sizing_round_trip(
    generic_rocket: BaseVehicleConfig, full_flight: PointMassBoostResults
) -> None:
    """Size the main for a speed, simulate, and get that speed back at landing."""
    target = 5.0
    diameter = size_main_diameter(MASS, target, MAIN_CD)
    config = ParachuteConfig(DROGUE_CD, DROGUE_D, MAIN_CD, diameter, MAIN_ALT)
    results = run_descent(generic_rocket, full_flight, config)
    assert results.main_descent_speed == pytest.approx(target, rel=0.005)


def test_sizing_formula_and_validation() -> None:
    """D = sqrt(8 m g / (pi rho Cd v^2)); invalid inputs raise ValueError."""
    rho = isa_atmosphere(0.0).density
    expected = math.sqrt(8.0 * 12.0 * 9.80665 / (math.pi * rho * 2.2 * 6.0**2))
    assert size_main_diameter(12.0, 6.0, 2.2) == pytest.approx(expected, rel=1e-12)
    assert size_main_diameter(12.0, 3.0, 2.2) == pytest.approx(
        2.0 * expected, rel=1e-12
    )
    for args in ((0.0, 6.0, 2.2), (12.0, 0.0, 2.2), (12.0, 6.0, -1.0)):
        with pytest.raises(ValueError):
            size_main_diameter(*args)


def test_result_fields_are_consistent(
    descent: ParachuteDescentResults, full_flight: PointMassBoostResults
) -> None:
    """Times, positions and the mass follow from the apogee state."""
    assert descent.mass == pytest.approx(MASS)
    assert descent.apogee_altitude == full_flight.apogee_altitude
    samples = descent.samples
    assert samples is not None
    assert samples.t_s[0] == pytest.approx(full_flight.apogee_time)
    assert samples.x_m[0] == pytest.approx(full_flight.apogee_range)
    assert samples.h_m[0] == pytest.approx(full_flight.apogee_altitude)
    assert samples.h_m[-1] == pytest.approx(0.0, abs=1e-3)
    assert descent.descent_time == pytest.approx(samples.t_s[-1] - samples.t_s[0])
    assert 0.0 < descent.main_deployment_time < descent.descent_time
    assert np.all(np.diff(samples.h_m) <= 1e-9)
    assert samples.t_s[samples.main_open_idx] - samples.t_s[0] == pytest.approx(
        descent.main_deployment_time
    )


def test_landing_x_between_apogee_and_ballistic_drift(
    descent: ParachuteDescentResults, full_flight: PointMassBoostResults
) -> None:
    """Drag slows the horizontal motion: landing x is past apogee, short of coasting."""
    assert descent.samples is not None
    vx0 = float(descent.samples.vx_ms[0])
    assert vx0 > 0.0
    assert (
        full_flight.apogee_range
        < descent.landing_x
        < full_flight.apogee_range + vx0 * descent.descent_time
    )


def test_peak_deceleration_at_main_opening(
    descent: ParachuteDescentResults, main_diameter: float
) -> None:
    """The peak drag deceleration is the main's drag at the opening speed, divided by mass."""
    samples = descent.samples
    assert samples is not None
    i = samples.main_open_idx
    rho = isa_atmosphere(float(samples.h_m[i])).density
    area = math.pi / 4.0 * main_diameter**2
    expected = 0.5 * rho * float(samples.speed_ms[i]) ** 2 * MAIN_CD * area / MASS
    assert descent.peak_deceleration == pytest.approx(expected, rel=1e-3)
    assert descent.peak_deceleration > 9.80665


def test_limit_flag_in_results(
    generic_rocket: BaseVehicleConfig,
    full_flight: PointMassBoostResults,
    config: ParachuteConfig,
    descent: ParachuteDescentResults,
) -> None:
    """The analysis reports True within the limit and None without a limit."""
    assert descent.landing_speed_within_limit is True
    tight = ParachuteConfig(
        config.drogue_cd,
        config.drogue_diameter,
        config.main_cd,
        config.main_diameter,
        config.main_deployment_altitude,
        descent_speed_limit=5.0,
    )
    assert (
        run_descent(generic_rocket, full_flight, tight).landing_speed_within_limit
        is False
    )


def test_main_above_apogee_opens_at_apogee(
    generic_rocket: BaseVehicleConfig,
    full_flight: PointMassBoostResults,
    main_diameter: float,
) -> None:
    """A main deployment altitude above the apogee skips the drogue phase."""
    config = ParachuteConfig(DROGUE_CD, DROGUE_D, MAIN_CD, main_diameter, 20000.0)
    results = run_descent(generic_rocket, full_flight, config)
    assert results.samples is not None
    assert results.samples.main_open_idx == 0
    assert results.main_deployment_time == 0.0
    assert results.main_descent_speed == pytest.approx(TARGET_SPEED, rel=0.01)


def test_scalars_and_units(descent: ParachuteDescentResults) -> None:
    """Scalar outputs carry units and the headline metrics exist."""
    scalars = descent.scalars()
    for name in ParachuteDescentResults.headline_metrics():
        assert name in scalars
    assert descent.units()["peak_deceleration"] == "m/s^2"


def test_config_validation() -> None:
    """Non-positive parachute inputs raise ValueError."""
    good = (1.5, 0.6, 2.2, 1.7, 300.0)
    ParachuteConfig(*good)
    for index in range(5):
        bad = list(good)
        bad[index] = 0.0
        with pytest.raises(ValueError):
            ParachuteConfig(*bad)
    with pytest.raises(ValueError):
        ParachuteConfig(*good, descent_speed_limit=0.0)


def test_setup_rejects_boost_only_flight(
    generic_rocket: BaseVehicleConfig, config: ParachuteConfig
) -> None:
    """A burnout-only flight has no apogee, so the descent cannot start."""
    analysis = PointMass3DOFBoostAnalysis()
    analysis.setup(generic_rocket, stop_at_burnout=True, enable_logging=False)
    boost_only = analysis.execute()
    descent = ParachuteDescentAnalysis()
    with pytest.raises(ValueError):
        descent.setup(
            generic_rocket, flight=boost_only, parachutes=config, enable_logging=False
        )


def test_setup_requires_flight_and_parachutes(
    generic_rocket: BaseVehicleConfig,
) -> None:
    """setup() without the flight or the parachute inputs raises ValueError."""
    with pytest.raises(ValueError):
        ParachuteDescentAnalysis().setup(generic_rocket, enable_logging=False)


def test_execute_before_setup_raises() -> None:
    """Executing without setup raises RuntimeError."""
    with pytest.raises(RuntimeError):
        ParachuteDescentAnalysis().execute()


def test_plot_descent(descent: ParachuteDescentResults) -> None:
    """The plot has an altitude panel and a speed panel."""
    import matplotlib.pyplot as plt

    assert descent.samples is not None
    fig = plot_descent(descent.samples)
    assert len(fig.axes) == 2
    plt.close(fig)
