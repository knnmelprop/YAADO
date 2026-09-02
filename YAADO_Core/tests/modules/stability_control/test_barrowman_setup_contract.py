"""Tests for the BaseAnalysis.setup(vehicle, operating_state) contract on the
Barrowman stability-control analyses (Issue #28).

These tests build a generic, realistic ``BaseVehicleConfig`` in-memory (no
YAML on disk) and verify that ``setup`` reads geometry exclusively from the
``vehicle`` object, matching the numerics of the retired file-parsing
``load_geometry`` path.
"""

from __future__ import annotations

import math

import pytest

from YAADO_Core.ComponentStore.aero_surfaces import Fins
from YAADO_Core.ComponentStore.body import AxisymmetricBody
from YAADO_Core.ComponentStore.mass import MassProperties
from YAADO_Core.Foundation.analysis_base import AnalysisResults, FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.stability_control.methods.barrowman.barrowman_extended import (
    BarrowmanExtendedAnalysis,
)
from YAADO_Core.modules.stability_control.methods.barrowman.barrowman_stability import (
    BarrowmanStabilityAnalysis,
    RocketGeometry,
    geometry_from_vehicle,
)


@pytest.fixture()
def generic_vehicle() -> BaseVehicleConfig:
    """A minimal, realistic body+fins vehicle for the Barrowman method.

    Values are loosely modeled on a small sounding-rocket airframe: a
    slender ogive-nosed body (fineness ratio > 5) with a 4-fin cruciform
    tail set, and an explicit global CG.
    """
    body = AxisymmetricBody(
        length_m=2.0,
        diameter_m=0.15,
        nose_type="ogive",
        nose_length_m=0.45,
        nose_diameter_m=0.12,
        total_length_m=2.0,
    )
    fins = Fins(
        count=4,
        span_m=0.12,
        sweep_deg=25.0,
        chord_root_m=0.20,
        chord_tip_m=0.08,
    )
    mass = MassProperties(cg_from_nose_m=1.2, total_mass_kg=12.0)

    return BaseVehicleConfig(
        name="generic_test_rocket",
        bodies={"main_body": body},
        aero_surfaces={"tail_fins": fins},
        mass_properties=mass,
    )


def test_geometry_from_vehicle_reads_all_fields(generic_vehicle: BaseVehicleConfig) -> None:
    """geometry_from_vehicle maps every RocketGeometry field from the vehicle."""
    geometry = geometry_from_vehicle(generic_vehicle)

    assert isinstance(geometry, RocketGeometry)
    assert geometry.d_ref_m == pytest.approx(0.15)
    assert geometry.nose_length_m == pytest.approx(0.45)
    assert geometry.nose_base_diameter_m == pytest.approx(0.12)
    assert geometry.total_length_m == pytest.approx(2.0)
    assert geometry.fin_count == 4
    assert geometry.fin_span_m == pytest.approx(0.12)
    assert geometry.fin_root_chord_m == pytest.approx(0.20)
    assert geometry.fin_tip_chord_m == pytest.approx(0.08)
    assert geometry.fin_sweep_deg == pytest.approx(25.0)
    assert geometry.cg_from_nose_m == pytest.approx(1.2)


def test_geometry_from_vehicle_falls_back_to_body_length_when_total_unset() -> None:
    """total_length_m falls back to the body's own length_m when unmeasured."""
    body = AxisymmetricBody(
        length_m=1.5,
        diameter_m=0.10,
        nose_length_m=0.30,
        nose_diameter_m=0.10,
    )
    fins = Fins(count=3, span_m=0.08, sweep_deg=20.0, chord_root_m=0.15, chord_tip_m=0.05)
    mass = MassProperties(cg_from_nose_m=0.9)
    vehicle = BaseVehicleConfig(
        name="fallback_test",
        bodies={"body": body},
        aero_surfaces={"fins": fins},
        mass_properties=mass,
    )

    geometry = geometry_from_vehicle(vehicle)
    assert geometry.total_length_m == pytest.approx(1.5)


