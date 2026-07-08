# MELprop-IADE | analyses.trajectory.booster_burnout | v0.1.0
"""Low-order 3-DOF boost-phase trajectory for the Project B stage-1 booster.

This module integrates a point-mass, vertical-plane (3-DOF: range, altitude,
and their rates) equation of motion for the solid-propellant booster stage
of the MELprop two-stage ramjet rocket, from ignition to nominal burnout
(``burn_time_s`` from the vehicle config) or ground impact, whichever comes
first.

Theory / model references:
    - Equations of motion: point-mass flight mechanics, e.g. Anderson,
      *Introduction to Flight*, ch. 9 (rocket/missile trajectory), or
      Sutton & Biblarz, *Rocket Propulsion Elements*, ch. 4.
    - ISA troposphere model: ICAO Doc 7488 (Manual of the ICAO Standard
      Atmosphere), ``0 <= h < 11000 m`` layer, constant lapse rate.
    - Impulse-consistent thrust ``F = mdot * Isp * g0``: Sutton & Biblarz,
      *Rocket Propulsion Elements*, eq. 2-14.
    - Drag build-up (subsonic/transonic/supersonic step CD, fin wave drag):
      simplified DATCOM-style body + fin drag estimate, consistent with the
      empirical (non-AVL) supersonic aero approach mandated by
      ``CLAUDE.md`` for Project B.

Known open issue (see :func:`main` output and printed warnings):
    The booster is modeled at a 0-degree (horizontal) launch angle per the
    task definition, with thrust fixed along the body axis and no lift.
    Under gravity alone this trajectory sinks toward the ground well before
    the nominal 6 s burnout — a real launch requires a positive launch
    angle and/or lift to stay airborne through burnout. This module reports
    the along-track state honestly, including early ground impact if it
    occurs, and flags it in the output JSON.

Run as a script to integrate the trajectory, print the burnout state, and
write ``burnout_state.json`` + ``boost_phase.png`` next to this file::

    python3 analyses/trajectory/booster_burnout.py
"""

from __future__ import annotations

import json
import math
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.integrate import solve_ivp  # noqa: E402
from scipy.integrate._ivp.ivp import OdeResult  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.schemas.vehicle_schema import BaseVehicleConfig, RocketConfig  # noqa: E402

# --------------------------------------------------------------------------
# Named physical constants (SI units throughout; field/variable names carry
# unit suffixes per CLAUDE.md rule 1).
# --------------------------------------------------------------------------

G0_MS2: float = 9.80665
"""Standard gravity [m/s^2]."""

R_AIR_J_PER_KGK: float = 287.05
"""Specific gas constant of dry air [J/(kg*K)]."""

GAMMA_AIR: float = 1.4
"""Ratio of specific heats for air (calorically perfect gas assumption)."""

T0_ISA_K: float = 288.15
"""ISA sea-level standard temperature [K]."""

P0_ISA_PA: float = 101325.0
"""ISA sea-level standard pressure [Pa]."""

LAPSE_RATE_K_PER_M: float = 0.0065
"""ISA troposphere lapse rate [K/m] (0 <= h < 11000 m)."""

TROPOPAUSE_ALT_M: float = 11000.0
"""Upper bound of the ISA troposphere layer [m]; not expected to be
reached by this low-altitude boost phase, retained as a documented model
boundary only."""

ISA_PRESSURE_EXPONENT: float = G0_MS2 / (LAPSE_RATE_K_PER_M * R_AIR_J_PER_KGK)
"""Barometric exponent ``g0 / (L * R)`` for ``p = p0 * (T / T0)**exponent``.
Evaluates to ~5.2559, matching the commonly quoted ICAO manual value."""

# -- Aerodynamic drag model (step CD vs. Mach; see module docstring) -------

CD_BODY_SUBSONIC: float = 0.20
"""Body drag coefficient for Mach < 0.8."""

CD_BODY_TRANSONIC: float = 0.35
"""Body drag coefficient for 0.8 <= Mach < 1.5 (transonic drag rise)."""

CD_BODY_SUPERSONIC: float = 0.25
"""Body drag coefficient for Mach >= 1.5."""

MACH_TRANSONIC_LO: float = 0.8
"""Lower Mach bound of the transonic CD step."""

