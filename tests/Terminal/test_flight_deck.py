"""Tests for Flight Deck view, Available Solvers catalog, and execution pipeline.

Verifies that only repaired and verified physics solvers are exposed, ensures
strict vehicle compatibility checking, confirms pipeline staging, and verifies
that zero emojis are used anywhere in the Flight Deck UI.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from textual import events
from textual.widgets import Input, OptionList, Static, TabbedContent

from Terminal.app import YaadoApp
from Terminal.screens.flight_deck import (
    FlightDeckView,
    SolversStoreView,
    SolverTile,
)
from Terminal.solvers import (
    REPAIRED_SOLVERS,
    PipelineStage,
    SolverDescriptor,
    check_solver_compatibility,
    resolve_fins_name,
)
from Terminal.widgets import SolverParamsForm, format_stage_param_specs
from YAADO_Core.ComponentStore import RamjetEngine
from YAADO_Core.Foundation.analysis_base import FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.flight_dynamics.containers import PointMassBoostResults
from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
    PointMass3DOFBoostAnalysis,
)
from YAADO_Core.modules.powerplant.containers import HeiserPrattResults
from YAADO_Core.modules.powerplant.cycle_methods.heiser_pratt import (
    HeiserPrattCycleAnalysis,
)
from YAADO_Core.modules.stability_control.methods.barrowman.barrowman_stability import (
    BarrowmanStabilityAnalysis,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ALVRJ_TOML = REPO_ROOT / "Hangar" / "examples" / "ALVRJ" / "ALVRJ.toml"
HARPOON_TOML = REPO_ROOT / "Hangar" / "examples" / "AGM-84_HARPOON" / "AGM-84_HARPOON.toml"

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


def _ramjet_descriptor() -> SolverDescriptor:
    """Return the Heiser & Pratt ramjet cycle catalog entry."""
    return next(s for s in REPAIRED_SOLVERS if s.solver_id == "heiser_pratt_cycle")


def _assert_no_emojis(text: str) -> None:
    """Assert that a string contains no emoji characters."""
    matches = EMOJI_PATTERN.findall(text)
    assert not matches, f"Forbidden emoji(s) found in text: {matches} in '{text}'"


def test_repaired_solvers_catalog_contains_only_repaired() -> None:
    """Verify that REPAIRED_SOLVERS strictly exposes only verified solvers."""
    ids = [s.solver_id for s in REPAIRED_SOLVERS]
    assert ids == [
        "point_mass_3dof_boost",
        "heiser_pratt_cycle",
        "conical_inlet",
        "barrowman_stability",
        "barrowman_extended",
        "datcom_class_stability",
        "ackeret_fin_check",
    ], "Only repaired solvers must be in catalog"

    trajectory = REPAIRED_SOLVERS[0]
    assert trajectory.solver_cls is PointMass3DOFBoostAnalysis
    assert trajectory.fidelity == FidelityLevel.LEVEL_0
    assert trajectory.discipline == "FLIGHT DYNAMICS"

    ramjet = _ramjet_descriptor()
    assert ramjet.solver_cls is HeiserPrattCycleAnalysis
    assert ramjet.fidelity == FidelityLevel.LEVEL_2
    assert ramjet.discipline == "PROPULSION"

    stability = next(s for s in REPAIRED_SOLVERS if s.solver_id == "barrowman_stability")
    assert stability.solver_cls is BarrowmanStabilityAnalysis
    assert stability.discipline in SolversStoreView.DISCIPLINES

    # Verify no unverified methods exist
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
    """Verify SolverTile and SolversStoreView render without emojis and reflect state."""
    harpoon_path = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")
    vehicle = BaseVehicleConfig.from_toml(harpoon_path)
    desc = REPAIRED_SOLVERS[0]

    # Test SolverTile directly
    tile = SolverTile(descriptor=desc)
    tile.update_status(vehicle)
    assert tile.is_ready is True
    assert tile.is_staged is False
    prompt_str = str(tile.render())
    assert "[L0]" in prompt_str
    assert "Point-Mass 3-DOF Boost" in prompt_str
    assert "[READY]" in prompt_str
    assert "[STAGED]" not in prompt_str
    _assert_no_emojis(prompt_str)

    # Test with incompatible vehicle
    tile.update_status(None)
    assert tile.is_ready is False
    prompt_inapplicable_str = str(tile.render())
    assert "[INAPPLICABLE]" in prompt_inapplicable_str
    _assert_no_emojis(prompt_inapplicable_str)

    # Test with staged solver
    tile.update_status(vehicle, staged_ids=["point_mass_3dof_boost"])
    assert tile.is_staged is True
    assert tile.has_class("-staged")
    prompt_staged_str = str(tile.render())
    assert "[STAGED]" in prompt_staged_str
    _assert_no_emojis(prompt_staged_str)

    # Test SolversStoreView and disciplines
    store = SolversStoreView(REPAIRED_SOLVERS, vehicle)
    assert len(store.DISCIPLINES) > 0
    assert "FLIGHT DYNAMICS" in store.DISCIPLINES


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


def test_flight_deck_interactive_navigation_and_staging() -> None:
    """Verify interactive focus, 'a' key, Enter key, double-click, and styling via pilot."""
    import asyncio

    async def _test() -> None:
        app = YaadoApp()
        async with app.run_test(size=(120, 36)) as pilot:
            # Confirm startup tab is main
            tabs = app.query_one(TabbedContent)
            assert tabs.active == "main"

            # Switch to Flight Deck tab via 'f' key
            await pilot.press("f")
            await pilot.pause(0.2)
            assert tabs.active == "flight-deck"

            fd = app.query_one(FlightDeckView)
            tile = app.query_one(SolverTile)
            assert tile is not None

            # Initially, tile is not focused and Enter does NOT stage
            assert tile.has_focus is False
            await pilot.press("enter")
            await pilot.pause(0.1)
            assert len(fd.pipeline) == 0

            # Clicking the tile directly focuses it
            await pilot.click(tile)
            await pilot.pause(0.1)
            assert tile.has_focus is True
            assert "[L0]" in str(tile.render())
            assert "Point-Mass 3-DOF Boost" in str(tile.render())
            _assert_no_emojis(str(tile.render()))

            # Key 'a' adds to pipeline
            await pilot.press("a")
            await pilot.pause(0.1)
            assert len(fd.pipeline) == 1
            assert tile.is_staged is True
            assert tile.has_class("-staged")
            assert "[STAGED]" in str(tile.render())
            _assert_no_emojis(str(tile.render()))

            # Key 'enter' adds to pipeline again
            await pilot.press("enter")
            await pilot.pause(0.1)
            assert len(fd.pipeline) == 2

            # Key 'c' clears pipeline
            await pilot.press("c")
            await pilot.pause(0.1)
            assert len(fd.pipeline) == 0
            assert tile.is_staged is False
            assert not tile.has_class("-staged")
            assert "[STAGED]" not in str(tile.render())

            # Double-click event adds to pipeline
            click_evt = events.Click(
                tile, 0, 0, 0, 0, button=1, shift=False, meta=False, ctrl=False, chain=2
            )
            tile.on_click(click_evt)
            await pilot.pause(0.1)
            assert len(fd.pipeline) == 1
            assert tile.is_staged is True
            assert tile.has_class("-staged")

    asyncio.run(_test())


def test_flight_deck_results_vertical_scroll_and_persistence() -> None:
    """Verify that results card contains VerticalScroll and selection persists across hover."""
    import asyncio

    from textual.app import App, ComposeResult
    from textual.containers import ScrollableContainer

    from Terminal.widgets import FlightLogsTree

    class TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield FlightDeckView(id="flightdeck")

    async def _test() -> None:
        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)
            fd = app.query_one("#flightdeck", FlightDeckView)
            tree = app.query_one("#flightdeck-runs-tree", FlightLogsTree)

            # 1. Verify results scroll container exists
            scroll = fd.query_one("#flightdeck-results-scroll", ScrollableContainer)
            assert scroll is not None

            # 2. Test selection persistence across hover
            sample_run = Path("FlightLogs/ALVRJ/point_mass_3dof_boost_2026-09-20_195902")
            if not sample_run.is_dir():
                pytest.skip("Historical run directory not found")

            log_file = sample_run / "execution.log"
            csv_file = sample_run / "summary.csv"

            # User selects log_file
            fd._on_flightlog_selected(FlightLogsTree.FlightLogSelected(tree, log_file))
            assert fd._selected_flightlog_path == log_file
            results_card = fd.query_one("#flightdeck-results-card")
            assert results_card.border_title == f"File: {log_file.name}"

            # User hovers over csv_file
            fd._on_flightlog_highlighted(FlightLogsTree.FlightLogHighlighted(tree, csv_file))
            assert results_card.border_title == f"File: {csv_file.name}"
            # Selected path remains log_file
            assert fd._selected_flightlog_path == log_file

            # Mouse leaves hover (posts None) -> restores selected log_file
            fd._on_flightlog_highlighted(FlightLogsTree.FlightLogHighlighted(tree, None))
            assert results_card.border_title == f"File: {log_file.name}"

            # Mouse leaves runs card completely -> restores selected log_file
            fd._on_runs_card_leave()
            assert results_card.border_title == f"File: {log_file.name}"

            # Switching back to inspector clears selected flightlog
            fd.action_show_inspector()
            assert fd._selected_flightlog_path is None
            assert results_card.border_title == "Solver Inspector"

    asyncio.run(_test())


def test_flight_deck_run_solver_generates_all_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that run_solver generates figures, artifacts, results.json, and summary.csv."""
    from YAADO_Core.Foundation.flight_logger import FlightLogger

    harpoon_path = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")
    vehicle = BaseVehicleConfig.from_toml(harpoon_path)

    # Monkeypatch FlightLogger so all disk writes go to tmp_path (FlightLogs/ is not touched)
    orig_init = FlightLogger.__init__

    def patched_init(
        self: FlightLogger,
        vehicle_name: str,
        analysis_name: str,
        enabled: bool = True,
        log_to_console: bool = False,
        show_figures: bool = False,
        log_level: int = 20,
    ) -> None:
        # Initialize with enabled=False so no directories are created in FlightLogs/
        orig_init(
            self,
            vehicle_name,
            analysis_name,
            enabled=False,
            log_to_console=log_to_console,
            show_figures=show_figures,
            log_level=log_level,
        )
        self.enabled = enabled
        self.output_dir = tmp_path / vehicle_name / self.run_folder_name
        self.figures_dir = self.output_dir / "figures"
        self.artifacts_dir = self.output_dir / "artifacts"
        self.log_file_path = self.output_dir / "execution.log"
        self._setup_directories()
        self._setup_logging()

    monkeypatch.setattr(FlightLogger, "__init__", patched_init)

    fd = FlightDeckView(active_vehicle=vehicle, active_vehicle_path=harpoon_path)
    desc = REPAIRED_SOLVERS[0]

    results = fd.run_solver(desc, enable_logging=True)
    assert results is not None
    assert isinstance(results, PointMassBoostResults)

    # Find the output directory created in tmp_path
    vehicle_output_dirs = list((tmp_path / vehicle.name).iterdir())
    assert len(vehicle_output_dirs) == 1
    run_dir = vehicle_output_dirs[0]

    # Verify all 6 artifacts were generated
    assert (run_dir / "results.json").is_file(), "results.json must be generated"
    assert (run_dir / "summary.csv").is_file(), "summary.csv must be generated"
    assert (run_dir / "execution.log").is_file(), "execution.log must be generated"
    assert (run_dir / "figures" / "boost_phase.png").is_file(), "boost_phase.png must be generated"
    assert (
        run_dir / "figures" / "launch_angle_sweep.png"
    ).is_file(), "launch_angle_sweep.png must be generated"
    assert (
        run_dir / "artifacts" / "launch_angle_sweep.csv"
    ).is_file(), "launch_angle_sweep.csv must be generated"


