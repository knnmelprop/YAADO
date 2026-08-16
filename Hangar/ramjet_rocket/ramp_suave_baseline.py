# MELprop-IADE | analyses.suave.ramp_suave_baseline | v0.1.0
"""RamP (Project B) SUAVE baseline mission, with a solver-agnostic 0D fallback.

Wires the Night-3 propulsion data set into a two-segment baseline mission
(ground boost -> nominal ramjet cruise) for the two-stage ramjet rocket.
Two solve paths share the exact same output JSON schema:

    1. **SUAVE path** (preferred): builds a
       :mod:`SUAVE.Analyses.Mission.Segments` mission -- a ground
       climb/boost segment (initial conditions taken from
       :mod:`analyses.trajectory.booster_burnout`) followed by a
       :class:`SUAVE.Analyses.Mission.Segments.Cruise.Constant_Mach_Constant_Altitude`
       cruise segment at the Night-3 nominal design point (Mach 2.5,
       6000 m ISA, Th2 real thrust from the Grzywka combustor/nozzle
       cycle). Only attempted if ``import SUAVE`` AND the specific
       ``SUAVE.Analyses.Mission.Segments`` submodule resolve; this
       container ships an EMPTY namespace-package stub named ``SUAVE``
       at the repo root (``/SUAVE/version.py`` only, no ``Analyses``
       subpackage) that shadows the real ``external/suave/trunk/SUAVE`` fork on
       ``sys.path``, so ``import SUAVE`` alone succeeds but
       ``from SUAVE.Analyses...`` raises :class:`ModuleNotFoundError`
       (a subclass of :class:`ImportError`) -- this is deliberately
       caught by the SAME guarded ``except ImportError`` block used for
       a plain missing-package case.
    2. **0D fallback path** (what actually executes in this container):
       an internal, dependency-free mission integrator built from
       already-validated repo analyses, reusing rather than duplicating
       their pipelines:
         - :func:`analyses.mission.operational_envelope.isa_atmosphere`,
           :func:`~analyses.mission.operational_envelope.compute_th2_thrust_N`,
           :func:`~analyses.mission.operational_envelope.compute_drag_N` and
           :func:`~analyses.mission.operational_envelope.reference_area_m2`
           for the cruise segment (the SAME pipeline that produced
           ``analyses/mission/results/operational_envelope.csv``, so the
           Night-3 grid point Th2=19107.4 N / drag=3546.3 N at Mach
           2.5 / 6000 m ISA is reproduced, not re-derived).
         - :class:`analyses.propulsion.combustor_nozzle_cycle.GrzywkaCombustorNozzleAnalysis`
           for the cruise fuel mass flow (``mdot_fuel_kg_s``), needed for
           the fuel-burn estimate but not exposed by
           ``compute_th2_thrust_N``.
         - :func:`analyses.trajectory.booster_burnout.load_booster_params`
           and :func:`~analyses.trajectory.booster_burnout.drag_coefficient`
           for the boost-segment drag estimate, evaluated at the
           committed ``burnout_state.json`` handoff state.

Both paths emit the common schema::

    {
        "mission_type": str,
        "segments": [
            {
                "name": str, "duration_s": float, "range_m": float,
                "mach_start": float, "mach_end": float,
                "altitude_m": float, "thrust_N": float, "drag_N": float,
            }, ...
        ],
        "total_range_m": float,
        "notes": [str, ...],
    }

References:
    SUAVE mission-segment structure: ``external/suave/trunk/SUAVE/Analyses/Mission/Segments/``
    (read-only reference fork; ``Climb/Constant_Mach_Linear_Altitude.py``,
    ``Cruise/Constant_Mach_Constant_Altitude.py``).
    Night-3 nominal cruise design point and thrust-drag pipeline:
    :mod:`analyses.mission.operational_envelope` (P1-C operational
    envelope sweep, ``analyses/mission/results/operational_envelope.csv``).
    Grzywka combustor/nozzle cycle: :mod:`analyses.propulsion.combustor_nozzle_cycle`
    (Grzywka, *Analiza numeryczna komory spalania i dyszy silnika
    strumieniowego*, Politechnika Warszawska, 2022, Sec. 6.2.2).
    Stage-1 boost-phase trajectory: :mod:`analyses.trajectory.booster_burnout`
    (point-mass 3-DOF integration, Sutton & Biblarz, *Rocket Propulsion
    Elements*, ch. 4).

Run as a script to execute the (fallback) baseline mission and write the
JSON + PNG report::

    python3 analyses/suave/ramp_suave_baseline.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from FlightLogs.Studies.operational_envelope import (  # noqa: E402
    CD0_PLACEHOLDER,
    NIGHT3_ALTITUDE_M,
    NIGHT3_MACH,
    compute_drag_N,
    compute_th2_thrust_N,
    isa_atmosphere,
    reference_area_m2,
)
from IADE_Core.modules.powerplant.cycle_methods.grzywka import (  # noqa: E402
    GrzywkaCombustorNozzleAnalysis,
)
from IADE_Core.modules.powerplant.inlet_methods.wedge import mil_e_5007_eta_std  # noqa: E402
from IADE_Core.modules.flight_dynamics.methods.point_mass_3dof import (  # noqa: E402
    BoosterParams,
    drag_coefficient as booster_drag_coefficient,
    load_booster_params,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Paths and fixed placeholders
# --------------------------------------------------------------------------

THIS_DIR: Path = Path(__file__).resolve().parent
RESULTS_DIR = THIS_DIR.parents[2] / "FlightLogs"
OUTPUT_JSON_PATH: Path = RESULTS_DIR / "suave_baseline_mission.json"
OUTPUT_PNG_PATH: Path = RESULTS_DIR / "suave_baseline_altitude_mach.png"
BURNOUT_STATE_JSON_PATH: Path = (
    Path(__file__).resolve().parents[2] / "IADE_Core" / "modules" / "trajectory" / "burnout_state.json"
)

CRUISE_DURATION_FALLBACK_S: float = 60.0
"""SZACOWANY placeholder cruise duration [s], used ONLY because no stage-2
ramjet fuel mass is available in ``Hangar/ramjet_rocket/vehicle_config.yaml``
(stage_2 has ``combustor_temp_K``/``nozzle_area_ratio``/``design_mach``, but
no ``fuel_mass_kg`` field). Matches the same order-of-magnitude placeholder
used by ``workflows.ramp_staged_mission``'s degraded-mode stub, chosen for
repo-wide consistency of the "no real fuel budget yet" flag rather than any
independent derivation."""

BOOST_INITIAL_ALTITUDE_M: float = 100.0
"""Boost-segment nominal ground/launch-rail altitude [m] (# SZACOWANY,
matches ``analyses.trajectory.booster_burnout.H0_M``)."""

BOOST_INITIAL_MACH: float = 0.0
"""Boost-segment initial Mach number (rail launch, at rest)."""


# --------------------------------------------------------------------------
# SUAVE availability probe (guarded import)
# --------------------------------------------------------------------------


def _probe_suave_available() -> bool:
    """Probe whether a functional SUAVE mission-segment API is importable.

    A plain ``import SUAVE`` is insufficient here: this container's repo
    root has an EMPTY namespace-package stub directory named ``SUAVE``
    (``/SUAVE/version.py`` only) that shadows the real reference fork in
    ``external/suave/trunk/SUAVE`` on ``sys.path``, so ``import SUAVE`` alone succeeds
    without error yet exposes none of the real mission-segment classes.
    This probe additionally attempts the specific submodule import the
    SUAVE mission path actually needs
    (``SUAVE.Analyses.Mission.Segments.Cruise``), which correctly raises
    :class:`ModuleNotFoundError` (an :class:`ImportError` subclass) in
    that situation.

    Returns:
        ``True`` only if SUAVE's mission-segment API is genuinely usable.

    Reference:
        SUAVE package layout, ``external/suave/trunk/SUAVE/Analyses/Mission/Segments/``
        (read-only reference fork).
    """
    try:
        import SUAVE  # noqa: F401
        from SUAVE.Analyses.Mission.Segments.Cruise import (  # noqa: F401
            Constant_Mach_Constant_Altitude,
        )
        from SUAVE.Analyses.Mission.Segments.Climb import (  # noqa: F401
            Constant_Mach_Linear_Altitude,
        )

        return True
    except ImportError:
        return False


SUAVE_AVAILABLE: bool = _probe_suave_available()


# --------------------------------------------------------------------------
# SUAVE mission path
# --------------------------------------------------------------------------


def build_mission_suave(
    burnout_state: dict[str, Any],
    cruise_mach: float = NIGHT3_MACH,
    cruise_altitude_m: float = NIGHT3_ALTITUDE_M,
) -> dict[str, Any]:
    """Build the two-segment baseline mission using real SUAVE segments.

    Constructs a :class:`SUAVE.Analyses.Mission.Segments.Climb.Constant_Mach_Linear_Altitude`
    ground-boost segment (initial conditions from ``burnout_state``,
    i.e. the stage-1 booster boost-phase handoff) followed by a
    :class:`SUAVE.Analyses.Mission.Segments.Cruise.Constant_Mach_Constant_Altitude`
    cruise segment at the Night-3 nominal design point, computes
    range/endurance/fuel burn per segment via the SUAVE mission solve,
    and converts the result to this module's common JSON schema.

    Args:
        burnout_state: Stage-1 booster burnout state dict (from
            ``analyses/trajectory/burnout_state.json``), providing the
            boost segment's terminal conditions.
        cruise_mach: Cruise design Mach number (Night-3 nominal, 2.5).
        cruise_altitude_m: Cruise design ISA altitude [m] (Night-3
            nominal, 6000 m).

    Returns:
        Mission dict in the common schema (see module docstring).

    Raises:
        NotImplementedError: If SUAVE is unavailable
            (:data:`SUAVE_AVAILABLE` is ``False``) or if constructing /
            solving the SUAVE mission raises any exception -- this repo's
            policy is to never let an external-solver failure propagate
            as an unhandled crash; the caller is expected to fall back to
            :func:`build_mission_fallback`.

    Reference:
        SUAVE mission-segment API, ``external/suave/trunk/SUAVE/Analyses/Mission/Segments/``
        (read-only reference fork; this repo's container does not have a
        functional top-level ``SUAVE`` package, so this path is not
        exercised here -- see :func:`_probe_suave_available`).
    """
    if not SUAVE_AVAILABLE:
        raise NotImplementedError(
            "SUAVE mission-segment API is not importable in this container "
            "(see _probe_suave_available docstring: only an empty namespace "
            "-package stub named SUAVE is on sys.path, not the real "
            "external/suave/trunk/SUAVE fork); use build_mission_fallback() instead."
        )

    try:  # pragma: no cover - unreachable while SUAVE_AVAILABLE is False
        import SUAVE
        from SUAVE.Core import Units
        from SUAVE.Analyses.Mission.Segments.Climb import Constant_Mach_Linear_Altitude
        from SUAVE.Analyses.Mission.Segments.Cruise import Constant_Mach_Constant_Altitude

        mission = SUAVE.Analyses.Mission.Sequential_Segments()
        mission.tag = "ramp_suave_baseline"

        boost = Constant_Mach_Linear_Altitude()
        boost.tag = "boost_stage_1"
        boost.altitude_start = BOOST_INITIAL_ALTITUDE_M * Units.meter
        boost.altitude_end = burnout_state["burnout_altitude_m"] * Units.meter
        boost.mach_number = max(burnout_state["burnout_mach"], 1e-3)
        mission.append_segment(boost)

        cruise = Constant_Mach_Constant_Altitude()
        cruise.tag = "cruise_stage_2_ramjet"
        cruise.altitude = cruise_altitude_m * Units.meter
        cruise.mach_number = cruise_mach
        mission.append_segment(cruise)

        results = mission.evaluate()

        segments_out = [_suave_segment_to_schema(seg) for seg in results.segments.values()]
        total_range_m = sum(seg["range_m"] for seg in segments_out)

        return {
            "mission_type": "ramp_suave_baseline_suave_solve",
            "segments": segments_out,
            "total_range_m": total_range_m,
            "notes": [
                "Solved via SUAVE.Analyses.Mission.Sequential_Segments "
                f"(boost + cruise at Mach {cruise_mach} / {cruise_altitude_m:.0f} m ISA)."
            ],
        }
    except Exception as exc:  # noqa: BLE001 - deliberate graceful degradation
        raise NotImplementedError(
            f"SUAVE mission construction/solve failed unexpectedly: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def _suave_segment_to_schema(segment: Any) -> dict[str, float | str]:
    """Flatten one solved SUAVE mission segment into the common schema.

    Args:
        segment: A solved SUAVE mission-segment results container
            (``mission.evaluate().segments[<tag>]``).

    Returns:
        Dict with ``name``, ``duration_s``, ``range_m``, ``mach_start``,
        ``mach_end``, ``altitude_m``, ``thrust_N`` and ``drag_N``.

    Reference:
        SUAVE segment ``conditions`` data structure,
        ``external/suave/trunk/SUAVE/Analyses/Mission/Segments/Conditions``.
    """  # pragma: no cover - unreachable while SUAVE_AVAILABLE is False
    conditions = segment.conditions
    return {
        "name": segment.tag,
        "duration_s": float(conditions.frames.inertial.time[-1, 0] - conditions.frames.inertial.time[0, 0]),
        "range_m": float(conditions.frames.inertial.position_vector[-1, 0]),
        "mach_start": float(conditions.freestream.mach_number[0, 0]),
        "mach_end": float(conditions.freestream.mach_number[-1, 0]),
        "altitude_m": float(-conditions.frames.inertial.position_vector[-1, 2]),
        "thrust_N": float(conditions.frames.body.thrust_force_vector[-1, 0]),
        "drag_N": float(-conditions.frames.wind.drag_force_vector[-1, 0]),
    }


# --------------------------------------------------------------------------
# 0D fallback mission path
# --------------------------------------------------------------------------


def _load_burnout_state(
    burnout_json_path: Path = BURNOUT_STATE_JSON_PATH,
) -> dict[str, Any]:
    """Load the stage-1 booster burnout handoff state.

    Args:
        burnout_json_path: Path to ``burnout_state.json`` produced by
            :func:`analyses.trajectory.booster_burnout.main`.

    Returns:
        The parsed JSON dict.

    Raises:
        FileNotFoundError: If the burnout state has not been generated
            yet (run ``python3 analyses/trajectory/booster_burnout.py``
            first).
    """
    if not burnout_json_path.exists():
        raise FileNotFoundError(
            f"{burnout_json_path} not found; run "
            "analyses/trajectory/booster_burnout.py first to produce the "
            "stage-1 boost-phase initial conditions this baseline needs."
        )
    return json.loads(burnout_json_path.read_text(encoding="utf-8"))


def _boost_segment_fallback(burnout_state: dict[str, Any]) -> dict[str, float | str]:
    """Build the ground-boost segment from the booster-burnout handoff state.

    Reuses :func:`analyses.trajectory.booster_burnout.load_booster_params`
    and :func:`~analyses.trajectory.booster_burnout.drag_coefficient` (the
    SAME step-CD(Mach) + constant fin-CD model used by the boost-phase ODE
    integration) to evaluate drag AT the burnout flow state, rather than
    re-deriving a new drag model. Thrust is the impulse-consistent
    sea-level value already recorded in ``burnout_state.json``'s metadata
    (``F = Isp_sl * mdot * g0``, Sutton & Biblarz, *Rocket Propulsion
    Elements*, eq. 2-14).

    Args:
        burnout_state: Parsed ``burnout_state.json`` dict.

    Returns:
        Segment dict in the common schema.

    Reference:
        :mod:`analyses.trajectory.booster_burnout` (point-mass 3-DOF boost
        -phase integration); :mod:`analyses.mission.operational_envelope`
        (``isa_atmosphere`` ISA 1976 troposphere helper, reused here).
    """
    booster_params: BoosterParams = load_booster_params()

    burnout_mach = float(burnout_state["burnout_mach"])
    burnout_altitude_m = float(burnout_state["burnout_altitude_m"])
    burnout_velocity_ms = float(burnout_state["burnout_velocity_ms"])
    burnout_time_s = float(burnout_state["burnout_time_s"])
    range_at_burnout_m = float(burnout_state["range_at_burnout_m"])
    thrust_used_N = float(burnout_state["metadata"]["thrust_used_N"])

    rho_kg_m3, _t_K, _p_Pa, _a_m_s = isa_atmosphere(burnout_altitude_m)
    cd_total = booster_drag_coefficient(burnout_mach, booster_params)
    q_Pa = 0.5 * rho_kg_m3 * burnout_velocity_ms**2
    drag_N = cd_total * q_Pa * booster_params.a_ref_m2

    return {
        "name": "boost_stage_1",
        "duration_s": burnout_time_s,
        "range_m": range_at_burnout_m,
        "mach_start": BOOST_INITIAL_MACH,
        "mach_end": burnout_mach,
        "altitude_m": burnout_altitude_m,
        "thrust_N": thrust_used_N,
        "drag_N": drag_N,
    }


def _cruise_grzywka_mdot_fuel_kg_s(mach: float, altitude_m: float, eta_d: float) -> float:
    """Run the Grzywka cycle once to obtain the cruise fuel mass flow.

    :func:`analyses.mission.operational_envelope.compute_th2_thrust_N`
    only returns the scalar ``Th2_N``; the fallback mission integrator
    additionally needs ``mdot_fuel_kg_s`` (not exposed by that helper) to
    derive a fuel-burn estimate, so
    :class:`~analyses.propulsion.combustor_nozzle_cycle.GrzywkaCombustorNozzleAnalysis`
    is run directly here with the SAME ``eta_inlet`` override
    (MIL-E-5007D ``eta_d``) that ``operational_envelope`` uses, so the
    two stay on the identical inlet-recovery model.

    Args:
        mach: Freestream Mach number.
        altitude_m: ISA altitude [m].
        eta_d: MIL-E-5007D inlet total-pressure recovery [-].

    Returns:
        Fuel mass flow [kg/s].

    Reference:
        Grzywka, *Analiza numeryczna komory spalania i dyszy silnika
        strumieniowego*, Politechnika Warszawska, 2022, Sec. 6.2.2, via
        :mod:`analyses.propulsion.combustor_nozzle_cycle`.
    """
    analysis = GrzywkaCombustorNozzleAnalysis()
    analysis.setup(mach0=mach, altitude_m=altitude_m, eta_inlet=eta_d)
    results = analysis.execute()
    return float(results["mdot_fuel_kg_s"])


def _cruise_segment_fallback(
    cruise_mach: float = NIGHT3_MACH,
    cruise_altitude_m: float = NIGHT3_ALTITUDE_M,
    cd0: float = CD0_PLACEHOLDER,
    cruise_duration_s: float = CRUISE_DURATION_FALLBACK_S,
) -> dict[str, Any]:
    """Build the nominal ramjet-cruise segment (Mach 2.5, 6000 m ISA).

    Reuses :mod:`analyses.mission.operational_envelope`'s exact
    thrust/drag pipeline (:func:`~analyses.mission.operational_envelope.compute_th2_thrust_N`,
    :func:`~analyses.mission.operational_envelope.compute_drag_N`,
    :func:`~analyses.mission.operational_envelope.reference_area_m2`)
    so this baseline's cruise Th2/drag reproduce the committed Night-3 /
    P1-C operational-envelope grid point at Mach 2.5 / 6000 m ISA
    (``Th2_N=19107.4``, ``drag_N=3546.3``), rather than re-deriving a
    second, potentially inconsistent, thrust/drag model. Range is
    integrated as ``dR/dt = V`` (constant-Mach, constant-altitude cruise,
    so ``R = V * t``); fuel burn is
    ``mdot_fuel_kg_s * cruise_duration_s``.

    Args:
        cruise_mach: Cruise design Mach number.
        cruise_altitude_m: Cruise design ISA altitude [m].
        cd0: Zero-lift drag coefficient [-] (# SZACOWANY, same
            placeholder as ``operational_envelope.CD0_PLACEHOLDER``).
        cruise_duration_s: Cruise duration [s] (# SZACOWANY -- no stage-2
            fuel mass is present in ``vehicle_config.yaml``, so a fixed
            placeholder duration bounds the segment instead of a
            fuel-mass-derived burn time).

    Returns:
        Tuple-like dict: the segment dict (common schema) plus
        ``fuel_burn_kg`` and ``mdot_fuel_kg_s`` as extra informational
        keys (not part of the strict 8-field schema but useful metadata,
        surfaced under the segment's own dict rather than silently
        dropped).

    Reference:
        :mod:`analyses.mission.operational_envelope` (Night-3 / P1-C
        pipeline reuse); :mod:`analyses.propulsion.combustor_nozzle_cycle`
        (Grzywka cycle, fuel mass flow).
    """
    aref_m2 = reference_area_m2()
    eta_d = mil_e_5007_eta_std(cruise_mach)

    thrust_N = compute_th2_thrust_N(cruise_mach, cruise_altitude_m, eta_d)
    drag_N = compute_drag_N(cruise_mach, cruise_altitude_m, cd0, aref_m2)
    mdot_fuel_kg_s = _cruise_grzywka_mdot_fuel_kg_s(cruise_mach, cruise_altitude_m, eta_d)

    _rho_kg_m3, _t_K, _p_Pa, a_m_s = isa_atmosphere(cruise_altitude_m)
    v_cruise_ms = cruise_mach * a_m_s
    range_m = v_cruise_ms * cruise_duration_s
    fuel_burn_kg = mdot_fuel_kg_s * cruise_duration_s

    return {
        "name": "cruise_stage_2_ramjet",
        "duration_s": cruise_duration_s,
        "range_m": range_m,
        "mach_start": cruise_mach,
        "mach_end": cruise_mach,
        "altitude_m": cruise_altitude_m,
        "thrust_N": thrust_N,
        "drag_N": drag_N,
        "mdot_fuel_kg_s": mdot_fuel_kg_s,
        "fuel_burn_kg": fuel_burn_kg,
    }


def build_mission_fallback(
    burnout_state: dict[str, Any] | None = None,
    cruise_mach: float = NIGHT3_MACH,
    cruise_altitude_m: float = NIGHT3_ALTITUDE_M,
) -> dict[str, Any]:
    """Build the two-segment baseline mission via the internal 0D integrator.

    Args:
        burnout_state: Parsed ``burnout_state.json`` dict; loaded from
            :data:`BURNOUT_STATE_JSON_PATH` if ``None``.
        cruise_mach: Cruise design Mach number (Night-3 nominal, 2.5).
        cruise_altitude_m: Cruise design ISA altitude [m] (Night-3
            nominal, 6000 m).

    Returns:
        Mission dict in the common schema (see module docstring).

    Reference:
        :mod:`analyses.mission.operational_envelope`,
        :mod:`analyses.propulsion.combustor_nozzle_cycle`,
        :mod:`analyses.trajectory.booster_burnout`.
    """
    if burnout_state is None:
        burnout_state = _load_burnout_state()

    boost_segment = _boost_segment_fallback(burnout_state)
    cruise_segment = _cruise_segment_fallback(
        cruise_mach=cruise_mach, cruise_altitude_m=cruise_altitude_m
    )

    total_range_m = boost_segment["range_m"] + cruise_segment["range_m"]

    notes: list[str] = [
        "0D fallback mission integrator (SUAVE not importable in this "
        "container -- see _probe_suave_available).",
        "Cruise segment reuses analyses.mission.operational_envelope's "
        "exact Th2/drag pipeline (Night-3 / P1-C grid point at Mach "
        f"{cruise_mach} / {cruise_altitude_m:.0f} m ISA).",
        f"cruise_duration_s={cruise_segment['duration_s']:.1f} s is a "
        "SZACOWANY fixed placeholder: Hangar/ramjet_rocket/"
        "vehicle_config.yaml stage_2 has no fuel_mass_kg field, so cruise "
        "duration cannot be derived from a real fuel budget yet.",
        f"CD0={CD0_PLACEHOLDER} zero-lift drag coefficient is SZACOWANY "
        "(no CFD drag polar across the Mach/altitude grid yet; single "
        "CFD reference point only, see operational_envelope module "
        "docstring).",
        "Boost segment thrust/drag: impulse-consistent sea-level thrust "
        "(Isp_sl*mdot*g0) and the booster's own step-CD(Mach)+fin-CD drag "
        "model, both evaluated at the burnout_state.json handoff state.",
        "Staging event (booster separation -> ramjet ignition) is NOT "
        "modeled as a third segment here (out of this baseline's scope; "
        "see workflows.ramp_staged_mission for the staging-event "
        "placeholder).",
    ]

    return {
        "mission_type": "ramp_suave_baseline_0D_fallback",
        "segments": [boost_segment, cruise_segment],
        "total_range_m": total_range_m,
        "notes": notes,
    }


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def run_baseline_mission(
    burnout_state: dict[str, Any] | None = None,
    cruise_mach: float = NIGHT3_MACH,
    cruise_altitude_m: float = NIGHT3_ALTITUDE_M,
) -> dict[str, Any]:
    """Run the baseline mission, preferring SUAVE and falling back to 0D.

    Args:
        burnout_state: Parsed ``burnout_state.json`` dict; loaded from
            :data:`BURNOUT_STATE_JSON_PATH` if ``None`` (loaded once here
            so both the SUAVE attempt and the fallback share the same
            state).
        cruise_mach: Cruise design Mach number (Night-3 nominal, 2.5).
        cruise_altitude_m: Cruise design ISA altitude [m] (Night-3
            nominal, 6000 m).

    Returns:
        Mission dict in the common schema (see module docstring).

    Reference:
        Both :func:`build_mission_suave` and :func:`build_mission_fallback`.
    """
    if burnout_state is None:
        burnout_state = _load_burnout_state()

    if SUAVE_AVAILABLE:
        try:
            return build_mission_suave(
                burnout_state, cruise_mach=cruise_mach, cruise_altitude_m=cruise_altitude_m
            )
        except NotImplementedError as exc:
            logger.warning(
                "SUAVE mission solve failed (%s); falling back to internal 0D integrator.",
                exc,
            )

    logger.warning("WARNING: SUAVE not available, using internal 0D fallback")
    return build_mission_fallback(
        burnout_state, cruise_mach=cruise_mach, cruise_altitude_m=cruise_altitude_m
    )


def write_json(mission_data: dict[str, Any], output_path: Path = OUTPUT_JSON_PATH) -> None:
    """Write the mission dict to JSON.

    Args:
        mission_data: Mission dict in the common schema.
        output_path: Destination JSON path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(mission_data, indent=2), encoding="utf-8")


