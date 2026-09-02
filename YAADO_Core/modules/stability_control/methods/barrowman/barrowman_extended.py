"""Extended Barrowman static-stability sensitivity analysis (Generic Vehicle).

Extends the existing subsonic/supersonic Barrowman method in
``analyses.stability.barrowman_stability`` with two additional
corrections used by "practical" Barrowman implementations (RockSim /
OpenRocket-style "extended Barrowman"), and sweeps the suspect
``fins.span_m`` geometry field to quantify how much of the
Barrowman-vs-Teltik-CFD static-margin discrepancy documented in
``docs/vehicle/stability_reconciliation.md`` (+8.99 cal Barrowman vs. -2.75
cal Teltik CFD at Mach 2.5) each correction, and each candidate fin
span, can explain.

This module does **not** reimplement the base Barrowman formulas: nose,
transition, and fin ``CN_alpha``/CP are all obtained by calling
``analyses.stability.barrowman_stability.compute_stability_at_mach``
(and its component helpers) directly. Only two new pieces of physics
are added here:

1. **Galejs body-lift correction** -- an empirical cylindrical-afterbody
   normal-force contribution, referenced to the body's planform
   (side-projection) area, that classical linear Barrowman omits
   because pure slender-body potential theory predicts zero normal
   force from a constant-cross-section cylinder (Munk's theorem). Real
   (viscous, cross-flow-separated) afterbodies do generate normal force
   at nonzero angle of attack; Galejs' extension -- as used by
   RockSim/OpenRocket -- adds it back in as
   ``CN_alpha_body = 2 * K_body * (A_planform_body / A_ref)``.
2. **Prandtl-Glauert / Ackeret compressibility on the fin CN_alpha** --
   this module does **not** re-derive this: it is already implemented
   in ``barrowman_stability.fin_mach_correction_factor`` (Prandtl-Glauert
   subsonic branch, linear transonic bridge, Ackeret supersonic branch)
   and is reused as-is via ``compute_stability_at_mach``. Applying a
   second compressibility factor here would double-count the
   correction, so this module never touches fin CN_alpha directly.

Theory references
------------------
- Barrowman, J. S. and Barrowman, J. A., *The Theoretical Prediction of
  the Center of Pressure*, NARAM-8, 1966; Barrowman, J. S., *The
  Practical Calculation of the Aerodynamic Characteristics of Slender
  Finned Vehicles*, MS Thesis, The Catholic University of America, 1967.
- Galejs, R., *Where is the Center of Pressure?*, describing the
  planform-area body-lift extension used in RockSim/OpenRocket, which
  restores a nonzero cylindrical-afterbody normal force that first-order
  slender-body (Munk) theory omits.
- Allen, H. J. and Perkins, E. W., *A Study of Effects of Viscosity on
  Flow over Slender Inclined Bodies of Revolution*, NACA Report 1048
  (1951) -- physical motivation for nonzero cylindrical-body cross-flow
  normal force at angle of attack (the "viscous crossflow" term the
  Galejs planform-area correction approximates in linearized form).
- Munk, M. M., *The Aerodynamic Forces on Airship Hulls*, NACA Report
  184 (1924) -- slender-body potential-flow result that a
  constant-cross-section cylinder carries zero normal force, motivating
  why the base Barrowman nose+transition-only model needs the Galejs
  correction to capture the afterbody's real contribution.

Applicability and limits
-------------------------
Per project rule, AVL (subsonic VLM) is never used for this vehicle's
supersonic regime; this module only ever calls empirical/analytical
DATCOM-style correlations, consistent with
``analyses/stability/barrowman_stability.py``. This is a low-order
engineering estimate, not CFD -- see ``docs/vehicle/stability_reconciliation.md``
for the full discussion of why a large gap against the Teltik CFD result
is expected to remain even after both corrections in this module.

This module is analysis-only: it never writes to
``Hangar/generic_vehicle/vehicle_config.yaml`` (frozen, HUMAN_REVIEW
pending) and never modifies ``analyses/stability/barrowman_stability.py``.
"""

from __future__ import annotations

import csv
import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