def test_aerospace_symbol_formatting() -> None:
    """Verify that stage parameters format using compact aerospace symbols and no emojis."""
    desc = REPAIRED_SOLVERS[0]
    stage = PipelineStage(descriptor=desc, params=dict(desc.default_params))
    badge = format_stage_param_specs(stage)

    # Check key symbols
    assert "γ₀=83°" in badge
    assert "h₀=100m" in badge
    assert "h_g=0m" in badge
    assert "t_max=300s" in badge
    assert "stop_burnout=True" in badge
    _assert_no_emojis(badge)

    # Change params and verify symbol formatting updates
    stage.params["launch_angle_deg"] = 75.0
    stage.params["altitude_m"] = 250.0
    stage.params["stop_at_burnout"] = False
    badge_updated = format_stage_param_specs(stage)
    assert "γ₀=75°" in badge_updated
    assert "h₀=250m" in badge_updated
    assert "stop_burnout=False" in badge_updated
    _assert_no_emojis(badge_updated)


def test_flight_deck_pipeline_stage_symbols_display() -> None:
    """Verify that staged pipeline options display compact aerospace symbols instead of words."""
    import asyncio

    from textual.app import App, ComposeResult

    harpoon_path = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")
    vehicle = BaseVehicleConfig.from_toml(harpoon_path)

    class TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield FlightDeckView(active_vehicle=vehicle, id="flightdeck")

    async def _test() -> None:
        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)
            fd = app.query_one("#flightdeck", FlightDeckView)
            desc = REPAIRED_SOLVERS[0]

            # Stage solver
            fd.stage_solver(desc)
            await pilot.pause(0.1)

            pipeline_list = fd.query_one("#flightdeck-pipeline-list", OptionList)
            assert pipeline_list.option_count == 1
            option = pipeline_list.get_option_at_index(0)
            prompt_str = str(option.prompt)

            # Assert aerospace symbols are present in prompt
            assert "γ₀=83°" in prompt_str
            assert "h₀=100m" in prompt_str
            assert "stop_burnout=True" in prompt_str
            assert "[READY]" in prompt_str
            _assert_no_emojis(prompt_str)

            # Update a parameter on stage 1 via ParamChanged event
            form = fd.query_one("#flightdeck-params-form", SolverParamsForm)
            fd._on_param_changed(
                SolverParamsForm.ParamChanged(
                    form=form,
                    name="launch_angle_deg",
                    value=72.5,
                    is_valid=True,
                    stage_index=1,
                )
            )
            await pilot.pause(0.1)

            # Option prompt in pipeline list should now reflect tuned symbol
            updated_option = pipeline_list.get_option_at_index(0)
            updated_prompt_str = str(updated_option.prompt)
            assert "γ₀=72.5°" in updated_prompt_str
            assert "stop_burnout=True" in updated_prompt_str
            _assert_no_emojis(updated_prompt_str)

    asyncio.run(_test())


