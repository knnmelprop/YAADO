"""Core infrastructure for the YAADO multi-fidelity design environment.

Exposes the base abstractions used by all analysis and vehicle modules
"""  # noqa: N999

from .analysis_base import (
    BaseAnalysis,
    BaseAnalysisResults,
    FidelityLevel,
)
from .flight_logger import (
    CheckpointPayload,
    FlightLogger,
    YaadoJSONEncoder,
)
from .mission_builder import (
    AnyMissionSegment,
    BaseMissionSegment,
    BoostSegment,
    ClimbSegment,
    CruiseSegment,
    DescentSegment,
    MissionBuilder,
    MissionProfile,
    StagingSegment,
)
from .solver_registry import (
    DEFAULT_REGISTRY,
    SolverInfo,
    SolverRegistry,
)
from .vehicle_base import (
    BaseVehicleConfig,
)
from .vehicle_factory import (
    VehicleFactory,
)

__all__ = [
    "DEFAULT_REGISTRY",
    "AnyMissionSegment",
    "BaseAnalysis",
    "BaseAnalysisResults",
    "BaseMissionSegment",
    "BaseVehicleConfig",
    "BoostSegment",
    "CheckpointPayload",
    "ClimbSegment",
    "CruiseSegment",
    "DescentSegment",
    "FidelityLevel",
    "FlightLogger",
    "MissionBuilder",
    "MissionProfile",
    "SolverInfo",
    "SolverRegistry",
    "StagingSegment",
    "VehicleFactory",
    "YaadoJSONEncoder",
]



