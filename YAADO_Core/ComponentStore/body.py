'''This module provides the standardized Pydantic components used to 
    represent axisymmetric bodies and fuselages.
'''

from __future__ import annotations

from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field

from .mass import MassProperties

class AxisymmetricBody(BaseModel):
    """Axisymmetric body definition.

    Attributes:
        length_m: Total body length in meters. (> 0)
        diameter_m: Body diameter in meters. (> 0)
        nose_type: Nose shape ("ogive", "conical" or "hemispherical"). Defaults to ogive.
        nose_length_m: Length of the nose section in meters. Defaults to None if unmeasured. (> 0)
        nose_diameter_m: Diameter at the base of the nose in meters. Defaults to None if unmeasured. (> 0)
        total_length_m: Total length of the vehicle including protrusions in meters. Defaults to None if unmeasured. (> 0)
        max_diameter_m: Maximum diameter including any transitions in meters. Defaults to None if unmeasured. (> 0)
        mass: Mass Properties
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["axisymmetric_body"] = Field(default="axisymmetric_body", frozen=True)

    length_m: float = Field(
        gt=0.0,
        description='''Total body length in meters. (> 0)'''
    )
    
    diameter_m: float = Field(
        gt=0.0,
        description='''Body diameter in meters. (> 0)'''
    )
    
    nose_type: Literal["ogive", "conical", "hemispherical"] = Field(
        default="ogive",
        description='''Nose shape ("ogive", "conical" or "hemispherical"). Defaults to ogive.'''
    )
    
    nose_length_m: float | None = Field(
        default=None, 
        gt=0.0,
        description='''Length of the nose section in meters. Defaults to None if unmeasured. (> 0)'''
    )
    
    nose_diameter_m: float | None = Field(
        default=None, 
        gt=0.0,
        description='''Diameter at the base of the nose in meters. Defaults to None if unmeasured. (> 0)'''
    )
    
    total_length_m: float | None = Field(
        default=None, 
        gt=0.0,
        description='''Total length of the vehicle including protrusions in meters. Defaults to None if unmeasured. (> 0)'''
    )
    
    max_diameter_m: float | None = Field(
        default=None, 
        gt=0.0,
        description='''Maximum diameter including any transitions in meters. Defaults to None if unmeasured. (> 0)'''
    )

    mass: MassProperties | None = Field(
        default=None,
        description='''Mass properties.'''
    )

AnyBodyComponent = Annotated[
    AxisymmetricBody, 
    Field(discriminator="type")
]