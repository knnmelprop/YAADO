"""Main view (Tab 1) serving as the default landing cockpit and telemetry dashboard.

Displays environment readiness (verified physics solvers), active vehicle summary,
recent simulation run activity from FlightLogs, and quick launchpad navigation actions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from textual import events, on
from textual.binding import Binding, BindingType
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Static, Tree

from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig

if TYPE_CHECKING:
    from textual.app import ComposeResult

class HangarTree(Tree[Path | None]):
    """Tree widget for browsing Hangar vehicle configurations."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "open_selected", "Open in Hangar", show=True),
    ]

    def action_open_selected(self) -> None:
        """Open the highlighted vehicle in Hangar Workshop."""
        if (
            self.cursor_node is not None
            and isinstance(self.cursor_node.data, Path)
            and self.cursor_node.data.is_file()
        ):
            from Terminal.app import YaadoApp

            if isinstance(self.app, YaadoApp):
                self.app.call_after_refresh(self.app.action_switch_tab, "hangar")

    def on_click(self, event: events.Click) -> None:
        """Open vehicle on double click."""
        if event.chain == 2:
            self.action_open_selected()


class FlightLogsTree(Tree[Path | None]):
    """Tree widget for browsing simulation history runs."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "open_selected", "Open in Flight Deck", show=True),
    ]

    def action_open_selected(self) -> None:
        """Open the highlighted simulation run in Flight Deck."""
        if (
            self.cursor_node is not None
            and isinstance(self.cursor_node.data, Path)
            and (self.cursor_node.data / "results.json").is_file()
        ):
            from Terminal.app import YaadoApp

            if isinstance(self.app, YaadoApp):
                self.app.call_after_refresh(self.app.action_switch_tab, "flight-deck")

    def on_click(self, event: events.Click) -> None:
        """Open simulation run on double click."""
        if event.chain == 2:
            self.action_open_selected()


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
                    tree = HangarTree("Hangar", id="hangar-tree")
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
                    tree_fl = FlightLogsTree("FlightLogs", id="flightlogs-tree")
                    tree_fl.show_root = False
                    tree_fl.guide_depth = 2
                    self._populate_flightlogs_tree(tree_fl)
                    yield tree_fl
                    btn_fl = Button("⚡ Run New Analysis", id="new-analysis-btn")
                    btn_fl.can_focus = False
                    yield btn_fl

            # Right column: Main window for info preview depending on the selected item
            with Vertical(id="right-column", classes="cockpit-col"):
                preview_card = Container(id="preview-card", classes="cockpit-card")
                preview_card.border_title = "Preview"
                with preview_card:
                    preview_content = Static(
                        "[dim]Select a vehicle or simulation run to inspect telemetry.[/dim]",
                        id="preview-content",
                    )
                    preview_content.can_focus = True
                    yield preview_content

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

    def _populate_flightlogs_tree(self, tree: Tree[Path | None]) -> None:
        """Scan filesystem and populate the FlightLogs history tree grouped by vehicle.

        Args:
            tree: The Tree widget to populate with discovered simulation runs.
        """
        repo_root = Path(__file__).resolve().parents[2]
        logs_dir = repo_root / "FlightLogs"
        if not logs_dir.is_dir():
            tree.root.add_leaf("[dim](No simulation runs yet)[/dim]", data=None)
            return

        vehicle_dirs = [
            d for d in sorted(logs_dir.iterdir())
            if d.is_dir() and not d.name.startswith((".", "__"))
        ]

        if not vehicle_dirs:
            tree.root.add_leaf("[dim](No simulation runs yet)[/dim]", data=None)
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
            v_node = tree.root.add(f"📁 [bold]{v_dir.name}[/bold]", expand=True, data=v_dir)
            for run_dir in runs:
                label = self._format_run_label(run_dir)
                v_node.add_leaf(label, data=run_dir)

        if not has_any_runs:
            tree.root.add_leaf("[dim](No simulation runs yet)[/dim]", data=None)

    def _format_run_label(self, run_dir: Path) -> str:
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
            pretty_analysis = self._pretty_analysis_name(analysis_slug)
            return f"📊 {pretty_analysis} [dim]{date_str[5:]} {formatted_time}[/dim]"

        return f"📊 {name.replace('_', ' ')}"

    def _pretty_analysis_name(self, slug: str) -> str:
        """Map analysis slugs to clean human-readable names.

        Args:
            slug: Raw analysis identifier.

        Returns:
            Human-readable analysis title.
        """
        mapping = {
            "point_mass_3dof_boost": "3-DOF Boost",
            "point_mass_3dof": "Point Mass 3-DOF",
            "aero_polar": "Aero Polars",
            "mass_estimation": "Mass & Inertia",
        }
        return mapping.get(slug, slug.replace("_", " ").title())

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
            f"[bold amber]🚀 {config.name}[/bold amber]",
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

    def _format_flightlog_preview(self, run_dir: Path) -> str:
        """Format simulation run telemetry into rich preview text using reflection.

        Args:
            run_dir: Path to the simulation run directory containing results.json.

        Returns:
            Rich-formatted string displaying simulation results in SI units.
        """
        results_file = run_dir / "results.json"
        if not results_file.is_file():
            return f"[bold amber]📊 {run_dir.name}[/bold amber]\n[dim](No results.json found)[/dim]"

        try:
            with open(results_file, encoding="utf-8") as f:
                res = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            return f"[red]Error parsing results.json:[/red]\n{exc}"

        vehicle = res.get("vehicle_name", run_dir.parent.name)
        analysis_name = res.get("analysis_name", run_dir.name)
        raw_ts = res.get("timestamp", "")
        if not raw_ts:
            parts = run_dir.name.rsplit("_", 2)
            if len(parts) >= 3 and "-" in parts[1]:
                raw_ts = f"{parts[1]}_{parts[2]}"
        formatted_ts = self._format_timestamp(raw_ts)
        fidelity = res.get("fidelity", "")
        data: dict[str, Any] = res.get("data", {})
        units_map: dict[str, str] = res.get("units", {})
        details: dict[str, Any] = res.get("details", {})
        headline_keys: list[str] = res.get("headline_metrics", [])

        # Fallback headline keys for existing logs if headline_metrics is empty
        if not headline_keys:
            candidate_headlines = (
                "apogee_altitude",
                "burnout_velocity",
                "burnout_mach",
                "q_max",
                "t_end_s",
                "final_x",
                "cl_max",
                "cd_min",
                "ld_max",
                "dry_mass",
                "total_mass",
            )
            headline_keys = [k for k in candidate_headlines if k in data]

        pretty_analysis = self._pretty_analysis_name(analysis_name)
        header_meta = f"Vehicle: {vehicle}"
        if formatted_ts:
            header_meta += f" • {formatted_ts}"
        if fidelity:
            header_meta += f" • {fidelity.replace('_', ' ').title()}"

        lines: list[str] = [
            f"[bold amber]📊 {pretty_analysis}[/bold amber]",
            f"[dim]{header_meta}[/dim]",
            "",
        ]

        # 1. Headline metrics section (curated prominent metrics)
        if headline_keys:
            lines.append("[bold cyan]Headline Metrics:[/bold cyan]")
            for k in headline_keys:
                if k in data:
                    val = data[k]
                    unit = units_map.get(k, "")
                    unit_str = f" {unit}" if unit and unit != "-" else ""
                    val_str = self._format_number(val)
                    extra_str = ""
                    if unit == "m" and isinstance(val, (int, float)) and abs(val) >= 1000:
                        extra_str = f" ({val / 1000:.2f} km)"
                    label = k.replace("_", " ").title()
                    lines.append(f"  • [bold]{label}:[/bold] {val_str}{unit_str}{extra_str}")
            lines.append("")

        # 2. Detailed scalar outputs (generic reflection of remaining metrics)
        remaining_keys = [k for k in sorted(data.keys()) if k not in headline_keys]
        if remaining_keys:
            lines.append("[bold cyan]Telemetry Metrics:[/bold cyan]")
            for k in remaining_keys:
                val = data[k]
                unit = units_map.get(k, "")
                unit_str = f" {unit}" if unit and unit != "-" else ""
                val_str = self._format_number(val)
                label = k.replace("_", " ").title()
                lines.append(f"  • {label}: {val_str}{unit_str}")

        # 3. Artifacts / Figures (if any)
        figures_dir = run_dir / "figures"
        if figures_dir.is_dir():
            figs = sorted([f.name for f in figures_dir.glob("*.png")])
            if figs:
                lines.append(f"\n[bold cyan]Generated Figures:[/bold cyan] [dim]{', '.join(figs)}[/dim]")

        # 4. Termination detail (factual, no "converged")
        stopped_reason = details.get("stopped_reason")
        if stopped_reason:
            reason_str = str(stopped_reason).replace("_", " ").title()
            lines.append(f"\n[bold]Flight Termination:[/bold] {reason_str}")

        return "\n".join(lines)

    def _format_vehicle_runs_preview(self, vehicle_dir: Path) -> str:
        """Format vehicle run overview into preview text.

        Args:
            vehicle_dir: Directory containing simulation runs for a vehicle.

        Returns:
            Rich-formatted summary of the vehicle's simulation history.
        """
        runs = [
            d for d in sorted(vehicle_dir.iterdir(), reverse=True)
            if d.is_dir() and not d.name.startswith((".", "__"))
        ]
        lines: list[str] = [
            f"[bold amber]📁 {vehicle_dir.name} — FlightLogs[/bold amber]",
            f"[dim]{len(runs)} simulation runs recorded[/dim]",
            "",
            "[bold cyan]Recent Runs:[/bold cyan]",
        ]
        for run in runs[:5]:
            lines.append(f"  • {self._format_run_label(run)}")

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

    def _update_flightlog_preview(self, data: Path | None) -> None:
        """Update preview card when a flightlog run or vehicle node is targeted.

        Args:
            data: Path to run directory or vehicle directory.
        """
        preview = self.query_one("#preview-content", Static)
        preview_card = self.query_one("#preview-card", Container)
        if isinstance(data, Path) and data.is_dir():
            if (data / "results.json").is_file():
                preview.update(self._format_flightlog_preview(data))
                preview_card.border_subtitle = "↵ Open in Flight Deck"
                self._current_preview_type = "flight-deck"
            else:
                preview.update(self._format_vehicle_runs_preview(data))
                preview_card.border_subtitle = "Select a run"
                self._current_preview_type = None
        else:
            preview.update("[dim]Select a vehicle or simulation run to inspect telemetry.[/dim]")
            preview_card.border_subtitle = None
            self._current_preview_type = None

    @on(Tree.NodeHighlighted, "#flightlogs-tree")
    def on_flightlog_node_highlighted(self, event: Tree.NodeHighlighted[Path | None]) -> None:
        """Update preview card when a flightlog tree node is highlighted.

        Args:
            event: The node highlighted event with node reference.
        """
        self._update_flightlog_preview(event.node.data)

    @on(events.MouseMove, "#flightlogs-tree")
    def on_flightlogs_tree_mouse_move(self, event: events.MouseMove) -> None:
        """Preview simulation run telemetry on mouse hover.

        Args:
            event: Mouse move event containing cursor coordinates.
        """
        tree = self.query_one("#flightlogs-tree", Tree)
        line_index = event.y + tree.scroll_offset.y
        node = tree.get_node_at_line(line_index)
        if node is not None and node.data is not None:
            self._update_flightlog_preview(node.data)

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
        preview.update(
            "[bold cyan]⚡ Run Simulation & Analysis[/bold cyan]\n\n"
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
        """Restore preview to currently targeted tree node or fallback placeholder."""
        fl_tree = self.query_one("#flightlogs-tree", FlightLogsTree)
        if fl_tree.has_focus and fl_tree.cursor_node is not None and fl_tree.cursor_node.data is not None:
            self._update_flightlog_preview(fl_tree.cursor_node.data)
            return

        hangar_tree = self.query_one("#hangar-tree", HangarTree)
        if hangar_tree.cursor_node is not None and hangar_tree.cursor_node.data is not None:
            self._update_preview(hangar_tree.cursor_node.data)
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
            self.query_one("#hangar-tree", HangarTree).focus()
        elif clicked_card is flightlogs_card:
            self.query_one("#flightlogs-tree", FlightLogsTree).focus()
