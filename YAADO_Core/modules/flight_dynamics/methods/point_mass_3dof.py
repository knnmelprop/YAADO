"""Low-order 3-DOF boost-phase trajectory point-mass integrator.

This module integrates a point-mass, vertical-plane (3-DOF: range, altitude,
and their rates) equation of motion for the solid-propellant booster stage
of a rocket vehicle, from ignition to nominal burnout
(``burn_time`` from the vehicle config) or ground impact, whichever comes
first.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from matplotlib.figure import Figure

import numpy as np
from scipy.integrate import solve_ivp
from scipy.integrate._ivp.ivp import OdeResult

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
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig


@dataclass(frozen=True)
class BoosterParams:
    """Resolved stage-1 booster parameters used by the trajectory ODE.

    Attributes:
        launch_mass_kg: Total vehicle mass at ignition [kg].
        propellant_mass_kg: Propellant mass consumed over the burn [kg].
        burnout_mass_kg: ``launch_mass_kg - propellant_mass_kg`` [kg].
        burn_time_s: Nominal burn duration [s].
        mdot_kg_s: Constant propellant mass flow rate [kg/s].
        isp_sl_s: Sea-level specific impulse [s].
        isp_vacuum_s: Vacuum specific impulse [s].
        thrust_mean_yaml_N: Mean thrust from vehicle YAML [N] (informational).
        a_ref_m2: Reference (body cross-section) area for drag [m^2].
        cd_fins: Constant fin-drag contribution to CD (count * per-fin CD).
        launch_angle_deg: Fixed thrust/body angle above horizontal [deg].
        launch_angle_rad: Fixed thrust/body angle above horizontal [rad].
        cd_body_subsonic: Body drag coefficient for Mach < mach_transonic_lo.
        cd_body_transonic: Body drag coefficient for transonic regime.
        cd_body_supersonic: Body drag coefficient for Mach >= mach_supersonic_lo.
        mach_transonic_lo: Lower Mach bound of the transonic CD step.
        mach_supersonic_lo: Lower Mach bound of the supersonic CD step.
        isp_alt_ref_m: Reference altitude for linear sea-level -> vacuum Isp.
    """

    launch_mass_kg: float
    propellant_mass_kg: float
    burnout_mass_kg: float
    burn_time_s: float
    mdot_kg_s: float
    isp_sl_s: float
    isp_vacuum_s: float
    thrust_mean_yaml_N: float
    a_ref_m2: float
    cd_fins: float
    launch_angle_deg: float
    launch_angle_rad: float
    cd_body_subsonic: float = 0.20
    cd_body_transonic: float = 0.35
    cd_body_supersonic: float = 0.25
    mach_transonic_lo: float = 0.8
    mach_supersonic_lo: float = 1.5
    isp_alt_ref_m: float = 30000.0

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
            "Please specify 'motor_name' in operating_state."
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
            "Please specify 'body_name' in operating_state."
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
            "Please specify 'fins_name' in operating_state."
        )
    return next(iter(aero_surfaces.values()))


def resolve_booster_params_from_vehicle(
    vehicle: BaseVehicleConfig,
    operating_state: dict[str, Any] | None = None,
    *,
    motor_name: str | None = None,
    body_name: str | None = None,
    fins_name: str | None = None,
) -> BoosterParams:
    """Resolve stage-1 booster parameters from a validated vehicle config.

    All mass, propulsion and geometry data is read from ``vehicle``
    (composition of components belonging to :data:`~YAADO_Core.ComponentStore.PROPULSION_COMPONENTS`,
    :data:`~YAADO_Core.ComponentStore.BODY_COMPONENTS`,
    :data:`~YAADO_Core.ComponentStore.AERO_COMPONENTS`, and
    :class:`~YAADO_Core.ComponentStore.mass.MassProperties`). Launch-site
    and operating conditions are read from ``operating_state``.

    Args:
        vehicle: Validated, vehicle-agnostic configuration providing the
            propulsion, body, aero_surfaces (fins) and mass_properties
            components.
        operating_state: Optional operating conditions in SI units.
            Recognized keys: ``launch_angle_deg`` (fixed thrust/body angle
            above horizontal [deg], defaults to
            :attr:`PointMass3DOFBoostAnalysis.DEFAULT_LAUNCH_ANGLE_DEG`),
            component names (``motor_name``, ``body_name``, ``fins_name``, ``aero_name``),
            and drag/Isp calibration overrides.
        motor_name: Optional explicit name of the solid motor in ``vehicle.propulsion``
            (overrides ``operating_state.get("motor_name")`` if both given).
        body_name: Optional explicit name of the body in ``vehicle.bodies``
            (overrides ``operating_state.get("body_name")`` if both given).
        fins_name: Optional explicit name of the fin set in ``vehicle.aero_surfaces``
            (overrides ``operating_state.get("fins_name")`` if both given).

    Returns:
        Resolved :class:`BoosterParams` with the impulse-consistent thrust
        caveat already computed (see :attr:`BoosterParams.thrust_sl_N`).

    Raises:
        ValueError: If ``vehicle`` has no boost-capable propulsion component,
            no body component, no ``mass_properties.total_mass``, or if multiple
            components of a subsystem exist without specifying the component name.
        TypeError: If a specified component name refers to an unregistered component type.
    """
    operating_state = operating_state or {}
    motor_name = motor_name or operating_state.get("motor_name")
    body_name = body_name or operating_state.get("body_name")
    fins_name = (
        fins_name
        or operating_state.get("fins_name")
        or operating_state.get("aero_name")
    )

    launch_angle_deg = float(
        operating_state.get(
            "launch_angle_deg",
            PointMass3DOFBoostAnalysis.DEFAULT_LAUNCH_ANGLE_DEG,
        )
    )
    cd_body_subsonic = float(
        operating_state.get(
            "cd_body_subsonic",
            PointMass3DOFBoostAnalysis.CD_BODY_SUBSONIC,
        )
    )
    cd_body_transonic = float(
        operating_state.get(
            "cd_body_transonic",
            PointMass3DOFBoostAnalysis.CD_BODY_TRANSONIC,
        )
    )
    cd_body_supersonic = float(
        operating_state.get(
            "cd_body_supersonic",
            PointMass3DOFBoostAnalysis.CD_BODY_SUPERSONIC,
        )
    )
    mach_transonic_lo = float(
        operating_state.get(
            "mach_transonic_lo",
            PointMass3DOFBoostAnalysis.MACH_TRANSONIC_LO,
        )
    )
    mach_supersonic_lo = float(
        operating_state.get(
            "mach_supersonic_lo",
            PointMass3DOFBoostAnalysis.MACH_SUPERSONIC_LO,
        )
    )
    cd_wave_per_fin = float(
        operating_state.get(
            "cd_wave_per_fin",
            PointMass3DOFBoostAnalysis.CD_WAVE_PER_FIN,
        )
    )
    isp_alt_ref_m = float(
        operating_state.get(
            "isp_alt_ref_m",
            PointMass3DOFBoostAnalysis.ISP_ALT_REF_M,
        )
    )

    propulsion = _resolve_booster_propulsion(vehicle, motor_name=motor_name)
    body = _resolve_body(vehicle, body_name=body_name)
    fins = _resolve_aero_surface(vehicle, fins_name=fins_name)

    if vehicle.mass_properties is None or vehicle.mass_properties.total_mass is None:
        raise ValueError("vehicle.mass_properties.total_mass is required")

    launch_mass_kg = vehicle.mass_properties.total_mass
    propellant_mass_kg = propulsion.propellant_mass
    burnout_mass_kg = launch_mass_kg - propellant_mass_kg
    burn_time_s = propulsion.burn_time
    mdot_kg_s = propellant_mass_kg / burn_time_s

    d_ref_m = getattr(body, "diameter", None)
    if d_ref_m is None:
        raise ValueError(
            f"Body component '{type(body).__name__}' does not define a 'diameter' attribute"
        )
    a_ref_m2 = math.pi / 4.0 * d_ref_m**2
    if fins is not None:
        fin_count = getattr(fins, "count", 2)
        cd_fins = fin_count * cd_wave_per_fin
    else:
        cd_fins = 0.0

    return BoosterParams(
        launch_mass_kg=launch_mass_kg,
        propellant_mass_kg=propellant_mass_kg,
        burnout_mass_kg=burnout_mass_kg,
        burn_time_s=burn_time_s,
        mdot_kg_s=mdot_kg_s,
        isp_sl_s=float(propulsion.isp_sl),
        isp_vacuum_s=float(getattr(propulsion, "isp_vacuum", propulsion.isp_sl)),
        thrust_mean_yaml_N=float(getattr(propulsion, "thrust_mean", 0.0)),
        a_ref_m2=a_ref_m2,
        cd_fins=cd_fins,
        launch_angle_deg=launch_angle_deg,
        launch_angle_rad=math.radians(launch_angle_deg),
        cd_body_subsonic=cd_body_subsonic,
        cd_body_transonic=cd_body_transonic,
        cd_body_supersonic=cd_body_supersonic,
        mach_transonic_lo=mach_transonic_lo,
        mach_supersonic_lo=mach_supersonic_lo,
        isp_alt_ref_m=isp_alt_ref_m,
    )


def load_booster_params(
    config_path: Path | str,
    launch_angle_deg: float | None = None,
    *,
    motor_name: str | None = None,
    body_name: str | None = None,
    fins_name: str | None = None,
) -> BoosterParams:
    """Load stage-1 booster parameters from the rocket vehicle config file.

    Thin file-loading wrapper around :func:`resolve_booster_params_from_vehicle`
    for standalone script/CLI use (:func:`main`, :func:`run_launch_angle_sweep`).
    Analyses embedded in an MDO workflow should call
    :meth:`PointMass3DOFBoostAnalysis.setup` with an already-validated
    ``vehicle`` object instead of reading from disk.

    Args:
        config_path: Path to vehicle config file.
        launch_angle_deg: Fixed thrust/body angle above horizontal [deg].
            Defaults to :attr:`PointMass3DOFBoostAnalysis.DEFAULT_LAUNCH_ANGLE_DEG` (83.0 deg);
            overridden by :func:`run_launch_angle_sweep` to explore shallower angles.
        motor_name: Optional explicit name of the solid motor in ``vehicle.propulsion``.
        body_name: Optional explicit name of the body in ``vehicle.bodies``.
        fins_name: Optional explicit name of the fin set in ``vehicle.aero_surfaces``.

    Returns:
        Resolved :class:`BoosterParams` with the impulse-consistent thrust
        caveat already computed (see :attr:`BoosterParams.thrust_sl_N`).

    Raises:
        ValueError: If the loaded config is missing required components
            (see :func:`resolve_booster_params_from_vehicle`).
    """
    if launch_angle_deg is None:
        launch_angle_deg = PointMass3DOFBoostAnalysis.DEFAULT_LAUNCH_ANGLE_DEG
    vehicle = BaseVehicleConfig.from_toml(Path(config_path))
    return resolve_booster_params_from_vehicle(
        vehicle,
        operating_state={"launch_angle_deg": launch_angle_deg},
        motor_name=motor_name,
        body_name=body_name,
        fins_name=fins_name,
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
    speed_ms, mach, _q_pa, density_kg_m3 = flow_state((vx, vh), h)

    cd_total = drag_coefficient(mach, params)
    drag_N = 0.5 * density_kg_m3 * speed_ms**2 * cd_total * params.a_ref_m2

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
    thrust_x_N = thrust_N * math.cos(params.launch_angle_rad)
    thrust_h_N = thrust_N * math.sin(params.launch_angle_rad)

    ax_ms2 = (thrust_x_N - drag_N * ux) / mass_kg
    ah_ms2 = (thrust_h_N - drag_N * uh) / mass_kg - const.G0

    return [vx, vh, ax_ms2, ah_ms2]


def _ground_impact_event(t_s: float, state: np.ndarray, params: BoosterParams) -> float:
    """Zero-crossing event: altitude reaching 0 m (terminal, decreasing)."""
    return state[1]


def integrate_boost_phase(
    params: BoosterParams,
    h0_m: float | None = None,
) -> OdeResult:
    """Integrate the boost-phase trajectory from ignition to burnout/impact.

    Args:
        params: Booster parameters from :func:`load_booster_params` or
            :func:`resolve_booster_params_from_vehicle`.
        h0_m: Initial altitude [m] at ignition. Defaults to
            :attr:`PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M`; this is a
            launch-site condition with no field on
            :class:`~YAADO_Core.Foundation.vehicle_base.BaseVehicleConfig`,
            so callers building it from ``operating_state`` (e.g.
            ``operating_state["altitude_m"]``) should pass it explicitly.

    Returns:
        The ``scipy.integrate.solve_ivp`` result, with dense output enabled.
    """
    if h0_m is None:
        h0_m = PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M

    # solve_ivp appends `args` to every callable passed via `events` as
    # well as `fun`, so `_ground_impact_event` must accept `params` as a
    # positional arg directly (a closure lambda would double up args).
    _ground_impact_event.terminal = True
    _ground_impact_event.direction = -1.0

    y0 = [
        PointMass3DOFBoostAnalysis.DEFAULT_X0_M,
        h0_m,
        PointMass3DOFBoostAnalysis.DEFAULT_V0_MS,
        PointMass3DOFBoostAnalysis.DEFAULT_V0_MS,
    ]
    sol = solve_ivp(
        fun=boost_dynamics,
        t_span=(0.0, params.burn_time_s),
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


def postprocess(
    sol: OdeResult,
    params: BoosterParams,
    h0_m: float | None = None,
) -> dict[str, Any]:
    """Derive burnout state, q_max, and dense sample arrays from the solution.

    Args:
        sol: Result from :func:`integrate_boost_phase` (dense output).
        params: Booster parameters.
        h0_m: Initial altitude [m] used for the integration (see
            :func:`integrate_boost_phase`), reported back in the metadata.
            Defaults to :attr:`PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M`.

    Returns:
        Dict with scalar results, a ``metadata`` sub-dict, and a
        ``_samples`` sub-dict of dense arrays for plotting (not written to
        the JSON report as-is; see :func:`main`).
    """
    if h0_m is None:
        h0_m = PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M

    t_end_s = float(sol.t[-1])
    ground_impact = bool(len(sol.t_events[0]) > 0)

    t_fine = np.linspace(0.0, t_end_s, PointMass3DOFBoostAnalysis.N_DENSE_SAMPLES)
    y_fine = sol.sol(t_fine)
    x_fine, h_fine, vx_fine, vh_fine = y_fine

    speed_fine = np.hypot(vx_fine, vh_fine)
    mach_fine = np.empty_like(t_fine)
    q_fine = np.empty_like(t_fine)
    for i in range(len(t_fine)):
        _, mach_fine[i], q_fine[i], _ = flow_state((vx_fine[i], vh_fine[i]), h_fine[i])

    q_max_idx = int(np.argmax(q_fine))
    q_max_pa = float(q_fine[q_max_idx])

    x_end, h_end, vx_end, vh_end = (
        float(x_fine[-1]),
        float(h_fine[-1]),
        float(vx_fine[-1]),
        float(vh_fine[-1]),
    )
    v_end = float(speed_fine[-1])
    mach_end = float(mach_fine[-1])

    thrust_used_N = params.thrust_sl_N

    result: dict[str, Any] = {
        "burnout_time": t_end_s,
        "burnout_velocity": v_end,
        "burnout_mach": mach_end,
        "burnout_altitude": h_end,
        "q_max": q_max_pa,
        "range_at_burnout": x_end,
        "metadata": {
            "burnout_vx": vx_end,
            "burnout_vh": vh_end,
            "nominal_burn_time": params.burn_time_s,
            "integration_stopped_reason": "ground_impact" if ground_impact else "burnout",
            "ground_impact_before_burnout": ground_impact,
            "model_limitations": (
                "Point-mass 3-DOF with fixed launch angle (no pitch program). "
                "Zero-lift gravity-turn approximation: thrust along body axis "
                f"at {params.launch_angle_deg:.1f} deg, no explicit lift force. "
                "Angle-of-attack effects neglected. Reasonable for near-vertical "
                "boost phase; higher-fidelity models would include 6-DOF pitch "
                "dynamics and alpha-dependent lift/moment."
            ),
            "thrust_used": thrust_used_N,
            "thrust_yaml_mean": params.thrust_mean_yaml_N,
            "thrust_note": (
                f"Impulse-consistent thrust F = Isp_sl * mdot * g0 = {thrust_used_N:.0f} N. "
                f"YAML thrust_mean_N = {params.thrust_mean_yaml_N:.0f} N is now schema-validated "
                "for consistency (peak >= mean, mean consistent with Isp*mdot*g0)."
            ),
            "isp_sl": params.isp_sl_s,
            "isp_vacuum": params.isp_vacuum_s,
            "isp_interpolation": (
                "linear in altitude from isp_sl at h=0 to isp_vacuum at "
                f"h={params.isp_alt_ref_m:.0f} m, clamped beyond; negligible effect "
                f"here since altitude stays near h0={h0_m:.0f} m"
            ),
            "mdot": params.mdot_kg_s,
            "launch_mass": params.launch_mass_kg,
            "burnout_mass": params.burnout_mass_kg,
            "mass_at_stop": mass_at_time(t_end_s, params),
            "launch_angle": params.launch_angle_deg,
            "initial_altitude": h0_m,
            "reference_area": params.a_ref_m2,
            "cd_fins": params.cd_fins,
            "atmosphere_model": (
                "ISA troposphere (ICAO Doc 7488 manual formula via ambiance), "
                "valid from -5000 m to 80000 m"
            ),
            "cd_model": (
                f"CD_body: {params.cd_body_subsonic:.2f} (M<{params.mach_transonic_lo:.1f}) / "
                f"{params.cd_body_transonic:.2f} ({params.mach_transonic_lo:.1f}<=M<{params.mach_supersonic_lo:.1f}, transonic) / "
                f"{params.cd_body_supersonic:.2f} (M>={params.mach_supersonic_lo:.1f}); step function, not smoothed. "
                f"CD_fins = {params.cd_fins:.4f} (constant). CD_total = CD_body + CD_fins."
            ),
            "integrator": (
                f"scipy.integrate.solve_ivp, RK45, rtol={PointMass3DOFBoostAnalysis.RTOL}, atol={PointMass3DOFBoostAnalysis.ATOL}, "
                "dense_output=True, terminal ground-impact event (h=0, "
                "decreasing)"
            ),
        },
        "_samples": {
            "t_s": t_fine,
            "x_m": x_fine,
            "h_m": h_fine,
            "v_ms": speed_fine,
            "mach": mach_fine,
            "q_pa": q_fine,
            "q_max_idx": q_max_idx,
        },
    }
    return result


class PointMass3DOFBoostAnalysis(BaseAnalysis):
    """3-DOF point-mass boost-phase trajectory analysis.

    Wraps the ISA atmosphere, drag build-up and boost-phase
    ODE integration as a :class:`BaseAnalysis`. Point-mass analytical
    integration with empirical drag/Isp correlations ->
    ``FidelityLevel.LEVEL_0``.

    Example:
        >>> analysis = PointMass3DOFBoostAnalysis()
        >>> analysis.setup(vehicle)  # doctest: +SKIP
        >>> results = analysis.execute()  # doctest: +SKIP
        >>> results["burnout_mach"]  # doctest: +SKIP
    """

    fidelity = FidelityLevel.LEVEL_0

    # Default launch conditions
    DEFAULT_LAUNCH_ANGLE_DEG: float = 83.0
    DEFAULT_ALTITUDE_M: float = 100.0
    DEFAULT_X0_M: float = 0.0
    DEFAULT_V0_MS: float = 0.0

    # Empirical drag parameters (can be calibrated per vehicle via operating_state)
    CD_BODY_SUBSONIC: float = 0.20
    CD_BODY_TRANSONIC: float = 0.35
    CD_BODY_SUPERSONIC: float = 0.25
    MACH_TRANSONIC_LO: float = 0.8
    MACH_SUPERSONIC_LO: float = 1.5
    CD_WAVE_PER_FIN: float = 0.012

    # Propulsion & numerical solver settings
    ISP_ALT_REF_M: float = 30000.0
    RTOL: float = 1e-8
    ATOL: float = 1e-10
    N_DENSE_SAMPLES: int = 4001
    VELOCITY_EPS_MS: float = 1e-6
    DEFAULT_SWEEP_ANGLES_DEG: tuple[float, ...] = (5.0, 10.0, 15.0, 20.0, 25.0, 30.0)

    def __init__(self, name: str = "point_mass_3dof_boost") -> None:
        super().__init__(name)
        self._params: BoosterParams | None = None
        self._h0_m: float = self.DEFAULT_ALTITUDE_M

    def setup(
        self,
        vehicle: BaseVehicleConfig,
        operating_state: dict[str, Any] | None = None,
    ) -> None:
        """Bind the analysis to a vehicle config and operating conditions.

        Mass, propulsion (``SolidMotor``) and geometry (``AxisymmetricBody``
        body diameter, ``Fins`` count) are read from ``vehicle``. The fixed
        launch angle and initial altitude are launch-site conditions with
        no field on :class:`~YAADO_Core.Foundation.vehicle_base.BaseVehicleConfig`,
        so they are read from ``operating_state`` instead (see
        :func:`resolve_booster_params_from_vehicle`). Drag and Isp parameters
        can also be calibrated via ``operating_state``.

        Args:
            vehicle: Validated, vehicle-agnostic configuration providing
                the propulsion, body, aero_surfaces (fins) and
                mass_properties components used by the boost-phase model.
            operating_state: Optional operating conditions in SI units.
                Recognized keys: ``launch_angle_deg`` (defaults to
                :attr:`DEFAULT_LAUNCH_ANGLE_DEG`), ``altitude_m`` (defaults
                to :attr:`DEFAULT_ALTITUDE_M`), and drag/Isp overrides
                (``cd_body_subsonic``, ``cd_body_transonic``, ``cd_body_supersonic``,
                ``mach_transonic_lo``, ``mach_supersonic_lo``, ``cd_wave_per_fin``,
                ``isp_alt_ref_m``). ``None`` falls back to all defaults.

        Raises:
            ValueError: If ``vehicle`` is missing a required component
                (see :func:`resolve_booster_params_from_vehicle`).
        """
        operating_state = operating_state or {}
        self._params = resolve_booster_params_from_vehicle(vehicle, operating_state)
        self._h0_m = float(operating_state.get("altitude_m", self.DEFAULT_ALTITUDE_M))
        self._is_setup = True

    def execute(self) -> AnalysisResults:
        """Integrate the boost-phase trajectory and return results.

        Returns:
            AnalysisResults with ``burnout_time``, ``burnout_velocity``,
            ``burnout_mach``, ``burnout_altitude``, ``q_max`` and
            ``range_at_burnout`` in SI units. ``units`` maps each key
            to its SI unit string. ``metadata`` carries the full
            postprocessing breakdown (model documentation, resolved
            booster parameters, and dense trajectory samples under
            ``_samples``).

        Raises:
            RuntimeError: If called before :meth:`setup`, or if results
                fail the analytical sanity check.
        """
        if not self._is_setup or self._params is None:
            raise RuntimeError(
                "PointMass3DOFBoostAnalysis.execute() called before setup()"
            )

        sol = integrate_boost_phase(self._params, h0_m=self._h0_m)
        result = postprocess(sol, self._params, h0_m=self._h0_m)

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
        metadata = dict(result["metadata"])
        samples = result["_samples"]
        metadata["_samples"] = {
            key: value.tolist() if isinstance(value, np.ndarray) else value
            for key, value in samples.items()
        }

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
        return results

    def validate_results(self, results: AnalysisResults) -> bool:
        """Sanity-check the burnout state against physical bounds.

        Checks that ``burnout_time``, ``burnout_velocity`` and
        ``q_max`` are non-negative and finite, and that
        ``burnout_altitude`` is not below ground level (the terminal
        ground-impact event should have stopped the integration at or
        above ``h = 0``).

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        if not results.data:
            return False
        for key in ("burnout_time", "burnout_velocity", "q_max"):
            value = results[key]
            if not math.isfinite(value) or value < 0.0:
                return False
        if results["burnout_altitude"] < -1e-6:
            return False
        return True


