"""Core infrastructure for the MELprop-IADE multi-fidelity design environment.

Exposes the base abstractions used by all analysis and vehicle modules:

- :class:`IADE_Core.analysis_base.BaseComponent`
- :class:`IADE_Core.analysis_base.BaseAnalysis`
- :class:`IADE_Core.analysis_base.FidelityLevel`
- :class:`IADE_Core.analysis_base.AnalysisResults`
- :class:`IADE_Core.analysis_base.ComponentRegistry`
"""

from IADE_Core.Foundation.analysis_base import (
    AnalysisResults,
    BaseAnalysis,
    BaseComponent,
    ComponentRegistry,
    FidelityLevel,
)

__all__ = [
    "AnalysisResults",
    "BaseAnalysis",
    "BaseComponent",
    "ComponentRegistry",
    "FidelityLevel",
]
