# MELprop-IADE | analyses.stability.datcom_class_sweep | v0.1.0
"""DATCOM-class supersonic component-buildup static stability (Project B, ramP).

Replaces the out-of-regime Barrowman supersonic result as the CDR stability gate.
Implements a DATCOM / RASAero-style slender-body + fin component CN_alpha and CP
buildup valid in the supersonic regime (Mach 1.2–3.0), sweeping across CG and
Mach to establish static margin bounds.

Rationale for retirement of Barrowman supersonic values
--------------------------------------------------------
The Barrowman method in barrowman_stability.py produces +8.99 cal (basic) / +4.594 cal
(extended) static margin at supersonic speeds. These results are HISTORICAL / OUT-OF-REGIME:

1. Barrowman slender-body theory is validated only to ~Mach 0.7; the ramP cruise
   condition is Mach 2.5.
2. The ramP fins violate the small-fin assumption: fin semi-span 0.550 m / body
   diameter 0.200 m = 2.75 (fin extends ~2.67× a body diameter from the centerline).
   Classical Barrowman assumes fins are "small perturbations" on the body.

The Barrowman supersonic result is therefore NOT reconciled with the Teltik CFD
-2.75 cal @ Ma2.5 value; instead, this DATCOM-class method provides a regime-correct
intermediate-fidelity replacement.

Theory references
-----------------
- Missile-DATCOM (1997) slender-body normal-force / wave-drag correlations.
- RASAero II (subsonic/supersonic component buildup) methodology.
- Puckett (1946), linearized supersonic lifting-surface tip-loss approximation.
- Hoerner & Borst, *Fluid-Dynamic Lift* (fin-body interference).
- Ackeret (1925), linearized supersonic thin-airfoil slope ``4/sqrt(M^2-1)``.

Component model (all CN_alpha per radian, ref S_ref = pi/4 * d_body^2; x_cp in meters from nose)
--------------------------------------------------------------------------------------------------
1. **BODY** (slender-body, Mach-independent area terms — valid supersonically for
   the area-change contribution):
   - Nose cone: ``CN_alpha = 2 * (d_nose_base / d)^2`` ref S_ref;
     ``x_cp = (2/3) * L_nose`` [CONE supersonic value, NOT 0.466 ogive factor].
   - Shoulder transition (0.150 -> 0.200 m): reused from barrowman_stability.py,
     ``CN_alpha = 2 * (1 - (d_nb/d)^2)``, its x_cp formula.
   - **Body viscous cross-flow (Allen-Perkins) term is proportional to alpha^2**
     (non-linear side-force on a cylinder in crossflow). Its contribution to the
     **static (linear, alpha->0) CN_alpha slope is zero** and it does NOT move
     the static-margin CP. This is a known DATCOM result and is explicitly
     stated here, not silently omitted.

2. **FINS** (supersonic linearized lifting-surface, regime-correct):
   - ``beta = sqrt(M^2 - 1)``; 2-D Ackeret section slope ``a_2D = 4/beta`` per rad.
   - Finite-span supersonic tip loss (DATCOM/Puckett rectangular-tip approximation):
     exposed-panel MAC ``c_mac = (2/3) * (cr + ct - cr*ct/(cr+ct))`` (planform-averaged);
     panel aspect ratio ``AR_e = s / c_mac``;
     tip-loss factor ``eta = max(0.5, 1 - 1/(2*beta*AR_e))``.
     Fin-panel slope ``slope_fin = a_2D * eta``.
     **This is an engineering supersonic finite-AR correction**, flagged PROVISIONAL
     (not full lifting-line or vortex-lattice theory).
   - Fin-body carryover interference ``K_fb = 1 + R/(s+R)``, ``R = d/2`` (same as
     Barrowman; note supersonic carryover is somewhat lower — this is an approximation).
   - Effective panels producing pitch-plane normal force for a 4-fin "+" set = 2.
     Panel area ``A_f = c_mac * s``.
     Fin-set ``CN_alpha`` (ref S_ref) = ``K_fb * 2 * slope_fin * (A_f / S_ref)``.
   - **Fin CP (SUPERSONIC)**: chordwise at 50% of MAC (supersonic flat-plate
     uniform-pressure center of pressure, NOT the subsonic ~60% MAC value).
     Streamwise ``x_cp_fin = fin_root_le_x + y_mac*tan(sweep_LE) + 0.5*c_mac``,
     where ``y_mac = (s/3)*((cr+2ct)/(cr+ct))`` (spanwise centroid of trapezoidal panel).

3. **TOTAL**: ``CN_alpha_total = sum(CN_alpha_i)``; ``x_cp_total = sum(CN_alpha_i * x_cp_i) / CN_alpha_total``.
   Static margin ``SM = (x_cp_total - x_cg) / d_body`` [calibers, positive = stable].

Sweep ranges
------------
- Mach: [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]. Method is **supersonic** — for M<=1 the
  result is emitted but tagged ``"SUBSONIC_OUT_OF_METHOD_REGIME"`` (not authoritative).
- CG sweep (fraction of total length): [0.37, 0.45, 0.55, 0.64].
  Justification:
  - 0.37 = config/ramjet-forward anchor (``cg_from_nose_m=1.6084 / L=4.35501``).
  - Aft values (0.45–0.64) bound the booster-attached / pre-burn CG envelope.
  **CG is UNCERTAIN (TBD_PHYSICAL_PARAM) — do NOT use a single value as definitive.**

Output
------
- CSV: ``datcom_class_sweep.csv`` with columns:
  ``mach``, ``cg_frac``, ``cg_from_nose_m``, ``cn_alpha_total``, ``x_cp_m``,
  ``static_margin_cal``, ``stable_bool``.
- PNG: ``datcom_class_sweep.png`` (SM vs Mach, one line per CG).
- JSON: ``datcom_class_sweep_summary.json`` (method, geometry, sweep grid, results).
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Reuse the RocketGeometry dataclass and load_geometry from barrowman_stability.
from IADE_Core.modules.stability.barrowman_stability import (
    RocketGeometry,
    load_geometry,
    transition_cn_alpha_and_cp,
)

DEFAULT_VEHICLE_CONFIG = (
    Path(__file__).resolve().parents[3]
    / "Hangar"
    / "ramjet_rocket"
    / "vehicle_config.yaml"
)

RESULTS_DIR = Path(__file__).resolve().parent / "results"
CSV_PATH = RESULTS_DIR / "datcom_class_sweep.csv"
PNG_PATH = RESULTS_DIR / "datcom_class_sweep.png"
JSON_PATH = RESULTS_DIR / "datcom_class_sweep_summary.json"

# CG sweep: fraction of total length.
# TBD_PHYSICAL_PARAM: CG is UNCERTAIN. Do NOT use a single value as definitive.
CG_FRACTIONS = [0.37, 0.45, 0.55, 0.64]

# Mach sweep: method is supersonic (M>1.2); M<=1 results tagged out-of-regime.
MACH_SWEEP = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


def nose_cone_cn_alpha_and_cp_supersonic(geometry: RocketGeometry) -> tuple[float, float]:
    """Conical-nose CN_alpha and CP location (SUPERSONIC cone value).

    ``CN_alpha = 2 * (d_nose_base / d)^2`` ref S_ref;
    ``x_cp = (2/3) * L_nose`` (cone supersonic center of pressure, NOT 0.466 ogive).

    Reference:
        DATCOM slender-body cone CN_alpha; supersonic cone CP factor 2/3 from
        linearized conical-flow theory (Kopal 1947).

    Args:
        geometry: Rocket geometry.

    Returns:
        Tuple of (CN_alpha [1/rad, ref. S_ref], x_cp [m from nose]).
    """
    area_ratio = (geometry.nose_base_diameter_m / geometry.d_ref_m) ** 2
    cn_alpha = 2.0 * area_ratio
    x_cp = (2.0 / 3.0) * geometry.nose_length_m  # Supersonic cone CP factor.
    return cn_alpha, x_cp


def fin_cn_alpha_and_cp_supersonic(
    geometry: RocketGeometry, mach: float
) -> tuple[float, float]:
    """Fin-set CN_alpha and CP location (DATCOM-class supersonic).

    Supersonic linearized lifting-surface (Ackeret slope with Puckett tip-loss),
    body interference, and supersonic 50%-MAC CP location.

    Reference:
        DATCOM supersonic fin normal-force slope, Puckett (1946) rectangular-wing
        tip-loss approximation, Hoerner fin-body interference, supersonic flat-plate
        CP at 50% chord.

    Args:
        geometry: Rocket geometry.
        mach: Freestream Mach number (>= 1.0 for supersonic regime).

    Returns:
        Tuple of (CN_alpha [1/rad, ref. S_ref], x_cp [m from nose]).

    Raises:
        ValueError: If mach < 1.0 (subsonic, out of method regime).
    """
    if mach <= 1.0:
        raise ValueError(
            f"fin_cn_alpha_and_cp_supersonic requires mach > 1.0 (strictly supersonic, beta>0); got {mach}"
        )

    s = geometry.fin_span_m
    cr = geometry.fin_root_chord_m
    ct = geometry.fin_tip_chord_m
    n = geometry.fin_count
    r = geometry.body_radius_m
    d = geometry.d_ref_m
    sweep_rad = math.radians(geometry.fin_sweep_deg)

    # Beta (supersonic Mach parameter).
    beta = math.sqrt(mach**2 - 1.0)

    # 2D Ackeret section slope [1/rad].
    a_2d = 4.0 / beta

    # Finite-span tip loss (DATCOM/Puckett rectangular-tip approximation).
    # Exposed-panel MAC (planform-averaged chord).
    c_mac = (2.0 / 3.0) * (cr + ct - cr * ct / (cr + ct))
    ar_e = s / c_mac  # Panel aspect ratio.
    # PROVISIONAL: engineering supersonic finite-AR correction.
    tip_loss_factor = max(0.5, 1.0 - 1.0 / (2.0 * beta * ar_e))
    slope_fin = a_2d * tip_loss_factor

    # Fin-body carryover interference (same as Barrowman; supersonic carryover
    # is somewhat lower — this is an approximation).
    k_fb = 1.0 + r / (s + r)

    # Effective panels producing pitch-plane normal force (4-fin "+" set).
    n_effective = 2

    # Panel area.
    a_f = c_mac * s

    # Fin-set CN_alpha (ref S_ref).
    s_ref = math.pi / 4.0 * d**2
    cn_alpha = k_fb * n_effective * slope_fin * (a_f / s_ref)

    # Fin CP (SUPERSONIC): 50% MAC chordwise, streamwise accounting for sweep.
    # Spanwise centroid of trapezoidal panel.
    y_mac = (s / 3.0) * ((cr + 2.0 * ct) / (cr + ct))
    x_cp = geometry.fin_root_le_x_m + y_mac * math.tan(sweep_rad) + 0.5 * c_mac

    return cn_alpha, x_cp


def compute_static_margin_datcom(
    geometry: RocketGeometry, mach: float, cg_from_nose_m: float
) -> dict[str, Any]:
    """Compute DATCOM-class static margin at a single Mach and CG location.

    Args:
        geometry: Rocket geometry.
        mach: Freestream Mach number.
        cg_from_nose_m: CG location [m from nose tip]. TBD_PHYSICAL_PARAM.

    Returns:
        Dict with keys: ``cn_alpha_nose``, ``cn_alpha_transition``, ``cn_alpha_fins``,
        ``cn_alpha_total``, ``x_cp_nose``, ``x_cp_transition``, ``x_cp_fins``,
        ``x_cp_total``, ``static_margin_cal``, ``stable_bool``, ``regime_flag``.
    """
    # Nose (supersonic cone CP factor).
    cn_nose, x_nose = nose_cone_cn_alpha_and_cp_supersonic(geometry)

    # Transition (reused from barrowman_stability; Mach-independent).
    cn_trans, x_trans = transition_cn_alpha_and_cp(geometry)

    # Fins (supersonic).
    # Guard: beta = sqrt(M^2-1) -> 0 at M=1; fin formula requires M>1 (strictly supersonic).
    if mach > 1.0:
        cn_fin, x_fin = fin_cn_alpha_and_cp_supersonic(geometry, mach)
        regime_flag = (
            "SUPERSONIC_REGIME" if mach >= 1.2 else "TRANSONIC_OUT_OF_METHOD_REGIME"
        )
    else:
        # For M<=1, method is out of regime; emit a placeholder zero-contribution
        # (do NOT use subsonic Barrowman fin formula here — this is a supersonic-only method).
        cn_fin, x_fin = 0.0, 0.0
        regime_flag = "SUBSONIC_OUT_OF_METHOD_REGIME"

    # Total.
    cn_alpha_total = cn_nose + cn_trans + cn_fin
    if cn_alpha_total > 0:
        x_cp_total = (
            cn_nose * x_nose + cn_trans * x_trans + cn_fin * x_fin
        ) / cn_alpha_total
    else:
        x_cp_total = 0.0

    # Static margin [calibers].
    static_margin_cal = (x_cp_total - cg_from_nose_m) / geometry.d_ref_m
    stable_bool = static_margin_cal > 0.0

    return {
        "cn_alpha_nose": cn_nose,
        "cn_alpha_transition": cn_trans,
        "cn_alpha_fins": cn_fin,
        "cn_alpha_total": cn_alpha_total,
        "x_cp_nose": x_nose,
        "x_cp_transition": x_trans,
        "x_cp_fins": x_fin,
        "x_cp_total": x_cp_total,
        "static_margin_cal": static_margin_cal,
        "stable_bool": stable_bool,
        "regime_flag": regime_flag,
    }


def run_sweep(
    geometry: RocketGeometry,
    mach_values: list[float] = MACH_SWEEP,
    cg_fractions: list[float] = CG_FRACTIONS,
) -> list[dict[str, Any]]:
    """Run DATCOM-class stability sweep over Mach and CG.

    Args:
        geometry: Rocket geometry.
        mach_values: Mach sweep (method is supersonic; M<=1 tagged out-of-regime).
        cg_fractions: CG sweep (fraction of total length). TBD_PHYSICAL_PARAM.

    Returns:
        List of result dicts, one per (Mach, CG) grid point.
    """
    results = []
    for mach in mach_values:
        for cg_frac in cg_fractions:
            cg_from_nose_m = cg_frac * geometry.total_length_m  # TBD_PHYSICAL_PARAM
            res = compute_static_margin_datcom(geometry, mach, cg_from_nose_m)
            results.append(
                {
                    "mach": mach,
                    "cg_frac": cg_frac,
                    "cg_from_nose_m": cg_from_nose_m,  # TBD_PHYSICAL_PARAM
                    **res,
                }
            )
    return results


def write_csv(results: list[dict[str, Any]], output_path: Path = CSV_PATH) -> None:
    """Write sweep results to CSV.

    Args:
        results: List of result dicts from :func:`run_sweep`.
        output_path: CSV output path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        fieldnames = [
            "mach",
            "cg_frac",
            "cg_from_nose_m",
            "cn_alpha_total",
            "x_cp_m",
            "static_margin_cal",
            "stable_bool",
            "regime_flag",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for res in results:
            writer.writerow(
                {
                    "mach": res["mach"],
                    "cg_frac": res["cg_frac"],
                    "cg_from_nose_m": res["cg_from_nose_m"],  # TBD_PHYSICAL_PARAM
                    "cn_alpha_total": res["cn_alpha_total"],
                    "x_cp_m": res["x_cp_total"],
                    "static_margin_cal": res["static_margin_cal"],
                    "stable_bool": res["stable_bool"],
                    "regime_flag": res["regime_flag"],
                }
            )


def write_json(
    results: list[dict[str, Any]], geometry: RocketGeometry, output_path: Path = JSON_PATH
) -> None:
    """Write sweep summary to JSON.

    Args:
        results: List of result dicts from :func:`run_sweep`.
        geometry: Rocket geometry.
        output_path: JSON output path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "method": "DATCOM-class supersonic component buildup",
        "geometry": {
            "d_ref_m": geometry.d_ref_m,
            "total_length_m": geometry.total_length_m,
            "nose_length_m": geometry.nose_length_m,
            "nose_base_diameter_m": geometry.nose_base_diameter_m,
            "fin_span_m": geometry.fin_span_m,
            "fin_root_chord_m": geometry.fin_root_chord_m,
            "fin_tip_chord_m": geometry.fin_tip_chord_m,
            "fin_sweep_deg": geometry.fin_sweep_deg,
        },
        "sweep_grid": {
            "mach": MACH_SWEEP,
            "cg_fractions": CG_FRACTIONS,  # TBD_PHYSICAL_PARAM
        },
        "results": results,
        "notes": [
            "CG is UNCERTAIN (TBD_PHYSICAL_PARAM) — do NOT use a single value as definitive.",
            "Method is SUPERSONIC (M>1.2); M<=1 results tagged SUBSONIC_OUT_OF_METHOD_REGIME.",
            "Body viscous cross-flow (Allen-Perkins) term ~ alpha^2; zero static CN_alpha contribution.",
            "Fin tip-loss (Puckett) is PROVISIONAL; supersonic carryover K_fb approximation.",
        ],
    }
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)


def plot_sm_vs_mach(results: list[dict[str, Any]], output_path: Path = PNG_PATH) -> None:
    """Plot static margin vs Mach, one line per CG.

    Args:
        results: List of result dicts from :func:`run_sweep`.
        output_path: PNG output path (150 DPI).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Group by CG fraction.
    cg_groups: dict[float, list[dict[str, Any]]] = {}
    for res in results:
        cg_frac = res["cg_frac"]
        if cg_frac not in cg_groups:
            cg_groups[cg_frac] = []
        cg_groups[cg_frac].append(res)

    fig, ax = plt.subplots(figsize=(8.0, 5.0), dpi=150)

    for cg_frac in sorted(cg_groups.keys()):
        group = sorted(cg_groups[cg_frac], key=lambda r: r["mach"])
        mach_vals = [r["mach"] for r in group]
        sm_vals = [r["static_margin_cal"] for r in group]
        ax.plot(mach_vals, sm_vals, marker="o", label=f"CG = {cg_frac:.2f} L")

    ax.axhline(0.0, color="red", linestyle="--", linewidth=1.0, label="SM = 0 (neutral)")
    ax.set_xlabel("Mach number [-]")
    ax.set_ylabel("Static margin [calibers, (CP-CG)/d_body]")
    ax.set_title("MELprop ramP — DATCOM-class supersonic static margin vs Mach")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main(config_path: Path | str = DEFAULT_VEHICLE_CONFIG) -> dict[str, Any]:
    """Run the full DATCOM-class sweep: compute, write CSV/JSON/PNG.

    Args:
        config_path: Path to the ramjet-rocket ``vehicle_config.yaml``.

    Returns:
        Summary dict (also written to JSON).
    """
    geometry = load_geometry(config_path)
    results = run_sweep(geometry)
    write_csv(results, CSV_PATH)
    write_json(results, geometry, JSON_PATH)
    plot_sm_vs_mach(results, PNG_PATH)

    print(f"DATCOM-class sweep complete: {len(results)} grid points.")
    print(f"CSV: {CSV_PATH}")
    print(f"JSON: {JSON_PATH}")
    print(f"PNG: {PNG_PATH}")

    # Return a summary for programmatic use.
    return {
        "method": "DATCOM-class supersonic component buildup",
        "results_count": len(results),
        "csv_path": str(CSV_PATH),
        "json_path": str(JSON_PATH),
        "png_path": str(PNG_PATH),
    }


if __name__ == "__main__":
    summary = main()
    print(json.dumps(summary, indent=2))
