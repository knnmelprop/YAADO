'''This module provides the standardized Pydantic components used to 
    represent various propulsion systems, including solid rocket motors and ramjets.
'''

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .mass import MassProperties


class SolidMotor(BaseModel):
    """Solid Rocket Motor (SRM) definition.

    Note:
        Example values are taken from the AGM-84 Harpoon.

    Attributes:
        isp_vacuum: Vacuum specific impulse for solid propellants in seconds. (Range: 80 to 320)
        isp_sl: Sea-level specific impulse for solid propellants in seconds. (Range: 80 to 320)
        propellant_mass: Total propellant mass in kilograms. (> 0)
        burn_time: Total motor burn duration in seconds. (> 0)
        thrust_mean: Time-averaged thrust over the burn duration in newtons. (> 0)
        thrust_peak: Peak thrust in newtons. Must not be less than mean thrust. (> 0)
        propellant_density: Propellant density in kg/m^3. (> 0)
        casing_length: Length of the internal metal casing of the motor in meters. Defaults to None. (> 0)
        casing_diameter: Diameter of the internal metal casing of the motor in meters. Defaults to None. (> 0)
        mass: Mass Properties
    """

    model_config = ConfigDict(extra="forbid")

    UNITS: ClassVar[dict[str, str]] = {
        "isp_vacuum": "s",
        "isp_sl": "s",
        "propellant_mass": "kg",
        "burn_time": "s",
        "thrust_mean": "N",
        "thrust_peak": "N",
        "propellant_density": "kg/m^3",
        "casing_length": "m",
        "casing_diameter": "m",
    }

    type: Literal["solid_motor"] = Field(default="solid_motor", frozen=True)

    isp_vacuum: float = Field(
        ge=80.0, 
        le=320.0,
        examples=[255.0],
        description='''Vacuum specific impulse for solid propellants in seconds. (Range: 80 to 320)'''
    )
    
    isp_sl: float = Field(
        ge=80.0, 
        le=320.0,
        examples=[230.0],
        description='''Sea-level specific impulse for solid propellants in seconds. (Range: 80 to 320)'''
    )
    
    propellant_mass: float = Field(
        gt=0.0,
        examples=[70.0],
        description='''Total propellant mass in kilograms. (> 0)'''
    )
    
    burn_time: float = Field(
        gt=0.0,
        examples=[2.90],
        description='''Total motor burn duration in seconds. (> 0)'''
    )
    
    thrust_mean: float = Field(
        gt=0.0,
        examples=[53000.0],
        description='''Time-averaged thrust over the burn duration in newtons. (> 0)'''
    )
    
    thrust_peak: float = Field(
        gt=0.0,
        examples=[58000.0],
        description='''Peak thrust in newtons. Must not be less than mean thrust. (> 0)'''
    )
    
    propellant_density: float = Field(
        gt=0.0,
        examples=[1750.0],
        description='''Propellant density in kg/m^3. (> 0)'''
    )
    
    casing_length: float | None = Field(
        default=None,
        gt=0.0,
        examples=[0.70],
        description='''Length of the internal metal casing of the motor in meters. Defaults to None. (> 0)'''
    )
    
    casing_diameter: float | None = Field(
        default=None,
        gt=0.0,
        examples=[0.343],
        description='''Diameter of the internal metal casing of the motor in meters. Defaults to None. (> 0)'''
    )
    
    mass: MassProperties | None = Field(
        default=None,
        examples=[
            {
                "type": "mass",
                "cg_from_nose": 4.25,
                "cg_source": "Aerojet booster structural balance sheet",
                "total_mass": 140.0,
            }
        ],
        description='''Mass Properties'''
    )

    @property
    def mdot(self) -> float:
        """Mean mass flow rate [kg/s]."""
        return self.propellant_mass / self.burn_time

    @property
    def total_impulse(self) -> float:
        """Total impulse from measured mean thrust [N*s]."""
        return self.thrust_mean * self.burn_time

    @model_validator(mode="after")
    def _thrust_peak_not_below_mean(self) -> SolidMotor:
        """Peak thrust can never be below the time-average of a non-negative thrust curve."""
        if self.thrust_peak < self.thrust_mean:
            raise ValueError(
                f"thrust_peak={self.thrust_peak:.0f} < thrust_mean={self.thrust_mean:.0f} N"
            )
        return self

    @model_validator(mode="after")
    def _mean_thrust_consistent_with_isp(self) -> SolidMotor:
        """Cross-check: mean thrust vs. impulse-consistent Isp*mdot*g0 within a factor of 3."""
        g0 = 9.80665  # m/s^2
        thrust_ideal_N = self.isp_sl * self.mdot * g0
        if not (thrust_ideal_N / 3.0 <= self.thrust_mean <= thrust_ideal_N * 3.0):
            raise ValueError(
                f"thrust_mean={self.thrust_mean:.0f} inconsistent with "
                f"Isp_sl*mdot*g0={thrust_ideal_N:.0f} N (check units)"
            )
        return self


