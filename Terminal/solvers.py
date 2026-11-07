"""UI-free solver catalog and execution shared by the Flight Deck and the bare CLI.

Holds the verified solver descriptors, their vehicle compatibility rules, and the
single run routine that executes a solver and saves its FlightLogs artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from YAADO_Core.ComponentStore import (
    AERO_COMPONENTS,
    BODY_COMPONENTS,
    BOOSTER_COMPONENTS,
    RAMJET_COMPONENTS,
)
from YAADO_Core.Foundation.analysis_base import (
    BaseAnalysis,
    BaseAnalysisResults,
    FidelityLevel,
)
from YAADO_Core.Foundation.constants import LHV_KEROSENE
from YAADO_Core.Foundation.flight_logger import FlightLogger
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.flight_dynamics.containers import (
    LaunchAngleSweepPoint,
    PointMassBoostResults,
)
from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
    PointMass3DOFBoostAnalysis,
    format_sweep_csv,
    plot_boost_phase,
    plot_full_flight,
    plot_launch_angle_sweep,
    run_launch_angle_sweep,
)
from YAADO_Core.modules.powerplant.cycle_methods.heiser_pratt import (
    HeiserPrattCycleAnalysis,
)

_TRUE_STRINGS = frozenset({"true", "1", "yes"})
_FALSE_STRINGS = frozenset({"false", "0", "no"})


@dataclass(frozen=True)
class SolverParam:
    """Metadata and validation rules for a tunable solver parameter.

    Attributes:
        name: Internal parameter keyword name passed to solver.setup().
        label: Human-readable form label.
        symbol: Compact aerospace symbol (e.g. γ₀, h₀, M, α).
        unit: Canonical SI unit string (e.g. deg, m, s).
        param_type: Python type (float, int, bool, str).
        default: Default value in canonical SI units. ``None`` makes the parameter
            optional: it may be left blank and the solver resolves the value.
        description: Informative parameter explanation tooltip/hint.
        min_value: Optional minimum numerical bound.
        max_value: Optional maximum numerical bound.
        placeholder: Source of the value while an optional parameter is blank.
    """

    name: str
    label: str
    symbol: str
    unit: str
    param_type: type
    default: Any
    description: str = ""
    min_value: float | None = None
    max_value: float | None = None
    placeholder: str = ""

    def parse(self, raw: str) -> Any:
        """Convert text input to this parameter's type and check its bounds.

        Args:
            raw: User-entered text value.

        Returns:
            The parsed value, or ``None`` for a blank optional parameter.

        Raises:
            ValueError: If the text does not parse or the value is out of bounds.
        """
        text = raw.strip()
        if not text and self.default is None:
            return None
        if self.param_type is bool:
            if text.lower() in _TRUE_STRINGS:
                return True
            if text.lower() in _FALSE_STRINGS:
                return False
            raise ValueError("Value must be true or false")
        if self.param_type is str:
            return text

        value: float = int(text) if self.param_type is int else float(text)
        if self.min_value is not None and value < self.min_value:
            raise ValueError(f"Value must be >= {self.min_value}")
        if self.max_value is not None and value > self.max_value:
            raise ValueError(f"Value must be <= {self.max_value}")
        return value


@dataclass(frozen=True)
class SolverDescriptor:
    """Metadata descriptor for verified physics solvers in YAADO.

    Attributes:
        solver_id: Unique string identifier for the solver method.
        name: Human-readable display name.
        discipline: Engineering discipline category.
        fidelity: Solver fidelity level (Level 0 through Level 3).
        solver_cls: Concrete solver implementation class inheriting from BaseAnalysis.
        description: Methodological and physics summary.
        required_components_desc: Required vehicle components and attributes.
        headline_outputs: Sequence of (field_name, unit_str, display_title) tuples.
        parameters: Sequence of tunable SolverParam definitions with symbols and defaults.
    """

    solver_id: str
    name: str
    discipline: str
    fidelity: FidelityLevel
    solver_cls: type[BaseAnalysis[Any]]
    description: str
    required_components_desc: str
    headline_outputs: tuple[tuple[str, str, str], ...]
    parameters: tuple[SolverParam, ...]

    @property
    def default_params(self) -> dict[str, Any]:
        """Canonical default parameters in SI units."""
        return {p.name: p.default for p in self.parameters}


@dataclass
class PipelineStage:
    """A configured solver stage in an execution pipeline.

    Attributes:
        descriptor: Metadata descriptor for the solver.
        params: Configured execution parameters in SI units.
    """

    descriptor: SolverDescriptor
    params: dict[str, Any]


@dataclass(frozen=True)
class SolverRun:
    """Outcome of a single solver execution.

    Attributes:
        results: Typed results returned by the solver.
        params: Parameters passed to solver.setup(), including auto-detected component names.
        output_dir: FlightLogs run directory, or None when logging was disabled.
    """

    results: BaseAnalysisResults
    params: dict[str, Any]
    output_dir: Path | None


REPAIRED_SOLVERS: tuple[SolverDescriptor, ...] = (
    SolverDescriptor(
        solver_id="point_mass_3dof_boost",
        name="Point-Mass 3-DOF Boost",
        discipline="FLIGHT DYNAMICS",
        fidelity=FidelityLevel.LEVEL_0,
        solver_cls=PointMass3DOFBoostAnalysis,
        description=(
            "Integrates vertical-plane point-mass equations of motion for rocket booster stage "
            "from ignition to motor burnout or ground impact under ISA atmosphere and empirical drag."
        ),
        required_components_desc="Booster motor (SolidMotor), body geometry (Fuselage diameter), positive total_mass.",
        headline_outputs=(
            ("burnout_mach", "-", "Burnout Mach"),
            ("burnout_velocity", "m/s", "Burnout Velocity"),
            ("burnout_altitude", "m", "Burnout Altitude"),
            ("apogee_altitude", "m", "Apogee Altitude"),
            ("q_max", "Pa", "Max Dynamic Pressure"),
            ("nominal_burn_time", "s", "Nominal Burn Time"),
            ("range_at_burnout", "m", "Burnout Range"),
            ("final_x", "m", "Final Range"),
            ("flight_time", "s", "Flight Time"),
        ),
        parameters=(
            SolverParam(
                name="launch_angle_deg",
                label="Launch Angle",
                symbol="γ₀",
                unit="deg",
                param_type=float,
                default=83.0,
                description="Elevation launch rail angle above horizon",
                min_value=0.0,
                max_value=90.0,
            ),
            SolverParam(
                name="altitude_m",
                label="Launch Altitude",
                symbol="h₀",
                unit="m",
                param_type=float,
                default=100.0,
                description="Initial launch pad altitude above MSL",
                min_value=0.0,
            ),
            SolverParam(
                name="ground_altitude_m",
                label="Ground Altitude",
                symbol="h_g",
                unit="m",
                param_type=float,
                default=0.0,
                description="Ground elevation for ballistic impact termination",
                min_value=0.0,
            ),
            SolverParam(
                name="t_max_s",
                label="Max Flight Time",
                symbol="t_max",
                unit="s",
                param_type=float,
                default=300.0,
                description="Maximum simulation integration duration",
                min_value=1.0,
            ),
            SolverParam(
                name="stop_at_burnout",
                label="Stop at Burnout",
                symbol="stop_burnout",
                unit="bool",
                param_type=bool,
                default=True,
                description="Terminate integration at motor burnout",
            ),
        ),
    ),
    SolverDescriptor(
        solver_id="heiser_pratt_cycle",
        name="Heiser & Pratt Ramjet Cycle",
        discipline="PROPULSION",
        fidelity=HeiserPrattCycleAnalysis.fidelity,
        solver_cls=HeiserPrattCycleAnalysis,
        description=(
            "Evaluates a 1-D two-gas ramjet station cycle at one flight condition: inlet recovery, "
            "combustor heat addition, and expansion through the finite nozzle area ratio. "
            "Loss factors are placeholders until set for the vehicle."
        ),
        required_components_desc=(
            "One ramjet (RamjetEngine) with nozzle_throat_diameter, or an air mass flow set below."
        ),
        headline_outputs=(
            ("thrust_real", "N", "Net Thrust"),
            ("thrust_ideal", "N", "Ideal Thrust"),
            ("mdot_air", "kg/s", "Air Mass Flow"),
            ("fuel_air_ratio", "-", "Fuel-Air Ratio"),
            ("capture_area", "m^2", "Required Capture Area"),
            ("mach_exit", "-", "Exit Mach"),
            ("v_exit", "m/s", "Exit Velocity"),
            ("p_exit_over_p0", "-", "Exit Pressure Ratio p_e/p0"),
            ("a_throat", "m^2", "Throat Area"),
            ("a_exit", "m^2", "Exit Area"),
        ),
        parameters=(
            SolverParam(
                name="mach",
                label="Flight Mach",
                symbol="M",
                unit="-",
                param_type=float,
                default=None,
                description="Flight Mach number (> 1). Blank uses design_mach",
                min_value=1.0,
                placeholder="design_mach",
            ),
            SolverParam(
                name="altitude_m",
                label="Flight Altitude",
                symbol="h",
                unit="m",
                param_type=float,
                default=HeiserPrattCycleAnalysis.DEFAULT_ALTITUDE_M,
                description="ISA flight altitude above MSL",
                min_value=0.0,
                max_value=80000.0,
            ),
            SolverParam(
                name="tt4",
                label="Combustor Exit Temp",
                symbol="Tt₄",
                unit="K",
                param_type=float,
                default=None,
                description="Combustor-exit total temperature. Blank uses combustor_temp",
                min_value=0.0,
                placeholder="combustor_temp",
            ),
            SolverParam(
                name="mdot_air",
                label="Air Mass Flow",
                symbol="ṁ_air",
                unit="kg/s",
                param_type=float,
                default=None,
                description="Blank derives the flow from the choked nozzle throat",
                min_value=0.0,
                placeholder="nozzle throat",
            ),
            SolverParam(
                name="eta_inlet",
                label="Inlet Recovery",
                symbol="η_i",
                unit="-",
                param_type=float,
                default=HeiserPrattCycleAnalysis.DEFAULT_ETA_INLET,
                description="Inlet total-pressure recovery pt2/pt0 (placeholder default)",
                min_value=0.0,
                max_value=1.0,
            ),
            SolverParam(
                name="pi_cc",
                label="Combustor Pressure Ratio",
                symbol="π_cc",
                unit="-",
                param_type=float,
                default=HeiserPrattCycleAnalysis.DEFAULT_PI_CC,
                description="Combustor total-pressure ratio pt4/pt2 (placeholder default)",
                min_value=0.0,
                max_value=1.0,
            ),
            SolverParam(
                name="pi_nozzle",
                label="Nozzle Pressure Ratio",
                symbol="π_n",
                unit="-",
                param_type=float,
                default=HeiserPrattCycleAnalysis.DEFAULT_PI_NOZZLE,
                description="Nozzle total-pressure ratio (placeholder default)",
                min_value=0.0,
                max_value=1.0,
            ),
            SolverParam(
                name="eta_b",
                label="Combustion Efficiency",
                symbol="η_b",
                unit="-",
                param_type=float,
                default=HeiserPrattCycleAnalysis.DEFAULT_ETA_B,
                description="Fraction of fuel energy released (placeholder default)",
                min_value=0.0,
                max_value=1.0,
            ),
            SolverParam(
                name="gamma_hot",
                label="Products Gamma",
                symbol="γ_h",
                unit="-",
                param_type=float,
                default=None,
                description=(
                    f"Blank uses {HeiserPrattCycleAnalysis.DEFAULT_GAMMA_HOT} for kerosene. "
                    "Required for other fuels"
                ),
                min_value=1.0,
                placeholder="kerosene",
            ),
            SolverParam(
                name="fuel_lhv",
                label="Fuel Heating Value",
                symbol="LHV",
                unit="J/kg",
                param_type=float,
                default=None,
                description=f"Blank uses {LHV_KEROSENE:.3g} for kerosene. Required for other fuels",
                min_value=0.0,
                placeholder="kerosene",
            ),
        ),
    ),
)


def check_solver_compatibility(
    descriptor: SolverDescriptor,
    vehicle: BaseVehicleConfig | None,
) -> tuple[bool, str]:
    """Evaluate whether the given vehicle configuration satisfies the solver's prerequisites.

    Args:
        descriptor: Solver descriptor to evaluate.
        vehicle: Currently loaded vehicle configuration, or None.

    Returns:
        Tuple of (is_compatible, status_message).
    """
    if vehicle is None:
        return False, "No active vehicle loaded in Hangar"

    if descriptor.solver_id == "point_mass_3dof_boost":
        boosters = vehicle.get_components_by_type(BOOSTER_COMPONENTS)
        if not boosters:
            return False, "Missing booster propulsion (SolidMotor / RocketMotor)"

        bodies = vehicle.get_components_by_type(BODY_COMPONENTS)
        if not bodies:
            return False, "Missing fuselage/body component"

        has_diameter = any(
            getattr(b, "diameter", None) is not None for b in bodies.values()
        )
        if not has_diameter:
            return False, "Fuselage/body component missing diameter specification"

        if vehicle.total_mass is None or vehicle.total_mass <= 0:
            return False, "Mass properties missing positive total_mass"

        booster_name = next(iter(boosters.keys()))
        body_name = next(iter(bodies.keys()))
        return True, f"Ready ({booster_name}, {body_name}, {vehicle.total_mass:.1f} kg)"

    if descriptor.solver_id == "heiser_pratt_cycle":
        ramjets = vehicle.get_components_by_type(RAMJET_COMPONENTS)
        if not ramjets:
            return False, "Missing ramjet propulsion (RamjetEngine)"
        if len(ramjets) > 1:
            return False, f"Flight Deck runs one ramjet at a time; found {sorted(ramjets)}"

        ramjet_name, ramjet = next(iter(ramjets.items()))
        if ramjet.nozzle_throat_diameter is None:
            return True, f"Ready ({ramjet_name}); no nozzle throat, so set the air mass flow"
        return True, f"Ready ({ramjet_name}, design Mach {ramjet.design_mach:g})"

    return False, "Unknown solver compatibility rule"


def resolve_fins_name(vehicle: BaseVehicleConfig) -> str | None:
    """Auto-detect appropriate aerodynamic fin surface for 3-DOF boost trajectory.

    Args:
        vehicle: Vehicle configuration.

    Returns:
        Name of aerodynamic surface to use for fin drag, or None.
    """
    candidate_fins = vehicle.get_components_by_type(AERO_COMPONENTS)
    if not candidate_fins:
        return None
    for name in candidate_fins:
        if "fin" in name.lower() or "tail" in name.lower():
            return name
    return next(iter(candidate_fins.keys()))


def execute_solver(
    descriptor: SolverDescriptor,
    vehicle: BaseVehicleConfig,
    params: dict[str, Any] | None = None,
    *,
    enable_logging: bool = True,
    run_sweep: bool = True,
) -> SolverRun:
    """Execute a solver on a vehicle and save its FlightLogs artifacts.

    Args:
        descriptor: Solver to execute.
        vehicle: Vehicle configuration to analyze.
        params: Parameter overrides, merged over ``descriptor.default_params``.
        enable_logging: Whether FlightLogger writes results, figures and artifacts to disk.
        run_sweep: Whether a logged run also computes and saves the launch angle sweep.

    Returns:
        The typed results, the parameters used, and the run directory.

    Raises:
        ValueError: If the vehicle does not satisfy the solver's prerequisites.
    """
    is_ready, msg = check_solver_compatibility(descriptor, vehicle)
    if not is_ready:
        raise ValueError(f"Cannot run {descriptor.name}: {msg}")

    exec_params = {**descriptor.default_params, **(params or {})}
    if descriptor.solver_id == "point_mass_3dof_boost":
        fins_name = resolve_fins_name(vehicle)
        if fins_name:
            exec_params["fins_name"] = fins_name

    solver = descriptor.solver_cls(descriptor.solver_id)
    solver.setup(vehicle, enable_logging=enable_logging, **exec_params)
    results = solver.execute()

    if not solver.logger.enabled:
        return SolverRun(results=results, params=exec_params, output_dir=None)

    if isinstance(results, PointMassBoostResults):
        _save_point_mass_artifacts(solver.logger, vehicle, results, exec_params, run_sweep)
    solver.logger.save_results(results)
    return SolverRun(results=results, params=exec_params, output_dir=solver.logger.output_dir)


def _save_point_mass_artifacts(
    logger: FlightLogger,
    vehicle: BaseVehicleConfig,
    results: PointMassBoostResults,
    exec_params: dict[str, Any],
    run_sweep: bool,
) -> None:
    """Save trajectory figures and, optionally, the launch angle sweep for a 3-DOF run."""
    ground_alt = exec_params.get(
        "ground_altitude_m", PointMass3DOFBoostAnalysis.DEFAULT_GROUND_ALTITUDE_M
    )
    stop_at_burnout = exec_params.get(
        "stop_at_burnout", PointMass3DOFBoostAnalysis.DEFAULT_STOP_AT_BURNOUT
    )
    if results.boost_samples is not None:
        fig_boost = plot_boost_phase(
            results.boost_samples,
            burn_time_s=results.nominal_burn_time,
            ground_altitude_m=ground_alt,
        )
        logger.save_figure(fig_boost, "boost_phase.png", show=False)
    if not stop_at_burnout and results.samples is not None:
        fig_full = plot_full_flight(
            results.samples,
            burn_time_s=results.nominal_burn_time,
            ground_altitude_m=ground_alt,
        )
        logger.save_figure(fig_full, "full_flight.png", show=False)

    if not run_sweep:
        return

    sweep_results: list[LaunchAngleSweepPoint] = run_launch_angle_sweep(
        vehicle,
        angles_deg=PointMass3DOFBoostAnalysis.DEFAULT_SWEEP_ANGLES_DEG,
        altitude_m=exec_params.get(
            "altitude_m", PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M
        ),
        ground_altitude_m=ground_alt,
        fins_name=exec_params.get("fins_name"),
        motor_name=exec_params.get("motor_name"),
        body_name=exec_params.get("body_name"),
        stop_at_burnout=stop_at_burnout,
        t_max_s=exec_params.get("t_max_s", PointMass3DOFBoostAnalysis.DEFAULT_T_MAX_S),
    )
    sweep_fig = plot_launch_angle_sweep(sweep_results, ground_altitude_m=ground_alt)
    logger.save_figure(sweep_fig, "launch_angle_sweep.png", show=False)
    logger.save_artifact("launch_angle_sweep.csv", format_sweep_csv(sweep_results))