MACH_SUPERSONIC_LO: float = 1.5
"""Lower Mach bound of the supersonic CD step."""

CD_WAVE_PER_FIN: float = 0.012
"""Per-fin wave-drag CD estimate, summed over all fins for CD_fins."""

# Note on smoothing: the CD(Mach) law above is left as the literal step
# function requested (no smoothing applied). RK45 with a tight rtol handles
# the two finite jumps by locally shrinking its step size; some local
# convergence-order reduction is expected exactly at Mach 0.8 and 1.5
# crossings but does not affect the adaptive error control's global
# tolerance elsewhere in the trajectory.

ISP_ALT_REF_M: float = 30000.0
"""Reference altitude [m] for linear sea-level -> vacuum Isp interpolation,
``Isp(h) = isp_sl + (isp_vac - isp_sl) * clip(h / ISP_ALT_REF_M, 0, 1)``.
This is a documented approximation (typical altitude by which a small
solid motor's expansion is close to vacuum-optimized); since this boost
phase stays within ~100 m of h0, the correction is negligible (<0.1 s of
Isp) and the task's own suggestion of "just use isp_sl" is recovered to
within that tolerance."""

LAUNCH_ANGLE_DEG: float = 0.0
"""Fixed body-axis / thrust angle above horizontal at launch [deg]."""

H0_M: float = 100.0
"""Initial altitude [m]."""

V0_MS: float = 0.0
"""Initial speed (both range and altitude rate) [m/s]."""

X0_M: float = 0.0
"""Initial downrange position [m]."""

VELOCITY_EPS_MS: float = 1e-6
"""Guard velocity below which the drag/thrust direction unit vector is
taken as undefined (zero) to avoid division by zero."""

N_DENSE_SAMPLES: int = 4001
"""Number of dense-output samples used for plotting and q_max search."""

RTOL: float = 1e-8
"""solve_ivp relative tolerance."""

ATOL: float = 1e-10
"""solve_ivp absolute tolerance."""

