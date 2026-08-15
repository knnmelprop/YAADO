# MELprop-IADE | analyses.propulsion.inlet_actuation | v0.1.0
"""Cone half-angle vs Mach actuation schedule for the 4-cone spike inlet.

This module is the Mach-SCHEDULE layer on top of the movable-spike
multi-cone inlet model in :mod:`analyses.propulsion.inlet_performance`
(v0.2.0). It does NOT duplicate the shock chain, the recovery model, the
MIL-E-5007D standard, or the angle optimizer -- all of those are imported
directly from ``inlet_performance``:

* :func:`analyses.propulsion.inlet_performance.optimize_multi_cone_angles`
  -- Nelder-Mead search for the incremental cone deflections that maximize
  ``eta_inlet`` at a given freestream Mach.
* :func:`analyses.propulsion.inlet_performance.multi_cone_recovery_chain`
  -- n-oblique-shock + terminal-normal-shock + diffuser recovery model,
  used here for the Mach <= 1 (no attached-shock) fallback rows where the
  optimizer's precondition (``mach1 > 1``) does not hold.
* :func:`analyses.propulsion.inlet_performance.mil_e_5007_eta_std` -- the
  MIL-E-5007D total-pressure-recovery standard used as the per-Mach PASS/
  FAIL gate.

What THIS module adds: for the fixed 4-cone geometry (capture area and
spike base diameter from ``inlet_performance``'s Fusion Assembly v6
constants), sweep the optimizer across flight Mach and report:

1. The optimal cone half-angle schedule (cumulative, i.e. the physical
   half-angle of each of the 4 frusta measured from the axis, as opposed
   to the per-stage incremental deflection) vs Mach.
2. The achieved ``eta_inlet`` and the MIL-E-5007D ``eta_std`` at that
   Mach, with an honest PASS/FAIL flag -- physically, Ma <= 1 always
   FAILS (``eta_std`` saturates at 1.0, which no real diffuser chain can
   reach), and low supersonic Mach can fail too (shallow required cone
   angles give little pressure recovery margin). No physics is tuned to
   force a PASS.
3. The per-cone required actuation range ``Delta_theta = theta_max -
   theta_min`` across the supersonic part of the sweep -- i.e. how far
   each cone segment must physically rotate/translate to track the
   optimum across the Mach range.
4. The Mach band where ``eta_inlet >= eta_std(M)`` (the physically
   correct, Mach-dependent gate) and, separately for reference, the band
   where ``eta_inlet`` meets the fixed absolute design threshold used
   elsewhere in this repo (0.8703, MIL-E-5007D evaluated at M = 2.5).

References:
    Seddon, J. & Goldsmith, E. L., *Intake Aerodynamics*, 2nd ed.,
    Blackwell Science, 1999, Sec. 4.3 (multi-shock external-compression
    intakes, variable-geometry scheduling).
    Anderson, J. D., *Modern Compressible Flow: With Historical
    Perspective*, 3rd ed., McGraw-Hill, 2003, Ch. 4 (oblique shocks,
    theta-beta-M relation, shock detachment).
    MIL-E-5007D, *Military Specification: Engines, Aircraft, Turbojet
    and Turbofan* -- total-pressure-recovery standard.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    # Allow `python3 analyses/propulsion/inlet_actuation.py` direct
    # execution by putting the repository root on sys.path, mirroring
    # inlet_performance.py's own guard.
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from IADE_Core.modules.propulsion.inlet_performance import (
    CAPTURE_AREA_M2,
    DEFAULT_N_CONES_M25,
    ETA_DIFFUSER,
    SPIKE_BASE_DIAMETER_M,
    mil_e_5007_eta_std,
    multi_cone_recovery_chain,
    optimize_multi_cone_angles,
)
from IADE_Core.FlightDeck.component_base import AnalysisResults, BaseAnalysis, FidelityLevel

# --------------------------------------------------------------------------
# Sweep defaults
# --------------------------------------------------------------------------

#: Default lower bound of the Mach sweep (spec: 1.0 -> 3.5, step 0.1).
MACH_SWEEP_MIN: float = 1.0

#: Default upper bound of the Mach sweep.
MACH_SWEEP_MAX: float = 3.5

#: Default Mach step for the full production sweep (used only by main()).
MACH_SWEEP_STEP: float = 0.1

#: Fixed absolute total-pressure-recovery design threshold used elsewhere
#: in this repo (MIL-E-5007D evaluated at the M = 2.5 design point),
#: reported alongside the physically-correct per-Mach eta_std(M) gate.
ETA_ABSOLUTE_THRESHOLD: float = 0.8703


def _mach_sweep_values(
    mach_min: float, mach_max: float, mach_step: float
) -> list[float]:
    """Build an inclusive Mach sweep list, rounded to avoid float drift.

    Args:
        mach_min: Lower bound (inclusive).
        mach_max: Upper bound (inclusive, up to floating-point rounding).
        mach_step: Step size (> 0).

    Returns:
        List of Mach values from ``mach_min`` to ``mach_max`` in steps of
        ``mach_step``, each rounded to 6 decimal places.

    Raises:
        ValueError: If ``mach_step <= 0`` or ``mach_max < mach_min``.
    """
    if mach_step <= 0.0:
        raise ValueError(f"mach_step must be > 0, got {mach_step}")
    if mach_max < mach_min:
        raise ValueError(f"mach_max ({mach_max}) must be >= mach_min ({mach_min})")

    n_steps = round((mach_max - mach_min) / mach_step)
    return [round(mach_min + i * mach_step, 6) for i in range(n_steps + 1)]


def _schedule_row(
    mach: float,
    n_cones: int,
    eta_diffuser: float,
    eta_abs_threshold: float,
) -> dict[str, Any]:
    """Compute one Mach-sweep row: optimum cone angles + recovery + gates.

    For ``mach > 1.0`` this runs
    :func:`optimize_multi_cone_angles` (imported from
    ``inlet_performance``) to find the optimal incremental deflections,
    then converts them to cumulative (physical) cone half-angles. For
    ``mach <= 1.0`` the optimizer's precondition does not hold (no
    attached oblique-shock system is possible), so the row falls back to
    :func:`multi_cone_recovery_chain` with all-zero incremental angles,
    which correctly degenerates to the diffuser-only recovery
    ``eta_inlet = eta_diffuser`` (no shocks engage below Mach 1).

    Args:
        mach: Freestream Mach number (>= 0).
        n_cones: Number of cone segments.
        eta_diffuser: Assumed subsonic-diffuser total-pressure efficiency.
        eta_abs_threshold: Fixed absolute eta_inlet reference threshold.

    Returns:
        Dict with ``mach``, ``theta_increments_deg``,
        ``theta_half_angles_deg`` (cumulative, physical half-angle per
        cone), ``eta_inlet``, ``eta_std``, ``meets_mil_flag`` (PASS/FAIL
        against the Mach-dependent ``eta_std(M)``), ``meets_abs_threshold``
        (reference-only, against ``eta_abs_threshold``), and ``detached``.
    """
    if mach > 1.0:
        theta_increments_rad, eta_inlet = optimize_multi_cone_angles(
            mach, n_cones, eta_diffuser
        )
        chain = multi_cone_recovery_chain(mach, theta_increments_rad, eta_diffuser)
        detached = chain["detached"]
    else:
        theta_increments_rad = [0.0] * n_cones
        chain = multi_cone_recovery_chain(mach, theta_increments_rad, eta_diffuser)
        eta_inlet = chain["eta_inlet"]
        detached = chain["detached"]

    import math

    theta_increments_deg = [math.degrees(t) for t in theta_increments_rad]
    theta_half_angles_deg = [
        sum(theta_increments_deg[: i + 1]) for i in range(len(theta_increments_deg))
    ]

    eta_std = mil_e_5007_eta_std(mach)
    meets_mil_flag = eta_inlet >= eta_std
    meets_abs_threshold = eta_inlet >= eta_abs_threshold

    return {
        "mach": mach,
        "theta_increments_deg": theta_increments_deg,
        "theta_half_angles_deg": theta_half_angles_deg,
        "eta_inlet": eta_inlet,
        "eta_std": eta_std,
        "meets_mil_flag": meets_mil_flag,
        "meets_abs_threshold": meets_abs_threshold,
        "detached": detached,
    }


def build_actuation_schedule(
    mach_min: float = MACH_SWEEP_MIN,
    mach_max: float = MACH_SWEEP_MAX,
    mach_step: float = MACH_SWEEP_STEP,
    n_cones: int = DEFAULT_N_CONES_M25,
    eta_diffuser: float = ETA_DIFFUSER,
    eta_abs_threshold: float = ETA_ABSOLUTE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Sweep the optimal cone-angle schedule across freestream Mach.

    Args:
        mach_min: Lower bound of the Mach sweep (inclusive).
        mach_max: Upper bound of the Mach sweep (inclusive).
        mach_step: Mach step size (> 0).
        n_cones: Number of cone segments (>= 1).
        eta_diffuser: Assumed subsonic-diffuser total-pressure efficiency.
        eta_abs_threshold: Fixed absolute eta_inlet reference threshold.

    Returns:
        List of per-Mach schedule rows (see :func:`_schedule_row`), sorted
        by ascending Mach.

    Raises:
        ValueError: If ``n_cones < 1``, ``eta_diffuser`` outside (0, 1],
            ``mach_step <= 0``, or ``mach_max < mach_min``.
    """
    if n_cones < 1:
        raise ValueError(f"n_cones must be >= 1, got {n_cones}")
    if not (0.0 < eta_diffuser <= 1.0):
        raise ValueError(f"eta_diffuser must be in (0, 1], got {eta_diffuser}")

    mach_values = _mach_sweep_values(mach_min, mach_max, mach_step)
    return [
        _schedule_row(mach, n_cones, eta_diffuser, eta_abs_threshold)
        for mach in mach_values
    ]


