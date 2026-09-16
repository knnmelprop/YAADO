"""Unit tests for BaseAnalysis and BaseAnalysisResults contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import pytest

from YAADO_Core.Foundation.analysis_base import (
    AnalysisResults,
    BaseAnalysis,
    BaseAnalysisResults,
    FidelityLevel,
)
from YAADO_Core.Foundation.flight_logger import FlightLogger
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig


@dataclass
class MockTypedResults(BaseAnalysisResults):
    """Custom strongly typed result container used for testing."""

    thrust: float = 1200.0
    burnout_mach: float = 2.4
    ground_impact: bool = False
    notes: str = "nominal"

    UNITS: ClassVar[dict[str, str]] = {
        "thrust": "N",
        "burnout_mach": "-",
    }


class MockAnalysis(BaseAnalysis[MockTypedResults]):
    """Concrete analysis implementation for testing BaseAnalysis lifecycle."""

    fidelity = FidelityLevel.LEVEL_1

    def __init__(self, name: str = "mock_solver") -> None:
        super().__init__(name=name)

    def setup(self, vehicle: BaseVehicleConfig, *args: Any, **kwargs: Any) -> None:
        self.logger = FlightLogger(
            vehicle_name=vehicle.name,
            analysis_name=self.name,
            enabled=False,
        )
        self._is_setup = True

    def execute(self) -> MockTypedResults:
        if not self._is_setup:
            raise RuntimeError("execute called before setup")
        return MockTypedResults(
            name=self.name,
            fidelity=self.fidelity,
            thrust=1500.0,
            burnout_mach=2.8,
        )


def test_base_analysis_results_typed_extraction():
    """Verify scalar extraction and units mapping on BaseAnalysisResults."""
    res = MockTypedResults(
        name="test_sim",
        fidelity=FidelityLevel.LEVEL_1,
        thrust=1250.0,
        burnout_mach=2.2,
    )

    # Scalar extraction ignores strings and booleans
    scalars = res.scalar_metrics()
    assert scalars == {"thrust": 1250.0, "burnout_mach": 2.2}

    # Units mapping
    units = res.units_map()
    assert units == {"thrust": "N", "burnout_mach": "-"}

    # Attribute and key access
    assert res.thrust == 1250.0
    assert res["thrust"] == 1250.0
    assert "burnout_mach" in res
    assert res.get_unit("thrust") == "N"
    assert res.get_unit("unknown") == "-"


def test_analysis_results_legacy_compatibility():
    """Verify legacy AnalysisResults behavior is fully preserved."""
    legacy = AnalysisResults(
        name="legacy_solver",
        fidelity=FidelityLevel.LEVEL_0,
        data={"CL": 0.45, "CD": 0.02},
        units={"CL": "-", "CD": "-"},
        metadata={"solver": "handbook"},
    )

    assert legacy["CL"] == 0.45
    assert "CD" in legacy
    assert legacy.scalar_metrics() == {"CL": 0.45, "CD": 0.02}
    assert legacy.units_map() == {"CL": "-", "CD": "-"}
    assert legacy.to_dict()["data"] == {"CL": 0.45, "CD": 0.02}


def test_base_analysis_lifecycle():
    """Verify BaseAnalysis setup check and logger property guard."""
    analysis = MockAnalysis()

    # Logger access before setup raises RuntimeError
    with pytest.raises(RuntimeError, match="has not been setup yet"):
        _ = analysis.logger

    # Setup with minimal config
    vehicle = BaseVehicleConfig(name="test_rocket")
    analysis.setup(vehicle)

    # Logger is now accessible
    assert analysis.logger.vehicle_name == "test_rocket"

    # Execution returns strongly typed container
    results = analysis.execute()
    assert isinstance(results, MockTypedResults)
    assert isinstance(results, BaseAnalysisResults)
    assert results.thrust == 1500.0
    assert results.burnout_mach == 2.8
    assert analysis.validate_results(results) is True