class RamjetEngine(BaseModel):
    """Ramjet engine definition.

    Note:
        Example values are taken from the ALVRJ (Advanced Low-Volume Ramjet).

    Attributes:
        design_mach: Design-point Mach number. Ramjets do not produce net thrust below ~Mach 1.5. (Range: 1.5 to 6.0)
        fuel_type: Fuel designation (e.g. "kerosene"). Defaults to kerosene.
        combustor_temp: Combustor exit total temperature in kelvin. Bounded by material/dissociation limits. (Range: 1200 to 2600)
        nozzle_area_ratio: Nozzle exit/throat area ratio. (>= 1)
        nozzle_throat_diameter: Nozzle throat diameter in meters, if known from a dimensioned drawing. Defaults to None. (> 0)
        nozzle_exit_diameter: Nozzle exit diameter in meters, if known from a dimensioned drawing. Defaults to None. (> 0)
        mass: Mass Properties
    """

    model_config = ConfigDict(extra="forbid")

    UNITS: ClassVar[dict[str, str]] = {
        "design_mach": "-",
        "combustor_temp": "K",
        "nozzle_area_ratio": "-",
        "nozzle_throat_diameter": "m",
        "nozzle_exit_diameter": "m",
    }

    type: Literal["ramjet_engine"] = Field(default="ramjet_engine", frozen=True)
    
    design_mach: float = Field(
        ge=1.5, 
        le=6.0,
        examples=[2.60],
        description='''Design-point Mach number. Ramjets do not produce net thrust below ~Mach 1.5. (Range: 1.5 to 6.0)'''
    )
    
    fuel_type: str = Field(
        default="kerosene",
        examples=["kerosene"],
        description='''Fuel designation (e.g. "kerosene"). Defaults to kerosene.'''
    )
    
    combustor_temp: float = Field(
        ge=1200.0, 
        le=2600.0,
        examples=[2150.0],
        description='''Combustor exit total temperature in kelvin. Bounded by material/dissociation limits. (Range: 1200 to 2600)'''
    )
    
    nozzle_area_ratio: float = Field(
        ge=1.0,
        examples=[2.25],
        description='''Nozzle exit/throat area ratio. (>= 1)'''
    )
    
    nozzle_throat_diameter: float | None = Field(
        default=None, 
        gt=0.0,
        examples=[0.250],
        description='''Nozzle throat diameter in meters, if known from a dimensioned drawing. Defaults to None. (> 0)'''
    )
    
    nozzle_exit_diameter: float | None = Field(
        default=None, 
        gt=0.0,
        examples=[0.375],
        description='''Nozzle exit diameter in meters, if known from a dimensioned drawing. Defaults to None. (> 0)'''
    )
    
    mass: MassProperties | None = Field(
        default=None,
        examples=[
            {
                "type": "mass",
                "cg_from_nose": 3.40,
                "cg_source": "Ramjet combustor liner and injector assembly",
                "total_mass": 115.0,
            }
        ],
        description='''Mass Properties'''
    )

    @model_validator(mode="after")
    def _nozzle_area_ratio_consistency(self) -> RamjetEngine:
        """If both diameters are given, cross-check against nozzle_area_ratio."""
        if self.nozzle_throat_diameter is not None and self.nozzle_exit_diameter is not None:
            implied_ratio = (self.nozzle_exit_diameter / self.nozzle_throat_diameter) ** 2
            if abs(implied_ratio - self.nozzle_area_ratio) / implied_ratio > 0.02:
                raise ValueError(
                    f"nozzle_area_ratio={self.nozzle_area_ratio} inconsistent with "
                    f"diameters (implies {implied_ratio:.4f}); update one to match"
                )
        return self

