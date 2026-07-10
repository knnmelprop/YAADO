# MELprop-IADE | analyses.mission.operational_envelope | v0.1.0
"""RamP (Project B) ramjet operational envelope: net-thrust sustain boundary.

Sweeps a Mach x altitude grid and, at each grid point, evaluates whether
the stage-2 ramjet can sustain level cruise flight (``net_thrust_N =
Th2_N - drag_N > 0``). This is a *design-space* survey -- distinct from
:mod:`analyses.trajectory.booster_burnout` (single time-domain boost-phase
integration) and from :mod:`workflows.ramp_staged_mission` (single
quasi-steady cruise design point) -- answering "where in (Mach, altitude)
space can the ramjet even produce net positive thrust", not "what
trajectory does the vehicle actually fly".

Per-grid-point pipeline:
    1. Inlet total-pressure recovery ``eta_d`` from the MIL-E-5007D
       standard (:func:`analyses.propulsion.inlet_performance.mil_e_5007_eta_std`,
       ``eta_d = 1 - 0.075*(Ma-1)^1.35`` for Ma > 1). This is the SAME
       formula used as the pass/fail *standard* elsewhere in the repo
       (inlet_performance.py); here it doubles as the recovery MODEL
       fed into the cycle, which is a conservative-ish simplification
       relative to the project's actual multi-cone inlet design (whose
       optimized recovery sits slightly ABOVE the MIL-E-5007D standard
       by construction -- see inlet_performance.py's confirmed-result
       table). Using the standard itself keeps this sweep geometry-
       independent (no cone-count / angle choice baked into the
       envelope) and is flagged here rather than silently assumed.
    2. Real (Th2, both combustor AND nozzle total-pressure losses)
       thrust from the Grzywka station cycle,
       :class:`analyses.propulsion.combustor_nozzle_cycle.GrzywkaCombustorNozzleAnalysis`,
       with ``eta_inlet`` overridden to the ``eta_d`` from step 1 (so
       every grid point uses the SAME conservative inlet-recovery model,
       rather than the design-Mach-only 4-cone preset chain the cycle
       class falls back to by default).
    3. Drag from a flat-plate-style estimate ``D = CD0 * q * Aref`` with
       a placeholder ``CD0 = 0.35`` (SZACOWANY -- no CFD drag polar
       exists yet across this Mach/altitude grid; the single available
       CFD drag data point, Teltik 2024 CFD 2451.95 N at Mach 2.5 /
       6000 m ISA per ``docs/assumptions.md`` A15, is retained here only
       as a SANITY REFERENCE, not fitted to -- see
       :data:`TELTIK_CFD_DRAG_N_REF`).
    4. ``net_thrust_N = Th2_N - drag_N``; ``status`` = ``SUSTAINED`` if
       positive, else ``UNABLE_TO_SUSTAIN``.

Reference markers (plotted, not fitted to):
    * Night-3 nominal cruise point (Mach 2.5 / 6000 m ISA) -- the
      condition used to wire :mod:`workflows.ramp_staged_mission`'s
      cruise segment and as the Grzywka cycle's own internal Teltik-CFD
      cross-check condition (``combustor_nozzle_cycle.TELTIK_MACH`` /
      ``TELTIK_ALTITUDE_M``).
    * Recommended launch-angle stage-1 burnout point, read from
      ``analyses/trajectory/burnout_state.json`` if present (produced by
      :mod:`analyses.trajectory.booster_burnout`).

References:
    MIL-E-5007D, *Military Specification: Engines, Aircraft, Turbojet and
    Turbofan* -- inlet total-pressure-recovery standard.
    U.S. Standard Atmosphere, 1976 (ISA troposphere model), valid to
    11 km -- this module's grid tops out at 10,000 m, within range.
    Grzywka, *Analiza numeryczna komory spalania i dyszy silnika
    strumieniowego*, Politechnika Warszawska, 2022 -- combustor/nozzle
    cycle (via :mod:`analyses.propulsion.combustor_nozzle_cycle`).
    ``docs/assumptions.md`` A15 -- Teltik 2024 CFD drag sanity reference.

Run as a script to sweep the grid, write the CSV, generate the PNG, and
print the Night-3 consistency check::

    python3 analyses/mission/operational_envelope.py
"""

