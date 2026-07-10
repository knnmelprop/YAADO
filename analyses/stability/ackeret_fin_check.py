# MELprop-IADE | analyses.stability.ackeret_fin_check | v0.1.0
"""Independent Ackeret fin cross-check at Mach 2.5 (Project B ramjet rocket).

Provides a closed-form hand-check of the fins ONLY using pure Ackeret 2D
thin-airfoil theory (CN_alpha_fin = 4/beta per rad, uniform load, CP at
0.50 MAC) and slender-body potential lift for the body (no crossflow).

Purpose: verify SIGN agreement with the DATCOM-class buildup at Mach 2.5.
This is a minimal independent cross-check, not a full flight-analysis method.

Theory references
------------------
- Ackeret, J., "Air Forces on Airfoils Moving Faster than Sound,"
  NACA TM 317, 1925. (Pure 2D supersonic thin-airfoil theory.)
- Barrowman 1967 (slender-body potential lift, reused here).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analyses.stability.barrowman_stability import (  # noqa: E402
    RocketGeometry,
    load_geometry,
)

# Output path.
MD_PATH = Path(__file__).resolve().parent / "ackeret_fin_check.md"

# Comparison conditions.
MACH_CHECK = 2.5
CG_NOMINAL = 1.6084  # Fusion full-stack CG.


def ackeret_fin_cn_alpha_and_cp(geometry: RocketGeometry, mach: float) -> tuple[float, float]:
    """Pure Ackeret 2D fin CN_alpha and CP (mid-chord).

    No finite-span correction, no interference — just the 2D slope
    4/beta applied to the total fin planform area, referenced to A_ref,
    and the CP at 0.50 MAC due to the uniform supersonic load.

    Args:
        geometry: Rocket geometry.
        mach: Freestream Mach number (must be > 1).

    Returns:
        Tuple of (CN_alpha [1/rad, ref. A_ref], x_cp [m from nose]).

    Reference:
        Ackeret 1925.
    """
    if mach <= 1.0:
        raise ValueError(f"Ackeret theory requires Mach > 1, got {mach}")

    beta = math.sqrt(mach**2 - 1.0)

    # 2D Ackeret slope: 4 / beta per radian.
    slope_2d = 4.0 / beta

    # Total fin planform area: N fins × exposed panel area.
    n_fins = geometry.fin_count
    s = geometry.fin_span_m
    c_mean = 0.5 * (geometry.fin_root_chord_m + geometry.fin_tip_chord_m)
    a_fin_total = n_fins * s * c_mean

    # Reference area.
    a_ref = math.pi / 4.0 * geometry.d_ref_m**2

    cn_alpha = slope_2d * (a_fin_total / a_ref)

    # CP at mid-chord (0.50 MAC).
    sweep_le_rad = math.radians(geometry.fin_sweep_deg)
    mac_sweep_offset = (s / 2.0) * math.tan(sweep_le_rad)
    x_cp = geometry.fin_root_le_x_m + mac_sweep_offset + 0.5 * c_mean

    return cn_alpha, x_cp


def body_slender_cn_alpha_and_cp(geometry: RocketGeometry) -> tuple[float, float]:
    """Slender-body potential lift (Mach-invariant).

    CN_alpha = 2.0 (referenced to A_ref for a pointed body with A_max = A_ref),
    CP at (2/3) * L_nose from the tip (conical nose).

    Args:
        geometry: Rocket geometry.

    Returns:
        Tuple of (CN_alpha [1/rad, ref. A_ref], x_cp [m from nose]).

    Reference:
        Barrowman 1967.
    """
    cn_alpha = 2.0
    x_cp = (2.0 / 3.0) * geometry.nose_length_m
    return cn_alpha, x_cp


def run_ackeret_check(
    geometry: RocketGeometry | None = None,
    mach: float = MACH_CHECK,
    cg_m: float = CG_NOMINAL,
    md_path: Path | str = MD_PATH,
) -> dict[str, float]:
    """Run the Ackeret fin + slender-body cross-check at a single point.

    Args:
        geometry: Rocket geometry. If None, loads from default YAML.
        mach: Mach number.
        cg_m: Center of gravity [m from nose].
        md_path: Output markdown path.

    Returns:
        Dict with CN_alpha components, CP, and static margin.
    """
    if geometry is None:
        geometry = load_geometry()

    # Body: slender-body potential only (no crossflow).
    cn_body, x_cp_body = body_slender_cn_alpha_and_cp(geometry)

    # Fins: pure Ackeret 2D.
    cn_fins, x_cp_fins = ackeret_fin_cn_alpha_and_cp(geometry, mach)

    # Total.
    cn_total = cn_body + cn_fins
    x_cp_m = (cn_body * x_cp_body + cn_fins * x_cp_fins) / cn_total

    static_margin_cal = (x_cp_m - cg_m) / geometry.d_ref_m

    # Write markdown report.
    md_path = Path(md_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    with md_path.open("w", encoding="utf-8") as fh:
        fh.write("# Ackeret Fin Cross-Check (Mach 2.5, ramjet rocket)\n\n")
        fh.write("**Purpose:** Independent closed-form hand-check of fin stability.\n\n")
        fh.write(f"**Mach:** {mach:.2f}\n\n")
        fh.write(f"**CG (nominal):** {cg_m:.4f} m from nose\n\n")
        fh.write(f"**Body diameter (d_ref):** {geometry.d_ref_m:.3f} m\n\n")
        fh.write("## Component Breakdown\n\n")
        fh.write(f"- **Body (slender-body potential):** CN_alpha = {cn_body:.6f} /rad, ")
        fh.write(f"CP = {x_cp_body:.6f} m\n")
        fh.write(f"- **Fins (pure Ackeret 2D):** CN_alpha = {cn_fins:.6f} /rad, ")
        fh.write(f"CP = {x_cp_fins:.6f} m\n")
        fh.write(f"- **Total:** CN_alpha = {cn_total:.6f} /rad, CP = {x_cp_m:.6f} m\n\n")
        fh.write("## Static Margin\n\n")
        fh.write(f"**SM = (CP - CG) / d_ref = ({x_cp_m:.6f} - {cg_m:.4f}) / {geometry.d_ref_m:.3f}")
        fh.write(f" = {static_margin_cal:.6f} cal**\n\n")

        sign_str = "POSITIVE (stable)" if static_margin_cal > 0 else "NEGATIVE (unstable)"
        fh.write(f"**SIGN: {sign_str}**\n\n")
        fh.write("## Comparison to DATCOM-class\n\n")
        fh.write(
            "This Ackeret check uses NO crossflow, NO finite-span correction, "
            "and NO fin-body interference. It should agree in SIGN with the "
            "DATCOM-class buildup at Mach 2.5 (same CG), even if the absolute "
            "values differ.\n\n"
        )
        fh.write("Reference: Ackeret 1925; Barrowman 1967.\n")

    return {
        "cn_alpha_body": cn_body,
        "cn_alpha_fins": cn_fins,
        "cn_alpha_total": cn_total,
        "x_cp_m": x_cp_m,
        "static_margin_cal": static_margin_cal,
    }


if __name__ == "__main__":
    result = run_ackeret_check()
    print(f"Ackeret fin check (Mach {MACH_CHECK:.2f}, CG {CG_NOMINAL:.4f} m):")
    print(f"  CN_alpha_body = {result['cn_alpha_body']:.6f}")
    print(f"  CN_alpha_fins = {result['cn_alpha_fins']:.6f}")
    print(f"  CN_alpha_total = {result['cn_alpha_total']:.6f}")
    print(f"  CP = {result['x_cp_m']:.6f} m")
    print(f"  SM = {result['static_margin_cal']:.6f} cal")
    print(f"\nMarkdown written to: {MD_PATH}")
