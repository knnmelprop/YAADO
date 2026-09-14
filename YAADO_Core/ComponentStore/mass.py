'''This module provides the standardized Pydantic components used to 
    represent mass properties and center of gravity (CG).
'''

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field


class MassProperties(BaseModel):
    """Vehicle mass properties.

    Note:
        Example values are taken from the AGM-84 Harpoon.

    Attributes:
        cg_from_nose: Longitudinal centre of gravity measured from the nose tip of the entire vehicle in meters. Must be less than the total vehicle length. (> 0)
        cg_source: Provenance of the CG value. Examples include "estimate", "NX file_name.prt 01-01-2026", or a specific reference URL.
        total_mass: Total vehicle mass in kilograms. Defaults to None if unmeasured. (> 0)
    """

    model_config = ConfigDict(extra="forbid")

    UNITS: ClassVar[dict[str, str]] = {
        "cg_from_nose": "m",
        "total_mass": "kg",
    }

    type: Literal["mass"] = Field(default="mass", frozen=True)

    cg_from_nose: float = Field(
        gt=0.0,
        examples=[2.05],
        description='''Longitudinal centre of gravity measured from the nose tip of the entire vehicle in meters. Must be less than the total vehicle length. (> 0)''',
    )
    cg_source: str = Field(
        default="not provided",
        examples=["AGM-84A baseline mass properties document"],
        description='''Provenance of the CG value. Examples include "estimate", "NX file_name.prt 01-01-2026", or a specific reference URL.''',
    )
    total_mass: float | None = Field(
        default=None,
        gt=0.0,
        examples=[520.0],
        description='''Total vehicle mass in kilograms. Defaults to None if unmeasured. (> 0)''',
    )