def test_geometry_from_vehicle_uses_body_mass_when_no_global_mass() -> None:
    """CG is read from the body's own mass block if vehicle.mass_properties is unset."""
    body = AxisymmetricBody(
        length_m=1.5,
        diameter_m=0.10,
        nose_length_m=0.30,
        nose_diameter_m=0.10,
        mass=MassProperties(cg_from_nose_m=0.75),
    )
    fins = Fins(count=3, span_m=0.08, sweep_deg=20.0, chord_root_m=0.15, chord_tip_m=0.05)
    vehicle = BaseVehicleConfig(
        name="body_mass_test",
        bodies={"body": body},
        aero_surfaces={"fins": fins},
    )

    geometry = geometry_from_vehicle(vehicle)
    assert geometry.cg_from_nose_m == pytest.approx(0.75)


def test_geometry_from_vehicle_rejects_missing_cg() -> None:
    """No vehicle.mass_properties and no body.mass -> explicit ValueError."""
    body = AxisymmetricBody(length_m=1.5, diameter_m=0.10, nose_length_m=0.30, nose_diameter_m=0.10)
    fins = Fins(count=3, span_m=0.08, sweep_deg=20.0, chord_root_m=0.15, chord_tip_m=0.05)
    vehicle = BaseVehicleConfig(name="no_cg", bodies={"body": body}, aero_surfaces={"fins": fins})

    with pytest.raises(ValueError, match="CG"):
        geometry_from_vehicle(vehicle)


def test_geometry_from_vehicle_rejects_missing_body() -> None:
    """A vehicle with no AxisymmetricBody raises rather than guessing."""
    fins = Fins(count=3, span_m=0.08, sweep_deg=20.0, chord_root_m=0.15, chord_tip_m=0.05)
    vehicle = BaseVehicleConfig(name="no_body", aero_surfaces={"fins": fins})

    with pytest.raises(ValueError, match="AxisymmetricBody"):
        geometry_from_vehicle(vehicle)


def test_geometry_from_vehicle_rejects_missing_fins() -> None:
    """A vehicle with no Fins component raises rather than guessing."""
    body = AxisymmetricBody(length_m=1.5, diameter_m=0.10, nose_length_m=0.30, nose_diameter_m=0.10)
    vehicle = BaseVehicleConfig(
        name="no_fins", bodies={"body": body}, mass_properties=MassProperties(cg_from_nose_m=0.5)
    )

    with pytest.raises(ValueError, match="Fins"):
        geometry_from_vehicle(vehicle)


def test_barrowman_stability_setup_matches_new_contract_signature(
    generic_vehicle: BaseVehicleConfig,
) -> None:
    """setup(vehicle, operating_state=None) binds geometry read from vehicle."""
    analysis = BarrowmanStabilityAnalysis()
    analysis.setup(generic_vehicle, operating_state=None)

    assert analysis._is_setup is True
    assert analysis.geometry is not None
    assert analysis.geometry.d_ref_m == pytest.approx(0.15)


def test_barrowman_stability_execute_after_vehicle_setup(
    generic_vehicle: BaseVehicleConfig,
) -> None:
    """execute() after the new setup() still returns a valid AnalysisResults."""
    analysis = BarrowmanStabilityAnalysis()
    analysis.setup(generic_vehicle)
    results = analysis.execute()

    assert isinstance(results, AnalysisResults)
    assert results.fidelity is FidelityLevel.LEVEL_0
    assert "static_margin_cal" in results
    assert "cp_subsonic_m" in results
    assert math.isfinite(results["static_margin_cal"])
    # CP must lie within the physical body length.
    assert 0.0 <= results["cp_subsonic_m"] <= analysis.geometry.total_length_m


def test_barrowman_extended_setup_matches_new_contract_signature(
    generic_vehicle: BaseVehicleConfig,
) -> None:
    """BarrowmanExtendedAnalysis.setup also takes (vehicle, operating_state)."""
    analysis = BarrowmanExtendedAnalysis()
    analysis.setup(generic_vehicle, operating_state={"mach": 2.5})

    assert analysis._is_setup is True
    assert analysis._geometry is not None
    assert analysis._geometry.fin_count == 4


def test_barrowman_stability_rejects_execute_before_setup() -> None:
    """execute() before setup() still raises (contract unaffected by #28)."""
    analysis = BarrowmanStabilityAnalysis()
    with pytest.raises(RuntimeError):
        analysis.execute()
