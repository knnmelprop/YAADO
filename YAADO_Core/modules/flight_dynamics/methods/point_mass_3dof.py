"""Low-order 3-DOF boost-phase trajectory point-mass integrator.

This module integrates a point-mass, vertical-plane (3-DOF: range, altitude,
and their rates) equation of motion for the solid-propellant booster stage
of a rocket vehicle, from ignition to nominal burnout
(``burn_time`` from the vehicle config) or ground impact, whichever comes
first.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from matplotlib.figure import Figure

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import OptimizeResult

import YAADO_Core.Foundation.constants as const
from YAADO_Core.ComponentStore import (
    AERO_COMPONENTS,
    BODY_COMPONENTS,
    PROPULSION_COMPONENTS,
    AnyAeroComponent,
    AnyBodyComponent,
    AnyPropulsionComponent,
)
from YAADO_Core.Foundation.analysis_base import (
    AnalysisResults,
    BaseAnalysis,
    FidelityLevel,
)
from YAADO_Core.Foundation.atmosphere import isa_atmosphere
from YAADO_Core.Foundation.flight_logger import FlightLogger
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig


class PointMass3DOFBoostAnalysis(BaseAnalysis):
    """3-DOF point-mass boost-phase trajectory analysis.

    Wraps the ISA atmosphere, drag build-up and boost-phase
    ODE integration as a :class:`BaseAnalysis`. Point-mass analytical
    integration with empirical drag/Isp correlations ->
    ``FidelityLevel.LEVEL_0``.

    Example:
        analysis = PointMass3DOFBoostAnalysis()
        analysis.setup(vehicle)
        results = analysis.execute()
        burnout_mach = results["burnout_mach"]
    """

    fidelity = FidelityLevel.LEVEL_0

    # Default launch conditions
    DEFAULT_LAUNCH_ANGLE_DEG: float = 83.0
    DEFAULT_ALTITUDE_M: float = 100.0
    DEFAULT_X0_M: float = 0.0
    DEFAULT_V0_MS: float = 0.0
    DEFAULT_GROUND_ALTITUDE_M: float = 0.0

    # Empirical drag parameters (can be calibrated per vehicle via kwargs)
    CD_BODY_SUBSONIC: float = 0.20
    CD_BODY_TRANSONIC: float = 0.35
    CD_BODY_SUPERSONIC: float = 0.25
    MACH_TRANSONIC_LO: float = 0.8
    MACH_SUPERSONIC_LO: float = 1.5
    CD_WAVE_PER_FIN: float = 0.012
    DEFAULT_AERO_SURFACE_COUNT: int = 2

    # Propulsion & numerical solver settings
    ISP_ALT_REF_M: float = 30000.0
    RTOL: float = 1e-8
    ATOL: float = 1e-10
    N_DENSE_SAMPLES: int = 4001
    VELOCITY_EPS_MS: float = 1e-6
    DEFAULT_SWEEP_ANGLES_DEG: tuple[float, ...] = (
        60.0,
        70.0,
        75.0,
        80.0,
        83.0,
        85.0,
        88.0,
    )

    DEFAULT_STOP_AT_BURNOUT: bool = True
    DEFAULT_T_MAX_S: float = 300.0
    IGNITION_PAD_CLEAR_TIME_S: float = 0.5
    IGNITION_PAD_CLEAR_ALTITUDE_MARGIN_M: float = 1.0

    def __init__(
        self,
        name: str = "point_mass_3dof_boost",
    ) -> None:
        super().__init__(name)
        self._stop_at_burnout: bool = self.DEFAULT_STOP_AT_BURNOUT
        self._params: BoosterParams | None = None

    def setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        launch_angle_deg: float = DEFAULT_LAUNCH_ANGLE_DEG,
        altitude_m: float = DEFAULT_ALTITUDE_M,
        ground_altitude_m: float = DEFAULT_GROUND_ALTITUDE_M,
        fins_name: str | None = None,
        motor_name: str | None = None,
        body_name: str | None = None,
        t_max_s: float = DEFAULT_T_MAX_S,
        stop_at_burnout: bool = DEFAULT_STOP_AT_BURNOUT,
        enable_logging: bool = True,
        cd_body_subsonic: float = CD_BODY_SUBSONIC,
        cd_body_transonic: float = CD_BODY_TRANSONIC,
        cd_body_supersonic: float = CD_BODY_SUPERSONIC,
        mach_transonic_lo: float = MACH_TRANSONIC_LO,
        mach_supersonic_lo: float = MACH_SUPERSONIC_LO,
        cd_wave_per_fin: float = CD_WAVE_PER_FIN,
        isp_alt_ref_m: float = ISP_ALT_REF_M,
        **kwargs: Any,
    ) -> None:
        """Bind the analysis to a vehicle config and operating conditions.

        Mass, propulsion (``SolidMotor``) and geometry (``AxisymmetricBody``
        body diameter, ``Fins`` count) are read from ``vehicle``. The fixed
        launch angle and initial altitude are launch-site conditions configured
        directly via keyword arguments (see :func:`resolve_booster_params_from_vehicle`).
        A :class:`~YAADO_Core.Foundation.flight_logger.FlightLogger` is automatically
        initialized from the vehicle name and analysis name.

        Args:
            vehicle: Validated, vehicle-agnostic configuration providing
                the propulsion, body, aero_surfaces (fins) and
                mass_properties components used by the boost-phase model.
            launch_angle_deg: Launch elevation angle above horizontal [deg].
                Defaults to :attr:`DEFAULT_LAUNCH_ANGLE_DEG`.
            altitude_m: Initial launch altitude [m]. Defaults to :attr:`DEFAULT_ALTITUDE_M`.
            ground_altitude_m: Ground impact plane altitude [m]. Defaults to :attr:`DEFAULT_GROUND_ALTITUDE_M`.
            fins_name: Explicit name of fin set in ``vehicle.aero_surfaces``.
            motor_name: Explicit name of motor in ``vehicle.propulsion``.
            body_name: Explicit name of body in ``vehicle.bodies``.
            t_max_s: Maximum flight duration [s]. Defaults to :attr:`DEFAULT_T_MAX_S`.
            stop_at_burnout: Optional explicit override for whether the simulation
                terminates at booster depletion (True) or continues through
                unpowered coast to ground impact/apogee (False).
            enable_logging: Whether FlightLogger creates disk artifacts and logs.
                Set to False for zero-disk-I/O in high-speed sweeps and tests.
            cd_body_subsonic: Subsonic body drag coefficient.
            cd_body_transonic: Transonic body drag coefficient.
            cd_body_supersonic: Supersonic body drag coefficient.
            mach_transonic_lo: Lower Mach boundary for transonic regime.
            mach_supersonic_lo: Lower Mach boundary for supersonic regime.
            cd_wave_per_fin: Wave drag coefficient contribution per fin.
            isp_alt_ref_m: Reference altitude [m] for Isp vacuum interpolation.
            **kwargs: Extra keyword arguments for BaseAnalysis contract compatibility.

        Raises:
            ValueError: If ``vehicle`` is missing a required component
                (see :func:`resolve_booster_params_from_vehicle`).
        """
        self.logger = FlightLogger(
            vehicle_name=vehicle.name,
            analysis_name=self.name,
            enabled=bool(enable_logging),
        )

        self._stop_at_burnout = bool(stop_at_burnout)

        self._params = resolve_booster_params_from_vehicle(
            vehicle,
            launch_angle_deg=launch_angle_deg,
            altitude_m=altitude_m,
            ground_altitude_m=ground_altitude_m,
            fins_name=fins_name,
            motor_name=motor_name,
            body_name=body_name,
            stop_at_burnout=self._stop_at_burnout,
            t_max_s=t_max_s,
            cd_body_subsonic=cd_body_subsonic,
            cd_body_transonic=cd_body_transonic,
            cd_body_supersonic=cd_body_supersonic,
            mach_transonic_lo=mach_transonic_lo,
            mach_supersonic_lo=mach_supersonic_lo,
            cd_wave_per_fin=cd_wave_per_fin,
            isp_alt_ref_m=isp_alt_ref_m,
        )
        self._is_setup = True

        self.logger.info(
            "Configured PointMass3DOFBoostAnalysis for vehicle '%s' (launch_angle=%.1f deg, h0=%.1f m, stop_at_burnout=%s)",
            vehicle.name,
            self._params.launch_angle_deg,
            self._params.initial_altitude_m,
            self._stop_at_burnout,
        )
        self.logger.debug(
            "Booster parameters: m_launch=%.1f kg, m_prop=%.1f kg, m_burnout=%.1f kg, t_burn=%.1f s, Isp_sl=%.1f s",
            self._params.launch_mass_kg,
            self._params.propellant_mass_kg,
            self._params.burnout_mass_kg,
            self._params.burn_time_s,
            self._params.isp_sl_s,
        )

    def execute(self) -> AnalysisResults:
        """Integrate the trajectory and return results.

        Returns:
            AnalysisResults with ``burnout_time``, ``burnout_velocity``,
            ``burnout_mach``, ``burnout_altitude``, ``q_max`` and
            ``range_at_burnout`` in SI units. If ``stop_at_burnout=False``,
            additionally includes ``apogee_altitude``, ``apogee_time``,
            ``flight_time``, ``flight_range``, and ``impact_velocity``.
            ``units`` maps each key to its SI unit string. ``metadata``
            carries the full postprocessing breakdown (model documentation,
            resolved booster parameters, and dense trajectory samples).

        Raises:
            RuntimeError: If called before :meth:`setup`, or if results
                fail the analytical sanity check.
        """
        if not self._is_setup or self._params is None:
            raise RuntimeError(
                "PointMass3DOFBoostAnalysis.execute() called before setup()"
            )

        self.logger.info(
            "Starting boost trajectory integration (ODE solve_ivp RK45, stop_at_burnout=%s)...",
            self._stop_at_burnout,
        )
        sol = integrate_boost_phase(self._params)
        result = postprocess(sol, self._params)

        data = {
            "burnout_time": result["burnout_time"],
            "burnout_velocity": result["burnout_velocity"],
            "burnout_mach": result["burnout_mach"],
            "burnout_altitude": result["burnout_altitude"],
            "q_max": result["q_max"],
            "range_at_burnout": result["range_at_burnout"],
        }
        units = {
            "burnout_time": "s",
            "burnout_velocity": "m/s",
            "burnout_mach": "-",
            "burnout_altitude": "m",
            "q_max": "Pa",
            "range_at_burnout": "m",
        }
        if not self._stop_at_burnout:
            data["apogee_altitude"] = result["apogee_altitude"]
            units["apogee_altitude"] = "m"
            data["apogee_time"] = result["apogee_time"]
            units["apogee_time"] = "s"
            data["flight_time"] = result["flight_time"]
            units["flight_time"] = "s"
            data["flight_range"] = result["flight_range"]
            units["flight_range"] = "m"
            if result["impact_velocity"] is not None:
                data["impact_velocity"] = result["impact_velocity"]
                units["impact_velocity"] = "m/s"

        metadata = dict(result["metadata"])
        metadata["_samples"] = result["_samples"]
        if "_boost_samples" in result:
            metadata["_boost_samples"] = result["_boost_samples"]

        results = AnalysisResults(
            name=self.name,
            fidelity=self.fidelity,
            data=data,
            metadata=metadata,
            units=units,
        )
        if not self.validate_results(results):
            raise RuntimeError(
                "PointMass3DOFBoostAnalysis results failed analytical "
                "sanity check; see validate_results()"
            )

        if result["metadata"]["ground_impact_before_burnout"]:
            self.logger.warning(
                "Trajectory impacted ground at t=%.3f s before nominal %.1f s burnout!",
                result["burnout_time"],
                self._params.burn_time_s,
            )
        else:
            self.logger.info(
                "Burnout reached at t=%.3f s: velocity=%.1f m/s (Mach %.2f), altitude=%.1f m, q_max=%.0f Pa",
                result["burnout_time"],
                result["burnout_velocity"],
                result["burnout_mach"],
                result["burnout_altitude"],
                result["q_max"],
            )

        if not self._stop_at_burnout:
            self.logger.info(
                "Full flight finished at t=%.3f s (%s): apogee=%.1f m (at t=%.1f s), flight_range=%.1f m%s",
                result["flight_time"],
                result["metadata"]["integration_stopped_reason"],
                result["apogee_altitude"],
                result["apogee_time"],
                result["flight_range"],
                f", impact_velocity={result['impact_velocity']:.1f} m/s" if result["impact_velocity"] is not None else "",
            )

        return results

    def validate_results(self, results: AnalysisResults) -> bool:
        """Sanity-check the trajectory state against physical bounds.

        Checks that ``burnout_time``, ``burnout_velocity`` and
        ``q_max`` are non-negative and finite, and that
        ``burnout_altitude`` is not below ground level. For full flight
        simulations (``stop_at_burnout=False``), also checks
        ``apogee_altitude``, ``flight_time`` and ``flight_range``.

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        if not results.data or self._params is None:
            return False
        for key in ("burnout_time", "burnout_velocity", "q_max"):
            value = results[key]
            if not math.isfinite(value) or value < 0.0:
                return False
        ground_alt = self._params.ground_altitude_m
        if (
            not math.isfinite(results["burnout_altitude"])
            or results["burnout_altitude"] < ground_alt - 1e-6
        ):
            return False
        if not self._stop_at_burnout:
            for key in ("apogee_altitude", "flight_time", "flight_range"):
                if key in results.data:
                    val = results[key]
                    if not math.isfinite(val) or val < 0.0:
                        return False
        return True


