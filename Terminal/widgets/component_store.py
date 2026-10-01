"""Component Store catalog widgets with collapsible categories and draggable tiles.

Provides modular ComponentTile cards arranged inside Collapsible category shelves,
supporting drag-and-drop with a live cursor-following ghost, 'a' key addition,
double-click addition, and single-click parameter inspection.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel
from rich.text import Text
from textual import events
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.css.query import NoMatches
from textual.errors import NoWidget
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Collapsible, Static

from YAADO_Core.ComponentStore import (
    AERO_COMPONENTS,
    BODY_COMPONENTS,
    PROPULSION_COMPONENTS,
    MassProperties,
)

if TYPE_CHECKING:
    from textual.app import ComposeResult


class DragGhost(Static):
    """Floating ghost badge that follows the mouse cursor during drag-and-drop."""

    ALLOW_SELECT: ClassVar[bool] = False


class ComponentTile(Widget, can_focus=True):
    """Interactive modular card representing a component in the store.

    Attributes:
        comp_id: Pydantic component class name (e.g. 'AxisymmetricBody').
        tag: Subsystem category badge string (e.g. 'BODY', 'PROP').
        pretty_name: Clean human-readable component name.
        color: Category color identifier for Textual markup.
    """

    ALLOW_SELECT: ClassVar[bool] = False

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("a", "add_to_vehicle", "Add to Vehicle", show=True),
        Binding("enter", "select_tile", "Preview", show=False),
    ]

    class ComponentSelected(Message):
        """Dispatched when a component is confirmed for addition via double-click, 'a', or drop."""

        def __init__(self, tile: ComponentTile, comp_id: str) -> None:
            super().__init__()
            self.tile = tile
            self.comp_id = comp_id

        @property
        def control(self) -> ComponentTile:
            return self.tile

    def __init__(
        self,
        comp_id: str,
        tag: str,
        pretty_name: str,
        color: str,
        **kwargs: Any,
    ) -> None:
        """Initialize component card tile.

        Args:
            comp_id: Class name string.
            tag: Short category tag.
            pretty_name: Display label.
            color: Rich markup color.
            **kwargs: Standard Textual widget arguments.
        """
        super().__init__(**kwargs)
        self.comp_id = comp_id
        self.tag = tag
        self.pretty_name = pretty_name
        self.color = color
        self._ghost: DragGhost | None = None
        self._is_dragging: bool = False
        self._mouse_down: bool = False
        self._drag_start_x: int = 0
        self._drag_start_y: int = 0
        self._last_click_time: float = 0.0

    def render(self) -> Text:
        """Render centered grip handle and component name."""
        return Text.from_markup(f"[dim #94a3b8]⠿[/dim #94a3b8]  {self.pretty_name}")

    def action_add_to_vehicle(self) -> None:
        """Add this component to the active vehicle."""
        self.post_message(self.ComponentSelected(self, self.comp_id))

    def action_select_tile(self) -> None:
        """Focus the component tile."""
        self.focus()

    def on_click(self, event: events.Click) -> None:
        """Handle mouse clicks: single click focuses, double click adds to vehicle."""
        event.prevent_default()
        event.stop()
        if event.chain == 2:
            self.post_message(self.ComponentSelected(self, self.comp_id))
        else:
            self.focus()

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Focus tile, highlight component parameters, and start drag tracking."""
        if event.button == 1:
            event.prevent_default()
            event.stop()
            self.screen.clear_selection()
            self.focus()
            self._mouse_down = True
            self._drag_start_x = event.screen_x
            self._drag_start_y = event.screen_y
            self._is_dragging = False
            self.capture_mouse(True)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Track drag displacement and update floating ghost position."""
        if self._mouse_down:
            event.prevent_default()
            event.stop()
            dx = abs(event.screen_x - self._drag_start_x)
            dy = abs(event.screen_y - self._drag_start_y)
            if dx > 1 or dy > 1:
                if not self._is_dragging:
                    self._is_dragging = True
                    self.add_class("-dragging")
                    self._ghost = DragGhost(f"⠿  {self.pretty_name}")
                    self.screen.mount(self._ghost)

                if self._ghost is not None:
                    self._ghost.styles.offset = (event.screen_x + 1, event.screen_y)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Complete drag-and-drop or release mouse capture."""
        event.prevent_default()
        event.stop()
        self.screen.clear_selection()
        self._mouse_down = False
        self.capture_mouse(False)
        self.remove_class("-dragging")

        if self._ghost is not None:
            self._ghost.visible = False
            self._ghost.display = False
            self._ghost.remove()
            self._ghost = None

        if self._is_dragging:
            self._is_dragging = False
            is_dropped_on_target = False
            try:
                right_col = self.screen.query_one("#hangar-right-column")
                if right_col.region.contains(event.screen_x, event.screen_y):
                    is_dropped_on_target = True
            except (NoMatches, KeyError):
                pass

            if not is_dropped_on_target:
                try:
                    target_widget, _ = self.screen.get_widget_at(event.screen_x, event.screen_y)
                except (NoWidget, KeyError):
                    target_widget = None

                current: Any = target_widget
                while current is not None:
                    if getattr(current, "id", None) in (
                        "hangar-right-column",
                        "panel-and-hangar",
                        "workspace-card",
                        "vehicle-components-list",
                        "workspace-header",
                        "component-preview-card",
                        "component-form",
                    ):
                        is_dropped_on_target = True
                        break
                    current = getattr(current, "parent", None)

            if is_dropped_on_target:
                self.post_message(self.ComponentSelected(self, self.comp_id))


class ComponentStoreView(VerticalScroll):
    """Scrollable container housing collapsible component categories and modular tiles."""

    ALLOW_SELECT: ClassVar[bool] = False

    SUBSYSTEM_CATEGORIES: ClassVar[list[tuple[str, str, str, tuple[type[BaseModel], ...]]]] = [
        ("AIRFRAME", "BODY", "#3b82f6", BODY_COMPONENTS),
        ("PROPULSION", "PROP", "#f59e0b", PROPULSION_COMPONENTS),
        ("AERODYNAMICS", "AERO", "#0284c7", AERO_COMPONENTS),
        ("MASS & INERTIA", "MASS", "#94a3b8", (MassProperties,)),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.component_classes: dict[str, type[BaseModel]] = {}
        for _, _, _, comp_tuple in self.SUBSYSTEM_CATEGORIES:
            for comp_cls in comp_tuple:
                self.component_classes[comp_cls.__name__] = comp_cls

    def compose(self) -> ComposeResult:
        """Render collapsible categories with individual component tiles."""
        for cat_name, tag, color, comp_tuple in self.SUBSYSTEM_CATEGORIES:
            with Collapsible(title=cat_name, collapsed=False):
                for comp_cls in comp_tuple:
                    comp_id = comp_cls.__name__
                    pretty_name = re.sub(r"(?<!^)(?=[A-Z])", " ", comp_id)
                    yield ComponentTile(
                        comp_id=comp_id,
                        tag=tag,
                        pretty_name=pretty_name,
                        color=color,
                        id=f"tile-{comp_id.lower()}",
                    )
