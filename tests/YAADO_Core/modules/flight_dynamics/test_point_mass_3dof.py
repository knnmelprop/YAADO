"""Unit tests for YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof."""

import math
from pathlib import Path

import pytest

from YAADO_Core.ComponentStore import (
    AxisymmetricBody,
    Fins,
    MassProperties,
    SolidMotor,
)
from YAADO_Core.Foundation.analysis_base import AnalysisResults, FidelityLevel
from YAADO_Core.Foundation.flight_logger import FlightLogger
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
    """Explicit kwargs override the default launch angle."""
    params = resolve_booster_params_from_vehicle(
        vehicle, launch_angle_deg=45.0
    )
    assert params.launch_angle_deg == pytest.approx(45.0)


def test_resolve_booster_params_drag_overrides(vehicle: BaseVehicleConfig) -> None:
    """Explicit kwargs override empirical drag and Isp parameters."""
    params = resolve_booster_params_from_vehicle(
        vehicle,
        cd_body_subsonic=0.15,
        cd_body_transonic=0.40,
        cd_body_supersonic=0.30,
        cd_wave_per_fin=0.02,
        isp_alt_ref_m=25000.0,
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


def test_point_mass_3dof_setup_execute_new_contract(
    vehicle: BaseVehicleConfig,
) -> None:
    """setup(vehicle, ...) + execute() follow the BaseAnalysis contract."""
    analysis = PointMass3DOFBoostAnalysis()
    analysis.setup(
        vehicle,
        launch_angle_deg=83.0,
        altitude_m=PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M,
        enable_logging=False,
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


def test_point_mass_3dof_setup_defaults(
    vehicle: BaseVehicleConfig,
) -> None:
    """setup() falls back to module defaults when called without kwargs."""
    analysis = PointMass3DOFBoostAnalysis()
    analysis.setup(vehicle, enable_logging=False)
    results = analysis.execute()
    assert results["burnout_time"] > 0.0


def test_point_mass_3dof_execute_before_setup_raises() -> None:
    """execute() before setup() raises RuntimeError per the BaseAnalysis contract."""
    analysis = PointMass3DOFBoostAnalysis()
    with pytest.raises(RuntimeError):
        analysis.execute()


def test_resolve_booster_params_explicit_names(vehicle: BaseVehicleConfig) -> None:
    """Explicit component names can be passed as kwargs."""
    params_kw = resolve_booster_params_from_vehicle(
        vehicle, motor_name="stage_1", body_name="body", fins_name="fins"
    )
    assert params_kw.propellant_mass_kg == pytest.approx(8.0)


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
    """PointMass3DOFBoostAnalysis executes successfully when component names are passed via kwargs."""
    analysis = PointMass3DOFBoostAnalysis()
    analysis.setup(
        vehicle,
        motor_name="stage_1",
        body_name="body",
        fins_name="fins",
        enable_logging=False,
    )
    results = analysis.execute()
    assert results["burnout_time"] > 0.0
    assert results["burnout_velocity"] > 0.0


def test_point_mass_3dof_setup_auto_initializes_logger(vehicle: BaseVehicleConfig) -> None:
    """setup() automatically initializes self.logger from vehicle and analysis names."""
    analysis = PointMass3DOFBoostAnalysis()
    with pytest.raises(RuntimeError, match="has not been setup yet"):
        _ = analysis.logger

    analysis.setup(vehicle, enable_logging=False)
    assert isinstance(analysis.logger, FlightLogger)
    assert analysis.logger.vehicle_name == vehicle.name
    assert analysis.logger.analysis_name == analysis.name
    assert analysis.logger.enabled is False


def test_point_mass_3dof_executes_with_enabled_logger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, vehicle: BaseVehicleConfig
) -> None:
    """Enabled FlightLogger logs execution; saving results is explicit or via study."""
    monkeypatch.chdir(tmp_path)
    analysis = PointMass3DOFBoostAnalysis()
    analysis.setup(vehicle, enable_logging=True)
    assert analysis.logger is not None
    assert analysis.logger.enabled is True
    results = analysis.execute()

    assert results["burnout_time"] > 0.0
    assert analysis.logger.log_file_path.is_file()
    log_content = analysis.logger.log_file_path.read_text(encoding="utf-8")
    assert "Starting boost trajectory integration" in log_content
    assert "Burnout reached" in log_content

    # execute() does not automatically save results to avoid redundant disk I/O in studies
    results_json = analysis.logger.output_dir / "results.json"
    summary_csv = analysis.logger.output_dir / "summary.csv"
    assert not results_json.exists()
    assert not summary_csv.exists()

    # Explicit save_results produces the checkpoint
    analysis.logger.save_results(results)
    assert results_json.is_file()
    assert summary_csv.is_file()

    analysis.logger.close()


def test_point_mass_3dof_executes_with_disabled_logger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, vehicle: BaseVehicleConfig
) -> None:
    """Disabled FlightLogger performs zero disk I/O."""
    monkeypatch.chdir(tmp_path)
    analysis = PointMass3DOFBoostAnalysis()
    analysis.setup(vehicle, enable_logging=False)
    results = analysis.execute()

    assert results["burnout_time"] > 0.0
    assert analysis.logger is not None
    assert not analysis.logger.output_dir.exists()


