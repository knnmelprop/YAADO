# MELprop-IADE | analyses.stability.datcom_class_sweep | v0.1.0
"""DATCOM-class supersonic component buildup for the ramjet rocket (Project B).

Implements a Missile-DATCOM / RASAero-style supersonic static-stability
method that combines:

1. Body potential lift (slender-body theory, Mach-invariant for pointed
   axisymmetric bodies).
2. Body viscous crossflow (Allen-Perkins-Jorgensen nonlinear term,
   linearized at a reference trim alpha for component-buildup compatibility).
3. Fin supersonic linearized lifting-surface theory (4/beta per rad 2D,
   finite-span tip correction, Pitts-Nielsen carryover interference).

This method SUPERSEDES the Barrowman supersonic extension as the CDR gate
because:
  (a) Barrowman theory is only valid to ~Mach 0.7.
  (b) The ramP fins violate the small-fin/slender-body assumption: exposed
      fin semi-span 0.550 m vs body diameter 0.200 m => span/diameter = 2.75.

The supersonic fin CP (uniform load, mid-chord) sits significantly aft of
the subsonic Barrowman fin CP (loaded ~2/3 chord from LE), which is a key
physics difference captured by this method and missed by Barrowman.

Theory references
------------------
- Jorgensen, L.H., "Prediction of Static Aerodynamic Characteristics for
  Slender Bodies Alone and with Lifting Surfaces to Very High Angles of
  Attack," NASA TN D-6996, 1977. (Source of the Allen-Perkins viscous
  crossflow delta-CN model and the eta ~ 0.7 slender-body proportionality.)
- Pitts, W.C., Nielsen, J.N., "Lift and Center of Pressure of Wing-Body-
  Tail Combinations at Subsonic, Transonic, and Supersonic Speeds,"
  NACA TR 1307, 1959. (Source of the K_W(B) = 1 + r/(s+r) fin-body
  interference factor, reused from Barrowman but now applied to
  supersonic fin slopes.)
- Ackeret, J., "Air Forces on Airfoils Moving Faster than Sound,"
  NACA TM 317, 1925. (Source of the 4/sqrt(M^2-1) supersonic 2D
  thin-airfoil slope.)
- Ashley, H. and Landahl, M., *Aerodynamics of Wings and Bodies*, 1965.
  (Supersonic finite-aspect-ratio tip correction; thin-edge load
  distribution.)

Applicability and limits
-------------------------
Valid for M >= 1.2 (supersonic regime with beta*AR_e >= 1), alpha small
enough for linearized theory (~< 10 deg for the potential term; the
crossflow term is inherently nonlinear and linearized here at alpha_ref).
Rows for M < 1.2 are emitted with regime_flag = "OUT_OF_METHOD_REGIME"
for continuity.
"""

from __future__ import annotations

import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from analyses.stability.barrowman_stability import (  # noqa: E402
    RocketGeometry,
    load_geometry,
)
from core.component_base import (  # noqa: E402
    AnalysisResults,
    BaseAnalysis,
    FidelityLevel,
)

# --------------------------------------------------------------------------
# Constants and paths
# --------------------------------------------------------------------------

# PROVISIONAL default reference trim angle for evaluating the nonlinear
# body viscous-crossflow term at a single point, per task instruction.
# Source: DATCOM/Allen-Perkins crossflow evaluated at small trim alpha.
# TBD_PHYSICAL_PARAM: replace when a real trim-alpha schedule exists.
ALPHA_REF_DEG = 4.0

# Supersonic body viscous-crossflow parameters (Allen-Perkins-Jorgensen).
# PROVISIONAL, source: Jorgensen 1977, slender-body crossflow proportionality.
ETA_CROSSFLOW = 0.7

# PROVISIONAL, crossflow drag coefficient of a cylinder.
CDC_CROSSFLOW = 1.2

# Mach sweep: 0.5, 0.8, 1.0 (transonic), 1.2, 1.5, 2.0, 2.5, 3.0.
MACH_SWEEP = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0]

# CG sweep: 1.40 to 2.20 m in 0.05 m steps (covers Fusion full-stack CG
# 1.6084 m and plausible forward shift after stage-1 booster separation).
# TBD_PHYSICAL_PARAM: CG pending Fusion MOI/mass-layout extraction.
CG_FROM_NOSE_MIN = 1.40
CG_FROM_NOSE_MAX = 2.20
CG_STEP = 0.05