@dataclass(frozen=True)
class BoosterParams:
    """Resolved stage-1 booster parameters used by the trajectory ODE.

    Attributes:
        launch_mass_kg: Total vehicle mass at ignition [kg].
        propellant_mass_kg: Propellant mass consumed over the burn [kg].
        burn_time_s: Nominal burn duration [s].
        isp_sl_s: Sea-level specific impulse [s].
        isp_vacuum_s: Vacuum specific impulse [s].
        thrust_mean_config_N: Mean thrust from vehicle configuration [N] (informational).
        a_ref_m2: Reference (body cross-section) area for drag [m^2].
        cd_fins: Constant fin-drag contribution to CD (count * per-fin CD).
        launch_angle_deg: Fixed thrust/body angle above horizontal [deg].
        initial_altitude_m: Launch-site initial altitude [m].
        ground_altitude_m: Ground impact plane altitude [m].
        cd_body_subsonic: Body drag coefficient for Mach < mach_transonic_lo.
        cd_body_transonic: Body drag coefficient for transonic regime.
        cd_body_supersonic: Body drag coefficient for Mach >= mach_supersonic_lo.
        mach_transonic_lo: Lower Mach bound of the transonic CD step.
        mach_supersonic_lo: Lower Mach bound of the supersonic CD step.
        isp_alt_ref_m: Reference altitude for linear sea-level -> vacuum Isp.
        stop_at_burnout: Whether simulation stops at booster motor burnout.
        t_max_s: Maximum simulation duration [s].
    """

    launch_mass_kg: float
    propellant_mass_kg: float
    burn_time_s: float
    isp_sl_s: float
    isp_vacuum_s: float
    thrust_mean_config_N: float
    a_ref_m2: float
    cd_fins: float
    launch_angle_deg: float
    initial_altitude_m: float = PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M
    ground_altitude_m: float = PointMass3DOFBoostAnalysis.DEFAULT_GROUND_ALTITUDE_M
    cd_body_subsonic: float = PointMass3DOFBoostAnalysis.CD_BODY_SUBSONIC
    cd_body_transonic: float = PointMass3DOFBoostAnalysis.CD_BODY_TRANSONIC
    cd_body_supersonic: float = PointMass3DOFBoostAnalysis.CD_BODY_SUPERSONIC
    mach_transonic_lo: float = PointMass3DOFBoostAnalysis.MACH_TRANSONIC_LO
    mach_supersonic_lo: float = PointMass3DOFBoostAnalysis.MACH_SUPERSONIC_LO
    isp_alt_ref_m: float = PointMass3DOFBoostAnalysis.ISP_ALT_REF_M
    stop_at_burnout: bool = PointMass3DOFBoostAnalysis.DEFAULT_STOP_AT_BURNOUT
    t_max_s: float = PointMass3DOFBoostAnalysis.DEFAULT_T_MAX_S

    @property
    def burnout_mass_kg(self) -> float:
        """Burnout mass: launch_mass_kg - propellant_mass_kg [kg]."""
        return self.launch_mass_kg - self.propellant_mass_kg

    @property
    def mdot_kg_s(self) -> float:
        """Constant propellant mass flow rate: propellant_mass_kg / burn_time_s [kg/s]."""
        return self.propellant_mass_kg / self.burn_time_s

    @property
    def thrust_sl_N(self) -> float:
        """Impulse-consistent thrust at sea level, ``Isp_sl * mdot * g0`` [N]."""
        return self.isp_sl_s * self.mdot_kg_s * const.G0


