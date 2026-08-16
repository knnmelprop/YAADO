# MELprop-IADE | analyses.propulsion.nozzle_expansion_check | v0.1.0
"""Nozzle over/under-expansion check on the corrected geometry and gamma.

Stage 3 (nozzle half) of the 2026-07-11 RamP rerun. **Coupled to Stage 2:**
this check uses the SAME station gamma as the Heiser & Pratt cycle rebuild
(:mod:`analyses.propulsion.cycle_v2.hp_stream_thrust_cycle`), NOT the legacy
gamma = 1.4 — the two analyses must not disagree on gamma
(research finding Section 4).

It evaluates the convergent-divergent nozzle with the real drawing area
ratio ``A_exit/A_throat = 1.317`` against a plausible altitude/ambient-pressure
band and reports whether the flow is over-, under-, or matched-expanded, plus
the (much larger) area ratio that WOULD match at the design Mach.

Key coupled result (documented in the .md): at the design M0 = 2.5 the exit
static pressure and the ambient pressure BOTH scale with the altitude
pressure (pt0 ∝ p0 at fixed Mach), so ``p_exit/p0`` is nearly constant with
altitude — the nozzle is **under-expanded by a roughly constant factor across
the whole band**, not matched at any altitude in it.
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path
from typing import Any

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from IADE_Core.modules.powerplant.cycle_methods.heiser_pratt import (  # noqa: E402
    GAMMA_HOT_DEFAULT,
    CycleInputs,
    area_ratio_from_mach,
    evaluate_cycle,
    isa_atmosphere,
    supersonic_mach_from_area_ratio,
)

_HERE = Path(__file__).resolve().parent
CSV_PATH = _HERE / "nozzle_expansion_check.csv"

#: PROVISIONAL altitude band [m]. source: Teltik reference 6 km + config
#: M2.5 @ 10 km, ISA standard troposphere (assumptions A20). Mark PROVISIONAL
#: until the mission altitude profile is confirmed.
ALTITUDE_BAND_M: tuple[float, ...] = (4000.0, 6000.0, 8000.0, 10000.0)

#: Expansion verdict tolerance on p_exit/p0 for "matched".
_MATCH_TOL: float = 0.05


def classify_expansion(p_exit_pa: float, p0_pa: float) -> str:
    """Classify nozzle expansion from exit vs ambient static pressure.

    Args:
        p_exit_pa: Nozzle exit static pressure [Pa].
        p0_pa: Ambient static pressure [Pa].

    Returns:
        ``"matched"``, ``"under-expanded"`` (p_exit > p0) or
        ``"over-expanded"`` (p_exit < p0).
    """
    ratio = p_exit_pa / p0_pa
    if abs(ratio - 1.0) <= _MATCH_TOL:
        return "matched"
    return "under-expanded" if ratio > 1.0 else "over-expanded"


def matched_area_ratio(
    pt_exit_pa: float, p0_pa: float, gamma: float
) -> float:
    """Area ratio A_e/A_t that would fully expand pt_exit to ambient p0.

    Args:
        pt_exit_pa: Nozzle total pressure feeding the expansion [Pa].
        p0_pa: Ambient static pressure [Pa].
        gamma: Ratio of specific heats.

    Returns:
        Matched (fully-expanded) area ratio [-].
    """
    g = gamma
    # Matched exit Mach from isentropic pt/p relation.
    pr = pt_exit_pa / p0_pa
    m_e = math.sqrt((pr ** ((g - 1.0) / g) - 1.0) * 2.0 / (g - 1.0))
    return area_ratio_from_mach(m_e, g)


def run_band(
    gamma_hot: float = GAMMA_HOT_DEFAULT,
    altitudes_m: tuple[float, ...] = ALTITUDE_BAND_M,
    mach0: float = 2.5,
) -> list[dict[str, Any]]:
    """Evaluate expansion state across the altitude band.

    Args:
        gamma_hot: Post-combustion gamma (SAME as Stage 2 cycle).
        altitudes_m: PROVISIONAL altitude band [m].
        mach0: Flight Mach.

    Returns:
        One result dict per altitude.
    """
    ar = CycleInputs().nozzle_area_ratio
    rows: list[dict[str, Any]] = []
    for h in altitudes_m:
        res = evaluate_cycle(CycleInputs(altitude_m=h, mach0=mach0, gamma_hot=gamma_hot))
        _t0, p0, _rho = isa_atmosphere(h)
        pt_exit = res.inputs.pi_nozzle * res.pt4_Pa
        rows.append(
            {
                "altitude_m": h,
                "gamma_hot": gamma_hot,
                "nozzle_area_ratio": ar,
                "mach_exit": res.mach_exit,
                "p0_Pa": p0,
                "p_exit_Pa": res.p_exit_Pa,
                "p_exit_over_p0": res.p_exit_Pa / p0,
                "expansion_state": classify_expansion(res.p_exit_Pa, p0),
                "matched_area_ratio_needed": matched_area_ratio(pt_exit, p0, gamma_hot),
            }
        )
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path = CSV_PATH) -> None:
    """Write the band results to CSV."""
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> list[dict[str, Any]]:
    """Run the band check, write CSV, print a short table."""
    rows = run_band()
    write_csv(rows)
    print(f"{'alt_m':>7} {'M_e':>6} {'p0_Pa':>9} {'p_e_Pa':>9} "
          f"{'pe/p0':>6} {'state':>15} {'AR_match':>9}")
    for r in rows:
        print(f"{r['altitude_m']:>7.0f} {r['mach_exit']:>6.3f} {r['p0_Pa']:>9.0f} "
              f"{r['p_exit_Pa']:>9.0f} {r['p_exit_over_p0']:>6.2f} "
              f"{r['expansion_state']:>15} {r['matched_area_ratio_needed']:>9.2f}")
    return rows


if __name__ == "__main__":
    main()
