"""Main view (Tab 1) serving as the default landing cockpit and telemetry dashboard.

Displays environment readiness (verified physics solvers), active vehicle summary,
recent simulation run activity from FlightLogs, and quick launchpad navigation actions.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from textual import events, on
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, Static

from Terminal.widgets import (
    FlightLogsTree,
    VehicleTree,
    render_flightlog_preview,
)
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
        self._current_preview_type: str | None = None
        self._selected_vehicle_path: Path | None = None
        self._selected_flightlog_path: Path | None = None
        self._last_selected_source: Literal["hangar", "flightlogs"] = "hangar"

    def on_mount(self) -> None:
        """Initialize default selection and preview on mount."""
        hangar_tree = self.query_one("#hangar-tree", VehicleTree)
        first_path = hangar_tree.select_first_vehicle()
        if first_path:
            self._selected_vehicle_path = first_path
            self._last_selected_source = "hangar"
            self._update_preview(first_path)

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
                    yield VehicleTree(id="hangar-tree")
                    btn = Button("+ New Vehicle", id="new-vehicle-btn")
                    btn.can_focus = False
                    yield btn

                flightlogs_card = Container(id="flightlogs-card", classes="cockpit-card")
                flightlogs_card.border_title = "FlightLogs"
                flightlogs_card.border_subtitle = "↵ View  o Open  f Folder  d Delete"
                with flightlogs_card:
                    yield FlightLogsTree(id="flightlogs-tree")
                    btn_fl = Button("+ Run Analysis", id="new-analysis-btn")
                    btn_fl.can_focus = False
                    yield btn_fl

            # Right column: Main window for info preview depending on the selected item
            with Vertical(id="right-column", classes="cockpit-col"):
                preview_card = Container(id="preview-card", classes="cockpit-card")
                preview_card.border_title = "Preview"
                with preview_card, ScrollableContainer(id="preview-scroll"):
                    preview_content = Static(
                        "[dim]Select a vehicle or simulation run to inspect telemetry.[/dim]",
                        id="preview-content",
                    )
                    yield preview_content

    def _format_timestamp(self, ts: str) -> str:
        """Format a timestamp string into standard YYYY-MM-DD HH:MM:SS format.

        Args:
            ts: Raw timestamp string (e.g. '2026-09-20_195902').

        Returns:
            Formatted timestamp string with colon-separated time components.
        """
        if not ts:
            return ""
        if "_" in ts:
            date_part, time_part = ts.split("_", 1)
            if len(time_part) == 6 and time_part.isdigit():
                return f"{date_part} {time_part[:2]}:{time_part[2:4]}:{time_part[4:]}"
            if len(time_part) == 4 and time_part.isdigit():
                return f"{date_part} {time_part[:2]}:{time_part[2:]}"
            return f"{date_part} {time_part}"
        return ts

    def _format_number(self, val: Any) -> str:
        """Format a numeric or raw value cleanly with SI grouping.

        Args:
            val: Arbitrary value to format.

        Returns:
            Human-readable formatted string.
        """
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            if abs(val) >= 10_000 or (isinstance(val, int) and abs(val) >= 1_000):
                return f"{val:,.0f}"
            if abs(val) < 0.001 and val != 0:
                return f"{val:.2e}"
            if isinstance(val, float):
                formatted = f"{val:.2f}".rstrip("0").rstrip(".")
                return formatted if formatted else "0"
            return str(val)
        return str(val)

    def _format_component_summary(self, name: str, comp: Any) -> str:
        """Dynamically format any component using its Pydantic model and UNITS metadata.

        Args:
            name: Identifier/tag of the component in the vehicle configuration.
            comp: Pydantic component model instance.

        Returns:
            Rich-formatted line summarizing the component.
        """
        raw_type = getattr(comp, "type", comp.__class__.__name__)
        comp_type = str(raw_type).replace("_", " ").title()
        units_map: dict[str, str] = getattr(comp, "UNITS", {})
        headline_fields: tuple[str, ...] = getattr(comp, "HEADLINE_FIELDS", ())

        dump: dict[str, Any]
        if hasattr(comp, "model_dump"):
            dump = comp.model_dump(exclude_unset=True)
        else:
            dump = getattr(comp, "__dict__", {})

        fields_to_show: list[tuple[str, Any, str]] = []
        if headline_fields:
            for f in headline_fields:
                if f in dump and dump[f] is not None and not isinstance(dump[f], (dict, list)):
                    fields_to_show.append((f, dump[f], units_map.get(f, "")))
        else:
            for f, val in dump.items():
                if f in ("type", "name", "mass") or val is None or isinstance(val, (dict, list)):
                    continue
                fields_to_show.append((f, val, units_map.get(f, "")))
                if len(fields_to_show) >= 3:
                    break

        specs: list[str] = []
        for f_name, f_val, f_unit in fields_to_show:
            label = f_name.replace("_", " ").title()
            val_str = self._format_number(f_val)
            unit_str = f" {f_unit}" if f_unit and f_unit != "-" else ""
            specs.append(f"{label}: {val_str}{unit_str}")

        specs_str = f" ({', '.join(specs)})" if specs else ""
        return f"  • [bold]{name}[/bold] - {comp_type}{specs_str}"

    def _format_vehicle_preview(self, config: BaseVehicleConfig, path: Path) -> str:
        """Format vehicle configuration into rich preview text using schema reflection.

        Args:
            config: Parsed vehicle configuration model.
            path: Source file path on disk.

        Returns:
            Rich-formatted string displaying vehicle specifications and dimensions.
        """
        lines: list[str] = [
            f"[bold amber]{config.name}[/bold amber]",
            f"[dim]{path.name} ({path.parent.name})[/dim]",
            "",
        ]

        subsystems: list[tuple[str, dict[str, Any]]] = [
            ("Body Components", config.bodies),
            ("Propulsion Networks", config.propulsion),
            ("Aerodynamic Surfaces", config.aero_surfaces),
        ]

        for title, group in subsystems:
            if group:
                lines.append(f"[bold cyan]{title}:[/bold cyan]")
                for comp_name, comp in group.items():
                    lines.append(self._format_component_summary(comp_name, comp))
                lines.append("")

        if getattr(config, "mass_properties", None) is not None and config.mass_properties is not None:
            lines.append("[bold cyan]Mass Properties:[/bold cyan]")
            lines.append(self._format_component_summary("mass", config.mass_properties))

        return "\n".join(lines)

    @on(VehicleTree.VehicleHighlighted, "#hangar-tree")
    def on_hangar_vehicle_highlighted(self, event: VehicleTree.VehicleHighlighted) -> None:
        """Preview vehicle on cursor highlight or mouse hover.

        Args:
            event: Vehicle highlighted event containing vehicle path.
        """
        tree = self.query_one("#hangar-tree", VehicleTree)
        if event.path is not None:
            if tree.cursor_node and tree.cursor_node.data == event.path:
                self._selected_vehicle_path = event.path
                self._last_selected_source = "hangar"
            self._update_preview(event.path)
        else:
            self._restore_default_preview()

    @on(VehicleTree.VehicleSelected, "#hangar-tree")
    def on_hangar_vehicle_selected(self, event: VehicleTree.VehicleSelected) -> None:
        """Open the selected vehicle in Hangar Workshop on confirmation.

        Args:
            event: Vehicle selected event containing vehicle path.
        """
        from Terminal.app import YaadoApp

        if isinstance(self.app, YaadoApp):
            self.app.set_active_vehicle(event.path)
            self.app.call_after_refresh(self.app.action_switch_tab, "hangar")

    @on(FlightLogsTree.FlightLogHighlighted, "#flightlogs-tree")
    def on_flightlog_highlighted(self, event: FlightLogsTree.FlightLogHighlighted) -> None:
        """Preview simulation run on cursor highlight or mouse hover.

        Args:
            event: FlightLog highlighted event containing run or vehicle path.
        """
        tree = self.query_one("#flightlogs-tree", FlightLogsTree)
        if event.path is not None:
            if tree.cursor_node and tree.cursor_node.data == event.path:
                self._selected_flightlog_path = event.path
                self._last_selected_source = "flightlogs"
            self._update_flightlog_preview(event.path)
        else:
            self._restore_default_preview()

    @on(FlightLogsTree.FlightLogSelected, "#flightlogs-tree")
    def on_flightlog_selected(self, event: FlightLogsTree.FlightLogSelected) -> None:
        """Inspect the selected simulation run or file in the main preview pane.

        Args:
            event: FlightLog selected event containing run directory or file path.
        """
        self._selected_flightlog_path = event.path
        self._last_selected_source = "flightlogs"
        self._update_flightlog_preview(event.path)

    @on(FlightLogsTree.FlightLogDeleted, "#flightlogs-tree")
    def on_flightlog_deleted(self, event: FlightLogsTree.FlightLogDeleted) -> None:
        """Handle run deletion by resetting preview if active run was deleted."""
        if self._selected_flightlog_path is not None and (
            self._selected_flightlog_path == event.path
            or str(self._selected_flightlog_path).startswith(str(event.path))
        ):
            self._selected_flightlog_path = None
            self._restore_default_preview()

    @on(events.Leave, "#hangar-card")
    @on(events.Leave, "#flightlogs-card")
    def on_tree_card_leave(self) -> None:
        """Restore default preview when mouse leaves a cockpit card."""
        self._restore_default_preview()

    def _update_preview(self, data: Path | None) -> None:
        """Update the preview card with the given vehicle file data or placeholder.

        Args:
            data: Optional Path to vehicle TOML file.
        """
        preview = self.query_one("#preview-content", Static)
        preview.remove_class("-wide-table")
        preview_card = self.query_one("#preview-card", Container)
        if isinstance(data, Path) and data.is_file():
            try:
                config = BaseVehicleConfig.from_toml(data)
                preview.update(self._format_vehicle_preview(config, data))
                preview_card.border_subtitle = "↵ Open in Hangar"
                self._current_preview_type = "hangar"
            except (OSError, ValueError, KeyError) as exc:
                preview.update(f"[red]Error loading vehicle:[/red]\n{exc}")
                preview_card.border_subtitle = None
                self._current_preview_type = None
        else:
            preview.update("[dim]Select a vehicle or simulation run to inspect telemetry.[/dim]")
            preview_card.border_subtitle = None
            self._current_preview_type = None
        self._scroll_preview_to_top()

    def _update_flightlog_preview(self, data: Path | None) -> None:
        """Update preview card when a flightlog run, file, or vehicle node is targeted.

        Args:
            data: Path to run directory, artifact file, or vehicle directory.
        """
        preview = self.query_one("#preview-content", Static)
        preview_card = self.query_one("#preview-card", Container)
        if isinstance(data, Path):
            is_csv = data.is_file() and data.suffix.lower() == ".csv"
            preview.set_class(is_csv, "-wide-table")
            preview.update(render_flightlog_preview(data))
            preview_card.border_subtitle = "o Open  f Folder"
            self._current_preview_type = None
        else:
            preview.remove_class("-wide-table")
            preview.update("[dim]Select a vehicle or simulation run to inspect telemetry.[/dim]")
            preview_card.border_subtitle = None
            self._current_preview_type = None
        self._scroll_preview_to_top()

    def _scroll_preview_to_top(self) -> None:
        """Scroll the preview vertical container back to the top."""
        from textual.css.query import NoMatches
        try:
            scroll = self.query_one("#preview-scroll", ScrollableContainer)
            scroll.scroll_to(x=0, y=0, animate=False)
        except NoMatches:
            pass

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
        preview.remove_class("-wide-table")
        preview.update(
            "[bold cyan]Create New Vehicle[/bold cyan]\n\n"
            "Launch the vehicle assembly wizard to build a new configuration from a template:\n\n"
            "  • [bold]Solid Motor Rocket[/bold] (Sounding rocket / Ballistic missile)\n"
            "  • [bold]Turbojet Cruise Vehicle[/bold] (Subsonic cruise / Drone)\n"
            "  • [bold]Ramjet High-Speed Missile[/bold] (Supersonic / Hypersonic)"
        )
        self.query_one("#preview-card", Container).border_subtitle = "↵ Launch Wizard"

    @on(events.Leave, "#new-vehicle-btn")
    def on_new_vehicle_leave(self) -> None:
        """Restore preview to selected item or placeholder when mouse leaves button."""
        self._restore_default_preview()

    @on(Button.Pressed, "#new-analysis-btn")
    def on_new_analysis_pressed(self) -> None:
        """Switch to Flight Deck when Run Analysis button is pressed."""
        from Terminal.app import YaadoApp

        if isinstance(self.app, YaadoApp):
            self.app.call_after_refresh(self.app.action_switch_tab, "flight-deck")

    @on(events.Enter, "#new-analysis-btn")
    def on_new_analysis_hover(self) -> None:
        """Show simulation solver suite preview when hovering Run Analysis button."""
        preview = self.query_one("#preview-content", Static)
        preview.remove_class("-wide-table")
        preview.update(
            "[bold cyan]Run Simulation & Analysis[/bold cyan]\n\n"
            "Launch physics solvers and multi-stage pipelines from the Flight Deck:\n\n"
            "  • [bold]Point Mass 3-DOF Trajectory[/bold] (Ascent, boost, coast, and ballistic descent)\n"
            "  • [bold]Aerodynamic Polars[/bold] (Barrowman, AVL vortex lattice, empirical DATCOM)\n"
            "  • [bold]Propulsion & Cycle Analysis[/bold] (pyCycle thermodynamic engine models)"
        )
        self.query_one("#preview-card", Container).border_subtitle = "↵ Launch Flight Deck"

    @on(events.Leave, "#new-analysis-btn")
    def on_new_analysis_leave(self) -> None:
        """Restore preview when mouse leaves Run Analysis button."""
        self._restore_default_preview()

    def _restore_default_preview(self) -> None:
        """Restore preview to currently selected tree node or fallback placeholder."""
        if self._last_selected_source == "flightlogs":
            fl_tree = self.query_one("#flightlogs-tree", FlightLogsTree)
            target = (
                fl_tree.cursor_node.data
                if fl_tree.cursor_node and isinstance(fl_tree.cursor_node.data, Path)
                else self._selected_flightlog_path
            )
            if target is not None:
                self._update_flightlog_preview(target)
                return

        hangar_tree = self.query_one("#hangar-tree", VehicleTree)
        target_v = (
            hangar_tree.cursor_node.data
            if hangar_tree.cursor_node and isinstance(hangar_tree.cursor_node.data, Path)
            else self._selected_vehicle_path
        )
        if target_v is not None:
            self._update_preview(target_v)
            return

        if self._last_selected_source != "flightlogs":
            fl_tree = self.query_one("#flightlogs-tree", FlightLogsTree)
            target = (
                fl_tree.cursor_node.data
                if fl_tree.cursor_node and isinstance(fl_tree.cursor_node.data, Path)
                else self._selected_flightlog_path
            )
            if target is not None:
                self._update_flightlog_preview(target)
                return

        preview = self.query_one("#preview-content", Static)
        preview.update("[dim]Select a vehicle or simulation run to inspect telemetry.[/dim]")
        self.query_one("#preview-card", Container).border_subtitle = None
        self._current_preview_type = None

    @on(events.Key)
    def on_key(self, event: events.Key) -> None:
        """Handle Enter key when preview pane is active.

        Args:
            event: The key event containing the pressed key.
        """
        if event.key == "enter":
            from Terminal.app import YaadoApp

            if not isinstance(self.app, YaadoApp):
                return

            preview_content = self.query_one("#preview-content", Static)
            if preview_content.has_focus and self._current_preview_type:
                self.app.call_after_refresh(self.app.action_switch_tab, self._current_preview_type)

    @on(events.Click)
    def on_click(self, event: events.Click) -> None:
        """Clear or transfer card focus when clicking across dashboard panels.

        Args:
            event: Textual mouse click event.
        """
        if isinstance(event.widget, Button) or (
            event.widget is not None and isinstance(getattr(event.widget, "parent", None), Button)
        ):
            return

        hangar_card = self.query_one("#hangar-card", Container)
        flightlogs_card = self.query_one("#flightlogs-card", Container)
        preview_card = self.query_one("#preview-card", Container)

        current: Any = event.widget
        clicked_card: Container | None = None
        while current is not None and current is not self:
            if current in (hangar_card, flightlogs_card, preview_card):
                clicked_card = current
                break
            current = getattr(current, "parent", None)

        if clicked_card is None:
            self.app.set_focus(None)
        elif clicked_card is preview_card:
            self.query_one("#preview-content", Static).focus()
        elif clicked_card is hangar_card:
            self.query_one("#hangar-tree", VehicleTree).focus()
        elif clicked_card is flightlogs_card:
            self.query_one("#flightlogs-tree", FlightLogsTree).focus()