if __name__ == "__main__" and __package__ in (None, ""):
    # Allow `python3 analyses/aero/barrowman_extended.py` direct execution
    # by putting the repository root on sys.path (mirrors
    # barrowman_stability.py's own bootstrap).
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (backend must be set first)
import numpy as np  # noqa: E402

from YAADO_Core.modules.stability_control.methods.barrowman.barrowman_stability import (  # noqa: E402
    ComponentContribution,
    RocketGeometry,
    StabilityResult,
    compute_stability_at_mach,
    geometry_from_vehicle,
    load_geometry,
)
from YAADO_Core.Foundation.analysis_base import AnalysisResults, BaseAnalysis, FidelityLevel  # noqa: E402
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig  # noqa: E402

# --------------------------------------------------------------------------
# Named constants.
# --------------------------------------------------------------------------

#: Mach number used for the Teltik CFD comparison and the fin-span sweep,
#: per docs/vehicle/stability_reconciliation.md Section 3 ("Ma 2.5").
COMPARISON_MACH = 2.5

#: Teltik 2024 CFD static-margin result at COMPARISON_MACH, calibers.
#: Source: docs/vehicle/stability_margin_report.md / stability_reconciliation.md
#: (Barrowman +8.99 cal vs. Teltik CFD -2.75 cal discrepancy).
TELTIK_CFD_SM_CAL = -2.75

#: Minimum static margin generally considered "safe" for a finned rocket
#: (rule of thumb, e.g. NAR/TRA amateur-rocketry guidance: >= 1 caliber).
SM_MIN_SAFE_CAL = 1.0

#: Static margin above which the vehicle is flagged for human review as
#: still implausibly over-stable relative to the -2.75 cal CFD anchor
#: (task-specified threshold).
SM_REVIEW_THRESHOLD_CAL = 2.0

#: Fin-span sweep bounds, as a multiplicative factor on the YAML
#: `fins.span_m` value, per task specification.
FIN_SPAN_SWEEP_FACTOR_MIN = 0.4
FIN_SPAN_SWEEP_FACTOR_MAX = 1.6
FIN_SPAN_SWEEP_POINTS = 9

#: Bisection search bounds/precision for the neutral-span (SM=0) solve.
NEUTRAL_SPAN_SEARCH_MIN_M = 1.0e-4
NEUTRAL_SPAN_SEARCH_MAX_FACTOR = 5.0
NEUTRAL_SPAN_SEARCH_GRID_POINTS = 4000
NEUTRAL_SPAN_BISECTION_ITERATIONS = 60

#: Output artifact paths.
RESULTS_DIR = Path(__file__).resolve().parents[5] / "FlightLogs"
CSV_PATH = RESULTS_DIR / "SM_sensitivity_fin_span.csv"
PNG_PATH = RESULTS_DIR / "SM_sensitivity_fin_span.png"


# --------------------------------------------------------------------------
# Galejs body-lift correction.
# --------------------------------------------------------------------------


def reference_area_m2(d_ref_m: float) -> float:
    """Reference (body cross-section) area used by all CN_alpha terms.

    Args:
        d_ref_m: Body reference diameter [m].

    Returns:
        ``pi/4 * d_ref_m**2`` [m^2], matching the ``A_ref`` convention
        used throughout ``barrowman_stability.py``.
    """
    return math.pi / 4.0 * d_ref_m**2


