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
    PointMass3DOFBoostAnalysis,
    resolve_booster_params_from_vehicle,
)


def _build_generic_solid_rocket() -> BaseVehicleConfig:
    """Build a minimal, generic, schema-valid solid-rocket vehicle config.

    Uses realistic small sounding-rocket values (consistent Isp/mdot/thrust,
    slender body, cruciform fins) so all cross-field validators pass.
    """
    motor = SolidMotor(
        isp_sl=180.0,
        isp_vacuum=210.0,
        propellant_mass=8.0,
        burn_time=4.0,
        thrust_mean=180.0 * (8.0 / 4.0) * 9.80665,
        thrust_peak=180.0 * (8.0 / 4.0) * 9.80665 * 1.2,
        propellant_density=1750.0,
    )
    body = AxisymmetricBody(
        length=2.0,
        diameter=0.15,
        nose_length=0.4,
        nose_diameter=0.15,
        total_length=2.0,
    )
    fins = Fins(
        count=4,
        span=0.08,
        sweep=30.0,
        chord_root=0.15,
        chord_tip=0.05,
    )
    mass = MassProperties(cg_from_nose=1.2, total_mass=20.0)

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
    assert params.launch_angle_deg == pytest.approx(
        PointMass3DOFBoostAnalysis.DEFAULT_LAUNCH_ANGLE_DEG
    )
    assert params.a_ref_m2 == pytest.approx(math.pi / 4.0 * 0.15**2)


def test_resolve_booster_params_launch_angle_override(vehicle: BaseVehicleConfig) -> None:
    """operating_state overrides the default launch angle."""
    params = resolve_booster_params_from_vehicle(
        vehicle, operating_state={"launch_angle_deg": 45.0}
    )
    assert params.launch_angle_deg == pytest.approx(45.0)
    assert params.launch_angle_rad == pytest.approx(math.radians(45.0))


def test_resolve_booster_params_drag_overrides(vehicle: BaseVehicleConfig) -> None:
    """operating_state overrides empirical drag and Isp parameters."""
    params = resolve_booster_params_from_vehicle(
        vehicle,
        operating_state={
            "cd_body_subsonic": 0.15,
            "cd_body_transonic": 0.40,
            "cd_body_supersonic": 0.30,
            "cd_wave_per_fin": 0.02,
            "isp_alt_ref_m": 25000.0,
        },
    )
    assert params.cd_body_subsonic == pytest.approx(0.15)
    assert params.cd_body_transonic == pytest.approx(0.40)
    assert params.cd_body_supersonic == pytest.approx(0.30)
    # Fins count is 4, so 4 * 0.02 = 0.08
    assert params.cd_fins == pytest.approx(0.08)
    assert params.isp_alt_ref_m == pytest.approx(25000.0)


def test_resolve_booster_params_requires_mass_properties() -> None:
    """A vehicle missing mass_properties raises ValueError."""
    vehicle = _build_generic_solid_rocket()
    vehicle.mass_properties = None
    with pytest.raises(ValueError):
        resolve_booster_params_from_vehicle(vehicle)


def test_point_mass_3dof_setup_execute_new_contract(vehicle: BaseVehicleConfig) -> None:
    """setup(vehicle, operating_state) + execute() follow the BaseAnalysis contract."""
    analysis = PointMass3DOFBoostAnalysis()
    analysis.setup(
        vehicle,
        operating_state={
            "launch_angle_deg": 83.0,
            "altitude_m": PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M,
        },
    )
    results = analysis.execute()

    assert isinstance(results, AnalysisResults)
    assert results.fidelity == FidelityLevel.LEVEL_0
    assert results.units == {
        "burnout_time": "s",
        "burnout_velocity": "m/s",
        "burnout_mach": "-",
        "burnout_altitude": "m",
        "q_max": "Pa",
        "range_at_burnout": "m",
    }
    assert results["burnout_time"] > 0.0
    assert results["burnout_velocity"] >= 0.0
    assert results["burnout_altitude"] >= 0.0
    assert results["range_at_burnout"] >= 0.0
    assert results["q_max"] >= 0.0
    assert math.isfinite(results["burnout_mach"])


def test_point_mass_3dof_setup_defaults_operating_state_to_none(
    vehicle: BaseVehicleConfig,
) -> None:
    """setup() accepts operating_state=None and falls back to module defaults."""
    analysis = PointMass3DOFBoostAnalysis()
    analysis.setup(vehicle, operating_state=None)
    results = analysis.execute()
    assert results["burnout_time"] > 0.0


def test_point_mass_3dof_execute_before_setup_raises() -> None:
    """execute() before setup() raises RuntimeError per the BaseAnalysis contract."""
    analysis = PointMass3DOFBoostAnalysis()
    with pytest.raises(RuntimeError):
        analysis.execute()


def test_resolve_booster_params_explicit_names(vehicle: BaseVehicleConfig) -> None:
    """Explicit component names can be passed as kwargs or via operating_state."""
    # Via kwargs
    params_kw = resolve_booster_params_from_vehicle(
        vehicle, motor_name="stage_1", body_name="body", fins_name="fins"
    )
    assert params_kw.propellant_mass_kg == pytest.approx(8.0)

    # Via operating_state
    params_st = resolve_booster_params_from_vehicle(
        vehicle,
        operating_state={
            "motor_name": "stage_1",
            "body_name": "body",
            "fins_name": "fins",
        },
    )
    assert params_st.propellant_mass_kg == pytest.approx(8.0)