def test_flight_deck_run_solver_with_custom_parameters() -> None:
    """Verify run_solver executes with custom parameter overrides."""
    harpoon_path = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")
    vehicle = BaseVehicleConfig.from_toml(harpoon_path)

    fd = FlightDeckView(active_vehicle=vehicle, active_vehicle_path=harpoon_path)
    desc = REPAIRED_SOLVERS[0]

    custom_params = {
        "launch_angle_deg": 45.0,
        "altitude_m": 500.0,
        "ground_altitude_m": 0.0,
        "t_max_s": 50.0,
        "stop_at_burnout": True,
    }
    results = fd.run_solver(desc, enable_logging=False, params=custom_params)
    assert results is not None
    assert isinstance(results, PointMassBoostResults)
    assert results.burnout_mach > 0.8


def test_flight_deck_solver_form_scrollable() -> None:
    """Verify that clicking on a solver loads its requirements and the form is vertically scrollable."""
    import asyncio

    from textual.app import App, ComposeResult
    from textual.widgets import Static

    harpoon_path = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")
    vehicle = BaseVehicleConfig.from_toml(harpoon_path)

    class TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield FlightDeckView(active_vehicle=vehicle, id="flightdeck")

    async def _test() -> None:
        app = TestApp()
        async with app.run_test(size=(120, 24)) as pilot:
            await pilot.pause(0.2)
            fd = app.query_one("#flightdeck", FlightDeckView)
            tile = fd.query_one(SolverTile)

            # Click on solver tile
            await pilot.click(tile)
            await pilot.pause(0.2)

            form = fd.query_one("#flightdeck-params-form", SolverParamsForm)
            assert form is not None
            assert not form.has_class("-hidden")

            # Check that header contains requirements
            header = form.query_one("#solver-form-header", Static)
            header_text = str(header.render())
            assert "booster motor" in header_text.lower() and "solidmotor" in header_text.lower()

            # Verify that form content overflows visible height and is scrollable
            assert form.virtual_size.height > form.size.height
            assert form.scroll_y == 0

            # Scroll down and verify scroll_y increases
            form.scroll_end(animate=False)
            await pilot.pause(0.1)
            assert form.scroll_y > 0

            # Scroll back home
            form.scroll_home(animate=False)
            await pilot.pause(0.1)
            assert form.scroll_y == 0

    asyncio.run(_test())