def plot_altitude_mach(
    mission_data: dict[str, Any], output_path: Path = OUTPUT_PNG_PATH
) -> None:
    """Plot the altitude-vs-Mach baseline mission trajectory to a 150-DPI PNG.

    Connects the segment start/end (altitude, Mach) points in mission
    order: launch-rail -> boost-segment end (burnout) -> cruise segment
    (constant Mach/altitude), annotating each waypoint.

    Args:
        mission_data: Mission dict in the common schema.
        output_path: Destination PNG path.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    segments = mission_data["segments"]

    machs: list[float] = [BOOST_INITIAL_MACH]
    alts: list[float] = [BOOST_INITIAL_ALTITUDE_M]
    labels: list[str] = ["launch"]

    for seg in segments:
        machs.append(seg["mach_end"])
        alts.append(seg["altitude_m"])
        labels.append(seg["name"])

    fig, ax = plt.subplots(figsize=(8.0, 6.0))
    ax.plot(machs, alts, marker="o", color="tab:blue", linewidth=2.0)
    for mach, alt, label in zip(machs, alts, labels):
        ax.annotate(label, (mach, alt), textcoords="offset points", xytext=(8, 6), fontsize=8)

    ax.set_xlabel("Mach number [-]")
    ax.set_ylabel("Altitude [m]")
    ax.set_title(
        f"MELprop-IADE | RamP SUAVE baseline mission ({mission_data['mission_type']})"
    )
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> dict[str, Any]:
    """Run the baseline mission and write JSON + PNG outputs.

    Returns:
        The mission dict in the common schema.
    """
    logging.basicConfig(level=logging.INFO)

    mission_data = run_baseline_mission()
    write_json(mission_data)
    plot_altitude_mach(mission_data)

    print(f"=== RamP SUAVE baseline mission ({mission_data['mission_type']}) ===")
    for seg in mission_data["segments"]:
        print(
            f"  {seg['name']}: duration={seg['duration_s']:.1f} s, "
            f"range={seg['range_m']:.1f} m, Mach {seg['mach_start']:.2f} -> "
            f"{seg['mach_end']:.2f}, altitude={seg['altitude_m']:.1f} m, "
            f"thrust={seg['thrust_N']:.1f} N, drag={seg['drag_N']:.1f} N"
        )
    print(f"Total range: {mission_data['total_range_m']:.1f} m")
    print(f"\nJSON written to: {OUTPUT_JSON_PATH}")
    print(f"PNG written to: {OUTPUT_PNG_PATH}")

    return mission_data


if __name__ == "__main__":
    main()
