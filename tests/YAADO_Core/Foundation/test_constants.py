"""Unit tests for YAADO_Core.Foundation.constants."""

import math
import pytest

import YAADO_Core.Foundation.constants as const


def test_standard_physical_constants_values() -> None:
    """Universal constants match exact CODATA / ICAO standards."""
    assert const.G0 == pytest.approx(9.80665)
    assert const.P0_ISA == pytest.approx(101325.0)
    assert const.T0_ISA == pytest.approx(288.15)
    assert const.M_AIR == pytest.approx(0.0289644)


def test_thermodynamic_gas_relations() -> None:
    """Calorically perfect gas identities hold for dry air."""
    assert const.GAMMA_AIR == pytest.approx(1.4)
    assert const.R_AIR == pytest.approx(287.05287, rel=1e-4)

    # Mayer's relation: cp - cv = R
    assert (const.CP_AIR - const.CV_AIR) == pytest.approx(const.R_AIR)

    # Specific heat ratio: gamma = cp / cv
    assert (const.CP_AIR / const.CV_AIR) == pytest.approx(const.GAMMA_AIR)

    # Ideal gas law at sea level: p0 = rho0 * R * T0
    expected_rho0 = const.P0_ISA / (const.R_AIR * const.T0_ISA)
    assert const.RHO0_ISA == pytest.approx(expected_rho0)
    assert const.RHO0_ISA == pytest.approx(1.225, rel=1e-3)

    # Speed of sound at sea level: a0 = sqrt(gamma * R * T0)
    expected_a0 = math.sqrt(const.GAMMA_AIR * const.R_AIR * const.T0_ISA)
    assert const.A0_ISA == pytest.approx(expected_a0)
    assert const.A0_ISA == pytest.approx(340.294, rel=1e-4)


def test_isa_troposphere_layer_constants() -> None:
    """ISA troposphere lapse rate and tropopause boundary match ICAO Doc 7488."""
    assert const.LAPSE_RATE_TROPOSPHERE == pytest.approx(0.0065)
    assert const.H_TROPOPAUSE == pytest.approx(11000.0)

    # Tropopause temperature: T = 288.15 - 0.0065 * 11000 = 216.65 K
    assert const.T_TROPOPAUSE == pytest.approx(216.65)

    # Barometric exponent: g0 / (L * R) ~ 5.2559
    assert const.ISA_PRESSURE_EXPONENT == pytest.approx(5.2559, rel=1e-3)


def test_sutherland_constants() -> None:
    """Sutherland viscosity constants match ICAO specifications."""
    assert const.SUTHERLAND_T == pytest.approx(110.4)
    assert const.SUTHERLAND_MU0 == pytest.approx(1.7894e-5)