from __future__ import annotations

import csv
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    # Allow `python3 analyses/mission/operational_envelope.py` direct
    # execution by putting the repository root on sys.path, mirroring the
    # convention used by analyses.propulsion.* and analyses.trajectory.*.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analyses.propulsion.combustor_nozzle_cycle import GrzywkaCombustorNozzleAnalysis
from analyses.propulsion.inlet_performance import mil_e_5007_eta_std
from src.schemas.vehicle_schema import BaseVehicleConfig, RocketConfig

# --------------------------------------------------------------------------
# ISA (1976) standard-atmosphere constants, standard troposphere layer.
# --------------------------------------------------------------------------

T0_ISA_K: float = 288.15
"""ISA sea-level standard temperature [K]."""

P0_ISA_PA: float = 101325.0
"""ISA sea-level standard pressure [Pa]."""

LAPSE_RATE_K_PER_M: float = 0.0065
"""ISA tropospheric lapse rate [K/m], valid 0-11 km."""

R_AIR_J_PER_KGK: float = 287.05
"""Specific gas constant of dry air [J/(kg*K)]."""

GAMMA_AIR: float = 1.4
"""Ratio of specific heats for air (calorically perfect gas)."""

TROPOPAUSE_ALTITUDE_M: float = 11000.0
"""Upper bound of ISA troposphere-layer validity [m]."""

ISA_PRESSURE_EXPONENT: float = 9.80665 / (LAPSE_RATE_K_PER_M * R_AIR_J_PER_KGK)
"""Barometric exponent ``g0 / (L * R)`` for ``p = p0 * (T / T0)**exponent``."""


def isa_atmosphere(altitude_m: float) -> tuple[float, float, float, float]:
    """Evaluate the ISA (1976) standard-troposphere atmospheric state.

    Standard-troposphere closed form (ICAO Doc 7488 / U.S. Standard
    Atmosphere 1976, ``0 <= h < 11000 m``):

        T = 288.15 - 0.0065*h
        p = 101325*(T/288.15)^5.2561
        rho = p/(287.05*T)
        a = sqrt(1.4*287.05*T)

    Args:
        altitude_m: Geometric altitude above sea level [m]. Must be in
            ``[0, 11000]`` (the standard-troposphere layer this module's
            grid stays within); values outside raise ``ValueError``.

    Returns:
        Tuple ``(rho_kg_m3, T_K, p_Pa, a_m_s)``: density, static
        temperature, static pressure and speed of sound in SI units.

    Raises:
        ValueError: If ``altitude_m`` is negative or above the
            tropopause (11,000 m), where this closed form is invalid.
    """
    if altitude_m < 0.0:
        raise ValueError(f"altitude_m must be >= 0, got {altitude_m}")
    if altitude_m > TROPOPAUSE_ALTITUDE_M:
        raise ValueError(
            f"altitude_m={altitude_m} exceeds the tropopause "
            f"({TROPOPAUSE_ALTITUDE_M} m); this module's ISA closed form "
            "is only valid in the standard troposphere layer"
        )

    t_K = T0_ISA_K - LAPSE_RATE_K_PER_M * altitude_m
    p_Pa = P0_ISA_PA * (t_K / T0_ISA_K) ** ISA_PRESSURE_EXPONENT
    rho_kg_m3 = p_Pa / (R_AIR_J_PER_KGK * t_K)
    a_m_s = math.sqrt(GAMMA_AIR * R_AIR_J_PER_KGK * t_K)
    return rho_kg_m3, t_K, p_Pa, a_m_s


# --------------------------------------------------------------------------
# Grid, drag model and reference-condition constants
# --------------------------------------------------------------------------

MACH_GRID: tuple[float, ...] = (1.5, 2.0, 2.5, 3.0, 3.5)
"""Freestream Mach numbers swept by the envelope."""

