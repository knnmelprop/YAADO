"""Pydantic v2 configuration schemas for MELprop-IADE vehicles."""
from typing import Annotated
from pydantic import Field

from .mass import MassProperties
from .body import AxisymmetricBody
from .propulsion import SolidMotor, RamjetEngine
from .aero_surfaces import Fins, ControlSurface

# Define the Union BEFORE any outside files import this module to break circular dependencies
AnyComponent = Annotated[
    MassProperties | AxisymmetricBody | SolidMotor | RamjetEngine | Fins,
    Field(discriminator="type")
]

# (We removed the import of BaseVehicleConfig from here because it caused a circular import
# with Foundation.vehicle_base. BaseVehicleConfig lives safely in Foundation now!)

__all__ = [
    "MassProperties",
    "AxisymmetricBody",
    "SolidMotor",
    "RamjetEngine",
    "Fins",
    "ControlSurface",
    "AnyComponent",
]
