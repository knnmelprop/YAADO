# MELprop-IADE | workflows.ramp_staged_mission | v0.2.0
"""Staged mission profile for the Project B two-stage ramjet rocket.

This module builds a solver-agnostic mission profile using
:class:`core.mission_builder.MissionBuilder`, defining the sequence of
segments from solid-booster ignition through ramjet cruise. The mission
includes a staging event that propagates the booster burnout state (mass,
velocity, altitude) as initial conditions for the ramjet cruise segment.

The ramjet-cruise design point (segment 3, ``cruise_stage_2_ramjet``) is
computed from
:class:`analyses.propulsion.combustor_nozzle_cycle.GrzywkaCombustorNozzleAnalysis`
(the Grzywka station 1-2-21-3 combustor/nozzle cycle). Its three thrust
scenarios -- ``Thi`` (ideal), ``Th1`` (combustor loss only) and ``Th2``
(real, combustor + nozzle losses) -- are never collapsed to a single
number: each is propagated through its own cruise-time/range derivation
and preserved under the cruise segment's ``thrust_scenarios`` parameter.

Night-3 Phase 2 change: the mission's NOMINAL top-level design point was
switched from ``Th2`` to ``Th1`` (combustor-loss-only, non-ideal), per
the project verification gate's requirement that a non-ideal but
non-most-conservative operating point drive the nominal mission profile.
``Thi`` and ``Th2`` remain always present as explicit upper/lower thrust
bounds under ``thrust_scenarios`` (and mirrored as
``thrust_upper_bound_N`` / ``thrust_lower_bound_N`` at the top level) --
all three scenarios are still never collapsed away. A first-order net
thrust margin at cruise, ``net_thrust_margin_N = Th1 - drag_estimate_N``,
is also computed and logged against two independent drag estimates (a
0-order CD0*q*Aref placeholder and the Teltik 2024 CFD point), see
:func:`_estimate_cruise_drag_N` and the cruise segment's
``drag_estimates`` parameter.

Theory / model references:
    - Staging dynamics: Sutton & Biblarz, *Rocket Propulsion Elements*, ch. 4
      (stage separation, momentum balance, coast phase).
    - Mission segment sequencing: SUAVE mission structure, adapted to a
      solver-agnostic builder pattern per CLAUDE.md architecture.
    - Ramjet cruise cycle: Grzywka, *Analiza numeryczna komory spalania i
      dyszy silnika strumieniowego*, Politechnika Warszawska, 2022, Sec.
      6.2.2 (three-thrust decomposition), via
      :mod:`analyses.propulsion.combustor_nozzle_cycle`.

Run as a script to print the mission profile and booster-burnout handoff state::

    python3 workflows/ramp_staged_mission.py
"""

from __future__ import annotations

import json
import math
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
    # Thrust/TSFC/Isp/mdot_fuel are computed from the L2 1-D Grzywka
    # combustor+nozzle cycle model
    # (analyses.propulsion.combustor_nozzle_cycle.GrzywkaCombustorNozzleAnalysis)
    # at the design condition (Mach 2.5, 10,000 m ISA), for EACH of the
    # three Grzywka thrust scenarios (Thi ideal / Th1 combustor-loss-only /
    # Th2 real — see _THRUST_SCENARIOS below); Th2 (most conservative) is
    # the nominal top-level design point, but all three are preserved
    # under cruise_design_point["thrust_scenarios"]. This is still NOT a
    # trajectory ODE integration (fuel depletion, drag, and
    # altitude/velocity coupling over time remain TBD); it is a single
    # quasi-steady operating point used to derive a first-order
    # cruise_time_s / cruise_range_m estimate PER SCENARIO from the
    # SZACOWANY 15 kg fuel load.
    cruise_design_point = _compute_ramjet_design_point()

    builder.add_segment(
        name="cruise_stage_2_ramjet",
        segment_type="cruise",
        propulsion_type="ramjet",
        **cruise_design_point,
    )

    return builder.build()