def test_run_boost_study_with_flight_logger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, vehicle: BaseVehicleConfig
) -> None:
    """run_boost_study runs end-to-end generating figures, artifacts, and checkpoints."""
    from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
        run_boost_study,
    )

    monkeypatch.chdir(tmp_path)
    results = run_boost_study(vehicle, enable_logging=True)
    assert isinstance(results, AnalysisResults)
    assert results["burnout_time"] > 0.0
    run_dir = next((tmp_path / "FlightLogs" / vehicle.name).glob("point_mass_3dof_boost_*"))
    assert (run_dir / "execution.log").is_file()
    assert (run_dir / "results.json").is_file()
    assert (run_dir / "summary.csv").is_file()
    assert (run_dir / "figures" / "boost_phase.png").is_file()
    assert (run_dir / "figures" / "launch_angle_sweep.png").is_file()
    assert (run_dir / "artifacts" / "launch_angle_sweep.csv").is_file()


def test_run_boost_study_rejects_path_input(
    tmp_path: Path, vehicle: BaseVehicleConfig
) -> None:
    """run_boost_study strictly requires a BaseVehicleConfig instance, not a path."""
    from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
        run_boost_study,
    )

    config_file = tmp_path / "test_vehicle.toml"
    vehicle.to_toml(config_file)

    with pytest.raises(TypeError, match="BaseVehicleConfig"):
        run_boost_study(config_file, enable_logging=False)  # type: ignore[arg-type]


def test_point_mass_3dof_full_flight_simulation(
    vehicle: BaseVehicleConfig,
) -> None:
    """stop_at_burnout=False simulates full trajectory past burnout to ground impact."""
    analysis = PointMass3DOFBoostAnalysis(stop_at_burnout=False)
    analysis.setup(vehicle, enable_logging=False)
    results = analysis.execute()

    assert isinstance(results, AnalysisResults)
    # Burnout metrics are still present and positive
    assert results["burnout_time"] == pytest.approx(4.0)
    assert results["burnout_velocity"] > 0.0
    assert results["burnout_altitude"] > 0.0
    # Full flight metrics are computed
    assert results["apogee_altitude"] > results["burnout_altitude"]
    assert results["apogee_time"] > results["burnout_time"]
    assert results["flight_time"] > results["apogee_time"]
    assert results["flight_range"] > results["range_at_burnout"]
    assert results["impact_velocity"] > 0.0
    assert results.units["apogee_altitude"] == "m"
    assert results.units["flight_time"] == "s"
    assert results.units["flight_range"] == "m"
    assert results.metadata["stop_at_burnout"] is False
    assert results.metadata["integration_stopped_reason"] == "ground_impact"


def test_point_mass_3dof_full_flight_via_setup_override(
    vehicle: BaseVehicleConfig,
) -> None:
    """Explicit stop_at_burnout=False on setup() activates full flight."""
    analysis = PointMass3DOFBoostAnalysis()
    analysis.setup(vehicle, stop_at_burnout=False, enable_logging=False)
    results = analysis.execute()
    assert results["flight_time"] > results["burnout_time"]
    assert results["apogee_altitude"] > results["burnout_altitude"]


