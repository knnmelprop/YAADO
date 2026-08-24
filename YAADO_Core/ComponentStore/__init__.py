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
]