#: Grzywka three-thrust-model scenarios (Sec. 6.2.2), in canonical order
#: from least to most conservative. Each tuple is
#: ``(scenario_key, results_data_key, description)``; ``results_data_key``
#: indexes the ``AnalysisResults`` returned by
#: :meth:`analyses.propulsion.combustor_nozzle_cycle.GrzywkaCombustorNozzleAnalysis.execute`.
_THRUST_SCENARIOS: tuple[tuple[str, str, str], ...] = (
    ("Thi", "Thi_N", "ideal: no combustor or nozzle total-pressure losses (upper bound)"),
    (
        "Th1",
        "Th1_N",
        "combustor total-pressure loss only, nozzle idealized "
        "(NOMINAL as of Night-3 Phase 2 -- see module docstring)",
    ),
    (
        "Th2",
        "Th2_N",
        "real: combustor AND nozzle total-pressure losses "
        "(most conservative; lower bound, no longer the nominal)",
    ),
)

#: CD0 (zero-lift drag coefficient) placeholder used for the first-order
#: cruise drag estimate. SZACOWANY -- a generic slender-body supersonic
#: drag-coefficient guess, NOT derived from AVL/CFD/wind-tunnel data for
#: this airframe (AVL is invalid here per CLAUDE.md rule 7: Ma > 0.6).
CD0_CRUISE_PLACEHOLDER: float = 0.35  # SZACOWANY

#: Teltik 2024 CFD-derived cruise drag reference point [N], independent of
#: the 0-order CD0*q*Aref estimate above. Logged alongside it (both drags
#: and both resulting net-thrust margins are always reported together, per
#: this repo's method-discrepancy convention -- CFD delta is surfaced, not
#: resolved).
TELTIK_CFD_DRAG_N: float = 2451.95


#: Fallback cruise-segment parameters used only if the L2 combustor/nozzle
#: cycle model (analyses.propulsion.combustor_nozzle_cycle) is unavailable
#: or raises an unexpected error. These reproduce the original fixed-guess
#: stub, extended with a ``thrust_scenarios`` block so downstream code that
#: expects all three Grzywka scenarios keeps working even in degraded mode.
_STUB_CRUISE_DESIGN_POINT: dict[str, Any] = {
    "design_mach": 2.5,  # from vehicle_config.yaml stage_2.design_mach
    "cruise_altitude_m": 10000.0,  # TBD — design decision, typical ramjet cruise alt
    "cruise_time_s": 60.0,  # TBD — placeholder cruise duration
    "cruise_range_m": 0.0,  # TBD — cannot be derived without the cycle model
    "fuel_mass_kg": 15.0,  # SZACOWANY — placeholder stage-2 fuel load
    "thrust_N": 0.0,  # TBD — cycle model unavailable (nominal Th1, Night-3 Phase 2)
    "tsfc_kg_per_Ns": 0.0,  # TBD — cycle model unavailable
    "isp_s": 0.0,  # TBD — cycle model unavailable
    "mdot_fuel_kg_s": 0.0,  # TBD — cycle model unavailable
    "eta_inlet": 0.0,  # TBD — cycle model unavailable
    "thrust_upper_bound_N": 0.0,  # TBD — mirrors Thi
    "thrust_lower_bound_N": 0.0,  # TBD — mirrors Th2
    "net_thrust_margin_N": 0.0,  # TBD — Th1 - drag_estimate_N
    "drag_estimates": {
        "cd0_placeholder_N": 0.0,
        "teltik_cfd_N": TELTIK_CFD_DRAG_N,
    },
    "thrust_scenarios": {
        key: {
            "thrust_N": 0.0,
            "tsfc_kg_per_Ns": 0.0,
            "isp_s": 0.0,
            "mdot_fuel_kg_s": 0.0,
            "cruise_time_s": 60.0,
            "cruise_range_m": 0.0,
            "description": description,
        }
        for key, _field, description in _THRUST_SCENARIOS
    },
    "note": (
        "FALLBACK STUB: analyses.propulsion.combustor_nozzle_cycle raised "
        "an unexpected error, so this segment reverted to fixed-guess "
        "placeholder values (thrust/TSFC/mdot_fuel = 0.0 for all three "
        "Thi/Th1/Th2 scenarios, cruise_time_s = 60.0 s placeholder). "
        "Re-run once the Grzywka combustor/nozzle cycle model is fixed to "
        "recover a real design point."
    ),
}


