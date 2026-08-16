# MELprop-IADE | src.schemas | v0.1.0
"""Pydantic v2 configuration schemas for MELprop-IADE vehicles."""

from IADE_Core.Inspectors.vehicle_schema import (
    BaseVehicleConfig,
    MassProperties,
)

__all__ = [
    "BaseVehicleConfig",
    "MassProperties",
]
