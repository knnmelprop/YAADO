# MELprop-IADE | analyses.trajectory.coldflow_boost_prd240 | v0.1.0
"""Boost-only, cold-ramjet mission using the real PRD-240 thrust curve.

Mission: stage-1 boost with the archived, real PRD-240 static-test thrust
curve (data/RamP_analitical_computations/acceleration_macro.xls, sheet
"PRD-240", extracted to motor_data/PRD-240_thrust_curve.csv). No fuel is
injected into the ramjet combustor -- the ramjet duct only sees cold,
unreacted air throughout. This module never models ramjet combustion (only
:mod:`analyses.trajectory.booster_burnout`'s boost-phase physics), so that
condition is exactly what integrating this module represents; nothing
extra needed to "turn off" the ramjet.

Uses ``Hangar/ramjet_rocket/vehicle_config_coldflow_PRD240.yaml``. The
PRD-240 motor-vs-Fusion-CAD-wing-panel name collision that originally
motivated keeping this config separate is RESOLVED (2026-07-11, human
confirmed) -- the same real thrust-curve data now also lives in the
official ``vehicle_config.yaml``. This module and its config are kept
regardless, for the real time-varying-thrust integrator (vs. the official
config's constant-mean-thrust default model) and the ARCHIVE100
cross-validation case -- see ``docs/decision-log.md``.

Two cases are run and clearly named throughout outputs. Both use the same
100.0 kg mass (2026-07-11: total_mass_kg corrected 355.02 -> 100.0 kg in
both this config and the official one -- the Fusion physics-engine mass
estimate is considered wrong/oversized; the archive's own reference mass
is the real target), differentiated by launch angle:
    - ``ARCHIVE100``: 50 deg, the archive spreadsheet's own worked-example
      launch angle -- used to cross-validate this module's integration
      against the archive's own independently-computed altitude/velocity
      numbers at the "Separation" event (t=5.0 s).
    - ``OFFICIAL100``: 83 deg, the official ``vehicle_config.yaml``'s
      nominal near-vertical launch angle (``LAUNCH_ANGLE_DEG`` in
      :mod:`analyses.trajectory.booster_burnout`) -- the ramjet stage is
      physically present (as dead mass) but not firing.

Higher fidelity than :func:`analyses.trajectory.booster_burnout.
boost_dynamics`'s constant-mean-thrust model: thrust here is the real
time-varying curve (linear interpolation between archived points, clipped
to >= 0 -- the curve's final point is small negative sensor noise, not
physical reverse thrust). Mass depletion follows the curve's own
cumulative-impulse fraction, not a constant mdot.

Run as a script to integrate both cases, print a comparison table, and
write ``coldflow_boost_results.json`` + ``coldflow_boost_trajectories.png``
next to this file::

    python3 analyses/trajectory/coldflow_boost_prd240.py
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.integrate import solve_ivp  # noqa: E402

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
if __name__ in ("__main__",) and __package__ in (None, ""):
    sys.path.insert(0, str(REPO_ROOT))

from IADE_Core.modules.flight_dynamics.methods.point_mass_3dof import (  # noqa: E402
    BoosterParams,
    G0_MS2,
    H0_M,
    LAUNCH_ANGLE_DEG,
    V0_MS,
    X0_M,
    drag_coefficient,
    flow_state,
    load_booster_params,
)

#: Real PRD-240 thrust curve, extracted verbatim from the archive.
THRUST_CURVE_CSV_PATH = (
    REPO_ROOT / "Hangar" / "ramjet_rocket" / "motor_data" / "PRD-240_thrust_curve.csv"
)

#: Non-official vehicle config for this mission (see module docstring).
COLDFLOW_VEHICLE_CONFIG_PATH = (
    REPO_ROOT / "Hangar" / "ramjet_rocket" / "vehicle_config_coldflow_PRD240.yaml"
)

#: Archive spreadsheet's own reference mass, for cross-validation.
ARCHIVE_REFERENCE_MASS_KG: float = 100.0

#: solve_ivp tolerances (matches booster_burnout.py's convention).
RTOL: float = 1.0e-8
ATOL: float = 1.0e-8

#: Dense output sample count for plotting.
N_DENSE_SAMPLES: int = 2001

OUTPUT_JSON_PATH = THIS_DIR.parents[1] / "FlightLogs" / "coldflow_boost_results.json"
OUTPUT_PNG_PATH = THIS_DIR.parents[1] / "FlightLogs" / "coldflow_boost_trajectories.png"


def load_thrust_curve(
    csv_path: Path = THRUST_CURVE_CSV_PATH,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Load the real PRD-240 thrust curve and its cumulative impulse.

    Args:
        csv_path: Path to the extracted ``time_s,thrust_N`` CSV.

    Returns:
        Tuple ``(t_s, thrust_N, cumulative_impulse_Ns, total_impulse_Ns)``.
        Thrust is clipped to ``>= 0`` (the archive's final point is a small
        negative sensor-noise artifact, not physical reverse thrust).
    """
    rows: list[tuple[float, float]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append((float(row["time_s"]), float(row["thrust_N"])))
    rows.sort()
    t_s = np.array([t for t, _ in rows])
    thrust_N = np.clip(np.array([f for _, f in rows]), 0.0, None)
    cumulative_impulse_Ns = np.concatenate(
        [[0.0], np.cumsum(0.5 * (thrust_N[1:] + thrust_N[:-1]) * np.diff(t_s))]
    )
    total_impulse_Ns = float(cumulative_impulse_Ns[-1])
    return t_s, thrust_N, cumulative_impulse_Ns, total_impulse_Ns


def mass_at_time_real_curve(
    t_s: float,
    params: BoosterParams,
    curve_t: np.ndarray,
    cumulative_impulse_Ns: np.ndarray,
    total_impulse_Ns: float,
) -> float:
    """Instantaneous mass under real-curve cumulative-impulse depletion.

    Args:
        t_s: Time since ignition [s].
        params: Booster parameters (``launch_mass_kg``, ``propellant_mass_kg``).
        curve_t: Thrust-curve time samples [s].
        cumulative_impulse_Ns: Cumulative impulse at each ``curve_t`` [N*s].
        total_impulse_Ns: Total impulse over the full curve [N*s].

    Returns:
        Mass [kg]: depletes propellant in proportion to the fraction of
        total impulse delivered so far (not a constant mdot).
    """
    imp_now = float(np.interp(t_s, curve_t, cumulative_impulse_Ns, left=0.0, right=total_impulse_Ns))
    depleted_fraction = imp_now / total_impulse_Ns
    return params.launch_mass_kg - params.propellant_mass_kg * depleted_fraction


def boost_dynamics_real_curve(
    t_s: float,
    state: np.ndarray,
    params: BoosterParams,
    curve_t: np.ndarray,
    curve_thrust: np.ndarray,
    cumulative_impulse_Ns: np.ndarray,
    total_impulse_Ns: float,
) -> list[float]:
    """3-DOF point-mass EOM using the real, time-varying PRD-240 thrust.

    Same drag/gravity/geometry model as
    :func:`analyses.trajectory.booster_burnout.boost_dynamics`; only the
    thrust and mass-depletion laws differ (real curve vs. constant mdot).

    Args:
        t_s: Time since ignition [s].
        state: Current state ``[x, h, vx, vh]``.
        params: Booster parameters.
        curve_t: Thrust-curve time samples [s].
        curve_thrust: Thrust-curve values [N], clipped >= 0.
        cumulative_impulse_Ns: Cumulative impulse at each ``curve_t``.
        total_impulse_Ns: Total impulse over the full curve.

    Returns:
        State derivative ``[vx, vh, ax, ah]``.
    """
    _x, h, vx, vh = state
    speed_ms, mach, _q_pa, density_kg_m3 = flow_state((vx, vh), h)

    cd_total = drag_coefficient(mach, params)
    drag_N = 0.5 * density_kg_m3 * speed_ms**2 * cd_total * params.a_ref_m2

    if speed_ms > 1.0e-6:
        ux, uh = vx / speed_ms, vh / speed_ms
    else:
        ux, uh = 0.0, 0.0

    thrust_N = float(np.interp(t_s, curve_t, curve_thrust, left=0.0, right=0.0))
    mass_kg = mass_at_time_real_curve(
        t_s, params, curve_t, cumulative_impulse_Ns, total_impulse_Ns
    )

    thrust_x_N = thrust_N * np.cos(params.launch_angle_rad)
    thrust_h_N = thrust_N * np.sin(params.launch_angle_rad)

    ax_ms2 = (thrust_x_N - drag_N * ux) / mass_kg
    ah_ms2 = (thrust_h_N - drag_N * uh) / mass_kg - G0_MS2

    return [vx, vh, ax_ms2, ah_ms2]


def _ground_impact_event(t_s: float, state: np.ndarray, *_args: Any) -> float:
    return state[1]


def run_case(
    case_name: str,
    mass_override_kg: float | None,
    launch_angle_deg: float,
) -> dict[str, Any]:
    """Integrate one boost-only cold-ramjet case with the real PRD-240 curve.

    Args:
        case_name: Human-readable case label (e.g. ``"ARCHIVE100"``).
        mass_override_kg: If given, overrides ``launch_mass_kg`` (and the
            derived ``burnout_mass_kg``) from the loaded config -- used for
            the ``ARCHIVE100`` cross-validation case.
        launch_angle_deg: Fixed thrust/body angle above horizontal [deg].

    Returns:
        Dict of scalar results plus a ``_samples`` dense-array sub-dict.
    """
    params = load_booster_params(
        config_path=COLDFLOW_VEHICLE_CONFIG_PATH, launch_angle_deg=launch_angle_deg
    )
    if mass_override_kg is not None:
        params = replace(
            params,
            launch_mass_kg=mass_override_kg,
            burnout_mass_kg=mass_override_kg - params.propellant_mass_kg,
        )

    curve_t, curve_thrust, cum_impulse, total_impulse = load_thrust_curve()
    t_end_s = float(curve_t[-1])

    _ground_impact_event.terminal = True
    _ground_impact_event.direction = -1.0

    sol = solve_ivp(
        fun=boost_dynamics_real_curve,
        t_span=(0.0, t_end_s),
        y0=[X0_M, H0_M, V0_MS, V0_MS],
        method="RK45",
        args=(params, curve_t, curve_thrust, cum_impulse, total_impulse),
        rtol=RTOL,
        atol=ATOL,
        dense_output=True,
        events=_ground_impact_event,
    )
    if not sol.success:
        raise RuntimeError(f"solve_ivp failed for case {case_name}: {sol.message}")

    t_fine = np.linspace(0.0, float(sol.t[-1]), N_DENSE_SAMPLES)
    y_fine = sol.sol(t_fine)
    x_fine, h_fine, vx_fine, vh_fine = y_fine
    speed_fine = np.hypot(vx_fine, vh_fine)
    mach_fine = np.empty_like(t_fine)
    for i in range(len(t_fine)):
        _, mach_fine[i], _, _ = flow_state((vx_fine[i], vh_fine[i]), h_fine[i])

    ground_impact = bool(len(sol.t_events[0]) > 0)

    return {
        "case_name": case_name,
        "launch_mass_kg": params.launch_mass_kg,
        "launch_angle_deg": launch_angle_deg,
        "burnout_time_s": float(sol.t[-1]),
        "burnout_altitude_m": float(h_fine[-1]),
        "burnout_velocity_ms": float(speed_fine[-1]),
        "burnout_mach": float(mach_fine[-1]),
        "range_at_burnout_m": float(x_fine[-1]),
        "total_impulse_Ns": total_impulse,
        "ground_impact_before_burnout": ground_impact,
        "_samples": {
            "t_s": t_fine,
            "h_m": h_fine,
            "v_ms": speed_fine,
            "mach": mach_fine,
        },
    }


def plot_cases(cases: list[dict[str, Any]], output_path: Path = OUTPUT_PNG_PATH) -> None:
    """Overlay altitude/Mach vs. time for all cases in a 1x2 grid.

    Args:
        cases: List of :func:`run_case` results (with ``_samples`` intact).
        output_path: Destination PNG path.
    """
    fig, (ax_h, ax_m) = plt.subplots(1, 2, figsize=(12, 5))
    colors = ["#3a7d44", "#2f6690"]
    for case, color in zip(cases, colors):
        s = case["_samples"]
        label = f"{case['case_name']} ({case['launch_mass_kg']:.1f} kg)"
        ax_h.plot(s["t_s"], s["h_m"], color=color, linewidth=2, label=label)
        ax_m.plot(s["t_s"], s["mach"], color=color, linewidth=2, label=label)

    ax_h.set_xlabel("Time since ignition [s]")
    ax_h.set_ylabel("Altitude [m]")
    ax_h.set_title("Boost-only, cold ramjet: altitude (real PRD-240 curve)")
    ax_h.legend(fontsize=9)
    ax_h.grid(alpha=0.3)

    ax_m.set_xlabel("Time since ignition [s]")
    ax_m.set_ylabel("Mach number [-]")
    ax_m.set_title("Boost-only, cold ramjet: Mach (real PRD-240 curve)")
    ax_m.axhline(1.0, color="black", linestyle="--", linewidth=1.0, label="Mach 1")
    ax_m.legend(fontsize=9)
    ax_m.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> dict[str, Any]:
    """Run both cases (same mass, different launch angle), print a
    comparison, and write JSON + PNG.

    2026-07-11: both cases now use the same 100.0 kg mass (see module
    docstring); the remaining distinction is launch angle -- ARCHIVE100
    (50deg, the archive's own worked example) vs OFFICIAL100 (83deg, the
    official vehicle_config.yaml's nominal near-vertical angle).
    """
    cases = [
        run_case("ARCHIVE100", ARCHIVE_REFERENCE_MASS_KG, launch_angle_deg=50.0),
        run_case("OFFICIAL100", None, launch_angle_deg=LAUNCH_ANGLE_DEG),
    ]

    print("Boost-only, cold-ramjet mission -- real PRD-240 thrust curve")
    print(f"{'Case':<12} {'Mass [kg]':>10} {'t_end [s]':>10} {'Alt [m]':>10} {'V [m/s]':>10} {'Mach':>7}")
    for c in cases:
        print(
            f"{c['case_name']:<12} {c['launch_mass_kg']:>10.2f} {c['burnout_time_s']:>10.3f} "
            f"{c['burnout_altitude_m']:>10.1f} {c['burnout_velocity_ms']:>10.1f} {c['burnout_mach']:>7.3f}"
        )

    plot_cases(cases)

    json_out = []
    for c in cases:
        c2 = dict(c)
        c2.pop("_samples")
        json_out.append(c2)
    OUTPUT_JSON_PATH.write_text(json.dumps(json_out, indent=2), encoding="utf-8")

    print(f"\nWrote {OUTPUT_JSON_PATH}")
    print(f"Wrote {OUTPUT_PNG_PATH}")

    return {"cases": json_out}


if __name__ == "__main__":
    main()