def test_ramjet_compatibility_follows_the_vehicle_propulsion() -> None:
    """The ramjet cycle is ready only for a vehicle with exactly one ramjet."""
    desc = _ramjet_descriptor()

    is_ready, msg = check_solver_compatibility(desc, BaseVehicleConfig.from_toml(ALVRJ_TOML))
    assert is_ready
    assert "sustainer" in msg
    _assert_no_emojis(msg)

    is_ready, msg = check_solver_compatibility(desc, BaseVehicleConfig.from_toml(HARPOON_TOML))
    assert not is_ready
    assert "Missing ramjet" in msg

    twin = BaseVehicleConfig(
        name="twin",
        propulsion={
            "left": RamjetEngine(design_mach=2.5, combustor_temp=2000.0, nozzle_area_ratio=2.0),
            "right": RamjetEngine(design_mach=2.5, combustor_temp=2000.0, nozzle_area_ratio=2.0),
        },
    )
    is_ready, msg = check_solver_compatibility(desc, twin)
    assert not is_ready
    assert "left" in msg and "right" in msg


def test_ramjet_run_uses_toml_values_when_parameters_are_blank() -> None:
    """Default parameters leave Mach, Tt4 and mass flow to the vehicle."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_TOML)
    fd = FlightDeckView(active_vehicle=vehicle, active_vehicle_path=ALVRJ_TOML)

    results = fd.run_solver(_ramjet_descriptor(), enable_logging=False)

    assert isinstance(results, HeiserPrattResults)
    assert results.inputs.mach == 2.6
    assert results.inputs.tt4 == 2150.0
    assert results.thrust_real > 10000.0


def test_ramjet_run_applies_custom_parameters() -> None:
    """Tuned parameters override the vehicle's design point."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_TOML)
    fd = FlightDeckView(active_vehicle=vehicle, active_vehicle_path=ALVRJ_TOML)
    desc = _ramjet_descriptor()

    params = {**desc.default_params, "mach": 3.0, "altitude_m": 12000.0, "eta_inlet": 0.7}
    results = fd.run_solver(desc, enable_logging=False, params=params)

    assert isinstance(results, HeiserPrattResults)
    assert results.inputs.mach == 3.0
    assert results.inputs.altitude == 12000.0
    assert results.inputs.eta_inlet == 0.7


