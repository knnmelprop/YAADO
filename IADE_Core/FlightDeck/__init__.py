"""Core infrastructure for the MELprop-IADE multi-fidelity design environment.

Exposes the base abstractions used by all analysis and vehicle modules:

- :class:`IADE_Core.component_base.BaseComponent`
- :class:`IADE_Core.component_base.BaseAnalysis`
- :class:`IADE_Core.component_base.FidelityLevel`
- :class:`IADE_Core.component_base.AnalysisResults`
- :class:`IADE_Core.component_base.ComponentRegistry`
"""

from IADE_Core.Foundation.component_base import (
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
