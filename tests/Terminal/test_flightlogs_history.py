"""Tests for FlightLogs history tree, contextual preview renderers, and system openers.

Verifies that historical simulation runs correctly display their internal files
(results.json, execution.log, summary.csv, figures, artifacts), tests external
viewer launchers, and confirms zero emojis are generated anywhere in the preview UI.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text

from Terminal.app import YaadoApp
from Terminal.system_utils import open_folder_in_system, open_path_in_system
from Terminal.widgets import FlightLogsTree, render_flightlog_preview

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U0001F1E0-\U0001F251"
    "]+",
    flags=re.UNICODE,
)


def _assert_no_emojis(obj: RenderableType | str) -> None:
    """Verify that a Rich renderable or string contains zero emoji characters."""
    if isinstance(obj, str):
        text = obj
    elif isinstance(obj, Text):
        text = obj.plain
    elif isinstance(obj, Group):
        pieces: list[str] = []
        for child in obj.renderables:
            if isinstance(child, Text):
                pieces.append(child.plain)
            else:
                pieces.append(str(child))
        text = " ".join(pieces)
    elif isinstance(obj, Table):
        caption_text = str(obj.caption) if obj.caption is not None else ""
        text = f"{obj.title or ''} {caption_text} " + " ".join(str(col.header) for col in obj.columns)
    else:
        text = str(obj)

    matches = EMOJI_PATTERN.findall(text)
    assert not matches, f"Forbidden emoji(s) found in renderable: {matches}"


def test_system_utils_nonexistent_path() -> None:
    """Verify open_path_in_system gracefully reports nonexistent target."""
    nonexistent = Path("/nonexistent/file/path/figure.png")
    success, msg = open_path_in_system(nonexistent)
    assert not success
    assert "does not exist" in msg


def test_system_utils_open_folder_delegates_to_parent(tmp_path: Path) -> None:
    """Verify open_folder_in_system targets parent directory for files."""
    dummy_file = tmp_path / "dummy.log"
    dummy_file.write_text("log content", encoding="utf-8")

    with patch("subprocess.Popen") as mock_popen, patch("shutil.which", return_value="/usr/bin/xdg-open"):
        success, _msg = open_folder_in_system(dummy_file)
        assert success
        assert mock_popen.called
        args = mock_popen.call_args[0][0]
        assert str(tmp_path.resolve()) in args


def test_render_flightlog_preview_none() -> None:
    """Verify placeholder rendering when path is None."""
    res = render_flightlog_preview(None)
    assert isinstance(res, Text)
    _assert_no_emojis(res)
    assert "Select a simulation run" in res.plain


def test_render_flightlog_preview_nonexistent() -> None:
    """Verify error reporting when path does not exist."""
    res = render_flightlog_preview(Path("FlightLogs/nonexistent_dir"))
    assert isinstance(res, Text)
    _assert_no_emojis(res)
    assert "does not exist" in res.plain


def test_render_flightlog_preview_existing_run() -> None:
    """Verify preview generation on real historical run in FlightLogs."""
    run_dir = Path("FlightLogs/ALVRJ/point_mass_3dof_boost_2026-09-20_195902")
    if not run_dir.is_dir():
        pytest.skip("Historical run directory not found in repository")

    res = render_flightlog_preview(run_dir)
    assert isinstance(res, Text)
    _assert_no_emojis(res)
    assert "3-DOF BOOST" in res.plain.upper()
    assert "Headline Metrics:" in res.plain
    assert "Run Files & Artifacts:" in res.plain
    assert "summary.csv" in res.plain
    assert "execution.log" in res.plain


def test_render_flightlog_preview_log_file() -> None:
    """Verify formatting of execution.log."""
    log_file = Path("FlightLogs/ALVRJ/point_mass_3dof_boost_2026-09-20_195902/execution.log")
    if not log_file.is_file():
        pytest.skip("Historical execution.log not found in repository")

    res = render_flightlog_preview(log_file)
    assert isinstance(res, Text)
    _assert_no_emojis(res)
    assert "LOG: execution.log" in res.plain
    assert "[INFO]" in res.plain


def test_render_flightlog_preview_csv_file() -> None:
    """Verify formatting of summary.csv table."""
    csv_file = Path("FlightLogs/ALVRJ/point_mass_3dof_boost_2026-09-20_195902/summary.csv")
    if not csv_file.is_file():
        pytest.skip("Historical summary.csv not found in repository")

    res = render_flightlog_preview(csv_file)
    assert isinstance(res, Table)
    _assert_no_emojis(res)
    assert res.caption is not None
    assert "Press 'o' to open" in str(res.caption)


def test_render_flightlog_preview_wide_csv_file() -> None:
    """Verify formatting of wide CSV tables (e.g. launch_angle_sweep.csv) with no_wrap and dynamic min_width."""
    csv_file = Path("FlightLogs/ALVRJ/point_mass_3dof_boost_2026-09-20_195902/artifacts/launch_angle_sweep.csv")
    if not csv_file.is_file():
        pytest.skip("Historical launch_angle_sweep.csv not found in repository")

    res = render_flightlog_preview(csv_file)
    assert isinstance(res, Table)
    _assert_no_emojis(res)

    assert len(res.columns) == 9
    for col in res.columns:
        assert col.no_wrap is True
        assert col.min_width is not None
        assert col.min_width > 0

    assert res.caption is not None
    assert "Wide Table" in str(res.caption)


def test_render_flightlog_preview_figure_file() -> None:
    """Verify formatting of figures/*.png with thumbnail and launcher prompt."""
    fig_file = Path("FlightLogs/ALVRJ/point_mass_3dof_boost_2026-09-20_195902/figures/boost_phase.png")
    if not fig_file.is_file():
        pytest.skip("Historical figure not found in repository")

    res = render_flightlog_preview(fig_file)
    assert isinstance(res, Group)
    _assert_no_emojis(res)


def test_flightlogs_tree_hierarchical_structure() -> None:
    """Verify that FlightLogsTree builds expandable run nodes with file children."""
    tree = FlightLogsTree(logs_root=Path("FlightLogs"))
    tree.populate()

    # Find vehicle node
    alvrj_nodes = [node for node in tree.root.children if "ALVRJ" in str(node.label)]
    if not alvrj_nodes:
        pytest.skip("No ALVRJ historical runs present")

    alvrj_node = alvrj_nodes[0]
    assert len(alvrj_node.children) > 0, "ALVRJ vehicle node must contain run nodes"

    completed_runs = [
        node for node in alvrj_node.children
        if node.data is not None and isinstance(node.data, Path) and (node.data / "results.json").is_file()
    ]
    if not completed_runs:
        pytest.skip("No completed ALVRJ run with results.json found")

    run_node = completed_runs[0]
    assert run_node.data is not None and run_node.data.is_dir()

    # Verify that run node contains child files
    child_labels = [str(c.label) for c in run_node.children]
    has_checkpoint = any("results.json" in l for l in child_labels)
    assert has_checkpoint, f"Run node should contain results.json leaf, got: {child_labels}"
    has_log = any("execution.log" in l for l in child_labels)
    assert has_log, f"Run node should contain execution.log leaf, got: {child_labels}"


def test_flightlogs_history_actions_in_app() -> None:
    """Verify that FlightLogsTree actions (o for open external, f for open folder) run cleanly."""
    import asyncio

    async def _test() -> None:
        app = YaadoApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_switch_tab("flight-deck")
            await pilot.pause()

            tree = app.query_one("#flightdeck-runs-tree", FlightLogsTree)
            first_run = tree.select_first_run()
            if first_run is None:
                pytest.skip("No simulation runs available for test")

            with patch("subprocess.Popen") as mock_popen, patch("shutil.which", return_value="/usr/bin/xdg-open"):
                # Trigger 'o' open file action
                tree.action_open_external()
                assert mock_popen.called

                # Trigger 'f' open folder action
                mock_popen.reset_mock()
                tree.action_open_folder()
                assert mock_popen.called

    asyncio.run(_test())


def test_flightlogs_tree_single_click_and_toggle() -> None:
    """Verify that single click selects tree node and double click toggles directories."""
    import asyncio

    from textual import events
    from textual.app import App, ComposeResult

    class TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield FlightLogsTree(id="test-tree", logs_root=Path("FlightLogs"))

    async def _test() -> None:
        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)
            tree = app.query_one("#test-tree", FlightLogsTree)
            if not tree.root.children:
                pytest.skip("No historical runs in FlightLogs")

            vehicle_node = tree.root.children[0]
            if not vehicle_node.children:
                pytest.skip("No run children in vehicle node")

            run_node = vehicle_node.children[0]
            initial_expanded = run_node.is_expanded

            # Simulate single click: chain = 1
            click_1 = events.Click(
                tree, 0, 1, 0, 1, button=1, shift=False, meta=False, ctrl=False, chain=1
            )
            tree.on_click(click_1)
            await pilot.pause(0.05)

            # Node should be selected without toggle
            assert run_node.is_expanded == initial_expanded

            # Simulate double click: chain = 2
            click_2 = events.Click(
                tree, 0, 1, 0, 1, button=1, shift=False, meta=False, ctrl=False, chain=2
            )
            tree.on_click(click_2)
            await pilot.pause(0.05)

            # Directory should toggle
            assert run_node.is_expanded != initial_expanded

    asyncio.run(_test())


def test_flightlogs_tree_image_selection_auto_opens_and_keeps_parent_run() -> None:
    """Verify selecting an image automatically launches viewer and keeps parent run in workspace."""
    import asyncio

    from textual import on
    from textual.app import App, ComposeResult

    sample_fig = Path("FlightLogs/ALVRJ/point_mass_3dof_boost_2026-09-20_195902/figures/boost_phase.png")
    if not sample_fig.is_file():
        pytest.skip("Sample figure not present")

    class TestApp(App[None]):
        def __init__(self) -> None:
            super().__init__()
            self.posted_runs: list[Path] = []

        def compose(self) -> ComposeResult:
            yield FlightLogsTree(id="test-tree", logs_root=Path("FlightLogs"))

        @on(FlightLogsTree.FlightLogSelected)
        def on_flightlog_selected(self, event: FlightLogsTree.FlightLogSelected) -> None:
            self.posted_runs.append(event.path)

    async def _test() -> None:
        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)
            tree = app.query_one("#test-tree", FlightLogsTree)
            parent_run = tree.find_parent_run_dir(sample_fig)
            assert parent_run is not None
            assert parent_run.name == "point_mass_3dof_boost_2026-09-20_195902"

            def find_node(node: Any) -> Any:
                if getattr(node, "data", None) == sample_fig:
                    return node
                for child in getattr(node, "children", []):
                    res = find_node(child)
                    if res is not None:
                        return res
                return None

            fig_node = find_node(tree.root)
            if fig_node is None:
                pytest.skip("Figure node not found in tree")

            curr = fig_node.parent
            while curr is not None:
                curr.expand()
                curr = curr.parent

            await pilot.pause(0.1)
            tree.move_cursor(fig_node)
            assert tree.cursor_node is fig_node

            with patch("subprocess.Popen") as mock_popen, patch("shutil.which", return_value="/usr/bin/xdg-open"):
                tree.action_select_run()
                await pilot.pause(0.1)
                assert mock_popen.called
                assert len(app.posted_runs) == 1
                # The target path posted to workspace must be the parent run directory!
                assert app.posted_runs[0] == parent_run

    asyncio.run(_test())


def test_flightlogs_tree_action_delete_run(tmp_path: Path) -> None:
    """Verify that action_delete_run prompts with ConfirmModal and deletes run directory."""
    import asyncio

    from textual import on
    from textual.app import App, ComposeResult
    from textual.widgets import Button

    # Set up mock vehicle run directory in tmp_path
    vehicle_dir = tmp_path / "TEST_VEHICLE"
    run_dir = vehicle_dir / "point_mass_3dof_boost_2026-10-01_120000"
    run_dir.mkdir(parents=True)
    (run_dir / "results.json").write_text("{}", encoding="utf-8")
    (run_dir / "execution.log").write_text("done", encoding="utf-8")

    class TestApp(App[None]):
        def __init__(self) -> None:
            super().__init__()
            self.deleted_paths: list[Path] = []

        def compose(self) -> ComposeResult:
            yield FlightLogsTree(id="test-tree", logs_root=tmp_path)

        @on(FlightLogsTree.FlightLogDeleted)
        def on_flightlog_deleted(self, event: FlightLogsTree.FlightLogDeleted) -> None:
            self.deleted_paths.append(event.path)

    async def _test() -> None:
        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)
            tree = app.query_one("#test-tree", FlightLogsTree)
            assert len(tree.root.children) == 1
            vehicle_node = tree.root.children[0]
            assert len(vehicle_node.children) == 1
            run_node = vehicle_node.children[0]

            tree.move_cursor(run_node)
            assert tree.cursor_node is run_node

            # Trigger delete action
            tree.action_delete_run()
            await pilot.pause(0.1)

            # Confirm modal should be open
            confirm_btn = app.screen.query_one("#modal-confirm-btn", Button)
            confirm_btn.press()
            await pilot.pause(0.1)

            # The run directory and now-empty vehicle directory must be deleted
            assert not run_dir.exists()
            assert not vehicle_dir.exists()
            assert len(app.deleted_paths) == 1
            assert app.deleted_paths[0] == run_dir

            # Tree should be repopulated with empty placeholder leaf
            assert len(tree.root.children) == 1
            assert "(No simulation runs yet)" in str(tree.root.children[0].label)
            assert tree.root.children[0].data is None

    asyncio.run(_test())


def test_main_view_flightlog_selection_keeps_on_main_screen() -> None:
    """Verify that clicking/selecting a simulation run on the main dashboard updates preview and stays on main screen."""
    import asyncio

    from textual.widgets import Static, TabbedContent

    from Terminal.screens.main_view import MainView

    async def _test() -> None:
        app = YaadoApp()
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.1)
            tabs = app.query_one(TabbedContent)
            assert tabs.active == "main"

            tree = app.query_one("#flightlogs-tree", FlightLogsTree)
            first_run = tree.select_first_run()
            if first_run is None:
                pytest.skip("No historical simulation runs available")

            # Simulate selecting the flightlog run
            tree.action_select_run()
            await pilot.pause(0.1)

            # Crucial: Active tab MUST still be "main" (user is not sent away to flight-deck)
            assert tabs.active == "main"

            # MainView preview pane must display results
            main_view = app.query_one(MainView)
            assert main_view._selected_flightlog_path == first_run
            preview_content = app.query_one("#preview-content", Static)
            preview_text = str(preview_content.render())
            assert "Telemetry" in preview_text or "Results" in preview_text or "ALVRJ" in preview_text

    asyncio.run(_test())


def test_main_view_csv_preview_has_horizontal_scrolling() -> None:
    """Verify that selecting a wide CSV enables horizontal scrolling, while regular text does not."""
    import asyncio

    from textual.containers import ScrollableContainer
    from textual.widgets import Static

    from Terminal.screens.main_view import MainView
    from Terminal.widgets import VehicleTree

    csv_path = Path("FlightLogs/ALVRJ/point_mass_3dof_boost_2026-09-20_195902/artifacts/launch_angle_sweep.csv")
    if not csv_path.is_file():
        pytest.skip("Historical launch_angle_sweep.csv not found in repository")

    async def _test() -> None:
        app = YaadoApp()
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.1)
            main_view = app.query_one(MainView)
            scroll = app.query_one("#preview-scroll", ScrollableContainer)
            preview = app.query_one("#preview-content", Static)

            # 1. On regular vehicle preview, width is constrained to container and max_scroll_x is 0
            assert not preview.has_class("-wide-table")
            assert scroll.max_scroll_x == 0

            # 2. Select wide CSV: -wide-table class is applied and max_scroll_x > 0
            main_view._update_flightlog_preview(csv_path)
            await pilot.pause(0.1)

            assert preview.has_class("-wide-table")
            assert scroll.max_scroll_x > 0

            # Test horizontal scrolling works
            scroll.scroll_to(x=20, animate=False)
            await pilot.pause(0.1)
            assert scroll.scroll_x == 20

            # 3. Switching back to vehicle resets -wide-table and max_scroll_x returns to 0
            first_path = app.query_one("#hangar-tree", VehicleTree).select_first_vehicle()
            if first_path:
                main_view._update_preview(first_path)
                await pilot.pause(0.1)
                assert not preview.has_class("-wide-table")
                assert scroll.max_scroll_x == 0
                assert scroll.scroll_x == 0

    asyncio.run(_test())


def test_flightdeck_csv_preview_has_horizontal_scrolling() -> None:
    """Verify that viewing a wide CSV in FlightDeck enables horizontal scrolling."""
    import asyncio

    from textual.containers import ScrollableContainer
    from textual.widgets import Static, TabbedContent

    from Terminal.screens.flight_deck import FlightDeckView

    csv_path = Path("FlightLogs/ALVRJ/point_mass_3dof_boost_2026-09-20_195902/artifacts/launch_angle_sweep.csv")
    if not csv_path.is_file():
        pytest.skip("Historical launch_angle_sweep.csv not found in repository")

    async def _test() -> None:
        app = YaadoApp()
        async with app.run_test(size=(120, 36)) as pilot:
            tabs = app.query_one(TabbedContent)
            tabs.active = "flight-deck"
            await pilot.pause(0.1)

            flight_deck = app.query_one(FlightDeckView)
            scroll = flight_deck.query_one("#flightdeck-results-scroll", ScrollableContainer)
            content = flight_deck.query_one("#flightdeck-results-content", Static)

            flight_deck._render_historical_log(csv_path)
            await pilot.pause(0.1)

            assert content.has_class("-wide-table")
            assert scroll.max_scroll_x > 0

            scroll.scroll_to(x=30, animate=False)
            await pilot.pause(0.1)
            assert scroll.scroll_x == 30

    asyncio.run(_test())