def test_ramjet_without_throat_needs_a_mass_flow_from_the_form() -> None:
    """A throatless ramjet is runnable, but fails clearly until the flow is set."""
    engine = RamjetEngine(design_mach=2.5, combustor_temp=2000.0, nozzle_area_ratio=2.0)
    vehicle = BaseVehicleConfig(name="no_throat", propulsion={"ramjet": engine})
    fd = FlightDeckView(active_vehicle=vehicle)
    desc = _ramjet_descriptor()

    is_ready, msg = check_solver_compatibility(desc, vehicle)
    assert is_ready
    assert "air mass flow" in msg

    assert fd.run_solver(desc, enable_logging=False) is None

    params = {**desc.default_params, "mdot_air": 12.0}
    results = fd.run_solver(desc, enable_logging=False, params=params)
    assert isinstance(results, HeiserPrattResults)
    assert results.mdot_air == 12.0


def test_ramjet_stage_badge_skips_blank_parameters() -> None:
    """Parameters left to the vehicle must not show as 'None' in the pipeline."""
    desc = _ramjet_descriptor()
    stage = PipelineStage(descriptor=desc, params=dict(desc.default_params))

    badge = format_stage_param_specs(stage)
    assert "None" not in badge
    assert "η_i" not in badge

    stage.params["mach"] = 3.0
    stage.params["eta_inlet"] = 0.8
    assert "M=3" in format_stage_param_specs(stage)
    assert "η_i=0.8" in format_stage_param_specs(stage)
    _assert_no_emojis(format_stage_param_specs(stage))


