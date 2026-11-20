"""Parachute descent after apogee: drogue, then main, planar point-mass model.

The analysis starts from the apogee state of a full 3-DOF flight
(:class:`~YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof.PointMass3DOFBoostAnalysis`
with ``stop_at_burnout=False``) and does not change the boost dynamics. The vehicle has
its burnout mass. The drogue opens at apogee and the main at a given altitude above
the ground; both open instantly (no opening-shock or inflation model). Drag opposes the
velocity relative to the air (no wind), with the density from the ISA model.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import OptimizeResult

import YAADO_Core.Foundation.constants as const
from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.atmosphere import isa_atmosphere, isa_atmosphere_array
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.flight_dynamics.containers import (
    DescentSamples,
    ParachuteConfig,
    ParachuteDescentResults,
    PointMassBoostResults,
)
from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
    resolve_booster_params_from_vehicle,
)

if TYPE_CHECKING:
    from matplotlib.figure import Figure

RTOL: float = 1e-8
ATOL: float = 1e-8
N_SAMPLES_PER_PHASE: int = 1500
VELOCITY_EPS_MS: float = 1e-9
T_MAX_S: float = 7200.0


def _circle_area(diameter_m: float) -> float:
    """Area of a circle of the given diameter [m^2]."""
    return 0.25 * math.pi * diameter_m**2


def steady_descent_speed(
    mass_kg: float, cd: float, diameter_m: float, altitude_m: float = 0.0
) -> float:
    """Steady descent speed under a parachute, ``v = sqrt(2 m g / (rho Cd A))``.

    Args:
        mass_kg: Vehicle mass [kg].
        cd: Parachute drag coefficient (based on its reference area).
        diameter_m: Parachute reference diameter [m].
        altitude_m: Altitude where the air density is evaluated [m].

    Returns:
        Steady descent speed [m/s].
    """
    rho = isa_atmosphere(altitude_m).density
    return math.sqrt(2.0 * mass_kg * const.G0 / (rho * cd * _circle_area(diameter_m)))


def size_main_diameter(
    mass_kg: float, target_speed_ms: float, cd: float, altitude_m: float = 0.0
) -> float:
    """Main parachute diameter for a target steady descent speed.

    ``D = sqrt(8 m g / (pi rho Cd v^2))``, with the density at ``altitude_m`` (use the
    landing altitude to size for the landing speed).

    Args:
        mass_kg: Vehicle mass [kg].
        target_speed_ms: Wanted steady descent speed [m/s] (> 0).
        cd: Parachute drag coefficient (> 0).
        altitude_m: Altitude where the air density is evaluated [m].

    Returns:
        Parachute reference diameter [m].

    Raises:
        ValueError: If the mass, speed or drag coefficient is not positive.
    """
    if mass_kg <= 0.0 or target_speed_ms <= 0.0 or cd <= 0.0:
        raise ValueError("mass_kg, target_speed_ms and cd must be positive.")
    rho = isa_atmosphere(altitude_m).density
    return math.sqrt(
        8.0 * mass_kg * const.G0 / (math.pi * rho * cd * target_speed_ms**2)
    )


def _descent_dynamics(
    _t_s: float, state: np.ndarray, mass_kg: float, cd: float, area_m2: float
) -> list[float]:
    """Planar point-mass dynamics under a parachute. State ``[x, h, vx, vh]``."""
    _x, h, vx, vh = state
    speed = math.hypot(vx, vh)
    drag_n = 0.5 * isa_atmosphere(h).density * speed**2 * cd * area_m2
    if speed > VELOCITY_EPS_MS:
        ux, uh = vx / speed, vh / speed
    else:
        ux, uh = 0.0, 0.0
    return [vx, vh, -drag_n * ux / mass_kg, -drag_n * uh / mass_kg - const.G0]


def _make_altitude_event(altitude_m: float) -> Any:
    """Terminal event: altitude falling through ``altitude_m``."""

    def event(_t_s: float, state: np.ndarray, *_args: float) -> float:
        return float(state[1]) - altitude_m

    setattr(event, "terminal", True)  # noqa: B010
    setattr(event, "direction", -1.0)  # noqa: B010
    return event


def _integrate_phase(
    t0_s: float,
    state0: np.ndarray,
    stop_altitude_m: float,
    mass_kg: float,
    cd: float,
    diameter_m: float,
) -> OptimizeResult:
    """Integrate one parachute phase until the altitude falls to ``stop_altitude_m``."""
    sol = solve_ivp(
        _descent_dynamics,
        (t0_s, t0_s + T_MAX_S),
        state0,
        method="RK45",
        args=(mass_kg, cd, _circle_area(diameter_m)),
        rtol=RTOL,
        atol=ATOL,
        dense_output=True,
        events=_make_altitude_event(stop_altitude_m),
    )
    if not sol.success or len(sol.t_events[0]) == 0:
        raise RuntimeError(
            f"Descent integration did not reach {stop_altitude_m:.1f} m: {sol.message}"
        )
    return sol


def simulate_descent(
    mass_kg: float,
    apogee_time_s: float,
    apogee_range_m: float,
    apogee_altitude_m: float,
    horizontal_speed_ms: float,
    ground_altitude_m: float,
    parachutes: ParachuteConfig,
) -> tuple[DescentSamples, float]:
    """Integrate the descent from apogee to the ground.

    Args:
        mass_kg: Vehicle mass [kg].
        apogee_time_s: Flight time at apogee [s]; the returned times start here.
        apogee_range_m: Downrange position at apogee [m].
        apogee_altitude_m: Apogee altitude [m].
        horizontal_speed_ms: Horizontal speed at apogee [m/s].
        ground_altitude_m: Ground plane altitude [m].
        parachutes: Drogue and main parachute inputs.

    Returns:
        ``(samples, main_deployment_time_s)`` where the time in the samples is flight
        time and ``main_deployment_time_s`` is measured from apogee.

    Raises:
        ValueError: If the apogee is not above the ground.
    """
    if apogee_altitude_m <= ground_altitude_m:
        raise ValueError("The apogee must be above the ground plane.")

    main_altitude_m = ground_altitude_m + parachutes.main_deployment_altitude
    state = np.array([apogee_range_m, apogee_altitude_m, horizontal_speed_ms, 0.0])
    t_start_s = 0.0
    segments: list[np.ndarray] = []
    times: list[np.ndarray] = []

    if apogee_altitude_m > main_altitude_m:
        drogue = _integrate_phase(
            t_start_s,
            state,
            main_altitude_m,
            mass_kg,
            parachutes.drogue_cd,
            parachutes.drogue_diameter,
        )
        t_open_s = float(drogue.t_events[0][0])
        t_grid = np.linspace(t_start_s, t_open_s, N_SAMPLES_PER_PHASE)
        segments.append(drogue.sol(t_grid))
        times.append(t_grid)
        state = np.asarray(drogue.sol(t_open_s))
        t_start_s = t_open_s

    main_open_idx = sum(len(t) for t in times)
    main = _integrate_phase(
        t_start_s,
        state,
        ground_altitude_m,
        mass_kg,
        parachutes.main_cd,
        parachutes.main_diameter,
    )
    t_land_s = float(main.t_events[0][0])
    t_grid = np.linspace(t_start_s, t_land_s, N_SAMPLES_PER_PHASE)
    segments.append(main.sol(t_grid))
    times.append(t_grid)

    y = np.concatenate(segments, axis=1)
    t = np.concatenate(times)
    samples = DescentSamples(
        t_s=t + apogee_time_s,
        x_m=y[0],
        h_m=y[1],
        vx_ms=y[2],
        vh_ms=y[3],
        speed_ms=np.hypot(y[2], y[3]),
        main_open_idx=main_open_idx,
    )
    return samples, t_start_s


class ParachuteDescentAnalysis(BaseAnalysis[ParachuteDescentResults]):
    """Drogue and main parachute descent from the apogee of a 3-DOF flight.

    Example:
        flight_analysis = PointMass3DOFBoostAnalysis()
        flight_analysis.setup(vehicle, stop_at_burnout=False)
        flight = flight_analysis.execute()

        analysis = ParachuteDescentAnalysis()
        analysis.setup(vehicle, flight=flight, parachutes=config)
        descent = analysis.execute()
    """

    fidelity = FidelityLevel.LEVEL_0

    def __init__(self, name: str = "parachute_descent") -> None:
        super().__init__(name)
        self._flight: PointMassBoostResults | None = None
        self._parachutes: ParachuteConfig | None = None
        self._mass_kg: float = 0.0

    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        flight: PointMassBoostResults | None = None,
        parachutes: ParachuteConfig | None = None,
        motor_name: str | None = None,
        body_name: str | None = None,
        fins_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Bind the analysis to a vehicle, a full 3-DOF flight and the parachute inputs.

        Args:
            vehicle: Vehicle configuration; the descent mass is its burnout mass.
            flight: Results of a full 3-DOF flight (``stop_at_burnout=False``), with samples.
            parachutes: Drogue and main parachute inputs.
            motor_name: Optional motor name, as for the 3-DOF analysis.
            body_name: Optional body name.
            fins_name: Optional fin set name.

        Raises:
            ValueError: If ``flight`` or ``parachutes`` is missing, or ``flight`` has no
                samples or ends before apogee.
        """
        if flight is None or parachutes is None:
            raise ValueError("setup() needs both 'flight' and 'parachutes'.")
        samples = flight.samples
        if samples is None:
            raise ValueError("flight must contain trajectory samples.")
        if samples.apogee_idx >= len(samples.t_s) - 1 and not flight.ground_impact:
            raise ValueError(
                "flight ends at its highest point: run the 3-DOF analysis with stop_at_burnout=False."
            )
        params = resolve_booster_params_from_vehicle(
            vehicle, motor_name=motor_name, body_name=body_name, fins_name=fins_name
        )
        self._flight = flight
        self._parachutes = parachutes
        self._mass_kg = params.burnout_mass_kg
        self.logger.info(
            "Configured parachute descent for '%s': m=%.2f kg, apogee=%.0f m, main at %.0f m AGL",
            vehicle.name,
            self._mass_kg,
            flight.apogee_altitude,
            parachutes.main_deployment_altitude,
        )

    def _compute(self, **kwargs: Any) -> ParachuteDescentResults:
        """Integrate the descent and return typed results."""
        if self._flight is None or self._parachutes is None:
            raise RuntimeError(
                f"Analysis '{self.name}' must be setup before computation. Call setup() first."
            )
        flight, chutes = self._flight, self._parachutes
        flight_samples = flight.samples
        assert flight_samples is not None
        apogee_idx = flight_samples.apogee_idx
        samples, t_open_s = simulate_descent(
            mass_kg=self._mass_kg,
            apogee_time_s=flight.apogee_time,
            apogee_range_m=flight.apogee_range,
            apogee_altitude_m=flight.apogee_altitude,
            horizontal_speed_ms=float(flight_samples.v_ms[apogee_idx]),
            ground_altitude_m=flight_samples.ground_altitude_m,
            parachutes=chutes,
        )

        open_idx = samples.main_open_idx
        drogue_speed = (
            float(samples.speed_ms[open_idx - 1])
            if open_idx > 0
            else float(samples.speed_ms[0])
        )
        landing_speed = float(samples.speed_ms[-1])

        rho = isa_atmosphere_array(samples.h_m).density
        cd_area = np.where(
            np.arange(len(samples.t_s)) < open_idx,
            chutes.drogue_cd * _circle_area(chutes.drogue_diameter),
            chutes.main_cd * _circle_area(chutes.main_diameter),
        )
        decel = 0.5 * rho * samples.speed_ms**2 * cd_area / self._mass_kg

        limit = chutes.descent_speed_limit
        results = ParachuteDescentResults(
            name=self.name,
            fidelity=self.fidelity,
            mass=self._mass_kg,
            apogee_altitude=flight.apogee_altitude,
            drogue_descent_speed=drogue_speed,
            main_descent_speed=landing_speed,
            descent_time=float(samples.t_s[-1] - samples.t_s[0]),
            main_deployment_time=t_open_s,
            landing_x=float(samples.x_m[-1]),
            peak_deceleration=float(np.max(decel)),
            landing_speed_within_limit=None
            if limit is None
            else landing_speed <= limit,
            samples=samples,
        )
        self.logger.info(
            "Descent: drogue %.1f m/s, landing %.1f m/s, %.0f s, landing x=%.0f m, peak decel %.1f m/s^2",
            results.drogue_descent_speed,
            results.main_descent_speed,
            results.descent_time,
            results.landing_x,
            results.peak_deceleration,
        )
        return results

    def validate_results(self, results: ParachuteDescentResults) -> bool:
        """Check that times and speeds are finite and positive."""
        values = (
            results.drogue_descent_speed,
            results.main_descent_speed,
            results.descent_time,
            results.peak_deceleration,
        )
        return (
            all(math.isfinite(v) and v >= 0.0 for v in values)
            and results.descent_time > 0.0
        )


def plot_descent(samples: DescentSamples) -> Figure:
    """Plot altitude and speed against time for the descent.

    Args:
        samples: Descent samples from :class:`ParachuteDescentResults`.

    Returns:
        A matplotlib figure with ``h(t)`` and ``v(t)`` (total and vertical speed).
    """
    import matplotlib.pyplot as plt

    fig, (ax_h, ax_v) = plt.subplots(2, 1, sharex=True, figsize=(7.0, 6.0))
    t = samples.t_s
    ax_h.plot(t, samples.h_m)
    ax_h.set_ylabel("Altitude [m]")
    ax_v.plot(t, samples.speed_ms, label="speed")
    ax_v.plot(t, -samples.vh_ms, "--", label="descent rate")
    ax_v.set_ylabel("Speed [m/s]")
    ax_v.set_xlabel("Flight time [s]")
    ax_v.legend()
    for ax in (ax_h, ax_v):
        ax.axvline(t[samples.main_open_idx], color="grey", linestyle=":")
        ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


__all__ = [
    "ParachuteDescentAnalysis",
    "plot_descent",
    "simulate_descent",
    "size_main_diameter",
    "steady_descent_speed",
]
