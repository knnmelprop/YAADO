# MELprop-IADE | first-cell height sizing for wall-resolved RANS | v0.1.0
"""Compute the near-wall first-cell height for a target y+ via ISA + flat-plate Cf.

Standalone re-implementation of the ISA troposphere/stratosphere model
already reviewed in ``analyses/propulsion/inlet_performance.py::isa_atmosphere``
(kept separate here because that module imports scipy, which is not
installed in this meshing environment; the ISA constants and formula below
are identical — do not let the two drift apart).

Method (standard first-cell sizing recipe, e.g. NASA's turbulence-modeling
resource, https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html):
    1. Re_L = rho * V * L / mu           (Reynolds number on REF_LENGTH)
    2. Cf   = 0.026 / Re_L ** (1/7)      (turbulent flat-plate skin friction)
    3. tau_wall = 0.5 * Cf * rho * V^2
    4. u_tau    = sqrt(tau_wall / rho)
    5. y1  = y_plus_target * mu / (rho * u_tau)

This is a first-order estimate for RANS mesh sizing, not a boundary-layer
solve. It is deliberately conservative-simple: no compressibility correction
on Cf, no pressure-gradient correction. Treat the result as a starting first-
cell height to iterate on if y+ diagnostics from an actual solve disagree.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: ISA sea-level temperature [K].
T0_ISA = 288.15
#: ISA sea-level pressure [Pa].
P0_ISA = 101325.0
#: ISA tropospheric lapse rate [K/m], valid 0-11 km.
LAPSE_RATE = 0.0065
#: Altitude of the tropopause [m] (ISA).
TROPOPAUSE_ALTITUDE_M = 11000.0
#: Specific gas constant for air [J/(kg K)].
GAS_CONSTANT_AIR = 287.058
#: Standard gravity [m/s^2].
G0 = 9.80665
#: Sutherland's law reference viscosity [Pa s] and temperature [K].
MU0_SUTHERLAND = 1.716e-5
T0_SUTHERLAND = 273.15
S_SUTHERLAND = 110.4


@dataclass
class AtmosphereState:
    """Freestream atmospheric state at a given altitude (ISA model).

    Attributes:
        altitude_m: Geopotential altitude, metres.
        temperature_K: Static temperature, kelvin.
        pressure_Pa: Static pressure, pascal.
        density_kg_m3: Density, kg/m^3 (ideal gas law).
        dynamic_viscosity_Pa_s: Dynamic viscosity via Sutherland's law, Pa s.
    """

    altitude_m: float
    temperature_K: float
    pressure_Pa: float
    density_kg_m3: float
    dynamic_viscosity_Pa_s: float


def isa_atmosphere(altitude_m: float) -> AtmosphereState:
    """Compute the ISA (1976) atmospheric state at a given altitude.

    Valid 0-20 km (troposphere + lower isothermal stratosphere), matching
    ``analyses/propulsion/inlet_performance.py::isa_atmosphere``.

    Args:
        altitude_m: Geopotential altitude, metres.

    Returns:
        The atmospheric state at that altitude.
    """
    exponent = G0 / (GAS_CONSTANT_AIR * LAPSE_RATE)
    if altitude_m <= TROPOPAUSE_ALTITUDE_M:
        temperature_K = T0_ISA - LAPSE_RATE * altitude_m
        pressure_Pa = P0_ISA * (temperature_K / T0_ISA) ** exponent
    else:
        t11 = T0_ISA - LAPSE_RATE * TROPOPAUSE_ALTITUDE_M
        p11 = P0_ISA * (t11 / T0_ISA) ** exponent
        temperature_K = t11
        pressure_Pa = p11 * math.exp(
            -G0 * (altitude_m - TROPOPAUSE_ALTITUDE_M) / (GAS_CONSTANT_AIR * t11)
        )
    density_kg_m3 = pressure_Pa / (GAS_CONSTANT_AIR * temperature_K)
    mu = (
        MU0_SUTHERLAND
        * (temperature_K / T0_SUTHERLAND) ** 1.5
        * (T0_SUTHERLAND + S_SUTHERLAND)
        / (temperature_K + S_SUTHERLAND)
    )
    return AtmosphereState(
        altitude_m=altitude_m,
        temperature_K=temperature_K,
        pressure_Pa=pressure_Pa,
        density_kg_m3=density_kg_m3,
        dynamic_viscosity_Pa_s=mu,
    )


def first_cell_height_m(
    mach: float,
    altitude_m: float,
    ref_length_m: float,
    y_plus_target: float = 1.0,
    gamma: float = 1.4,
) -> float:
    """First near-wall cell height for a target y+ (turbulent flat-plate Cf).

    Args:
        mach: Freestream Mach number.
        altitude_m: ISA altitude, metres.
        ref_length_m: Reference length for the Reynolds number (e.g. body
            length to the station of interest), metres.
        y_plus_target: Target dimensionless wall distance (default 1.0 for
            wall-resolved SA/SST).
        gamma: Ratio of specific heats (default 1.4, calorically perfect air).

    Returns:
        First-cell height, metres.
    """
    atm = isa_atmosphere(altitude_m)
    speed_of_sound = math.sqrt(gamma * GAS_CONSTANT_AIR * atm.temperature_K)
    velocity = mach * speed_of_sound
    reynolds = atm.density_kg_m3 * velocity * ref_length_m / atm.dynamic_viscosity_Pa_s
    cf = 0.026 / reynolds ** (1.0 / 7.0)
    tau_wall = 0.5 * cf * atm.density_kg_m3 * velocity**2
    u_tau = math.sqrt(tau_wall / atm.density_kg_m3)
    return y_plus_target * atm.dynamic_viscosity_Pa_s / (atm.density_kg_m3 * u_tau)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mach", type=float, required=True)
    p.add_argument("--altitude-m", type=float, required=True)
    p.add_argument("--ref-length-m", type=float, required=True)
    p.add_argument("--y-plus", type=float, default=1.0)
    a = p.parse_args()

    atm = isa_atmosphere(a.altitude_m)
    y1 = first_cell_height_m(a.mach, a.altitude_m, a.ref_length_m, a.y_plus)
    print(f"ISA @ {a.altitude_m:.0f} m: T={atm.temperature_K:.2f} K  P={atm.pressure_Pa:.1f} Pa"
          f"  rho={atm.density_kg_m3:.5f} kg/m^3  mu={atm.dynamic_viscosity_Pa_s:.3e} Pa s")
    print(f"Mach {a.mach}, ref_length {a.ref_length_m} m -> "
          f"first cell height for y+={a.y_plus}: {y1*1e6:.2f} um ({y1:.3e} m)")