def test_completion_message_reports_the_solver_headline() -> None:
    """The run notification must not report a trajectory metric for a ramjet."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_TOML)
    fd = FlightDeckView(active_vehicle=vehicle)
    desc = _ramjet_descriptor()
    results = fd.run_solver(desc, enable_logging=False)
    assert results is not None

    message = fd._completion_message(desc, results)
    assert message.startswith("Completed Heiser & Pratt Ramjet Cycle (Net Thrust: ")
    assert message.endswith(" N)")
    assert "Mach" not in message


def test_ramjet_full_workflow_through_the_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Select, tune, run and stage the ramjet cycle with the real key bindings."""
    import asyncio

    monkeypatch.chdir(tmp_path)

    async def _test() -> None:
        app = YaadoApp()
        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.press("f")
            await pilot.pause(0.2)
            fd = app.query_one(FlightDeckView)
            fd.set_active_vehicle(BaseVehicleConfig.from_toml(ALVRJ_TOML), ALVRJ_TOML)
            await pilot.pause(0.2)

            tile = fd.query_one("#tile-solver-heiser_pratt_cycle", SolverTile)
            await pilot.click(tile)
            await pilot.pause(0.3)
            form = fd.query_one("#flightdeck-params-form", SolverParamsForm)
            assert form.query_one("#param-inp-mach", Input).value == ""
            assert form.query_one("#param-inp-mach", Input).placeholder == "TOML"

            # A symbol such as [M] must not be read as Rich markup
            labels = [str(label.render()) for label in form.query(".form-label").results(Static)]
            assert "Flight Mach [M]:" in labels
            assert "Fuel Heating Value [LHV]:" in labels

            # Tune through the form, then run with the 'r' binding
            form.query_one("#param-inp-mach", Input).value = "3.0"
            await pilot.pause(0.1)
            await pilot.press("r")
            await pilot.pause(0.3)
            content = str(fd.query_one("#flightdeck-results-content", Static).render())
            assert "Net Thrust" in content
            assert " kN)" in content
            assert "Fuel-Air Ratio" in content
            assert "Placeholder values used for: inlet_recovery" in content

            # Clearing the input returns the value to the vehicle
            await pilot.press("b")
            await pilot.pause(0.2)
            form.query_one("#param-inp-mach", Input).value = ""
            await pilot.pause(0.1)
            assert fd._active_params["mach"] is None

            # A mixed pipeline runs both solvers with their own parameters
            await pilot.press("a")
            await pilot.pause(0.1)
            await pilot.click(fd.query_one("#tile-solver-point_mass_3dof_boost", SolverTile))
            await pilot.pause(0.3)
            await pilot.press("a")
            await pilot.pause(0.1)
            assert [s.descriptor.solver_id for s in fd.pipeline] == [
                "heiser_pratt_cycle",
                "point_mass_3dof_boost",
            ]
            pipeline_list = fd.query_one("#flightdeck-pipeline-list", OptionList)
            assert "[READY]" in str(pipeline_list.get_option_at_index(0).prompt)
            await pilot.press("x")
            await pilot.pause(1.0)

    asyncio.run(_test())

    runs = sorted(p.parent.name for p in (tmp_path / "FlightLogs" / "ALVRJ").glob("*/results.json"))
    assert sum(name.startswith("heiser_pratt_cycle_") for name in runs) >= 2
    assert sum(name.startswith("point_mass_3dof_boost_") for name in runs) == 1


