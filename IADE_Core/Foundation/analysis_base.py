"""Base abstractions for MELprop-IADE analyses.

Every computational method (VLM, cycle analysis, empirical correlations) 
derives from :class:`BaseAnalysis`.
Analyses declare their fidelity via :class:`FidelityLevel` and return a
uniform :class:`AnalysisResults` container so that workflows can swap
methods of different fidelity without changing downstream code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class FidelityLevel(IntEnum):
    """Fidelity ladder for analysis methods.

    Attributes:
        LEVEL_0: Analytical / handbook correlations (instant).
        LEVEL_1: Linear methods — VLM/AVL, XFOIL, DATCOM-style empirics.
        LEVEL_2: Medium fidelity — Euler CFD, 1-D cycle analysis (pyCycle).
        LEVEL_3: High fidelity — RANS CFD, FEM.
    """

    LEVEL_0 = 0
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3


@dataclass
class AnalysisResults:
    """Uniform container for outputs of any :class:`BaseAnalysis`.

    Attributes:
        name: Name of the analysis that produced the results.
        fidelity: Fidelity level of the method used.
        data: Scalar outputs in SI units, keyed by symbol (e.g. ``CL``,
            ``CD``, ``CL_alpha``, ``CM``).
        metadata: Free-form context (solver version, mesh size, warnings).
    """

    name: str
    fidelity: FidelityLevel
    data: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> float:
        """Return a scalar output by symbol name."""
        return self.data[key]

    def __contains__(self, key: str) -> bool:
        return key in self.data


class BaseAnalysis(ABC):
    """Abstract base class for all analysis methods.

    Subclasses must declare their fidelity level and implement the
    ``setup`` / ``execute`` pair. ``execute`` must only be called after a
    successful ``setup``.

    Args:
        name: Unique analysis name (used in :class:`AnalysisResults`).
    """

    #: Fidelity level of the method; override in subclasses.
    fidelity: FidelityLevel = FidelityLevel.LEVEL_0

    def __init__(self, name: str) -> None:
        self.name = name
        self._is_setup = False

    @abstractmethod
    def setup(self, *args: Any, **kwargs: Any) -> None:
        """Bind the analysis to a vehicle configuration and prepare inputs."""

    @abstractmethod
    def execute(self) -> AnalysisResults:
        """Run the analysis and return results.

        Returns:
            AnalysisResults with scalar outputs in SI units.

        Raises:
            RuntimeError: If called before :meth:`setup`.
        """

    def validate_results(self, results: AnalysisResults) -> bool:
        """Sanity-check results against analytical expectations.

        Subclasses should override with physics-based checks. The default
        implementation only verifies the container is non-empty.
        """
        return bool(results.data)