ALTITUDE_GRID_M: tuple[float, ...] = (0.0, 2000.0, 4000.0, 6000.0, 8000.0, 10000.0)
"""ISA altitudes [m] swept by the envelope."""

CD0_PLACEHOLDER: float = 0.35
"""Zero-lift drag coefficient placeholder [-] (# SZACOWANY -- no CFD drag
polar exists yet across this Mach/altitude grid; the single CFD drag data
point available, :data:`TELTIK_CFD_DRAG_N_REF`, is a sanity reference at
one condition only, not a fitted polar)."""

TELTIK_CFD_DRAG_N_REF: float = 2451.95
"""Teltik 2024 CFD drag [N] at Mach 2.5 / 6000 m ISA (``docs/assumptions.md``
A15). Retained as a SANITY REFERENCE for the flat-plate CD0 drag model at
that one condition; the CD0=0.35 placeholder is NOT tuned to reproduce it
(the two drag models -- CFD vs. constant-CD0 -- are expected to disagree;
see :func:`night3_reference_point` and the module-level test suite)."""

NIGHT3_MACH: float = 2.5
"""Night-3 nominal cruise Mach number (matches ``workflows.ramp_staged_mission``
cruise wiring's design Mach and the Grzywka cycle's internal Teltik-CFD
cross-check Mach)."""

NIGHT3_ALTITUDE_M: float = 6000.0
"""Night-3 nominal cruise altitude [m] ISA (matches
``analyses.propulsion.combustor_nozzle_cycle.TELTIK_ALTITUDE_M``)."""

VEHICLE_CONFIG_PATH: Path = (
    Path(__file__).resolve().parents[2] / "vehicles" / "ramjet_rocket" / "vehicle_config.yaml"
)
"""Path to the Project B rocket vehicle config (READ ONLY; never modified
by this module)."""

THIS_DIR: Path = Path(__file__).resolve().parent
RESULTS_DIR: Path = THIS_DIR / "results"
OUTPUT_CSV_PATH: Path = RESULTS_DIR / "operational_envelope.csv"
OUTPUT_PNG_PATH: Path = RESULTS_DIR / "operational_envelope.png"
BURNOUT_STATE_JSON_PATH: Path = (
    Path(__file__).resolve().parents[2] / "analyses" / "trajectory" / "burnout_state.json"
)

STATUS_SUSTAINED: str = "SUSTAINED"
STATUS_UNABLE: str = "UNABLE_TO_SUSTAIN"


def reference_area_m2(config_path: Path = VEHICLE_CONFIG_PATH) -> float:
    """Read the body diameter from the vehicle config and derive ``Aref``.

    ``Aref = pi * d^2 / 4`` using ``body.diameter_m`` (0.200 m as of
    2026-07-10, drawing-verified — see vehicle_config.yaml cfd_notes).
    The config is read-only here (never modified).

    Args:
        config_path: Path to ``vehicles/ramjet_rocket/vehicle_config.yaml``.

    Returns:
        Reference (body cross-section) area [m^2].

    Raises:
        ValueError: If the loaded config is not a Project B
            :class:`RocketConfig`.
    """
    config = BaseVehicleConfig.from_yaml(config_path)
    if not isinstance(config, RocketConfig):
        raise ValueError(f"{config_path} is not a Project B RocketConfig")
    d_m = config.body.diameter_m
    return math.pi * d_m**2 / 4.0


def compute_th2_thrust_N(mach: float, altitude_m: float, eta_d: float) -> float:
    """Evaluate the Grzywka real (Th2) thrust at one flight condition.

    Runs :class:`GrzywkaCombustorNozzleAnalysis` with ``eta_inlet``
    overridden to ``eta_d`` (the MIL-E-5007D recovery from this module's
    grid, NOT the class's default 4-cone-preset resolution), so every
    grid point shares the same inlet-recovery model.

    Args:
        mach: Freestream Mach number (> 1).
        altitude_m: ISA altitude [m].
        eta_d: Inlet total-pressure recovery to feed into the cycle [-].

    Returns:
        ``Th2_N`` -- real thrust (combustor AND nozzle total-pressure
        losses included), the conservative Grzywka Sec. 6.2.2 model.
    """
    analysis = GrzywkaCombustorNozzleAnalysis()
    analysis.setup(mach0=mach, altitude_m=altitude_m, eta_inlet=eta_d)
    results = analysis.execute()
    return float(results["Th2_N"])


