'''This module provides the standardized Pydantic components used to 
    represent various propulsion systems, including solid rocket motors and ramjets.
'''

from __future__ import annotations

from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

from .mass import MassProperties

class SolidMotor(BaseModel):
    """Solid Rocket Motor (SRM) definition.

    Attributes:
        isp_vacuum_s: Vacuum specific impulse for solid propellants in seconds. (Range: 80 to 320)
        isp_sl_s: Sea-level specific impulse for solid propellants in seconds. (Range: 80 to 320)
        propellant_mass_kg: Total propellant mass in kilograms. (> 0)
        burn_time_s: Total motor burn duration in seconds. (> 0)
        thrust_mean_N: Time-averaged thrust over the burn duration in newtons. (> 0)
        thrust_peak_N: Peak thrust in newtons. Must not be less than mean thrust. (> 0)
        propellant_density_kg_m3: Propellant density in kg/m^3. (> 0)
        casing_length_m: Length of the internal metal casing of the motor in meters. Defaults to None. (> 0)
        casing_diameter_m: Diameter of the internal metal casing of the motor in meters. Defaults to None. (> 0)
        mass: Mass Properties
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["solid_motor"] = Field(default="solid_motor", frozen=True)

    isp_vacuum_s: float = Field(
        ge=80.0, 
        le=320.0,
        description='''Vacuum specific impulse for solid propellants in seconds. (Range: 80 to 320)'''
    )
    
    isp_sl_s: float = Field(
        ge=80.0, 
        le=320.0,
        description='''Sea-level specific impulse for solid propellants in seconds. (Range: 80 to 320)'''
    )
    
    propellant_mass_kg: float = Field(
        gt=0.0,
        description='''Total propellant mass in kilograms. (> 0)'''
    )
    
    burn_time_s: float = Field(
        gt=0.0,
        description='''Total motor burn duration in seconds. (> 0)'''
    )
    
    thrust_mean_N: float = Field(
        gt=0.0,
        description='''Time-averaged thrust over the burn duration in newtons. (> 0)'''
    )
    
    thrust_peak_N: float = Field(
        gt=0.0,
        description='''Peak thrust in newtons. Must not be less than mean thrust. (> 0)'''
    )
    
    propellant_density_kg_m3: float = Field(
        gt=0.0,
        description='''Propellant density in kg/m^3. (> 0)'''
    )
    
    casing_length_m: float | None = Field(
        default=None,
        gt=0.0,
        description='''Length of the internal metal casing of the motor in meters. Defaults to None. (> 0)'''
    )
    
    casing_diameter_m: float | None = Field(
        default=None,
        gt=0.0,
        description='''Diameter of the internal metal casing of the motor in meters. Defaults to None. (> 0)'''
    )
    
    mass: MassProperties | None = Field(
        default=None,
        description='''Mass Properties'''
    )

    @property
    def mdot_kg_per_s(self) -> float:
        """Mean mass flow rate [kg/s]."""
        return self.propellant_mass_kg / self.burn_time_s

    @property
    def total_impulse_Ns(self) -> float:
        """Total impulse from measured mean thrust [N*s]."""
        return self.thrust_mean_N * self.burn_time_s

    @model_validator(mode="after")
    def _thrust_peak_not_below_mean(self) -> SolidMotor:
        """Peak thrust can never be below the time-average of a non-negative thrust curve."""
        if self.thrust_peak_N < self.thrust_mean_N:
            raise ValueError(
                f"thrust_peak_N={self.thrust_peak_N:.0f} < thrust_mean_N={self.thrust_mean_N:.0f} N"
            )
        return self

    @model_validator(mode="after")
    def _mean_thrust_consistent_with_isp(self) -> SolidMotor:
        """Cross-check: mean thrust vs. impulse-consistent Isp*mdot*g0 within a factor of 3."""
        g0 = 9.80665  # m/s^2
        thrust_ideal_N = self.isp_sl_s * self.mdot_kg_per_s * g0
        if not (thrust_ideal_N / 3.0 <= self.thrust_mean_N <= thrust_ideal_N * 3.0):
            raise ValueError(
                f"thrust_mean_N={self.thrust_mean_N:.0f} inconsistent with "
                f"Isp_sl*mdot*g0={thrust_ideal_N:.0f} N (check units)"
            )
        return self


class RamjetEngine(BaseModel):
    """Ramjet engine definition.

    Attributes:
        design_mach: Design-point Mach number. Ramjets do not produce net thrust below ~Mach 1.5. (Range: 1.5 to 6.0)
        fuel_type: Fuel designation (e.g. "kerosene"). Defaults to kerosene.
        combustor_temp_K: Combustor exit total temperature in kelvin. Bounded by material/dissociation limits. (Range: 1200 to 2600)
        nozzle_area_ratio: Nozzle exit/throat area ratio. (>= 1)
        nozzle_throat_diameter_m: Nozzle throat diameter in meters, if known from a dimensioned drawing. Defaults to None. (> 0)
        nozzle_exit_diameter_m: Nozzle exit diameter in meters, if known from a dimensioned drawing. Defaults to None. (> 0)
        mass: Mass Properties
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["ramjet_engine"] = Field(default="ramjet_engine", frozen=True)
    
    design_mach: float = Field(
        ge=1.5, 
        le=6.0,
        description='''Design-point Mach number. Ramjets do not produce net thrust below ~Mach 1.5. (Range: 1.5 to 6.0)'''
    )
    
    fuel_type: str = Field(
        default="kerosene",
        description='''Fuel designation (e.g. "kerosene"). Defaults to kerosene.'''
    )
    
    combustor_temp_K: float = Field(
        ge=1200.0, 
        le=2600.0,
        description='''Combustor exit total temperature in kelvin. Bounded by material/dissociation limits. (Range: 1200 to 2600)'''
    )
    
    nozzle_area_ratio: float = Field(
        ge=1.0,
        description='''Nozzle exit/throat area ratio. (>= 1)'''
    )
    
    nozzle_throat_diameter_m: float | None = Field(
        default=None, 
        gt=0.0,
        description='''Nozzle throat diameter in meters, if known from a dimensioned drawing. Defaults to None. (> 0)'''
    )
    
    nozzle_exit_diameter_m: float | None = Field(
        default=None, 
        gt=0.0,
        description='''Nozzle exit diameter in meters, if known from a dimensioned drawing. Defaults to None. (> 0)'''
    )
    
    mass: MassProperties | None = Field(
        default=None,
        description='''Mass Properties'''
    )

    @model_validator(mode="after")
    def _nozzle_area_ratio_consistency(self) -> RamjetEngine:
        """If both diameters are given, cross-check against nozzle_area_ratio."""
        if self.nozzle_throat_diameter_m is not None and self.nozzle_exit_diameter_m is not None:
            implied_ratio = (self.nozzle_exit_diameter_m / self.nozzle_throat_diameter_m) ** 2
            if abs(implied_ratio - self.nozzle_area_ratio) / implied_ratio > 0.02:
                raise ValueError(
                    f"nozzle_area_ratio={self.nozzle_area_ratio} inconsistent with "
                    f"diameters (implies {implied_ratio:.4f}); update one to match"
                )
        return self