THIS_DIR = Path(__file__).resolve().parent
VEHICLE_CONFIG_PATH = THIS_DIR.parents[1] / "vehicles" / "ramjet_rocket" / "vehicle_config.yaml"
OUTPUT_JSON_PATH = THIS_DIR / "burnout_state.json"
OUTPUT_PNG_PATH = THIS_DIR / "boost_phase.png"


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
        thrust_peak_yaml_N: Peak thrust as listed in the vehicle YAML
            (flagged inconsistent, see module docstring).
        a_ref_m2: Reference (body cross-section) area for drag [m^2].
        cd_fins: Constant fin-drag contribution to CD (count * per-fin CD).
        launch_angle_rad: Fixed thrust/body angle above horizontal [rad].
    """

    launch_mass_kg: float
    propellant_mass_kg: float
    burnout_mass_kg: float
    burn_time_s: float
    mdot_kg_s: float
    isp_sl_s: float
    isp_vacuum_s: float
    thrust_peak_yaml_N: float
    a_ref_m2: float
    cd_fins: float
    launch_angle_rad: float

    @property
    def thrust_sl_N(self) -> float:
        """Impulse-consistent thrust at sea level, ``Isp_sl * mdot * g0`` [N]."""
        return self.isp_sl_s * self.mdot_kg_s * G0_MS2


def load_booster_params(config_path: Path = VEHICLE_CONFIG_PATH) -> BoosterParams:
    """Load stage-1 booster parameters from the rocket vehicle config.

    Args:
        config_path: Path to ``vehicle_config.yaml`` for the ramjet rocket.

    Returns:
        Resolved :class:`BoosterParams` with the impulse-consistent thrust
        caveat already computed (see :attr:`BoosterParams.thrust_sl_N`).

    Raises:
        ValueError: If the loaded config is not a :class:`RocketConfig`.
    """
    config = BaseVehicleConfig.from_yaml(config_path)
    if not isinstance(config, RocketConfig):
        raise ValueError(f"{config_path} is not a Project B RocketConfig")

    propulsion = config.stage_1.propulsion
    if config.mass_properties is None or config.mass_properties.total_mass_kg is None:
        raise ValueError("vehicle config is missing mass_properties.total_mass_kg")

    launch_mass_kg = config.mass_properties.total_mass_kg
    propellant_mass_kg = propulsion.propellant_mass_kg
    burnout_mass_kg = launch_mass_kg - propellant_mass_kg
    burn_time_s = propulsion.burn_time_s
    mdot_kg_s = propellant_mass_kg / burn_time_s

    d_ref_m = config.body.diameter_m
    a_ref_m2 = math.pi / 4.0 * d_ref_m**2
    cd_fins = config.fins.count * CD_WAVE_PER_FIN

    return BoosterParams(
        launch_mass_kg=launch_mass_kg,
        propellant_mass_kg=propellant_mass_kg,
        burnout_mass_kg=burnout_mass_kg,
        burn_time_s=burn_time_s,
        mdot_kg_s=mdot_kg_s,
        isp_sl_s=propulsion.isp_sl_s,
        isp_vacuum_s=propulsion.isp_vacuum_s,
        thrust_peak_yaml_N=propulsion.thrust_peak_N,
        a_ref_m2=a_ref_m2,
        cd_fins=cd_fins,
        launch_angle_rad=math.radians(LAUNCH_ANGLE_DEG),
    )


def isa_atmosphere(altitude_m: float) -> tuple[float, float, float]:
    """Evaluate the ICAO standard atmosphere in the troposphere layer.

    Args:
        altitude_m: Geometric altitude [m]. Clamped to ``>= 0`` (guard for
            transient negative altitudes produced by the ODE solver's
            internal trial steps before the ground-impact event fires).

    Returns:
        Tuple ``(temperature_K, pressure_Pa, density_kg_m3)``.
    """
    h = max(altitude_m, 0.0)
    temperature_K = T0_ISA_K - LAPSE_RATE_K_PER_M * h
    pressure_Pa = P0_ISA_PA * (temperature_K / T0_ISA_K) ** ISA_PRESSURE_EXPONENT
    density_kg_m3 = pressure_Pa / (R_AIR_J_PER_KGK * temperature_K)
    return temperature_K, pressure_Pa, density_kg_m3


def specific_impulse_s(altitude_m: float, params: BoosterParams) -> float:
    """Interpolate Isp linearly from sea-level toward vacuum with altitude.

    Args:
        altitude_m: Geometric altitude [m] (clamped to ``>= 0``).
        params: Booster parameters (``isp_sl_s``, ``isp_vacuum_s``).

    Returns:
        Specific impulse [s] at the given altitude.
    """
    h = max(altitude_m, 0.0)
    frac = min(h / ISP_ALT_REF_M, 1.0)
    return params.isp_sl_s + (params.isp_vacuum_s - params.isp_sl_s) * frac


def drag_coefficient(mach: float, params: BoosterParams) -> float:
    """Total drag coefficient: stepped body CD(Mach) plus constant fin CD.

    Args:
        mach: Free-stream Mach number.
        params: Booster parameters (for ``cd_fins``).

    Returns:
        ``CD_total = CD_body(mach) + CD_fins``.
    """
    if mach < MACH_TRANSONIC_LO:
        cd_body = CD_BODY_SUBSONIC
    elif mach < MACH_SUPERSONIC_LO:
        cd_body = CD_BODY_TRANSONIC
    else:
        cd_body = CD_BODY_SUPERSONIC
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
    temperature_K, _pressure_Pa, density_kg_m3 = isa_atmosphere(altitude_m)
    a_sound_ms = math.sqrt(GAMMA_AIR * R_AIR_J_PER_KGK * temperature_K)
    mach = speed_ms / a_sound_ms if a_sound_ms > 0.0 else 0.0
    dynamic_pressure_pa = 0.5 * density_kg_m3 * speed_ms**2
    return speed_ms, mach, dynamic_pressure_pa, density_kg_m3


def boost_dynamics(t_s: float, state: np.ndarray, params: BoosterParams) -> list[float]:
    """3-DOF point-mass equations of motion for the boost phase.

    State vector ``[x_range_m, h_m, vx_ms, vh_ms]``. Thrust acts along the
    fixed launch angle (body axis, no pitch program); drag opposes the
    velocity vector; gravity acts along ``-h``.

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

    if speed_ms > VELOCITY_EPS_MS:
        ux, uh = vx / speed_ms, vh / speed_ms
    else:
        ux, uh = 0.0, 0.0

    if t_s <= params.burn_time_s:
        isp_s = specific_impulse_s(h, params)
        thrust_N = params.mdot_kg_s * G0_MS2 * isp_s
    else:
        thrust_N = 0.0

    mass_kg = mass_at_time(t_s, params)
    thrust_x_N = thrust_N * math.cos(params.launch_angle_rad)
    thrust_h_N = thrust_N * math.sin(params.launch_angle_rad)

    ax_ms2 = (thrust_x_N - drag_N * ux) / mass_kg
    ah_ms2 = (thrust_h_N - drag_N * uh) / mass_kg - G0_MS2

    return [vx, vh, ax_ms2, ah_ms2]