def compute_drag_N(
    mach: float, altitude_m: float, cd0: float, aref_m2: float
) -> float:
    """Flat-plate-style drag estimate ``D = CD0 * q * Aref``.

    Args:
        mach: Freestream Mach number.
        altitude_m: ISA altitude [m].
        cd0: Zero-lift drag coefficient [-] (see :data:`CD0_PLACEHOLDER`).
        aref_m2: Reference area [m^2] (see :func:`reference_area_m2`).

    Returns:
        Drag force [N].
    """
    rho_kg_m3, _t_K, _p_Pa, a_m_s = isa_atmosphere(altitude_m)
    v_m_s = mach * a_m_s
    q_Pa = 0.5 * rho_kg_m3 * v_m_s**2
    return cd0 * q_Pa * aref_m2


@dataclass(frozen=True)
class EnvelopePoint:
    """One (Mach, altitude) grid point of the operational envelope.

    Attributes:
        mach: Freestream Mach number [-].
        altitude_m: ISA altitude [m].
        eta_d: Inlet total-pressure recovery (MIL-E-5007D standard) [-].
        Th2_N: Real (combustor + nozzle loss) Grzywka thrust [N].
        drag_N: Flat-plate CD0*q*Aref drag estimate [N].
        net_thrust_N: ``Th2_N - drag_N`` [N].
        status: ``"SUSTAINED"`` if ``net_thrust_N > 0``, else
            ``"UNABLE_TO_SUSTAIN"``.
    """

    mach: float
    altitude_m: float
    eta_d: float
    Th2_N: float
    drag_N: float
    net_thrust_N: float
    status: str


def evaluate_point(
    mach: float, altitude_m: float, cd0: float, aref_m2: float
) -> EnvelopePoint:
    """Evaluate the full envelope pipeline at one (Mach, altitude) point.

    Args:
        mach: Freestream Mach number (> 1).
        altitude_m: ISA altitude [m].
        cd0: Zero-lift drag coefficient [-].
        aref_m2: Reference area [m^2].

    Returns:
        The resolved :class:`EnvelopePoint`.
    """
    eta_d = mil_e_5007_eta_std(mach)
    th2_N = compute_th2_thrust_N(mach, altitude_m, eta_d)
    drag_N = compute_drag_N(mach, altitude_m, cd0, aref_m2)
    net_thrust_N = th2_N - drag_N
    status = STATUS_SUSTAINED if net_thrust_N > 0.0 else STATUS_UNABLE
    return EnvelopePoint(
        mach=mach,
        altitude_m=altitude_m,
        eta_d=eta_d,
        Th2_N=th2_N,
        drag_N=drag_N,
        net_thrust_N=net_thrust_N,
        status=status,
    )


def compute_envelope_grid(
    mach_values: tuple[float, ...] = MACH_GRID,
    altitude_values_m: tuple[float, ...] = ALTITUDE_GRID_M,
    cd0: float = CD0_PLACEHOLDER,
    aref_m2: float | None = None,
) -> list[EnvelopePoint]:
    """Sweep the Mach x altitude grid and evaluate every point.

    Args:
        mach_values: Freestream Mach numbers to sweep.
        altitude_values_m: ISA altitudes [m] to sweep.
        cd0: Zero-lift drag coefficient [-].
        aref_m2: Reference area [m^2]; resolved from the vehicle config
            via :func:`reference_area_m2` if ``None``.

    Returns:
        List of :class:`EnvelopePoint`, ordered Mach-major then altitude.
    """
    if aref_m2 is None:
        aref_m2 = reference_area_m2()
    return [
        evaluate_point(mach, altitude_m, cd0, aref_m2)
        for mach in mach_values
        for altitude_m in altitude_values_m
    ]