def test_run_boost_study_full_flight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, vehicle: BaseVehicleConfig
) -> None:
    """run_boost_study with stop_at_burnout=False generates full_flight.png and full metrics."""
    from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
        run_boost_study,
    )

    monkeypatch.chdir(tmp_path)
    results = run_boost_study(vehicle, stop_at_burnout=False, enable_logging=True)
    assert isinstance(results, AnalysisResults)
    assert results["flight_time"] > results["burnout_time"]
    assert results["apogee_altitude"] > results["burnout_altitude"]

    run_dir = next((tmp_path / "FlightLogs" / vehicle.name).glob("point_mass_3dof_boost_*"))
    boost_png = run_dir / "figures" / "boost_phase.png"
    full_png = run_dir / "figures" / "full_flight.png"
    sweep_png = run_dir / "figures" / "launch_angle_sweep.png"
    sweep_csv = run_dir / "artifacts" / "launch_angle_sweep.csv"

    assert boost_png.is_file()
    assert full_png.is_file()
    assert sweep_png.is_file()
    assert sweep_csv.is_file()

    # Crucial check: boost_phase.png and full_flight.png must not be identical
    assert boost_png.read_bytes() != full_png.read_bytes()

    # Metadata should contain both _boost_samples (0-4s) and _samples (0-flight_time)
    assert "_boost_samples" in results.metadata
    assert "_samples" in results.metadata
    assert results.metadata["_boost_samples"]["t_s"][-1] == pytest.approx(4.0)
    assert results.metadata["_samples"]["t_s"][-1] > 4.0


def test_plot_boost_phase_and_full_flight() -> None:
    """plot_boost_phase slices full samples and plot_full_flight plots full trajectory."""
    from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
        plot_boost_phase,
        plot_full_flight,
    )
    import matplotlib.pyplot as plt

    samples = {
        "t_s": [0.0, 2.0, 4.0, 6.0, 8.0, 10.0],
        "x_m": [0.0, 100.0, 300.0, 600.0, 800.0, 900.0],
        "h_m": [0.0, 200.0, 600.0, 900.0, 800.0, 0.0],
        "v_ms": [0.0, 100.0, 250.0, 200.0, 100.0, 80.0],
        "mach": [0.0, 0.3, 0.8, 0.6, 0.3, 0.2],
        "q_pa": [0.0, 5000.0, 25000.0, 15000.0, 4000.0, 2000.0],
        "burn_time_s": 4.0,
    }

    fig_boost = plot_boost_phase(samples, burn_time_s=4.0)
    assert fig_boost is not None
    # X-limits on boost figure should end around 4.0 s
    ax_speed = fig_boost.axes[0]
    assert ax_speed.get_lines()[0].get_xdata()[-1] == pytest.approx(4.0)
    plt.close(fig_boost)

    fig_full = plot_full_flight(samples, burn_time_s=4.0)
    assert fig_full is not None
    ax_full_speed = fig_full.axes[0]
    assert ax_full_speed.get_lines()[0].get_xdata()[-1] == pytest.approx(10.0)
    plt.close(fig_full)


def test_resolve_booster_params_preserves_ground_altitude(
    vehicle: BaseVehicleConfig,
) -> None:
    """resolve_booster_params_from_vehicle correctly propagates ground_altitude_m."""
    params_default = resolve_booster_params_from_vehicle(vehicle)
    assert (
        params_default.ground_altitude_m
        == PointMass3DOFBoostAnalysis.DEFAULT_GROUND_ALTITUDE_M
    )

    params_custom = resolve_booster_params_from_vehicle(
        vehicle, ground_altitude_m=250.0
    )
    assert params_custom.ground_altitude_m == 250.0

    params_arg = resolve_booster_params_from_vehicle(
        vehicle, ground_altitude_m=500.0
    )
    assert params_arg.ground_altitude_m == 500.0


def test_booster_params_derived_properties_and_initial_altitude(
    vehicle: BaseVehicleConfig,
) -> None:
    """BoosterParams computes burnout_mass_kg and mdot_kg_s dynamically, and carries initial_altitude_m."""
    params = resolve_booster_params_from_vehicle(
        vehicle, altitude_m=1200.0
    )
    assert params.initial_altitude_m == pytest.approx(1200.0)
    assert params.burnout_mass_kg == pytest.approx(params.launch_mass_kg - params.propellant_mass_kg)
    assert params.mdot_kg_s == pytest.approx(params.propellant_mass_kg / params.burn_time_s)
    # Ensure launch_angle_rad is not a field
    assert not hasattr(params, "launch_angle_rad")


def test_sweep_results_standardized_q_max(
    vehicle: BaseVehicleConfig,
) -> None:
    """run_launch_angle_sweep uses standardized q_max and does not emit max_q."""
    from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
        run_launch_angle_sweep,
    )

    sweep = run_launch_angle_sweep(vehicle, angles_deg=[80.0, 85.0])
    for entry in sweep:
        assert "q_max" in entry
        assert "max_q" not in entry
        assert entry["q_max"] > 0.0