def actuation_range_per_cone_deg(
    schedule: list[dict[str, Any]], supersonic_only: bool = True
) -> list[float]:
    """Required actuation range Delta_theta = theta_max - theta_min per cone.

    Args:
        schedule: Rows produced by :func:`build_actuation_schedule`.
        supersonic_only: If True (default), exclude Mach <= 1.0 rows --
            those carry degenerate zero angles (no attached-shock system
            exists there) that would otherwise inflate the reported range
            with a non-physical actuation requirement.

    Returns:
        List of length ``n_cones`` with ``theta_max_deg - theta_min_deg``
        for each cone index across the (filtered) sweep.

    Raises:
        ValueError: If ``schedule`` is empty after filtering.
    """
    rows = [r for r in schedule if (not supersonic_only) or r["mach"] > 1.0]
    if not rows:
        raise ValueError("No schedule rows available to compute actuation range")

    n_cones = len(rows[0]["theta_half_angles_deg"])
    ranges: list[float] = []
    for cone_idx in range(n_cones):
        angles = [r["theta_half_angles_deg"][cone_idx] for r in rows]
        ranges.append(max(angles) - min(angles))
    return ranges


def mach_band_meeting_mil(schedule: list[dict[str, Any]]) -> tuple[float, float] | None:
    """Contiguous-by-sweep Mach band where eta_inlet >= eta_std(M).

    Args:
        schedule: Rows produced by :func:`build_actuation_schedule`, in
            ascending-Mach order.

    Returns:
        ``(mach_low, mach_high)`` spanning the rows flagged
        ``meets_mil_flag`` True, or ``None`` if no row passes.
    """
    passing_mach = [r["mach"] for r in schedule if r["meets_mil_flag"]]
    if not passing_mach:
        return None
    return min(passing_mach), max(passing_mach)


