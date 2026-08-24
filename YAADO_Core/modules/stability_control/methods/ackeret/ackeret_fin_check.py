"""Ackeret / slender-body independent fin CP hand-check (Generic Vehicle, vehicle).

Independent closed-form cross-check of the FIN center of pressure and fin-alone
normal force using pure Ackeret slender/thin-supersonic theory (no DATCOM
correlations, no reuse of datcom_class_sweep functions — genuinely independent).

Purpose
-------
Verify that the DATCOM-class fin CP (datcom_class_sweep.py) and this Ackeret
fin CP agree on sign and location (within ~one caliber) at the cruise condition
(Ma 2.5, config CG).

Theory
------
Ackeret linearized supersonic thin-airfoil theory:
- Fin-panel 2D slope: ``a_2D = 4 / sqrt(M^2 - 1)`` [1/rad].
- Finite-span (simple slender-body approximation, no Puckett correlation):
  exposed-panel aspect ratio ``AR = s / c_mean``;
  slope ``slope_fin = a_2D / (1 + 2/AR)`` (inviscid elliptic lift-distribution
  downwash correction, classical low-AR formula).
- Fin-body interference: ``K_fb = 1 + R/(s+R)``, ``R = d/2`` (same as all other methods).
- CP location (supersonic): 50% of mean chord (uniform-pressure center of pressure).

Reference:
    Ackeret (1925) linearized supersonic theory; Anderson *Fundamentals of
    Aerodynamics* Ch.12; classical low-AR downwash correction (Glauert,
    Prandtl lifting-line).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from YAADO_Core.modules.stability_control.methods.barrowman.barrowman_stability import (
    RocketGeometry,
    load_geometry,
    nose_cn_alpha_and_cp,
    transition_cn_alpha_and_cp,
)

DEFAULT_VEHICLE_CONFIG = (
    Path(__file__).resolve().parents[5]
    / "Hangar"
    / "generic_vehicle"
    / "vehicle_config.yaml"
)

RESULTS_DIR = Path(__file__).resolve().parents[5] / "FlightLogs"
MARKDOWN_PATH = RESULTS_DIR / "ackeret_fin_check.md"

# Cruise condition for the hand-check.
CRUISE_MACH = 2.5


def ackeret_fin_cn_alpha_and_cp(
    geometry: RocketGeometry, mach: float
) -> tuple[float, float]:
    """Fin-set CN_alpha and CP location (pure Ackeret, independent).

    Args:
        geometry: Rocket geometry.
        mach: Freestream Mach number (>= 1.0).

    Returns:
        Tuple of (CN_alpha [1/rad, ref. S_ref], x_cp [m from nose]).

    Raises:
        ValueError: If mach < 1.0.
    """
    if mach <= 1.0:
        raise ValueError(f"ackeret_fin_cn_alpha_and_cp requires mach > 1.0 (strictly supersonic, beta>0); got {mach}")

    s = geometry.fin_span_m
    cr = geometry.fin_root_chord_m
    ct = geometry.fin_tip_chord_m
    r = geometry.body_radius_m
    d = geometry.d_ref_m
    sweep_rad = math.radians(geometry.fin_sweep_deg)

    # Beta.
    beta = math.sqrt(mach**2 - 1.0)

    # 2D Ackeret slope.
    a_2d = 4.0 / beta

    # Finite-span correction (classical low-AR downwash, NOT Puckett).
    c_mean = (cr + ct) / 2.0
    ar_panel = s / c_mean
    slope_fin = a_2d / (1.0 + 2.0 / ar_panel)

    # Fin-body interference.
    k_fb = 1.0 + r / (s + r)

    # Effective panels (4-fin "+" set, pitch plane).
    n_effective = 2

    # Panel area.
    a_f = s * c_mean

    # Fin-set CN_alpha (ref S_ref).
    s_ref = math.pi / 4.0 * d**2
    cn_alpha = k_fb * n_effective * slope_fin * (a_f / s_ref)

    # Fin CP (supersonic): 50% of mean chord, streamwise accounting for sweep.
    # For a rectangular fin (cr=ct), the spanwise centroid is at s/2.
    # For a trapezoidal fin, use (s/3)*((cr+2ct)/(cr+ct)).
    y_centroid = (s / 3.0) * ((cr + 2.0 * ct) / (cr + ct))
    x_cp = geometry.fin_root_le_x_m + y_centroid * math.tan(sweep_rad) + 0.5 * c_mean

    return cn_alpha, x_cp


def compute_whole_vehicle_sm_ackeret(
    geometry: RocketGeometry, mach: float, cg_from_nose_m: float
) -> dict[str, Any]:
    """Compute whole-vehicle static margin using Ackeret fin + body terms.

    Args:
        geometry: Rocket geometry.
        mach: Freestream Mach number.
        cg_from_nose_m: CG location [m from nose tip].

    Returns:
        Dict with component CN_alpha, CP, total CP, and static margin.
    """
    # Nose (use subsonic Barrowman value; this is a hand-check, not a full model).
    cn_nose, x_nose = nose_cn_alpha_and_cp(geometry)

    # Transition (Barrowman).
    cn_trans, x_trans = transition_cn_alpha_and_cp(geometry)

    # Fins (Ackeret).
    cn_fin, x_fin = ackeret_fin_cn_alpha_and_cp(geometry, mach)

    # Total.
    cn_alpha_total = cn_nose + cn_trans + cn_fin
    x_cp_total = (cn_nose * x_nose + cn_trans * x_trans + cn_fin * x_fin) / cn_alpha_total

    # Static margin.
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
    }


def write_markdown_report(
    geometry: RocketGeometry,
    ackeret_result: dict[str, Any],
    output_path: Path = MARKDOWN_PATH,
) -> None:
    """Write Ackeret fin check report to Markdown.

    Args:
        geometry: Rocket geometry.
        ackeret_result: Result dict from :func:`compute_whole_vehicle_sm_ackeret`.
        output_path: Markdown output path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        fh.write("# Ackeret Fin CP Hand-Check (Generic Vehicle, vehicle)\n\n")
        fh.write(
            "Independent closed-form cross-check of the fin center of pressure "
            "using pure Ackeret slender-body / thin-supersonic theory.\n\n"
        )
        fh.write("## Method\n\n")
        fh.write(
            "- **Fin-panel 2D slope**: `a_2D = 4 / sqrt(M^2 - 1)` [1/rad].\n"
        )
        fh.write(
            "- **Finite-span correction**: `slope_fin = a_2D / (1 + 2/AR)` "
            "(classical low-AR downwash, NOT Puckett).\n"
        )
        fh.write("- **Fin-body interference**: `K_fb = 1 + R/(s+R)`.\n")
        fh.write("- **CP location**: 50% of mean chord (supersonic uniform-pressure).\n\n")
        fh.write("## Geometry\n\n")
        fh.write(f"- Body diameter: {geometry.d_ref_m:.4f} m\n")
        fh.write(f"- Total length: {geometry.total_length_m:.5f} m\n")
        fh.write(f"- Fin span (exposed): {geometry.fin_span_m:.4f} m\n")
        fh.write(f"- Fin root chord: {geometry.fin_root_chord_m:.4f} m\n")
        fh.write(f"- Fin tip chord: {geometry.fin_tip_chord_m:.4f} m\n")
        fh.write(f"- Fin sweep: {geometry.fin_sweep_deg:.2f} deg\n")
        fh.write(f"- CG (config): {geometry.cg_from_nose_m:.4f} m from nose\n\n")
        fh.write(f"## Results at Ma {CRUISE_MACH} (cruise condition)\n\n")
        fh.write(f"- **Nose CN_alpha**: {ackeret_result['cn_alpha_nose']:.6f} [1/rad]\n")
        fh.write(
            f"- **Transition CN_alpha**: {ackeret_result['cn_alpha_transition']:.6f} [1/rad]\n"
        )
        fh.write(
            f"- **Fins CN_alpha (Ackeret)**: {ackeret_result['cn_alpha_fins']:.6f} [1/rad]\n"
        )
        fh.write(
            f"- **Total CN_alpha**: {ackeret_result['cn_alpha_total']:.6f} [1/rad]\n\n"
        )
        fh.write(f"- **Nose CP**: {ackeret_result['x_cp_nose']:.6f} m from nose\n")
        fh.write(
            f"- **Transition CP**: {ackeret_result['x_cp_transition']:.6f} m from nose\n"
        )
        fh.write(
            f"- **Fins CP (Ackeret)**: {ackeret_result['x_cp_fins']:.6f} m from nose\n"
        )
        fh.write(
            f"- **Total CP**: {ackeret_result['x_cp_total']:.6f} m from nose\n\n"
        )
        fh.write(
            f"- **Static margin**: {ackeret_result['static_margin_cal']:.6f} cal "
            f"({'STABLE' if ackeret_result['stable_bool'] else 'UNSTABLE'})\n\n"
        )
        fh.write("## Comparison with DATCOM-class method\n\n")
        fh.write(
            "See `datcom_class_sweep.csv` for the DATCOM-class fin CP at Ma 2.5, "
            "CG = 0.37 L (config anchor).\n\n"
        )
        fh.write(
            "**Agreement criterion**: Ackeret fin CP should be within ~one caliber "
            f"({geometry.d_ref_m:.4f} m) of the DATCOM fin CP, and both should "
            "agree on sign (fins push CP aft, stabilizing).\n"
        )


