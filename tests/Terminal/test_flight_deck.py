"""Tests for Flight Deck view, Available Solvers catalog, and execution pipeline.

Verifies that only repaired and verified physics solvers are exposed, ensures
strict vehicle compatibility checking, confirms pipeline staging, and verifies
that zero emojis are used anywhere in the Flight Deck UI.
"""

from __future__ import annotations

import re
from pathlib import Path

from Terminal.screens.flight_deck import (
    REPAIRED_SOLVERS,
    AvailableSolversList,
    FlightDeckView,
    check_solver_compatibility,
    resolve_fins_name,
)
from YAADO_Core.Foundation.analysis_base import FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.flight_dynamics.containers import PointMassBoostResults
from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
    PointMass3DOFBoostAnalysis,
)

# Regex matching common emoji unicode ranges
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # Emoticons
    "\U0001F300-\U0001F5FF"  # Misc Symbols and Pictographs
    "\U0001F680-\U0001F6FF"  # Transport and Map Symbols
    "\U0001F700-\U0001F77F"  # Alchemical Symbols
    "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
    "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
    "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
    "\U0001FA00-\U0001FA6F"  # Chess Symbols
    "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
    "\U00002702-\U000027B0"  # Dingbats
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)


def _assert_no_emojis(text: str) -> None:
    """Assert that a string contains no emoji characters."""
    matches = EMOJI_PATTERN.findall(text)
    assert not matches, f"Forbidden emoji(s) found in text: {matches} in '{text}'"


def test_repaired_solvers_catalog_contains_only_repaired() -> None:
    """Verify that REPAIRED_SOLVERS strictly exposes only verified solvers."""
    assert len(REPAIRED_SOLVERS) == 1, "Only repaired solvers must be in catalog"
    single_solver = REPAIRED_SOLVERS[0]

    assert single_solver.solver_id == "point_mass_3dof_boost"
    assert single_solver.solver_cls is PointMass3DOFBoostAnalysis
    assert single_solver.fidelity == FidelityLevel.LEVEL_0
    assert single_solver.discipline == "FLIGHT DYNAMICS"

    # Verify no unverified methods exist
    ids = [s.solver_id for s in REPAIRED_SOLVERS]
    for unverified in ("avl", "xfoil", "su2", "ramjet", "openvsp", "datcom"):
        assert unverified not in ids, f"Unverified solver '{unverified}' must not be listed"


def test_no_emojis_in_repaired_solver_descriptors() -> None:
    """Verify that all strings in REPAIRED_SOLVERS descriptors are free of emojis."""
    for desc in REPAIRED_SOLVERS:
        _assert_no_emojis(desc.name)
        _assert_no_emojis(desc.discipline)
        _assert_no_emojis(desc.description)
        _assert_no_emojis(desc.required_components_desc)
        for _, unit, title in desc.headline_outputs:
            _assert_no_emojis(unit)
            _assert_no_emojis(title)


def test_check_solver_compatibility_none_vehicle() -> None:
    """Verify compatibility evaluation when no vehicle is loaded."""
    desc = REPAIRED_SOLVERS[0]
    is_ready, msg = check_solver_compatibility(desc, None)
    assert not is_ready
    assert "No active vehicle loaded" in msg
    _assert_no_emojis(msg)


def test_check_solver_compatibility_empty_vehicle() -> None:
    """Verify compatibility evaluation when vehicle is missing required components."""
    desc = REPAIRED_SOLVERS[0]
    harpoon_path = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")
    vehicle = BaseVehicleConfig.from_toml(harpoon_path)

    # Empty vehicle
    empty_vehicle = BaseVehicleConfig(name="EmptyRocket")
    is_ready, msg = check_solver_compatibility(desc, empty_vehicle)
    assert not is_ready
    assert "booster propulsion" in msg

    # Missing booster propulsion
    no_prop = BaseVehicleConfig.from_toml(harpoon_path)
    no_prop.propulsion.clear()
    is_ready, msg = check_solver_compatibility(desc, no_prop)
    assert not is_ready
    assert "booster propulsion" in msg

    # Missing body
    no_body = BaseVehicleConfig.from_toml(harpoon_path)
    no_body.bodies.clear()
    is_ready, msg = check_solver_compatibility(desc, no_body)
    assert not is_ready
    assert "fuselage/body" in msg

    # Missing total_mass
    no_mass = BaseVehicleConfig.from_toml(harpoon_path)
    no_mass.mass_properties = None
    is_ready, msg = check_solver_compatibility(desc, no_mass)
    assert not is_ready
    assert "positive total_mass" in msg

    # Original vehicle is ready
    is_ready, msg = check_solver_compatibility(desc, vehicle)
    assert is_ready
    assert "Ready" in msg
    _assert_no_emojis(msg)


