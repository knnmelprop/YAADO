"""Main Textual application orchestrator for YAADO.

Coordinates top-level tab navigation across the three primary stages:
1. Main View (Cockpit & Dashboard)
2. Hangar (Vehicle Workshop & Assembly)
3. Flight Deck (Analyses, Pipelines, Sweeps, and FlightLogs)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.css.query import NoMatches
from textual.widgets import Footer, Static, TabbedContent, TabPane

from Terminal.screens.flight_deck import FlightDeckView
from Terminal.screens.hangar import HangarView
from Terminal.screens.main_view import MainView
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig


class YaadoApp(App[None]):
    """The central YAADO interactive terminal application."""

    TITLE = "YAADO"
    CSS_PATH = "theme.tcss"
    ALLOW_SELECT = False

    MIN_WIDTH: ClassVar[int] = 110
    MIN_HEIGHT: ClassVar[int] = 28

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(ansi_color=True, **kwargs)
        self._active_tab: str = "main"
        self.active_vehicle: BaseVehicleConfig | None = None
        self.active_vehicle_path: Path | None = None

    def set_active_vehicle(
        self,
        path: Path | None,
        config: BaseVehicleConfig | None = None,
    ) -> None:
        """Set the globally active vehicle across the application tabs.

        Args:
            path: Source file path of the vehicle.
            config: Optional pre-loaded BaseVehicleConfig instance.
        """
        if config is not None:
            self.active_vehicle = config
            self.active_vehicle_path = path
        elif path is not None and path.is_file():
            try:
                self.active_vehicle = BaseVehicleConfig.from_toml(path)
                self.active_vehicle_path = path
            except (OSError, ValueError, KeyError):
                self.active_vehicle = None
                self.active_vehicle_path = None
        else:
            self.active_vehicle = None
            self.active_vehicle_path = None

        try:
            hangar_view = self.query_one(HangarView)
            hangar_view.load_vehicle(self.active_vehicle, self.active_vehicle_path)
        except NoMatches:
            pass

        try:
            flight_deck_view = self.query_one(FlightDeckView)
            flight_deck_view.set_active_vehicle(self.active_vehicle, self.active_vehicle_path)
        except NoMatches:
            pass

    BINDINGS: ClassVar[list[BindingType]] = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark/Light Mode"),
        ("m", "switch_tab('main')", "Main"),
        ("h", "switch_tab('hangar')", "Hangar"),
        ("f", "switch_tab('flight-deck')", "Flight Deck"),
    ]

    def compose(self) -> ComposeResult:
        """Mount header, three primary tab panes, footer, and resize warning overlay.

        Yields:
            Core application layout widgets.
        """
        with TabbedContent(id="main-tabs", initial="main"):
            with TabPane("Main", id="main"):
                yield MainView(id="main-view")
            with TabPane("Hangar", id="hangar"):
                yield HangarView(id="hangar-view")
            with TabPane("Flight Deck", id="flight-deck"):
                yield FlightDeckView(id="flight-deck-view")
        yield Footer()
        yield Static(
            "Please maximize the terminal to make sure our UI doesn't break :)",
            id="maximize-warning",
        )

    def on_mount(self) -> None:
        """Configure application-level settings on mount."""
        type(self.screen).ALLOW_SELECT = False
        self._check_terminal_size(self.size.width, self.size.height)

    def on_resize(self, event: events.Resize) -> None:
        """Check terminal dimensions and toggle maximize warning.

        Args:
            event: Terminal resize event containing updated dimensions.
        """
        self._check_terminal_size(event.size.width, event.size.height)

    def _check_terminal_size(self, width: int, height: int) -> None:
        """Toggle main UI visibility based on minimum terminal dimensions.

        Args:
            width: Current terminal width in characters.
            height: Current terminal height in rows.
        """
        too_small = width < self.MIN_WIDTH or height < self.MIN_HEIGHT
        try:
            main_tabs = self.query_one("#main-tabs", TabbedContent)
            footer = self.query_one(Footer)
            warning = self.query_one("#maximize-warning", Static)
            main_tabs.display = not too_small
            footer.display = not too_small
            warning.display = too_small
        except NoMatches:
            pass

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Dynamically enable or hide actions in the footer.

        Args:
            action: The name of the action being checked.
            parameters: Action parameters tuple.

        Returns:
            False to hide the binding from the footer, or True to display it.
        """
        return not (action == "switch_tab" and bool(parameters) and parameters[0] == self._active_tab)

    @on(TabbedContent.TabActivated)
    def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Update active tab state and refresh footer bindings when tab changes.

        Args:
            event: Tab activated event with active tab reference.
        """
        self._active_tab = event.tabbed_content.active
        self.refresh_bindings()

    def action_toggle_dark(self) -> None:
        """Toggle between dark and light themes."""
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )

    def action_switch_tab(self, tab_id: str) -> None:
        """Switch active tab pane programmatically.

        Args:
            tab_id: Identifier of the target tab ('main', 'hangar', or 'flight-deck').
        """
        self._active_tab = tab_id
        tabs = self.query_one(TabbedContent)
        tabs.active = tab_id
        if tab_id == "flight-deck":
            try:
                fd = self.query_one(FlightDeckView)
                fd.set_active_vehicle(self.active_vehicle, self.active_vehicle_path)
            except NoMatches:
                pass
        self.set_focus(None)
        self.refresh_bindings()