# MELprop-IADE | workflows.ramp_staged_mission | v0.1.0
"""Staged mission profile for the Project B two-stage ramjet rocket.

This module builds a solver-agnostic mission profile using
:class:`core.mission_builder.MissionBuilder`, defining the sequence of
segments from solid-booster ignition through ramjet cruise. The mission
includes a staging event that propagates the booster burnout state (mass,
velocity, altitude) as initial conditions for the ramjet cruise segment.

Theory / model references:
    - Staging dynamics: Sutton & Biblarz, *Rocket Propulsion Elements*, ch. 4
      (stage separation, momentum balance, coast phase).
    - Mission segment sequencing: SUAVE mission structure, adapted to a
      solver-agnostic builder pattern per CLAUDE.md architecture.

Run as a script to print the mission profile and booster-burnout handoff state::

    python3 workflows/ramp_staged_mission.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.mission_builder import MissionBuilder, MissionSegment  # noqa: E402


@dataclass
class BurnoutState:
    """Stage-1 booster burnout state handed off to stage-2.

    Attributes:
        time_s: Time since launch at burnout [s].
        mass_kg: Vehicle mass at burnout (stage-1 propellant depleted) [kg].
        velocity_ms: Velocity magnitude at burnout [m/s].
        velocity_x_ms: Horizontal (downrange) velocity component [m/s].
        velocity_h_ms: Vertical velocity component [m/s].
        altitude_m: Geometric altitude at burnout [m].
        range_m: Downrange distance traveled [m].
        mach: Mach number at burnout [-].
        dynamic_pressure_pa: Dynamic pressure at burnout [Pa].
    """

    time_s: float
    mass_kg: float
    velocity_ms: float
    velocity_x_ms: float
    velocity_h_ms: float
    altitude_m: float
    range_m: float
    mach: float
    dynamic_pressure_pa: float


def load_burnout_state_from_json(
    burnout_json_path: Path,
) -> BurnoutState:
    """Load stage-1 burnout state from booster_burnout.py JSON output.

    Args:
        burnout_json_path: Path to ``burnout_state.json`` produced by
            ``analyses.trajectory.booster_burnout.main()``.

    Returns:
        Parsed :class:`BurnoutState` ready for handoff to stage-2.

    Raises:
        FileNotFoundError: If the JSON file does not exist.
        KeyError: If required fields are missing from the JSON.
    """
    data = json.loads(burnout_json_path.read_text(encoding="utf-8"))

    # Compute q at burnout from the reported state (not directly in top-level JSON,
    # but can be recomputed from velocity + altitude)
    # For now, read the scalar q_max as a proxy (this is a simplification;
    # in production you'd evaluate ISA + q at the actual burnout point)
    q_burnout_pa = data.get("q_max_pa", 0.0)  # TBD: compute exact q at burnout

    return BurnoutState(
        time_s=data["burnout_time_s"],
        mass_kg=data["metadata"]["mass_at_stop_kg"],
        velocity_ms=data["burnout_velocity_ms"],
        velocity_x_ms=data["metadata"]["burnout_vx_ms"],
        velocity_h_ms=data["metadata"]["burnout_vh_ms"],
        altitude_m=data["burnout_altitude_m"],
        range_m=data["range_at_burnout_m"],
        mach=data["burnout_mach"],
        dynamic_pressure_pa=q_burnout_pa,
    )


def build_ramp_staged_mission(burnout_state: BurnoutState) -> list[MissionSegment]:
    """Build the two-stage ramjet rocket mission profile.

    Args:
        burnout_state: Stage-1 booster burnout state from
            :func:`load_burnout_state_from_json`.

    Returns:
        Ordered list of :class:`MissionSegment` definitions, ready for a
        solver (SUAVE or OpenMDAO) to instantiate and integrate.
    """
    builder = MissionBuilder("ramp_two_stage")

    # Segment 1: Solid booster boost phase (already integrated offline by
    # booster_burnout.py; this segment is a "completed" reference that logs
    # the initial boost but does not re-integrate during mission solve)
    builder.add_segment(
        name="boost_stage_1",
        segment_type="boost",
        propulsion_type="solid_rocket",
        burn_time_s=6.0,  # from vehicle_config.yaml stage_1.propulsion.burn_time_s
        initial_mass_kg=355.02,  # SZACOWANY, from vehicle_config mass_properties
        final_mass_kg=burnout_state.mass_kg,
        final_velocity_ms=burnout_state.velocity_ms,
        final_altitude_m=burnout_state.altitude_m,
        note="Pre-integrated by analyses.trajectory.booster_burnout; burnout state fed forward",
    )

    # Segment 2: Staging event — stage separation, coast, ramjet ignition
    # In a real MDO workflow this would model:
    #   - Momentum balance across separation (if stage-1 is jettisoned)
    #   - Coast phase under drag + gravity until ramjet ignition conditions met
    #   - Ramjet start sequence (inlet start, combustor light-off)
    # For now, this is a symbolic "handoff" segment with the burnout state
    # as parameters; a future ODE integration or SUAVE mission segment would
    # compute the transient.
    builder.add_segment(
        name="staging_event",
        segment_type="staging_event",
        event_type="booster_burnout_to_ramjet_ignition",
        initial_mass_kg=burnout_state.mass_kg,
        initial_velocity_ms=burnout_state.velocity_ms,
        initial_velocity_x_ms=burnout_state.velocity_x_ms,
        initial_velocity_h_ms=burnout_state.velocity_h_ms,
        initial_altitude_m=burnout_state.altitude_m,
        initial_range_m=burnout_state.range_m,
        initial_mach=burnout_state.mach,
        coast_time_s=0.5,  # SZACOWANY — brief coast before ramjet ignition
        separation_delta_v_ms=0.0,  # SZACOWANY — assume no pyro kick for now
        note=(
            "Stage-1 burnout -> stage-2 ignition handoff. Coast phase under "
            "drag + gravity (not yet integrated; placeholder). Ramjet inlet "
            "start and combustor ignition transient not modeled (TBD)."
        ),
    )

    # Segment 3: Ramjet cruise (stage-2) — quasi-steady design point.
    # Thrust/TSFC/mdot_fuel are computed from the L2 1-D ramjet cycle model
    # (analyses.propulsion.ramjet_cycle.RamjetCycleAnalysis) at the design
    # condition (Mach 2.5, 10,000 m ISA). This is still NOT a trajectory
    # ODE integration (fuel depletion, drag, and altitude/velocity coupling
    # over time remain TBD); it is a single quasi-steady operating point
    # used to derive a first-order cruise_time_s / cruise_range_m estimate
    # from the SZACOWANY 15 kg fuel load.
    cruise_design_point = _compute_ramjet_design_point()

    builder.add_segment(
        name="cruise_stage_2_ramjet",
        segment_type="cruise",
        propulsion_type="ramjet",
        **cruise_design_point,
    )

    return builder.build()


#: Fallback cruise-segment parameters used only if the L2 ramjet cycle
#: model (analyses.propulsion.ramjet_cycle) is unavailable or raises an
#: unexpected error. These reproduce the original fixed-guess stub so the
#: mission structure keeps degrading gracefully rather than failing.
_STUB_CRUISE_DESIGN_POINT: dict[str, Any] = {
    "design_mach": 2.5,  # from vehicle_config.yaml stage_2.design_mach
    "cruise_altitude_m": 10000.0,  # TBD — design decision, typical ramjet cruise alt
    "cruise_time_s": 60.0,  # TBD — placeholder cruise duration
    "cruise_range_m": 0.0,  # TBD — cannot be derived without the cycle model
    "fuel_mass_kg": 15.0,  # SZACOWANY — placeholder stage-2 fuel load
    "thrust_N": 0.0,  # TBD — cycle model unavailable
    "thrust_cylindrical_nozzle_N": 0.0,  # TBD — cycle model unavailable
    "tsfc_kg_per_Ns": 0.0,  # TBD — cycle model unavailable
    "mdot_fuel_kg_s": 0.0,  # TBD — cycle model unavailable
    "note": (
        "FALLBACK STUB: analyses.propulsion.ramjet_cycle raised an "
        "unexpected error, so this segment reverted to fixed-guess "
        "placeholder values (thrust/TSFC/mdot_fuel = 0.0, cruise_time_s = "
        "60.0 s placeholder). Re-run once the ramjet cycle model is "
        "fixed to recover a real design point."
    ),
}


def _compute_ramjet_design_point() -> dict[str, Any]:
    """Compute the stage-2 ramjet cruise design point via the L2 cycle model.

    Runs :class:`analyses.propulsion.ramjet_cycle.RamjetCycleAnalysis` at
    the design condition (Mach 2.5, 10,000 m ISA) and derives a first-order
    quasi-steady cruise duration and range from the SZACOWANY 15 kg fuel
    load: ``cruise_time_s = fuel_mass_kg / mdot_fuel_kg_s`` and
    ``cruise_range_m = V_cruise * cruise_time_s``.

    This is a design-point evaluation, NOT a trajectory ODE — fuel
    depletion, drag and altitude/velocity coupling over time are not
    integrated (TBD). If the cycle model import or execution fails
    unexpectedly, the function degrades gracefully to the documented
    fixed-guess stub values (see :data:`_STUB_CRUISE_DESIGN_POINT`) rather
    than raising, so the mission structure keeps building.

    Returns:
        Dict of cruise-segment parameters ready to pass as
        ``**kwargs`` to :meth:`core.mission_builder.MissionBuilder.add_segment`.
    """
    fuel_mass_kg = 15.0  # SZACOWANY — placeholder stage-2 fuel load

    try:
        from analyses.propulsion.ramjet_cycle import (
            DESIGN_ALTITUDE_M,
            MACH_DESIGN,
            RamjetCycleAnalysis,
        )

        analysis = RamjetCycleAnalysis()
        analysis.setup(mach0=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M)
        results = analysis.execute()

        thrust_N = results["thrust_N"]
        thrust_cylindrical_nozzle_N = results["thrust_cylindrical_nozzle_N"]
        tsfc_kg_per_Ns = results["tsfc_kg_per_Ns"]
        mdot_fuel_kg_s = results["mdot_fuel_kg_s"]
        v_cruise_ms = results.metadata["station_table"][0]["velocity_m_s"]

        cruise_time_s = fuel_mass_kg / mdot_fuel_kg_s
        cruise_range_m = v_cruise_ms * cruise_time_s

        return {
            "design_mach": MACH_DESIGN,
            "cruise_altitude_m": DESIGN_ALTITUDE_M,
            "cruise_time_s": cruise_time_s,
            "cruise_range_m": cruise_range_m,
            "fuel_mass_kg": fuel_mass_kg,  # SZACOWANY — placeholder fuel load
            "thrust_N": thrust_N,
            "thrust_cylindrical_nozzle_N": thrust_cylindrical_nozzle_N,
            "tsfc_kg_per_Ns": tsfc_kg_per_Ns,
            "mdot_fuel_kg_s": mdot_fuel_kg_s,
            "note": (
                "Ramjet cruise: quasi-steady design point (Mach 2.5, "
                "10,000 m ISA), NOT a trajectory ODE (fuel depletion, "
                "drag and altitude/velocity coupling over time remain "
                "TBD). thrust_N/tsfc_kg_per_Ns/mdot_fuel_kg_s from "
                "analyses.propulsion.ramjet_cycle.RamjetCycleAnalysis "
                "(matched design nozzle); thrust_cylindrical_nozzle_N is "
                "the as-built Fusion CAD cylindrical-nozzle thrust, kept "
                "alongside thrust_N so the CAD-vs-design discrepancy "
                "stays visible. cruise_time_s = fuel_mass_kg / "
                "mdot_fuel_kg_s and cruise_range_m = V_cruise * "
                "cruise_time_s are DERIVED from the SZACOWANY 15 kg "
                "fuel_mass_kg. Reference model: L2 1-D cycle, "
                "single-method, MATLAB baseline unavailable, CFD delta "
                "+20-30% open (see ramjet_cycle module docstring "
                "'REFERENCE-MODEL DISCLOSURE')."
            ),
        }
    except Exception as exc:  # noqa: BLE001 — deliberate graceful degradation
        stub = dict(_STUB_CRUISE_DESIGN_POINT)
        stub["note"] = (
            f"{stub['note']} Original exception: {type(exc).__name__}: {exc}"
        )
        return stub


def main() -> None:
    """Load booster burnout state, build the staged mission, and print.

    Writes the mission profile and burnout handoff state to
    ``staged_mission_profile.json`` in the same directory as this script.
    """
    this_dir = Path(__file__).resolve().parent
    burnout_json_path = this_dir.parent / "analyses" / "trajectory" / "burnout_state.json"
    output_json_path = this_dir / "staged_mission_profile.json"

    burnout_state = load_burnout_state_from_json(burnout_json_path)
    mission = build_ramp_staged_mission(burnout_state)

    output: dict[str, Any] = {
        "mission_name": "ramp_two_stage",
        "burnout_handoff_state": asdict(burnout_state),
        "segments": [
            {
                "name": seg.name,
                "segment_type": seg.segment_type,
                "parameters": seg.parameters,
            }
            for seg in mission
        ],
    }

    output_json_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print("Two-stage ramjet rocket mission profile:")
    print(json.dumps(output, indent=2))
    print(f"\nWrote {output_json_path}")


if __name__ == "__main__":
    main()
