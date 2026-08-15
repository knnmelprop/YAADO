# MELprop-IADE | tests.unit.test_aero_avl | v0.1.0
"""Unit tests for analyses.aerodynamics.avl_wrapper."""

import math
from pathlib import Path

import pytest

from IADE_Core.modules.aerodynamics.avl_wrapper import AVLAnalysis, helmbold_cl_alpha
from IADE_Core.FlightDeck.component_base import FidelityLevel
from IADE_Core.Inspectors.vehicle_schema import BaseVehicleConfig, UAVConfig

REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture()
def uav_config() -> UAVConfig:
    """Load the committed GTM-140 drone configuration."""
    path = REPO_ROOT / "Hangar" / "gtm140_drone" / "vehicle_config.yaml"
    config = BaseVehicleConfig.from_yaml(path)
    assert isinstance(config, UAVConfig)
    return config


def test_execute_returns_validated_coefficients(uav_config: UAVConfig) -> None:
    """CL_alpha lands within 2*pi/(1 + 2/AR) +/- 20% and CL/CD are sane."""
    analysis = AVLAnalysis()
    analysis.setup(uav_config, mach=0.3, alpha_deg=4.0)
    results = analysis.execute()

    ar = uav_config.wing.aspect_ratio
    reference = 2.0 * math.pi / (1.0 + 2.0 / ar)
    assert results["CL_alpha"] == pytest.approx(reference, rel=0.2)
    assert 0.0 < results["CL"] < 1.5
    assert 0.0 < results["CD"] < 0.2
    assert results.fidelity == FidelityLevel.LEVEL_1


def test_setup_rejects_out_of_envelope_conditions(uav_config: UAVConfig) -> None:
    """Mach >= 0.6 or |alpha| >= 15 deg violate AVL applicability."""
    analysis = AVLAnalysis()
    with pytest.raises(ValueError, match="Mach"):
        analysis.setup(uav_config, mach=0.8, alpha_deg=2.0)
    with pytest.raises(ValueError, match="alpha"):
        analysis.setup(uav_config, mach=0.3, alpha_deg=20.0)


def test_execute_before_setup_raises() -> None:
    """execute() without setup() must raise RuntimeError."""
    with pytest.raises(RuntimeError):
        AVLAnalysis().execute()


def test_helmbold_limits() -> None:
    """Helmbold slope grows with AR and stays below the 2D limit 2*pi."""
    slopes = [helmbold_cl_alpha(ar) for ar in (2.0, 6.0, 12.0, 40.0)]
    assert slopes == sorted(slopes)
    assert all(s < 2.0 * math.pi for s in slopes)