class ConeActuationScheduleAnalysis(BaseAnalysis):
    """Mach-schedule of optimal cone half-angles for the 4-cone spike inlet.

    Wraps :func:`build_actuation_schedule` as a :class:`BaseAnalysis`.
    Built entirely on the closed-form shock relations and Nelder-Mead
    angle optimizer of ``inlet_performance`` -> ``FidelityLevel.LEVEL_0``.

    Geometry (capture area, spike base diameter) is fixed and taken
    directly from ``inlet_performance``'s Fusion Assembly v6 constants
    (``CAPTURE_AREA_M2``, ``SPIKE_BASE_DIAMETER_M``); this analysis does
    not re-derive geometry from vehicle YAML.

    Example:
        >>> analysis = ConeActuationScheduleAnalysis()
        >>> analysis.setup(mach_min=1.0, mach_max=3.0, mach_step=1.0)
        >>> results = analysis.execute()
        >>> len(results.metadata["schedule"])  # doctest: +SKIP
    """

    fidelity = FidelityLevel.LEVEL_0

    def __init__(
        self,
        name: str = "cone_actuation_schedule",
        n_cones: int = DEFAULT_N_CONES_M25,
    ) -> None:
        super().__init__(name)
        self._n_cones = n_cones
        self._mach_min = MACH_SWEEP_MIN
        self._mach_max = MACH_SWEEP_MAX
        self._mach_step = MACH_SWEEP_STEP
        self._eta_diffuser = ETA_DIFFUSER
        self._eta_abs_threshold = ETA_ABSOLUTE_THRESHOLD
        self._capture_area_m2 = CAPTURE_AREA_M2
        self._base_diameter_m = SPIKE_BASE_DIAMETER_M

    def setup(
        self,
        mach_min: float = MACH_SWEEP_MIN,
        mach_max: float = MACH_SWEEP_MAX,
        mach_step: float = MACH_SWEEP_STEP,
        n_cones: int = DEFAULT_N_CONES_M25,
        eta_diffuser: float = ETA_DIFFUSER,
        eta_abs_threshold: float = ETA_ABSOLUTE_THRESHOLD,
    ) -> None:
        """Bind the analysis to a Mach sweep range and cone count.

        Args:
            mach_min: Lower bound of the Mach sweep (inclusive, >= 0).
            mach_max: Upper bound of the Mach sweep (inclusive, >= mach_min).
            mach_step: Mach step size (> 0). Use a coarse step (e.g. 0.5)
                for fast test runs; the full production sweep (0.1) is
                run only by :func:`main`.
            n_cones: Number of cone segments (>= 1).
            eta_diffuser: Assumed subsonic-diffuser total-pressure
                efficiency (0, 1].
            eta_abs_threshold: Fixed absolute eta_inlet reference
                threshold reported alongside the Mach-dependent gate.

        Raises:
            ValueError: If ``mach_min < 0``, ``mach_max < mach_min``,
                ``mach_step <= 0``, ``n_cones < 1``, or ``eta_diffuser``
                outside (0, 1].
        """
        if mach_min < 0.0:
            raise ValueError(f"mach_min must be >= 0, got {mach_min}")
        if mach_max < mach_min:
            raise ValueError(f"mach_max ({mach_max}) must be >= mach_min ({mach_min})")
        if mach_step <= 0.0:
            raise ValueError(f"mach_step must be > 0, got {mach_step}")
        if n_cones < 1:
            raise ValueError(f"n_cones must be >= 1, got {n_cones}")
        if not (0.0 < eta_diffuser <= 1.0):
            raise ValueError(f"eta_diffuser must be in (0, 1], got {eta_diffuser}")

        self._mach_min = mach_min
        self._mach_max = mach_max
        self._mach_step = mach_step
        self._n_cones = n_cones
        self._eta_diffuser = eta_diffuser
        self._eta_abs_threshold = eta_abs_threshold
        self._is_setup = True

    def execute(self) -> AnalysisResults:
        """Run the Mach sweep and summarize the actuation schedule.

        Returns:
            AnalysisResults with the per-cone actuation range and MIL
            passing band in ``data``, and the full per-Mach schedule
            (list of row dicts) in ``metadata["schedule"]``.

        Raises:
            RuntimeError: If called before :meth:`setup`.
        """
        if not self._is_setup:
            raise RuntimeError(
                "ConeActuationScheduleAnalysis.execute() called before setup()"
            )

        schedule = build_actuation_schedule(
            mach_min=self._mach_min,
            mach_max=self._mach_max,
            mach_step=self._mach_step,
            n_cones=self._n_cones,
            eta_diffuser=self._eta_diffuser,
            eta_abs_threshold=self._eta_abs_threshold,
        )
        delta_theta_deg = actuation_range_per_cone_deg(schedule, supersonic_only=True)
        mil_band = mach_band_meeting_mil(schedule)

        data: dict[str, Any] = {
            "n_cones": self._n_cones,
            "mach_min": self._mach_min,
            "mach_max": self._mach_max,
            "mach_step": self._mach_step,
            "capture_area_m2": self._capture_area_m2,
            "base_diameter_m": self._base_diameter_m,
            "eta_diffuser": self._eta_diffuser,
            "eta_abs_threshold": self._eta_abs_threshold,
            "delta_theta_deg": delta_theta_deg,
            "mil_band_mach_low": mil_band[0] if mil_band is not None else None,
            "mil_band_mach_high": mil_band[1] if mil_band is not None else None,
        }
        metadata: dict[str, Any] = {
            "schedule": schedule,
            "n_rows": len(schedule),
            "n_passing_mil": sum(1 for r in schedule if r["meets_mil_flag"]),
            "n_passing_abs_threshold": sum(
                1 for r in schedule if r["meets_abs_threshold"]
            ),
            "geometry_source": (
                "CAPTURE_AREA_M2 / SPIKE_BASE_DIAMETER_M constants from "
                "IADE_Core.modules.propulsion.inlet_performance (Fusion Assembly v6: "
                "cone length 0.293 m / base diameter 0.150 m, capture area "
                "0.04909 m^2) -- not re-read from vehicle YAML here."
            ),
            "assumptions": [
                "Mach <= 1.0 rows use zero incremental cone angles (no "
                "attached oblique-shock system exists below Mach 1); "
                "eta_inlet there equals eta_diffuser and MIL-E-5007D's "
                "eta_std saturates at 1.0, so those rows always FAIL -- "
                "this is physically correct, not a bug.",
                "meets_mil_flag compares eta_inlet against the "
                "Mach-dependent mil_e_5007_eta_std(M), the physically "
                "correct gate. meets_abs_threshold is a fixed-threshold "
                "reference (0.8703, the M=2.5 design-point value used "
                "elsewhere in this repo) and is NOT the primary gate.",
                "Per-cone actuation range (Delta_theta) is computed over "
                "the supersonic (Mach > 1) rows only, excluding the "
                "degenerate Mach <= 1 zero-angle rows.",
            ],
        }
        return AnalysisResults(
            name=self.name, fidelity=self.fidelity, data=data, metadata=metadata
        )