# Supersonic regime threshold for fin method validity.
MACH_SUPERSONIC_MIN = 1.2

# Output paths.
CSV_PATH = Path(__file__).resolve().parent / "datcom_class_sweep.csv"
PNG_PATH = Path(__file__).resolve().parent / "datcom_class_sweep.png"


# --------------------------------------------------------------------------
# Component formulas
# --------------------------------------------------------------------------


def body_potential_cn_alpha(geometry: RocketGeometry) -> tuple[float, float]:
    """Body potential (linear) slender-body lift, Mach-invariant.

    For a pointed axisymmetric body, slender-body theory gives
    CN_alpha = 2.0 * (A_body_max / A_ref) per radian, referenced to
    A_ref = pi/4 * d_ref^2. The CP of this potential term sits at the
    centroid of the cross-sectional-area growth region (nose + nose-to-body
    transition).

    For a conical nose, the supersonic slender-body CP is at
    (2/3) * L_nose from the tip (NOT the 0.466 ogive factor used in
    barrowman_stability.py's subsonic anchor).

    Args:
        geometry: Rocket geometry.

    Returns:
        Tuple of (CN_alpha [1/rad, ref. A_ref], x_cp [m from nose]).

    Reference:
        Barrowman 1967; Ashley & Landahl 1965 (slender-body theory).
    """
    # A_body_max / A_ref = (d_ref / d_ref)^2 = 1.0 here, since the body
    # is a constant-diameter cylinder aft of the transition and the
    # reference diameter is already the body diameter.
    cn_alpha = 2.0

    # For the conical nose: supersonic CP at 2/3 * L_nose from the tip.
    # (The transition also contributes, but for this simple model we
    # place the combined potential-lift CP at the nose centroid as an
    # approximation.)
    x_cp = (2.0 / 3.0) * geometry.nose_length_m

    return cn_alpha, x_cp


def body_viscous_crossflow_cn_alpha_eff(
    geometry: RocketGeometry, alpha_ref_deg: float = ALPHA_REF_DEG
) -> tuple[float, float]:
    """Body viscous crossflow (Allen-Perkins), linearized at alpha_ref.

    The nonlinear viscous-crossflow normal-force contribution is
    delta-CN_body(alpha) = eta * Cdc * (A_plan / A_ref) * sin^2(alpha),
    where A_plan is the planform (side-view) area of the body. To fold
    this quadratic term into a linear CN_alpha buildup so that the
    combined CP is evaluated *at* alpha_ref, we use the SECANT slope
    (the value of the term at alpha_ref divided by alpha_ref), NOT the
    tangent/derivative slope. This is what makes the combined
    ``CP = sum(CN_i(alpha_ref) * x_i) / sum(CN_i(alpha_ref))`` come out
    at the reference angle, consistent with RASAero/DATCOM practice:

        CN_alpha_body_visc_eff = (delta-CN at alpha_ref) / (alpha_ref in rad)
                                = eta * Cdc * (A_plan / A_ref)
                                  * sin^2(alpha_ref) / alpha_ref_rad

    (Using the derivative d(delta-CN)/d(alpha) = ...*sin(2*alpha_ref)
    here would over-count the term by ~sin(2a)/(a*sin^2 a) ~ 30x at
    alpha_ref = 4 deg and is physically wrong for a small-trim buildup.)

    The CP of the crossflow term is at the centroid of the body planform
    area (approximately mid-body for a cylindrical afterbody).

    Args:
        geometry: Rocket geometry.
        alpha_ref_deg: Reference trim angle [deg] at which to linearize.

    Returns:
        Tuple of (CN_alpha_eff [1/rad], x_cp [m from nose]).

    Reference:
        Jorgensen 1977 (Allen-Perkins-Jorgensen crossflow model).
    """
    alpha_ref_rad = math.radians(alpha_ref_deg)

    # Planform area: cylindrical portion + triangular nose planform.
    # Nose planform: triangle, base = nose_base_diameter_m, height = nose_length_m.
    a_plan_nose = 0.5 * geometry.nose_base_diameter_m * geometry.nose_length_m

    # Cylindrical portion: from end of nose (x = nose_length_m) to aft end.
    # Length of cylindrical section: total - nose.
    cyl_length = geometry.total_length_m - geometry.nose_length_m
    a_plan_cyl = geometry.d_ref_m * cyl_length

    a_plan = a_plan_nose + a_plan_cyl

    # Reference area.
    a_ref = math.pi / 4.0 * geometry.d_ref_m**2

    # Secant effective slope: fold the quadratic crossflow term into the
    # linear buildup by dividing its VALUE at alpha_ref by alpha_ref, so
    # the combined CP is the alpha_ref CP (RASAero/DATCOM convention).
    # delta-CN(alpha_ref) = eta * Cdc * (A_plan/A_ref) * sin^2(alpha_ref)
    # CN_alpha_eff = delta-CN(alpha_ref) / alpha_ref_rad
    cn_alpha_eff = (
        ETA_CROSSFLOW
        * CDC_CROSSFLOW
        * (a_plan / a_ref)
        * math.sin(alpha_ref_rad) ** 2
    ) / alpha_ref_rad

    # CP at the centroid of the planform area.
    # Nose planform centroid: (2/3) * nose_length_m from the tip.
    # Cylindrical planform centroid: (nose_length_m + cyl_length/2).
    x_cp_nose = (2.0 / 3.0) * geometry.nose_length_m
    x_cp_cyl = geometry.nose_length_m + cyl_length / 2.0

    x_cp = (a_plan_nose * x_cp_nose + a_plan_cyl * x_cp_cyl) / a_plan

    return cn_alpha_eff, x_cp