class TurbojetEngine(BaseModel):
    """Turbojet engine definition.

    Attributes:
        name: Engine designation.
        thrust_N: Static sea-level thrust in newtons. (> 0)
        sfc_kg_per_Ns: Thrust-specific fuel consumption in kg/(N*s). (> 0)
        mach_range: Operational (min, max) Mach numbers, increasing.
        mass_flow_kg_per_s: Optional air/mass flow rate in kg/s. Defaults to None. (> 0)
        compression_ratio: Optional compressor pressure ratio. Defaults to None. (> 1.0)
        egt_K: Optional exhaust gas temperature in kelvin. Defaults to None. (> 0)
        diameter_m: Optional engine diameter in meters. Defaults to None. (> 0)
        length_m: Optional engine length in meters. Defaults to None. (> 0)
        max_rpm: Optional maximum RPM. Defaults to None. (> 0)
        mass: Mass Properties
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["turbojet_engine"] = Field(default="turbojet_engine", frozen=True)
    
    name: str = Field(
        description='''Engine designation.'''
    )
    
    thrust_N: float = Field(
        gt=0.0,
        description='''Static sea-level thrust in newtons. (> 0)'''
    )
    
    sfc_kg_per_Ns: float = Field(
        gt=0.0,
        description='''Thrust-specific fuel consumption in kg/(N*s). (> 0)'''
    )
    
    mach_range: tuple[float, float] = Field(
        description='''Operational (min, max) Mach numbers, increasing.'''
    )
    
    mass_flow_kg_per_s: float | None = Field(
        default=None, 
        gt=0.0,
        description='''Optional air/mass flow rate in kg/s. Defaults to None. (> 0)'''
    )
    
    compression_ratio: float | None = Field(
        default=None, 
        gt=1.0,
        description='''Optional compressor pressure ratio. Defaults to None. (> 1.0)'''
    )
    
    egt_K: float | None = Field(
        default=None, 
        gt=0.0,
        description='''Optional exhaust gas temperature in kelvin. Defaults to None. (> 0)'''
    )
    
    diameter_m: float | None = Field(
        default=None, 
        gt=0.0,
        description='''Optional engine diameter in meters. Defaults to None. (> 0)'''
    )
    
    length_m: float | None = Field(
        default=None, 
        gt=0.0,
        description='''Optional engine length in meters. Defaults to None. (> 0)'''
    )
    
    max_rpm: float | None = Field(
        default=None, 
        gt=0.0,
        description='''Optional maximum RPM. Defaults to None. (> 0)'''
    )
    
    mass: MassProperties | None = Field(
        default=None,
        description='''Mass Properties'''
    )

    @field_validator("mach_range")
    @classmethod
    def _mach_range_valid(cls, v: tuple[float, float]) -> tuple[float, float]:
        """Require 0 <= mach_min < mach_max."""
        lo, hi = v
        if lo < 0.0:
            raise ValueError("mach_range minimum must be >= 0")
        if hi <= lo:
            raise ValueError("mach_range must be increasing (min < max)")
        return v

AnyPropulsionComponent = Annotated[
    SolidMotor | RamjetEngine | TurbojetEngine, 
    Field(discriminator="type")
]
