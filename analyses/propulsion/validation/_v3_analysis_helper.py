# MELprop-IADE | analyses.propulsion.validation.v3_analysis_helper | v0.1.0
"""Root-cause helper for the V3 (nozzle-exit velocity) discrepancy study.

Reproduces the Grzywka combustor/nozzle cycle station-by-station, runs a
combustor-exit total-temperature (``T04`` == Grzywka ``Tt2``) sensitivity
sweep, and produces the supporting CSV + PNG for
``v3_discrepancy_analysis.md``.

This helper ONLY imports and calls the production module
:mod:`analyses.propulsion.combustor_nozzle_cycle` (via its public
functions and the analysis object's factored ``_run_condition``); it does
NOT reimplement any cycle physics and does NOT modify production code or
YAML. Analytical side-estimates (gamma sensitivity, MIL-E-5007 recovery)
are closed-form and clearly labelled.

SI units throughout; field names carry unit suffixes.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from analyses.propulsion.combustor_nozzle_cycle import (  # noqa: E402
    GrzywkaCombustorNozzleAnalysis,
    TELTIK_ALTITUDE_M,
    TELTIK_MACH,
    TELTIK_V3_M_S,
)
from analyses.propulsion.inlet_performance import mil_e_5007_eta_std  # noqa: E402
from analyses.propulsion.ramjet_cycle import CP_HOT, GAMMA_HOT  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
CSV_PATH = OUT_DIR / "v3_sensitivity_T04.csv"
PNG_PATH = OUT_DIR / "v3_sensitivity_T04.png"


def run_condition_for_t04(t04_K: float) -> dict:
    """Evaluate the Grzywka cycle at the Teltik condition for a given T04.

    Args:
        t04_K: Combustor-exit total temperature (Grzywka Tt2) [K].

    Returns:
        The raw ``_run_condition`` dict at Mach ``TELTIK_MACH`` /
        ``TELTIK_ALTITUDE_M``. ``_run_condition`` is used directly (not
        ``execute``) so the material-ceiling validation does not reject
        the high-T04 sweep rows; no cycle physics is reimplemented.
    """
    analysis = GrzywkaCombustorNozzleAnalysis()
    analysis.setup(
        mach0=TELTIK_MACH,
        altitude_m=TELTIK_ALTITUDE_M,
        combustor_exit_temp_K=t04_K,
    )
    return analysis._run_condition(TELTIK_MACH, TELTIK_ALTITUDE_M)


def main() -> None:
    """Reproduce V3, run the T04 sweep, and write the CSV + PNG."""
    print("=" * 70)
    print("V3 DISCREPANCY ROOT-CAUSE — Grzywka combustor/nozzle cycle")
    print(f"Condition: Mach {TELTIK_MACH} / {TELTIK_ALTITUDE_M:.0f} m ISA "
          f"(Teltik CFD reference; V3_CFD = {TELTIK_V3_M_S:.0f} m/s)")
    print(f"Gas model in code: gamma_hot = {GAMMA_HOT}, cp_hot = {CP_HOT} J/kgK")
    print("=" * 70)

    # ---- Task 1: station-by-station reproduction (baseline T04 = 2000 K) --
    base = run_condition_for_t04(2000.0)
    throat = base["throat"]
    th2 = base["Th2"]
    print("\n[Task 1] Station table (baseline T04 = 2000 K, Th2 real losses):")
    print(f"  eta_inlet                : {base['eta_inlet']:.4f}")
    print(f"  Station 1 (comb. inlet)  : T1(tt1)={base['tt1_K']:.2f} K  "
          f"p1(pt1)={base['pt1_Pa']:.1f} Pa")
    print(f"  Station 2 (comb. exit)   : T2(tt2)={base['tt2_K']:.2f} K  "
          f"p2(pt2)={base['pt2_real_Pa']:.1f} Pa")
    print(f"  Station 21 (throat, M=1) : T21={throat['T21_K']:.2f} K  "
          f"p21={throat['p21_Pa']:.1f} Pa  u21={throat['u21_m_s']:.2f} m/s  "
          f"A21={throat['A21_m2']:.5f} m^2")
    print(f"  Station 3 (nozzle exit)  : T3={th2['T3_K']:.2f} K  "
          f"p3={th2['p3_Pa']:.1f} Pa  V3={th2['V3_m_s']:.2f} m/s  "
          f"Ma3={th2['Ma3']:.3f}  A3={th2['A3_m2']:.5f} m^2")
    v3_base = th2["V3_m_s"]
    print(f"  A3/A21 (implied full-expansion ratio): "
          f"{th2['A3_m2'] / throat['A21_m2']:.3f}  "
          f"(CAD cylindrical stub = 1.0)")
    print(f"  V3(model) = {v3_base:.2f} m/s vs CFD {TELTIK_V3_M_S:.0f} m/s  "
          f"-> delta {(v3_base - TELTIK_V3_M_S) / TELTIK_V3_M_S * 100:+.1f}%")

    # ---- Task 2: T04 sensitivity sweep + T04_teltik_equivalent -----------
    t04_grid = [1600.0, 1800.0, 2000.0, 2200.0, 2400.0, 2600.0]
    rows: list[tuple[float, float, float, float, float]] = []
    print("\n[Task 2] T04 sensitivity sweep:")
    print(f"  {'T04_K':>7} {'V3_m_s':>10} {'Thi_N':>11} {'Th1_N':>11} {'Th2_N':>11}")
    for t04 in t04_grid:
        cyc = run_condition_for_t04(t04)
        v3 = cyc["Th2"]["V3_m_s"]
        thi = cyc["Thi"]["thrust_N"]
        th1 = cyc["Th1"]["thrust_N"]
        th2n = cyc["Th2"]["thrust_N"]
        rows.append((t04, v3, thi, th1, th2n))
        print(f"  {t04:>7.0f} {v3:>10.2f} {thi:>11.1f} {th1:>11.1f} {th2n:>11.1f}")

    # V3 scales as sqrt(T04) at fixed pressure ratio; bisect the model to
    # find T04 giving V3 = TELTIK_V3_M_S (verify the sqrt law numerically).
    def v3_of_t04(t04_K: float) -> float:
        return run_condition_for_t04(t04_K)["Th2"]["V3_m_s"]

    lo, hi = 300.0, 2600.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if v3_of_t04(mid) < TELTIK_V3_M_S:
            lo = mid
        else:
            hi = mid
    t04_match = 0.5 * (lo + hi)
    t04_match_analytic = 2000.0 * (TELTIK_V3_M_S / v3_base) ** 2
    print(f"\n  T04_teltik_equivalent_K (bisection) = {t04_match:.1f} K")
    print(f"  T04_teltik_equivalent_K (sqrt law)  = {t04_match_analytic:.1f} K")
    print(f"  V3 at that T04 = {v3_of_t04(t04_match):.2f} m/s")

    # ---- Task 3: gamma sensitivity in the nozzle expansion ----------------
    # V3 = sqrt(2*cp*Tt2*(1 - (p0/pt_noz)^((g-1)/g))); isolate the gamma
    # effect in the EXPANSION EXPONENT with cp (energy) held fixed, then
    # also show the composition-consistent variant (R fixed -> cp varies).
    p0_over_ptnoz = (base["p0_Pa"] /
                     (0.97 * 0.8924 * base["pt1_Pa"]))  # p0 / pt_noz (Th2)
    tt2 = 2000.0
    r_hot = CP_HOT * (GAMMA_HOT - 1.0) / GAMMA_HOT

    def v3_gamma(gamma: float, cp: float) -> float:
        pr = p0_over_ptnoz ** ((gamma - 1.0) / gamma)
        return math.sqrt(2.0 * cp * tt2 * (1.0 - pr))

    v3_g133 = v3_gamma(1.33, CP_HOT)               # code baseline
    v3_g128_cpfix = v3_gamma(1.28, CP_HOT)         # exponent-only
    cp_g128 = 1.28 * r_hot / (1.28 - 1.0)          # R fixed -> cp
    v3_g128_consistent = v3_gamma(1.28, cp_g128)
    v3_g140_cpfix = v3_gamma(1.40, CP_HOT)         # the (wrong) premise
    print("\n[Task 3] Gamma sensitivity in the nozzle expansion:")
    print(f"  p0/pt_noz (Th2) = {p0_over_ptnoz:.5f}")
    print(f"  gamma=1.33 (code), cp={CP_HOT:.0f}      -> V3 = {v3_g133:.2f} m/s")
    print(f"  gamma=1.28, cp fixed {CP_HOT:.0f}       -> V3 = {v3_g128_cpfix:.2f} m/s "
          f"(delta {(v3_g128_cpfix - v3_g133) / v3_g133 * 100:+.2f}%)")
    print(f"  gamma=1.28, cp={cp_g128:.0f} (R fixed)  -> V3 = {v3_g128_consistent:.2f} m/s "
          f"(delta {(v3_g128_consistent - v3_g133) / v3_g133 * 100:+.2f}%)")
    print(f"  gamma=1.40, cp fixed {CP_HOT:.0f}       -> V3 = {v3_g140_cpfix:.2f} m/s "
          f"(delta {(v3_g140_cpfix - v3_g133) / v3_g133 * 100:+.2f}%)  "
          f"[task's assumed-but-WRONG premise]")

    # ---- Task 4: inlet recovery vs MIL-E-5007D ---------------------------
    eta_inlet = base["eta_inlet"]
    eta_d_mil = mil_e_5007_eta_std(TELTIK_MACH)
    print("\n[Task 4] Inlet recovery vs MIL-E-5007D:")
    print(f"  eta_inlet (model, 4-cone chain) = {eta_inlet:.4f}")
    print(f"  eta_d_MIL (1-0.075*(M-1)^1.35)   = {eta_d_mil:.4f}")
    print(f"  delta (model - MIL)              = {eta_inlet - eta_d_mil:+.4f} "
          f"({(eta_inlet - eta_d_mil) / eta_d_mil * 100:+.2f}%)")
    print(f"  NOTE: pi_CC=0.8924 is the COMBUSTOR loss pt2/pt1, NOT the inlet "
          f"recovery. Inlet recovery is eta_inlet={eta_inlet:.4f}.")

    # ---- Write CSV -------------------------------------------------------
    with open(CSV_PATH, "w", encoding="utf-8") as f:
        f.write("# MELprop-IADE | v3_sensitivity_T04 | v0.1.0\n")
        f.write(f"# Condition: Mach {TELTIK_MACH} / {TELTIK_ALTITUDE_M:.0f} m ISA "
                f"(Teltik 2024 CFD reference, V3_CFD={TELTIK_V3_M_S:.0f} m/s)\n")
        f.write(f"# Gas: gamma_hot={GAMMA_HOT}, cp_hot={CP_HOT} J/kgK; "
                f"V3 is the Th2 (real losses) fully-expanded exit velocity\n")
        f.write(f"# T04 == Grzywka combustor-exit total temperature Tt2\n")
        f.write(f"# T04_teltik_equivalent_K={t04_match:.1f} "
                f"(model bisection; V3 propto sqrt(T04))\n")
        f.write("T04_K,V3_m_s,Thi_N,Th1_N,Th2_N\n")
        for t04, v3, thi, th1, th2n in rows:
            f.write(f"{t04:.1f},{v3:.4f},{thi:.4f},{th1:.4f},{th2n:.4f}\n")
    print(f"\nCSV written: {CSV_PATH}")

    # ---- Plot ------------------------------------------------------------
    t04_arr = [r[0] for r in rows]
    v3_arr = [r[1] for r in rows]
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    ax.plot(t04_arr, v3_arr, "o-", color="#1f77b4", linewidth=2.0,
            label="V3 model (Th2, gamma=1.33, full expansion)")
    ax.axhline(TELTIK_V3_M_S, color="#d62728", linestyle="--", linewidth=1.8,
               label=f"Teltik 2024 CFD V3 = {TELTIK_V3_M_S:.0f} m/s")
    ax.axvline(t04_match, color="gray", linestyle=":", linewidth=1.5,
               label=f"T04 equiv = {t04_match:.0f} K")
    ax.axvspan(2400.0, 2600.0, color="#ff7f0e", alpha=0.12,
               label="T04 > 2400 K flame-holder risk (A4)")
    ax.set_xlabel("Combustor-exit total temperature T04 = Tt2 [K]")
    ax.set_ylabel("Nozzle-exit velocity V3 (Th2) [m/s]")
    ax.set_title("MELprop ramP | V3 vs combustor-exit temperature T04\n"
                 f"Grzywka cycle @ Mach {TELTIK_MACH} / {TELTIK_ALTITUDE_M:.0f} m "
                 "vs Teltik 2024 CFD")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(PNG_PATH, dpi=150)
    plt.close(fig)
    print(f"PNG written: {PNG_PATH}")

    # Emit machine-readable summary line for the markdown author.
    print("\nSUMMARY_JSON "
          f'{{"v3_base_m_s": {v3_base:.2f}, '
          f'"t04_teltik_equivalent_K": {t04_match:.1f}, '
          f'"v3_gamma128_cpfix_m_s": {v3_g128_cpfix:.2f}, '
          f'"v3_gamma128_delta_pct": {(v3_g128_cpfix - v3_g133) / v3_g133 * 100:.2f}, '
          f'"eta_inlet": {eta_inlet:.4f}, "eta_d_mil": {eta_d_mil:.4f}, '
          f'"eta_delta": {eta_inlet - eta_d_mil:.4f}, '
          f'"a3_over_a21": {th2["A3_m2"] / throat["A21_m2"]:.3f}}}')


if __name__ == "__main__":
    main()