def test_validate_results_supports_below_sea_level(
    vehicle: BaseVehicleConfig,
) -> None:
    """validate_results accepts flight where ground altitude is below sea level."""
    analysis = PointMass3DOFBoostAnalysis()
    analysis.setup(
        vehicle,
        altitude_m=-350.0,
        ground_altitude_m=-400.0,
        launch_angle_deg=85.0,
        enable_logging=False,
    )
    results = analysis.execute()
    assert results["burnout_altitude"] > -400.0
    assert analysis.validate_results(results) is True


def test_plots_clip_y_axis_to_zero_and_ground() -> None:
    """Plotting functions clip velocity, mach, and q to 0.0, and altitude to ground."""
    from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
        plot_boost_phase,
        plot_full_flight,
        plot_launch_angle_sweep,
    )
    import matplotlib.pyplot as plt

    samples = {
        "t_s": [0.0, 2.0, 4.0],
        "x_m": [0.0, 100.0, 300.0],
        "h_m": [100.0, 200.0, 400.0],
        "v_ms": [0.0, 150.0, 300.0],
        "mach": [0.0, 0.45, 0.9],
        "q_pa": [0.0, 12000.0, 35000.0],
        "ground_altitude_m": 50.0,
        "burn_time_s": 4.0,
    }

    fig_boost = plot_boost_phase(samples)
    assert fig_boost.axes[0].get_ylim()[0] == pytest.approx(0.0)  # speed
    assert fig_boost.axes[1].get_ylim()[0] == pytest.approx(50.0)  # altitude bottom at ground
    assert fig_boost.axes[2].get_ylim()[0] == pytest.approx(0.0)  # mach
    assert fig_boost.axes[3].get_ylim()[0] == pytest.approx(0.0)  # dynamic pressure
    plt.close(fig_boost)

    fig_full = plot_full_flight(samples)
    assert fig_full.axes[0].get_ylim()[0] == pytest.approx(0.0)
    assert fig_full.axes[1].get_ylim()[0] == pytest.approx(50.0)
    assert fig_full.axes[2].get_ylim()[0] == pytest.approx(0.0)
    assert fig_full.axes[3].get_ylim()[0] == pytest.approx(0.0)
    plt.close(fig_full)

    sweep_results = [
        {"launch_angle_deg": 10.0, "burnout_mach": 1.2, "burnout_altitude": 200.0, "q_max": 20000.0},
        {"launch_angle_deg": 20.0, "burnout_mach": 1.3, "burnout_altitude": 400.0, "q_max": 22000.0},
    ]
    fig_sweep = plot_launch_angle_sweep(sweep_results, ground_altitude_m=0.0)
    assert len(fig_sweep.axes) == 2
    assert fig_sweep.axes[1].get_ylim()[0] == pytest.approx(0.0)  # burnout altitude
    plt.close(fig_sweep)

    sweep_results_full = [
        {
            "launch_angle_deg": 10.0,
            "burnout_mach": 1.2,
            "burnout_altitude": 200.0,
            "apogee_altitude": 5000.0,
            "q_max": 20000.0,
        },
        {
            "launch_angle_deg": 20.0,
            "burnout_mach": 1.3,
            "burnout_altitude": 400.0,
            "apogee_altitude": 8000.0,
            "q_max": 22000.0,
        },
    ]
    fig_sweep_full = plot_launch_angle_sweep(sweep_results_full, ground_altitude_m=0.0)
    assert len(fig_sweep_full.axes) == 3
    assert fig_sweep_full.axes[1].get_ylim()[0] == pytest.approx(0.0)  # burnout altitude
    assert fig_sweep_full.axes[2].get_ylim()[0] == pytest.approx(0.0)  # apogee altitude
    plt.close(fig_sweep_full)


def test_run_boost_study_with_explicit_kwargs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, vehicle: BaseVehicleConfig
) -> None:
    """run_boost_study runs end-to-end with explicit kwargs (no operating_state dict)."""
    from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
        run_boost_study,
    )

    monkeypatch.chdir(tmp_path)
    results = run_boost_study(
        vehicle,
        launch_angle_deg=80.0,
        altitude_m=100.0,
        stop_at_burnout=False,
        enable_logging=False,
    )
    assert isinstance(results, AnalysisResults)
    assert results["burnout_time"] > 0.0
    assert results.metadata["initial_altitude"] == pytest.approx(100.0)
    assert results.metadata["launch_angle"] == pytest.approx(80.0)
    assert "apogee_altitude" in results







