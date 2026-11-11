"""Typed input and result containers for powerplant analyses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from YAADO_Core.Foundation.analysis_base import BaseAnalysisResults
from YAADO_Core.Foundation.units import (
    Degrees,
    Dimensionless,
    JoulesPerKilogram,
    Kelvin,
    KilogramsPerSecond,
    Meters,
    MetersPerSecond,
    Newtons,
    Pascals,
    Seconds,
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
        specific_impulse: Net thrust per unit fuel weight flow, for the real model.
        capture_area: Freestream tube area that supplies ``mdot_air``.
        assumed_losses: Loss fields that the analysis took from placeholder defaults.
    """

    HEADLINE_METRICS: ClassVar[tuple[str, ...]] = (
        "thrust_real",
        "specific_impulse",
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
    specific_impulse: Seconds
    momentum_thrust: Newtons
    pressure_thrust: Newtons
    assumed_losses: tuple[str, ...] = ()


@dataclass(frozen=True)
class MachSweepPoint:
    """Off-design cycle performance at one Mach number and a fixed nozzle throat."""

    mach: Dimensionless
    thrust_real: Newtons
    specific_impulse: Seconds
    mdot_air: KilogramsPerSecond
    fuel_air_ratio: Dimensionless
    capture_area: SquareMeters
    p_exit_over_p0: Dimensionless


@dataclass(frozen=True)
class ConicalShock:
    """Attached conical shock on a cone in supersonic flow (Taylor-Maccoll).

    Attributes:
        shock_angle: Shock angle from the cone axis.
        mach_behind_shock: Mach number just behind the shock.
        mach_cone_surface: Mach number on the cone surface, after the isentropic
            compression between shock and cone.
        pt_ratio: Total-pressure ratio across the shock.
    """

    shock_angle: Degrees
    mach_behind_shock: Dimensionless
    mach_cone_surface: Dimensionless
    pt_ratio: Dimensionless


@dataclass(frozen=True)
class ConicalInletResults(BaseAnalysisResults):
    """Total-pressure recovery of a single-cone external-compression inlet.

    The chain is conical shock, terminal normal shock at the Mach number behind
    the conical shock, and a subsonic-diffuser loss. A detached shock is bounded
    by a normal shock at the flight Mach number.

    Attributes:
        mach: Flight Mach number.
        cone_half_angle: Spike half-angle.
        max_attached_half_angle: Largest half-angle with an attached shock at ``mach``.
        shock: Conical shock, or None if it is detached.
        pt_normal_shock: Total-pressure ratio of the terminal (or bow) normal shock.
        pt_diffuser: Total-pressure ratio of the subsonic diffuser.
        recovery: Overall total-pressure recovery pt2/pt0.
        mil_e_5007d_recovery: MIL-E-5007D reference recovery at ``mach``.
        recovery_margin: ``recovery - mil_e_5007d_recovery``.
        assumptions: Modeling assumptions and flags for this run.
    """

    HEADLINE_METRICS: ClassVar[tuple[str, ...]] = (
        "recovery",
        "mil_e_5007d_recovery",
        "max_attached_half_angle",
    )

    mach: Dimensionless
    cone_half_angle: Degrees
    max_attached_half_angle: Degrees
    shock: ConicalShock | None
    pt_normal_shock: Dimensionless
    pt_diffuser: Dimensionless
    recovery: Dimensionless
    mil_e_5007d_recovery: Dimensionless
    recovery_margin: Dimensionless
    assumptions: tuple[str, ...] = ()

    @property
    def shock_angle(self) -> Degrees | None:
        """Conical shock angle, or None if the shock is detached."""
        return None if self.shock is None else self.shock.shock_angle

    @property
    def mach_behind_shock(self) -> Dimensionless | None:
        """Mach number behind the conical shock, or None if it is detached."""
        return None if self.shock is None else self.shock.mach_behind_shock


@dataclass(frozen=True)
class InletMachPoint:
    """Recovery of a fixed spike at one flight Mach number."""

    mach: Dimensionless
    recovery: Dimensionless
    mil_e_5007d_recovery: Dimensionless
    attached: bool


@dataclass(frozen=True)
class ShockChain:
    """External compression by oblique shocks, a terminal normal shock and a diffuser.

    Attributes:
        deflections: Flow deflection of each oblique shock (ramp angle increment).
        shock_angles: Angle of each oblique shock to its upstream flow.
        mach_stages: Mach number upstream of each shock, then before the normal shock.
        pt_oblique: Total-pressure ratio of each oblique shock.
        pt_normal: Total-pressure ratio of the terminal normal shock.
        pt_diffuser: Total-pressure ratio of the subsonic diffuser.
        recovery: Overall total-pressure recovery pt2/pt0.
        detached: True if a stage had no attached oblique shock; the remaining
            compression is then a normal shock at that stage's Mach number.
    """

    deflections: tuple[Degrees, ...]
    shock_angles: tuple[Degrees, ...]
    mach_stages: tuple[Dimensionless, ...]
    pt_oblique: tuple[Dimensionless, ...]
    pt_normal: Dimensionless
    pt_diffuser: Dimensionless
    recovery: Dimensionless
    detached: bool

    @property
    def mach_before_normal(self) -> Dimensionless:
        """Mach number ahead of the terminal normal shock."""
        return self.mach_stages[-1]

    @property
    def total_turning(self) -> Degrees:
        """Sum of the oblique-shock deflections."""
        return sum(self.deflections)


@dataclass(frozen=True)
class MultiShockInletResults(BaseAnalysisResults):
    """Recovery of a multi-ramp external-compression inlet.

    Attributes:
        mach: Flight Mach number.
        chain: The shock chain.
        optimized: True if the deflections are the equal-normal-Mach optimum.
        recovery: Overall total-pressure recovery pt2/pt0.
        mil_e_5007d_recovery: MIL-E-5007D reference recovery at ``mach``.
        recovery_margin: ``recovery - mil_e_5007d_recovery``.
        total_turning: Sum of the ramp deflections.
        mach_before_normal: Mach number ahead of the terminal normal shock.
        assumptions: Modeling assumptions and flags for this run.
    """

    HEADLINE_METRICS: ClassVar[tuple[str, ...]] = (
        "recovery",
        "mil_e_5007d_recovery",
        "total_turning",
    )

    mach: Dimensionless
    chain: ShockChain
    optimized: bool
    recovery: Dimensionless
    mil_e_5007d_recovery: Dimensionless
    recovery_margin: Dimensionless
    total_turning: Degrees
    mach_before_normal: Dimensionless
    assumptions: tuple[str, ...] = ()