def _resolve_booster_propulsion(
    vehicle: BaseVehicleConfig, motor_name: str | None = None
) -> AnyPropulsionComponent:
    """Resolve the booster propulsion component from the vehicle configuration.

    Args:
        vehicle: Validated vehicle configuration to search.
        motor_name: Optional explicit name/ID of the motor in ``vehicle.propulsion``.

    Returns:
        The resolved propulsion component conforming to :data:`~YAADO_Core.ComponentStore.PROPULSION_COMPONENTS`.

    Raises:
        ValueError: If ``motor_name`` is not found in ``vehicle.propulsion``,
            if no boost-capable propulsion component exists on the vehicle,
            if the specified motor lacks required burn properties, or if multiple
            booster candidates exist and ``motor_name`` was not specified.
        TypeError: If the component specified by ``motor_name`` does not belong
            to :data:`~YAADO_Core.ComponentStore.PROPULSION_COMPONENTS`.
    """
    if motor_name is not None:
        if motor_name not in vehicle.propulsion:
            raise ValueError(
                f"Specified motor '{motor_name}' not found in vehicle.propulsion. "
                f"Available propulsion components: {list(vehicle.propulsion.keys())}"
            )
        component = vehicle.propulsion[motor_name]
        if not isinstance(component, PROPULSION_COMPONENTS):
            raise TypeError(
                f"Propulsion component '{motor_name}' is {type(component).__name__}, "
                "expected a registered propulsion component."
            )
        if not (hasattr(component, "burn_time") and hasattr(component, "propellant_mass")):
            raise ValueError(
                f"Propulsion component '{motor_name}' ({type(component).__name__}) "
                "does not provide 'burn_time' and 'propellant_mass' required for boost simulation."
            )
        return component

    booster_candidates = {
        name: comp
        for name, comp in vehicle.propulsion.items()
        if isinstance(comp, PROPULSION_COMPONENTS)
        and hasattr(comp, "burn_time")
        and hasattr(comp, "propellant_mass")
    }
    if not booster_candidates:
        raise ValueError(
            "vehicle has no boost-capable propulsion component "
            "(must belong to PROPULSION_COMPONENTS and define burn_time and propellant_mass)"
        )
    if len(booster_candidates) > 1:
        raise ValueError(
            f"Multiple booster components found: {list(booster_candidates.keys())}. "
            "Please specify 'motor_name'."
        )
    return next(iter(booster_candidates.values()))


def _resolve_body(
    vehicle: BaseVehicleConfig, body_name: str | None = None
) -> AnyBodyComponent:
    """Resolve the body component from the vehicle configuration.

    Args:
        vehicle: Validated vehicle configuration to search.
        body_name: Optional explicit name/ID of the body in ``vehicle.bodies``.

    Returns:
        The resolved body component conforming to :data:`~YAADO_Core.ComponentStore.BODY_COMPONENTS`.

    Raises:
        ValueError: If ``body_name`` is not found in ``vehicle.bodies``,
            if no body component exists on the vehicle, or if multiple exist
            and ``body_name`` was not specified.
        TypeError: If the component specified by ``body_name`` does not belong
            to :data:`~YAADO_Core.ComponentStore.BODY_COMPONENTS`.
    """
    if body_name is not None:
        if body_name not in vehicle.bodies:
            raise ValueError(
                f"Specified body '{body_name}' not found in vehicle.bodies. "
                f"Available bodies: {list(vehicle.bodies.keys())}"
            )
        component = vehicle.bodies[body_name]
        if not isinstance(component, BODY_COMPONENTS):
            raise TypeError(
                f"Body component '{body_name}' is {type(component).__name__}, "
                "expected a registered body component."
            )
        return component

    bodies = {
        name: comp for name, comp in vehicle.bodies.items() if isinstance(comp, BODY_COMPONENTS)
    }
    if not bodies:
        raise ValueError("vehicle has no body component in vehicle.bodies")
    if len(bodies) > 1:
        raise ValueError(
            f"Multiple body components found: {list(bodies.keys())}. "
            "Please specify 'body_name'."
        )
    return next(iter(bodies.values()))


def _resolve_aero_surface(
    vehicle: BaseVehicleConfig, fins_name: str | None = None
) -> AnyAeroComponent | None:
    """Resolve the aero-surface component from the vehicle configuration.

    Args:
        vehicle: Validated vehicle configuration to search.
        fins_name: Optional explicit name/ID of the fin set in ``vehicle.aero_surfaces``.

    Returns:
        The resolved aero component conforming to :data:`~YAADO_Core.ComponentStore.AERO_COMPONENTS`,
        or ``None`` if the vehicle has no aero surfaces.

    Raises:
        ValueError: If ``fins_name`` is not found in ``vehicle.aero_surfaces``,
            or if multiple aero surfaces exist and ``fins_name`` was not specified.
        TypeError: If the component specified by ``fins_name`` does not belong
            to :data:`~YAADO_Core.ComponentStore.AERO_COMPONENTS`.
    """
    if fins_name is not None:
        if fins_name not in vehicle.aero_surfaces:
            raise ValueError(
                f"Specified fin set '{fins_name}' not found in vehicle.aero_surfaces. "
                f"Available aero surfaces: {list(vehicle.aero_surfaces.keys())}"
            )
        component = vehicle.aero_surfaces[fins_name]
        if not isinstance(component, AERO_COMPONENTS):
            raise TypeError(
                f"Aero surface '{fins_name}' is {type(component).__name__}, "
                "expected a registered aero surface component."
            )
        return component

    aero_surfaces = {
        name: comp for name, comp in vehicle.aero_surfaces.items() if isinstance(comp, AERO_COMPONENTS)
    }
    if not aero_surfaces:
        return None
    if len(aero_surfaces) > 1:
        raise ValueError(
            f"Multiple aero surfaces found: {list(aero_surfaces.keys())}. "
            "Please specify 'fins_name'."
        )
    return next(iter(aero_surfaces.values()))


