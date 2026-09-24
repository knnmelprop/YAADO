"""Main view (Tab 1) serving as the default landing cockpit and telemetry dashboard.

Displays environment readiness (verified physics solvers), active vehicle summary,
recent simulation run activity from FlightLogs, and quick launchpad navigation actions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.containers import Container, Horizontal, Vertical
from textual.widgets import DataTable, Label, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig


class MainView(Container):
    """Default landing screen and system telemetry dashboard.

    Attributes:
        active_vehicle: Currently selected vehicle configuration for the session, if any.
    """

    def __init__(
        self,
        active_vehicle: BaseVehicleConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Main View dashboard.

        Args:
            active_vehicle: Optional currently loaded vehicle configuration.
            **kwargs: Standard Textual container keyword arguments.
        """
        super().__init__(**kwargs)
        self.active_vehicle = active_vehicle

    def compose(self) -> ComposeResult:
        """Render the hangar, flightlogs and a window for info preview.

        Yields:
            Child widgets comprising the main dashboard interface.
        """
        with Horizontal(id="main-layout"):
            # Left column: Action launchpads
            with Vertical(id="left-column", classes="cockpit-col"):
                hangar_card = Container(id="hangar-card", classes="cockpit-card")
                hangar_card.border_title = "Hangar"
                with hangar_card:
                    yield Static("• [bold]New Vehicle[/bold] (Create from template)")
                    yield Static("• [bold]Open Vehicle[/bold] (Select from Hangar)")

                flightlogs_card = Container(id="flightlogs-card", classes="cockpit-card")
                flightlogs_card.border_title = "FlightLogs"
                with flightlogs_card:
                    yield Static("• [bold]New Analysis[/bold] (Point Mass 3-DOF / Aero / Mass)")
                    yield Static("• [bold]Browse History[/bold] (Recent simulation runs)")

            # Right column: Main window for info preview depending on the selected item
            with Vertical(id="right-column", classes="cockpit-col"):
                preview_card = Container(id="preview-card", classes="cockpit-card")
                preview_card.border_title = "Preview"
                with preview_card:
                    yield Static(
                        "Nothing to show\n\nClick on something or select an action to see details.",
                        id="preview-content",
                    )

    def refresh_system_status(self) -> dict[str, Any]:
        """Query system solvers and environment health.

        Returns:
            Dictionary containing verified solver count, ISA model state, and checks.
        """
        raise NotImplementedError

    def load_recent_activity(self, limit: int = 5) -> list[dict[str, Any]]:
        """Scan FlightLogs for recent simulation runs and convergence statuses.

        Args:
            limit: Maximum number of recent runs to retrieve.

        Returns:
            List of dictionaries containing run metadata and convergence indicators.
        """
        raise NotImplementedError
