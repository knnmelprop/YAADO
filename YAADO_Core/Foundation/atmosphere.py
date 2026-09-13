"""Standard atmospheric models for the YAADO framework.

Evaluates the International Civil Aviation Organization (ICAO) 1993 Standard
Atmosphere (ISO 2533 compliant) from sea level to 80,000 meters geometric altitude.
All outputs are strictly returned in canonical SI units.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ambiance import Atmosphere
import numpy as np

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

    temperature: float | np.ndarray
    pressure: float | np.ndarray
    density: float | np.ndarray
    speed_of_sound: float | np.ndarray
    dynamic_viscosity: float | np.ndarray


def isa_atmosphere(
    altitude: float | np.ndarray | Sequence[float], delta_t_isa: float = 0.0
) -> AtmosphereState:
    """Evaluate standard atmosphere properties at geometric altitude(s).

    Uses the ICAO 1993 Standard Atmosphere model (via ``ambiance``), supporting
    troposphere, tropopause, stratosphere, and mesosphere layers from -5,000 m
    to 80,000 m geometric altitude. Altitudes below :data:`~YAADO_Core.Foundation.constants.H_MIN_ISA`
    are clamped to the ICAO lower boundary.

    Args:
        altitude: Geometric altitude above mean sea level [m]. Accepts a scalar
            float or a 1D NumPy array/sequence. Supports negative altitudes
            (e.g. Dead Sea depression at -430 m).
        delta_t_isa: Temperature offset from standard day [K] (e.g. ``+10.0``
            for an ISA + 10 °C hot day). Defaults to 0.0 (nominal day).

    Returns:
        :class:`AtmosphereState` containing temperature, pressure, density,
        speed of sound, and dynamic viscosity in canonical SI units. When
        ``altitude`` is an array or sequence, the returned attributes are
        NumPy arrays; when scalar, attributes are floats.
    """
    is_array = isinstance(altitude, np.ndarray) or (
        isinstance(altitude, Sequence) and not isinstance(altitude, (str, bytes))
    )

    if is_array:
        arr = np.asarray(altitude, dtype=float)
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
    else:
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
