'''This module provides the standardized Pydantic components used to 
    represent axisymmetric bodies and fuselages.
'''

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from .mass import MassProperties


class AxisymmetricBody(BaseModel):
    """Axisymmetric body definition.

    Note:
        Example values are taken from the AGM-84 Harpoon.

    Attributes:
        length: Total body length in meters. (> 0)
        diameter: Body diameter in meters. (> 0)
        nose_type: Nose shape ("ogive", "conical" or "hemispherical"). Defaults to ogive.
        nose_length: Length of the nose section in meters. Defaults to None if unmeasured. (> 0)
        nose_diameter: Diameter at the base of the nose in meters. Defaults to None if unmeasured. (> 0)
        total_length: Total length of the vehicle including protrusions in meters. Defaults to None if unmeasured. (> 0)
        max_diameter: Maximum diameter including any transitions in meters. Defaults to None if unmeasured. (> 0)
        mass: Mass Properties
    """

    model_config = ConfigDict(extra="forbid")

    UNITS: ClassVar[dict[str, str]] = {
        "length": "m",
        "diameter": "m",
        "nose_length": "m",
        "nose_diameter": "m",
        "total_length": "m",
        "max_diameter": "m",
    }

    type: Literal["axisymmetric_body"] = Field(default="axisymmetric_body", frozen=True)

    length: float = Field(
        gt=0.0,
        examples=[3.84],
        description='''Total body length in meters. (> 0)'''
    )
    
    diameter: float = Field(
        gt=0.0,
        examples=[0.343],
        description='''Body diameter in meters. (> 0)'''
    )
    
    nose_type: Literal["ogive", "conical", "hemispherical"] = Field(
        default="ogive",
        examples=["ogive"],
        description='''Nose shape ("ogive", "conical" or "hemispherical"). Defaults to ogive.'''
    )
    
    nose_length: float | None = Field(
        default=None, 
        gt=0.0,
        examples=[0.75],
        description='''Length of the nose section in meters. Defaults to None if unmeasured. (> 0)'''
    )
    
    nose_diameter: float | None = Field(
        default=None, 
        gt=0.0,
        examples=[0.343],
        description='''Diameter at the base of the nose in meters. Defaults to None if unmeasured. (> 0)'''
    )
    
    total_length: float | None = Field(
        default=None, 
        gt=0.0,
        examples=[3.84],
        description='''Total length of the vehicle including protrusions in meters. Defaults to None if unmeasured. (> 0)'''
    )
    
    max_diameter: float | None = Field(
        default=None, 
        gt=0.0,
        examples=[0.343],
        description='''Maximum diameter including any transitions in meters. Defaults to None if unmeasured. (> 0)'''
    )

    mass: MassProperties | None = Field(
        default=None,
        examples=[
            {
                "type": "mass",
                "cg_from_nose": 2.05,
                "cg_source": "AGM-84A baseline mass properties document",
                "total_mass": 520.0,
            }
        ],
        description='''Mass properties.'''
    )

AnyBodyComponent = Annotated[
    AxisymmetricBody, 
    Field(discriminator="type")
]