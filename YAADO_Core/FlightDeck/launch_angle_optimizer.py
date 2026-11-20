"""Launch angle for maximum range, found with OpenMDAO.

This is the first OpenMDAO loop in ``FlightDeck``. It follows the "hidden OpenMDAO"
rule of the FlightDeck README: the caller passes a vehicle and gets a typed result, and
never builds an ``openmdao.api.Problem`` themselves.

The simulation has no analytic derivatives, so the driver is SLSQP with finite
differences (step ``fd_step_deg``, default 0.5 deg). SLSQP needs far fewer simulations
than a gradient-free method such as COBYLA for one smooth design variable, and the range
is smooth in the launch angle: the ODE is integrated with tight tolerances, so a 0.5 deg
step is well above the numerical noise.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import openmdao.api as om

from YAADO_Core.Foundation.units import Degrees, Meters
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
    BoosterParams,
    PointMass3DOFBoostAnalysis,
    derive_trajectory_metrics,
    integrate_boost_phase,
    resolve_booster_params_from_vehicle,
)

DEFAULT_ANGLE_BOUNDS_DEG: tuple[float, float] = (5.0, 85.0)
DEFAULT_INITIAL_ANGLE_DEG: float = 45.0
DEFAULT_FD_STEP_DEG: float = 0.5
DEFAULT_TOLERANCE: float = 1e-6
DEFAULT_MAX_ITERATIONS: int = 50
RANGE_SCALER: float = 1.0e-4
"""Scales the range [m] to order 1 for the optimizer (the sign is set by the maximization)."""


@dataclass(frozen=True)
class LaunchAngleOptimum:
    """Result of the launch-angle optimization.

    Attributes:
        launch_angle_deg: Launch angle that gives the maximum range [deg].
        flight_range: Maximum ground range at that angle [m].
        n_simulations: Number of 3-DOF simulations run, finite-difference ones included.
    """

    launch_angle_deg: Degrees
    flight_range: Meters
    n_simulations: int


class LaunchAngleRangeComponent(om.ExplicitComponent):  # type: ignore[misc]
    """OpenMDAO component: launch angle in, full-flight ground range out.

    Runs the same integration as :class:`PointMass3DOFBoostAnalysis` with
    ``stop_at_burnout=False``. The partial derivative is a finite difference.
    """

    def initialize(self) -> None:
        """Declare the options: the resolved booster parameters and the FD step."""
        self.options.declare("params", types=BoosterParams)
        self.options.declare("fd_step_deg", types=float, default=DEFAULT_FD_STEP_DEG)
        self.n_simulations: int = 0

    def setup(self) -> None:
        """Declare the input, the output and the finite-difference partial."""
        self.add_input("launch_angle_deg", val=DEFAULT_INITIAL_ANGLE_DEG)
        self.add_output("flight_range", val=0.0)
        self.declare_partials(
            "flight_range",
            "launch_angle_deg",
            method="fd",
            step=self.options["fd_step_deg"],
        )

    def compute(self, inputs: Any, outputs: Any) -> None:
        """Simulate the flight at the given launch angle and return its range."""
        params = replace(
            self.options["params"],
            launch_angle_deg=float(inputs["launch_angle_deg"][0]),
        )
        solution = integrate_boost_phase(params)
        metrics, _, _ = derive_trajectory_metrics(solution, params)
        outputs["flight_range"] = metrics.final_x
        self.n_simulations += 1


def optimize_launch_angle(
    vehicle: BaseVehicleConfig,
    *,
    bounds_deg: tuple[float, float] = DEFAULT_ANGLE_BOUNDS_DEG,
    initial_angle_deg: float = DEFAULT_INITIAL_ANGLE_DEG,
    altitude_m: float = PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M,
    ground_altitude_m: float = PointMass3DOFBoostAnalysis.DEFAULT_GROUND_ALTITUDE_M,
    fins_name: str | None = None,
    motor_name: str | None = None,
    body_name: str | None = None,
    t_max_s: float = PointMass3DOFBoostAnalysis.DEFAULT_T_MAX_S,
    fd_step_deg: float = DEFAULT_FD_STEP_DEG,
    tolerance: float = DEFAULT_TOLERANCE,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> LaunchAngleOptimum:
    """Find the launch angle that maximizes the ground range of the 3-DOF flight.

    Args:
        vehicle: Validated vehicle configuration.
        bounds_deg: Lower and upper bound of the launch angle [deg].
        initial_angle_deg: Starting angle for the optimizer [deg], inside the bounds.
        altitude_m: Launch altitude [m].
        ground_altitude_m: Ground plane altitude [m].
        fins_name: Optional fin set name, as for the 3-DOF analysis.
        motor_name: Optional motor name.
        body_name: Optional body name.
        t_max_s: Maximum flight duration [s].
        fd_step_deg: Finite-difference step of the gradient [deg].
        tolerance: SLSQP convergence tolerance (on the scaled range).
        max_iterations: Maximum number of SLSQP iterations.

    Returns:
        The optimal angle, the maximum range and the number of simulations run.

    Raises:
        TypeError: If ``vehicle`` is not a :class:`BaseVehicleConfig`.
        ValueError: If the bounds are not ordered or the initial angle is outside them.
        RuntimeError: If the optimizer fails.
    """
    if not isinstance(vehicle, BaseVehicleConfig):
        raise TypeError(
            f"vehicle must be a BaseVehicleConfig, got {type(vehicle).__name__}"
        )
    lower, upper = bounds_deg
    if not 0.0 <= lower < upper <= 90.0:
        raise ValueError("bounds_deg must satisfy 0 <= lower < upper <= 90.")
    if not lower <= initial_angle_deg <= upper:
        raise ValueError("initial_angle_deg must lie inside bounds_deg.")

    params = resolve_booster_params_from_vehicle(
        vehicle,
        launch_angle_deg=initial_angle_deg,
        altitude_m=altitude_m,
        ground_altitude_m=ground_altitude_m,
        fins_name=fins_name,
        motor_name=motor_name,
        body_name=body_name,
        stop_at_burnout=False,
        t_max_s=t_max_s,
    )

    component = LaunchAngleRangeComponent(params=params, fd_step_deg=fd_step_deg)
    problem = om.Problem(reports=False)
    problem.model.add_subsystem("range", component, promotes=["*"])
    problem.model.add_design_var("launch_angle_deg", lower=lower, upper=upper)
    problem.model.add_objective("flight_range", scaler=-RANGE_SCALER)
    problem.driver = om.ScipyOptimizeDriver(
        optimizer="SLSQP",
        tol=tolerance,
        maxiter=max_iterations,
        disp=False,
    )
    problem.setup(check=False)
    problem.set_val("launch_angle_deg", initial_angle_deg)
    driver_result = problem.run_driver()
    if not driver_result.success:
        raise RuntimeError("Launch angle optimization did not converge.")

    return LaunchAngleOptimum(
        launch_angle_deg=float(np.squeeze(problem.get_val("launch_angle_deg"))),
        flight_range=float(np.squeeze(problem.get_val("flight_range"))),
        n_simulations=component.n_simulations,
    )
