"""Reusable simulation run tree widget for FlightLogs.

Provides a unified hierarchical tree browser for historical simulation runs and artifacts,
supporting file drill-down (logs, figures, CSVs) and external system viewer launching.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from textual import events, on
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.widgets import Tree

from Terminal.system_utils import open_folder_in_system, open_path_in_system
from Terminal.widgets.modals import ConfirmModal


class FlightLogsTree(Tree[Path | None]):
    """Unified tree widget for browsing and inspecting historical simulation runs and files."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "select_run", "Select/Open", show=True),
        Binding("o", "open_external", "Open File", show=True),
        Binding("f", "open_folder", "Open Folder", show=True),
        Binding("delete,backspace,d", "delete_run", "Delete Run", show=True),
    ]

    class FlightLogSelected(Message):
        """Dispatched when a run or file node is confirmed via double-click or Enter key."""

        def __init__(self, tree: FlightLogsTree, path: Path) -> None:
            super().__init__()
            self.tree = tree
            self.path = path

        @property
        def control(self) -> FlightLogsTree:
            """Target control widget for Textual selector matching."""
            return self.tree

    class FlightLogHighlighted(Message):
        """Dispatched when a node is highlighted or hovered (None when over whitespace)."""

        def __init__(self, tree: FlightLogsTree, path: Path | None) -> None:
            super().__init__()
            self.tree = tree
            self.path = path

        @property
        def control(self) -> FlightLogsTree:
            """Target control widget for Textual selector matching."""
            return self.tree

    class FlightLogDeleted(Message):
        """Dispatched after a simulation run directory has been deleted."""

        def __init__(self, tree: FlightLogsTree, path: Path) -> None:
            super().__init__()
            self.tree = tree
            self.path = path

        @property
        def control(self) -> FlightLogsTree:
            """Target control widget for Textual selector matching."""
            return self.tree

    ANALYSIS_NAMES: ClassVar[dict[str, str]] = {
        "point_mass_3dof_boost": "3-DOF Boost",
        "point_mass_3dof": "Point Mass 3-DOF",
        "aero_polar": "Aero Polars",
        "mass_estimation": "Mass & Inertia",
    }
    IMAGE_EXTENSIONS: ClassVar[set[str]] = {".png", ".jpg", ".jpeg", ".svg", ".pdf"}

    @staticmethod
    def find_parent_run_dir(path: Path) -> Path | None:
        """Find the root run directory containing results.json or execution.log."""
        curr = path if path.is_dir() else path.parent
        while curr != curr.parent and curr.name:
            if (curr / "results.json").is_file() or (curr / "execution.log").is_file():
                return curr
            curr = curr.parent
        return None

    def __init__(
        self,
        label: str = "FlightLogs",
        logs_root: Path | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the flight logs tree browser.

        Args:
            label: Root node label (hidden when show_root is False).
            logs_root: Optional directory holding historical simulation run logs.
            **kwargs: Standard Textual Tree arguments.
        """
        super().__init__(label, **kwargs)
        repo_root = Path(__file__).resolve().parents[2]
        self.logs_root = logs_root or (repo_root / "FlightLogs")
        self.show_root = False
        self.guide_depth = 2
        self.auto_expand = False

    def on_mount(self) -> None:
        """Populate the tree structure upon widget mount."""
        self.populate()

    def populate(self) -> None:
        """Scan the filesystem and populate simulation runs grouped by vehicle."""
        self.clear()

        if not self.logs_root.is_dir():
            self.root.add_leaf("[dim](No simulation runs yet)[/dim]", data=None)
            return

        vehicle_dirs = [
            d for d in sorted(self.logs_root.iterdir())
            if d.is_dir() and not d.name.startswith((".", "__"))
        ]

        if not vehicle_dirs:
            self.root.add_leaf("[dim](No simulation runs yet)[/dim]", data=None)
            return

        has_any_runs = False
        for v_dir in vehicle_dirs:
            runs = [
                d for d in sorted(v_dir.iterdir(), reverse=True)
                if d.is_dir() and not d.name.startswith((".", "__"))
            ]
            if not runs:
                continue

            has_any_runs = True
            v_node = self.root.add(f"[bold]{v_dir.name}[/bold]", expand=True, data=v_dir)
            for run_dir in runs:
                label = self.format_run_label(run_dir)
                run_node = v_node.add(label, expand=False, data=run_dir)

                # 1. Standard checkpoint results.json
                results_file = run_dir / "results.json"
                if results_file.is_file():
                    run_node.add_leaf("[cyan]results.json[/cyan]", data=results_file)

                # 2. Execution log
                log_file = run_dir / "execution.log"
                if log_file.is_file():
                    run_node.add_leaf("[yellow]execution.log[/yellow]", data=log_file)

                # 3. Summary CSV
                csv_file = run_dir / "summary.csv"
                if csv_file.is_file():
                    run_node.add_leaf("[green]summary.csv[/green]", data=csv_file)

                # 4. Figures directory
                figures_dir = run_dir / "figures"
                if figures_dir.is_dir():
                    fig_files = [
                        f for f in sorted(figures_dir.iterdir())
                        if f.is_file() and not f.name.startswith((".", "__"))
                    ]
                    if fig_files:
                        fig_node = run_node.add(
                            f"[blue]figures[/blue] [dim]({len(fig_files)})[/dim]",
                            expand=False,
                            data=figures_dir,
                        )
                        for fig_f in fig_files:
                            fig_node.add_leaf(f"[blue]{fig_f.name}[/blue]", data=fig_f)

                # 5. Artifacts directory
                artifacts_dir = run_dir / "artifacts"
                if artifacts_dir.is_dir():
                    art_files = [
                        f for f in sorted(artifacts_dir.iterdir())
                        if f.is_file() and not f.name.startswith((".", "__"))
                    ]
                    if art_files:
                        art_node = run_node.add(
                            f"[magenta]artifacts[/magenta] [dim]({len(art_files)})[/dim]",
                            expand=False,
                            data=artifacts_dir,
                        )
                        for art_f in art_files:
                            art_node.add_leaf(f"[magenta]{art_f.name}[/magenta]", data=art_f)

                # 6. Any other auxiliary files
                standard_names = {
                    "results.json",
                    "execution.log",
                    "summary.csv",
                    "figures",
                    "artifacts",
                }
                other_files = [
                    f for f in sorted(run_dir.iterdir())
                    if f.is_file()
                    and f.name not in standard_names
                    and not f.name.startswith((".", "__"))
                ]
                for other_f in other_files:
                    run_node.add_leaf(f"[white]{other_f.name}[/white]", data=other_f)

        if not has_any_runs:
            self.root.add_leaf("[dim](No simulation runs yet)[/dim]", data=None)

    def select_first_run(self) -> Path | None:
        """Select the first available simulation run leaf in the tree.

        Returns:
            The directory path of the first simulation run, or None if no runs exist.
        """
        for group in self.root.children:
            for child in group.children:
                if child.data is not None and isinstance(child.data, Path) and child.data.is_dir():
                    self.select_node(child)
                    return child.data
        return None

    @classmethod
    def format_run_label(cls, run_dir: Path) -> str:
        """Generate a compact label for a simulation run in the tree.

        Args:
            run_dir: Directory of the simulation run.

        Returns:
            Rich-formatted string representation for the tree leaf.
        """
        name = run_dir.name
        parts = name.rsplit("_", 2)
        if len(parts) >= 3 and "-" in parts[1]:
            analysis_slug = parts[0]
            date_str = parts[1]
            time_str = parts[2]
            formatted_time = f"{time_str[:2]}:{time_str[2:4]}" if len(time_str) >= 4 else time_str
            pretty_analysis = cls.pretty_analysis_name(analysis_slug)
            return f"{pretty_analysis} [dim]{date_str[5:]} {formatted_time}[/dim]"

        return name.replace("_", " ")

    @classmethod
    def pretty_analysis_name(cls, slug: str) -> str:
        """Map analysis slugs to clean human-readable names.

        Args:
            slug: Raw analysis identifier.

        Returns:
            Human-readable analysis title.
        """
        return cls.ANALYSIS_NAMES.get(slug, slug.replace("_", " ").title())

    def action_select_run(self) -> None:
        """Handle Enter key action on tree nodes."""
        if self.cursor_node is None or not isinstance(self.cursor_node.data, Path):
            return

        path = self.cursor_node.data
        if path.is_dir():
            if self.cursor_node.children:
                self.cursor_node.toggle()
            self.post_message(self.FlightLogSelected(self, path))
            return

        if path.is_file():
            if path.suffix.lower() in self.IMAGE_EXTENSIONS:
                success, msg = open_path_in_system(path)
                self.app.notify(msg, severity="information" if success else "warning")
                parent_run = self.find_parent_run_dir(path)
                target = parent_run if parent_run is not None else path
                self.post_message(self.FlightLogSelected(self, target))
                return
            self.post_message(self.FlightLogSelected(self, path))

    def action_open_external(self) -> None:
        """Launch the system default application for the highlighted file or folder."""
        if self.cursor_node is not None and isinstance(self.cursor_node.data, Path):
            path = self.cursor_node.data
            success, msg = open_path_in_system(path)
            self.app.notify(msg, severity="information" if success else "warning")

    def action_open_folder(self) -> None:
        """Open the containing directory in the system file manager."""
        if self.cursor_node is not None and isinstance(self.cursor_node.data, Path):
            path = self.cursor_node.data
            success, msg = open_folder_in_system(path)
            self.app.notify(msg, severity="information" if success else "warning")

    def action_delete_run(self) -> None:
        """Handle 'd', Delete, or Backspace key action to prompt deletion of the targeted run."""
        if self.cursor_node is None or not isinstance(self.cursor_node.data, Path):
            return
        path = self.cursor_node.data
        target_run = self.find_parent_run_dir(path)
        if target_run is None and path.is_dir():
            target_run = path
        if target_run is None or not target_run.is_dir():
            self.app.notify("No simulation run selected to delete", severity="warning")
            return

        run_name = target_run.name
        vehicle_name = target_run.parent.name

        def on_confirmed(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                import shutil
                shutil.rmtree(target_run)
                # If vehicle folder is now empty, clean it up
                if target_run.parent.is_dir() and not any(target_run.parent.iterdir()):
                    target_run.parent.rmdir()

                self.populate()
                self.post_message(self.FlightLogDeleted(self, target_run))
                self.app.notify(f"Deleted run '{run_name}'", severity="information")
            except OSError as exc:
                self.app.notify(f"Failed to delete run: {exc}", severity="error")

        self.app.push_screen(
            ConfirmModal(
                title="Delete Simulation Run",
                message=f"Are you sure you want to permanently delete run '{run_name}' for vehicle '{vehicle_name}'?\nThis will remove all artifacts, logs, and figures.",
                confirm_label="Delete",
                is_destructive=True,
            ),
            callback=on_confirmed,
        )

    def on_click(self, event: events.Click) -> None:
        """Handle mouse clicks: single-click selects/previews, double-click toggles."""
        line_index = event.y + self.scroll_offset.y
        node = self.get_node_at_line(line_index)
        if node is None or node.data is None or not isinstance(node.data, Path):
            return

        self.move_cursor(node)

        # For images, automatically open in system viewer and keep run telemetry in workspace
        if node.data.is_file() and node.data.suffix.lower() in self.IMAGE_EXTENSIONS:
            success, msg = open_path_in_system(node.data)
            self.app.notify(msg, severity="information" if success else "warning")
            parent_run = self.find_parent_run_dir(node.data)
            target = parent_run if parent_run is not None else node.data
            self.post_message(self.FlightLogSelected(self, target))
            return

        self.post_message(self.FlightLogSelected(self, node.data))

        if event.chain == 2 and node.data.is_dir() and node.children:
            node.toggle()

    @on(Tree.NodeHighlighted)
    def _on_tree_node_highlighted(self, event: Tree.NodeHighlighted[Path | None]) -> None:
        """Bubble run highlighted event when cursor moves."""
        path = event.node.data
        if (
            path is not None
            and isinstance(path, Path)
            and path.is_file()
            and path.suffix.lower() in self.IMAGE_EXTENSIONS
        ):
            parent_run = self.find_parent_run_dir(path)
            self.post_message(
                self.FlightLogHighlighted(self, parent_run if parent_run is not None else path)
            )
        else:
            self.post_message(self.FlightLogHighlighted(self, path))

    @on(events.MouseMove)
    def _on_mouse_move(self, event: events.MouseMove) -> None:
        """Preview run on mouse hover, or post None when over whitespace."""
        line_index = event.y + self.scroll_offset.y
        node = self.get_node_at_line(line_index)
        if node is not None and node.data is not None and isinstance(node.data, Path):
            path = node.data
            if path.is_file() and path.suffix.lower() in self.IMAGE_EXTENSIONS:
                parent_run = self.find_parent_run_dir(path)
                self.post_message(
                    self.FlightLogHighlighted(self, parent_run if parent_run is not None else path)
                )
            else:
                self.post_message(self.FlightLogHighlighted(self, path))
        else:
            self.post_message(self.FlightLogHighlighted(self, None))

    @on(events.Leave)
    def on_tree_leave(self, event: events.Leave) -> None:
        """Reset hover when mouse pointer leaves the widget."""
        self.post_message(self.FlightLogHighlighted(self, None))
