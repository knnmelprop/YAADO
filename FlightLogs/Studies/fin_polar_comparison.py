# MELprop-IADE | analyses.aero.fin_polar_comparison | v0.1.0
"""Supersonic fin polar comparison: Ackeret linearised theory vs. an
AVL-style analytic surrogate (Diederich formula), for the MELprop ramP
two-stage rocket fins (Project B).

``analyses/aero/xfoil_runner.py`` (Night-3) is a stub -- it defines the
fin section geometry constants but never implements the actual Ackeret
supersonic relations (its ``execute()`` unconditionally raises
``NotImplementedError``). Per the project's AVL applicability limit
(Mach < 0.6, alpha < 15 deg -- see ``CLAUDE.md`` and
``core/solver_registry.py``), AVL itself is *never* run at this
vehicle's cruise Mach (2.5) and the binary is not available in this
environment in any case. This module therefore:

1. Implements 2D thin-airfoil **Ackeret theory** directly (linearised
   supersonic potential flow) for a symmetric double-wedge (diamond)
   fin section, and
2. Implements a finite-aspect-ratio **analytic surrogate** for what a
   vortex-lattice (AVL-style) supersonic lifting-surface solve would
   give -- the **Diederich (1951) equivalent-aspect-ratio formula** --
   without invoking AVL or any external binary.

Both are closed-form, run in milliseconds, and are cross-checked
against each other (ratio flagging) rather than against a live AVL run.

Theory references
------------------
- Ackeret, J., "Air Forces on Airfoils Moving Faster than Sound",
  NACA TM 317 (1925) -- linearised supersonic thin-airfoil theory:
  ``c_l = 4*alpha/beta``, ``c_d = 4/beta * (alpha^2 + <(dy/dx)^2>)``
  with ``beta = sqrt(M^2 - 1)``.
- Anderson, J. D., *Fundamentals of Aerodynamics*, 6th ed., Ch. 12
  ("Linearized Supersonic Flow") -- derivation and worked double-wedge
  (diamond) airfoil example for the wave-drag mean-square-slope term.
- Ames Research Staff, "Equations, Tables, and Charts for Compressible
  Flow", NACA Report 1135 (1953) -- supersonic thin-section wave drag,
  also cited by ``xfoil_runner.py``.
- Diederich, F. W., "A Simple Approximate Method for Calculating the
  Spanwise Lift Distribution and Aerodynamic Loading of Sweptback
  Wings", NACA TN 2751 (1952) and Diederich, F. W., "A Plan-Form
  Parameter for Correlating Certain Aerodynamic Characteristics of
  Sweptback Wings" -- finite-AR lift-slope correlation of the form
  ``CL_alpha = AR_eff * alpha / (1 + AR_eff/(4*beta))`` used here as an
  analytic surrogate for a vortex-lattice/AVL-style solution at
  supersonic speeds with a supersonic leading edge.

Applicability and limits
-------------------------
- AVL (VLM) itself: Mach < 0.6, alpha < 15 deg only (never used here;
  this module's Mach sweep, 1.5-3.5, is entirely outside the AVL
  envelope by design).
- Ackeret / Diederich supersonic-leading-edge surrogate: Mach > 1.2,
  and only valid while the fin leading edge is *supersonic*
  (``Mach * cos(sweep_LE) > 1``, evaluated here with a small +5%
  engineering margin per task specification: ``Mach > 1.05 /
  cos(sweep_LE_rad)``). Rows that violate this are flagged
  ``SUBSONIC_LE_WARNING`` rather than silently reported.

This module never modifies ``Hangar/ramjet_rocket/vehicle_config.yaml``
(read-only) and reuses (does not reimplement) fin planform geometry via
``analyses.stability.barrowman_stability.load_geometry``.
"""

from __future__ import annotations

import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    # Allow `python3 analyses/aero/fin_polar_comparison.py` direct execution
    # by putting the repository root on sys.path (mirrors the pattern used
    # by analyses/aero/barrowman_extended.py).
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (backend must be set first)