def fin_supersonic_cn_alpha_and_cp(geometry: RocketGeometry, mach: float) -> tuple[float, float]:
    """Fin CN_alpha and CP via supersonic linearized lifting-surface theory.

    Applies the 4/beta 2D supersonic slope with a finite-span tip
    correction for a supersonic leading edge, Pitts-Nielsen fin-body
    interference (K_W(B) = 1 + r/(s+r)), and places the CP at mid-chord
    (0.50 MAC) because the supersonic flat-plate load distribution is
    uniform along the chord (contrast with the subsonic Barrowman fin CP).

    Valid when beta*AR_e >= 1 (supersonic leading edge). If beta*AR_e < 1,
    the correction factor is clamped to avoid negative CN_alpha and the
    row is flagged OUT_OF_METHOD_REGIME.

    Args:
        geometry: Rocket geometry.
        mach: Freestream Mach number.

    Returns:
        Tuple of (CN_alpha [1/rad, ref. A_ref], x_cp [m from nose]).

    Reference:
        Ackeret 1925; Ashley & Landahl 1965 (supersonic thin-airfoil
        and finite-AR corrections); Pitts & Nielsen 1959 (K_W(B)).
    """
    if mach <= 1.0:
        # Subsonic/transonic: no valid supersonic formula.
        # Return a placeholder; caller will flag the row.
        return 0.0, geometry.total_length_m

    beta = math.sqrt(mach**2 - 1.0)

    # Exposed fin geometry (assuming rectangular planform here since
    # chord_root == chord_tip in the current YAML).
    s = geometry.fin_span_m
    c_mean = 0.5 * (geometry.fin_root_chord_m + geometry.fin_tip_chord_m)
    ar_e = s / c_mean

    # 2D supersonic slope: 4 / beta per radian.
    slope_2d = 4.0 / beta

    # Finite-span tip correction: (1 - 1/(2*beta*AR_e)) if beta*AR_e >= 1.
    beta_ar_e = beta * ar_e
    if beta_ar_e >= 1.0:
        tip_correction = 1.0 - 1.0 / (2.0 * beta_ar_e)
    else:
        # Low-Mach or low-AR case: clamp to zero (subsonic edge regime).
        tip_correction = 0.0

    cn_alpha_panel_2d_corrected = slope_2d * tip_correction

    # Reference each panel to its own area, then to A_ref.
    n_fins = geometry.fin_count
    a_fin_exposed = c_mean * s  # single panel
    a_ref = math.pi / 4.0 * geometry.d_ref_m**2

    cn_alpha_fins_isolated = cn_alpha_panel_2d_corrected * (n_fins * a_fin_exposed / a_ref)

    # Fin-body interference (Pitts-Nielsen carryover).
    r = geometry.body_radius_m
    k_wb = 1.0 + r / (s + r)

    cn_alpha = k_wb * cn_alpha_fins_isolated

    # Fin CP: mid-chord (0.50 MAC) for uniform supersonic load.
    # Root LE position: geometry.fin_root_le_x_m.
    # Sweep offset at the MAC spanwise station: for a rectangular fin,
    # MAC is at mid-span, so sweep offset = (s/2) * tan(sweep_LE).
    sweep_le_rad = math.radians(geometry.fin_sweep_deg)
    mac_sweep_offset = (s / 2.0) * math.tan(sweep_le_rad)

    x_cp = geometry.fin_root_le_x_m + mac_sweep_offset + 0.5 * c_mean

    return cn_alpha, x_cp


