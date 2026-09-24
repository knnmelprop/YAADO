"""Hangar view (Tab 2) unifying vehicle library inspection and interactive assembly.

Provides a complete vehicle workshop allowing users to browse configurations in Hangar/,
fork read-only reference templates from Hangar/examples/, and interactively build
or modify vehicles using the longitudinal spatial canvas and parameter forms.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig


class HangarView(Container):
    """Unified vehicle manager and construction workspace.

    Attributes:
        hangar_root: Path to the root directory storing user vehicle configurations.
        examples_root: Path to read-only reference configuration examples.
        selected_vehicle_name: Name of the currently selected vehicle, if any.
        current_mode: Active sub-mode ('library' for browsing or 'assembly' for building).
    """

    def __init__(
        self,
        hangar_root: Path = Path("Hangar"),
        examples_root: Path = Path("Hangar/examples"),
        **kwargs: Any,
    ) -> None:
        """Initialize the Hangar view.

        Args:
            hangar_root: Path to user vehicle configurations directory.
            examples_root: Path to pre-built reference examples.
            **kwargs: Standard Textual container keyword arguments.
        """
        super().__init__(**kwargs)
        self.hangar_root = hangar_root
        self.examples_root = examples_root
        self.selected_vehicle_name: str | None = None
        self.current_mode: Literal["library", "assembly"] = "library"

    def compose(self) -> ComposeResult:
        """Render the vehicle library browser and the assembly mode switcher.

        Yields:
            Child widgets comprising the Hangar workspace.
        """
        with Horizontal(id="hangar-layout"):
            # Left column: ComponentStore
            componentstore_card = Container(id="componentstore-card", classes="cockpit-card")
            componentstore_card.border_title = "Component Store"
            with componentstore_card:
                    yield Static("• [bold]This is a catalog of components[/bold]")
                    yield Static("• [bold]Here the user can pick a component to add it to the workspace[/bold]")

            # Right column
            with Vertical(id="hangar-right-column", classes="cockpit-col"):

                with Horizontal(id="panel-and-hangar"):
                    workspace_card = Container(id="workspace-card", classes="cockpit-card")
                    workspace_card.border_title = "Vehicle"
                    with workspace_card:
                        yield Static("• [bold]Here all the component comprising the vehicle are displayed[/bold]")
                        yield Static("• [bold]The user can drop a component here to add it to the vehicle[/bold]")

                    hangar_card = Container(id="hangar-library-card", classes="cockpit-card")
                    hangar_card.border_title = "Hangar"
                    with hangar_card:
                        yield Static("• [bold]The user can see vehicles here[/bold]")
                        yield Static("• [bold]Browse and pick the vehicles that are displayed in the workspace[/bold]")

                # Right column bottom: Component parameters
                component_stat_card = Container(id="component-preview-card", classes="cockpit-card")
                component_stat_card.border_title = "Component Parameters"
                with component_stat_card:
                    yield Static(
                        "Nothing to show\n\nSelect a component to see details.",
                        id="component-preview",
                    )

    def refresh_vehicle_library(self) -> None:
        """Scan the filesystem to discover user vehicles and reference examples."""
        pass

    def inspect_vehicle(self, vehicle_name: str) -> BaseVehicleConfig | None:
        """Load and display detailed metadata and component composition for a vehicle.

        Args:
            vehicle_name: Name of the target vehicle to inspect.

        Returns:
            The loaded BaseVehicleConfig instance, or None if loading failed.
        """
        raise NotImplementedError

    def fork_reference_example(self, example_name: str, target_name: str) -> Path:
        """Clone a read-only reference example into a new writable user directory.

        Args:
            example_name: Identifier of the source template in Hangar/examples/.
            target_name: Identifier for the new vehicle in Hangar/<target_name>/.

        Returns:
            Destination path to the cloned TOML configuration file.
        """
        raise NotImplementedError

    def delete_user_vehicle(self, vehicle_name: str) -> bool:
        """Safely remove a user vehicle configuration from the Hangar directory.

        Args:
            vehicle_name: Identifier of the vehicle to delete.

        Returns:
            True if deletion succeeded, False otherwise.
        """
        raise NotImplementedError

    def switch_to_assembly(self, vehicle_name: str | None = None) -> None:
        """Switch view into assembly mode to edit or construct a vehicle.

        Args:
            vehicle_name: Identifier of an existing vehicle to edit, or None for a new blank canvas.
        """
        pass

    def switch_to_library(self) -> None:
        """Switch view back to the vehicle library browser."""
        pass
