"""Main Textual application orchestrator for YAADO.

Coordinates top-level tab navigation across the three primary stages:
1. Main View (Cockpit & Dashboard)
2. Hangar (Vehicle Workshop & Assembly)
3. Flight Deck (Analyses, Pipelines, Sweeps, and FlightLogs)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from textual import on
from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.widgets import Footer, TabbedContent, TabPane

from Terminal.screens.flight_deck import FlightDeckView
from Terminal.screens.hangar import HangarView
from Terminal.screens.main_view import MainView
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig


class YaadoApp(App[None]):
    """The central YAADO interactive terminal application."""

    TITLE = "YAADO"
    CSS_PATH = "theme.tcss"
    ALLOW_SELECT = False

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

        from textual.css.query import NoMatches

        try:
            hangar_view = self.query_one(HangarView)
            hangar_view.load_vehicle(self.active_vehicle, self.active_vehicle_path)
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
        """Mount header, three primary tab panes, and footer.

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
        self.set_focus(None)
        self.refresh_bindings()