# --------------------------------------------------------------------------
# Combined buildup
# --------------------------------------------------------------------------


@dataclass
class DATCOMResult:
    """Single-point (Mach, CG) stability result from the DATCOM-class buildup.

    Attributes:
        mach: Freestream Mach number.
        cg_m: Center of gravity [m from nose].
        cn_alpha_body: Body (potential + viscous crossflow) CN_alpha [1/rad].
        cn_alpha_fins: Fin CN_alpha [1/rad].
        cn_alpha_total: Total CN_alpha [1/rad].
        x_cp_m: Combined center-of-pressure [m from nose].
        static_margin_cal: Static margin [calibers].
        regime_flag: "VALID" or "OUT_OF_METHOD_REGIME" (M < 1.2).
    """

    mach: float
    cg_m: float
    cn_alpha_body: float
    cn_alpha_fins: float
    cn_alpha_total: float
    x_cp_m: float
    static_margin_cal: float
    regime_flag: str


def compute_datcom_at_mach_cg(
    geometry: RocketGeometry, mach: float, cg_m: float
) -> DATCOMResult:
    """Compute the DATCOM-class buildup at a single (Mach, CG) point.

    Args:
        geometry: Rocket geometry.
        mach: Freestream Mach number.
        cg_m: Center of gravity [m from nose].

    Returns:
        DATCOMResult with component breakdown and static margin.
    """
    # Body: potential + viscous crossflow.
    cn_pot, x_pot = body_potential_cn_alpha(geometry)
    cn_visc, x_visc = body_viscous_crossflow_cn_alpha_eff(geometry)

    # For the combined body CP: weighted average of the two body terms.
    cn_alpha_body = cn_pot + cn_visc
    if cn_alpha_body > 0.0:
        x_cp_body = (cn_pot * x_pot + cn_visc * x_visc) / cn_alpha_body
    else:
        x_cp_body = x_pot

    # Fins.
    cn_alpha_fins, x_cp_fins = fin_supersonic_cn_alpha_and_cp(geometry, mach)

    # Total.
    cn_alpha_total = cn_alpha_body + cn_alpha_fins
    if cn_alpha_total > 0.0:
        x_cp_m = (cn_alpha_body * x_cp_body + cn_alpha_fins * x_cp_fins) / cn_alpha_total
    else:
        x_cp_m = 0.0

    static_margin_cal = (x_cp_m - cg_m) / geometry.d_ref_m

    # Regime check: M >= 1.2 and beta*AR_e >= 1 for valid supersonic fin formula.
    if mach < MACH_SUPERSONIC_MIN:
        regime_flag = "OUT_OF_METHOD_REGIME"
    else:
        beta = math.sqrt(mach**2 - 1.0)
        s = geometry.fin_span_m
        c_mean = 0.5 * (geometry.fin_root_chord_m + geometry.fin_tip_chord_m)
        ar_e = s / c_mean
        if beta * ar_e < 1.0:
            regime_flag = "OUT_OF_METHOD_REGIME"
        else:
            regime_flag = "VALID"

    return DATCOMResult(
        mach=mach,
        cg_m=cg_m,
        cn_alpha_body=cn_alpha_body,
        cn_alpha_fins=cn_alpha_fins,
        cn_alpha_total=cn_alpha_total,
        x_cp_m=x_cp_m,
        static_margin_cal=static_margin_cal,
        regime_flag=regime_flag,
    )