def night3_reference_point(
    mach: float = NIGHT3_MACH, altitude_m: float = NIGHT3_ALTITUDE_M
) -> dict[str, float]:
    """Recompute the Night-3 nominal cruise Th2 using the DEFAULT inlet model.

    Mirrors ``workflows.ramp_staged_mission._compute_ramjet_design_point``:
    :class:`GrzywkaCombustorNozzleAnalysis` is run WITHOUT the ``eta_d``
    override used elsewhere in this module, so ``eta_inlet`` resolves via
    the class's own default (the 4-cone multi-shock preset chain,
    :class:`analyses.propulsion.inlet_performance.MultiConeInletPerformanceAnalysis`)
    rather than the MIL-E-5007D standard formula this module's grid uses.

    This is deliberately a SEPARATE evaluation from the grid points (which
    all use the same MIL-E-5007D ``eta_d``): the two inlet-recovery models
    are close at Mach 2.5 (the multi-cone design was optimized specifically
    to clear the MIL-E-5007D standard there, per
    ``inlet_performance.py``'s confirmed-result table), so their Th2
    values are expected to agree closely -- quantified, not assumed, by
    the unit tests.

    Args:
        mach: Freestream Mach number (default 2.5, Night-3 nominal).
        altitude_m: ISA altitude [m] (default 6000 m, Night-3 nominal).

    Returns:
        Dict with ``mach``, ``altitude_m``, ``eta_inlet`` (multi-cone
        chain resolved value) and ``Th2_N``.
    """
    analysis = GrzywkaCombustorNozzleAnalysis()
    analysis.setup(mach0=mach, altitude_m=altitude_m)
    results = analysis.execute()
    return {
        "mach": mach,
        "altitude_m": altitude_m,
        "eta_inlet": float(results["eta_inlet"]),
        "Th2_N": float(results["Th2_N"]),
    }


def load_burnout_marker(
    burnout_json_path: Path = BURNOUT_STATE_JSON_PATH,
) -> dict[str, float] | None:
    """Load the recommended launch-angle stage-1 burnout (Mach, altitude).

    Args:
        burnout_json_path: Path to ``burnout_state.json`` produced by
            :mod:`analyses.trajectory.booster_burnout`.

    Returns:
        Dict with ``mach`` and ``altitude_m``, or ``None`` if the file is
        not present (booster trajectory not yet run).
    """
    if not burnout_json_path.exists():
        return None
    data = json.loads(burnout_json_path.read_text(encoding="utf-8"))
    return {
        "mach": float(data["burnout_mach"]),
        "altitude_m": float(data["burnout_altitude_m"]),
    }


