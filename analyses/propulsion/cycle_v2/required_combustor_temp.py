# MELprop-IADE | analyses.propulsion.cycle_v2.required_combustor_temp | v0.1.0
"""Inverse cycle problem: what Tt4 does steady cruise actually require?

:mod:`analyses.propulsion.cycle_v2.hp_stream_thrust_cycle` runs the cycle
FORWARD: given an assumed combustor-exit temperature ``tt4_K`` (2000 K,
``vehicle_config.yaml``'s ``combustor_temp_K``, SZACOWANY/HR-7 -- see that
module's docstring and this repo's own answer on how heat is inserted),
it solves for the fuel-air ratio and resulting thrust.

This module inverts that: given a REQUIRED thrust (= drag, for steady,
unaccelerated cruise -- net thrust = 0), it solves for the combustor-exit
temperature ``tt4_K`` (and the corresponding fuel-air ratio) that would
actually have to be sustained to fly level at that condition. This answers
"how good does combustion have to be to maintain steady flight," rather
than assuming a temperature and reporting whatever thrust falls out.

Root-find: :func:`analyses.propulsion.cycle_v2.hp_stream_thrust_cycle.
evaluate_cycle`'s ``thrust_real_N`` is monotonically increasing in
``tt4_K`` over any physically sane range (more heat release -> higher
exit velocity -> more thrust; the fuel-air ratio only diverges as
``tt4_K -> eta_b*fuel_lhv_J_kg/cp_hot`` ~31,000 K, far outside any
realistic bracket), so a bisection-style solver (``scipy.optimize.
brentq``) is well-posed over e.g. [600 K, 3000 K].

Two independent required-thrust targets are used, since neither is a
uniquely "official" number (see docs/decision-log.md and
docs/ramP/human_review_night4.md HR-2):
    - the REAL supersonic drag buildup in :mod:`analyses.aero.drag_polar`
      (body wave + friction + fin wave + base drag, current geometry);
    - the independent Teltik 2024 CFD reference drag point (2451.95 N,
      assumptions.md A15) -- a different, lower-fidelity-model-independent
      data point, at its own reference condition, not re-derived here.

Run as a script to solve both cases at the cruise design point and write
``required_combustor_temp_results.json`` + a comparison PNG next to this
file::

    python3 analyses/propulsion/cycle_v2/required_combustor_temp.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from scipy.optimize import brentq  # noqa: E402

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[2]
if __name__ in ("__main__",) and __package__ in (None, ""):
    sys.path.insert(0, str(REPO_ROOT))

from analyses.propulsion.cycle_v2.hp_stream_thrust_cycle import (  # noqa: E402
    CycleInputs,
    CycleResult,
    evaluate_cycle,
)

#: Independent Teltik 2024 CFD reference drag [N] (assumptions.md A15).
TELTIK_DRAG_N: float = 2451.95

#: Bracket for the Tt4 root-find [K]. Well inside the physical fuel-air-ratio
#: singularity (~31,000 K for eta_b=0.95, LHV=43 MJ/kg, cp_hot~1312 J/kgK).
TT4_BRACKET_LO_K: float = 600.0
TT4_BRACKET_HI_K: float = 3000.0

OUTPUT_JSON_PATH = THIS_DIR / "required_combustor_temp_results.json"
OUTPUT_PNG_PATH = THIS_DIR / "required_combustor_temp_comparison.png"


def real_drag_at_condition_N(mach0: float, altitude_m: float) -> float:
    """Real supersonic drag buildup at a flight condition.

    Args:
        mach0: Freestream Mach number.
        altitude_m: Flight altitude [m] (ISA).

    Returns:
        Total zero-lift drag [N] from :mod:`analyses.aero.drag_polar`
        (body wave + friction + fin wave + base drag, current geometry).
    """
    from analyses.aero.drag_polar import DragPolarAnalysis

    analysis = DragPolarAnalysis()
    analysis.setup(mach_values=(mach0,), altitude_m=altitude_m)
    results = analysis.execute()
    return float(results.data["drag_N_at_teltik_point"])


def thrust_at_tt4_N(tt4_K: float, mach0: float, altitude_m: float) -> float:
    """Cycle thrust_real_N at a given combustor-exit temperature.

    Args:
        tt4_K: Combustor-exit total temperature [K].
        mach0: Freestream Mach number.
        altitude_m: Flight altitude [m] (ISA).

    Returns:
        ``thrust_real_N`` from :func:`evaluate_cycle` at that ``tt4_K``.
    """
    inputs = CycleInputs(mach0=mach0, altitude_m=altitude_m, tt4_K=tt4_K)
    return evaluate_cycle(inputs).thrust_real_N


def solve_required_tt4_K(
    required_thrust_N: float,
    mach0: float,
    altitude_m: float,
    lo_K: float = TT4_BRACKET_LO_K,
    hi_K: float = TT4_BRACKET_HI_K,
) -> tuple[float, CycleResult]:
    """Solve for the combustor-exit temperature that yields required_thrust_N.

    Args:
        required_thrust_N: Target ``thrust_real_N`` (drag, for steady,
            unaccelerated cruise).
        mach0: Freestream Mach number.
        altitude_m: Flight altitude [m] (ISA).
        lo_K: Lower bracket bound [K].
        hi_K: Upper bracket bound [K].

    Returns:
        Tuple ``(required_tt4_K, CycleResult at that tt4)``.

    Raises:
        ValueError: If the bracket does not contain a root (required
            thrust outside what's achievable in [lo_K, hi_K]).
    """
    f_lo = thrust_at_tt4_N(lo_K, mach0, altitude_m) - required_thrust_N
    f_hi = thrust_at_tt4_N(hi_K, mach0, altitude_m) - required_thrust_N
    if f_lo > 0.0 or f_hi < 0.0:
        raise ValueError(
            f"required_thrust_N={required_thrust_N:.1f} not bracketed by "
            f"tt4 in [{lo_K}, {hi_K}] K (thrust range "
            f"[{f_lo + required_thrust_N:.1f}, {f_hi + required_thrust_N:.1f}] N)"
        )

    required_tt4_K = brentq(
        lambda tt4: thrust_at_tt4_N(tt4, mach0, altitude_m) - required_thrust_N,
        lo_K,
        hi_K,
        xtol=1e-6,
    )
    inputs = CycleInputs(mach0=mach0, altitude_m=altitude_m, tt4_K=required_tt4_K)
    return required_tt4_K, evaluate_cycle(inputs)


def run_case(name: str, required_thrust_N: float, mach0: float, altitude_m: float) -> dict[str, Any]:
    """Solve and summarize one required-Tt4 case.

    Args:
        name: Case label (e.g. ``"real_drag_polar"``).
        required_thrust_N: Target thrust [N] (= drag for steady flight).
        mach0: Freestream Mach number.
        altitude_m: Flight altitude [m] (ISA).

    Returns:
        Dict of the solved state plus the assumed-2000K comparison.
    """
    required_tt4_K, r = solve_required_tt4_K(required_thrust_N, mach0, altitude_m)

    assumed_inputs = CycleInputs(mach0=mach0, altitude_m=altitude_m)  # default tt4_K=2000
    assumed_r = evaluate_cycle(assumed_inputs)

    return {
        "case_name": name,
        "mach0": mach0,
        "altitude_m": altitude_m,
        "required_thrust_N": required_thrust_N,
        "required_tt4_K": required_tt4_K,
        "required_f_fuel_air": r.f_fuel_air,
        "required_v_exit_m_s": r.v_exit_m_s,
        "assumed_tt4_K": assumed_inputs.tt4_K,
        "assumed_thrust_N": assumed_r.thrust_real_N,
        "assumed_f_fuel_air": assumed_r.f_fuel_air,
        "tt4_delta_K": required_tt4_K - assumed_inputs.tt4_K,
        "tt4_delta_pct": 100.0 * (required_tt4_K - assumed_inputs.tt4_K) / assumed_inputs.tt4_K,
    }


def plot_comparison(cases: list[dict[str, Any]], output_path: Path = OUTPUT_PNG_PATH) -> None:
    """Bar chart: required vs. assumed Tt4 for each case.

    Args:
        cases: List of :func:`run_case` results.
        output_path: Destination PNG path.
    """
    fig, ax = plt.subplots(figsize=(8, 5.5))
    names = [c["case_name"] for c in cases]
    required = [c["required_tt4_K"] for c in cases]
    assumed = [c["assumed_tt4_K"] for c in cases]

    x = range(len(names))
    width = 0.35
    ax.bar([i - width / 2 for i in x], assumed, width, label="Assumed (design input, 2000 K)", color="#d9a441")
    ax.bar([i + width / 2 for i in x], required, width, label="Required for steady flight (solved)", color="#3a7d44")
    for i, c in enumerate(cases):
        ax.text(i + width / 2, c["required_tt4_K"] + 20, f"{c['required_tt4_K']:.0f} K", ha="center", fontsize=9)
        ax.text(i - width / 2, c["assumed_tt4_K"] + 20, f"{c['assumed_tt4_K']:.0f} K", ha="center", fontsize=9)

    ax.set_xticks(list(x))
    ax.set_xticklabels(names)
    ax.set_ylabel("Combustor-exit total temperature Tt4 [K]")
    ax.set_title("Assumed vs. required combustor Tt4 for steady cruise\n(Mach 2.5 / 10,000 m, two independent drag estimates)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> dict[str, Any]:
    """Solve both required-Tt4 cases at the cruise design point, print,
    and write JSON + PNG."""
    mach0, altitude_m = 2.5, 10_000.0
    real_drag_N = real_drag_at_condition_N(mach0, altitude_m)

    cases = [
        run_case("real_drag_polar", real_drag_N, mach0, altitude_m),
        run_case("teltik_cfd_reference", TELTIK_DRAG_N, mach0, altitude_m),
    ]

    print("Required combustor Tt4 for steady, unaccelerated cruise (thrust = drag)")
    print(f"Condition: Mach {mach0} / {altitude_m:.0f} m ISA")
    print(f"{'Case':<22}{'Drag[N]':>10}{'Assumed Tt4[K]':>16}{'Required Tt4[K]':>17}{'Delta[%]':>10}{'Required f':>12}")
    for c in cases:
        print(
            f"{c['case_name']:<22}{c['required_thrust_N']:>10.1f}{c['assumed_tt4_K']:>16.1f}"
            f"{c['required_tt4_K']:>17.1f}{c['tt4_delta_pct']:>10.1f}{c['required_f_fuel_air']:>12.4f}"
        )

    plot_comparison(cases)

    OUTPUT_JSON_PATH.write_text(json.dumps(cases, indent=2), encoding="utf-8")
    print(f"\nWrote {OUTPUT_JSON_PATH}")
    print(f"Wrote {OUTPUT_PNG_PATH}")

    return {"cases": cases}


if __name__ == "__main__":
    main()