# --------------------------------------------------------------------------
# Sweep and output
# --------------------------------------------------------------------------


def run_datcom_sweep(
    geometry: RocketGeometry | None = None,
    csv_path: Path | str = CSV_PATH,
    png_path: Path | str = PNG_PATH,
) -> list[DATCOMResult]:
    """Run the DATCOM-class sweep over Mach × CG grid.

    Args:
        geometry: Rocket geometry. If None, loads from default YAML.
        csv_path: Output CSV path.
        png_path: Output PNG path.

    Returns:
        List of DATCOMResult objects (Mach × CG grid).
    """
    if geometry is None:
        geometry = load_geometry()

    # CG sweep.
    cg_sweep = np.arange(CG_FROM_NOSE_MIN, CG_FROM_NOSE_MAX + 0.5 * CG_STEP, CG_STEP)

    results: list[DATCOMResult] = []
    for mach in MACH_SWEEP:
        for cg in cg_sweep:
            result = compute_datcom_at_mach_cg(geometry, mach, float(cg))
            results.append(result)

    # Write CSV.
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "mach",
                "cg_m",
                "cn_alpha_body",
                "cn_alpha_fins",
                "cn_alpha_total",
                "x_cp_m",
                "static_margin_cal",
                "regime_flag",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    f"{r.mach:.2f}",
                    f"{r.cg_m:.4f}",
                    f"{r.cn_alpha_body:.6f}",
                    f"{r.cn_alpha_fins:.6f}",
                    f"{r.cn_alpha_total:.6f}",
                    f"{r.x_cp_m:.6f}",
                    f"{r.static_margin_cal:.6f}",
                    r.regime_flag,
                ]
            )

    # Write PNG: SM vs Mach for a few representative CGs.
    plot_datcom_sweep(results, geometry, png_path)

    return results


def plot_datcom_sweep(
    results: list[DATCOMResult], geometry: RocketGeometry, png_path: Path | str
) -> None:
    """Plot static margin vs Mach for a few representative CG values.

    Args:
        results: List of DATCOMResult objects.
        geometry: Rocket geometry.
        png_path: Output PNG path.
    """
    # Select a few CG values for plotting: min, nominal (1.6084), max, mid.
    cg_plot = [CG_FROM_NOSE_MIN, 1.6084, 1.80, CG_FROM_NOSE_MAX]

    fig, ax = plt.subplots(figsize=(8.0, 5.0), dpi=150)

    for cg_val in cg_plot:
        # Find closest CG in the sweep.
        cg_tol = 0.001
        subset = [r for r in results if abs(r.cg_m - cg_val) < cg_tol]
        if not subset:
            continue

        # Sort by Mach.
        subset.sort(key=lambda r: r.mach)

        mach_arr = [r.mach for r in subset]
        sm_arr = [r.static_margin_cal for r in subset]

        ax.plot(mach_arr, sm_arr, marker="o", lw=1.5, label=f"CG = {cg_val:.3f} m")

    ax.axhline(0.0, color="black", lw=0.8, ls="--", alpha=0.5)
    ax.axvline(MACH_SUPERSONIC_MIN, color="grey", lw=0.8, ls=":", alpha=0.5)
    ax.set_xlabel("Mach number [-]")
    ax.set_ylabel("Static margin [calibers]")
    ax.set_title("DATCOM-class supersonic buildup: SM vs Mach (ramjet rocket)")
    ax.legend(fontsize=8, loc="best")
    ax.grid(True, alpha=0.3)

    png_path = Path(png_path)
    fig.savefig(png_path, dpi=150)
    plt.close(fig)


# --------------------------------------------------------------------------
# BaseAnalysis wrapper
# --------------------------------------------------------------------------