def body_planform_area_and_centroid_m(geometry: RocketGeometry) -> tuple[float, float]:
    """Body-of-revolution planform (side-projection) area and its centroid.

    The body is split into three pieces along the axis, each with its
    own exact area + centroid formula, and combined by an area-weighted
    average (all measured from the nose tip, ``x = 0``):

    - **Nose** (``0 <= x <= nose_length_m``): local diameter grows
      linearly from 0 at the tip to ``nose_base_diameter_m`` -- a
      triangle in the (x, diameter) plane. Area = ``0.5 * d_base *
      L_nose``; centroid at ``(2/3) * L_nose`` from the tip (the
      standard result for a linear ramp from zero, i.e. an approximate
      confirmation of the task's "adjust for the conical nose
      contribution" instruction relative to the plain
      "0.5*L_body" cylindrical-body approximation).
    - **Transition/shoulder** (``nose_length_m <= x <= nose_length_m +
      transition_length_m``): local diameter grows linearly from
      ``nose_base_diameter_m`` to ``d_ref_m`` -- a trapezoid. Area =
      ``0.5*(d1+d2)*L_t``; centroid (from the start of the transition)
      at ``(L_t/3) * (d1 + 2*d2) / (d1 + d2)`` (standard linear-trapezoid
      centroid formula).
    - **Cylindrical afterbody** (remainder of ``total_length_m``):
      constant diameter ``d_ref_m`` -- a rectangle. Area = ``d_ref_m *
      L_cyl``; centroid at its axial midpoint, matching the task's
      "approx 0.5 * L_body from nose for a cylindrical body" baseline.

    Args:
        geometry: Rocket geometry (reused ``RocketGeometry`` from
            ``barrowman_stability``; ``transition_length_m`` here is the
            same ``TRANSITION_LENGTH_M`` engineering assumption used by
            the base module -- not re-derived).

    Returns:
        Tuple of (total planform area [m^2], area-weighted centroid
        location [m from nose tip]).
    """
    d1 = geometry.nose_base_diameter_m
    d2 = geometry.d_ref_m
    l_nose = geometry.nose_length_m
    l_trans = geometry.transition_length_m
    l_cyl = geometry.total_length_m - l_nose - l_trans

    area_nose = 0.5 * d1 * l_nose
    x_nose = (2.0 / 3.0) * l_nose

    area_trans = 0.5 * (d1 + d2) * l_trans
    x_trans = l_nose + (l_trans / 3.0) * (d1 + 2.0 * d2) / (d1 + d2)

    area_cyl = d2 * l_cyl
    x_cyl = l_nose + l_trans + l_cyl / 2.0

    area_total = area_nose + area_trans + area_cyl
    x_centroid = (
        area_nose * x_nose + area_trans * x_trans + area_cyl * x_cyl
    ) / area_total
    return area_total, x_centroid


def galejs_body_cn_alpha_and_cp(geometry: RocketGeometry) -> tuple[float, float]:
    """Galejs body-lift CN_alpha and CP location.

    ``CN_body_alpha = 2.0 * K_body * (A_planform_body / A_ref)`` with the
    Barrowman-original body-fin interference factor ``K_body = 1 +
    r_body / (r_body + r_fin)`` (``r_fin`` = exposed fin span), per task
    specification. Note this is the *same functional form* as the
    ``Kfb`` factor already applied to the fin CN_alpha in
    ``fin_cn_alpha_base_and_cp`` (Hoerner/Barrowman mutual body-fin
    interference), just evaluated as the reciprocal-role "body sees the
    fins" interference term rather than "fins see the body." It is
    computed independently here (not by calling into
    ``fin_cn_alpha_base_and_cp``) to avoid conflating the two distinct
    physical corrections.

    This term is Mach-invariant (first-order slender-body/cross-flow
    theory), consistent with how nose and transition CN_alpha are
    treated as Mach-invariant in ``barrowman_stability.py`` -- only the
    fin term there receives a compressibility correction.

    Args:
        geometry: Rocket geometry.

    Returns:
        Tuple of (CN_alpha [1/rad, ref. A_ref], x_cp [m from nose]).
    """
    r_body = geometry.body_radius_m
    r_fin = geometry.fin_span_m
    k_body = 1.0 + r_body / (r_body + r_fin)

    a_planform, x_cp = body_planform_area_and_centroid_m(geometry)
    a_ref = reference_area_m2(geometry.d_ref_m)
    cn_alpha = 2.0 * k_body * (a_planform / a_ref)
    return cn_alpha, x_cp


@dataclass
class ExtendedStabilityResult:
    """Basic + Galejs-extended stability result at a single Mach number.

    Attributes:
        mach: Freestream Mach number.
        basic: The unmodified ``compute_stability_at_mach`` result
            (nose + transition + fin, fin already Prandtl-Glauert/Ackeret
            corrected) -- reused, not recomputed.
        body: The Galejs body-lift component contribution added here.
        cn_alpha_extended: Total CN_alpha including the body term.
        x_cp_extended_m: Combined CP location including the body term.
    """

    mach: float
    basic: StabilityResult
    body: ComponentContribution
    cn_alpha_extended: float = 0.0
    x_cp_extended_m: float = 0.0