def _scenario_cruise_point(
    thrust_N: float,
    mdot_fuel_kg_s: float,
    fuel_mass_kg: float,
    v_cruise_ms: float,
    g0_m_s2: float,
) -> dict[str, float]:
    """Derive TSFC, Isp, cruise time and range for one thrust scenario.

    Fuel flow ``mdot_fuel_kg_s`` is, by construction of the Grzywka
    station model, IDENTICAL across the Thi/Th1/Th2 thrust scenarios (same
    mass flow, Tt1, Tt2 and fuel-air ratio; only the delivered nozzle
    total pressure differs — see the
    :mod:`analyses.propulsion.combustor_nozzle_cycle` module docstring).
    Consequently ``cruise_time_s = fuel_mass_kg / mdot_fuel_kg_s`` and
    ``cruise_range_m = V_cruise * cruise_time_s`` come out numerically
    equal across scenarios at THIS quasi-steady, constant-cruise-Mach
    design point (thrust differences show up in ``tsfc_kg_per_Ns`` /
    ``isp_s``, not in burn duration, since the combustor sets fuel flow
    independent of nozzle loss). This coincidence is a physical property
    of the model and is surfaced explicitly here rather than hidden, per
    this repo's method-discrepancy convention; a future trajectory-ODE
    cruise model (fuel depletion + drag/altitude/velocity coupling) would
    let a lower-thrust scenario diverge from the assumed constant Mach.

    Args:
        thrust_N: Scenario thrust [N] (Thi, Th1 or Th2).
        mdot_fuel_kg_s: Fuel mass flow [kg/s] (scenario-invariant).
        fuel_mass_kg: Available stage-2 fuel mass [kg].
        v_cruise_ms: Cruise (freestream) velocity [m/s].
        g0_m_s2: Standard gravity used for the Isp definition [m/s^2].

    Returns:
        Dict with ``thrust_N``, ``tsfc_kg_per_Ns``, ``isp_s``,
        ``mdot_fuel_kg_s``, ``cruise_time_s`` and ``cruise_range_m``.
    """
    tsfc_kg_per_Ns = mdot_fuel_kg_s / thrust_N
    isp_s = thrust_N / (mdot_fuel_kg_s * g0_m_s2)
    cruise_time_s = fuel_mass_kg / mdot_fuel_kg_s
    cruise_range_m = v_cruise_ms * cruise_time_s
    return {
        "thrust_N": thrust_N,
        "tsfc_kg_per_Ns": tsfc_kg_per_Ns,
        "isp_s": isp_s,
        "mdot_fuel_kg_s": mdot_fuel_kg_s,
        "cruise_time_s": cruise_time_s,
        "cruise_range_m": cruise_range_m,
    }


def _vehicle_body_diameter_m() -> float:
    """Load the stage-2 body diameter from vehicle_config.yaml.

    Loaded via :class:`src.schemas.vehicle_schema.BaseVehicleConfig` (NOT
    hardcoded), per this module's Night-3 Phase 2 requirement that the
    cruise drag reference area track the vehicle config as the single
    source of truth.

    Returns:
        Body (airframe) diameter ``body.diameter_m`` [m] from
        ``vehicles/ramjet_rocket/vehicle_config.yaml``.
    """
    from src.schemas.vehicle_schema import BaseVehicleConfig

    this_dir = Path(__file__).resolve().parent
    config_path = (
        this_dir.parent / "vehicles" / "ramjet_rocket" / "vehicle_config.yaml"
    )
    config = BaseVehicleConfig.from_yaml(config_path)
    return config.body.diameter_m  # type: ignore[union-attr]


