# MELprop-IADE | analyses.propulsion.validation.gamma_sensitivity | v0.1.0
"""Gamma sensitivity sweep for the Heiser & Pratt ramjet cycle rebuild.

Sweeps the post-combustion ratio of specific heats over
``[1.20, 1.25, 1.30, 1.35, 1.40]`` (the 2026-07-11 research finding,
Section 2) on the corrected nozzle geometry (``nozzle_area_ratio = 1.317``)
and reports exit velocity V3, the three thrust models, and the delta of V3
against the legacy MATLAB value (1474 m/s) and the deprioritized Teltik CFD
reference (1047 m/s).

Writes a CSV (committed) and a PNG (gitignored, regenerable) alongside this
module. Run directly::

    python analyses/propulsion/validation/gamma_sensitivity.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from analyses.propulsion.cycle_v2.hp_stream_thrust_cycle import (  # noqa: E402
    GAMMA_SWEEP,
    V3_LEGACY_MATLAB_M_S,
    V3_TELTIK_CFD_M_S,
    CycleInputs,
    evaluate_cycle,
)

_HERE = Path(__file__).resolve().parent
CSV_PATH = _HERE / "gamma_sensitivity.csv"
PNG_PATH = _HERE / "gamma_sensitivity.png"


def run_sweep(gammas: tuple[float, ...] = GAMMA_SWEEP) -> list[dict[str, Any]]:
    """Evaluate the cycle across the gamma sweep.

    Args:
        gammas: Post-combustion gamma values to sweep.

    Returns:
        One dict of results per gamma, in sweep order.
    """
    rows: list[dict[str, Any]] = []
    for g in gammas:
        res = evaluate_cycle(CycleInputs(gamma_hot=g))
        rows.append(
            {
                "gamma_hot": g,
                "v3_m_s": res.v_exit_m_s,
                "mach_exit": res.mach_exit,
                "p_exit_over_p0": res.extras["p_exit_over_p0"],
                "thrust_ideal_N": res.thrust_ideal_N,
                "thrust_cc_loss_N": res.thrust_cc_loss_N,
                "thrust_real_N": res.thrust_real_N,
                "momentum_thrust_N": res.momentum_thrust_N,
                "pressure_thrust_N": res.pressure_thrust_N,
                "f_fuel_air": res.f_fuel_air,
                "tt4_K": res.extras["tt4_K"],
                "delta_v3_vs_matlab_pct": res.extras["v3_delta_vs_matlab"] * 100.0,
                "delta_v3_vs_teltik_pct": res.extras["v3_delta_vs_teltik"] * 100.0,
            }
        )
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path = CSV_PATH) -> None:
    """Write the sweep rows to CSV."""
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_png(rows: list[dict[str, Any]], path: Path = PNG_PATH) -> None:
    """Plot V3 vs gamma with the legacy/CFD reference lines (gitignored PNG)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    gammas = [r["gamma_hot"] for r in rows]
    v3 = [r["v3_m_s"] for r in rows]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(gammas, v3, "o-", label="H&P cycle_v2 V3 (AR=1.317)")
    ax.axhline(V3_LEGACY_MATLAB_M_S, ls="--", color="tab:red",
               label=f"legacy MATLAB {V3_LEGACY_MATLAB_M_S:.0f} m/s")
    ax.axhline(V3_TELTIK_CFD_M_S, ls=":", color="tab:green",
               label=f"Teltik CFD {V3_TELTIK_CFD_M_S:.0f} m/s")
    ax.set_xlabel(r"post-combustion $\gamma$ [-]")
    ax.set_ylabel(r"nozzle exit velocity $V_3$ [m/s]")
    ax.set_title("RamP ramjet V3 gamma sensitivity (corrected geometry)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main() -> list[dict[str, Any]]:
    """Run the sweep, write CSV + PNG, and print a short table."""
    rows = run_sweep()
    write_csv(rows)
    try:
        write_png(rows)
    except Exception as exc:  # pragma: no cover - plotting is best-effort
        print(f"(PNG skipped: {exc})")
    print(f"{'gamma':>6} {'V3 m/s':>9} {'M_e':>6} {'pe/p0':>6} "
          f"{'Th2 N':>9} {'dMATLAB%':>9} {'dTeltik%':>9}")
    for r in rows:
        print(f"{r['gamma_hot']:>6.2f} {r['v3_m_s']:>9.2f} {r['mach_exit']:>6.3f} "
              f"{r['p_exit_over_p0']:>6.2f} {r['thrust_real_N']:>9.1f} "
              f"{r['delta_v3_vs_matlab_pct']:>+9.1f} {r['delta_v3_vs_teltik_pct']:>+9.1f}")
    return rows


if __name__ == "__main__":
    main()