def resolve_booster_params_from_vehicle(
    vehicle: BaseVehicleConfig,
    *,
    launch_angle_deg: float = PointMass3DOFBoostAnalysis.DEFAULT_LAUNCH_ANGLE_DEG,
    altitude_m: float = PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M,
    ground_altitude_m: float = PointMass3DOFBoostAnalysis.DEFAULT_GROUND_ALTITUDE_M,
    motor_name: str | None = None,
    body_name: str | None = None,
    fins_name: str | None = None,
    stop_at_burnout: bool = PointMass3DOFBoostAnalysis.DEFAULT_STOP_AT_BURNOUT,
    t_max_s: float = PointMass3DOFBoostAnalysis.DEFAULT_T_MAX_S,
    cd_body_subsonic: float = PointMass3DOFBoostAnalysis.CD_BODY_SUBSONIC,
    cd_body_transonic: float = PointMass3DOFBoostAnalysis.CD_BODY_TRANSONIC,
    cd_body_supersonic: float = PointMass3DOFBoostAnalysis.CD_BODY_SUPERSONIC,
    mach_transonic_lo: float = PointMass3DOFBoostAnalysis.MACH_TRANSONIC_LO,
    mach_supersonic_lo: float = PointMass3DOFBoostAnalysis.MACH_SUPERSONIC_LO,
    cd_wave_per_fin: float = PointMass3DOFBoostAnalysis.CD_WAVE_PER_FIN,
    isp_alt_ref_m: float = PointMass3DOFBoostAnalysis.ISP_ALT_REF_M,
) -> BoosterParams:
    """Resolve stage-1 booster parameters from a validated vehicle config.

    All mass, propulsion and geometry data is read from ``vehicle``
    (composition of components belonging to :data:`~YAADO_Core.ComponentStore.PROPULSION_COMPONENTS`,
    :data:`~YAADO_Core.ComponentStore.BODY_COMPONENTS`,
    :data:`~YAADO_Core.ComponentStore.AERO_COMPONENTS`, and
    :class:`~YAADO_Core.ComponentStore.mass.MassProperties`). Launch-site
    and operating conditions are passed via explicit keyword arguments.

    Args:
        vehicle: Validated, vehicle-agnostic configuration providing the
            propulsion, body, aero_surfaces (fins) and mass_properties
            components.
        launch_angle_deg: Launch elevation angle above horizontal [deg].
            Defaults to :attr:`PointMass3DOFBoostAnalysis.DEFAULT_LAUNCH_ANGLE_DEG`.
        altitude_m: Initial launch altitude [m]. Defaults to :attr:`PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M`.
        ground_altitude_m: Ground/impact plane altitude [m]. Defaults to 0.0.
        motor_name: Optional explicit name of the solid motor in ``vehicle.propulsion``.
        body_name: Optional explicit name of the body in ``vehicle.bodies``.
        fins_name: Optional explicit name of the fin set in ``vehicle.aero_surfaces``.
        stop_at_burnout: If True, trajectory ends at motor depletion. If False,
            simulation runs full test through unpowered coast to impact/apogee.
        t_max_s: Maximum flight duration [s] for full flight simulation.
        cd_body_subsonic: Subsonic body drag coefficient.
        cd_body_transonic: Transonic body drag coefficient.
        cd_body_supersonic: Supersonic body drag coefficient.
        mach_transonic_lo: Lower Mach boundary for transonic regime.
        mach_supersonic_lo: Lower Mach boundary for supersonic regime.
        cd_wave_per_fin: Wave drag coefficient contribution per fin.
        isp_alt_ref_m: Reference altitude [m] for Isp vacuum interpolation.

    Returns:
        Resolved :class:`BoosterParams` with the impulse-consistent thrust
        caveat already computed (see :attr:`BoosterParams.thrust_sl_N`).

    Raises:
        ValueError: If ``vehicle`` has no boost-capable propulsion component,
            no body component, no ``mass_properties.total_mass``, or if multiple
            components of a subsystem exist without specifying the component name.
        TypeError: If a specified component name refers to an unregistered component type.
    """
    initial_altitude_m = float(altitude_m)
    launch_angle_deg = float(launch_angle_deg)
    ground_altitude_m = float(ground_altitude_m)
    t_max_s = float(t_max_s)

    propulsion = _resolve_booster_propulsion(vehicle, motor_name=motor_name)
    body = _resolve_body(vehicle, body_name=body_name)
    fins = _resolve_aero_surface(vehicle, fins_name=fins_name)

    if vehicle.mass_properties is None or vehicle.mass_properties.total_mass is None:
        raise ValueError("vehicle.mass_properties.total_mass is required")

    launch_mass_kg = vehicle.mass_properties.total_mass
    propellant_mass_kg = propulsion.propellant_mass
    burn_time_s = propulsion.burn_time

    d_ref_m = getattr(body, "diameter", None)
    if d_ref_m is None:
        raise ValueError(
            f"Body component '{type(body).__name__}' does not define a 'diameter' attribute"
        )
    a_ref_m2 = math.pi / 4.0 * d_ref_m**2
    if fins is not None:
        fin_count = getattr(
            fins, "count", PointMass3DOFBoostAnalysis.DEFAULT_AERO_SURFACE_COUNT
        )
        cd_fins = fin_count * cd_wave_per_fin
    else:
        cd_fins = 0.0

    return BoosterParams(
        launch_mass_kg=launch_mass_kg,
        propellant_mass_kg=propellant_mass_kg,
        burn_time_s=burn_time_s,
        isp_sl_s=float(propulsion.isp_sl),
        isp_vacuum_s=float(getattr(propulsion, "isp_vacuum", propulsion.isp_sl)),
        thrust_mean_config_N=float(getattr(propulsion, "thrust_mean", 0.0)),
        a_ref_m2=a_ref_m2,
        cd_fins=cd_fins,
        launch_angle_deg=launch_angle_deg,
        initial_altitude_m=initial_altitude_m,
        ground_altitude_m=ground_altitude_m,
        cd_body_subsonic=cd_body_subsonic,
        cd_body_transonic=cd_body_transonic,
        cd_body_supersonic=cd_body_supersonic,
        mach_transonic_lo=mach_transonic_lo,
        mach_supersonic_lo=mach_supersonic_lo,
        isp_alt_ref_m=isp_alt_ref_m,
        stop_at_burnout=stop_at_burnout,
        t_max_s=t_max_s,
    )


def specific_impulse_s(altitude_m: float, params: BoosterParams) -> float:
    """Interpolate Isp linearly from sea-level toward vacuum with altitude.

    Args:
        altitude_m: Geometric altitude [m] (clamped to ``>= 0``).
        params: Booster parameters (``isp_sl_s``, ``isp_vacuum_s``, ``isp_alt_ref_m``).

    Returns:
        Specific impulse [s] at the given altitude.
    """
    h = max(altitude_m, 0.0)
    frac = min(h / params.isp_alt_ref_m, 1.0)
    return params.isp_sl_s + (params.isp_vacuum_s - params.isp_sl_s) * frac


def drag_coefficient(mach: float, params: BoosterParams) -> float:
    """Total drag coefficient: stepped body CD(Mach) plus constant fin CD.

    Args:
        mach: Free-stream Mach number.
        params: Booster parameters (for ``cd_fins`` and body CD thresholds).

    Returns:
        ``CD_total = CD_body(mach) + CD_fins``.
    """
    if mach < params.mach_transonic_lo:
        cd_body = params.cd_body_subsonic
    elif mach < params.mach_supersonic_lo:
        cd_body = params.cd_body_transonic
    else:
        cd_body = params.cd_body_supersonic
    return cd_body + params.cd_fins


def mass_at_time(t_s: float, params: BoosterParams) -> float:
    """Instantaneous vehicle mass under constant mass-flow depletion.

    Args:
        t_s: Time since ignition [s].
        params: Booster parameters.

    Returns:
        Mass [kg], clamped to ``burnout_mass_kg`` for ``t_s >= burn_time_s``.
    """
    if t_s >= params.burn_time_s:
        return params.burnout_mass_kg
    return params.launch_mass_kg - params.mdot_kg_s * t_s


def flow_state(
    velocity_ms: tuple[float, float], altitude_m: float
) -> tuple[float, float, float, float]:
    """Compute speed, Mach, dynamic pressure, and density at a state point.

    Args:
        velocity_ms: ``(vx, vh)`` velocity components [m/s].
        altitude_m: Geometric altitude [m].

    Returns:
        Tuple ``(speed_ms, mach, dynamic_pressure_pa, density_kg_m3)``.
    """
    vx, vh = velocity_ms
    speed_ms = math.hypot(vx, vh)
    atm = isa_atmosphere(altitude_m)
    mach = speed_ms / atm.speed_of_sound if atm.speed_of_sound > 0.0 else 0.0
    dynamic_pressure_pa = 0.5 * atm.density * speed_ms**2
    return speed_ms, mach, dynamic_pressure_pa, atm.density


def boost_dynamics(t_s: float, state: np.ndarray, params: BoosterParams) -> list[float]:
    """3-DOF point-mass equations of motion for the boost phase.

    State vector ``[x_range_m, h_m, vx_ms, vh_ms]``. Thrust acts along the
    fixed launch angle (body axis, no pitch program); drag opposes the
    velocity vector; gravity acts along ``-h``.

    Gravity-turn approximation: No explicit lift force is modeled. For a
    near-vertical launch (83 deg), the trajectory naturally arcs over due to
    the fixed thrust direction and gravity, resembling a zero-lift gravity
    turn. Angle-of-attack effects are neglected; this is acceptable for this
    low-order model but limits accuracy at high alpha (would require a 6-DOF
    simulation with pitch dynamics).

    Args:
        t_s: Time since ignition [s].
        state: Current state ``[x, h, vx, vh]``.
        params: Booster parameters.

    Returns:
        State derivative ``[vx, vh, ax, ah]``.
    """
    _x, h, vx, vh = state
    speed_ms, mach, q_pa, _density_kg_m3 = flow_state((vx, vh), h)

    cd_total = drag_coefficient(mach, params)
    drag_N = q_pa * cd_total * params.a_ref_m2

    if speed_ms > PointMass3DOFBoostAnalysis.VELOCITY_EPS_MS:
        ux, uh = vx / speed_ms, vh / speed_ms
    else:
        ux, uh = 0.0, 0.0

    if t_s <= params.burn_time_s:
        isp_s = specific_impulse_s(h, params)
        thrust_N = params.mdot_kg_s * const.G0 * isp_s
    else:
        thrust_N = 0.0

    mass_kg = mass_at_time(t_s, params)
    angle_rad = math.radians(params.launch_angle_deg)
    thrust_x_N = thrust_N * math.cos(angle_rad)
    thrust_h_N = thrust_N * math.sin(angle_rad)

    ax_ms2 = (thrust_x_N - drag_N * ux) / mass_kg
    ah_ms2 = (thrust_h_N - drag_N * uh) / mass_kg - const.G0

    return [vx, vh, ax_ms2, ah_ms2]