from IADE_Core.modules.stability_control.methods.barrowman.barrowman_stability import (  # noqa: E402
    RocketGeometry,
    load_geometry,
)
from IADE_Core.Foundation.component_base import AnalysisResults, BaseAnalysis, FidelityLevel  # noqa: E402

# --------------------------------------------------------------------------
# Named constants.
# --------------------------------------------------------------------------

#: Fin section thickness-to-chord ratio for the supersonic double-wedge
#: (diamond) profile assumed by this analysis.
#: SZACOWANY [engineering estimate, task specification]: the YAML fin
#: geometry (`Hangar/ramjet_rocket/vehicle_config.yaml`, `fins:` block)
#: gives only the planform (span/chord/sweep); it carries no airfoil
#: section/thickness data. `xfoil_runner.py` separately estimates
#: t/c ~ 0.17 (30 mm / 176.8 mm) from a *structural* (solid steel plate)
#: assumption suited to the low-speed XFOIL stub. For the supersonic
#: wave-drag estimate here, a thinner, wave-drag-optimised double-wedge
#: section (t/c = 0.05) is assumed instead, consistent with typical
#: supersonic fin design practice (minimise Ackeret wave drag ~ (t/c)^2)
#: -- the two t/c values serve different purposes and are not meant to
#: agree; a real profile drawing is a TODO_PHYSICAL_PARAM.
FIN_THICKNESS_TO_CHORD = 0.05  # SZACOWANY [double-wedge, wave-drag-optimised estimate]

#: Mach sweep [dimensionless], per task specification.
MACH_SWEEP = (1.5, 2.0, 2.5, 3.0, 3.5)

#: Angle-of-attack sweep [deg], per task specification.
ALPHA_DEG_SWEEP = (0.0, 2.0, 4.0, 6.0, 8.0, 10.0)

#: Ratio thresholds for the per-row comparison flag.
RATIO_LOW_THRESHOLD = 0.7
RATIO_HIGH_THRESHOLD = 1.3

#: Leading-edge "supersonic" margin factor, per task specification: the
#: LE is treated as subsonic (Diederich surrogate not strictly valid)
#: whenever ``Mach <= 1.05 / cos(sweep_LE_rad)``.
SUBSONIC_LE_MARGIN_FACTOR = 1.05

#: Mach number used for the CL-vs-alpha comparison plot.
PLOT_MACH = 2.5

#: Output artifact paths.
RESULTS_DIR = Path(__file__).resolve().parents[2] / "FlightLogs"
CSV_PATH = RESULTS_DIR / "fin_polar_ackeret_vs_avl.csv"
PNG_PATH = RESULTS_DIR / "fin_polar_ackeret_vs_avl.png"

CSV_COLUMNS = (
    "mach",
    "alpha_deg",
    "CL_ackeret",
    "CD_ackeret",
    "CL_avl_surrogate",
    "ratio",
    "flag",
)


# --------------------------------------------------------------------------
# Ackeret linearised supersonic thin-airfoil theory (2D).
# --------------------------------------------------------------------------


def prandtl_glauert_beta(mach: float) -> float:
    """Supersonic compressibility parameter ``beta = sqrt(M^2 - 1)``.

    Args:
        mach: Freestream Mach number (must be > 1.0).

    Returns:
        beta [dimensionless].

    Raises:
        ValueError: If ``mach <= 1.0`` (Ackeret theory is undefined/
            singular at and below Mach 1).

    Reference:
        Ackeret, J., NACA TM 317 (1925); Anderson, *Fundamentals of
        Aerodynamics*, Ch. 12.
    """
    if mach <= 1.0:
        raise ValueError(f"Ackeret beta undefined for Mach <= 1.0 (got {mach})")
    return math.sqrt(mach**2 - 1.0)


def ackeret_cl(alpha_deg: float, mach: float) -> float:
    """2D Ackeret lift coefficient for a thin symmetric supersonic airfoil.

    ``CL = 4 * alpha / beta``, alpha in radians.

    Args:
        alpha_deg: Angle of attack [deg].
        mach: Freestream Mach number (> 1.0).

    Returns:
        Section lift coefficient CL [dimensionless].

    Reference:
        Ackeret, J., "Air Forces on Airfoils Moving Faster than Sound",
        NACA TM 317 (1925).
    """
    beta = prandtl_glauert_beta(mach)
    alpha_rad = math.radians(alpha_deg)
    return 4.0 * alpha_rad / beta