def _ground_impact_event(t_s: float, state: np.ndarray, params: BoosterParams) -> float:
    """Zero-crossing event: altitude reaching 0 m (terminal, decreasing)."""
    return state[1]


def integrate_boost_phase(params: BoosterParams) -> OdeResult:
    """Integrate the boost-phase trajectory from ignition to burnout/impact.

    Args:
        params: Booster parameters from :func:`load_booster_params`.

    Returns:
        The ``scipy.integrate.solve_ivp`` result, with dense output enabled.
    """
    # solve_ivp appends `args` to every callable passed via `events` as
    # well as `fun`, so `_ground_impact_event` must accept `params` as a
    # positional arg directly (a closure lambda would double up args).
    _ground_impact_event.terminal = True
    _ground_impact_event.direction = -1.0

    y0 = [X0_M, H0_M, V0_MS, V0_MS]
    sol = solve_ivp(
        fun=boost_dynamics,
        t_span=(0.0, params.burn_time_s),
        y0=y0,
        method="RK45",
        args=(params,),
        rtol=RTOL,
        atol=ATOL,
        dense_output=True,
        events=_ground_impact_event,
    )
    if not sol.success:
        raise RuntimeError(f"solve_ivp failed: {sol.message}")
    return sol


def postprocess(sol: OdeResult, params: BoosterParams) -> dict[str, Any]:
    """Derive burnout state, q_max, and dense sample arrays from the solution.

    Args:
        sol: Result from :func:`integrate_boost_phase` (dense output).
        params: Booster parameters.

    Returns:
        Dict with scalar results, a ``metadata`` sub-dict, and a
        ``_samples`` sub-dict of dense arrays for plotting (not written to
        the JSON report as-is; see :func:`main`).
    """
    t_end_s = float(sol.t[-1])
    ground_impact = bool(len(sol.t_events[0]) > 0)

    t_fine = np.linspace(0.0, t_end_s, N_DENSE_SAMPLES)
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
    inconsistency_warning = (
        "vehicle_config.yaml stage_1.propulsion.thrust_peak_N="
        f"{params.thrust_peak_yaml_N:.0f} N is INCONSISTENT with the "
        f"impulse-consistent mean thrust F = Isp_sl*mdot*g0 = "
        f"{thrust_used_N:.0f} N (peak cannot be below mean). The YAML "
        "value was NOT used; impulse-consistent thrust was used instead."
    )

    result: dict[str, Any] = {
        "burnout_time_s": t_end_s,
        "burnout_velocity_ms": v_end,
        "burnout_mach": mach_end,
        "burnout_altitude_m": h_end,
        "q_max_pa": q_max_pa,
        "range_at_burnout_m": x_end,
        "metadata": {
            "burnout_vx_ms": vx_end,
            "burnout_vh_ms": vh_end,
            "nominal_burn_time_s": params.burn_time_s,
            "integration_stopped_reason": "ground_impact" if ground_impact else "burnout",
            "ground_impact_before_burnout": ground_impact,
            "open_issue": (
                "0-degree horizontal launch with gravity and no lift loses "
                "altitude from t=0; with h0=100 m the ballistic estimate "
                "h0 - 0.5*g0*t^2 = 0 predicts ground impact at "
                f"t~{math.sqrt(2 * H0_M / G0_MS2):.2f} s, before the "
                f"{params.burn_time_s:.1f} s nominal burnout. A real launch "
                "needs a positive launch angle and/or lift to stay "
                "airborne through burnout."
                if ground_impact
                else "None observed: trajectory stayed airborne to nominal burnout."
            ),
            "thrust_used_N": thrust_used_N,
            "thrust_yaml_peak_N": params.thrust_peak_yaml_N,
            "thrust_inconsistency_warning": inconsistency_warning,
            "isp_sl_s": params.isp_sl_s,
            "isp_vacuum_s": params.isp_vacuum_s,
            "isp_interpolation": (
                "linear in altitude from isp_sl_s at h=0 to isp_vacuum_s at "
                f"h={ISP_ALT_REF_M:.0f} m, clamped beyond; negligible effect "
                "here since altitude stays near h0=100 m"
            ),
            "mdot_kg_s": params.mdot_kg_s,
            "launch_mass_kg": params.launch_mass_kg,
            "burnout_mass_kg": params.burnout_mass_kg,
            "mass_at_stop_kg": mass_at_time(t_end_s, params),
            "launch_angle_deg": LAUNCH_ANGLE_DEG,
            "initial_altitude_m": H0_M,
            "reference_area_m2": params.a_ref_m2,
            "cd_fins": params.cd_fins,
            "atmosphere_model": (
                "ISA troposphere (ICAO Doc 7488 manual formula), "
                "T=288.15-0.0065*h [K], p=101325*(T/288.15)^5.2559 [Pa], "
                "rho=p/(287.05*T) [kg/m^3], altitude clamped to >= 0"
            ),
            "cd_model": (
                "CD_body: 0.20 (M<0.8) / 0.35 (0.8<=M<1.5, transonic) / "
                "0.25 (M>=1.5); step function, not smoothed. "
                "CD_fins = fin_count * 0.012 (per-fin wave drag estimate), "
                "constant. CD_total = CD_body + CD_fins."
            ),
            "integrator": (
                f"scipy.integrate.solve_ivp, RK45, rtol={RTOL}, atol={ATOL}, "
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


def plot_boost_phase(samples: dict[str, Any], output_path: Path = OUTPUT_PNG_PATH) -> None:
    """Plot V(t), h(t), Mach(t), q(t) in a 2x2 grid and save to PNG.

    Args:
        samples: The ``_samples`` sub-dict returned by :func:`postprocess`.
        output_path: Destination PNG path.
    """
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
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> dict[str, Any]:
    """Run the boost-phase simulation, print, and write JSON + PNG outputs.

    Returns:
        The JSON-serializable result dict (without the internal
        ``_samples`` key).
    """
    params = load_booster_params()

    if params.thrust_peak_yaml_N < params.thrust_sl_N:
        warnings.warn(
            "vehicle_config.yaml thrust_peak_N="
            f"{params.thrust_peak_yaml_N:.0f} N is below the "
            f"impulse-consistent mean thrust {params.thrust_sl_N:.0f} N "
            "(Isp_sl*mdot*g0). Using impulse-consistent thrust instead of "
            "the YAML value.",
            stacklevel=2,
        )
        print(
            "WARNING: thrust_peak_N in vehicle_config.yaml "
            f"({params.thrust_peak_yaml_N:.0f} N) is inconsistent with "
            f"mdot*Isp*g0 ({params.thrust_sl_N:.0f} N) -- using the "
            "impulse-consistent value for the simulation."
        )

    sol = integrate_boost_phase(params)
    result = postprocess(sol, params)
    samples = result.pop("_samples")

    plot_boost_phase(samples)

    OUTPUT_JSON_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("Boost-phase trajectory results (stage-1 booster):")
    print(json.dumps(result, indent=2))
    print(f"\nWrote {OUTPUT_JSON_PATH}")
    print(f"Wrote {OUTPUT_PNG_PATH}")

    if result["metadata"]["ground_impact_before_burnout"]:
        print(
            "\nOPEN ISSUE: trajectory hit h=0 at "
            f"t={result['burnout_time_s']:.3f} s, before the nominal "
            f"{params.burn_time_s:.1f} s burnout. See metadata.open_issue."
        )

    return result


if __name__ == "__main__":
    main()