def _estimate_cruise_drag_N(
    mach: float,
    altitude_m: float,
    diameter_m: float,
    cd0: float = CD0_CRUISE_PLACEHOLDER,
) -> dict[str, float]:
    """0-order cruise drag estimate ``CD0 * q * Aref`` plus the Teltik CFD point.

    ``Aref`` is the body cross-sectional area ``pi/4 * d^2`` with ``d``
    the airframe diameter loaded from ``vehicle_config.yaml`` (never
    hardcoded, see :func:`_vehicle_body_diameter_m`). ``q`` is the
    dynamic pressure ``0.5 * rho * V^2`` at the given (Mach, ISA
    altitude) condition, using
    :func:`analyses.propulsion.inlet_performance.isa_atmosphere` for the
    freestream state. ``CD0`` = 0.35 is a documented SZACOWANY generic
    slender-body supersonic placeholder -- NOT derived from AVL (invalid
    above Ma 0.6 per CLAUDE.md rule 7) or CFD for this specific airframe.

    Args:
        mach: Freestream Mach number at cruise [-].
        altitude_m: ISA cruise altitude [m].
        diameter_m: Body diameter used for the reference area [m].
        cd0: Zero-lift drag coefficient placeholder [-].

    Returns:
        Dict with ``cd0_placeholder``, ``q_pa``, ``aref_m2``,
        ``cd0_placeholder_N`` (the 0-order drag estimate) and
        ``teltik_cfd_N`` (the independent Teltik 2024 CFD drag point,
        :data:`TELTIK_CFD_DRAG_N`).
    """
    from analyses.propulsion.inlet_performance import isa_atmosphere

    atmosphere = isa_atmosphere(altitude_m)
    v_ms = mach * atmosphere.speed_of_sound_m_s
    q_pa = 0.5 * atmosphere.density_kg_m3 * v_ms**2
    aref_m2 = math.pi / 4.0 * diameter_m**2
    drag_0order_N = cd0 * q_pa * aref_m2

    return {
        "cd0_placeholder": cd0,
        "q_pa": q_pa,
        "aref_m2": aref_m2,
        "cd0_placeholder_N": drag_0order_N,
        "teltik_cfd_N": TELTIK_CFD_DRAG_N,
    }


