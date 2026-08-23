"""Pydantic v2 configuration schemas for MELprop-IADE vehicles."""

from .mass import MassProperties

from IADE_Core.Foundation.vehicle_base import (
    BaseVehicleConfig,
)

__all__ = [
    "BaseVehicleConfig",
    "MassProperties",
]
