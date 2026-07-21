# MELprop-IADE | docs.team_review_2026-07-11.generate_charts | v0.1.0
"""Generates the team-review chart set from committed repo data only.

Every number plotted here is read from a real file already committed to
the repo (docs/decision-log.md-derived constants transcribed below are
quoted verbatim from that file, not recomputed) -- this script performs
no new analysis, it only visualizes existing results.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent

PROVISIONAL_COLOR = "#d9a441"
CONFIRMED_COLOR = "#3a7d44"
BLOCKED_COLOR = "#b5453f"
CFD_COLOR = "#555555"


def savefig(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT_DIR / name, dpi=150)
    plt.close(fig)
    print(f"wrote {name}")


# --------------------------------------------------------------------------
# 1. Stability panel
# --------------------------------------------------------------------------


def stability_panel() -> None:
    with open(
        REPO_ROOT / "analyses/stability/results/datcom_class_sweep_summary.json"
    ) as f:
        datcom = json.load(f)
    ma25 = [r for r in datcom["results"] if r["mach"] == 2.5]
    cg_fracs = [r["cg_frac"] for r in ma25]
    datcom_sm = [r["static_margin_cal"] for r in ma25]

    # Ackeret single point at config CG (1.6084 m from nose, 0.3693 L)
    ackeret_sm = 9.707456
    ackeret_cg_frac = 1.6084 / 4.35501

    # Barrowman (historical, out-of-regime) -- both variants, from decision-log.md
    barrowman_basic = 8.99
    barrowman_extended = 4.594

    # Teltik 2024 CFD -- from docs/assumptions.md A15
    teltik_sm = -2.75

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(
        cg_fracs, datcom_sm, "o-", color=CONFIRMED_COLOR,
        label="DATCOM-class sweep (PROVISIONAL, CG sweep)", linewidth=2, markersize=7,
    )
    ax.scatter(
        [ackeret_cg_frac], [ackeret_sm], color="#2f6690", marker="D", s=90,
        label="Ackeret hand-check (PROVISIONAL, config CG)", zorder=5,
    )
    ax.axhline(
        barrowman_basic, color=PROVISIONAL_COLOR, linestyle="--", linewidth=1.5,
        label="Barrowman basic +8.99 cal (HISTORICAL/OUT-OF-REGIME, retired)",
    )
    ax.axhline(
        barrowman_extended, color=PROVISIONAL_COLOR, linestyle=":", linewidth=1.5,
        label="Barrowman extended +4.594 cal (HISTORICAL/OUT-OF-REGIME, retired)",
    )
    ax.axhline(
        teltik_sm, color=BLOCKED_COLOR, linestyle="-", linewidth=2.5,
        label="Teltik 2024 CFD -2.75 cal (single point, UNSTABLE -- conflicts with all analytical)",
    )
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.axvspan(0.0, 1.0, ymin=0.5, ymax=1.0, alpha=0.0)  # keep autoscale sane

    ax.set_xlabel("CG position [fraction of total length from nose]")
    ax.set_ylabel("Static margin [calibers]")
    ax.set_title(
        "Static margin at Mach 2.5 -- 2 analytical methods vs 1 CFD point\n"
        "SU2 RANS-SST cross-check: BLOCKED_BY_ENVIRONMENT (not run) -- gate NOT satisfied"
    )
    ax.legend(fontsize=8, loc="center right")
    ax.grid(alpha=0.3)
    savefig(fig, "stability_panel.png")


# --------------------------------------------------------------------------
# 2. Propulsion cycle panel (V3 comparison + gamma sensitivity)
# --------------------------------------------------------------------------


def cycle_panel() -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    labels = ["Legacy MATLAB\n(fully-expanded,\nAR implied~2.44)", "cycle_v2 rebuild\n(AR=1.317,\ngamma=1.28 nominal)", "Teltik CFD\n(reference)"]
    v3_values = [1474, 1200, 1047]
    colors = [PROVISIONAL_COLOR, CONFIRMED_COLOR, CFD_COLOR]
    bars = ax1.bar(labels, v3_values, color=colors)
    for bar, v in zip(bars, v3_values):
        ax1.text(bar.get_x() + bar.get_width() / 2, v + 15, f"{v:.0f}", ha="center", fontsize=10)
    ax1.set_ylabel("V3 exit velocity [m/s]")
    ax1.set_title("V3 exit velocity: legacy vs rebuilt cycle vs CFD\n(residual +14.6% vs CFD after geometry+gamma fix, PROVISIONAL)")
    ax1.grid(axis="y", alpha=0.3)

    gamma_csv = REPO_ROOT / "analyses/propulsion/validation/gamma_sensitivity.csv"
    gammas, v3s = [], []
    with open(gamma_csv) as f:
        for row in csv.DictReader(f):
            gammas.append(float(row["gamma_hot"]))
            v3s.append(float(row["v3_m_s"]))
    ax2.plot(gammas, v3s, "o-", color=CONFIRMED_COLOR)
    ax2.set_xlabel("gamma_hot [-] (swept 1.20-1.40, nominal 1.28)")
    ax2.set_ylabel("V3 [m/s]")
    ax2.set_title("Gamma sensitivity at fixed AR=1.317\n(V3 moves ~0.5% across sweep -- WEAK lever)")
    ax2.grid(alpha=0.3)
    ax2.set_ylim(min(v3s) - 5, max(v3s) + 5)

    savefig(fig, "cycle_panel.png")


# --------------------------------------------------------------------------
# 3. Inlet/nozzle panel
# --------------------------------------------------------------------------


def inlet_nozzle_panel() -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    csv_path = REPO_ROOT / "analyses/propulsion/inlet_performance_v2.csv"
    rows = list(csv.DictReader(open(csv_path)))
    for cone_angle, marker, color in [("42.0", "o", "#2f6690"), ("21.0", "s", "#8a4f9e")]:
        subset = [r for r in rows if r["cone_half_angle_deg"] == cone_angle]
        subset.sort(key=lambda r: float(r["mach0"]))
        machs = [float(r["mach0"]) for r in subset]
        rec = [float(r["overall_recovery"]) if r["overall_recovery"] else None for r in subset]
        mil = [float(r["mil_e_5007d_reference"]) for r in subset]
        ax1.plot(machs, rec, marker=marker, color=color, label=f"{cone_angle}deg cone, overall recovery (v2, Taylor-Maccoll)")
    machs_all = sorted({float(r["mach0"]) for r in rows})
    mil_by_mach = {float(r["mach0"]): float(r["mil_e_5007d_reference"]) for r in rows}
    ax1.plot(machs_all, [mil_by_mach[m] for m in machs_all], "k--", label="MIL-E-5007D reference (goal, not hard limit)")
    ax1.axvline(2.1, color=BLOCKED_COLOR, linestyle=":", label="~M2.1 detachment boundary (42deg cone)")
    ax1.set_xlabel("Freestream Mach number")
    ax1.set_ylabel("Total pressure recovery [-]")
    ax1.set_title("Inlet recovery vs Mach (as-drawn geometry, v2 Taylor-Maccoll)\nBoth cone-angle readings fall short of MIL goal at every Mach")
    ax1.legend(fontsize=7.5, loc="upper right")
    ax1.grid(alpha=0.3)
    ax1.set_ylim(0.3, 1.0)

    with open(REPO_ROOT / "analyses/propulsion/inlet_results.json") as f:
        old = json.load(f)
    mc = old["multi_cone_redesign"]
    ax1.scatter(
        [2.5], [mc["eta_inlet"]], color=CONFIRMED_COLOR, marker="*", s=220, zorder=6,
        label=f"4-cone chain concept (redesign, PASS {mc['eta_inlet']:.3f})",
    )
    ax1.legend(fontsize=7, loc="lower left")

    nozzle_csv = REPO_ROOT / "analyses/propulsion/nozzle_expansion_check.csv"
    nrows = list(csv.DictReader(open(nozzle_csv)))
    alts = [float(r["altitude_m"]) / 1000.0 for r in nrows]
    pe_p0 = [float(r["p_exit_over_p0"]) for r in nrows]
    ax2.plot(alts, pe_p0, "o-", color=BLOCKED_COLOR, label="p_exit/p0 at AR=1.317 (as-drawn, under-expanded)")
    ax2.axhline(1.0, color="black", linewidth=1.0, label="p_exit/p0 = 1 (perfectly expanded)")
    matched_ar = float(nrows[0]["matched_area_ratio_needed"])
    ax2.set_xlabel("Altitude [km]")
    ax2.set_ylabel("p_exit / p0 [-]")
    ax2.set_title(f"Nozzle expansion state, AR=1.317 (drawing)\nMatched AR would be ~{matched_ar:.2f} (~legacy's implied 2.44)")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)
    ax2.set_ylim(0, 4)

    savefig(fig, "inlet_nozzle_panel.png")


# --------------------------------------------------------------------------
# 4. Operational envelope
# --------------------------------------------------------------------------


def operational_envelope_panel() -> None:
    csv_path = REPO_ROOT / "analyses/mission/results/operational_envelope.csv"
    rows = list(csv.DictReader(open(csv_path)))

    machs = sorted({float(r["mach"]) for r in rows})
    alts = sorted({float(r["altitude_m"]) for r in rows})

    fig, ax = plt.subplots(figsize=(9, 6))
    for status, color, marker in [("SUSTAINED", CONFIRMED_COLOR, "o"), ("NOT_SUSTAINED", BLOCKED_COLOR, "x")]:
        pts = [(float(r["mach"]), float(r["altitude_m"]) / 1000.0) for r in rows if r["status"] == status]
        if pts:
            xs, ys = zip(*pts)
            ax.scatter(xs, ys, color=color, marker=marker, s=90, label=status)

    for r in rows:
        ax.annotate(
            f"{float(r['net_thrust_N'])/1000:.1f}",
            (float(r["mach"]), float(r["altitude_m"]) / 1000.0),
            fontsize=6.5, ha="center", va="bottom", xytext=(0, 4), textcoords="offset points",
        )

    ax.set_xlabel("Mach number")
    ax.set_ylabel("Altitude [km]")
    ax.set_title(
        "Operational envelope: net thrust [kN] annotated per cell\n"
        "CD0=0.35 flat placeholder (HR-9, PROVISIONAL) -- NOT the real drag_polar.py buildup"
    )
    ax.legend()
    ax.grid(alpha=0.3)
    savefig(fig, "operational_envelope_panel.png")


if __name__ == "__main__":
    stability_panel()
    cycle_panel()
    inlet_nozzle_panel()
    operational_envelope_panel()
    print("done")
