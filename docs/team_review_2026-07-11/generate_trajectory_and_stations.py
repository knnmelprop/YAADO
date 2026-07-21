# MELprop-IADE | docs.team_review_2026-07-11.generate_trajectory_and_stations | v0.1.0
"""Trajectory + cycle-station-table addendum to the 2026-07-11 team review.

Both panels reuse existing, already-validated models exactly as committed --
no new physics, no new assumptions beyond what's already in the repo:

- Trajectory: calls analyses.trajectory.booster_burnout's real solve_ivp
  boost-phase ODE directly (same functions main() calls) to get the dense
  time series, then parameterizes the existing quasi-steady cruise design
  point (workflows/staged_mission_profile.json) over its own already-computed
  duration. The gap between the two (unmodeled climb from 1289 m burnout
  altitude to the 10 km cruise altitude) is shown as an explicit gap, not
  smoothed over -- this repo has never modeled that segment.
- Cycle stations: calls analyses.propulsion.cycle_v2's evaluate_cycle()
  directly and reads off the CycleResult fields already computed at each
  station -- no new station-level modeling added.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from analyses.trajectory.booster_burnout import (  # noqa: E402
    integrate_boost_phase,
    load_booster_params,
    postprocess,
)
from analyses.propulsion.cycle_v2.hp_stream_thrust_cycle import (  # noqa: E402
    CycleInputs,
    evaluate_cycle,
)

CONFIRMED_COLOR = "#3a7d44"
PROVISIONAL_COLOR = "#d9a441"
BLOCKED_COLOR = "#b5453f"


def savefig(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT_DIR / name, dpi=150)
    plt.close(fig)
    print(f"wrote {name}")


# --------------------------------------------------------------------------
# Trajectory panel
# --------------------------------------------------------------------------


def trajectory_panel() -> None:
    import json

    params = load_booster_params()
    sol = integrate_boost_phase(params)
    result = postprocess(sol, params)
    samples = result.pop("_samples")

    t_boost = samples["t_s"]
    h_boost = samples["h_m"]
    v_boost = samples["v_ms"]
    mach_boost = samples["mach"]

    with open(REPO_ROOT / "workflows/staged_mission_profile.json") as f:
        mission = json.load(f)
    cruise = next(
        s for s in mission["segments"] if s["name"] == "cruise_stage_2_ramjet"
    )["parameters"]
    staging = next(
        s for s in mission["segments"] if s["name"] == "staging_event"
    )["parameters"]

    coast_t0 = t_boost[-1]
    coast_t1 = coast_t0 + staging["coast_time_s"]

    cruise_t0 = coast_t1  # unmodeled climb gap follows immediately -- see note
    cruise_t1 = cruise_t0 + cruise["cruise_time_s"]
    cruise_mach_series = [cruise["design_mach"], cruise["design_mach"]]

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    ax_h, ax_m = axes

    ax_h.plot(t_boost, h_boost, color=CONFIRMED_COLOR, linewidth=2, label="Boost phase (real 3-DOF ODE, solve_ivp)")
    ax_h.axhline(cruise["cruise_altitude_m"], color=PROVISIONAL_COLOR, linestyle="--", linewidth=1.5, label="Cruise altitude (quasi-steady design point, not integrated)")
    ax_h.axvspan(coast_t0, cruise_t0, color=BLOCKED_COLOR, alpha=0.15, label="Staging coast (0.5 s, placeholder -- not integrated)")
    ax_h.axvspan(cruise_t0, cruise_t0 + 0.01, color="none")
    ax_h.plot(
        [coast_t1, cruise_t0 + 1e-6], [staging["initial_altitude_m"], cruise["cruise_altitude_m"]],
        color=BLOCKED_COLOR, linestyle=":", linewidth=2,
        label="GAP: climb from 1289m to 10km NOT MODELED anywhere in this repo",
    )
    ax_h.plot([cruise_t0, cruise_t1], [cruise["cruise_altitude_m"]] * 2, color=PROVISIONAL_COLOR, linewidth=3)
    ax_h.set_ylabel("Altitude [m]")
    ax_h.set_title("Mission altitude profile -- boost phase is REAL, climb-to-cruise is an unmodeled GAP, cruise is quasi-steady")
    ax_h.legend(fontsize=7.5, loc="center right")
    ax_h.grid(alpha=0.3)

    ax_m.plot(t_boost, mach_boost, color=CONFIRMED_COLOR, linewidth=2, label="Boost phase (real)")
    ax_m.plot(
        [coast_t1, cruise_t0 + 1e-6], [staging["initial_mach"], cruise["design_mach"]],
        color=BLOCKED_COLOR, linestyle=":", linewidth=2, label="GAP: acceleration to Mach 2.5 NOT MODELED",
    )
    ax_m.plot([cruise_t0, cruise_t1], cruise_mach_series, color=PROVISIONAL_COLOR, linewidth=3, label="Cruise (constant Mach 2.5, quasi-steady)")
    ax_m.axvspan(coast_t0, coast_t1, color=BLOCKED_COLOR, alpha=0.15)
    ax_m.set_xlabel("Mission elapsed time [s]")
    ax_m.set_ylabel("Mach number [-]")
    ax_m.legend(fontsize=7.5, loc="center right")
    ax_m.grid(alpha=0.3)

    savefig(fig, "trajectory_panel.png")

    # Mass depletion during cruise (mechanical: mass(t) = m0 - mdot_fuel * t,
    # constant mdot_fuel per the quasi-steady cruise design point).
    fig2, ax = plt.subplots(figsize=(9, 5.5))
    t_cruise = [0.0, cruise["cruise_time_s"]]
    m0 = staging["initial_mass_kg"]
    mdot = cruise["mdot_fuel_kg_s"]
    mass_cruise = [m0 - mdot * t for t in t_cruise]
    ax.plot(t_cruise, mass_cruise, "o-", color=PROVISIONAL_COLOR, linewidth=2)
    ax.set_xlabel("Cruise elapsed time [s]")
    ax.set_ylabel("Vehicle mass [kg]")
    ax.set_title(
        f"Cruise mass depletion (fuel budget {cruise['fuel_mass_kg']:.1f} kg SZACOWANY, "
        f"mdot_fuel={mdot:.4f} kg/s)\nMach/altitude held fixed -- mass change NOT fed back into thrust/drag (quasi-steady only)",
        fontsize=10.5,
    )
    ax.grid(alpha=0.3)
    savefig(fig2, "cruise_mass_panel.png")

    return {
        "boost_end_s": coast_t0,
        "coast_end_s": coast_t1,
        "cruise_end_s": cruise_t1,
        "cruise": cruise,
        "staging": staging,
    }


# --------------------------------------------------------------------------
# Cycle station table
# --------------------------------------------------------------------------


def cycle_station_table() -> None:
    inputs = CycleInputs()  # nominal design point, all defaults from the module
    r = evaluate_cycle(inputs)

    rows = [
        ("0", "Freestream", f"{r.t0_K:.1f}", f"{r.p0_Pa:.0f}", f"{inputs.mach0:.3f}", "-", "static; tt0={:.1f} K, pt0={:.0f} Pa".format(r.tt0_K, r.pt0_Pa)),
        ("2", "Diffuser exit", "-", "-", "-", "-", f"total only: tt2={r.tt0_K:.1f} K (=tt0, adiabatic), pt2={r.pt2_Pa:.0f} Pa (eta_inlet={inputs.eta_inlet:.4f} applied). Static T/p/Mach at station 2 NOT tracked by this 1-D total-condition model."),
        ("4", "Combustor exit", "-", "-", "-", "-", f"total only: tt4={inputs.tt4_K:.1f} K (input), pt4={r.pt4_Pa:.0f} Pa (pi_cc={inputs.pi_cc:.4f} applied). f_fuel_air={r.f_fuel_air:.4f}. Static T/p/Mach at station 4 NOT tracked."),
        ("throat", "Nozzle throat (choked)", "-", "-", "1.000", f"{r.a_throat_m2*1e4:.2f}", "Ma=1 by construction (choked)"),
        ("e / 9", "Nozzle exit", f"{r.t_exit_K:.1f}", f"{r.p_exit_Pa:.0f}", f"{r.mach_exit:.3f}", f"{r.a_exit_m2*1e4:.2f}", f"v_exit={r.v_exit_m_s:.1f} m/s; AR={inputs.nozzle_area_ratio:.3f} (real, drawing)"),
    ]

    csv_path = OUT_DIR / "cycle_v2_station_table.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["station", "name", "T_static_K", "p_static_Pa", "Mach", "area_cm2", "note"])
        w.writerows(rows)
    print(f"wrote {csv_path.name}")

    print("\nCycle_v2 station table (nominal design point, Mach {:.1f} / {:.0f} m, gamma_hot={:.2f}):".format(
        inputs.mach0, inputs.altitude_m, inputs.gamma_hot
    ))
    for row in rows:
        print(row)

    return rows, inputs, r


if __name__ == "__main__":
    trajectory_panel()
    cycle_station_table()
    print("done")
