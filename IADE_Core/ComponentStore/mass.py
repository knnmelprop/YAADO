'''This module provides the standardized Pydantic components used to 
    represent mass properties and center of gravity (CG).
'''

from pydantic import BaseModel, Field, ConfigDict

class MassProperties(BaseModel):
    """Vehicle mass properties."""

    model_config = ConfigDict(extra="forbid")

    cg_from_nose_m: float = Field(
        gt=0.0,
        description='''Longitudinal centre of gravity measured from the nose tip
           in meters. Must be strictly positive (> 0) and less than the total
           vehicle length.''',
    )
    cg_source: str = Field(
        default="not provided",
        description='''Provenance of the CG value. Examples include `"estimate"`, 
            `"NX file_name.prt 01-01-2026"`, or a specific reference URL.''',
    )
    total_mass_kg: float | None = Field(
        gt=0.0,
        description='''Total vehicle mass in kilograms. Must be strictly positive
            (> 0). Defaults to None if unmeasured.''',
    )