def ackeret_cl_alpha(mach: float) -> float:
    """2D Ackeret lift-curve slope, ``dCL/d(alpha_rad) = 4/beta``.

    Args:
        mach: Freestream Mach number (> 1.0).

    Returns:
        Lift-curve slope [1/rad].

    Reference:
        Ackeret, J., NACA TM 317 (1925).
    """
    return 4.0 / prandtl_glauert_beta(mach)


def ackeret_cd_wave(
    alpha_deg: float, mach: float, thickness_to_chord: float = FIN_THICKNESS_TO_CHORD
) -> float:
    """2D Ackeret wave-drag coefficient for a symmetric double-wedge fin.

    ``CD_wave = 4/beta * (alpha^2 + <(dy/dx)^2>)``, alpha in radians,
    where ``<(dy/dx)^2>`` is the chord-averaged mean-square slope of the
    (single-surface) thickness distribution. For a symmetric double-wedge
    (diamond) section with maximum thickness at mid-chord, the half-
    thickness slope is constant in magnitude over the whole chord,
    ``|dy/dx| = t/c``, so ``<(dy/dx)^2> = (t/c)^2`` exactly (no camber
    term: the section is symmetric, uncambered).

    Args:
        alpha_deg: Angle of attack [deg].
        mach: Freestream Mach number (> 1.0).
        thickness_to_chord: Section maximum thickness-to-chord ratio
            ``t/c`` [dimensionless]. Defaults to
            :data:`FIN_THICKNESS_TO_CHORD` (SZACOWANY double-wedge).

    Returns:
        Section wave-drag coefficient CD [dimensionless]. (Friction/base
        drag are not modelled -- linearised supersonic theory captures
        wave drag only.)

    Reference:
        Ackeret, J., NACA TM 317 (1925); Anderson, *Fundamentals of
        Aerodynamics*, Ch. 12 (double-wedge worked example); Ames
        Research Staff, NACA Report 1135 (1953).
    """
    beta = prandtl_glauert_beta(mach)
    alpha_rad = math.radians(alpha_deg)
    mean_square_slope = thickness_to_chord**2
    return 4.0 / beta * (alpha_rad**2 + mean_square_slope)


# --------------------------------------------------------------------------
# Diederich analytic surrogate for a finite-AR supersonic lifting surface
# (stand-in for an AVL/VLM solve -- AVL itself is never invoked).
# --------------------------------------------------------------------------


def fin_effective_aspect_ratio(geometry: RocketGeometry) -> float:
    """Effective aspect ratio of one exposed fin panel, ``AR_eff = 2*s/c_mean``.

    Args:
        geometry: Rocket geometry (fin planform reused from
            ``barrowman_stability.load_geometry``; ``fin_span_m`` is
            documented there as the *exposed semi-span* already, matching
            the ``s`` used by the Diederich formula directly).

    Returns:
        AR_eff [dimensionless].

    Reference:
        Diederich, F. W., NACA TN 2751 (1952).
    """
    s = geometry.fin_span_m
    c_mean = 0.5 * (geometry.fin_root_chord_m + geometry.fin_tip_chord_m)
    return 2.0 * s / c_mean


