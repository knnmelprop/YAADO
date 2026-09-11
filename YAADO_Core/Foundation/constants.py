"""Physical and atmospheric constants for the YAADO framework.

All constants are expressed in canonical SI units:
- Acceleration: [m/s^2]
- Pressure: [Pa]
- Temperature: [K]
- Density: [kg/m^3]
- Specific energy / gas constants: [J/(kg*K)]
- Velocity: [m/s]
- Dynamic viscosity: [Pa*s]

References:
- ICAO Standard Atmosphere (ICAO Doc 7488 / Manual of the ICAO Standard Atmosphere).
- US Standard Atmosphere (1976), NASA-TM-X-74335.
- CODATA 2018 fundamental constants via `scipy.constants`.
"""

from __future__ import annotations

import scipy.constants as _sc

# -----------------------------------------------------------------------------
# Fundamental & Universal Physical Constants
# -----------------------------------------------------------------------------

G0: float = _sc.g
"""Standard acceleration of gravity at sea level [m/s^2] (exact: 9.80665)."""

R_UNIVERSAL: float = _sc.R
"""Universal molar gas constant [J/(mol*K)] (8.314462618...)."""

P0_ISA: float = _sc.atm
"""ICAO/ISA sea-level standard atmospheric pressure [Pa] (exact: 101325.0)."""

T0_ISA: float = 288.15
"""ICAO/ISA sea-level standard atmospheric temperature [K] (15.0 °C)."""

# -----------------------------------------------------------------------------
# Properties of Dry Air (ICAO Standard Atmosphere)
# -----------------------------------------------------------------------------

M_AIR: float = 0.0289644
"""Mean molar mass of dry air at sea level [kg/mol] (ICAO Doc 7488)."""

R_AIR: float = 287.05287
"""Specific gas constant of dry air [J/(kg*K)] (ICAO Doc 7488)."""

GAMMA_AIR: float = 1.4
"""Ratio of specific heats for dry air under calorically perfect gas assumptions [-]."""

CP_AIR: float = (GAMMA_AIR * R_AIR) / (GAMMA_AIR - 1.0)
"""Specific heat of dry air at constant pressure [J/(kg*K)] (~1004.685)."""

CV_AIR: float = CP_AIR - R_AIR
"""Specific heat of dry air at constant volume [J/(kg*K)] (~717.632)."""

RHO0_ISA: float = P0_ISA / (R_AIR * T0_ISA)
"""ICAO sea-level standard atmospheric air density [kg/m^3] (~1.2250)."""

A0_ISA: float = (GAMMA_AIR * R_AIR * T0_ISA) ** 0.5
"""ICAO sea-level standard speed of sound in air [m/s] (~340.294)."""

# -----------------------------------------------------------------------------
# ISA Troposphere Layer (0 <= h < 11,000 m)
# -----------------------------------------------------------------------------

LAPSE_RATE_TROPOSPHERE: float = 0.0065
"""Troposphere temperature lapse rate (-dT/dh) [K/m] (ICAO Doc 7488)."""

H_TROPOPAUSE: float = 11000.0
"""Altitude of the tropopause boundary [m]."""

T_TROPOPAUSE: float = T0_ISA - LAPSE_RATE_TROPOSPHERE * H_TROPOPAUSE
"""Temperature at the tropopause boundary [K] (exact: 216.65)."""

ISA_PRESSURE_EXPONENT: float = G0 / (LAPSE_RATE_TROPOSPHERE * R_AIR)
"""Troposphere barometric pressure exponent g0 / (L * R_air) [-] (~5.2559)."""

# -----------------------------------------------------------------------------
# Dynamic Viscosity (Sutherland's Law for Air)
# -----------------------------------------------------------------------------

SUTHERLAND_T: float = 110.4
"""Sutherland reference temperature constant for dry air [K]."""

SUTHERLAND_MU0: float = 1.7894e-5
"""Reference dynamic viscosity of dry air at T0_ISA [Pa*s] (ICAO Doc 7488)."""