def compute_extended_stability_at_mach(
    geometry: RocketGeometry, mach: float
) -> ExtendedStabilityResult:
    """Compute the Galejs-extended CN_alpha/CP at a given Mach number.

    Calls ``barrowman_stability.compute_stability_at_mach`` for the
    nose/transition/fin (Mach-corrected) baseline -- no reimplementation
    -- then folds in the Galejs body-lift term computed by
    :func:`galejs_body_cn_alpha_and_cp`.

    Args:
        geometry: Rocket geometry.
        mach: Freestream Mach number (>= 0).

    Returns:
        :class:`ExtendedStabilityResult` with both the reused basic
        result and the extended (body-lift-corrected) total.
    """
    basic = compute_stability_at_mach(geometry, mach)
    cn_body, x_body = galejs_body_cn_alpha_and_cp(geometry)
    body_component = ComponentContribution("body_galejs", cn_body, x_body)

    cn_alpha_extended = basic.cn_alpha_total + cn_body
    x_cp_extended_m = (
        sum(c.cn_alpha * c.x_cp_m for c in basic.components) + cn_body * x_body
    ) / cn_alpha_extended

    return ExtendedStabilityResult(
        mach=mach,
        basic=basic,
        body=body_component,
        cn_alpha_extended=cn_alpha_extended,
        x_cp_extended_m=x_cp_extended_m,
    )


def static_margin_cal(x_cp_m: float, cg_m: float, d_ref_m: float) -> float:
    """Static margin in calibers, ``(x_cp - x_cg) / d_ref``.

    Args:
        x_cp_m: Center-of-pressure location [m from nose].
        cg_m: Center-of-gravity location [m from nose].
        d_ref_m: Reference (body) diameter [m].

    Returns:
        Static margin [calibers]. Positive = CP aft of CG = stable.
    """
    return (x_cp_m - cg_m) / d_ref_m


def sm_flag(sm_cal: float) -> str:
    """Classify a static margin into a coarse per-row CSV flag.

    Args:
        sm_cal: Static margin [calibers].

    Returns:
        ``"UNSTABLE"`` if ``sm_cal < 0``, ``"MARGINAL"`` if
        ``0 <= sm_cal < SM_MIN_SAFE_CAL``, else ``"STABLE"``.
    """
    if sm_cal < 0.0:
        return "UNSTABLE"
    if sm_cal < SM_MIN_SAFE_CAL:
        return "MARGINAL"
    return "STABLE"


# --------------------------------------------------------------------------
# Fin-span sensitivity sweep.
# --------------------------------------------------------------------------


@dataclass
class SweepRow:
    """One row of the fin-span sensitivity sweep.

    Attributes correspond 1:1 to the required CSV columns.
    """

    fin_span_factor: float
    fin_span_m: float
    cp_nose_m: float
    cp_fin_m: float
    cp_body_m: float
    cp_total_m: float
    cg_m: float
    sm_cal_basic: float
    sm_cal_extended: float
    sm_flag: str = field(init=False)

    def __post_init__(self) -> None:
        self.sm_flag = sm_flag(self.sm_cal_extended)


def evaluate_span(
    geometry: RocketGeometry, fin_span_m: float, mach: float = COMPARISON_MACH
) -> SweepRow:
    """Evaluate basic and extended stability for one candidate fin span.

    Args:
        geometry: Baseline rocket geometry (``fin_span_m`` is overridden).
        fin_span_m: Candidate exposed fin span [m].
        mach: Freestream Mach number to evaluate at.

    Returns:
        A populated :class:`SweepRow`.
    """
    g = replace(geometry, fin_span_m=fin_span_m)
    extended = compute_extended_stability_at_mach(g, mach)
    basic = extended.basic

    nose_component = next(c for c in basic.components if c.name == "nose")
    fin_component = next(c for c in basic.components if c.name == "fins")

    sm_basic = static_margin_cal(basic.x_cp_m, geometry.cg_from_nose_m, g.d_ref_m)
    sm_extended = static_margin_cal(
        extended.x_cp_extended_m, geometry.cg_from_nose_m, g.d_ref_m
    )

    return SweepRow(
        fin_span_factor=fin_span_m / geometry.fin_span_m,
        fin_span_m=fin_span_m,
        cp_nose_m=nose_component.x_cp_m,
        cp_fin_m=fin_component.x_cp_m,
        cp_body_m=extended.body.x_cp_m,
        cp_total_m=extended.x_cp_extended_m,
        cg_m=geometry.cg_from_nose_m,
        sm_cal_basic=sm_basic,
        sm_cal_extended=sm_extended,
    )


