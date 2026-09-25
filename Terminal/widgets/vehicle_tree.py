"""Reusable vehicle configuration tree widget.

Provides a unified tree browser for user vehicles and reference configuration templates,
used across both the Main cockpit dashboard and the Hangar vehicle workshop.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from textual import events, on
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.widgets import Tree


class VehicleTree(Tree[Path | None]):
    """Unified tree widget for browsing and selecting YAADO vehicle configurations."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "select_vehicle", "Select Vehicle", show=True),
    ]

    class VehicleSelected(Message):
        """Dispatched when a vehicle is confirmed via double-click or Enter key."""

        def __init__(self, tree: VehicleTree, path: Path) -> None:
            super().__init__()
            self.tree = tree
            self.path = path

        @property
        def control(self) -> VehicleTree:
            """Target control widget for Textual selector matching."""
            return self.tree

    class VehicleHighlighted(Message):
        """Dispatched when a vehicle is highlighted or hovered (None when hovering whitespace)."""

        def __init__(self, tree: VehicleTree, path: Path | None) -> None:
            super().__init__()
            self.tree = tree
            self.path = path

        @property
        def control(self) -> VehicleTree:
            """Target control widget for Textual selector matching."""
            return self.tree

    def __init__(
        self,
        label: str = "Vehicles",
        hangar_root: Path | None = None,
        examples_root: Path | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the vehicle tree browser.

        Args:
            label: Root node label (hidden when show_root is False).
            hangar_root: Optional directory holding user vehicle configurations.
            examples_root: Optional directory holding reference template configurations.
            **kwargs: Standard Textual Tree arguments.
        """
        super().__init__(label, **kwargs)
        repo_root = Path(__file__).resolve().parents[2]
        self.hangar_root = hangar_root or (repo_root / "Hangar")
        self.examples_root = examples_root or (self.hangar_root / "examples")
        self.show_root = False
        self.guide_depth = 2

    def on_mount(self) -> None:
        """Populate the tree structure upon widget mount."""
        self.populate()

    def populate(self) -> None:
        """Scan the filesystem and populate reference examples and user vehicles."""
        self.clear()

        # 1. Reference examples
        examples_node = self.root.add("[bold]Reference Examples[/bold]", expand=True)
        if self.examples_root.is_dir():
            for toml_path in sorted(self.examples_root.rglob("*.toml")):
                vehicle_name = toml_path.stem.replace("_", " ")
                examples_node.add_leaf(vehicle_name, data=toml_path)

        # 2. User projects
        user_node = self.root.add("[bold]User Vehicles[/bold]", expand=True)
        user_tomls: list[Path] = []
        if self.hangar_root.is_dir():
            for p in sorted(self.hangar_root.rglob("*.toml")):
                if not p.is_relative_to(self.examples_root):
                    user_tomls.append(p)

        if user_tomls:
            for toml_path in user_tomls:
                user_node.add_leaf(toml_path.stem.replace("_", " "), data=toml_path)
        else:
            user_node.add_leaf("[dim](No user vehicles)[/dim]", data=None)

    def select_first_vehicle(self) -> Path | None:
        """Select the first available vehicle leaf in the tree.

        Returns:
            The file path of the first vehicle leaf, or None if no vehicles exist.
        """
        for group in self.root.children:
            for leaf in group.children:
                if leaf.data is not None and isinstance(leaf.data, Path) and leaf.data.is_file():
                    self.select_node(leaf)
                    return leaf.data
        return None

    def action_select_vehicle(self) -> None:
        """Handle Enter key action to select the current vehicle."""
        if (
            self.cursor_node is not None
            and isinstance(self.cursor_node.data, Path)
            and self.cursor_node.data.is_file()
        ):
            self.post_message(self.VehicleSelected(self, self.cursor_node.data))

    def on_click(self, event: events.Click) -> None:
        """Handle mouse clicks: double-click confirms selection."""
        if event.chain == 2:
            self.action_select_vehicle()

    @on(Tree.NodeHighlighted)
    def _on_tree_node_highlighted(self, event: Tree.NodeHighlighted[Path | None]) -> None:
        """Bubble vehicle highlighted event when cursor moves."""
        self.post_message(self.VehicleHighlighted(self, event.node.data))

    @on(events.MouseMove)
    def _on_mouse_move(self, event: events.MouseMove) -> None:
        """Preview vehicle on mouse hover, or post None when over whitespace."""
        line_index = event.y + self.scroll_offset.y
        node = self.get_node_at_line(line_index)
        if node is not None and node.data is not None and isinstance(node.data, Path) and node.data.is_file():
            self.post_message(self.VehicleHighlighted(self, node.data))
        else:
            self.post_message(self.VehicleHighlighted(self, None))

    @on(events.Leave)
    def on_tree_leave(self, event: events.Leave) -> None:
        """Reset hover when mouse pointer leaves the widget."""
        self.post_message(self.VehicleHighlighted(self, None))