def _compute_ramjet_design_point() -> dict[str, Any]:
    """Compute the stage-2 ramjet cruise design point via the L2 Grzywka cycle.

    Runs
    :class:`analyses.propulsion.combustor_nozzle_cycle.GrzywkaCombustorNozzleAnalysis`
    at the design condition (Mach 2.5, 10,000 m ISA) and derives, for
    EACH of the three Grzywka thrust scenarios (``Thi`` ideal, ``Th1``
    combustor-loss-only, ``Th2`` real/combustor+nozzle losses — see
    :data:`_THRUST_SCENARIOS`), a first-order quasi-steady cruise duration
    and range from the SZACOWANY 15 kg fuel load via
    :func:`_scenario_cruise_point`. The three scenarios are never
    collapsed to a single number: all three are returned under
    ``thrust_scenarios``, keyed ``"Thi"``/``"Th1"``/``"Th2"``.

    Night-3 Phase 2: the top-level ``thrust_N``/``tsfc_kg_per_Ns``/
    ``isp_s``/``cruise_time_s``/``cruise_range_m`` fields now mirror
    ``Th1`` (combustor-loss-only, non-ideal) as the mission's NOMINAL
    design point -- previously ``Th2`` (real, most conservative) was
    nominal; that switch is the headline change of this phase. ``Thi``
    and ``Th2`` remain always-present explicit upper/lower thrust bounds,
    mirrored at the top level as ``thrust_upper_bound_N`` /
    ``thrust_lower_bound_N`` (verification-gate requirement: all three
    scenarios always present, never collapsed). A first-order net thrust
    margin at cruise, ``net_thrust_margin_N = Th1 - drag_estimate_N``, is
    computed against TWO independent drag estimates (0-order
    ``CD0*q*Aref`` and the Teltik 2024 CFD point) via
    :func:`_estimate_cruise_drag_N`; both margins are returned under
    ``net_thrust_margins_N``.

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
        from analyses.propulsion.combustor_nozzle_cycle import (
            GrzywkaCombustorNozzleAnalysis,
        )
        from analyses.propulsion.inlet_performance import (
            DESIGN_ALTITUDE_M,
            G0,
            MACH_DESIGN,
            isa_atmosphere,
        )

        analysis = GrzywkaCombustorNozzleAnalysis()
        analysis.setup(mach0=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M)
        results = analysis.execute()

        mdot_fuel_kg_s = results["mdot_fuel_kg_s"]
        atmosphere = isa_atmosphere(DESIGN_ALTITUDE_M)
        v_cruise_ms = MACH_DESIGN * atmosphere.speed_of_sound_m_s

        thrust_scenarios: dict[str, dict[str, float]] = {}
        for key, thrust_field, description in _THRUST_SCENARIOS:
            scenario = _scenario_cruise_point(
                thrust_N=results[thrust_field],
                mdot_fuel_kg_s=mdot_fuel_kg_s,
                fuel_mass_kg=fuel_mass_kg,
                v_cruise_ms=v_cruise_ms,
                g0_m_s2=G0,
            )
            scenario["description"] = description
            thrust_scenarios[key] = scenario

        nominal = thrust_scenarios["Th1"]  # combustor-loss-only, non-ideal

        diameter_m = _vehicle_body_diameter_m()
        drag_estimates = _estimate_cruise_drag_N(
            mach=MACH_DESIGN, altitude_m=DESIGN_ALTITUDE_M, diameter_m=diameter_m
        )
        net_thrust_margins_N = {
            "vs_cd0_placeholder_N": nominal["thrust_N"]
            - drag_estimates["cd0_placeholder_N"],
            "vs_teltik_cfd_N": nominal["thrust_N"] - drag_estimates["teltik_cfd_N"],
        }

        return {
            "design_mach": MACH_DESIGN,
            "cruise_altitude_m": DESIGN_ALTITUDE_M,  # source: inlet_performance.DESIGN_ALTITUDE_M (typical ramjet cruise band, TBD design decision)
            "cruise_time_s": nominal["cruise_time_s"],
            "cruise_range_m": nominal["cruise_range_m"],
            "fuel_mass_kg": fuel_mass_kg,  # SZACOWANY — placeholder fuel load
            "thrust_N": nominal["thrust_N"],  # NOMINAL = Th1 (Night-3 Phase 2)
            "tsfc_kg_per_Ns": nominal["tsfc_kg_per_Ns"],
            "isp_s": nominal["isp_s"],
            "mdot_fuel_kg_s": mdot_fuel_kg_s,
            "eta_inlet": results["eta_inlet"],
            "thrust_upper_bound_N": thrust_scenarios["Thi"]["thrust_N"],
            "thrust_lower_bound_N": thrust_scenarios["Th2"]["thrust_N"],
            "net_thrust_margin_N": net_thrust_margins_N["vs_cd0_placeholder_N"],
            "net_thrust_margins_N": net_thrust_margins_N,
            "drag_estimates": drag_estimates,
            "thrust_scenarios": thrust_scenarios,
            "note": (
                "Ramjet cruise: quasi-steady design point (Mach 2.5, "
                "10,000 m ISA), NOT a trajectory ODE (fuel depletion, "
                "drag and altitude/velocity coupling over time remain "
                "TBD). NIGHT-3 PHASE 2: thrust_N/tsfc_kg_per_Ns/isp_s/"
                "cruise_time_s/cruise_range_m at the top level now mirror "
                "Th1 (combustor-loss-only, non-ideal) as the NOMINAL "
                "design point -- changed from Th2 (real, most "
                "conservative), which was nominal prior to this phase. "
                "Thi and Th2 remain always-present explicit upper/lower "
                "thrust bounds (thrust_upper_bound_N / "
                "thrust_lower_bound_N), per the project verification gate "
                "(all three Grzywka scenarios always present, never "
                "collapsed) -- see thrust_scenarios for the full per-"
                "scenario breakdown from "
                "analyses.propulsion.combustor_nozzle_cycle."
                "GrzywkaCombustorNozzleAnalysis. mdot_fuel_kg_s is "
                "scenario-invariant (same combustor mass flow/Tt1/Tt2/"
                "fuel-air ratio for all three; only the delivered nozzle "
                "total pressure differs), so cruise_time_s/cruise_range_m "
                "come out numerically equal across scenarios at this "
                "constant-Mach design point while thrust_N/tsfc_kg_per_Ns/"
                "isp_s differ — see _scenario_cruise_point docstring. "
                "cruise_time_s = fuel_mass_kg / mdot_fuel_kg_s and "
                "cruise_range_m = V_cruise * cruise_time_s are DERIVED "
                "from the SZACOWANY 15 kg fuel_mass_kg. net_thrust_margin_N "
                "= Th1 - drag_estimate_N is a first-order margin (0-order "
                "CD0*q*Aref estimate, CD0=0.35 SZACOWANY, Aref from "
                "vehicle_config.yaml body.diameter_m); "
                "net_thrust_margins_N also reports the margin against the "
                "independent Teltik 2024 CFD drag point "
                f"({TELTIK_CFD_DRAG_N:.2f} N) -- both drags and both "
                "margins are logged together, agreement NOT forced. "
                "Reference model: L2 1-D Grzywka station cycle (1-2-21-3), "
                "single-method, MATLAB baseline unavailable, CFD delta "
                "open (see combustor_nozzle_cycle module docstring)."
            ),
        }
    except Exception as exc:  # noqa: BLE001 — deliberate graceful degradation
        stub = dict(_STUB_CRUISE_DESIGN_POINT)
        stub["note"] = (
            f"{stub['note']} Original exception: {type(exc).__name__}: {exc}"
        )
        return stub


def _write_cruise_summary_md(cruise_params: dict[str, Any], path: Path) -> None:
    """Write the Night-3 Phase 2 cruise summary to a Markdown file.

    Logs the cruise design point, the inlet recovery used, all three
    Grzywka thrust scenarios (Thi/Th1/Th2), both drag estimates, both net
    thrust margins, the fuel-based cruise time/range and the single-
    method disclosure, per the project verification gate.

    Args:
        cruise_params: The ``cruise_stage_2_ramjet`` segment parameters
            dict returned by :func:`_compute_ramjet_design_point`.
        path: Destination Markdown file path.
    """
    scenarios = cruise_params.get("thrust_scenarios", {})
    drag = cruise_params.get(
        "drag_estimates", {"cd0_placeholder_N": 0.0, "teltik_cfd_N": TELTIK_CFD_DRAG_N}
    )
    margins = cruise_params.get(
        "net_thrust_margins_N",
        {"vs_cd0_placeholder_N": 0.0, "vs_teltik_cfd_N": 0.0},
    )
    eta_inlet = cruise_params.get("eta_inlet")

    lines = [
        "# Cruise summary — Night-3 Phase 2 (Th1 nominal)",
        "",
        "Auto-generated by `workflows/ramp_staged_mission.py::main()`. Do not "
        "hand-edit; re-run the script to refresh.",
        "",
        "## Cruise design point",
        "",
        f"- Design Mach: {cruise_params.get('design_mach')}",
        f"- Cruise altitude: {cruise_params.get('cruise_altitude_m')} m ISA "
        "(source: `analyses.propulsion.inlet_performance.DESIGN_ALTITUDE_M`, "
        "a typical ramjet cruise-band assumption, TBD design decision — "
        "same altitude source the module has always used, unchanged this "
        "phase)",
        f"- eta_inlet used (Th1 scenario): {eta_inlet}",
        "",
        "## Grzywka three-thrust scenarios (Thi / Th1 / Th2)",
        "",
        "| Scenario | thrust_N | Role |",
        "|---|---|---|",
        f"| Thi | {scenarios.get('Thi', {}).get('thrust_N')} | upper bound |",
        f"| Th1 | {scenarios.get('Th1', {}).get('thrust_N')} | **NOMINAL** "
        "(Night-3 Phase 2 switch, was Th2) |",
        f"| Th2 | {scenarios.get('Th2', {}).get('thrust_N')} | lower bound "
        "(most conservative) |",
        "",
        "All three are always present under `thrust_scenarios` — the "
        "project verification gate requires never collapsing them to a "
        "single number.",
        "",
        "## Drag estimates and net thrust margin (Th1 - drag)",
        "",
        "| Drag estimate | Value [N] | Net margin vs Th1 [N] |",
        "|---|---|---|",
        f"| 0-order CD0*q*Aref (CD0=0.35 SZACOWANY) | "
        f"{drag.get('cd0_placeholder_N')} | {margins.get('vs_cd0_placeholder_N')} |",
        f"| Teltik 2024 CFD | {drag.get('teltik_cfd_N')} | "
        f"{margins.get('vs_teltik_cfd_N')} |",
        "",
        f"- q = {drag.get('q_pa')} Pa, Aref = {drag.get('aref_m2')} m^2 "
        "(pi/4*d^2, d = `vehicle_config.yaml` `body.diameter_m`, loaded "
        "via `BaseVehicleConfig`)",
        "",
        "## Fuel-based cruise time / range (Th1, nominal)",
        "",
        f"- fuel_mass_kg: {cruise_params.get('fuel_mass_kg')} (SZACOWANY)",
        f"- mdot_fuel_kg_s: {cruise_params.get('mdot_fuel_kg_s')}",
        f"- cruise_time_s: {cruise_params.get('cruise_time_s')}",
        f"- cruise_range_m: {cruise_params.get('cruise_range_m')}",
        "",
        "## Single-method disclosure",
        "",
        "- Fidelity: L2 1-D Grzywka station cycle (1-2-21-3), "
        "`analyses.propulsion.combustor_nozzle_cycle.GrzywkaCombustorNozzleAnalysis`.",
        "- MATLAB baseline (Grzywka 2022 original) is NOT vendored in this "
        "repo — unavailable for direct cross-check.",
        "- CFD delta: OPEN. The Teltik 2024 CFD drag point "
        f"({TELTIK_CFD_DRAG_N} N) and V3 cross-check are logged alongside "
        "the model results but agreement is NOT forced (see "
        "`combustor_nozzle_cycle` module docstring, `teltik_v3_cross_check`).",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Load booster burnout state, build the staged mission, and print.

    Writes the mission profile and burnout handoff state to
    ``staged_mission_profile.json`` in the same directory as this script,
    and a human-readable cruise summary to
    ``doc/ramP/cruise_summary_night3.md``.
    """
    this_dir = Path(__file__).resolve().parent
    burnout_json_path = this_dir.parent / "analyses" / "trajectory" / "burnout_state.json"
    output_json_path = this_dir / "staged_mission_profile.json"
    cruise_summary_md_path = this_dir.parent / "doc" / "ramP" / "cruise_summary_night3.md"

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

    cruise_segment = next(
        seg for seg in mission if seg.name == "cruise_stage_2_ramjet"
    )
    _write_cruise_summary_md(cruise_segment.parameters, cruise_summary_md_path)

    print("Two-stage ramjet rocket mission profile:")
    print(json.dumps(output, indent=2))
    print(f"\nWrote {output_json_path}")
    print(f"Wrote {cruise_summary_md_path}")


if __name__ == "__main__":
    main()