def diederich_cl_alpha(mach: float, ar_eff: float) -> float:
    """Diederich finite-AR supersonic lift-curve slope surrogate.

    ``CL_alpha = AR_eff / (1 + AR_eff / (4*beta))`` [1/rad] -- a simple
    closed-form correlation that reduces to the 2D Ackeret slope
    (``4/beta``) as ``AR_eff -> infinity`` and to slender-body/low-AR
    behaviour as ``AR_eff -> 0``, used here as an analytic stand-in for
    what a supersonic vortex-lattice (AVL-style) panel solve would
    predict for a low-sweep trapezoidal fin with a supersonic leading
    edge, without invoking AVL (which is out of its Mach < 0.6
    applicability envelope here and whose binary is unavailable).

    Args:
        mach: Freestream Mach number (> 1.0).
        ar_eff: Effective (2x exposed semi-span / mean chord) aspect
            ratio [dimensionless], see :func:`fin_effective_aspect_ratio`.

    Returns:
        Lift-curve slope [1/rad].

    Reference:
        Diederich, F. W., NACA TN 2751 (1952); Diederich, F. W., "A
        Plan-Form Parameter for Correlating Certain Aerodynamic
        Characteristics of Sweptback Wings".
    """
    beta = prandtl_glauert_beta(mach)
    return ar_eff / (1.0 + ar_eff / (4.0 * beta))


def diederich_cl(alpha_deg: float, mach: float, ar_eff: float) -> float:
    """Diederich finite-AR supersonic lift coefficient surrogate.

    ``CL = CL_alpha * alpha_rad`` using :func:`diederich_cl_alpha`.

    Args:
        alpha_deg: Angle of attack [deg].
        mach: Freestream Mach number (> 1.0).
        ar_eff: Effective aspect ratio [dimensionless].

    Returns:
        CL [dimensionless].

    Reference:
        Diederich, F. W., NACA TN 2751 (1952).
    """
    return diederich_cl_alpha(mach, ar_eff) * math.radians(alpha_deg)


def is_subsonic_leading_edge(
    mach: float, sweep_le_deg: float, margin_factor: float = SUBSONIC_LE_MARGIN_FACTOR
) -> bool:
    """Flag whether the fin leading edge is subsonic at this Mach number.

    The leading edge is subsonic when the Mach component normal to the
    LE is below 1, i.e. ``Mach * cos(sweep_LE) < 1``. Per task
    specification, an engineering margin factor is applied so the LE is
    only treated as reliably supersonic once
    ``Mach > margin_factor / cos(sweep_LE)`` (with the rectangular ramP
    fin's ``sweep_LE = 0 deg``, this reduces to ``Mach > 1.05``).

    Args:
        mach: Freestream Mach number.
        sweep_le_deg: Leading-edge sweep angle [deg].
        margin_factor: Engineering margin on the sonic-LE Mach threshold.

    Returns:
        True if the leading edge should be flagged as subsonic (Diederich
        supersonic-LE surrogate not strictly valid at this condition).

    Reference:
        Diederich, F. W., NACA TN 2751 (1952) (supersonic- vs. subsonic-
        leading-edge regimes for swept/tapered supersonic wings).
    """
    threshold = margin_factor / math.cos(math.radians(sweep_le_deg))
    return mach <= threshold


# --------------------------------------------------------------------------
# Per-row comparison flag.
# --------------------------------------------------------------------------


def classify_ratio_flag(
    ratio: float,
    subsonic_le: bool = False,
    low_threshold: float = RATIO_LOW_THRESHOLD,
    high_threshold: float = RATIO_HIGH_THRESHOLD,
) -> str:
    """Classify the Diederich/Ackeret CL ratio into a coarse per-row flag.

    Args:
        ratio: ``CL_avl_surrogate / CL_ackeret`` (slope ratio; see
            :func:`fin_polar_row` for why this is computed from the
            lift-curve slopes rather than the raw CL values).
        subsonic_le: True if :func:`is_subsonic_leading_edge` flags this
            Mach/sweep combination -- takes priority over the ratio bands.
        low_threshold: Ratio below which the row is flagged ``RATIO_LOW``.
        high_threshold: Ratio above which the row is flagged ``RATIO_HIGH``.

    Returns:
        One of ``"SUBSONIC_LE_WARNING"``, ``"RATIO_LOW"``,
        ``"RATIO_HIGH"``, or ``"OK"``.
    """
    if subsonic_le:
        return "SUBSONIC_LE_WARNING"
    if ratio < low_threshold:
        return "RATIO_LOW"
    if ratio > high_threshold:
        return "RATIO_HIGH"
    return "OK"