def fin_span_sweep(
    geometry: RocketGeometry,
    mach: float = COMPARISON_MACH,
    factor_min: float = FIN_SPAN_SWEEP_FACTOR_MIN,
    factor_max: float = FIN_SPAN_SWEEP_FACTOR_MAX,
    n_points: int = FIN_SPAN_SWEEP_POINTS,
) -> list[SweepRow]:
    """Sweep ``fin_span_m`` from ``factor_min`` to ``factor_max`` of YAML.

    Args:
        geometry: Baseline rocket geometry (YAML ``fin_span_m`` used as
            the 1.0x anchor).
        mach: Freestream Mach number (default: Teltik comparison, Ma 2.5).
        factor_min: Lower sweep bound as a fraction of the YAML span.
        factor_max: Upper sweep bound as a fraction of the YAML span.
        n_points: Number of sweep points.

    Returns:
        List of :class:`SweepRow`, one per factor, in increasing order.
    """
    factors = np.linspace(factor_min, factor_max, n_points)
    return [
        evaluate_span(geometry, float(f) * geometry.fin_span_m, mach) for f in factors
    ]


def find_neutral_span_m(
    geometry: RocketGeometry, mach: float = COMPARISON_MACH
) -> tuple[float, str]:
    """Bisect for the fin span at which the static margin crosses zero.

    Tries the Galejs-**extended** static margin first (the physically
    more complete model). If ``SM_cal_extended`` has no positive-span
    root in the search bracket -- which is the case for this vehicle at
    Ma 2.5: the cylindrical-afterbody planform centroid sits aft of the
    CG on its own, so ``SM_cal_extended`` asymptotes to a positive value
    (~+2.5 cal) as ``fin_span_m -> 0`` rather than crossing zero -- this
    falls back to the **basic** (unmodified Barrowman) static margin,
    which does have a well-defined root and reproduces the ~0.139 m
    figure independently derived in
    ``docs/vehicle/stability_reconciliation.md`` Section 3.

    Args:
        geometry: Baseline rocket geometry.
        mach: Freestream Mach number.

    Returns:
        Tuple of (``neutral_span_m``, ``variant`` where variant is
        ``"extended"`` or ``"basic (extended has no positive-span
        root)"``).

    Raises:
        RuntimeError: If neither the extended nor the basic curve has a
            root in the search bracket (would indicate a modeling error).
    """

    def _sm_extended(span_m: float) -> float:
        g = replace(geometry, fin_span_m=span_m)
        ext = compute_extended_stability_at_mach(g, mach)
        return static_margin_cal(ext.x_cp_extended_m, geometry.cg_from_nose_m, g.d_ref_m)

    def _sm_basic(span_m: float) -> float:
        g = replace(geometry, fin_span_m=span_m)
        res = compute_stability_at_mach(g, mach)
        return static_margin_cal(res.x_cp_m, geometry.cg_from_nose_m, g.d_ref_m)

    span_hi = NEUTRAL_SPAN_SEARCH_MAX_FACTOR * geometry.fin_span_m

    root = _bisect_for_root(_sm_extended, NEUTRAL_SPAN_SEARCH_MIN_M, span_hi)
    if root is not None:
        return root, "extended"

    root = _bisect_for_root(_sm_basic, NEUTRAL_SPAN_SEARCH_MIN_M, span_hi)
    if root is not None:
        return root, "basic (extended has no positive-span root)"

    raise RuntimeError(
        "No neutral-stability fin span found for either the extended or "
        f"basic static margin in [{NEUTRAL_SPAN_SEARCH_MIN_M}, {span_hi}] m"
    )


