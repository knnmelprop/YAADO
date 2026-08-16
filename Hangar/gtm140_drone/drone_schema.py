from __future__ import annotations

from typing import Literal, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator
from IADE_Core.Inspectors.vehicle_schema import BaseVehicleConfig

class WingConfig(BaseModel):
    """Fixed-wing planform definition.

    Attributes:
        aspect_ratio: Wing aspect ratio b^2/S (dimensionless, > 0).
        sweep_deg: Quarter-chord sweep in degrees (-10..70).
        taper_ratio: Tip/root chord ratio (0 < taper <= 1).
        span_m: Wing span in meters (> 0).
        airfoil_root: Root airfoil designation (e.g. ``"NACA2412"``).
        airfoil_tip: Tip airfoil designation.
    """

    model_config = ConfigDict(extra="forbid")

    aspect_ratio: float = Field(..., gt=0.0, le=50.0)
    sweep_deg: float = Field(..., ge=-10.0, le=70.0)
    taper_ratio: float = Field(..., gt=0.0, le=1.0)
    span_m: float = Field(..., gt=0.0)
    airfoil_root: str
    airfoil_tip: str



class TurbojetConfig(BaseModel):
    """Small turbojet engine definition (e.g. Jetpol GTM-140).

    Attributes:
        type: Discriminator, always ``"turbojet"``.
        name: Engine designation.
        thrust_N: Static sea-level thrust in newtons (> 0).
        sfc_kg_per_Ns: Thrust-specific fuel consumption in kg/(N*s) (> 0).
        mass_kg: Dry engine mass in kilograms (> 0).
        mach_range: Operational (min, max) Mach numbers, increasing,
            subsonic (max <= 1.0 for a small turbojet).
        mass_flow_kg_per_s: Optional air/mass flow rate in kg/s (> 0).
        compression_ratio: Optional compressor pressure ratio (> 1.0).
        egt_K: Optional exhaust gas temperature in kelvin (> 0).
        diameter_m: Optional engine diameter in meters (> 0).
        length_m: Optional engine length in meters (> 0).
        max_rpm: Optional maximum RPM (> 0).
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["turbojet"] = "turbojet"
    name: str
    thrust_N: float = Field(..., gt=0.0)
    sfc_kg_per_Ns: float = Field(..., gt=0.0)
    mass_kg: float = Field(..., gt=0.0)
    mach_range: tuple[float, float]
    mass_flow_kg_per_s: Union[float, None] = Field(default=None, gt=0.0)
    compression_ratio: Union[float, None] = Field(default=None, gt=1.0)
    egt_K: Union[float, None] = Field(default=None, gt=0.0)
    diameter_m: Union[float, None] = Field(default=None, gt=0.0)
    length_m: Union[float, None] = Field(default=None, gt=0.0)
    max_rpm: Union[float, None] = Field(default=None, gt=0.0)

    @field_validator("mach_range")
    @classmethod
    def _mach_range_valid(cls, v: tuple[float, float]) -> tuple[float, float]:
        """Require 0 <= mach_min < mach_max <= 1.0."""
        lo, hi = v
        if lo < 0.0:
            raise ValueError("mach_range minimum must be >= 0")
        if hi <= lo:
            raise ValueError("mach_range must be increasing (min < max)")
        if hi > 1.0:
            raise ValueError("small turbojet mach_range maximum must be <= 1.0")
        return v



class UAVConfig(BaseVehicleConfig):
    """Project A — fixed-wing UAV with a small turbojet.

    Attributes:
        wing: Wing planform definition.
        propulsion: Turbojet engine definition (Jetpol GTM-140).
    """

    vehicle_type: Literal["UAV"] = "UAV"
    wing: WingConfig
    propulsion: TurbojetConfig