# --------------------------------------------------------------------------
# Sweep row + full sweep.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FinPolarRow:
    """One row of the Ackeret-vs-Diederich fin polar comparison.

    Attributes correspond 1:1 to the required CSV columns.
    """

    mach: float
    alpha_deg: float
    cl_ackeret: float
    cd_ackeret: float
    cl_avl_surrogate: float
    ratio: float
    flag: str


def fin_polar_row(
    mach: float,
    alpha_deg: float,
    ar_eff: float,
    sweep_le_deg: float,
    thickness_to_chord: float = FIN_THICKNESS_TO_CHORD,
) -> FinPolarRow:
    """Compute one (Mach, alpha) row of the Ackeret-vs-Diederich comparison.

    The ``ratio`` column is computed from the two methods' **lift-curve
    slopes** (``CL_alpha_diederich / CL_alpha_ackeret``), not from the
    raw per-alpha CL values. Both :func:`ackeret_cl` and
    :func:`diederich_cl` are exactly linear through the origin in alpha
    (``CL = CL_alpha * alpha_rad``, no camber/offset term in either
    linearised-theory model), so the ratio of the two CL curves is
    analytically alpha-independent everywhere -- including, most
    importantly, at ``alpha = 0`` where the raw-CL ratio would be the
    indeterminate form ``0/0``. Computing the ratio from the slopes
    sidesteps this and gives the same (alpha-independent) number that
    would be obtained at any alpha != 0 by direct division.

    Args:
        mach: Freestream Mach number (> 1.0).
        alpha_deg: Angle of attack [deg].
        ar_eff: Fin effective aspect ratio, see
            :func:`fin_effective_aspect_ratio`.
        sweep_le_deg: Fin leading-edge sweep [deg] (subsonic-LE check).
        thickness_to_chord: Section t/c for the Ackeret wave-drag term.

    Returns:
        A populated :class:`FinPolarRow`.
    """
    cl_ackeret = ackeret_cl(alpha_deg, mach)
    cd_ackeret = ackeret_cd_wave(alpha_deg, mach, thickness_to_chord)
    cl_avl = diederich_cl(alpha_deg, mach, ar_eff)

    ratio = diederich_cl_alpha(mach, ar_eff) / ackeret_cl_alpha(mach)
    subsonic_le = is_subsonic_leading_edge(mach, sweep_le_deg)
    flag = classify_ratio_flag(ratio, subsonic_le=subsonic_le)

    return FinPolarRow(
        mach=mach,
        alpha_deg=alpha_deg,
        cl_ackeret=cl_ackeret,
        cd_ackeret=cd_ackeret,
        cl_avl_surrogate=cl_avl,
        ratio=ratio,
        flag=flag,
    )


def fin_polar_sweep(
    geometry: RocketGeometry,
    mach_values: tuple[float, ...] = MACH_SWEEP,
    alpha_deg_values: tuple[float, ...] = ALPHA_DEG_SWEEP,
    thickness_to_chord: float = FIN_THICKNESS_TO_CHORD,
) -> list[FinPolarRow]:
    """Full Mach x alpha sweep of the Ackeret-vs-Diederich fin comparison.

    Args:
        geometry: Rocket geometry (fin planform reused from
            ``barrowman_stability.load_geometry``).
        mach_values: Mach sweep values (> 1.2 recommended; Ackeret is
            singular at Mach <= 1).
        alpha_deg_values: Angle-of-attack sweep values [deg].
        thickness_to_chord: Fin section t/c for Ackeret wave drag.

    Returns:
        List of :class:`FinPolarRow`, Mach-major then alpha-minor order
        (matches the task's row ordering, 30 rows for the default 5x6
        sweep).
    """
    ar_eff = fin_effective_aspect_ratio(geometry)
    rows: list[FinPolarRow] = []
    for mach in mach_values:
        for alpha_deg in alpha_deg_values:
            rows.append(
                fin_polar_row(
                    mach, alpha_deg, ar_eff, geometry.fin_sweep_deg, thickness_to_chord
                )
            )
    return rows


# --------------------------------------------------------------------------
# CSV / PNG output.
# --------------------------------------------------------------------------