def _ground_impact_event(t_s: float, state: np.ndarray, params: BoosterParams) -> float:
    """Zero-crossing event: altitude reaching ground level (terminal, decreasing).

    Note:
        solve_ivp appends `args` to every callable passed via `events` as
        well as `fun`, so `_ground_impact_event` must accept `params` as a
        positional arg directly.
    """
    if t_s < PointMass3DOFBoostAnalysis.IGNITION_PAD_CLEAR_TIME_S:
        return PointMass3DOFBoostAnalysis.IGNITION_PAD_CLEAR_ALTITUDE_MARGIN_M
    return state[1] - params.ground_altitude_m


_ground_impact_event.terminal = True
_ground_impact_event.direction = -1.0


def integrate_boost_phase(
    params: BoosterParams,
    h0_m: float | None = None,
    *,
    stop_at_burnout: bool | None = None,
    t_max_s: float | None = None,
) -> OptimizeResult:
    """Integrate the boost or full trajectory from ignition to burnout/impact.

    Args:
        params: Booster parameters resolved by
            :func:`resolve_booster_params_from_vehicle`.
        h0_m: Initial altitude [m] at ignition. Defaults to
            ``params.initial_altitude_m``; callers can pass it explicitly
            to override.
        stop_at_burnout: If True, integration terminates at nominal booster
            burnout or ground impact (whichever occurs first). If False,
            simulation continues past booster depletion through unpowered
            coast until apogee and ground impact (or ``t_max_s``). Defaults
            to ``params.stop_at_burnout``.
        t_max_s: Maximum simulation time [s] when ``stop_at_burnout=False``.
            Defaults to ``params.t_max_s``.

    Returns:
        The ``scipy.integrate.solve_ivp`` result, with dense output enabled.
    """
    if h0_m is None:
        h0_m = params.initial_altitude_m
    if stop_at_burnout is None:
        stop_at_burnout = params.stop_at_burnout
    if t_max_s is None:
        t_max_s = params.t_max_s

    t_end = params.burn_time_s if stop_at_burnout else max(params.burn_time_s, t_max_s)

    y0 = [
        PointMass3DOFBoostAnalysis.DEFAULT_X0_M,
        h0_m,
        PointMass3DOFBoostAnalysis.DEFAULT_V0_MS,
        PointMass3DOFBoostAnalysis.DEFAULT_V0_MS,
    ]
    sol = solve_ivp(
        fun=boost_dynamics,
        t_span=(0.0, t_end),
        y0=y0,
        method="RK45",
        args=(params,),
        rtol=PointMass3DOFBoostAnalysis.RTOL,
        atol=PointMass3DOFBoostAnalysis.ATOL,
        dense_output=True,
        events=_ground_impact_event,
    )
    if not sol.success:
        raise RuntimeError(f"solve_ivp failed: {sol.message}")
    return sol


def _evaluate_samples(
    sol: OptimizeResult,
    t_eval: np.ndarray,
    burn_time_s: float,
) -> dict[str, Any]:
    """Sample the ODE solution densely and compute aerodynamic flow state.

    Args:
        sol: OptimizeResult object from scipy.integrate.solve_ivp with dense_output=True.
        t_eval: Monotonically increasing time evaluation points [s].
        burn_time_s: Motor burn time [s].

    Returns:
        Dictionary with keys: ``t_s``, ``x_m``, ``h_m``, ``v_ms``, ``mach``,
        ``q_pa``, ``q_max_idx``, ``apogee_idx``, ``burn_time_s``.
    """
    y_eval = sol.sol(t_eval)
    x_eval, h_eval, vx_eval, vh_eval = y_eval
    speed_eval = np.hypot(vx_eval, vh_eval)

    atm = isa_atmosphere(h_eval)
    sos = np.asarray(atm.speed_of_sound)
    rho = np.asarray(atm.density)

    mach_eval = np.where(sos > 0.0, speed_eval / sos, 0.0)
    q_eval = 0.5 * rho * speed_eval**2

    q_max_idx = int(np.argmax(q_eval))
    apogee_idx = int(np.argmax(h_eval))
    return {
        "t_s": t_eval,
        "x_m": x_eval,
        "h_m": h_eval,
        "v_ms": speed_eval,
        "mach": mach_eval,
        "q_pa": q_eval,
        "q_max_idx": q_max_idx,
        "apogee_idx": apogee_idx,
        "burn_time_s": burn_time_s,
    }


def postprocess(
    sol: OptimizeResult,
    params: BoosterParams,
    h0_m: float | None = None,
    *,
    stop_at_burnout: bool | None = None,
) -> dict[str, Any]:
    """Derive burnout state, full-flight metrics, and dense sample arrays from solution.

    Args:
        sol: Result from :func:`integrate_boost_phase` (dense output).
        params: Booster parameters.
        h0_m: Initial altitude [m] used for the integration (see
            :func:`integrate_boost_phase`), reported back in the metadata.
            Defaults to ``params.initial_altitude_m``.
        stop_at_burnout: Whether the integration was configured to stop at burnout.
            Defaults to ``params.stop_at_burnout``.

    Returns:
        Dict with scalar results, a ``metadata`` sub-dict, a ``_samples``
        sub-dict of dense arrays across the full simulated trajectory, and
        a ``_boost_samples`` sub-dict strictly for the boost phase.
    """
    if h0_m is None:
        h0_m = params.initial_altitude_m
    if stop_at_burnout is None:
        stop_at_burnout = params.stop_at_burnout

    t_end_s = float(sol.t[-1])
    ground_impact = bool(len(sol.t_events[0]) > 0)
    ground_impact_before_burnout = ground_impact and (t_end_s < params.burn_time_s - 1e-6)

    t_burnout_nominal = min(t_end_s, params.burn_time_s)

    # Dense samples specifically for the boost phase (0 to t_burnout_nominal)
    t_boost = np.linspace(0.0, t_burnout_nominal, PointMass3DOFBoostAnalysis.N_DENSE_SAMPLES)
    boost_samples = _evaluate_samples(sol, t_boost, params.burn_time_s)
    boost_samples["ground_altitude_m"] = params.ground_altitude_m

    # Dense samples for full flight (0 to t_end_s)
    if not stop_at_burnout and (t_end_s > t_burnout_nominal + 1e-3):
        t_fine = np.linspace(0.0, t_end_s, PointMass3DOFBoostAnalysis.N_DENSE_SAMPLES)
        full_samples = _evaluate_samples(sol, t_fine, params.burn_time_s)
        full_samples["ground_altitude_m"] = params.ground_altitude_m
    else:
        full_samples = dict(boost_samples)

    q_max_idx = full_samples["q_max_idx"]
    q_max_pa = float(full_samples["q_pa"][q_max_idx])

    # State at motor burnout (t = t_burnout_nominal)
    y_bo = sol.sol(t_burnout_nominal)
    x_bo, h_bo, vx_bo, vh_bo = [float(v) for v in y_bo]
    v_bo = math.hypot(vx_bo, vh_bo)
    _, mach_bo, _, _ = flow_state((vx_bo, vh_bo), h_bo)

    # Full trajectory / coast metrics
    apogee_idx = full_samples["apogee_idx"]
    apogee_altitude = float(full_samples["h_m"][apogee_idx])
    apogee_time = float(full_samples["t_s"][apogee_idx])
    apogee_range = float(full_samples["x_m"][apogee_idx])

    final_x = float(full_samples["x_m"][-1])
    final_h = float(full_samples["h_m"][-1])
    final_v = float(full_samples["v_ms"][-1])
    final_mach = float(full_samples["mach"][-1])

    if ground_impact_before_burnout:
        stopped_reason = "ground_impact" if stop_at_burnout else "ground_impact_before_burnout"
    elif ground_impact:
        stopped_reason = "ground_impact"
    elif stop_at_burnout or abs(t_end_s - params.burn_time_s) < 1e-6:
        stopped_reason = "burnout"
    else:
        stopped_reason = "max_time"

    thrust_used_N = params.thrust_sl_N

    result: dict[str, Any] = {
        "burnout_time": t_burnout_nominal,
        "burnout_velocity": v_bo,
        "burnout_mach": mach_bo,
        "burnout_altitude": h_bo,
        "q_max": q_max_pa,
        "range_at_burnout": x_bo,
        "apogee_altitude": apogee_altitude,
        "apogee_time": apogee_time,
        "apogee_range": apogee_range,
        "flight_time": t_end_s,
        "flight_range": final_x,
        "impact_velocity": final_v if ground_impact else None,
        "metadata": {
            "burnout_vx": vx_bo,
            "burnout_vh": vh_bo,
            "nominal_burn_time": params.burn_time_s,
            "integration_stopped_reason": stopped_reason,
            "ground_impact_before_burnout": ground_impact_before_burnout,
            "ground_impact": ground_impact,
            "stop_at_burnout": stop_at_burnout,
            "apogee_altitude": apogee_altitude,
            "apogee_time": apogee_time,
            "apogee_range": apogee_range,
            "flight_time": t_end_s,
            "flight_range": final_x,
            "final_altitude": final_h,
            "final_velocity": final_v,
            "final_mach": final_mach,
            "impact_velocity": final_v if ground_impact else None,
            "impact_mach": final_mach if ground_impact else None,
            "model_limitations": (
                "Point-mass 3-DOF with fixed launch angle (no pitch program). "
                "Zero-lift gravity-turn approximation: thrust along body axis "
                f"at {params.launch_angle_deg:.1f} deg, no explicit lift force. "
                "Angle-of-attack effects neglected. Reasonable for near-vertical "
                "boost phase; higher-fidelity models would include 6-DOF pitch "
                "dynamics and alpha-dependent lift/moment."
            ),
            "thrust_used": thrust_used_N,
            "thrust_config_mean": params.thrust_mean_config_N,
            "thrust_note": (
                f"Impulse-consistent thrust F = Isp_sl * mdot * g0 = {thrust_used_N:.0f} N."
            ),
            "isp_sl": params.isp_sl_s,
            "isp_vacuum": params.isp_vacuum_s,
            "isp_interpolation": (
                "linear in altitude from isp_sl at h=0 to isp_vacuum at "
                f"h={params.isp_alt_ref_m:.0f} m, clamped beyond"
            ),
            "mdot": params.mdot_kg_s,
            "launch_mass": params.launch_mass_kg,
            "burnout_mass": params.burnout_mass_kg,
            "mass_at_stop": mass_at_time(t_end_s, params),
            "launch_angle": params.launch_angle_deg,
            "initial_altitude": h0_m,
            "ground_altitude": params.ground_altitude_m,
            "reference_area": params.a_ref_m2,
            "cd_fins": params.cd_fins,
            "atmosphere_model": (
                "ISA troposphere (ICAO Doc 7488 manual formula via ambiance), "
                "valid from -5000 m to 80000 m"
            ),
            "cd_model": (
                f"CD_body: {params.cd_body_subsonic:.2f} (M<{params.mach_transonic_lo:.1f}) / "
                f"{params.cd_body_transonic:.2f} ({params.mach_transonic_lo:.1f}<=M<{params.mach_supersonic_lo:.1f}) / "
                f"{params.cd_body_supersonic:.2f} (M>={params.mach_supersonic_lo:.1f}). "
                f"CD_fins = {params.cd_fins:.4f}. CD_total = CD_body + CD_fins."
            ),
            "integrator": (
                f"scipy.integrate.solve_ivp, RK45, rtol={PointMass3DOFBoostAnalysis.RTOL}, atol={PointMass3DOFBoostAnalysis.ATOL}, "
                "dense_output=True, terminal ground-impact event (h=ground_altitude_m, "
                "decreasing)"
            ),
        },
        "_samples": full_samples,
        "_boost_samples": boost_samples,
    }
    return result