def main(config_path: Path | str = DEFAULT_VEHICLE_CONFIG) -> dict[str, Any]:
    """Run the Ackeret fin hand-check at cruise Ma, config CG.

    Args:
        config_path: Path to the ramjet-rocket ``vehicle_config.yaml``.

    Returns:
        Result dict.
    """
    geometry = load_geometry(config_path)
    cg_from_nose_m = geometry.cg_from_nose_m  # Config CG (0.37 L).
    result = compute_whole_vehicle_sm_ackeret(geometry, CRUISE_MACH, cg_from_nose_m)
    write_markdown_report(geometry, result, MARKDOWN_PATH)

    print(f"Ackeret fin check complete at Ma {CRUISE_MACH}, CG = {cg_from_nose_m:.4f} m.")
    print(f"Markdown report: {MARKDOWN_PATH}")
    print(f"Ackeret fin CN_alpha: {result['cn_alpha_fins']:.6f} [1/rad]")
    print(f"Ackeret fin CP: {result['x_cp_fins']:.6f} m from nose")
    print(f"Static margin: {result['static_margin_cal']:.6f} cal ({'STABLE' if result['stable_bool'] else 'UNSTABLE'})")

    return result


if __name__ == "__main__":
    res = main()
    print(json.dumps(res, indent=2))
