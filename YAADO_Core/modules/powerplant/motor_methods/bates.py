"""Internal ballistics of a BATES solid-propellant grain, and the nozzle thrust coefficient.

A BATES grain is a stack of ``N`` cylindrical segments with a central core. The outer
wall is inhibited, so the propellant burns on the core wall and on both segment ends.
After a web thickness ``w`` has burned, the core diameter is ``Di + 2 w`` and the
segment length is ``L - 2 w``.

The solver is quasi-steady. At each web ``w`` the chamber pressure is the one at which
the propellant gas generation equals the nozzle mass flow, and the burn rate follows
from Saint-Robert's law ``r = a Pc^n``. The thrust is ``F = C_F Pc At``, with ``C_F``
from :func:`nozzle_thrust_coefficient`.

References:
    * Sutton and Biblarz, *Rocket Propulsion Elements*, Ch. 11 (burn rate, grain).
    * NACA Report 1135, *Equations, Tables, and Charts for Compressible Flow*,
      Eq. 44 and Eq. 80.
    * NASA TM-105176, Eq. 7 (conical nozzle divergence loss).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq

from YAADO_Core.Foundation.constants import G0
from YAADO_Core.Foundation.units import (
    Dimensionless,
    Kilograms,
    KilogramsPerCubicMeter,
    Meters,
    MetersPerSecond,
    Newtons,
    Pascals,
    Radians,
    Seconds,
    SquareMeters,
)

#: Number of web steps used by :func:`solve_bates_burn` when the caller gives none.
DEFAULT_WEB_STEPS: int = 400


@dataclass(frozen=True)
class BatesGrainConfig:
    """Grain, propellant and nozzle data for a BATES motor.

    The burn rate is ``r = a * Pc**n`` with ``Pc`` in Pa and ``r`` in m/s, so ``a`` has
    the units ``m/s / Pa**n``.

    Attributes:
        outer_diameter: Grain outer diameter ``Do``.
        core_diameter: Initial core diameter ``Di`` (< ``Do``).
        segment_length: Length ``L`` of one segment (> ``Do - Di``).
        n_segments: Number of segments ``N`` (>= 1).
        burn_rate_coefficient: Saint-Robert coefficient ``a`` [m/s/Pa^n].
        burn_rate_exponent: Pressure exponent ``n`` (0 <= n < 1).
        propellant_density: Propellant density ``rho_prop``.
        characteristic_velocity: Characteristic velocity ``c*``.
        throat_area: Nozzle throat area ``At``.
        nozzle_area_ratio: Exit-to-throat area ratio ``epsilon`` (> 1).
        nozzle_half_angle: Half-angle ``alpha`` of the conical divergent section.
        gamma: Ratio of specific heats of the exhaust (> 1).
        ambient_pressure: Ambient pressure ``pa``, taken as constant over the burn.
    """

    outer_diameter: Meters
    core_diameter: Meters
    segment_length: Meters
    n_segments: int
    burn_rate_coefficient: float
    burn_rate_exponent: Dimensionless
    propellant_density: KilogramsPerCubicMeter
    characteristic_velocity: MetersPerSecond
    throat_area: SquareMeters
    nozzle_area_ratio: Dimensionless
    nozzle_half_angle: Radians
    gamma: Dimensionless
    ambient_pressure: Pascals = 0.0

    def __post_init__(self) -> None:
        """Validate the configuration.

        Raises:
            ValueError: If a dimension, rate or ratio is outside its valid range.
        """
        if not 0.0 < self.core_diameter < self.outer_diameter:
            raise ValueError("Need 0 < core_diameter < outer_diameter.")
        if self.segment_length <= self.outer_diameter - self.core_diameter:
            raise ValueError("segment_length must be larger than the web (Do - Di).")
        if self.n_segments < 1:
            raise ValueError("n_segments must be at least 1.")
        if not 0.0 <= self.burn_rate_exponent < 1.0:
            raise ValueError("burn_rate_exponent must satisfy 0 <= n < 1.")
        for name in (
            "burn_rate_coefficient",
            "propellant_density",
            "characteristic_velocity",
            "throat_area",
        ):
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be positive.")
        if self.ambient_pressure < 0.0:
            raise ValueError("ambient_pressure must not be negative.")

    @property
    def web(self) -> Meters:
        """Web thickness ``(Do - Di) / 2``."""
        return 0.5 * (self.outer_diameter - self.core_diameter)

    @property
    def propellant_mass(self) -> Kilograms:
        """Total propellant mass of all segments."""
        volume = (
            self.n_segments
            * 0.25
            * math.pi
            * (self.outer_diameter**2 - self.core_diameter**2)
            * self.segment_length
        )
        return self.propellant_density * volume


@dataclass(frozen=True, eq=False)
class SolidMotorBurnProfile:
    """Time history of a burning solid motor.

    All arrays have the same length and start at ignition (``t = 0``). The last point is
    burnout, when the web is consumed.

    Attributes:
        t: Time [s].
        web_burned: Web thickness burned [m].
        burn_area: Total burning surface area [m^2].
        chamber_pressure: Chamber pressure ``Pc`` [Pa].
        thrust: Thrust ``F`` [N].
        propellant_mass: Propellant mass left in the grain [kg].
    """

    t: np.ndarray
    web_burned: np.ndarray
    burn_area: np.ndarray
    chamber_pressure: np.ndarray
    thrust: np.ndarray
    propellant_mass: np.ndarray

    @property
    def burn_time(self) -> Seconds:
        """Time from ignition to burnout."""
        return float(self.t[-1])

    @property
    def total_impulse(self) -> float:
        """Total impulse ``integral F dt`` [N*s] (trapezoidal rule)."""
        return float(np.trapezoid(self.thrust, self.t))

    @property
    def average_thrust(self) -> Newtons:
        """Total impulse divided by burn time."""
        return self.total_impulse / self.burn_time

    @property
    def peak_thrust(self) -> Newtons:
        """Largest thrust over the burn."""
        return float(np.max(self.thrust))

    @property
    def specific_impulse(self) -> Seconds:
        """Delivered specific impulse ``I_tot / (m_prop g0)``."""
        return self.total_impulse / (float(self.propellant_mass[0]) * G0)


def nozzle_thrust_coefficient(
    area_ratio: float,
    half_angle_rad: float,
    gamma: float,
    ambient_pressure_ratio: float = 0.0,
) -> float:
    """Thrust coefficient of a conical nozzle (ideal isentropic flow, cone loss).

    It finds the supersonic exit Mach number ``Me`` from the area ratio (NACA 1135,
    Eq. 80), then the exit pressure ratio (Eq. 44), the momentum part of ``C_F``, and
    adds the pressure term. The cone loss ``(1 + cos(alpha)) / 2`` (NASA TM-105176,
    Eq. 7) applies to the momentum part only. Viscous losses and flow separation are
    not included.

    Args:
        area_ratio: Exit-to-throat area ratio ``epsilon`` (> 1).
        half_angle_rad: Half-angle ``alpha`` of the divergent cone [rad], 0 <= alpha < pi/2.
        gamma: Ratio of specific heats (> 1).
        ambient_pressure_ratio: Ambient to chamber pressure ``pa / Pc`` (>= 0).

    Returns:
        The thrust coefficient ``C_F``.

    Raises:
        ValueError: If ``area_ratio`` or ``gamma`` is 1 or less, if ``half_angle_rad`` is
            negative or at least 90 deg, or if ``ambient_pressure_ratio`` is negative.
    """
    if area_ratio <= 1.0:
        raise ValueError("area_ratio must be greater than 1.")
    if gamma <= 1.0:
        raise ValueError("gamma must be greater than 1.")
    if not 0.0 <= half_angle_rad < 0.5 * math.pi:
        raise ValueError("half_angle_rad must satisfy 0 <= alpha < 90 deg.")
    if ambient_pressure_ratio < 0.0:
        raise ValueError("ambient_pressure_ratio must not be negative.")

    gm1 = gamma - 1.0
    gp1 = gamma + 1.0

    def area_ratio_residual(mach: float) -> float:
        """Isentropic area ratio at ``mach`` minus the nozzle area ratio."""
        return (1.0 / mach) * (2.0 / gp1 * (1.0 + 0.5 * gm1 * mach * mach)) ** (
            0.5 * gp1 / gm1
        ) - area_ratio

    upper = 2.0
    while area_ratio_residual(upper) < 0.0:
        upper *= 2.0
    exit_mach = brentq(area_ratio_residual, 1.0 + 1e-12, upper, xtol=1e-14)

    pe_over_pc = (1.0 + 0.5 * gm1 * exit_mach * exit_mach) ** (-gamma / gm1)
    momentum = math.sqrt(
        2.0
        * gamma**2
        / gm1
        * (2.0 / gp1) ** (gp1 / gm1)
        * (1.0 - pe_over_pc ** (gm1 / gamma))
    )
    divergence = 0.5 * (1.0 + math.cos(half_angle_rad))
    return divergence * momentum + (pe_over_pc - ambient_pressure_ratio) * area_ratio


def bates_burn_area(
    config: BatesGrainConfig, web_burned: float | np.ndarray
) -> np.ndarray:
    """Burning surface area of the grain after a web thickness has burned.

    ``Ab(w) = N [pi (Di + 2w)(L - 2w) + (pi / 2)(Do^2 - (Di + 2w)^2)]``: the core wall
    plus the two ends of each segment.

    Args:
        config: Grain configuration.
        web_burned: Web thickness burned ``w`` [m], scalar or array.

    Returns:
        Burning area [m^2], same shape as ``web_burned``.
    """
    w = np.asarray(web_burned, dtype=float)
    core = config.core_diameter + 2.0 * w
    length = config.segment_length - 2.0 * w
    core_wall = math.pi * core * length
    ends = 0.5 * math.pi * (config.outer_diameter**2 - core**2)
    return np.asarray(config.n_segments * (core_wall + ends))


def neutral_segment_length(outer_diameter: Meters, core_diameter: Meters) -> Meters:
    """Segment length for which the burning area at ignition equals that at burnout.

    ``L = (3 Do + Di) / 2``.
    """
    return 0.5 * (3.0 * outer_diameter + core_diameter)


def solve_bates_burn(
    config: BatesGrainConfig, n_steps: int = DEFAULT_WEB_STEPS
) -> SolidMotorBurnProfile:
    """Compute the pressure, thrust and mass history of a BATES motor.

    The web is stepped from 0 to the full web. At each step the chamber pressure comes
    from the mass balance ``rho Ab a Pc^n = Pc At / c*``:

        ``Pc = (a rho c* Ab / At)^(1 / (1 - n))``.

    The burn rate ``r = a Pc^n`` converts web steps to time, ``dt = dw / r``. The
    thrust is ``F = C_F Pc At``, with ``C_F`` recomputed at each step because
    ``pa / Pc`` changes with ``Pc``. Tail-off after burnout is not modelled.

    Args:
        config: Grain, propellant and nozzle data.
        n_steps: Number of web intervals (>= 2).

    Returns:
        The burn profile, from ignition to burnout.

    Raises:
        ValueError: If ``n_steps`` is less than 2.
    """
    if n_steps < 2:
        raise ValueError("n_steps must be at least 2.")

    n = config.burn_rate_exponent
    web = np.linspace(0.0, config.web, n_steps + 1)
    area = bates_burn_area(config, web)
    chamber = (
        config.burn_rate_coefficient
        * config.propellant_density
        * config.characteristic_velocity
        * area
        / config.throat_area
    ) ** (1.0 / (1.0 - n))
    burn_rate = config.burn_rate_coefficient * chamber**n
    dt = np.diff(web) / (0.5 * (burn_rate[1:] + burn_rate[:-1]))
    time = np.concatenate(([0.0], np.cumsum(dt)))

    thrust_coeff = np.array(
        [
            nozzle_thrust_coefficient(
                config.nozzle_area_ratio,
                config.nozzle_half_angle,
                config.gamma,
                config.ambient_pressure / float(pc),
            )
            for pc in chamber
        ]
    )
    thrust = thrust_coeff * chamber * config.throat_area

    core = config.core_diameter + 2.0 * web
    length = config.segment_length - 2.0 * web
    remaining_volume = (
        config.n_segments
        * 0.25
        * math.pi
        * (config.outer_diameter**2 - core**2)
        * length
    )
    return SolidMotorBurnProfile(
        t=time,
        web_burned=web,
        burn_area=area,
        chamber_pressure=chamber,
        thrust=thrust,
        propellant_mass=config.propellant_density * remaining_volume,
    )
