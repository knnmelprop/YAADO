"""Main view (Tab 1) serving as the default landing cockpit and telemetry dashboard.

Displays environment readiness (verified physics solvers), active vehicle summary,
recent simulation run activity from FlightLogs, and quick launchpad navigation actions.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from textual import events, on
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Label, Static, Tree

from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig

if TYPE_CHECKING:
    from textual.app import ComposeResult


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
                    tree: Tree[Path | None] = Tree("Hangar", id="hangar-tree")
                    tree.show_root = False
                    tree.guide_depth = 2
                    self._populate_hangar_tree(tree)
                    yield tree
                    btn = Button("➕ New Vehicle", id="new-vehicle-btn")
                    btn.can_focus = False
                    yield btn

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
                        "[dim]Select a vehicle or action in Hangar to inspect configuration telemetry.[/dim]",
                        id="preview-content",
                    )

    def _populate_hangar_tree(self, tree: Tree[Path | None]) -> None:
        """Scan filesystem and populate the Hangar vehicle tree.

        Args:
            tree: The Tree widget to populate with discovered configurations.
        """
        repo_root = Path(__file__).resolve().parents[2]
        hangar_dir = repo_root / "Hangar"
        examples_dir = hangar_dir / "examples"

        # 1. Reference examples
        examples_node = tree.root.add("📁 [bold]Reference Examples[/bold]", expand=True)
        if examples_dir.is_dir():
            for toml_path in sorted(examples_dir.rglob("*.toml")):
                vehicle_name = toml_path.stem.replace("_", " ")
                examples_node.add_leaf(f"🚀 {vehicle_name}", data=toml_path)

        # 2. User projects
        user_node = tree.root.add("📁 [bold]User Vehicles[/bold]", expand=True)
        user_tomls: list[Path] = []
        if hangar_dir.is_dir():
            for p in sorted(hangar_dir.rglob("*.toml")):
                if not p.is_relative_to(examples_dir):
                    user_tomls.append(p)
        if user_tomls:
            for toml_path in user_tomls:
                user_node.add_leaf(f"🚀 {toml_path.stem.replace('_', ' ')}", data=toml_path)
        else:
            user_node.add_leaf("[dim](No custom vehicles yet)[/dim]", data=None)

    def _format_vehicle_preview(self, config: BaseVehicleConfig, path: Path) -> str:
        """Format vehicle configuration into rich preview text.

        Args:
            config: Parsed vehicle configuration model.
            path: Source file path on disk.

        Returns:
            Rich-formatted string displaying vehicle specifications and dimensions.
        """
        lines: list[str] = [
            f"[bold amber]🚀 {config.name}[/bold amber]",
            f"[dim]{path.name} ({path.parent.name})[/dim]",
            "",
        ]

        if config.bodies:
            lines.append("[bold cyan]Body Components:[/bold cyan]")
            for name, body in config.bodies.items():
                body_type = getattr(body, "type", "Body").replace("_", " ")
                specs: list[str] = []
                if hasattr(body, "length") and body.length is not None:
                    specs.append(f"Length: {body.length:.2f} m")
                if hasattr(body, "diameter") and body.diameter is not None:
                    specs.append(f"Diameter: {body.diameter:.2f} m")
                specs_str = f" ({', '.join(specs)})" if specs else ""
                lines.append(f"  • [bold]{name}[/bold] - {body_type}{specs_str}")

        if config.propulsion:
            lines.append("\n[bold cyan]Propulsion Networks:[/bold cyan]")
            for name, prop in config.propulsion.items():
                prop_type = getattr(prop, "type", "Engine").replace("_", " ")
                specs = []
                if hasattr(prop, "thrust") and prop.thrust is not None:
                    specs.append(f"Thrust: {prop.thrust:,.0f} N")
                elif hasattr(prop, "thrust_mean") and prop.thrust_mean is not None:
                    specs.append(f"Mean Thrust: {prop.thrust_mean:,.0f} N")
                if hasattr(prop, "burn_time") and prop.burn_time is not None:
                    specs.append(f"Burn: {prop.burn_time:.1f} s")
                if hasattr(prop, "isp") and prop.isp is not None:
                    specs.append(f"Isp: {prop.isp:.1f} s")
                elif hasattr(prop, "isp_sl") and prop.isp_sl is not None:
                    specs.append(f"Isp(SL): {prop.isp_sl:.1f} s")
                specs_str = f" ({', '.join(specs)})" if specs else ""
                lines.append(f"  • [bold]{name}[/bold] - {prop_type}{specs_str}")

        if config.aero_surfaces:
            lines.append("\n[bold cyan]Aerodynamic Surfaces:[/bold cyan]")
            for name, aero in config.aero_surfaces.items():
                aero_type = getattr(aero, "type", "Surface").replace("_", " ")
                specs = []
                if hasattr(aero, "span") and aero.span is not None:
                    specs.append(f"Span: {aero.span:.2f} m")
                if hasattr(aero, "aspect_ratio") and aero.aspect_ratio is not None:
                    specs.append(f"AR: {aero.aspect_ratio:.2f}")
                specs_str = f" ({', '.join(specs)})" if specs else ""
                lines.append(f"  • [bold]{name}[/bold] - {aero_type}{specs_str}")

        lines.extend([
            "",
            "[dim]" + "─" * 45 + "[/dim]",
            "[bold green]▶ Press Enter to open in Hangar Workshop[/bold green]",
        ])
        return "\n".join(lines)

    @on(Tree.NodeHighlighted, "#hangar-tree")
    def on_hangar_node_highlighted(self, event: Tree.NodeHighlighted[Path | None]) -> None:
        """Update the preview card when a tree node is highlighted.

        Args:
            event: The node highlighted event with node reference.
        """
        self._update_preview(event.node.data)

    @on(events.MouseMove, "#hangar-tree")
    def on_hangar_tree_mouse_move(self, event: events.MouseMove) -> None:
        """Preview vehicle configuration on mouse hover.

        Args:
            event: Mouse move event containing cursor coordinates.
        """
        tree = self.query_one("#hangar-tree", Tree)
        line_index = event.y + tree.scroll_offset.y
        node = tree.get_node_at_line(line_index)
        if node is not None and node.data is not None:
            self._update_preview(node.data)

    def _update_preview(self, data: Path | None) -> None:
        """Update the preview card with the given vehicle file data or placeholder.

        Args:
            data: Optional Path to vehicle TOML file.
        """
        preview = self.query_one("#preview-content", Static)
        if isinstance(data, Path) and data.is_file():
            try:
                config = BaseVehicleConfig.from_toml(data)
                preview.update(self._format_vehicle_preview(config, data))
            except Exception as exc:
                preview.update(f"[red]Error loading vehicle:[/red]\n{exc}")
        else:
            preview.update("[dim]Select a vehicle or action in Hangar to inspect configuration telemetry.[/dim]")

    @on(Button.Pressed, "#new-vehicle-btn")
    def on_new_vehicle_pressed(self) -> None:
        """Switch to Hangar workspace when New Vehicle button is pressed."""
        from Terminal.app import YaadoApp

        if isinstance(self.app, YaadoApp):
            self.app.call_after_refresh(self.app.action_switch_tab, "hangar")

    @on(events.Enter, "#new-vehicle-btn")
    def on_new_vehicle_hover(self) -> None:
        """Show template options preview when hovering the New Vehicle button."""
        preview = self.query_one("#preview-content", Static)
        preview.update(
            "[bold cyan]➕ Create New Vehicle[/bold cyan]\n\n"
            "Launch the vehicle assembly wizard to build a new configuration from a template:\n\n"
            "  • [bold]Solid Motor Rocket[/bold] (Sounding rocket / Ballistic missile)\n"
            "  • [bold]Turbojet Cruise Vehicle[/bold] (Subsonic cruise / Drone)\n"
            "  • [bold]Ramjet High-Speed Missile[/bold] (Supersonic / Hypersonic)\n\n"
            "[dim]" + "─" * 45 + "[/dim]\n"
            "[bold green]▶ Click or press Enter to launch Template Wizard[/bold green]"
        )

    @on(events.Leave, "#new-vehicle-btn")
    def on_new_vehicle_leave(self) -> None:
        """Restore preview to selected vehicle or placeholder when mouse leaves button."""
        tree = self.query_one("#hangar-tree", Tree)
        cursor_node = tree.cursor_node
        self._update_preview(cursor_node.data if cursor_node is not None else None)

    @on(events.Key)
    def on_key(self, event: events.Key) -> None:
        """Open Hangar workshop only when Enter is explicitly pressed on a vehicle.

        Args:
            event: The key event containing the pressed key.
        """
        if event.key == "enter":
            try:
                tree = self.query_one("#hangar-tree", Tree)
            except Exception:
                return

            if tree.has_focus and tree.cursor_node is not None:
                if isinstance(tree.cursor_node.data, Path):
                    from Terminal.app import YaadoApp

                    if isinstance(self.app, YaadoApp):
                        self.app.call_after_refresh(self.app.action_switch_tab, "hangar")
