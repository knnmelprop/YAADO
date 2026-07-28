# MELprop-IADE | docs.team_review_2026-07-28.generate_geometry_panel | v0.1.0
"""Barrel-diameter / fin-span discrepancy panel.

Unlike every other chart in this snapshot, the "measured" values here are
NOT read from a file on `main` -- they come from `analyses/geometry/results/
station_sweep_topology_2026-07-23.csv` and `docs/HANDOFF_2026-07-23.md`,
both real, committed files, but on closed/unmerged PR #13
(`refs/pull/13/head`, fetched locally as `origin/pr-13`), not on `main`.
This is flagged explicitly in the chart title and in the team-review doc --
do not mistake this for a `main`-sourced result.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT_DIR = Path(__file__).resolve().parent

CONFIRMED_COLOR = "#3a7d44"
BLOCKED_COLOR = "#b5453f"
PROVISIONAL_COLOR = "#d9a441"


def savefig(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT_DIR / name, dpi=150)
    plt.close(fig)
    print(f"wrote {name}")


def geometry_discrepancy_panel() -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))

    # Barrel outer diameter: config vs PR #13 real STEP-file measurement
    # (station_sweep_topology_2026-07-23.csv, x=2500-3600mm uniform section,
    # outer_bbox_r_mm=65.00 -> diameter 130.0mm).
    labels1 = ["vehicle_config.yaml\nbody.diameter_m\n(drawing-verified)", "PR #13 measured\n(STEP file, gmsh slice)\nx=2500-3600mm barrel"]
    values1 = [200.0, 130.0]
    colors1 = [PROVISIONAL_COLOR, BLOCKED_COLOR]
    bars1 = ax1.bar(labels1, values1, color=colors1)
    for bar, v in zip(bars1, values1):
        ax1.text(bar.get_x() + bar.get_width() / 2, v + 3, f"{v:.1f}", ha="center", fontsize=10)
    ax1.set_ylabel("Barrel outer diameter [mm]")
    ax1.set_title("Barrel diameter: config vs measured\n70mm gap -- UNRESOLVED, not on main, config unchanged")
    ax1.grid(axis="y", alpha=0.3)
    ax1.set_ylim(0, 230)

    # Fin tip-to-tip: two config-derived figures vs PR #13 measurement
    labels2 = ["config fins.span_m\n(x2, MODERATE\nCONFIDENCE)", "config\nbody.max_diameter_m\n(\"needs review\")", "PR #13 measured\n(fin-tip bbox radius\nx2, x=4000mm)"]
    values2 = [550.0, 639.0, 590.0]
    colors2 = [PROVISIONAL_COLOR, PROVISIONAL_COLOR, BLOCKED_COLOR]
    bars2 = ax2.bar(labels2, values2, color=colors2)
    for bar, v in zip(bars2, values2):
        ax2.text(bar.get_x() + bar.get_width() / 2, v + 5, f"{v:.0f}", ha="center", fontsize=10)
    ax2.set_ylabel("Fin tip-to-tip span [mm]")
    ax2.set_title("Fin span: two config readings vs measured\nMeasured (590mm) matches NEITHER config value")
    ax2.grid(axis="y", alpha=0.3)
    ax2.set_ylim(0, 700)

    fig.suptitle(
        "NOT ON main -- from closed/unmerged PR #13 (real STEP-file measurement, never merged)",
        fontsize=9, color=BLOCKED_COLOR,
    )
    savefig(fig, "geometry_discrepancy_panel.png")


if __name__ == "__main__":
    geometry_discrepancy_panel()
    print("done")