def _bisect_for_root(
    func: Any, lo: float, hi: float
) -> float | None:
    """Grid-scan for a sign change then bisect to high precision.

    Args:
        func: Scalar function of a single float span [m].
        lo: Lower search bound [m].
        hi: Upper search bound [m].

    Returns:
        The root location, or ``None`` if no sign change was found on
        the search grid.
    """
    grid = np.linspace(lo, hi, NEUTRAL_SPAN_SEARCH_GRID_POINTS)
    values = np.array([func(float(x)) for x in grid])
    sign_changes = np.where(np.diff(np.sign(values)) != 0)[0]
    if len(sign_changes) == 0:
        return None

    idx = int(sign_changes[0])
    a, b = float(grid[idx]), float(grid[idx + 1])
    fa = func(a)
    for _ in range(NEUTRAL_SPAN_BISECTION_ITERATIONS):
        mid = 0.5 * (a + b)
        fm = func(mid)
        if fa * fm <= 0.0:
            b = mid
        else:
            a, fa = mid, fm
    return 0.5 * (a + b)


# --------------------------------------------------------------------------
# CSV / PNG output.
# --------------------------------------------------------------------------

CSV_COLUMNS = (
    "fin_span_factor",
    "fin_span_m",
    "CP_nose_m",
    "CP_fin_m",
    "CP_body_m",
    "CP_total_m",
    "CG_m",
    "SM_cal_basic",
    "SM_cal_extended",
    "SM_flag",
)


