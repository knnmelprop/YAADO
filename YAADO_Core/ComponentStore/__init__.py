"""Pydantic v2 configuration schemas for YAADO vehicles."""
from typing import Annotated
from pydantic import Field

from .mass import MassProperties
from .body import AxisymmetricBody, AnyBodyComponent
from .propulsion import SolidMotor, RamjetEngine, TurbojetEngine, AnyPropulsionComponent
from .aero_surfaces import Fins, Wings, ControlSurface, AnyAeroComponent

AnyComponent = Annotated[
    MassProperties | AnyBodyComponent | AnyPropulsionComponent | AnyAeroComponent,
    Field(discriminator="type")
]

# Standard tuples for runtime isinstance() checks and CLI menu generation
AERO_COMPONENTS = (Fins, Wings)
BODY_COMPONENTS = (AxisymmetricBody,)
PROPULSION_COMPONENTS = (SolidMotor, RamjetEngine, TurbojetEngine)
ALL_COMPONENTS = (MassProperties,) + AERO_COMPONENTS + BODY_COMPONENTS + PROPULSION_COMPONENTS

__all__ = [
    "MassProperties",
    "AxisymmetricBody",
    "SolidMotor",
    "RamjetEngine",
    "TurbojetEngine",
    "Fins",
    "Wings",
    "ControlSurface",
    "AnyPropulsionComponent",
    "AnyAeroComponent",
    "AnyBodyComponent",
    "AnyComponent",
    "AERO_COMPONENTS",
    "BODY_COMPONENTS",
    "PROPULSION_COMPONENTS",
    "ALL_COMPONENTS",
]