def test_form_keeps_controls_when_highlight_events_arrive_together() -> None:
    """A click sends focus and click highlights at once; the form must still fill.

    Cancelling a remount for the second event used to leave the form empty.
    """
    import asyncio

    from textual.app import App, ComposeResult

    vehicle = BaseVehicleConfig.from_toml(ALVRJ_TOML)

    class TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield FlightDeckView(active_vehicle=vehicle, id="flightdeck")

    async def _test() -> None:
        app = TestApp()
        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.pause(0.2)
            fd = app.query_one("#flightdeck", FlightDeckView)
            form = fd.query_one("#flightdeck-params-form", SolverParamsForm)
            tiles = [fd.query_one(f"#tile-solver-{s.solver_id}", SolverTile) for s in REPAIRED_SOLVERS]

            for tile in (tiles[1], tiles[0], tiles[1]):
                tile.focus()
                tile.post_message(
                    SolverTile.SolverHighlighted(tile.descriptor, tile.is_ready, tile.status_msg)
                )
                await pilot.pause(0.3)
                assert form.descriptor is tile.descriptor
                assert len(form.query("#solver-form-header")) == 1
                numeric = [p for p in tile.descriptor.parameters if p.param_type is not bool]
                assert len(form.query(Input)) == len(numeric)
                assert set(fd._active_params) == {p.name for p in tile.descriptor.parameters}

            # Rapid switching must settle on the last solver without hanging
            for index in range(30):
                tiles[index % 2].focus()
                await asyncio.sleep(0)
            await pilot.pause(0.5)
            assert form.descriptor is tiles[1].descriptor
            assert len(form.query("#solver-form-header")) == 1

    asyncio.run(_test())


def test_optional_parameter_input_validation() -> None:
    """Blank is valid only for optional parameters; bounds still apply to typed values."""
    import asyncio

    from textual.app import App, ComposeResult

    vehicle = BaseVehicleConfig.from_toml(ALVRJ_TOML)

    class TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield FlightDeckView(active_vehicle=vehicle, id="flightdeck")

    async def _test() -> None:
        app = TestApp()
        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.pause(0.2)
            fd = app.query_one("#flightdeck", FlightDeckView)
            fd.query_one("#tile-solver-heiser_pratt_cycle", SolverTile).focus()
            await pilot.pause(0.3)
            form = fd.query_one("#flightdeck-params-form", SolverParamsForm)

            mach = form.query_one("#param-inp-mach", Input)
            mach.value = "0.5"
            await pilot.pause(0.1)
            assert mach.has_class("-invalid")
            assert fd._active_params["mach"] is None

            mach.value = ""
            await pilot.pause(0.1)
            assert not mach.has_class("-invalid")
            assert fd._active_params["mach"] is None

            altitude = form.query_one("#param-inp-altitude_m", Input)
            altitude.value = ""
            await pilot.pause(0.1)
            assert altitude.has_class("-invalid")
            assert fd._active_params["altitude_m"] == 10000.0

    asyncio.run(_test())


def test_stability_run_through_the_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Select, tune and run the Barrowman solver with the real key bindings."""
    import asyncio

    monkeypatch.chdir(tmp_path)

    async def _test() -> None:
        app = YaadoApp()
        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.press("f")
            await pilot.pause(0.2)
            fd = app.query_one(FlightDeckView)
            fd.set_active_vehicle(BaseVehicleConfig.from_toml(HARPOON_TOML), HARPOON_TOML)
            await pilot.pause(0.2)

            tile = fd.query_one("#tile-solver-barrowman_stability", SolverTile)
            await pilot.click(tile)
            await pilot.pause(0.3)
            form = fd.query_one("#flightdeck-params-form", SolverParamsForm)
            assert form.query_one("#param-inp-mach", Input).value == "0.3"
            assert form.query_one("#param-inp-cg_from_nose", Input).placeholder == "TOML"

            form.query_one("#param-inp-cg_from_nose", Input).value = "2.2"
            await pilot.pause(0.1)
            await pilot.press("r")
            await pilot.pause(0.3)
            content = str(fd.query_one("#flightdeck-results-content", Static).render())
            assert "Static Margin" in content
            assert " cal" in content
            assert "below the required" in content
            assert fd._active_params["cg_from_nose"] == 2.2

    asyncio.run(_test())


def test_ackeret_run_through_the_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the Ackeret check from its tile and see both methods in the results."""
    import asyncio

    monkeypatch.chdir(tmp_path)

    async def _test() -> None:
        app = YaadoApp()
        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.press("f")
            await pilot.pause(0.2)
            fd = app.query_one(FlightDeckView)
            fd.set_active_vehicle(BaseVehicleConfig.from_toml(ALVRJ_TOML), ALVRJ_TOML)
            await pilot.pause(0.2)

            tile = fd.query_one("#tile-solver-ackeret_fin_check", SolverTile)
            tile.scroll_visible(animate=False)
            await pilot.pause(0.1)
            await pilot.click(tile)
            await pilot.pause(0.3)
            form = fd.query_one("#flightdeck-params-form", SolverParamsForm)
            form.query_one("#param-inp-mach", Input).value = "2.5"
            form.query_one("#param-inp-cg_from_nose", Input).value = "4.0"
            await pilot.pause(0.1)
            await pilot.press("r")
            await pilot.pause(0.3)
            content = str(fd.query_one("#flightdeck-results-content", Static).render())
            assert "Static Margin (Ackeret)" in content
            assert "Static Margin (Barrowman)" in content
            assert "Statically unstable" in content

    asyncio.run(_test())