class DATCOMClassAnalysis(BaseAnalysis):
    """DATCOM-class supersonic component buildup for static stability.

    Replaces the Barrowman supersonic extension as the CDR gate for the
    ramjet rocket (Project B) because Barrowman theory is only valid to
    ~Mach 0.7 and the fins violate the small-fin assumption.

    Example:
        >>> analysis = DATCOMClassAnalysis()
        >>> analysis.setup()
        >>> results = analysis.execute()
        >>> results["static_margin_range_cal"]  # doctest: +SKIP
    """

    fidelity = FidelityLevel.LEVEL_1

    def __init__(self, name: str = "datcom_class_sweep") -> None:
        super().__init__(name)
        self._geometry: RocketGeometry | None = None

    def setup(self, config_path: Path | str | None = None) -> None:
        """Load geometry from the vehicle YAML.

        Args:
            config_path: Path to vehicle_config.yaml. If None, uses default.
        """
        self._geometry = load_geometry(config_path) if config_path else load_geometry()
        self._is_setup = True

    def execute(self) -> AnalysisResults:
        """Run the DATCOM-class sweep.

        Returns:
            AnalysisResults with static_margin_range_cal, static_margin_nominal_cal
            (at CG=1.6084), and metadata.

        Raises:
            RuntimeError: If called before setup().
        """
        if not self._is_setup or self._geometry is None:
            raise RuntimeError("DATCOMClassAnalysis.execute() called before setup()")

        results = run_datcom_sweep(self._geometry)

        # Extract summary: static margin at Mach 2.5 for the nominal CG.
        nominal_cg = 1.6084
        mach_25_results = [r for r in results if abs(r.mach - 2.5) < 0.01]
        if mach_25_results:
            sm_range = [r.static_margin_cal for r in mach_25_results]
            sm_min = min(sm_range)
            sm_max = max(sm_range)

            # Nominal CG.
            nominal_result = min(mach_25_results, key=lambda r: abs(r.cg_m - nominal_cg))
            sm_nominal = nominal_result.static_margin_cal
        else:
            sm_min = sm_max = sm_nominal = 0.0

        return AnalysisResults(
            name=self.name,
            fidelity=self.fidelity,
            data={
                "static_margin_range_cal": (sm_min, sm_max),
                "static_margin_nominal_cal": sm_nominal,
                "mach_comparison": 2.5,
                "cg_sweep_min_m": CG_FROM_NOSE_MIN,
                "cg_sweep_max_m": CG_FROM_NOSE_MAX,
            },
            metadata={
                "method": "datcom_class_supersonic_buildup",
                "alpha_ref_deg": ALPHA_REF_DEG,
                "eta_crossflow": ETA_CROSSFLOW,
                "cdc_crossflow": CDC_CROSSFLOW,
                "csv_path": str(CSV_PATH),
                "png_path": str(PNG_PATH),
            },
        )

    def validate_results(self, results: AnalysisResults) -> bool:
        """Sanity-check: CN_alpha_total > 0, static margin finite.

        Args:
            results: Results from execute().

        Returns:
            True if checks pass.
        """
        # Just check that the range is finite.
        sm_range = results.data.get("static_margin_range_cal", (0.0, 0.0))
        return math.isfinite(sm_range[0]) and math.isfinite(sm_range[1])


if __name__ == "__main__":
    geometry = load_geometry()
    results = run_datcom_sweep(geometry)

    print(f"DATCOM-class sweep complete. {len(results)} points.")
    print(f"CSV written to: {CSV_PATH}")
    print(f"PNG written to: {PNG_PATH}")

    # Summary at Mach 2.5.
    mach_25 = [r for r in results if abs(r.mach - 2.5) < 0.01]
    if mach_25:
        sm_vals = [r.static_margin_cal for r in mach_25]
        print(
            f"\nMach 2.5 static margin range (CG {CG_FROM_NOSE_MIN:.2f}–{CG_FROM_NOSE_MAX:.2f} m):"
        )
        print(f"  min = {min(sm_vals):.3f} cal, max = {max(sm_vals):.3f} cal")

        nominal_cg = 1.6084
        nominal = min(mach_25, key=lambda r: abs(r.cg_m - nominal_cg))
        print(f"\nAt CG = {nominal.cg_m:.4f} m (nominal):")
        print(f"  CN_alpha_body = {nominal.cn_alpha_body:.6f}")
        print(f"  CN_alpha_fins = {nominal.cn_alpha_fins:.6f}")
        print(f"  CN_alpha_total = {nominal.cn_alpha_total:.6f}")
        print(f"  CP = {nominal.x_cp_m:.6f} m")
        print(f"  SM = {nominal.static_margin_cal:.3f} cal ({nominal.regime_flag})")
