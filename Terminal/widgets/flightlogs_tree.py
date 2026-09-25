"""Reusable simulation run tree widget for FlightLogs.

Provides a unified tree browser for historical simulation runs grouped by vehicle,
used across the Main cockpit dashboard and the Flight Deck execution view.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from textual import events, on
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.widgets import Tree


class FlightLogsTree(Tree[Path | None]):
    """Unified tree widget for browsing and inspecting historical simulation runs."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "select_run", "Select Run", show=True),
    ]

    class FlightLogSelected(Message):
        """Dispatched when a simulation run is confirmed via double-click or Enter key."""

        def __init__(self, tree: FlightLogsTree, path: Path) -> None:
            super().__init__()
            self.tree = tree
            self.path = path

        @property
        def control(self) -> FlightLogsTree:
            """Target control widget for Textual selector matching."""
            return self.tree

    class FlightLogHighlighted(Message):
        """Dispatched when a run or vehicle is highlighted or hovered (None when over whitespace)."""

        def __init__(self, tree: FlightLogsTree, path: Path | None) -> None:
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
                v_node.add_leaf(label, data=run_dir)

        if not has_any_runs:
            self.root.add_leaf("[dim](No simulation runs yet)[/dim]", data=None)

    def select_first_run(self) -> Path | None:
        """Select the first available simulation run leaf in the tree.

        Returns:
            The directory path of the first simulation run, or None if no runs exist.
        """
        for group in self.root.children:
            for leaf in group.children:
                if leaf.data is not None and isinstance(leaf.data, Path) and leaf.data.is_dir():
                    self.select_node(leaf)
                    return leaf.data
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
        """Handle Enter key action to select the current simulation run."""
        if (
            self.cursor_node is not None
            and isinstance(self.cursor_node.data, Path)
            and (self.cursor_node.data / "results.json").is_file()
        ):
            self.post_message(self.FlightLogSelected(self, self.cursor_node.data))

    def on_click(self, event: events.Click) -> None:
        """Handle mouse clicks: double-click confirms selection."""
        if event.chain == 2:
            self.action_select_run()

    @on(Tree.NodeHighlighted)
    def _on_tree_node_highlighted(self, event: Tree.NodeHighlighted[Path | None]) -> None:
        """Bubble run highlighted event when cursor moves."""
        self.post_message(self.FlightLogHighlighted(self, event.node.data))

    @on(events.MouseMove)
    def _on_mouse_move(self, event: events.MouseMove) -> None:
        """Preview run on mouse hover, or post None when over whitespace."""
        line_index = event.y + self.scroll_offset.y
        node = self.get_node_at_line(line_index)
        if node is not None and node.data is not None and isinstance(node.data, Path):
            self.post_message(self.FlightLogHighlighted(self, node.data))
        else:
            self.post_message(self.FlightLogHighlighted(self, None))

    @on(events.Leave)
    def on_tree_leave(self, event: events.Leave) -> None:
        """Reset hover when mouse pointer leaves the widget."""
        self.post_message(self.FlightLogHighlighted(self, None))