def write_csv(points: list[EnvelopePoint], output_path: Path = OUTPUT_CSV_PATH) -> None:
    """Write the envelope grid to CSV with exactly 7 columns.

    Columns: ``mach, altitude_m, eta_d, Th2_N, drag_N, net_thrust_N,
    status``.

    Args:
        points: Envelope grid points (see :func:`compute_envelope_grid`).
        output_path: Destination CSV path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["mach", "altitude_m", "eta_d", "Th2_N", "drag_N", "net_thrust_N", "status"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for point in points:
            writer.writerow(asdict(point))


def plot_envelope(
    points: list[EnvelopePoint],
    output_path: Path = OUTPUT_PNG_PATH,
    night3_marker: dict[str, float] | None = None,
    burnout_marker: dict[str, float] | None = None,
) -> None:
    """Render the net-thrust contour/heatmap with the SUSTAINED boundary.

    Args:
        points: Envelope grid points.
        output_path: Destination PNG path.
        night3_marker: Night-3 nominal cruise reference point (``mach``,
            ``altitude_m``), plotted as a marker if given.
        burnout_marker: Stage-1 booster burnout reference point (``mach``,
            ``altitude_m``), plotted as a marker if given.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    machs = sorted({p.mach for p in points})
    alts = sorted({p.altitude_m for p in points})
    net_grid = np.zeros((len(alts), len(machs)))
    for point in points:
        i = alts.index(point.altitude_m)
        j = machs.index(point.mach)
        net_grid[i, j] = point.net_thrust_N

    fig, ax = plt.subplots(figsize=(8.0, 6.0))
    mesh = ax.contourf(machs, alts, net_grid, levels=20, cmap="RdYlGn")
    cbar = fig.colorbar(mesh, ax=ax)
    cbar.set_label("Net thrust, $Th2 - D$ [N]")

    # SUSTAINED / UNABLE_TO_SUSTAIN boundary (net_thrust_N == 0 contour).
    if net_grid.min() < 0.0 < net_grid.max():
        ax.contour(machs, alts, net_grid, levels=[0.0], colors="black", linewidths=2.0)

    if night3_marker is not None:
        ax.scatter(
            [night3_marker["mach"]],
            [night3_marker["altitude_m"]],
            marker="*",
            s=250,
            color="blue",
            edgecolors="black",
            zorder=5,
            label="Night-3 nominal cruise (Ma 2.5 / 6000 m)",
        )

    if burnout_marker is not None:
        ax.scatter(
            [burnout_marker["mach"]],
            [burnout_marker["altitude_m"]],
            marker="^",
            s=180,
            color="orange",
            edgecolors="black",
            zorder=5,
            label=(
                f"Stage-1 burnout (Ma {burnout_marker['mach']:.2f} / "
                f"{burnout_marker['altitude_m']:.0f} m)"
            ),
        )

    ax.set_xlabel("Freestream Mach number [-]")
    ax.set_ylabel("Altitude [m]")
    ax.set_title("MELprop-IADE | RamP ramjet operational envelope (net thrust)")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    """Sweep the envelope grid, write CSV + PNG, and print a summary."""
    aref_m2 = reference_area_m2()
    points = compute_envelope_grid(aref_m2=aref_m2)
    write_csv(points)

    night3 = night3_reference_point()
    burnout = load_burnout_marker()
    plot_envelope(
        points,
        night3_marker={"mach": NIGHT3_MACH, "altitude_m": NIGHT3_ALTITUDE_M},
        burnout_marker=burnout,
    )

    n_sustained = sum(1 for p in points if p.status == STATUS_SUSTAINED)
    n_unable = len(points) - n_sustained

    print("=== RamP ramjet operational envelope ===")
    print(f"Grid: {len(MACH_GRID)} Mach x {len(ALTITUDE_GRID_M)} altitude = {len(points)} points")
    print(f"Aref: {aref_m2:.5f} m^2, CD0: {CD0_PLACEHOLDER} (placeholder, SZACOWANY)")
    print(f"SUSTAINED: {n_sustained}, UNABLE_TO_SUSTAIN: {n_unable}")
    print(
        f"Night-3 nominal cruise (Ma {NIGHT3_MACH} / {NIGHT3_ALTITUDE_M:.0f} m): "
        f"Th2={night3['Th2_N']:.1f} N (eta_inlet multi-cone={night3['eta_inlet']:.4f})"
    )
    grid_night3 = next(
        p for p in points if p.mach == NIGHT3_MACH and p.altitude_m == NIGHT3_ALTITUDE_M
    )
    print(
        f"Grid point at same condition (MIL-E-5007D eta_d={grid_night3.eta_d:.4f}): "
        f"Th2={grid_night3.Th2_N:.1f} N, drag={grid_night3.drag_N:.1f} N, "
        f"net={grid_night3.net_thrust_N:.1f} N, status={grid_night3.status}"
    )
    print(f"Teltik 2024 CFD drag sanity reference: {TELTIK_CFD_DRAG_N_REF:.2f} N")
    if burnout is not None:
        print(f"Stage-1 burnout marker: Ma={burnout['mach']:.3f}, H={burnout['altitude_m']:.1f} m")
    print(f"\nCSV written to: {OUTPUT_CSV_PATH}")
    print(f"PNG written to: {OUTPUT_PNG_PATH}")


if __name__ == "__main__":
    main()
