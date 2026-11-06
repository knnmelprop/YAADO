"""Typed input and result containers for powerplant analyses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from YAADO_Core.Foundation.analysis_base import BaseAnalysisResults
from YAADO_Core.Foundation.units import (
    Dimensionless,
    JoulesPerKilogram,
    Kelvin,
    KilogramsPerSecond,
    Meters,
    MetersPerSecond,
    Newtons,
    Pascals,
    SquareMeters,
)


@dataclass(frozen=True)
class HeiserPrattInputs:
    """Inputs to the Heiser & Pratt two-gas ramjet station cycle.

    The air mass flow is either given directly (``mdot_air``) or set by a choked
    nozzle throat of known area (``throat_area``). Exactly one must be provided.

    Attributes:
        mach: Flight Mach number (> 1).
        altitude: ISA flight altitude.
        tt4: Combustor-exit total temperature.
        nozzle_area_ratio: Nozzle exit-to-throat area ratio (>= 1).
        eta_inlet: Inlet total-pressure recovery pt2/pt0.
        pi_cc: Combustor total-pressure ratio pt4/pt2.
        pi_nozzle: Nozzle total-pressure ratio.
        eta_b: Combustion efficiency.
        gamma_hot: Ratio of specific heats of the combustion products.
        gamma_cold: Ratio of specific heats of the inlet air.
        fuel_lhv: Fuel lower heating value.
        mdot_air: Captured air mass flow.
        throat_area: Nozzle throat area.
    """

    mach: Dimensionless
    altitude: Meters
    tt4: Kelvin
    nozzle_area_ratio: Dimensionless
    eta_inlet: Dimensionless
    pi_cc: Dimensionless
    pi_nozzle: Dimensionless
    eta_b: Dimensionless
    gamma_hot: Dimensionless
    gamma_cold: Dimensionless
    fuel_lhv: JoulesPerKilogram
    mdot_air: KilogramsPerSecond | None = None
    throat_area: SquareMeters | None = None

    def __post_init__(self) -> None:
        """Reject inputs outside the physical range of the cycle model."""
        if self.mach <= 1.0:
            raise ValueError(f"mach must be > 1, got {self.mach}")
        if self.nozzle_area_ratio < 1.0:
            raise ValueError(f"nozzle_area_ratio must be >= 1, got {self.nozzle_area_ratio}")
        for label, value in (
            ("eta_inlet", self.eta_inlet),
            ("pi_cc", self.pi_cc),
            ("pi_nozzle", self.pi_nozzle),
            ("eta_b", self.eta_b),
        ):
            if not 0.0 < value <= 1.0:
                raise ValueError(f"{label} must be in (0, 1], got {value}")
        if self.gamma_hot <= 1.0 or self.gamma_cold <= 1.0:
            raise ValueError(
                f"gamma_hot and gamma_cold must be > 1, got {self.gamma_hot} and {self.gamma_cold}"
            )
        if (self.mdot_air is None) == (self.throat_area is None):
            raise ValueError(
                "Provide exactly one of mdot_air or throat_area, got "
                f"mdot_air={self.mdot_air}, throat_area={self.throat_area}"
            )
        for label, flow_value in (("mdot_air", self.mdot_air), ("throat_area", self.throat_area)):
            if flow_value is not None and flow_value <= 0.0:
                raise ValueError(f"{label} must be > 0, got {flow_value}")


@dataclass(frozen=True)
class NozzleExpansion:
    """Nozzle exit state and thrust terms for one total-pressure loss model."""

    mach_exit: Dimensionless
    t_exit: Kelvin
    p_exit: Pascals
    v_exit: MetersPerSecond
    a_throat: SquareMeters
    a_exit: SquareMeters
    momentum_thrust: Newtons
    pressure_thrust: Newtons

    @property
    def thrust(self) -> Newtons:
        """Net thrust, the sum of the momentum and pressure terms."""
        return self.momentum_thrust + self.pressure_thrust


@dataclass(frozen=True)
class HeiserPrattResults(BaseAnalysisResults):
    """Outputs of the Heiser & Pratt ramjet cycle.

    Station numbers: 0 freestream, 2 diffuser exit, 4 combustor exit. The exit
    state and thrust terms belong to the real model (``thrust_real``).

    Attributes:
        thrust_ideal: Thrust without combustor or nozzle total-pressure loss.
        thrust_cc_loss: Thrust with the combustor loss only.
        thrust_real: Thrust with both losses. Nominal value for downstream use.
        capture_area: Freestream tube area that supplies ``mdot_air``.
    """

    HEADLINE_METRICS: ClassVar[tuple[str, ...]] = (
        "thrust_real",
        "mdot_air",
        "fuel_air_ratio",
        "mach_exit",
        "v_exit",
        "p_exit_over_p0",
    )

    inputs: HeiserPrattInputs
    t0: Kelvin
    p0: Pascals
    v0: MetersPerSecond
    tt0: Kelvin
    pt0: Pascals
    pt2: Pascals
    pt4: Pascals
    fuel_air_ratio: Dimensionless
    mdot_air: KilogramsPerSecond
    mdot_exit: KilogramsPerSecond
    capture_area: SquareMeters
    mach_exit: Dimensionless
    t_exit: Kelvin
    p_exit: Pascals
    v_exit: MetersPerSecond
    a_throat: SquareMeters
    a_exit: SquareMeters
    p_exit_over_p0: Dimensionless
    underexpanded: bool
    thrust_ideal: Newtons
    thrust_cc_loss: Newtons
    thrust_real: Newtons
    momentum_thrust: Newtons
    pressure_thrust: Newtons
