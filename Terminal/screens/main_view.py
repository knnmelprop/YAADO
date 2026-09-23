"""Main view (Tab 1) serving as the default landing cockpit and telemetry dashboard.

Displays environment readiness (verified physics solvers), active vehicle summary,
recent simulation run activity from FlightLogs, and quick launchpad navigation actions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.containers import Container

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
        """Render the system readiness card, active vehicle summary, and quick launchpad.

        Yields:
            Child widgets comprising the main dashboard interface.
        """
        yield from ()

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
