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
from .solver_registry import (
    DEFAULT_REGISTRY,
    SolverInfo,
    SolverRegistry,
)
from .vehicle_base import (
    BaseVehicleConfig,
)

__all__ = [
    "BaseAnalysis",
    "BaseAnalysisResults",
    "BaseVehicleConfig",
    "CheckpointPayload",
    "DEFAULT_REGISTRY",
    "FidelityLevel",
    "FlightLogger",
    "SolverInfo",
    "SolverRegistry",
    "YaadoJSONEncoder",
]