def plot_boost_phase(
    samples: dict[str, Any],
    *,
    burn_time_s: float | None = None,
    ground_altitude_m: float | None = None,
) -> Figure:
    """Plot V(t), h(t), Mach(t), q(t) for the boost phase in a 2x2 grid.

    Depicts the powered boost trajectory from ignition to motor burnout.
    All figure saving is handled by :class:`~YAADO_Core.Foundation.flight_logger.FlightLogger`.

    Args:
        samples: The ``_boost_samples`` or ``_samples`` sub-dict returned by :func:`postprocess`.
            If samples extend beyond burnout, they are sliced to the boost phase.
        burn_time_s: Optional motor burn time [s]. Used to slice samples if they extend beyond burnout.
        ground_altitude_m: Ground impact plane altitude [m]. Defaults to ground altitude from samples.

    Returns:
        The matplotlib Figure instance.
    """
    import matplotlib.pyplot as plt

    t_s = np.asarray(samples["t_s"])
    v_ms = np.asarray(samples["v_ms"])
    h_m = np.asarray(samples["h_m"])
    mach = np.asarray(samples["mach"])
    q_pa = np.asarray(samples["q_pa"])

    if ground_altitude_m is None:
        ground_altitude_m = float(
            samples.get("ground_altitude_m", PointMass3DOFBoostAnalysis.DEFAULT_GROUND_ALTITUDE_M)
        )

    if burn_time_s is None:
        burn_time_s = samples.get("burn_time_s")

    if burn_time_s is not None and len(t_s) > 0 and t_s[-1] > burn_time_s + 1e-3:
        mask = t_s <= (burn_time_s + 1e-6)
        t_s = t_s[mask]
        v_ms = v_ms[mask]
        h_m = h_m[mask]
        mach = mach[mask]
        q_pa = q_pa[mask]

    fig, axes = plt.subplots(2, 2, figsize=(10, 7))

    ax = axes[0, 0]
    ax.plot(t_s, v_ms, color="tab:blue")
    ax.set_ylim(bottom=0.0)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Velocity [m/s]")
    ax.set_title("Speed vs. time")
    ax.grid(True, alpha=0.3)

    ax = axes[0, 1]
    ax.plot(t_s, h_m, color="tab:green")
    ax.axhline(ground_altitude_m, color="k", linewidth=0.8, linestyle="--")
    min_h = float(np.min(h_m)) if len(h_m) > 0 else ground_altitude_m
    ax.set_ylim(bottom=min(ground_altitude_m, min_h))
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Altitude [m]")
    ax.set_title("Altitude vs. time")
    ax.grid(True, alpha=0.3)

    ax = axes[1, 0]
    ax.plot(t_s, mach, color="tab:red")
    ax.set_ylim(bottom=0.0)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Mach number [-]")
    ax.set_title("Mach vs. time")
    ax.grid(True, alpha=0.3)

    ax = axes[1, 1]
    ax.plot(t_s, q_pa, color="tab:purple")
    ax.set_ylim(bottom=0.0)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Dynamic pressure [Pa]")
    ax.set_title("Dynamic pressure vs. time")
    ax.grid(True, alpha=0.3)

    if len(t_s) > 0:
        for ax in axes.flat:
            ax.set_xlim(left=0.0)

    fig.suptitle("Stage-1 booster boost-phase trajectory (3-DOF point mass)")
    fig.tight_layout()
    return fig


