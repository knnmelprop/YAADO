# MELprop-IADE | src.schemas | v0.1.0
"""Pydantic v2 configuration schemas for MELprop-IADE vehicles."""

from src.schemas.vehicle_schema import (
    BaseVehicleConfig,
    BodyConfig,
    BoosterGeometry,
    BoosterStage,
    FinConfig,
    MassProperties,
    RamjetConfig,
    RocketConfig,
    SolidRocketConfig,
    SolidRocketPropulsion,
    TurbojetConfig,
    UAVConfig,
    WingConfig,
)

__all__ = [
    "BaseVehicleConfig",
    "BodyConfig",
    "BoosterGeometry",
    "BoosterStage",
    "FinConfig",
    "MassProperties",
    "RamjetConfig",
    "RocketConfig",
    "SolidRocketConfig",
    "SolidRocketPropulsion",
    "TurbojetConfig",
    "UAVConfig",
    "WingConfig",
]