def _write_schedule_csv(schedule: list[dict[str, Any]], csv_path: Path) -> None:
    """Write the actuation schedule to CSV.

    Args:
        schedule: Rows produced by :func:`build_actuation_schedule`.
        csv_path: Destination CSV path.
    """
    n_cones = len(schedule[0]["theta_half_angles_deg"]) if schedule else 0
    theta_cols = [f"theta{i + 1}_deg" for i in range(n_cones)]
    fieldnames = ["mach", *theta_cols, "eta_inlet", "eta_std", "meets_mil_flag"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in schedule:
            csv_row = {"mach": row["mach"]}
            for i, col in enumerate(theta_cols):
                csv_row[col] = row["theta_half_angles_deg"][i]
            csv_row["eta_inlet"] = row["eta_inlet"]
            csv_row["eta_std"] = row["eta_std"]
            csv_row["meets_mil_flag"] = row["meets_mil_flag"]
            writer.writerow(csv_row)


def _plot_eta_vs_mach(schedule: list[dict[str, Any]], png_path: Path) -> None:
    """Plot achieved eta_inlet and the MIL-E-5007D standard vs Mach.

    Args:
        schedule: Rows produced by :func:`build_actuation_schedule`.
        png_path: Destination PNG path.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mach = [r["mach"] for r in schedule]
    eta_inlet = [r["eta_inlet"] for r in schedule]
    eta_std = [r["eta_std"] for r in schedule]

    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    ax.plot(
        mach,
        eta_inlet,
        color="#1f77b4",
        linewidth=2.0,
        marker="o",
        markersize=3.0,
        label="4-cone spike, optimal angle schedule",
    )
    ax.plot(
        mach,
        eta_std,
        color="#d62728",
        linewidth=2.0,
        linestyle="--",
        label="MIL-E-5007D standard, eta_std(M)",
    )
    ax.axhline(
        ETA_ABSOLUTE_THRESHOLD,
        color="gray",
        linewidth=1.0,
        linestyle=":",
        label=f"Absolute reference threshold ({ETA_ABSOLUTE_THRESHOLD})",
    )
    ax.set_xlabel("Freestream Mach number [-]")
    ax.set_ylabel("Total pressure recovery, $\\eta_{inlet}$ [-]")
    ax.set_title("4-cone spike actuation schedule: eta_inlet vs Mach")
    ax.set_xlim(min(mach), max(mach))
    ax.set_ylim(0.0, 1.05)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(png_path, dpi=150)
    plt.close(fig)


def main() -> None:
    """Run the full-resolution Mach sweep and write the CSV + PNG outputs."""
    analysis = ConeActuationScheduleAnalysis()
    analysis.setup(
        mach_min=MACH_SWEEP_MIN,
        mach_max=MACH_SWEEP_MAX,
        mach_step=MACH_SWEEP_STEP,
        n_cones=DEFAULT_N_CONES_M25,
    )
    results = analysis.execute()
    schedule = results.metadata["schedule"]

    module_dir = Path(__file__).resolve().parent
    csv_path = module_dir / "inlet_actuation_schedule.csv"
    png_path = module_dir / "inlet_actuation_eta_vs_mach.png"

    _write_schedule_csv(schedule, csv_path)
    _plot_eta_vs_mach(schedule, png_path)

    print("=== 4-cone spike inlet actuation schedule (Mach 1.0 - 3.5, step 0.1) ===")
    print(f"n_cones: {results.data['n_cones']}")
    print(f"Capture area: {results.data['capture_area_m2']:.5f} m^2")
    print(f"Spike base diameter: {results.data['base_diameter_m']:.4f} m")
    print(f"Per-cone actuation range Delta_theta (supersonic rows only):")
    for i, delta in enumerate(results.data["delta_theta_deg"]):
        print(f"  cone {i + 1}: {delta:.3f} deg")
    mil_low = results.data["mil_band_mach_low"]
    mil_high = results.data["mil_band_mach_high"]
    if mil_low is None:
        print("Mach band meeting MIL-E-5007D eta_std(M): NONE (fails everywhere)")
    else:
        print(f"Mach band meeting MIL-E-5007D eta_std(M): [{mil_low}, {mil_high}]")
    print(
        f"Rows passing MIL gate: {results.metadata['n_passing_mil']} / "
        f"{results.metadata['n_rows']}"
    )
    print(
        f"Rows passing absolute threshold ({results.data['eta_abs_threshold']}): "
        f"{results.metadata['n_passing_abs_threshold']} / {results.metadata['n_rows']}"
    )
    for target_mach in (1.5, 2.5, 3.5):
        row = min(schedule, key=lambda r: abs(r["mach"] - target_mach))
        print(
            f"Ma {row['mach']:.2f}: eta_inlet={row['eta_inlet']:.4f}, "
            f"eta_std={row['eta_std']:.4f}, "
            f"{'PASS' if row['meets_mil_flag'] else 'FAIL'}"
        )
    print(f"\nCSV written to: {csv_path}")
    print(f"Plot written to: {png_path}")


if __name__ == "__main__":
    main()
