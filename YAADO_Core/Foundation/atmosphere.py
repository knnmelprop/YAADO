"""Standard atmospheric models for the YAADO framework.

Evaluates the International Civil Aviation Organization (ICAO) 1993 Standard
Atmosphere (ISO 2533 compliant) from sea level to 80,000 meters geometric altitude.
All outputs are strictly returned in canonical SI units.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from ambiance import Atmosphere

import YAADO_Core.Foundation.constants as const


@dataclass(frozen=True)
class AtmosphereState:
    """Atmospheric state evaluated at a specific altitude in canonical SI units.

    Attributes:
        temperature: Static temperature [K].
        pressure: Static atmospheric pressure [Pa].
        density: Atmospheric air density [kg/m^3].
        speed_of_sound: Local speed of sound in air [m/s].
        dynamic_viscosity: Dynamic air viscosity via Sutherland's formula [Pa*s].
    """

    temperature: float
    pressure: float
    density: float
    speed_of_sound: float
    dynamic_viscosity: float


@dataclass(frozen=True)
class AtmosphereArrayState:
    """Vectorized atmospheric state evaluated across multiple altitudes in canonical SI units.

    Attributes:
        temperature: Static temperature array [K].
        pressure: Static atmospheric pressure array [Pa].
        density: Atmospheric air density array [kg/m^3].
        speed_of_sound: Local speed of sound array [m/s].
        dynamic_viscosity: Dynamic air viscosity array [Pa*s].
    """

    temperature: np.ndarray
    pressure: np.ndarray
    density: np.ndarray
    speed_of_sound: np.ndarray
    dynamic_viscosity: np.ndarray


def isa_atmosphere(altitude: float, delta_t_isa: float = 0.0) -> AtmosphereState:
    """Evaluate standard atmosphere properties at a single geometric altitude.

    Uses the ICAO 1993 Standard Atmosphere model (via ``ambiance``), supporting
    troposphere, tropopause, stratosphere, and mesosphere layers from -5,000 m
    to 80,000 m geometric altitude. Altitudes below :data:`~YAADO_Core.Foundation.constants.H_MIN_ISA`
    are clamped to the ICAO lower boundary.

    Args:
        altitude: Geometric altitude above mean sea level [m]. Accepts a scalar
            float. Supports negative altitudes (e.g. Dead Sea depression at -430 m).
        delta_t_isa: Temperature offset from standard day [K] (e.g. ``+10.0``
            for an ISA + 10 °C hot day). Defaults to 0.0 (nominal day).

    Returns:
        :class:`AtmosphereState` containing temperature, pressure, density,
        speed of sound, and dynamic viscosity in canonical SI units as floats.
    """
    h_eval = max(float(altitude), const.H_MIN_ISA)
    base = Atmosphere(h_eval)

    t_nominal = float(base.temperature[0])
    p = float(base.pressure[0])
    mu = float(base.dynamic_viscosity[0])

    if delta_t_isa != 0.0:
        t = t_nominal + delta_t_isa
        rho = p / (const.R_AIR * t)
        a = (const.GAMMA_AIR * const.R_AIR * t) ** 0.5
    else:
        t = t_nominal
        rho = float(base.density[0])
        a = float(base.speed_of_sound[0])

    return AtmosphereState(
        temperature=t,
        pressure=p,
        density=rho,
        speed_of_sound=a,
        dynamic_viscosity=mu,
    )


def isa_atmosphere_array(
    altitudes: np.ndarray | Sequence[float], delta_t_isa: float = 0.0
) -> AtmosphereArrayState:
    """Evaluate standard atmosphere properties for an array or sequence of altitudes.

    Args:
        altitudes: 1D array or sequence of geometric altitudes [m].
        delta_t_isa: Temperature offset from standard day [K]. Defaults to 0.0.

    Returns:
        :class:`AtmosphereArrayState` containing properties as 1D NumPy arrays.
    """
    arr = np.asarray(altitudes, dtype=float)
    h_eval = np.maximum(arr, const.H_MIN_ISA)
    base = Atmosphere(h_eval)

    t_nominal = np.asarray(base.temperature)
    p = np.asarray(base.pressure)
    mu = np.asarray(base.dynamic_viscosity)

    if delta_t_isa != 0.0:
        t = t_nominal + delta_t_isa
        rho = p / (const.R_AIR * t)
        a = (const.GAMMA_AIR * const.R_AIR * t) ** 0.5
    else:
        t = t_nominal
        rho = np.asarray(base.density)
        a = np.asarray(base.speed_of_sound)

    return AtmosphereArrayState(
        temperature=t,
        pressure=p,
        density=rho,
        speed_of_sound=a,
        dynamic_viscosity=mu,
    )
