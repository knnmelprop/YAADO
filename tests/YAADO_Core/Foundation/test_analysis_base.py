"""Unit tests for BaseAnalysis and BaseAnalysisResults contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from YAADO_Core.Foundation.analysis_base import (
    BaseAnalysis,
    BaseAnalysisResults,
    FidelityLevel,
)
from YAADO_Core.Foundation.units import Dimensionless, Newtons
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig


@dataclass(frozen=True)
class MockTypedResults(BaseAnalysisResults):
    """Custom strongly typed result container used for testing."""

    thrust: Newtons
    burnout_mach: Dimensionless
    ground_impact: bool = False
    notes: str = "nominal"


class MockAnalysis(BaseAnalysis[MockTypedResults]):
    """Concrete analysis implementation for testing BaseAnalysis lifecycle."""

    fidelity = FidelityLevel.LEVEL_1

    def __init__(self, name: str = "mock_solver") -> None:
        super().__init__(name=name)
        self.should_pass_validation: bool = True

    def _setup(self, vehicle: BaseVehicleConfig, **kwargs: Any) -> None:
        self.vehicle_name = vehicle.name
        self.should_pass_validation = kwargs.get("should_pass_validation", True)

    def _compute(self, **kwargs: Any) -> MockTypedResults:
        return MockTypedResults(
            name=self.name,
            fidelity=self.fidelity,
            thrust=1500.0,
            burnout_mach=2.8,
        )

    def validate_results(self, results: MockTypedResults) -> bool:
        return self.should_pass_validation


def test_base_analysis_results_typed_extraction():
    """Verify scalar extraction and units reflection on BaseAnalysisResults."""
    res = MockTypedResults(
        name="test_sim",
        fidelity=FidelityLevel.LEVEL_1,
        thrust=1250.0,
        burnout_mach=2.2,
        ground_impact=False,
        notes="test run",
    )

    # Scalar extraction ignores strings and booleans
    scalars = res.scalars()
    assert scalars == {"thrust": 1250.0, "burnout_mach": 2.2}

    # Units reflection from Annotated types
    units = res.units()
    assert units == {"thrust": "N", "burnout_mach": "-"}

    # Attribute access
    assert res.thrust == 1250.0
    assert res.burnout_mach == 2.2
    assert res.ground_impact is False
    assert res.notes == "test run"
    assert res.name == "test_sim"
    assert res.fidelity == FidelityLevel.LEVEL_1


def test_base_analysis_lifecycle():
    """Verify BaseAnalysis setup check and logger property guard."""
    analysis = MockAnalysis()

    # Logger access before setup raises RuntimeError
    with pytest.raises(RuntimeError, match="has not been setup yet"):
        _ = analysis.logger

    # Execution before setup raises RuntimeError
    with pytest.raises(RuntimeError, match="called before setup"):
        analysis.execute()

    # Setup with minimal config
    vehicle = BaseVehicleConfig(name="test_rocket")
    analysis.setup(vehicle, enable_logging=False)

    # Logger is now accessible
    assert analysis.logger.vehicle_name == "test_rocket"

    # Execution returns strongly typed container
    results = analysis.execute()
    assert isinstance(results, MockTypedResults)
    assert isinstance(results, BaseAnalysisResults)
    assert results.thrust == 1500.0
    assert results.burnout_mach == 2.8


def test_base_analysis_validation_failure():
    """Verify BaseAnalysis raises RuntimeError if validation fails."""
    analysis = MockAnalysis()
    vehicle = BaseVehicleConfig(name="test_rocket")
    analysis.setup(vehicle, enable_logging=False, should_pass_validation=False)

    with pytest.raises(RuntimeError, match="failed physical validation checks"):
        analysis.execute()
