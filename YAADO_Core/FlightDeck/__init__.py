"""Core infrastructure for the YAADO multi-fidelity design environment.

Exposes the base abstractions used by all analysis and vehicle modules:

- :class:`YAADO_Core.analysis_base.BaseComponent`
- :class:`YAADO_Core.analysis_base.BaseAnalysis`
- :class:`YAADO_Core.analysis_base.FidelityLevel`
- :class:`YAADO_Core.analysis_base.AnalysisResults`
- :class:`YAADO_Core.analysis_base.ComponentRegistry`
"""

from YAADO_Core.Foundation.analysis_base import (
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