class TurbojetEngine(BaseModel):
    """Turbojet engine definition.

    Note:
        Example values are taken from the AGM-84 Harpoon.

    Attributes:
        name: Engine designation.
        thrust: Static sea-level thrust in newtons. (> 0)
        sfc: Thrust-specific fuel consumption in kg/(N*s). (> 0)
        mach_range: Operational (min, max) Mach numbers, increasing.
        mass_flow: Optional air/mass flow rate in kg/s. Defaults to None. (> 0)
        compression_ratio: Optional compressor pressure ratio. Defaults to None. (> 1.0)
        egt: Optional exhaust gas temperature in kelvin. Defaults to None. (> 0)
        diameter: Optional engine diameter in meters. Defaults to None. (> 0)
        length: Optional engine length in meters. Defaults to None. (> 0)
        max_rpm: Optional maximum RPM. Defaults to None. (> 0)
        mass: Mass Properties
    """

    model_config = ConfigDict(extra="forbid")

    UNITS: ClassVar[dict[str, str]] = {
        "thrust": "N",
        "sfc": "kg/(N*s)",
        "mass_flow": "kg/s",
        "compression_ratio": "-",
        "egt": "K",
        "diameter": "m",
        "length": "m",
        "max_rpm": "rpm",
    }

    type: Literal["turbojet_engine"] = Field(default="turbojet_engine", frozen=True)
    
    name: str = Field(
        examples=['Teledyne CAE J402-CA-400'],
        description='''Engine designation.'''
    )
    
    thrust: float = Field(
        gt=0.0,
        examples=[2940.0],
        description='''Static sea-level thrust in newtons. (> 0)'''
    )
    
    sfc: float = Field(
        gt=0.0,
        examples=[3.25e-5],
        description='''Thrust-specific fuel consumption in kg/(N*s). (> 0)'''
    )
    
    mach_range: tuple[float, float] = Field(
        examples=[(0.20, 0.85)],
        description='''Operational (min, max) Mach numbers, increasing.'''
    )
    
    mass_flow: float | None = Field(
        default=None, 
        gt=0.0,
        examples=[4.35],
        description='''Optional air/mass flow rate in kg/s. Defaults to None. (> 0)'''
    )
    
    compression_ratio: float | None = Field(
        default=None, 
        gt=1.0,
        examples=[5.60],
        description='''Optional compressor pressure ratio. Defaults to None. (> 1.0)'''
    )
    
    egt: float | None = Field(
        default=None, 
        gt=0.0,
        examples=[950.0],
        description='''Optional exhaust gas temperature in kelvin. Defaults to None. (> 0)'''
    )
    
    diameter: float | None = Field(
        default=None, 
        gt=0.0,
        examples=[0.318],
        description='''Optional engine diameter in meters. Defaults to None. (> 0)'''
    )
    
    length: float | None = Field(
        default=None, 
        gt=0.0,
        examples=[0.747],
        description='''Optional engine length in meters. Defaults to None. (> 0)'''
    )
    
    max_rpm: float | None = Field(
        default=None, 
        gt=0.0,
        examples=[41200.0],
        description='''Optional maximum RPM. Defaults to None. (> 0)'''
    )
    
    mass: MassProperties | None = Field(
        default=None,
        examples=[
            {
                "type": "mass",
                "cg_from_nose": 3.10,
                "cg_source": "Teledyne CAE technical datasheet",
                "total_mass": 46.0,
            }
        ],
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
