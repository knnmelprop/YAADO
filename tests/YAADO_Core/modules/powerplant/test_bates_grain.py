"""Tests for the BATES grain solver and the conical-nozzle thrust coefficient.

The C_F reference values were calculated with an independent script from NACA Report
1135 Eq. 44 and Eq. 80, the conical cone loss and the pressure term. They are not copied
from a published table.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from YAADO_Core.Foundation.constants import G0
from YAADO_Core.modules.powerplant.motor_methods.bates import (
    BatesGrainConfig,
    bates_burn_area,
    neutral_segment_length,
    nozzle_thrust_coefficient,
    solve_bates_burn,
)

DO = 0.0762
DI = 0.0254
BURN_COEFF = 0.0075 / 6.9e6**0.35  # r = 7.5 mm/s at 6.9 MPa


def make_config(**overrides: float) -> BatesGrainConfig:
    """Build a 4-segment, neutral-burning BATES motor, with optional overrides."""
    params: dict[str, float] = {
        "outer_diameter": DO,
        "core_diameter": DI,
        "segment_length": neutral_segment_length(DO, DI),
        "n_segments": 4,
        "burn_rate_coefficient": BURN_COEFF,
        "burn_rate_exponent": 0.35,
        "propellant_density": 1750.0,
        "characteristic_velocity": 1500.0,
        "throat_area": math.pi / 4.0 * 0.019**2,
        "nozzle_area_ratio": 6.0,
        "nozzle_half_angle": math.radians(12.0),
        "gamma": 1.22,
        "ambient_pressure": 101325.0,
    }
    params.update(overrides)
    return BatesGrainConfig(**params)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("area_ratio", "half_angle_rad", "gamma", "pa_over_pc", "expected"),
    [
        (4.0, 0.0, 1.4, 0.0, 1.5611),
        (4.0, 0.0, 1.4, 0.02979, 1.4420),
        (16.0, math.radians(20.0), 1.4, 0.00364, 1.5706),
        (9.0, math.radians(15.0), 1.2, 0.0, 1.7016),
        (9.0, math.radians(15.0), 1.2, 0.01, 1.6116),
    ],
)
def test_thrust_coefficient_reference_values(
    area_ratio: float,
    half_angle_rad: float,
    gamma: float,
    pa_over_pc: float,
    expected: float,
) -> None:
    """C_F agrees with the independently calculated values to 0.001."""
    value = nozzle_thrust_coefficient(area_ratio, half_angle_rad, gamma, pa_over_pc)
    assert value == pytest.approx(expected, abs=1e-3)


def test_thrust_coefficient_falls_with_half_angle() -> None:
    """A larger cone half-angle gives a smaller C_F."""
    small = nozzle_thrust_coefficient(9.0, math.radians(10.0), 1.2)
    large = nozzle_thrust_coefficient(9.0, math.radians(25.0), 1.2)
    assert large < small


def test_thrust_coefficient_falls_with_ambient_pressure() -> None:
    """A larger ambient pressure ratio gives a smaller C_F."""
    vacuum = nozzle_thrust_coefficient(9.0, math.radians(15.0), 1.2, 0.0)
    ambient = nozzle_thrust_coefficient(9.0, math.radians(15.0), 1.2, 0.02)
    assert ambient < vacuum


@pytest.mark.parametrize(
    ("area_ratio", "half_angle_rad", "gamma", "pa_over_pc"),
    [
        (1.0, 0.1, 1.4, 0.0),
        (0.5, 0.1, 1.4, 0.0),
        (4.0, 0.1, 1.0, 0.0),
        (4.0, 0.1, 0.9, 0.0),
        (4.0, -0.01, 1.4, 0.0),
        (4.0, math.pi / 2.0, 1.4, 0.0),
        (4.0, 0.1, 1.4, -0.1),
    ],
)
def test_thrust_coefficient_rejects_invalid_input(
    area_ratio: float, half_angle_rad: float, gamma: float, pa_over_pc: float
) -> None:
    """Invalid nozzle inputs raise ValueError."""
    with pytest.raises(ValueError):
        nozzle_thrust_coefficient(area_ratio, half_angle_rad, gamma, pa_over_pc)


def test_neutral_length_gives_equal_burn_area() -> None:
    """With L = (3 Do + Di) / 2 the burning area at ignition equals that at burnout."""
    config = make_config()
    start = float(bates_burn_area(config, 0.0))
    end = float(bates_burn_area(config, config.web))
    assert end == pytest.approx(start, rel=1e-12)


def test_burn_area_at_ignition_matches_closed_form() -> None:
    """At w = 0 the area is N (pi Di L + pi/2 (Do^2 - Di^2)) (textbook BATES)."""
    config = make_config(n_segments=1, segment_length=0.15)
    expected = math.pi * DI * 0.15 + 0.5 * math.pi * (DO**2 - DI**2)
    assert float(bates_burn_area(config, 0.0)) == pytest.approx(expected, rel=1e-12)


def test_long_segment_is_progressive_and_short_is_regressive() -> None:
    """The burning area rises for a longer segment and falls for a shorter one."""
    neutral = neutral_segment_length(DO, DI)
    longer = make_config(segment_length=neutral + 0.05)
    shorter = make_config(segment_length=neutral - 0.02)
    assert float(bates_burn_area(longer, longer.web)) > float(
        bates_burn_area(longer, 0.0)
    )
    assert float(bates_burn_area(shorter, shorter.web)) < float(
        bates_burn_area(shorter, 0.0)
    )


def test_mass_conservation() -> None:
    """The integral of the mass flow equals the propellant mass."""
    config = make_config()
    profile = solve_bates_burn(config)
    burned = config.propellant_mass - profile.propellant_mass
    assert profile.propellant_mass[0] == pytest.approx(
        config.propellant_mass, rel=1e-12
    )
    assert profile.propellant_mass[-1] == pytest.approx(0.0, abs=1e-9)
    mdot = -np.gradient(profile.propellant_mass, profile.t)
    assert float(np.trapezoid(mdot, profile.t)) == pytest.approx(
        config.propellant_mass, rel=1e-3
    )
    assert burned[-1] == pytest.approx(config.propellant_mass, rel=1e-12)


def test_mass_flow_matches_nozzle_flow() -> None:
    """Quasi-steady balance: dm/dt = Pc At / c* at every step (interior points)."""
    config = make_config()
    profile = solve_bates_burn(config, n_steps=800)
    mdot = -np.gradient(profile.propellant_mass, profile.t)
    nozzle = (
        profile.chamber_pressure * config.throat_area / config.characteristic_velocity
    )
    assert mdot[5:-5] == pytest.approx(nozzle[5:-5], rel=5e-3)


def test_neutral_grain_has_equal_start_and_end_pressure() -> None:
    """A neutral grain starts and ends the burn at the same chamber pressure."""
    profile = solve_bates_burn(make_config())
    assert profile.chamber_pressure[0] == pytest.approx(
        profile.chamber_pressure[-1], rel=1e-9
    )
    assert profile.thrust[0] == pytest.approx(profile.thrust[-1], rel=1e-9)


def test_chamber_pressure_follows_saint_robert_balance() -> None:
    """Pc at ignition equals (a rho c* Ab / At)^(1 / (1 - n))."""
    config = make_config()
    profile = solve_bates_burn(config)
    ab = float(bates_burn_area(config, 0.0))
    expected = (BURN_COEFF * 1750.0 * 1500.0 * ab / config.throat_area) ** (
        1.0 / (1.0 - config.burn_rate_exponent)
    )
    assert profile.chamber_pressure[0] == pytest.approx(expected, rel=1e-12)


def test_burn_time_matches_web_over_mean_rate() -> None:
    """For n = 0 the pressure scales with Ab, so r = a Pc^0 = a and t_burn = web / a."""
    config = make_config(burn_rate_exponent=0.0, burn_rate_coefficient=0.008)
    profile = solve_bates_burn(config)
    assert profile.burn_time == pytest.approx(config.web / 0.008, rel=1e-9)


def test_specific_impulse_is_physical() -> None:
    """Delivered Isp is close to c* C_F / g0 for the nearly constant C_F."""
    config = make_config()
    profile = solve_bates_burn(config)
    cf_mid = nozzle_thrust_coefficient(
        config.nozzle_area_ratio,
        config.nozzle_half_angle,
        config.gamma,
        config.ambient_pressure / float(profile.chamber_pressure[0]),
    )
    assert profile.specific_impulse == pytest.approx(
        config.characteristic_velocity * cf_mid / G0, rel=0.03
    )
    assert 150.0 < profile.specific_impulse < 300.0


def test_profile_is_immutable_and_arrays_are_aligned() -> None:
    """The profile is frozen and all arrays share one length."""
    profile = solve_bates_burn(make_config(), n_steps=50)
    lengths = {len(a) for a in (profile.t, profile.chamber_pressure, profile.thrust)}
    assert lengths == {51}
    assert np.all(np.diff(profile.t) > 0.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.t = np.zeros(3)  # type: ignore[misc]


@pytest.mark.parametrize(
    "override",
    [
        {"core_diameter": DO},
        {"segment_length": 0.04},
        {"n_segments": 0},
        {"burn_rate_exponent": 1.0},
        {"throat_area": 0.0},
        {"ambient_pressure": -1.0},
    ],
)
def test_config_rejects_invalid_values(override: dict[str, float]) -> None:
    """Invalid grain data raises ValueError."""
    with pytest.raises(ValueError):
        make_config(**override)


def test_solver_rejects_too_few_steps() -> None:
    """At least two web intervals are needed."""
    with pytest.raises(ValueError):
        solve_bates_burn(make_config(), n_steps=1)