def plot_boost_phase(
    samples: dict[str, Any], output_path: Path | str | None = None
) -> Figure:
    """Plot V(t), h(t), Mach(t), q(t) in a 2x2 grid and optionally save to PNG.

    Args:
        samples: The ``_samples`` sub-dict returned by :func:`postprocess`.
        output_path: Optional destination PNG path. If None, figure is not saved.

    Returns:
        The matplotlib Figure instance.
    """
    import matplotlib.pyplot as plt
    t_s = samples["t_s"]
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))

    ax = axes[0, 0]
    ax.plot(t_s, samples["v_ms"], color="tab:blue")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Velocity [m/s]")
    ax.set_title("Speed vs. time")
    ax.grid(True, alpha=0.3)

    ax = axes[0, 1]
    ax.plot(t_s, samples["h_m"], color="tab:green")
    ax.axhline(0.0, color="k", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Altitude [m]")
    ax.set_title("Altitude vs. time")
    ax.grid(True, alpha=0.3)

    ax = axes[1, 0]
    ax.plot(t_s, samples["mach"], color="tab:red")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Mach number [-]")
    ax.set_title("Mach vs. time")
    ax.grid(True, alpha=0.3)

    ax = axes[1, 1]
    ax.plot(t_s, samples["q_pa"], color="tab:purple")
    q_max_idx = samples["q_max_idx"]
    ax.scatter(
        [t_s[q_max_idx]],
        [samples["q_pa"][q_max_idx]],
        color="k",
        zorder=5,
        label="q_max",
    )
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Dynamic pressure [Pa]")
    ax.set_title("Dynamic pressure vs. time")
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.suptitle("Stage-1 booster boost-phase trajectory (3-DOF point mass)")
    fig.tight_layout()
    if output_path is not None:
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
    return fig


def run_launch_angle_sweep(
    vehicle_or_path: BaseVehicleConfig | Path | str,
    angles_deg: Sequence[float] = PointMass3DOFBoostAnalysis.DEFAULT_SWEEP_ANGLES_DEG,
) -> list[dict[str, Any]]:
    """Sweep the fixed launch angle and report burnout/impact metrics per angle.

    For each angle, the boost phase is re-integrated from ignition with
    overridden ``launch_angle_deg``, then the resulting trajectory is
    post-processed.

    Args:
        vehicle_or_path: Validated BaseVehicleConfig instance or Path/str to config file.
        angles_deg: Launch angles [deg] to sweep. Defaults to
            :attr:`PointMass3DOFBoostAnalysis.DEFAULT_SWEEP_ANGLES_DEG`
            (``5, 10, 15, 20, 25, 30``).

    Returns:
        A list of per-angle result dicts, one per swept angle, each with
        keys ``launch_angle_deg``, ``burnout_mach``, ``burnout_altitude``,
        ``burnout_range``, ``max_q``, and ``ground_impact_flag`` (bool,
        ``True`` if altitude reached ``<= 0 m`` before nominal burnout).
    """
    sweep_results: list[dict[str, Any]] = []
    for angle_deg in angles_deg:
        if isinstance(vehicle_or_path, BaseVehicleConfig):
            params = resolve_booster_params_from_vehicle(
                vehicle_or_path, operating_state={"launch_angle_deg": float(angle_deg)}
            )
        else:
            params = load_booster_params(
                config_path=Path(vehicle_or_path), launch_angle_deg=float(angle_deg)
            )
        sol = integrate_boost_phase(params)
        result = postprocess(sol, params)
        sweep_results.append(
            {
                "launch_angle_deg": float(angle_deg),
                "burnout_mach": result["burnout_mach"],
                "burnout_altitude": result["burnout_altitude"],
                "burnout_range": result["range_at_burnout"],
                "max_q": result["q_max"],
                "ground_impact_flag": bool(
                    result["metadata"]["ground_impact_before_burnout"]
                ),
            }
        )
    return sweep_results


def recommended_launch_angle_deg(sweep_results: list[dict[str, Any]]) -> float | None:
    """Pick the smallest swept launch angle that avoids premature ground impact.

    Args:
        sweep_results: Output of :func:`run_launch_angle_sweep`.

    Returns:
        The smallest ``launch_angle_deg`` among entries with
        ``ground_impact_flag is False``, or ``None`` if every swept angle
        results in ground impact.
    """
    viable_deg = [
        entry["launch_angle_deg"] for entry in sweep_results if not entry["ground_impact_flag"]
    ]
    return min(viable_deg) if viable_deg else None


def write_sweep_csv(
    sweep_results: list[dict[str, Any]], output_path: Path | str
) -> None:
    """Write the launch-angle sweep results to a CSV file.

    Args:
        sweep_results: Output of :func:`run_launch_angle_sweep`.
        output_path: Destination CSV path.
    """
    fieldnames = [
        "launch_angle_deg",
        "burnout_mach",
        "burnout_altitude",
        "burnout_range",
        "max_q",
        "ground_impact_flag",
    ]
    with Path(output_path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in sweep_results:
            writer.writerow({key: entry[key] for key in fieldnames})


def plot_launch_angle_sweep(
    sweep_results: list[dict[str, Any]], output_path: Path | str | None = None
) -> Figure:
    """Plot burnout Mach and burnout altitude vs. launch angle (2 subplots).

    Args:
        sweep_results: Output of :func:`run_launch_angle_sweep`.
        output_path: Optional destination PNG path. If None, figure is not saved.

    Returns:
        The matplotlib Figure instance.
    """
    import matplotlib.pyplot as plt

    angles_deg = [entry["launch_angle_deg"] for entry in sweep_results]
    mach_vals = [entry["burnout_mach"] for entry in sweep_results]
    alt_vals = [entry["burnout_altitude"] for entry in sweep_results]

    fig, (ax_mach, ax_alt) = plt.subplots(1, 2, figsize=(10, 4))

    ax_mach.plot(angles_deg, mach_vals, marker="o", color="tab:red")
    ax_mach.set_xlabel("Launch angle [deg]")
    ax_mach.set_ylabel("Burnout Mach [-]")
    ax_mach.set_title("Burnout Mach vs. launch angle")
    ax_mach.grid(True, alpha=0.3)

    ax_alt.plot(angles_deg, alt_vals, marker="o", color="tab:green")
    ax_alt.axhline(0.0, color="k", linewidth=0.8, linestyle="--")
    ax_alt.set_xlabel("Launch angle [deg]")
    ax_alt.set_ylabel("Burnout altitude [m]")
    ax_alt.set_title("Burnout altitude vs. launch angle")
    ax_alt.grid(True, alpha=0.3)

    fig.suptitle("Stage-1 booster: launch-angle sensitivity sweep")
    fig.tight_layout()
    if output_path is not None:
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
    return fig


def main(
    config_path: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Run the boost-phase simulation, print, and write JSON + PNG outputs.

    Args:
        config_path: Path to vehicle TOML config file. If None, reads from sys.argv[1].
        output_dir: Optional output directory where plots and reports are saved.
            Defaults to current working directory.

    Returns:
        The JSON-serializable result dict (without the internal
        ``_samples`` key).
    """
    if config_path is None:
        if len(sys.argv) > 1:
            config_path = Path(sys.argv[1])
        else:
            raise ValueError(
                "A vehicle config path must be provided: main(config_path) or python point_mass_3dof.py <path_to_config>"
            )

    config_path = Path(config_path)
    out_dir = Path(output_dir) if output_dir else Path.cwd()
    output_json_path = out_dir / "boost_phase.json"
    output_png_path = out_dir / "boost_phase.png"
    sweep_csv_path = out_dir / "launch_angle_sweep.csv"
    sweep_png_path = out_dir / "launch_angle_sweep.png"

    params = load_booster_params(config_path)
    sol = integrate_boost_phase(params)
    result = postprocess(sol, params)
    samples = result.pop("_samples")

    plot_boost_phase(samples, output_path=output_png_path)

    sweep_results = run_launch_angle_sweep(config_path)
    write_sweep_csv(sweep_results, output_path=sweep_csv_path)
    plot_launch_angle_sweep(sweep_results, output_path=sweep_png_path)
    result["recommended_launch_angle_deg"] = recommended_launch_angle_deg(sweep_results)

    output_json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("Boost-phase trajectory results (stage-1 booster):")
    print(json.dumps(result, indent=2))
    print(f"\nWrote {output_json_path}")
    print(f"Wrote {output_png_path}")
    print(f"Wrote {sweep_csv_path}")
    print(f"Wrote {sweep_png_path}")
    print(f"Recommended launch angle: {result['recommended_launch_angle_deg']} deg")

    if result["metadata"]["ground_impact_before_burnout"]:
        print(
            f"\nWARNING: trajectory hit ground at t={result['burnout_time']:.3f} s, "
            f"before nominal {params.burn_time_s:.1f} s burnout. Check launch angle "
            "and initial conditions."
        )

    return result


if __name__ == "__main__":
    main()
