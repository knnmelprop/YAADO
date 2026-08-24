'''This module provides the standardized Pydantic components used to 
    represent mass properties and center of gravity (CG).
'''

from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class MassProperties(BaseModel):
    """Vehicle mass properties.

    Attributes:
        cg_from_nose_m: Longitudinal centre of gravity measured from the nose tip of the entire vehicle in meters. Must be less than the total vehicle length. (> 0)
        cg_source: Provenance of the CG value. Examples include "estimate", "NX file_name.prt 01-01-2026", or a specific reference URL.
        total_mass_kg: Total vehicle mass in kilograms. Defaults to None if unmeasured. (> 0)
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["mass"] = Field(default="mass", frozen=True)

    cg_from_nose_m: float = Field(
        gt=0.0,
        description='''Longitudinal centre of gravity measured from the nose tip of the entire vehicle in meters. Must be less than the total vehicle length. (> 0)''',
    )
    cg_source: str = Field(
        default="not provided",
        description='''Provenance of the CG value. Examples include "estimate", "NX file_name.prt 01-01-2026", or a specific reference URL.''',
    )
    total_mass_kg: float | None = Field(
        default=None,
        gt=0.0,
        description='''Total vehicle mass in kilograms. Defaults to None if unmeasured. (> 0)''',
    )