def test_datcom_run_through_the_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the DATCOM-class solver from its tile with the default supersonic Mach."""
    import asyncio

    monkeypatch.chdir(tmp_path)

    async def _test() -> None:
        app = YaadoApp()
        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.press("f")
            await pilot.pause(0.2)
            fd = app.query_one(FlightDeckView)
            fd.set_active_vehicle(BaseVehicleConfig.from_toml(ALVRJ_TOML), ALVRJ_TOML)
            await pilot.pause(0.2)

            tile = fd.query_one("#tile-solver-datcom_class_stability", SolverTile)
            tile.scroll_visible(animate=False)
            await pilot.pause(0.1)
            await pilot.click(tile)
            await pilot.pause(0.3)
            form = fd.query_one("#flightdeck-params-form", SolverParamsForm)
            assert form.query_one("#param-inp-mach", Input).value == "2.0"
            await pilot.press("r")
            await pilot.pause(0.3)
            content = str(fd.query_one("#flightdeck-results-content", Static).render())
            assert "Static Margin" in content
            assert "Margin Above Required" in content

    asyncio.run(_test())


def test_extended_run_through_the_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the extended Barrowman solver from its tile and see the fin sizing."""
    import asyncio

    monkeypatch.chdir(tmp_path)

    async def _test() -> None:
        app = YaadoApp()
        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.press("f")
            await pilot.pause(0.2)
            fd = app.query_one(FlightDeckView)
            fd.set_active_vehicle(BaseVehicleConfig.from_toml(HARPOON_TOML), HARPOON_TOML)
            await pilot.pause(0.2)

            tile = fd.query_one("#tile-solver-barrowman_extended", SolverTile)
            tile.scroll_visible(animate=False)
            await pilot.pause(0.1)
            await pilot.click(tile)
            await pilot.pause(0.3)
            form = fd.query_one("#flightdeck-params-form", SolverParamsForm)
            form.query_one("#param-inp-alpha_deg", Input).value = "8"
            await pilot.pause(0.1)
            await pilot.press("r")
            await pilot.pause(0.3)
            content = str(fd.query_one("#flightdeck-results-content", Static).render())
            assert "Static Margin (with body lift)" in content
            assert "Tail Fin Span for Required Margin" in content

    asyncio.run(_test())


def test_conical_inlet_run_through_the_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the spike angle in the form, run the inlet and see its recovery."""
    import asyncio

    monkeypatch.chdir(tmp_path)

    async def _test() -> None:
        app = YaadoApp()
        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.press("f")
            await pilot.pause(0.2)
            fd = app.query_one(FlightDeckView)
            fd.set_active_vehicle(BaseVehicleConfig.from_toml(ALVRJ_TOML), ALVRJ_TOML)
            await pilot.pause(0.2)

            tile = fd.query_one("#tile-solver-conical_inlet", SolverTile)
            tile.scroll_visible(animate=False)
            await pilot.pause(0.1)
            await pilot.click(tile)
            await pilot.pause(0.3)
            form = fd.query_one("#flightdeck-params-form", SolverParamsForm)
            assert form.query_one("#param-inp-cone_half_angle_deg", Input).placeholder == "TOML"
            form.query_one("#param-inp-cone_half_angle_deg", Input).value = "21"
            await pilot.pause(0.1)
            await pilot.press("r")
            await pilot.pause(0.5)
            content = str(fd.query_one("#flightdeck-results-content", Static).render())
            assert "Total-Pressure Recovery" in content
            assert "Conical Shock Angle" in content

    asyncio.run(_test())
