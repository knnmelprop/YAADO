# MELprop-IADE | core | v0.1.0
"""Core infrastructure for the MELprop-IADE multi-fidelity design environment.

Exposes the base abstractions used by all analysis and vehicle modules:

- :class:`core.component_base.BaseComponent`
- :class:`core.component_base.BaseAnalysis`
- :class:`core.component_base.FidelityLevel`
- :class:`core.component_base.AnalysisResults`
- :class:`core.component_base.ComponentRegistry`
"""

from core.component_base import (
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