def plot_full_flight(
    samples: dict[str, Any],
    *,
    burn_time_s: float | None = None,
    ground_altitude_m: float | None = None,
) -> Figure:
    """Plot full-flight V(t), h(t), Mach(t), q(t) with burnout and apogee markers in a 2x2 grid.

    Depicts the entire trajectory including powered boost and unpowered coasting
    to apogee and ground impact.
    All figure saving is handled by :class:`~YAADO_Core.Foundation.flight_logger.FlightLogger`.

    Args:
        samples: The full trajectory ``_samples`` sub-dict returned by :func:`postprocess`.
        burn_time_s: Optional motor burn time [s]. If provided, vertical dotted lines
            are drawn at burnout across all subplots.
        ground_altitude_m: Ground impact plane altitude [m]. Defaults to ground altitude from samples.

    Returns:
        The matplotlib Figure instance.
    """
    import matplotlib.pyplot as plt

    t_s = np.asarray(samples["t_s"])
    v_ms = np.asarray(samples["v_ms"])
    h_m = np.asarray(samples["h_m"])
    mach = np.asarray(samples["mach"])
    q_pa = np.asarray(samples["q_pa"])

    if ground_altitude_m is None:
        ground_altitude_m = float(
            samples.get("ground_altitude_m", PointMass3DOFBoostAnalysis.DEFAULT_GROUND_ALTITUDE_M)
        )

    if burn_time_s is None:
        burn_time_s = samples.get("burn_time_s")

    fig, axes = plt.subplots(2, 2, figsize=(10, 7))

    ax = axes[0, 0]
    ax.plot(t_s, v_ms, color="tab:blue", label="Speed")
    ax.set_ylim(bottom=0.0)
    if burn_time_s is not None and len(t_s) > 0 and t_s[-1] >= burn_time_s - 1e-3:
        ax.axvline(burn_time_s, color="gray", linestyle=":", linewidth=1.2, label="Burnout")
        ax.legend()
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Velocity [m/s]")
    ax.set_title("Speed vs. time")
    ax.grid(True, alpha=0.3)

    ax = axes[0, 1]
    ax.plot(t_s, h_m, color="tab:green", label="Altitude")
    ax.axhline(ground_altitude_m, color="k", linewidth=0.8, linestyle="--")
    min_h = float(np.min(h_m)) if len(h_m) > 0 else ground_altitude_m
    ax.set_ylim(bottom=min(ground_altitude_m, min_h))
    if burn_time_s is not None and len(t_s) > 0 and t_s[-1] >= burn_time_s - 1e-3:
        ax.axvline(burn_time_s, color="gray", linestyle=":", linewidth=1.2, label="Burnout")
    ap_idx = samples.get("apogee_idx")
    if ap_idx is None and len(h_m) > 0:
        ap_idx = int(np.argmax(h_m))
    if len(h_m) > 0 and ap_idx is not None and 0 <= ap_idx < len(h_m):
        ax.scatter(
            [t_s[ap_idx]],
            [h_m[ap_idx]],
            color="tab:olive",
            zorder=5,
            label=f"Apogee ({h_m[ap_idx]:.0f} m)",
        )
    ax.legend()
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Altitude [m]")
    ax.set_title("Altitude vs. time")
    ax.grid(True, alpha=0.3)

    ax = axes[1, 0]
    ax.plot(t_s, mach, color="tab:red", label="Mach")
    ax.set_ylim(bottom=0.0)
    if burn_time_s is not None and len(t_s) > 0 and t_s[-1] >= burn_time_s - 1e-3:
        ax.axvline(burn_time_s, color="gray", linestyle=":", linewidth=1.2, label="Burnout")
        ax.legend()
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Mach number [-]")
    ax.set_title("Mach vs. time")
    ax.grid(True, alpha=0.3)

    ax = axes[1, 1]
    ax.plot(t_s, q_pa, color="tab:purple", label="Dynamic pressure")
    ax.set_ylim(bottom=0.0)
    q_max_idx = samples.get("q_max_idx")
    if q_max_idx is None and len(q_pa) > 0:
        q_max_idx = int(np.argmax(q_pa))
    if len(q_pa) > 0 and q_max_idx is not None and 0 <= q_max_idx < len(q_pa):
        ax.scatter(
            [t_s[q_max_idx]],
            [q_pa[q_max_idx]],
            color="k",
            zorder=5,
            label="q_max",
        )
    if burn_time_s is not None and len(t_s) > 0 and t_s[-1] >= burn_time_s - 1e-3:
        ax.axvline(burn_time_s, color="gray", linestyle=":", linewidth=1.2, label="Burnout")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Dynamic pressure [Pa]")
    ax.set_title("Dynamic pressure vs. time")
    ax.legend()
    ax.grid(True, alpha=0.3)

    if len(t_s) > 0:
        for ax in axes.flat:
            ax.set_xlim(left=0.0)

    fig.suptitle("Full-flight trajectory simulation (3-DOF point mass)")
    fig.tight_layout()
    return fig


def run_launch_angle_sweep(
    vehicle: BaseVehicleConfig,
    angles_deg: Sequence[float] = PointMass3DOFBoostAnalysis.DEFAULT_SWEEP_ANGLES_DEG,
    *,
    altitude_m: float = PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M,
    ground_altitude_m: float = PointMass3DOFBoostAnalysis.DEFAULT_GROUND_ALTITUDE_M,
    fins_name: str | None = None,
    motor_name: str | None = None,
    body_name: str | None = None,
    stop_at_burnout: bool = PointMass3DOFBoostAnalysis.DEFAULT_STOP_AT_BURNOUT,
    t_max_s: float = PointMass3DOFBoostAnalysis.DEFAULT_T_MAX_S,
) -> list[dict[str, Any]]:
    """Sweep the fixed launch angle and report burnout/impact metrics per angle.

    For each angle, the trajectory is integrated from ignition with
    overridden ``launch_angle_deg``, then post-processed.

    Args:
        vehicle: Validated BaseVehicleConfig instance.
        angles_deg: Launch angles [deg] to sweep. Defaults to
            :attr:`PointMass3DOFBoostAnalysis.DEFAULT_SWEEP_ANGLES_DEG`.
        altitude_m: Launch altitude [m]. Defaults to :attr:`PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M`.
        ground_altitude_m: Ground impact plane altitude [m]. Defaults to :attr:`PointMass3DOFBoostAnalysis.DEFAULT_GROUND_ALTITUDE_M`.
        fins_name: Explicit name of fin set in ``vehicle.aero_surfaces``.
        motor_name: Explicit name of motor in ``vehicle.propulsion``.
        body_name: Explicit name of body in ``vehicle.bodies``.
        stop_at_burnout: Whether simulation terminates at booster depletion.
            Defaults to :attr:`PointMass3DOFBoostAnalysis.DEFAULT_STOP_AT_BURNOUT`.
        t_max_s: Maximum simulation time [s]. Defaults to :attr:`PointMass3DOFBoostAnalysis.DEFAULT_T_MAX_S`.

    Returns:
        A list of per-angle result dicts, one per swept angle, each with
        keys ``launch_angle_deg``, ``burnout_mach``, ``burnout_altitude``,
        ``burnout_range``, ``q_max``, and ``ground_impact_flag`` (bool,
        ``True`` if altitude reached ``<= 0 m`` before nominal burnout).
        If ``stop_at_burnout=False``, also includes ``apogee_altitude``,
        ``flight_time``, and ``flight_range``.

    Raises:
        TypeError: If ``vehicle`` is not a BaseVehicleConfig instance.
    """
    if not isinstance(vehicle, BaseVehicleConfig):
        raise TypeError(
            f"vehicle must be a BaseVehicleConfig instance, got {type(vehicle).__name__}"
        )

    sweep_results: list[dict[str, Any]] = []
    base_params = resolve_booster_params_from_vehicle(
        vehicle,
        altitude_m=altitude_m,
        ground_altitude_m=ground_altitude_m,
        fins_name=fins_name,
        motor_name=motor_name,
        body_name=body_name,
        stop_at_burnout=stop_at_burnout,
        t_max_s=t_max_s,
    )

    for angle_deg in angles_deg:
        angle_float = float(angle_deg)
        params = replace(
            base_params,
            launch_angle_deg=angle_float,
        )
        sol = integrate_boost_phase(params)
        result = postprocess(sol, params)
        entry = {
            "launch_angle_deg": float(angle_deg),
            "burnout_mach": result["burnout_mach"],
            "burnout_altitude": result["burnout_altitude"],
            "burnout_range": result["range_at_burnout"],
            "q_max": result["q_max"],
            "ground_impact_flag": bool(
                result["metadata"]["ground_impact_before_burnout"]
            ),
        }
        if not stop_at_burnout:
            entry["apogee_altitude"] = result["apogee_altitude"]
            entry["flight_time"] = result["flight_time"]
            entry["flight_range"] = result["flight_range"]
        sweep_results.append(entry)
    return sweep_results


