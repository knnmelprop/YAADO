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

    # Segment 3: Ramjet cruise (stage-2)
    # This is a placeholder cruise segment; the ramjet propulsion analysis
    # (analyses.propulsion.ramjet_cycle) exists but is not yet wired into
    # a trajectory ODE. A production workflow would integrate:
    #   - Ramjet thrust and SFC from the pyCycle model
    #   - Drag from analyses.aerodynamics.rocket_empirical_aero
    #   - Fuel depletion over time -> cruise duration or range objective
    builder.add_segment(
        name="cruise_stage_2_ramjet",
        segment_type="cruise",
        propulsion_type="ramjet",
        design_mach=2.5,  # from vehicle_config.yaml stage_2.design_mach
        cruise_altitude_m=10000.0,  # TBD — design decision, typical ramjet cruise alt
        cruise_time_s=60.0,  # TBD — placeholder cruise duration
        fuel_mass_kg=15.0,  # SZACOWANY — placeholder stage-2 fuel load
        note=(
            "Ramjet cruise at Mach 2.5. Thrust/SFC from pyCycle ramjet_cycle "
            "analysis; drag from rocket_empirical_aero. Trajectory integration "
            "not yet implemented (TBD). This segment is a design-point "
            "placeholder for MDO workflows."
        ),
    )

    return builder.build()


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
