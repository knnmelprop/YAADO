"""Unit tests for YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof."""

import math

import pytest

from YAADO_Core.ComponentStore import (
    AxisymmetricBody,
    Fins,
    MassProperties,
    SolidMotor,
)
from YAADO_Core.Foundation.analysis_base import AnalysisResults, FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
    H0_M,
    LAUNCH_ANGLE_DEG,
    PointMass3DOFBoostAnalysis,
    resolve_booster_params_from_vehicle,
)


def _build_generic_solid_rocket() -> BaseVehicleConfig:
    """Build a minimal, generic, schema-valid solid-rocket vehicle config.

    Uses realistic small sounding-rocket values (consistent Isp/mdot/thrust,
    slender body, cruciform fins) so all cross-field validators pass.
    """
    motor = SolidMotor(
        isp_sl_s=180.0,
        isp_vacuum_s=210.0,
        propellant_mass_kg=8.0,
        burn_time_s=4.0,
        thrust_mean_N=180.0 * (8.0 / 4.0) * 9.80665,
        thrust_peak_N=180.0 * (8.0 / 4.0) * 9.80665 * 1.2,
        propellant_density_kg_m3=1750.0,
    )
    body = AxisymmetricBody(
        length_m=2.0,
        diameter_m=0.15,
        nose_length_m=0.4,
        nose_diameter_m=0.15,
        total_length_m=2.0,
    )
    fins = Fins(
        count=4,
        span_m=0.08,
        sweep_deg=30.0,
        chord_root_m=0.15,
        chord_tip_m=0.05,
    )
    mass = MassProperties(cg_from_nose_m=1.2, total_mass_kg=20.0)

    return BaseVehicleConfig(
        name="generic_test_sounding_rocket",
        propulsion={"stage_1": motor},
        bodies={"body": body},
        aero_surfaces={"fins": fins},
        mass_properties=mass,
    )


@pytest.fixture
def vehicle() -> BaseVehicleConfig:
    """A generic, schema-valid solid-rocket vehicle for trajectory tests."""
    return _build_generic_solid_rocket()


def test_resolve_booster_params_from_vehicle_reads_components(
    vehicle: BaseVehicleConfig,
) -> None:
    """Booster params are correctly resolved from vehicle composition."""
    params = resolve_booster_params_from_vehicle(vehicle)

    assert params.launch_mass_kg == pytest.approx(20.0)
    assert params.propellant_mass_kg == pytest.approx(8.0)
    assert params.burnout_mass_kg == pytest.approx(12.0)
    assert params.burn_time_s == pytest.approx(4.0)
    assert params.mdot_kg_s == pytest.approx(2.0)
    assert params.launch_angle_deg == pytest.approx(LAUNCH_ANGLE_DEG)
    assert params.a_ref_m2 == pytest.approx(math.pi / 4.0 * 0.15**2)


def test_resolve_booster_params_launch_angle_override(vehicle: BaseVehicleConfig) -> None:
    """operating_state overrides the default launch angle."""
    params = resolve_booster_params_from_vehicle(
        vehicle, operating_state={"launch_angle_deg": 45.0}
    )
    assert params.launch_angle_deg == pytest.approx(45.0)
    assert params.launch_angle_rad == pytest.approx(math.radians(45.0))


def test_resolve_booster_params_requires_mass_properties() -> None:
    """A vehicle missing mass_properties.total_mass_kg raises ValueError."""
    vehicle = _build_generic_solid_rocket()
    vehicle.mass_properties = None
    with pytest.raises(ValueError):
        resolve_booster_params_from_vehicle(vehicle)


def test_point_mass_3dof_setup_execute_new_contract(vehicle: BaseVehicleConfig) -> None:
    """setup(vehicle, operating_state) + execute() follow the BaseAnalysis contract."""
    analysis = PointMass3DOFBoostAnalysis()
    analysis.setup(vehicle, operating_state={"launch_angle_deg": 83.0, "altitude_m": H0_M})
    results = analysis.execute()

    assert isinstance(results, AnalysisResults)
    assert results.fidelity == FidelityLevel.LEVEL_0
    assert results["burnout_time_s"] > 0.0
    assert results["burnout_velocity_ms"] >= 0.0
    assert results["q_max_pa"] >= 0.0
    assert math.isfinite(results["burnout_mach"])


def test_point_mass_3dof_setup_defaults_operating_state_to_none(
    vehicle: BaseVehicleConfig,
) -> None:
    """setup() accepts operating_state=None and falls back to module defaults."""
    analysis = PointMass3DOFBoostAnalysis()
    analysis.setup(vehicle, operating_state=None)
    results = analysis.execute()
    assert results["burnout_time_s"] > 0.0


def test_point_mass_3dof_execute_before_setup_raises() -> None:
    """execute() before setup() raises RuntimeError per the BaseAnalysis contract."""
    analysis = PointMass3DOFBoostAnalysis()
    with pytest.raises(RuntimeError):
        analysis.execute()