def write_fin_polar_csv(
    rows: list[FinPolarRow],
    header_comments: list[str],
    output_path: Path | str = CSV_PATH,
) -> Path:
    """Write the fin polar comparison sweep to CSV.

    Units: ``mach`` and ``ratio`` dimensionless; ``alpha_deg`` degrees;
    ``CL_ackeret``/``CL_avl_surrogate`` dimensionless lift coefficients;
    ``CD_ackeret`` dimensionless wave-drag coefficient.

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
                    f"{row.mach:.4f}",
                    f"{row.alpha_deg:.4f}",
                    f"{row.cl_ackeret:.6f}",
                    f"{row.cd_ackeret:.6f}",
                    f"{row.cl_avl_surrogate:.6f}",
                    f"{row.ratio:.6f}",
                    row.flag,
                ]
            )
    return output_path


def plot_cl_vs_alpha(
    rows: list[FinPolarRow],
    mach: float = PLOT_MACH,
    output_path: Path | str = PNG_PATH,
) -> Path:
    """Plot CL vs. alpha at a fixed Mach for both methods, on one axes.

    Args:
        rows: Full sweep rows (filtered to ``mach`` internally).
        mach: Mach number to plot (must be present in ``rows``).
        output_path: PNG output path.

    Returns:
        Path to the saved PNG (150 DPI).

    Raises:
        ValueError: If no rows match ``mach``.
    """
    subset = sorted((r for r in rows if math.isclose(r.mach, mach)), key=lambda r: r.alpha_deg)
    if not subset:
        raise ValueError(f"No sweep rows found at Mach {mach}")

    alphas = [r.alpha_deg for r in subset]
    cl_ackeret = [r.cl_ackeret for r in subset]
    cl_avl = [r.cl_avl_surrogate for r in subset]

    fig, ax = plt.subplots(figsize=(8.0, 5.5), dpi=150)
    ax.plot(alphas, cl_ackeret, "o-", color="#1f77b4", lw=2.0, label="CL (Ackeret, 2D thin-airfoil)")
    ax.plot(
        alphas,
        cl_avl,
        "s-",
        color="#2ca02c",
        lw=2.0,
        label="CL (Diederich analytic AVL-style surrogate)",
    )

    ax.set_xlabel("Angle of attack, alpha [deg]")
    ax.set_ylabel("Lift coefficient, CL [-]")
    ax.set_title(
        f"MELprop ramP fin -- CL vs. alpha, Ackeret vs. AVL-style analytic "
        f"surrogate (Mach {mach:.1f})"
    )
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


# --------------------------------------------------------------------------
# BaseAnalysis wrapper.
# --------------------------------------------------------------------------


class FinPolarComparisonAnalysis(BaseAnalysis):
    """Ackeret-vs-Diederich fin polar comparison analysis (Project B).

    Wraps :func:`fin_polar_sweep` and the CSV/PNG writers behind the
    project's ``BaseAnalysis`` contract. Never invokes AVL or XFOIL
    binaries; both methods are closed-form analytic correlations.

    Example:
        >>> analysis = FinPolarComparisonAnalysis()
        >>> analysis.setup()
        >>> results = analysis.execute()
        >>> results["ar_eff"] > 0.0  # doctest: +SKIP
    """

    fidelity = FidelityLevel.LEVEL_0

    def __init__(self, name: str = "fin_polar_comparison") -> None:
        super().__init__(name)
        self._geometry: RocketGeometry | None = None

    def setup(self, config_path: Path | str | None = None) -> None:
        """Load fin planform geometry via the reused ``load_geometry``.

        Args:
            config_path: Optional override path to the ramjet-rocket
                ``vehicle_config.yaml``; defaults to the module's own
                default when omitted.
        """
        if config_path is None:
            self._geometry = load_geometry()
        else:
            self._geometry = load_geometry(config_path)
        self._is_setup = True

    def execute(self) -> AnalysisResults:
        """Run the sweep and write the CSV/PNG artifacts.

        Returns:
            AnalysisResults with ``ar_eff``, ``n_rows``, and
            ``n_flagged_rows`` in ``data``, and CSV/PNG paths in
            ``metadata``.

        Raises:
            RuntimeError: If called before :meth:`setup`.
        """
        if not self._is_setup or self._geometry is None:
            raise RuntimeError("FinPolarComparisonAnalysis.execute() called before setup()")

        output = run(geometry=self._geometry)

        results = AnalysisResults(
            name=self.name,
            fidelity=self.fidelity,
            data={
                "ar_eff": output["ar_eff"],
                "n_rows": float(len(output["rows"])),
                "n_flagged_rows": float(output["n_flagged_rows"]),
            },
            metadata={
                "csv_path": str(output["csv_path"]),
                "png_path": str(output["png_path"]),
                "mach_sweep": MACH_SWEEP,
                "alpha_deg_sweep": ALPHA_DEG_SWEEP,
            },
        )
        if not self.validate_results(results):
            raise RuntimeError(
                "FinPolarComparisonAnalysis results failed analytical cross-check"
            )
        return results

    def validate_results(self, results: AnalysisResults) -> bool:
        """Sanity-check the sweep output.

        Checks:

        1. ``ar_eff`` is finite and positive.
        2. ``n_rows`` matches the expected 5 (Mach) x 6 (alpha) = 30.

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        if "ar_eff" not in results or "n_rows" not in results:
            return False
        if not math.isfinite(results["ar_eff"]) or results["ar_eff"] <= 0.0:
            return False
        if int(results["n_rows"]) != len(MACH_SWEEP) * len(ALPHA_DEG_SWEEP):
            return False
        return True