def test_check_solver_compatibility_harpoon_example() -> None:
    """Verify compatibility with AGM-84 Harpoon reference configuration."""
    harpoon_path = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")
    vehicle = BaseVehicleConfig.from_toml(harpoon_path)

    desc = REPAIRED_SOLVERS[0]
    is_ready, msg = check_solver_compatibility(desc, vehicle)
    assert is_ready
    assert "Ready" in msg
    _assert_no_emojis(msg)


def test_check_solver_compatibility_alvrj_example() -> None:
    """Verify compatibility with ALVRJ reference configuration."""
    alvrj_path = Path("Hangar/examples/ALVRJ/ALVRJ.toml")
    vehicle = BaseVehicleConfig.from_toml(alvrj_path)

    desc = REPAIRED_SOLVERS[0]
    is_ready, msg = check_solver_compatibility(desc, vehicle)
    assert is_ready
    assert "Ready" in msg
    _assert_no_emojis(msg)


def test_resolve_fins_name_candidates() -> None:
    """Verify resolve_fins_name accurately selects aerodynamic fin components."""
    harpoon_path = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")
    vehicle = BaseVehicleConfig.from_toml(harpoon_path)

    # In Harpoon, candidate fins are ['mid_body_wings', 'aft_control_fins', 'planar_equivalent']
    # 'aft_control_fins' contains 'fin'
    assert resolve_fins_name(vehicle) == "aft_control_fins"

    # Vehicle with no aero surfaces
    vehicle.aero_surfaces.clear()
    assert resolve_fins_name(vehicle) is None


def test_available_solvers_list_population_and_labels() -> None:
    """Verify AvailableSolversList populates options without emojis."""
    solvers_list = AvailableSolversList()
    harpoon_path = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")
    vehicle = BaseVehicleConfig.from_toml(harpoon_path)

    solvers_list.populate(REPAIRED_SOLVERS, vehicle)
    assert solvers_list.option_count == len(REPAIRED_SOLVERS)

    opt = solvers_list.get_option_at_index(0)
    prompt_str = str(opt.prompt)
    assert "[L0]" in prompt_str
    assert "Point-Mass 3-DOF Boost" in prompt_str
    assert "[READY]" in prompt_str
    _assert_no_emojis(prompt_str)

    # Test with incompatible vehicle
    solvers_list.populate(REPAIRED_SOLVERS, None)
    opt_inapplicable = solvers_list.get_option_at_index(0)
    prompt_inapplicable_str = str(opt_inapplicable.prompt)
    assert "[INAPPLICABLE]" in prompt_inapplicable_str
    _assert_no_emojis(prompt_inapplicable_str)


def test_flight_deck_pipeline_staging_and_clear() -> None:
    """Verify pipeline staging, stage count, and clearing."""
    fd = FlightDeckView()
    desc = REPAIRED_SOLVERS[0]

    assert len(fd.pipeline) == 0
    fd.stage_solver(desc)
    assert len(fd.pipeline) == 1
    assert fd.pipeline[0].descriptor is desc

    fd.stage_solver(desc)
    assert len(fd.pipeline) == 2

    fd.action_clear_pipeline()
    assert len(fd.pipeline) == 0


def test_flight_deck_run_solver_execution() -> None:
    """Verify solver execution via run_solver with enable_logging=False."""
    harpoon_path = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")
    vehicle = BaseVehicleConfig.from_toml(harpoon_path)

    fd = FlightDeckView(active_vehicle=vehicle, active_vehicle_path=harpoon_path)
    desc = REPAIRED_SOLVERS[0]

    # Explicitly run with enable_logging=False so no FlightLogs/ files are created
    results = fd.run_solver(desc, enable_logging=False)
    assert results is not None
    assert isinstance(results, PointMassBoostResults)
    assert results.burnout_mach > 0.8
    assert results.burnout_velocity > 200.0
    assert results.nominal_burn_time > 0.0


def test_number_formatting() -> None:
    """Verify formatting of numerical output telemetry."""
    assert FlightDeckView._format_number(0.0) == "0"
    assert FlightDeckView._format_number(125000.0, "Pa") == "125.00"
    assert FlightDeckView._format_number(285.456, "m/s") == "285.5"
    assert FlightDeckView._format_number(0.8734, "-") == "0.873"
    assert FlightDeckView._format_number("text") == "text"
