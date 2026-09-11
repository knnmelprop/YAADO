"""Unit tests for YAADO_Core.Foundation.atmosphere."""

import pytest

import YAADO_Core.Foundation.constants as const
from YAADO_Core.Foundation.atmosphere import AtmosphereState, isa_atmosphere


def test_isa_atmosphere_sea_level() -> None:
    """Sea level atmosphere matches standard ICAO conditions."""
    atm = isa_atmosphere(0.0)

    assert isinstance(atm, AtmosphereState)
    assert atm.temperature == pytest.approx(const.T0_ISA, rel=1e-4)
    assert atm.pressure == pytest.approx(const.P0_ISA, rel=1e-4)
    assert atm.density == pytest.approx(const.RHO0_ISA, rel=1e-3)
    assert atm.speed_of_sound == pytest.approx(const.A0_ISA, rel=1e-4)
    assert atm.dynamic_viscosity == pytest.approx(const.SUTHERLAND_MU0, rel=1e-3)


def test_isa_atmosphere_below_sea_level() -> None:
    """Atmosphere below sea level (e.g. Dead Sea at -430 m) has higher density and pressure."""
    atm_dead_sea = isa_atmosphere(-430.0)
    atm_sea_level = isa_atmosphere(0.0)

    # In depressions below sea level, air is warmer, denser, and at higher pressure
    assert atm_dead_sea.pressure > atm_sea_level.pressure
    assert atm_dead_sea.density > atm_sea_level.density
    assert atm_dead_sea.temperature > atm_sea_level.temperature
    assert atm_dead_sea.pressure == pytest.approx(106598.0, rel=1e-3)


def test_isa_atmosphere_clamps_below_icao_minimum() -> None:
    """Altitudes below -5000 m are clamped to the ICAO lower bound."""
    atm_extreme = isa_atmosphere(-6000.0)
    atm_bound = isa_atmosphere(-5000.0)

    assert atm_extreme.pressure == pytest.approx(atm_bound.pressure)
    assert atm_extreme.temperature == pytest.approx(atm_bound.temperature)
    assert atm_extreme.density == pytest.approx(atm_bound.density)


def test_isa_atmosphere_tropopause() -> None:
    """Atmosphere evaluated at 11,000 m matches tropopause characteristics."""
    atm = isa_atmosphere(11000.0)

    # Around 11 km geopotential/geometric, temperature is ~216.65-216.77 K
    assert atm.temperature == pytest.approx(const.T_TROPOPAUSE, abs=0.5)
    # Pressure at 11 km is ~22.6-22.7 kPa
    assert 22000.0 < atm.pressure < 23000.0
    assert 0.35 < atm.density < 0.38


def test_isa_atmosphere_stratosphere() -> None:
    """Atmosphere in the lower stratosphere (15 km) remains isothermal."""
    atm_11k = isa_atmosphere(11000.0)
    atm_15k = isa_atmosphere(15000.0)

    # In lower stratosphere (11-20 km), temperature is constant within ~0.2 K
    assert atm_15k.temperature == pytest.approx(atm_11k.temperature, abs=0.5)
    # Pressure decays with altitude
    assert atm_15k.pressure < atm_11k.pressure
    assert atm_15k.density < atm_11k.density


def test_isa_atmosphere_delta_t_isa() -> None:
    """Hot day delta_t_isa shifts temperature and adjusts density and speed of sound."""
    delta_t = 10.0
    atm_nominal = isa_atmosphere(2000.0)
    atm_hot = isa_atmosphere(2000.0, delta_t_isa=delta_t)

    assert atm_hot.temperature == pytest.approx(atm_nominal.temperature + delta_t)
    assert atm_hot.pressure == pytest.approx(atm_nominal.pressure)
    # Hot air is less dense at the same pressure
    assert atm_hot.density < atm_nominal.density
    # Speed of sound is higher in warmer air
    assert atm_hot.speed_of_sound > atm_nominal.speed_of_sound