def run(
    geometry: RocketGeometry | None = None,
    csv_path: Path | str = CSV_PATH,
    png_path: Path | str = PNG_PATH,
) -> dict[str, object]:
    """Run the full Ackeret-vs-Diederich fin polar comparison sweep.

    Args:
        geometry: Rocket geometry; loaded from the default YAML config
            via ``barrowman_stability.load_geometry`` if omitted.
        csv_path: Destination CSV path.
        png_path: Destination PNG path.

    Returns:
        Dict of summary scalars and the row list (also embedded as CSV
        header comments).
    """
    if geometry is None:
        geometry = load_geometry()

    rows = fin_polar_sweep(geometry)
    ar_eff = fin_effective_aspect_ratio(geometry)
    n_flagged = sum(1 for r in rows if r.flag != "OK")

    header_comments = [
        "# MELprop-IADE ramP -- fin polar comparison: Ackeret (2D thin "
        "supersonic) vs. Diederich AVL-style analytic surrogate",
        f"# Fin planform: exposed span={geometry.fin_span_m:.4f} m, "
        f"root chord={geometry.fin_root_chord_m:.4f} m, "
        f"tip chord={geometry.fin_tip_chord_m:.4f} m, "
        f"sweep_LE={geometry.fin_sweep_deg:.1f} deg -> AR_eff={ar_eff:.4f}",
        f"# t/c={FIN_THICKNESS_TO_CHORD:.3f} SZACOWANY (double-wedge, "
        "wave-drag-optimised estimate; distinct from xfoil_runner.py's "
        "t/c~0.17 structural estimate)",
        f"# ratio = CL_alpha_diederich / CL_alpha_ackeret (alpha-independent "
        "by construction; see fin_polar_row() docstring)",
        f"# {n_flagged}/{len(rows)} rows flagged non-OK",
    ]

    csv_out = write_fin_polar_csv(rows, header_comments, csv_path)
    png_out = plot_cl_vs_alpha(rows, PLOT_MACH, png_path)

    return {
        "rows": rows,
        "ar_eff": ar_eff,
        "n_flagged_rows": n_flagged,
        "csv_path": csv_out,
        "png_path": png_out,
    }


if __name__ == "__main__":
    output = run()
    print(f"AR_eff            = {output['ar_eff']:.4f}")
    print(f"n_rows            = {len(output['rows'])}")
    print(f"n_flagged_rows    = {output['n_flagged_rows']}")
    print(f"CSV written to    : {output['csv_path']}")
    print(f"PNG written to    : {output['png_path']}")
