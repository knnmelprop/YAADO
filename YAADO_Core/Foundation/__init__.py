"""Core infrastructure for the YAADO multi-fidelity design environment.

Exposes the base abstractions used by all analysis and vehicle modules
"""

from .analysis_base import (
    AnalysisResults,
    BaseAnalysis,
    FidelityLevel,
)
from .vehicle_base import (
    BaseVehicleConfig,
)

__all__ = [
    "BaseVehicleConfig",
    "AnalysisResults",
    "BaseAnalysis",
    "FidelityLevel",
]