def test_resolve_booster_params_multiple_motors_requires_name(
    vehicle: BaseVehicleConfig,
) -> None:
    """Multiple booster motors raise ValueError unless motor_name is explicitly specified."""
    vehicle.propulsion["stage_2"] = SolidMotor(
        isp_sl=200.0,
        isp_vacuum=230.0,
        propellant_mass=3.0,
        burn_time=2.0,
        thrust_mean=200.0 * 1.5 * 9.80665,
        thrust_peak=200.0 * 1.5 * 9.80665 * 1.2,
        propellant_density=1750.0,
    )

    with pytest.raises(ValueError, match="Multiple booster components found"):
        resolve_booster_params_from_vehicle(vehicle)

    params = resolve_booster_params_from_vehicle(vehicle, motor_name="stage_2")
    assert params.propellant_mass_kg == pytest.approx(3.0)
    assert params.burn_time_s == pytest.approx(2.0)


def test_resolve_booster_params_multiple_fins_requires_name(
    vehicle: BaseVehicleConfig,
) -> None:
    """Multiple aero surfaces raise ValueError unless fins_name is specified."""
    vehicle.aero_surfaces["canards"] = Fins(
        count=4, span=0.04, sweep=20.0, chord_root=0.08, chord_tip=0.03
    )

    with pytest.raises(ValueError, match="Multiple aero surfaces found"):
        resolve_booster_params_from_vehicle(vehicle)

    params = resolve_booster_params_from_vehicle(vehicle, fins_name="canards")
    # count=4 with default CD_WAVE_PER_FIN (0.012) -> 0.048
    assert params.cd_fins == pytest.approx(
        4 * PointMass3DOFBoostAnalysis.CD_WAVE_PER_FIN
    )


def test_resolve_booster_params_nonexistent_name_raises(
    vehicle: BaseVehicleConfig,
) -> None:
    """Requesting a non-existent component name raises ValueError."""
    with pytest.raises(ValueError, match="Specified motor 'missing_stage' not found"):
        resolve_booster_params_from_vehicle(vehicle, motor_name="missing_stage")

    with pytest.raises(ValueError, match="Specified fin set 'missing_fins' not found"):
        resolve_booster_params_from_vehicle(vehicle, fins_name="missing_fins")

    with pytest.raises(ValueError, match="Specified body 'missing_body' not found"):
        resolve_booster_params_from_vehicle(vehicle, body_name="missing_body")


def test_resolve_booster_params_wrong_type_raises(
    vehicle: BaseVehicleConfig,
) -> None:
    """Targeting a component outside the registered component tuples raises TypeError."""
    vehicle.propulsion["invalid_motor"] = object()
    with pytest.raises(TypeError, match="expected a registered propulsion component"):
        resolve_booster_params_from_vehicle(vehicle, motor_name="invalid_motor")

    vehicle.bodies["invalid_body"] = object()
    with pytest.raises(TypeError, match="expected a registered body component"):
        resolve_booster_params_from_vehicle(vehicle, body_name="invalid_body")

    vehicle.aero_surfaces["invalid_surface"] = object()
    with pytest.raises(TypeError, match="expected a registered aero surface component"):
        resolve_booster_params_from_vehicle(vehicle, fins_name="invalid_surface")


def test_resolve_booster_params_finless_vehicle(vehicle: BaseVehicleConfig) -> None:
    """Finless vehicles resolve with cd_fins = 0.0 without error."""
    vehicle.aero_surfaces.clear()
    params = resolve_booster_params_from_vehicle(vehicle)
    assert params.cd_fins == pytest.approx(0.0)


def test_resolve_booster_params_multi_propulsion_auto_selects_booster(
    vehicle: BaseVehicleConfig,
) -> None:
    """Auto-discovery resolves the booster even when non-booster propulsion (e.g. Ramjet) is present."""
    from YAADO_Core.ComponentStore import RamjetEngine

    vehicle.propulsion["sustainer"] = RamjetEngine(
        design_mach=2.6,
        fuel_type="kerosene",
        combustor_temp=2150.0,
        nozzle_area_ratio=2.25,
    )
    # Auto-discovery should ignore the ramjet because it has no burn_time/propellant_mass
    params = resolve_booster_params_from_vehicle(vehicle)
    assert params.propellant_mass_kg == pytest.approx(8.0)

    # Explicitly requesting the non-booster raises ValueError
    with pytest.raises(ValueError, match="does not provide 'burn_time' and 'propellant_mass'"):
        resolve_booster_params_from_vehicle(vehicle, motor_name="sustainer")


def test_point_mass_3dof_setup_with_named_components(
    vehicle: BaseVehicleConfig,
) -> None:
    """PointMass3DOFBoostAnalysis executes successfully when component names are passed via operating_state."""
    analysis = PointMass3DOFBoostAnalysis()
    analysis.setup(
        vehicle,
        operating_state={
            "motor_name": "stage_1",
            "body_name": "body",
            "fins_name": "fins",
        },
    )
    results = analysis.execute()
    assert results["burnout_time"] > 0.0
    assert results["burnout_velocity"] > 0.0

