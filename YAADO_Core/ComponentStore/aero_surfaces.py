'''This module provides the standardized Pydantic components used to 
    represent aerodynamic lifting surfaces (wings, fins) and control surfaces.
'''

from __future__ import annotations

from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .mass import MassProperties

class ControlSurface(BaseModel):
    """A control surface attached to the trailing edge of a lifting surface (e.g. aileron, flap, rudder).

    Attributes:
        name: Name of the control surface for identification.
        span_fraction_start: The inboard starting position as a fraction of the span. (Range: 0.0 to 1.0)
        span_fraction_end: The outboard ending position as a fraction of the span. (Range: 0.0 to 1.0)
        chord_fraction: The fraction of the chord taken up by the control surface. (Range: 0.0 to 1.0)
        max_deflection_deg: Maximum physical deflection angle in degrees. (> 0)
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description='''Name of the control surface for identification.'''
    )
    function: Literal["aileron", "flap", "elevator", "rudder", "custom"]
    span_fraction_start: float = Field(
        ge=0.0,
        le=1.0,
        description='''The inboard starting position as a fraction of the span. (Range: 0.0 to 1.0)'''
    )
    span_fraction_end: float = Field(
        ge=0.0,
        le=1.0,
        description='''The outboard ending position as a fraction of the span. (Range: 0.0 to 1.0)'''
    )
    chord_fraction: float = Field(
        ge=0.0,
        le=1.0,
        description='''The fraction of the chord taken up by the control surface. (Range: 0.0 to 1.0)'''
    )
    max_deflection_deg: float = Field(
        gt=0.0,
        description='''Maximum physical deflection angle in degrees. (> 0)'''
    )

class Wings(BaseModel):
    """Fixed-wing planform definition.

    Attributes:
        aspect_ratio: Wing aspect ratio b^2/S. (> 0)
        sweep_deg: Quarter-chord sweep in degrees. (Range: -10 to 70)
        taper_ratio: Tip/root chord ratio. (Range: 0 to 1)
        span_m: Wing span in meters. (> 0)
        dihedral_deg: Dihedral angle in degrees. (Range: -20 to 20)
        airfoil_root: Root airfoil designation (e.g. "NACA2412").
        airfoil_tip: Tip airfoil designation. Defaults to root airfoil if omitted.
        control_surfaces: List of control surfaces attached to the wing.
        mass: Mass Properties
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["wing"] = Field(default="wing", frozen=True)

    aspect_ratio: float = Field(
        gt=0.0, 
        le=50.0,
        description='''Wing aspect ratio b^2/S. (> 0)'''
    )
    
    sweep_deg: float = Field(
        ge=-10.0, 
        le=70.0,
        description='''Quarter-chord sweep in degrees. (Range: -10 to 70)'''
    )
    
    taper_ratio: float = Field(
        gt=0.0, 
        le=1.0,
        description='''Tip/root chord ratio. (Range: 0 to 1)'''
    )
    
    span_m: float = Field(
        gt=0.0,
        description='''Wing span in meters. (> 0)'''
    )
    
    dihedral_deg: float = Field(
        default=0.0,
        ge=-20.0, 
        le=20.0,
        description='''Dihedral angle in degrees. (Range: -20 to 20)'''
    )
    
    airfoil_root: str = Field(
        description='''Root airfoil designation (e.g. "NACA2412").'''
    )
    
    airfoil_tip: str | None = Field(
        default=None,
        description='''Tip airfoil designation. Defaults to root airfoil if omitted.'''
    )
    
    control_surfaces: list[ControlSurface] = Field(
        default_factory=list,
        description='''List of control surfaces attached to the wing.'''
    )

    mass: MassProperties | None = Field(
        default=None,
        description='''Mass Properties'''
    )

    @model_validator(mode="after")
    def _default_tip_airfoil(self) -> Wings:
        """If no tip airfoil is provided, default to the root airfoil."""
        if self.airfoil_tip is None:
            self.airfoil_tip = self.airfoil_root
        return self

class Fins(BaseModel):
    """Rocket fin set definition.

    Attributes:
        count: Number of fins in the radial set. (Range: 3 to 8)
        span_m: Exposed semi-span of one individual fin in meters. (> 0)
        sweep_deg: Leading-edge sweep angle in degrees. (Range: 0.0 to 75.0)
        chord_root_m: Root chord length in meters. Defaults to None. (> 0)
        chord_tip_m: Tip chord length in meters. Defaults to None. (>= 0)
        control_surfaces: List of control surfaces attached to the trailing edge of these fins.
        mass: Mass Properties
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["fins"] = Field(default="fins", frozen=True)

    count: int = Field(
        ge=3, 
        le=8,
        description='''Number of fins in the radial set. (Range: 3 to 8)'''
    )
    
    span_m: float = Field(
        gt=0.0,
        description='''Exposed semi-span of one individual fin in meters. (> 0)'''
    )
    
    sweep_deg: float = Field(
        ge=0.0, 
        le=75.0,
        description='''Leading-edge sweep angle in degrees. (Range: 0.0 to 75.0)'''
    )
    
    chord_root_m: float | None = Field(
        default=None, 
        gt=0.0,
        description='''Root chord length in meters. Defaults to None. (> 0)'''
    )
    
    chord_tip_m: float | None = Field(
        default=None, 
        ge=0.0,
        description='''Tip chord length in meters. Defaults to None. (>= 0)'''
    )

    control_surfaces: list[ControlSurface] = Field(
        default_factory=list,
        description='''List of control surfaces attached to the trailing edge of these fins.'''
    )
    
    mass: MassProperties | None = Field(
        default=None,
        description='''Mass Properties'''
    )


AnyAeroComponent = Annotated[
    Fins | Wings, 
    Field(discriminator="type")
]
