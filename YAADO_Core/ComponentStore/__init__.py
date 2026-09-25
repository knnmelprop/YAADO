"""Pydantic v2 configuration schemas for YAADO vehicles."""
from typing import Annotated

from pydantic import Field

from .aero_surfaces import AnyAeroComponent, Fins, Wings
from .body import AnyBodyComponent, AxisymmetricBody
from .mass import MassProperties
from .propulsion import (
    AnyBoosterComponent,
    AnyPropulsionComponent,
    RamjetEngine,
    SolidMotor,
    TurbojetEngine,
)

AnyComponent = Annotated[
    MassProperties | AnyBodyComponent | AnyPropulsionComponent | AnyAeroComponent,
    Field(discriminator="type")
]

# Standard tuples for runtime isinstance() checks and CLI menu generation
AERO_COMPONENTS = (Fins, Wings)
BODY_COMPONENTS = (AxisymmetricBody,)
PROPULSION_COMPONENTS = (SolidMotor, RamjetEngine, TurbojetEngine)
BOOSTER_COMPONENTS = (SolidMotor,)
ALL_COMPONENTS = (MassProperties,) + AERO_COMPONENTS + BODY_COMPONENTS + PROPULSION_COMPONENTS

__all__ = [
    "AERO_COMPONENTS",
    "ALL_COMPONENTS",
    "BODY_COMPONENTS",
    "BOOSTER_COMPONENTS",
    "PROPULSION_COMPONENTS",
    "AnyAeroComponent",
    "AnyBodyComponent",
    "AnyBoosterComponent",
    "AnyComponent",
    "AnyPropulsionComponent",
    "MassProperties",
]
