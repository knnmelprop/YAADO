"""Base abstractions for YAADO analyses.

Every computational method derives from :class:`BaseAnalysis`.
Analyses declare their fidelity via :class:`FidelityLevel` and return a
strongly typed, frozen result container inheriting from :class:`BaseAnalysisResults`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, fields
from enum import IntEnum
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Generic,
    TypeVar,
    get_args,
    get_origin,
    get_type_hints,
)

from YAADO_Core.Foundation.flight_logger import FlightLogger

if TYPE_CHECKING:
    from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig


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


@dataclass(frozen=True)
class BaseAnalysisResults:
    """Universal base contract for all analysis result containers.

    Contains core metadata. Subclasses in discipline modules (`YAADO_Core/modules/`)
    define strictly typed fields with semantic SI unit annotations (e.g. ``Meters``, ``Newtons``).

    Attributes:
        name: Name of the analysis that produced the results.
        fidelity: Fidelity level of the method used.
    """

    name: str
    fidelity: FidelityLevel

    def scalars(self) -> dict[str, float]:
        """Extract all numeric scalar fields using standard dataclass reflection.

        Excludes metadata identifiers and non-scalar structures.

        Returns:
            Dictionary mapping scalar field names to floats in canonical SI units.
        """
        res: dict[str, float] = {}
        for f in fields(self):
            if f.name in ("name", "fidelity") or f.name.startswith("_"):
                continue
            val = getattr(self, f.name)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                res[f.name] = float(val)
        return res

    def units(self) -> dict[str, str]:
        """Auto-extract SI unit symbols from Annotated field type hints.

        Returns:
            Dictionary mapping each scalar metric name to its unit symbol string.
        """
        hints = get_type_hints(self.__class__, include_extras=True)
        scalar_keys = set(self.scalars().keys())
        out: dict[str, str] = {}
        for name in scalar_keys:
            hint = hints.get(name)
            if hint is not None and get_origin(hint) is Annotated:
                args = get_args(hint)
                if len(args) > 1 and isinstance(args[1], str):
                    out[name] = args[1]
                    continue
            out[name] = "-"
        return out

TResult = TypeVar("TResult", bound=BaseAnalysisResults)

class BaseAnalysis(ABC, Generic[TResult]):
    """Abstract base class for all analysis methods.

    Enforces the execution lifecycle via the Template Method pattern:
    setup verification -> computation via :meth:`_compute` -> validation via :meth:`validate_results`.

    Args:
        name: Unique analysis name.
    """

    fidelity: FidelityLevel = FidelityLevel.LEVEL_0

    def __init__(
        self,
        name: str,
    ) -> None:
        self.name = name
        self._logger: FlightLogger | None = None
        self._is_setup = False

    @property
    def logger(self) -> FlightLogger:
        """The FlightLogger bound to this analysis during setup.

        Returns:
            The active FlightLogger instance.

        Raises:
            RuntimeError: If accessed before setup(vehicle) is called.
        """
        if self._logger is None:
            raise RuntimeError(
                f"Analysis '{self.name}' has not been setup yet. "
                "Call setup(vehicle) before accessing the logger."
            )
        return self._logger

    @logger.setter
    def logger(self, value: FlightLogger) -> None:
        if not isinstance(value, FlightLogger):
            raise TypeError(
                f"logger must be a FlightLogger instance, got {type(value).__name__}"
            )
        self._logger = value

    def setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        enable_logging: bool = True,
        **kwargs: Any,
    ) -> None:
        """Bind analysis to vehicle configuration and prepare solver state.

        Initializes the FlightLogger and executes subclass setup.

        Args:
            vehicle: The centralized vehicle configuration to analyze.
            enable_logging: Whether FlightLogger creates disk artifacts. Defaults to True.
            **kwargs: Solver-specific execution settings.
        """
        self.logger = FlightLogger(
            vehicle_name=vehicle.name,
            analysis_name=self.name,
            enabled=enable_logging,
        )
        self._setup(vehicle, **kwargs)
        self._is_setup = True

    @abstractmethod
    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        **kwargs: Any,
    ) -> None:
        """Subclasses extract geometry and solver inputs from vehicle configuration."""

    def execute(self) -> TResult:
        """Run the analysis and return strongly typed results.

        Enforces setup verification, delegates computation to :meth:`_compute`,
        and runs physical validation checks.

        Returns:
            Strongly typed result container inheriting from BaseAnalysisResults.

        Raises:
            RuntimeError: If called before :meth:`setup` or if results fail validation.
        """
        if not self._is_setup:
            raise RuntimeError(
                f"Analysis '{self.name}'.execute() called before setup(vehicle)."
            )
        results = self._compute()
        if not self.validate_results(results):
            raise RuntimeError(
                f"Analysis '{self.name}' results failed physical validation checks."
            )
        return results

    @abstractmethod
    def _compute(self) -> TResult:
        """Subclasses execute the numerical solver and return typed results."""

    def validate_results(self, results: TResult) -> bool:
        """Sanity-check results against analytical expectations.

        Subclasses should override with physics-based checks. Default
        verifies that scalar outputs are present and non-empty.
        """
        return bool(results.scalars())
