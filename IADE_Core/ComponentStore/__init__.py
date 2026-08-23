# MELprop-IADE | src.schemas | v0.1.0
"""Pydantic v2 configuration schemas for MELprop-IADE vehicles."""

from .mass import MassProperties

from IADE_Core.ComponentStore.vehicle_schema import (
    BaseVehicleConfig,
)

__all__ = [
    "BaseVehicleConfig",
    "MassProperties",
]