def format_sweep_csv(sweep_results: list[dict[str, Any]]) -> str:
    """Format the launch-angle sweep results as a CSV string.

    Args:
        sweep_results: Output of :func:`run_launch_angle_sweep`.

    Returns:
        String containing CSV-formatted sweep data.
    """
    if not sweep_results:
        return ""
    fieldnames = list(sweep_results[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for entry in sweep_results:
        writer.writerow({key: entry.get(key, "") for key in fieldnames})
    return buf.getvalue()


def plot_launch_angle_sweep(
    sweep_results: list[dict[str, Any]],
    *,
    ground_altitude_m: float = PointMass3DOFBoostAnalysis.DEFAULT_GROUND_ALTITUDE_M,
) -> Figure:
    """Plot burnout Mach and burnout/apogee altitude vs. launch angle.

    All figure saving is handled by :class:`~YAADO_Core.Foundation.flight_logger.FlightLogger`.

    Args:
        sweep_results: Output of :func:`run_launch_angle_sweep`.
        ground_altitude_m: Ground impact plane altitude [m].

    Returns:
        The matplotlib Figure instance.
    """
    import matplotlib.pyplot as plt

    if not sweep_results:
        fig, ax = plt.subplots(figsize=(6, 4))
        return fig

    angles_deg = [entry["launch_angle_deg"] for entry in sweep_results]
    mach_vals = [entry["burnout_mach"] for entry in sweep_results]
    alt_vals = [entry["burnout_altitude"] for entry in sweep_results]
    has_apogee = bool("apogee_altitude" in sweep_results[0])

    n_cols = 3 if has_apogee else 2
    fig, axes = plt.subplots(1, n_cols, figsize=(5 * n_cols, 4))

    # 1. Burnout Mach vs launch angle (auto-scaled to highlight sensitivity)
    ax_mach = axes[0]
    ax_mach.plot(angles_deg, mach_vals, marker="o", color="tab:red")
    ax_mach.set_xlabel("Launch angle [deg]")
    ax_mach.set_ylabel("Burnout Mach [-]")
    ax_mach.set_title("Burnout Mach vs. launch angle")
    ax_mach.grid(True, alpha=0.3)

    # 2. Burnout altitude vs launch angle
    ax_burnout = axes[1]
    ax_burnout.plot(angles_deg, alt_vals, marker="o", color="tab:green")
    ax_burnout.axhline(ground_altitude_m, color="k", linewidth=0.8, linestyle="--")
    min_burnout = float(min(alt_vals)) if alt_vals else ground_altitude_m
    ax_burnout.set_ylim(bottom=min(ground_altitude_m, min_burnout))
    ax_burnout.set_xlabel("Launch angle [deg]")
    ax_burnout.set_ylabel("Burnout altitude [m]")
    ax_burnout.set_title("Burnout altitude vs. launch angle")
    ax_burnout.grid(True, alpha=0.3)

    # 3. Apogee altitude vs launch angle (if full flight simulated)
    if has_apogee:
        ax_apogee = axes[2]
        apogee_vals = [entry["apogee_altitude"] for entry in sweep_results]
        ax_apogee.plot(
            angles_deg,
            apogee_vals,
            marker="^",
            color="tab:olive",
            linestyle="--",
        )
        ax_apogee.axhline(ground_altitude_m, color="k", linewidth=0.8, linestyle="--")
        min_apogee = float(min(apogee_vals)) if apogee_vals else ground_altitude_m
        ax_apogee.set_ylim(bottom=min(ground_altitude_m, min_apogee))
        ax_apogee.set_xlabel("Launch angle [deg]")
        ax_apogee.set_ylabel("Apogee altitude [m]")
        ax_apogee.set_title("Apogee altitude vs. launch angle")
        ax_apogee.grid(True, alpha=0.3)

    fig.suptitle("Stage-1 booster: launch-angle sensitivity sweep")
    fig.tight_layout()
    return fig


def run_boost_study(
    vehicle: BaseVehicleConfig,
    *,
    launch_angle_deg: float = PointMass3DOFBoostAnalysis.DEFAULT_LAUNCH_ANGLE_DEG,
    altitude_m: float = PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M,
    ground_altitude_m: float = PointMass3DOFBoostAnalysis.DEFAULT_GROUND_ALTITUDE_M,
    fins_name: str | None = None,
    motor_name: str | None = None,
    body_name: str | None = None,
    stop_at_burnout: bool = PointMass3DOFBoostAnalysis.DEFAULT_STOP_AT_BURNOUT,
    t_max_s: float = PointMass3DOFBoostAnalysis.DEFAULT_T_MAX_S,
    enable_logging: bool = True,
    sweep_angles_deg: Sequence[float] = PointMass3DOFBoostAnalysis.DEFAULT_SWEEP_ANGLES_DEG,
) -> AnalysisResults:
    """Run a complete trajectory study with sensitivity sweep and visual artifacts.

    Orchestrates the 3-DOF trajectory integration, generates visual trajectory
    plots, runs a launch-angle sensitivity sweep, writes the sweep CSV artifact,
    and serializes the results checkpoint via :class:`FlightLogger`.

    Args:
        vehicle: Validated :class:`~YAADO_Core.Foundation.vehicle_base.BaseVehicleConfig` instance.
        launch_angle_deg: Launch elevation angle above horizontal [deg].
            Defaults to :attr:`PointMass3DOFBoostAnalysis.DEFAULT_LAUNCH_ANGLE_DEG`.
        altitude_m: Launch altitude [m]. Defaults to :attr:`PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M`.
        ground_altitude_m: Ground impact plane altitude [m]. Defaults to :attr:`PointMass3DOFBoostAnalysis.DEFAULT_GROUND_ALTITUDE_M`.
        fins_name: Explicit name of fin set in ``vehicle.aero_surfaces``.
        motor_name: Explicit name of motor in ``vehicle.propulsion``.
        body_name: Explicit name of body in ``vehicle.bodies``.
        stop_at_burnout: Boolean controlling whether the simulation ends
            when the booster is depleted (True, default) or continues through
            unpowered coast to ground impact/apogee (False).
        t_max_s: Maximum simulation time [s]. Defaults to :attr:`PointMass3DOFBoostAnalysis.DEFAULT_T_MAX_S`.
        enable_logging: Whether FlightLogger generates disk logs, figures, and checkpoints.
            Defaults to True. Set to False for zero-disk-I/O in sweeps/tests.
        sweep_angles_deg: Sequence of launch angles [deg] to sweep for ground-impact
            sensitivity. Defaults to :attr:`PointMass3DOFBoostAnalysis.DEFAULT_SWEEP_ANGLES_DEG`.

    Returns:
        The baseline :class:`~YAADO_Core.Foundation.analysis_base.AnalysisResults`.

    Raises:
        TypeError: If ``vehicle`` is not a BaseVehicleConfig instance.
    """
    if not isinstance(vehicle, BaseVehicleConfig):
        raise TypeError(
            f"vehicle must be a BaseVehicleConfig instance, got {type(vehicle).__name__}"
        )

    # 1. Baseline analysis
    analysis = PointMass3DOFBoostAnalysis()
    analysis.setup(
        vehicle,
        launch_angle_deg=launch_angle_deg,
        altitude_m=altitude_m,
        ground_altitude_m=ground_altitude_m,
        fins_name=fins_name,
        motor_name=motor_name,
        body_name=body_name,
        stop_at_burnout=stop_at_burnout,
        t_max_s=t_max_s,
        enable_logging=enable_logging,
    )
    results = analysis.execute()
    logger = analysis.logger

    # 2. Visual figure(s)
    ground_alt = float(results.metadata["ground_altitude"])
    boost_samples = results.metadata["_boost_samples"]
    fig_boost = plot_boost_phase(
        boost_samples,
        burn_time_s=results.metadata["nominal_burn_time"],
        ground_altitude_m=ground_alt,
    )
    logger.save_figure(fig_boost, "boost_phase.png")
    if not stop_at_burnout:
        fig_full = plot_full_flight(
            results.metadata["_samples"],
            burn_time_s=results.metadata["nominal_burn_time"],
            ground_altitude_m=ground_alt,
        )
        logger.save_figure(fig_full, "full_flight.png")

    # 3. Parameter sweep: launch angle sensitivity
    logger.info(
        "Running launch-angle sensitivity sweep over %s deg (stop_at_burnout=%s)...",
        list(sweep_angles_deg),
        stop_at_burnout,
    )
    sweep_results = run_launch_angle_sweep(
        vehicle,
        angles_deg=sweep_angles_deg,
        altitude_m=altitude_m,
        ground_altitude_m=ground_altitude_m,
        fins_name=fins_name,
        motor_name=motor_name,
        body_name=body_name,
        stop_at_burnout=stop_at_burnout,
        t_max_s=t_max_s,
    )
    sweep_fig = plot_launch_angle_sweep(sweep_results, ground_altitude_m=ground_alt)
    logger.save_figure(sweep_fig, "launch_angle_sweep.png")

    # 4. Auxiliary artifact: sweep CSV
    logger.save_artifact("launch_angle_sweep.csv", format_sweep_csv(sweep_results))

    # 5. Check for nominal ground impact
    if results.metadata["ground_impact_before_burnout"]:
        logger.warning(
            "Nominal trajectory hit ground before burnout. Check launch angle and initial conditions."
        )

    # Save results checkpoint with study metadata
    logger.save_results(results)
    return results