def write_sensitivity_csv(
    rows: list[SweepRow],
    header_comments: list[str],
    output_path: Path | str = CSV_PATH,
) -> Path:
    """Write the fin-span sensitivity sweep to CSV.

    Args:
        rows: Sweep rows, in the order to be written.
        header_comments: Lines to write above the header row, each
            prefixed with ``"# "`` if not already ``#``-prefixed.
        output_path: Destination CSV path.

    Returns:
        The path written.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as fh:
        for line in header_comments:
            fh.write(line if line.startswith("#") else f"# {line}")
            fh.write("\n")
        writer = csv.writer(fh)
        writer.writerow(CSV_COLUMNS)
        for row in rows:
            writer.writerow(
                [
                    f"{row.fin_span_factor:.6f}",
                    f"{row.fin_span_m:.6f}",
                    f"{row.cp_nose_m:.6f}",
                    f"{row.cp_fin_m:.6f}",
                    f"{row.cp_body_m:.6f}",
                    f"{row.cp_total_m:.6f}",
                    f"{row.cg_m:.6f}",
                    f"{row.sm_cal_basic:.6f}",
                    f"{row.sm_cal_extended:.6f}",
                    row.sm_flag,
                ]
            )
    return output_path


def plot_sm_sensitivity(
    rows: list[SweepRow], output_path: Path | str = PNG_PATH
) -> Path:
    """Plot SM_cal (basic and extended) vs. fin-span factor.

    Args:
        rows: Sweep rows (assumed sorted by ``fin_span_factor``).
        output_path: PNG output path.

    Returns:
        Path to the saved PNG (150 DPI).
    """
    factors = [r.fin_span_factor for r in rows]
    sm_basic = [r.sm_cal_basic for r in rows]
    sm_extended = [r.sm_cal_extended for r in rows]

    fig, ax = plt.subplots(figsize=(8.0, 5.5), dpi=150)
    ax.plot(factors, sm_basic, "o-", color="#1f77b4", lw=2.0, label="SM_cal (basic Barrowman)")
    ax.plot(
        factors,
        sm_extended,
        "s-",
        color="#2ca02c",
        lw=2.0,
        label="SM_cal (extended: Galejs body-lift + P-G/Ackeret fin)",
    )

    ax.axhline(0.0, color="black", lw=1.2, ls="-", label="SM = 0 (neutral)")
    ax.axhline(
        SM_MIN_SAFE_CAL, color="#ff7f0e", lw=1.2, ls="--", label=f"SM = +{SM_MIN_SAFE_CAL:.0f} (min safe)"
    )
    ax.axhline(
        TELTIK_CFD_SM_CAL,
        color="#d62728",
        lw=1.5,
        ls=":",
        label=f"SM = {TELTIK_CFD_SM_CAL:.2f} (Teltik CFD, Ma {COMPARISON_MACH})",
    )

    ax.set_xlabel("Fin span factor [-] (fraction of YAML fins.span_m = 0.6685 m)")
    ax.set_ylabel("Static margin [calibers]")
    ax.set_title(
        f"MELprop vehicle -- static margin vs. fin span (Barrowman, Ma {COMPARISON_MACH})"
    )
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


# --------------------------------------------------------------------------
# BaseAnalysis wrapper.
# --------------------------------------------------------------------------


class BarrowmanExtendedAnalysis(BaseAnalysis):
    """Galejs-extended Barrowman fin-span sensitivity analysis.

    Wraps :func:`fin_span_sweep`, :func:`find_neutral_span_m`, and the
    CSV/PNG writers behind the project's ``BaseAnalysis`` contract.

    Example:
        >>> analysis = BarrowmanExtendedAnalysis()
        >>> analysis.setup(vehicle)  # doctest: +SKIP
        >>> results = analysis.execute()
        >>> results["neutral_span_m"] < results["fin_span_yaml_m"]  # doctest: +SKIP
    """

    fidelity = FidelityLevel.LEVEL_0

    def __init__(self, name: str = "barrowman_extended") -> None:
        super().__init__(name)
        self._geometry: RocketGeometry | None = None

    def setup(
        self,
        vehicle: BaseVehicleConfig,
        operating_state: dict | None = None,
    ) -> None:
        """Bind the analysis to a validated vehicle configuration.

        Geometry is read from ``vehicle`` via the reused
        ``barrowman_stability.geometry_from_vehicle``

        Args:
            vehicle: Validated vehicle configuration providing the
                axisymmetric body, fin-set geometry, and CG.
            operating_state: Unused by this method -- the fin-span
                sensitivity sweep is evaluated at the fixed
                ``COMPARISON_MACH`` design point. Accepted for
                :class:`BaseAnalysis` contract compatibility.

        Raises:
            ValueError: If a field the method needs is missing from
                ``vehicle`` (see
                ``barrowman_stability.geometry_from_vehicle``).
        """
        self._geometry = geometry_from_vehicle(vehicle)
        self._is_setup = True

    def execute(self) -> AnalysisResults:
        """Run the sweep + neutral-span solve and write CSV/PNG artifacts.

        Returns:
            AnalysisResults with ``sm_basic_cal``, ``sm_extended_cal``,
            ``delta_sm_cal``, ``delta_vs_teltik_cal``, ``neutral_span_m``,
            and ``fin_span_yaml_m``.

        Raises:
            RuntimeError: If called before :meth:`setup`.
        """
        if not self._is_setup or self._geometry is None:
            raise RuntimeError("BarrowmanExtendedAnalysis.execute() called before setup()")

        output = run(geometry=self._geometry)

        results = AnalysisResults(
            name=self.name,
            fidelity=self.fidelity,
            data={
                "sm_basic_cal": output["sm_basic_cal"],
                "sm_extended_cal": output["sm_extended_cal"],
                "delta_sm_cal": output["delta_sm_cal"],
                "delta_vs_teltik_cal": output["delta_vs_teltik_cal"],
                "neutral_span_m": output["neutral_span_m"],
                "fin_span_yaml_m": output["fin_span_yaml_m"],
            },
            metadata={
                "neutral_span_variant": output["neutral_span_variant"],
                "review_needed": output["review_needed"],
                "csv_path": str(output["csv_path"]),
                "png_path": str(output["png_path"]),
                "mach": COMPARISON_MACH,
            },
        )
        if not self.validate_results(results):
            raise RuntimeError(
                "BarrowmanExtendedAnalysis results failed analytical cross-check"
            )
        return results

    def validate_results(self, results: AnalysisResults) -> bool:
        """Sanity-check the extended analysis against the basic one.

        Checks:

        1. ``neutral_span_m`` is finite, positive, and less than the
           YAML fin span (the correction should not make the vehicle
           *more* stable at small span than the design span).
        2. The Galejs body-lift correction moves the CP forward
           (destabilizing): ``sm_extended_cal <= sm_basic_cal``,
           consistent with the physical direction documented in
           :func:`galejs_body_cn_alpha_and_cp` (body-lift CN_alpha is
           centered well aft of the nose but, once blended into the
           weighted-average CP alongside the much-more-forward nose and
           transition terms, the net effect at this vehicle's geometry
           is a forward shift of the combined CP -- see the module test
           suite for the numeric direction actually produced).

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        if "neutral_span_m" not in results or "fin_span_yaml_m" not in results:
            return False
        neutral = results["neutral_span_m"]
        if not math.isfinite(neutral) or neutral <= 0.0:
            return False
        if neutral >= results["fin_span_yaml_m"]:
            return False
        if results["sm_extended_cal"] > results["sm_basic_cal"]:
            return False
        return True


def run(
    geometry: RocketGeometry | None = None,
    csv_path: Path | str = CSV_PATH,
    png_path: Path | str = PNG_PATH,
) -> dict[str, Any]:
    """Run the full sensitivity analysis and write the CSV + PNG artifacts.

    Args:
        geometry: Rocket geometry; loaded from the default YAML config
            via ``barrowman_stability.load_geometry`` if omitted.
        csv_path: Destination CSV path.
        png_path: Destination PNG path.

    Returns:
        Dict of summary scalars (also embedded as CSV header comments).
    """
    if geometry is None:
        geometry = load_geometry()

    rows = fin_span_sweep(geometry)

    yaml_row = evaluate_span(geometry, geometry.fin_span_m)
    sm_basic_cal = yaml_row.sm_cal_basic
    sm_extended_cal = yaml_row.sm_cal_extended
    delta_sm_cal = sm_extended_cal - sm_basic_cal
    delta_vs_teltik_cal = sm_extended_cal - TELTIK_CFD_SM_CAL
    review_needed = sm_extended_cal > SM_REVIEW_THRESHOLD_CAL

    neutral_span_m, neutral_variant = find_neutral_span_m(geometry)

    header_comments = [
        "# YAADO vehicle -- extended Barrowman fin-span sensitivity "
        f"(Ma={COMPARISON_MACH})",
        f"# YAML fin_span_m={geometry.fin_span_m:.4f} m -> "
        f"SM_basic={sm_basic_cal:.3f} cal, SM_extended={sm_extended_cal:.3f} cal, "
        f"delta_SM={delta_sm_cal:.3f} cal",
        f"# SM_extended vs Teltik CFD ({TELTIK_CFD_SM_CAL:.2f} cal): "
        f"delta={delta_vs_teltik_cal:.3f} cal (gap narrowed by the Galejs "
        "body-lift correction but not closed; see docs/vehicle/stability_reconciliation.md)",
        f"# neutral_span_m (SM_cal=0)={neutral_span_m:.4f} m [{neutral_variant}]",
    ]
    if review_needed:
        header_comments.append("# STABILITY_REVIEW_NEEDED")

    csv_out = write_sensitivity_csv(rows, header_comments, csv_path)
    png_out = plot_sm_sensitivity(rows, png_path)

    return {
        "rows": rows,
        "sm_basic_cal": sm_basic_cal,
        "sm_extended_cal": sm_extended_cal,
        "delta_sm_cal": delta_sm_cal,
        "delta_vs_teltik_cal": delta_vs_teltik_cal,
        "neutral_span_m": neutral_span_m,
        "neutral_span_variant": neutral_variant,
        "review_needed": review_needed,
        "fin_span_yaml_m": geometry.fin_span_m,
        "csv_path": csv_out,
        "png_path": png_out,
    }


if __name__ == "__main__":
    output = run()
    print(f"SM_basic_cal      = {output['sm_basic_cal']:.3f}")
    print(f"SM_extended_cal   = {output['sm_extended_cal']:.3f}")
    print(f"delta_SM_cal      = {output['delta_sm_cal']:.3f}")
    print(f"delta_vs_teltik   = {output['delta_vs_teltik_cal']:.3f}")
    print(
        f"neutral_span_m    = {output['neutral_span_m']:.4f} "
        f"({output['neutral_span_variant']})"
    )
    print(f"review_needed     = {output['review_needed']}")
    print(f"CSV written to    : {output['csv_path']}")
    print(f"PNG written to    : {output['png_path']}")
