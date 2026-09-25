"""Hangar view (Tab 2) unifying vehicle library inspection and interactive assembly.

Provides a complete vehicle workshop allowing users to browse configurations in Hangar/,
fork read-only reference templates from Hangar/examples/, and interactively build
or modify vehicles using the longitudinal spatial canvas and parameter forms.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import BaseModel
from textual import events, on
from textual.binding import Binding, BindingType
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from Terminal.Assembly.template_generator import VehicleTemplateGenerator
from Terminal.widgets import ComponentStoreView, ComponentTile, VehicleTree
from YAADO_Core.ComponentStore import (
    AERO_COMPONENTS,
    BODY_COMPONENTS,
    PROPULSION_COMPONENTS,
    MassProperties,
)
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig

if TYPE_CHECKING:
    from textual.app import ComposeResult


class VehicleComponentList(OptionList):
    """Component list for the active vehicle workspace."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("delete,backspace,d", "delete_selected", "Delete Component", show=True),
    ]

    def action_delete_selected(self) -> None:
        """Delete currently selected component from active vehicle."""
        parent: Any = self.parent
        while parent is not None and not isinstance(parent, HangarView):
            parent = getattr(parent, "parent", None)
        if isinstance(parent, HangarView):
            parent.delete_selected_component()


class HangarView(Container):
    """Unified vehicle manager and construction workspace.

    Attributes:
        hangar_root: Path to the root directory storing user vehicle configurations.
        examples_root: Path to read-only reference configuration examples.
        active_vehicle: Currently loaded BaseVehicleConfig instance.
        active_vehicle_path: Source file path for active_vehicle if saved to disk.
        selected_vehicle_name: Name of the currently selected vehicle, if any.
        current_mode: Active sub-mode ('library' for browsing or 'assembly' for building).
    """

    SUBSYSTEM_CATEGORIES: ClassVar[list[tuple[str, str, str, tuple[type[BaseModel], ...]]]] = [
        ("AIRFRAME", "BODY", "#3b82f6", BODY_COMPONENTS),
        ("PROPULSION", "PROP", "#f59e0b", PROPULSION_COMPONENTS),
        ("AERODYNAMICS", "AERO", "#0284c7", AERO_COMPONENTS),
        ("MASS & INERTIA", "MASS", "#94a3b8", (MassProperties,)),
    ]

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
        self.active_vehicle: BaseVehicleConfig | None = None
        self.active_vehicle_path: Path | None = None
        self.selected_vehicle_name: str | None = None
        self.current_mode: Literal["library", "assembly"] = "library"
        self._component_classes: dict[str, type[BaseModel]] = {}
        for _, _, _, comp_tuple in self.SUBSYSTEM_CATEGORIES:
            for comp_cls in comp_tuple:
                self._component_classes[comp_cls.__name__] = comp_cls

    def compose(self) -> ComposeResult:
        """Render the vehicle library browser and the assembly mode switcher.

        Yields:
            Child widgets comprising the Hangar workspace.
        """
        with Horizontal(id="hangar-layout"):
            # Left column: ComponentStore with Collapsible categories and draggable cards
            componentstore_card = Container(id="componentstore-card", classes="cockpit-card")
            componentstore_card.border_title = "Component Store"
            componentstore_card.border_subtitle = "[a] / Double-Click / Drag to Add"
            with componentstore_card:
                yield ComponentStoreView(id="component-store-view")

            # Right column
            with Vertical(id="hangar-right-column", classes="cockpit-col"):
                with Horizontal(id="panel-and-hangar"):
                    workspace_card = Container(id="workspace-card", classes="cockpit-card")
                    workspace_card.border_title = "Vehicle"
                    workspace_card.border_subtitle = "[d] Delete"
                    with workspace_card:
                        yield Static("", id="workspace-header")
                        yield Static("", id="workspace-schematic")
                        yield VehicleComponentList(id="vehicle-components-list")

                    hangar_card = Container(id="hangar-library-card", classes="cockpit-card")
                    hangar_card.border_title = "Hangar"
                    with hangar_card:
                        yield VehicleTree(id="hangar-library-tree")
                        with Horizontal(id="hangar-library-buttons"):
                            btn_new = Button("+ New", id="hangar-new-vehicle-btn")
                            btn_new.can_focus = False
                            yield btn_new
                            btn_fork = Button("Fork", id="hangar-fork-btn")
                            btn_fork.can_focus = False
                            yield btn_fork

                # Right column bottom: Component parameters
                component_stat_card = Container(id="component-preview-card", classes="cockpit-card")
                component_stat_card.border_title = "Component Parameters"
                with component_stat_card:
                    yield Static(
                        "[dim]Highlight a component in the store or workspace to inspect its parameters.[/dim]",
                        id="component-preview",
                    )

    def on_mount(self) -> None:
        """Initialize active vehicle on startup."""
        from Terminal.app import YaadoApp

        if isinstance(self.app, YaadoApp) and self.app.active_vehicle is not None:
            self.load_vehicle(self.app.active_vehicle, self.app.active_vehicle_path)
        elif self.active_vehicle is None:
            tree = self.query_one("#hangar-library-tree", VehicleTree)
            first_path = tree.select_first_vehicle()
            if first_path:
                self.load_vehicle(path=first_path)
            else:
                self._refresh_workspace()

    def _pretty_component_name(self, name: str) -> str:
        """Format PascalCase component class name into clean spaced words.

        Args:
            name: PascalCase string (e.g. AxisymmetricBody).

        Returns:
            Space-separated string (e.g. Axisymmetric Body).
        """
        return re.sub(r"(?<!^)(?=[A-Z])", " ", name)

    def _format_component_schema_preview(self, comp_cls: type[BaseModel]) -> str:
        """Format component schema parameters, units, and docstring into preview text.

        Args:
            comp_cls: Pydantic component model class.

        Returns:
            Rich-formatted string detailing component parameters.
        """
        pretty_name = self._pretty_component_name(comp_cls.__name__)
        units_map: dict[str, str] = getattr(comp_cls, "UNITS", {})
        headline_fields: tuple[str, ...] = getattr(comp_cls, "HEADLINE_FIELDS", ())

        lines: list[str] = [
            f"[bold amber]{pretty_name}[/bold amber]",
        ]

        doc = (comp_cls.__doc__ or "").strip().split("\n")[0]
        if doc:
            lines.append(f"[dim]{doc}[/dim]")
        lines.append("")

        lines.append("[bold cyan]Parameters:[/bold cyan]")
        from rich.markup import escape

        for name, field in comp_cls.model_fields.items():
            if name == "type":
                continue
            unit = units_map.get(name, "")
            unit_str = f" [bold #94a3b8][{unit}][/bold #94a3b8]" if unit and unit != "-" else ""
            marker = "[bold #f59e0b]★[/bold #f59e0b] " if name in headline_fields else "  • "
            desc = escape(field.description or "")
            lines.append(f"{marker}[bold]{name}[/bold]{unit_str} - [dim]{desc}[/dim]")

        return "\n".join(lines)

    def _format_installed_component_preview(self, comp_name: str, comp: BaseModel) -> str:
        """Format installed component parameter values, units, and descriptions.

        Args:
            comp_name: Installed component identifier on the active vehicle.
            comp: Pydantic component model instance.

        Returns:
            Rich-formatted string showing current parameter values and schema units.
        """
        cls_name = comp.__class__.__name__
        pretty_type = self._pretty_component_name(cls_name)
        units_map: dict[str, str] = getattr(comp, "UNITS", {})
        headline_fields: tuple[str, ...] = getattr(comp, "HEADLINE_FIELDS", ())

        lines: list[str] = [
            f"[bold amber]{comp_name}[/bold amber] [dim]({pretty_type})[/dim]",
        ]

        doc = (comp.__doc__ or "").strip().split("\n")[0]
        if doc:
            lines.append(f"[dim]{doc}[/dim]")
        lines.append("")
        lines.append("[bold cyan]Parameters & Values:[/bold cyan]")

        from rich.markup import escape

        for name, field in comp.__class__.model_fields.items():
            if name == "type":
                continue
            val = getattr(comp, name, None)
            unit = units_map.get(name, "")
            unit_str = f" [bold #94a3b8][{unit}][/bold #94a3b8]" if unit and unit != "-" else ""
            marker = "[bold #f59e0b]★[/bold #f59e0b] " if name in headline_fields else "  • "

            if val is None:
                val_str = "[dim]None[/dim]"
            elif isinstance(val, float):
                val_str = f"[bold green]{val:.4g}[/bold green]"
            else:
                val_str = f"[bold green]{escape(str(val))}[/bold green]"

            desc = f"  [dim]- {escape(field.description)}[/dim]" if field.description else ""
            lines.append(f"{marker}[bold]{name}[/bold]{unit_str} = {val_str}{desc}")

        return "\n".join(lines)

    def _generate_ascii_schematic(self, vehicle: BaseVehicleConfig) -> str:
        """Generate longitudinal schematic representation of the vehicle assembly.

        Args:
            vehicle: BaseVehicleConfig instance to summarize.

        Returns:
            Single-line ASCII schematic of the assembled components.
        """
        stages: list[str] = ["◄ NOSE"]
        for name in vehicle.bodies:
            stages.append(f"[{name}]")
        for name in vehicle.aero_surfaces:
            stages.append(f"[{name}]")
        for name in vehicle.propulsion:
            stages.append(f"[{name}]")
        if vehicle.mass_properties is not None:
            stages.append("[⌖ CG]")
        stages.append("EXHAUST ►")
        return " ══ ".join(stages)

    def _refresh_workspace(self) -> None:
        """Refresh workspace header, ASCII schematic, and component list."""
        workspace_card = self.query_one("#workspace-card", Container)
        workspace_header = self.query_one("#workspace-header", Static)
        workspace_schematic = self.query_one("#workspace-schematic", Static)
        comp_list = self.query_one("#vehicle-components-list", VehicleComponentList)

        if self.active_vehicle is None:
            workspace_card.border_title = "Vehicle Workspace"
            workspace_card.border_subtitle = "No Vehicle Loaded"
            workspace_header.update("[dim]No vehicle loaded. Select from library or click '+ New'.[/dim]")
            workspace_schematic.update("")
            comp_list.clear_options()
            comp_list.add_option(Option("[dim]No components loaded.[/dim]", disabled=True))
            return

        vehicle = self.active_vehicle
        workspace_card.border_title = f"Vehicle: {vehicle.name}"
        comp_count = len(vehicle.all_components())
        if vehicle.mass_properties is not None:
            comp_count += 1
        workspace_card.border_subtitle = f"{comp_count} Components • [d] Delete"

        mass_str = (
            f"  [dim]•[/dim]  [bold #94a3b8]{vehicle.total_mass:.1f} kg[/bold #94a3b8]"
            if vehicle.total_mass is not None
            else ""
        )
        n_body = len(vehicle.bodies)
        n_aero = len(vehicle.aero_surfaces)
        n_prop = len(vehicle.propulsion)
        header_text = (
            f"[bold white]{vehicle.name}[/bold white]"
            f"{mass_str}  [dim]•[/dim]  "
            f"[bold #3b82f6]{n_body} Body[/bold #3b82f6]  [dim]•[/dim]  "
            f"[bold #0284c7]{n_aero} Aero[/bold #0284c7]  [dim]•[/dim]  "
            f"[bold #f59e0b]{n_prop} Prop[/bold #f59e0b]"
        )
        workspace_header.update(header_text)
        workspace_schematic.update(self._generate_ascii_schematic(vehicle))

        comp_list.clear_options()
        has_items = False

        for name, body_comp in vehicle.bodies.items():
            has_items = True
            prompt = f"[bold #3b82f6][BODY][/bold #3b82f6]  [bold]{name}[/bold]  [dim]({body_comp.__class__.__name__})[/dim]"
            comp_list.add_option(Option(prompt, id=f"comp:BODY:{name}"))

        for name, aero_comp in vehicle.aero_surfaces.items():
            has_items = True
            prompt = f"[bold #0284c7][AERO][/bold #0284c7]  [bold]{name}[/bold]  [dim]({aero_comp.__class__.__name__})[/dim]"
            comp_list.add_option(Option(prompt, id=f"comp:AERO:{name}"))

        for name, prop_comp in vehicle.propulsion.items():
            has_items = True
            prompt = f"[bold #f59e0b][PROP][/bold #f59e0b]  [bold]{name}[/bold]  [dim]({prop_comp.__class__.__name__})[/dim]"
            comp_list.add_option(Option(prompt, id=f"comp:PROP:{name}"))

        if vehicle.mass_properties is not None:
            has_items = True
            prompt = "[bold #94a3b8][MASS][/bold #94a3b8]  [bold]mass_properties[/bold]  [dim](MassProperties)[/dim]"
            comp_list.add_option(Option(prompt, id="comp:MASS:mass_properties"))

        if not has_items:
            comp_list.add_option(Option("[dim]Vehicle frame is empty. Add from Component Store (left).[/dim]", disabled=True))
        else:
            comp_list.highlighted = 0

    def load_vehicle(
        self,
        config: BaseVehicleConfig | None = None,
        path: Path | None = None,
    ) -> None:
        """Load a vehicle configuration into the Hangar workspace.

        Args:
            config: Optional pre-loaded BaseVehicleConfig instance.
            path: Optional filesystem path to the TOML configuration file.
        """
        if config is not None:
            self.active_vehicle = config
            self.active_vehicle_path = path
            self.selected_vehicle_name = config.name
        elif path is not None and path.is_file():
            try:
                self.active_vehicle = BaseVehicleConfig.from_toml(path)
                self.active_vehicle_path = path
                self.selected_vehicle_name = self.active_vehicle.name
            except (OSError, ValueError, KeyError) as exc:
                self.notify(f"Failed to load vehicle: {exc}", severity="error")
                return

        from Terminal.app import YaadoApp

        if isinstance(self.app, YaadoApp):
            self.app.active_vehicle = self.active_vehicle
            self.app.active_vehicle_path = self.active_vehicle_path

        self._refresh_workspace()

    def _generate_unique_component_key(self, base: str, existing: dict[str, Any]) -> str:
        """Generate a unique key within the vehicle subsystem dictionary.

        Args:
            base: Suggested prefix name.
            existing: Existing component dictionary to avoid collision with.

        Returns:
            A unique component identifier string.
        """
        all_keys = set(self.active_vehicle.all_components().keys()) if self.active_vehicle else set()
        if base not in all_keys and base not in existing:
            return base
        idx = 1
        while f"{base}_{idx}" in all_keys or f"{base}_{idx}" in existing:
            idx += 1
        return f"{base}_{idx}"

    def _save_active_vehicle_if_writable(self) -> None:
        """Save active vehicle to disk if it resides in a writable user directory."""
        if self.active_vehicle is None or self.active_vehicle_path is None:
            return
        try:
            if self.active_vehicle_path.resolve().is_relative_to(self.examples_root.resolve()):
                return
            self.active_vehicle.to_toml(self.active_vehicle_path)
        except (OSError, ValueError) as exc:
            self.notify(f"Auto-save failed: {exc}", severity="warning")

    def add_component_to_vehicle(self, comp_cls_name: str | None) -> None:
        """Instantiate and attach a component from the store to the active vehicle.

        Args:
            comp_cls_name: Class name of the component to add.
        """
        if not comp_cls_name or comp_cls_name not in self._component_classes:
            return

        comp_cls = self._component_classes[comp_cls_name]
        try:
            new_comp = VehicleTemplateGenerator.prefill_component_values(comp_cls)
        except (ValueError, KeyError, TypeError):
            new_comp = comp_cls.model_construct()

        if self.active_vehicle is None:
            self.active_vehicle = BaseVehicleConfig(name="Custom_Vehicle")
            self.selected_vehicle_name = "Custom_Vehicle"
            self.active_vehicle_path = self.hangar_root / "Custom_Vehicle" / "Custom_Vehicle.toml"

        vehicle = self.active_vehicle
        key: str = ""

        if isinstance(new_comp, MassProperties):
            vehicle.mass_properties = new_comp
            key = "mass_properties"
        elif isinstance(new_comp, BODY_COMPONENTS):
            base_key = "fuselage" if "Axisymmetric" in comp_cls_name else "body"
            key = self._generate_unique_component_key(base_key, vehicle.bodies)
            vehicle.bodies[key] = new_comp
        elif isinstance(new_comp, AERO_COMPONENTS):
            base_key = "wings" if "Wings" in comp_cls_name else ("fins" if "Fins" in comp_cls_name else "surface")
            key = self._generate_unique_component_key(base_key, vehicle.aero_surfaces)
            vehicle.aero_surfaces[key] = new_comp
        elif isinstance(new_comp, PROPULSION_COMPONENTS):
            base_key = "booster" if "Solid" in comp_cls_name else ("ramjet" if "Ramjet" in comp_cls_name else "engine")
            key = self._generate_unique_component_key(base_key, vehicle.propulsion)
            vehicle.propulsion[key] = new_comp

        self._save_active_vehicle_if_writable()
        self._refresh_workspace()

        workspace_card = self.query_one("#workspace-card", Container)
        workspace_card.border_subtitle = f"Added {comp_cls.__name__} [{key}]"

    def delete_selected_component(self) -> None:
        """Delete currently highlighted component in the active vehicle."""
        if self.active_vehicle is None:
            return
        comp_list = self.query_one("#vehicle-components-list", VehicleComponentList)
        if comp_list.highlighted is None:
            return
        opt = comp_list.get_option_at_index(comp_list.highlighted)
        if not opt.id or not opt.id.startswith("comp:"):
            return

        _, category, name = opt.id.split(":", 2)
        if category == "MASS":
            self.active_vehicle.mass_properties = None
        elif category == "BODY" and name in self.active_vehicle.bodies:
            del self.active_vehicle.bodies[name]
        elif category == "AERO" and name in self.active_vehicle.aero_surfaces:
            del self.active_vehicle.aero_surfaces[name]
        elif category == "PROP" and name in self.active_vehicle.propulsion:
            del self.active_vehicle.propulsion[name]

        self._save_active_vehicle_if_writable()
        self._refresh_workspace()
        workspace_card = self.query_one("#workspace-card", Container)
        workspace_card.border_subtitle = f"Deleted {name}"

    @on(ComponentTile.ComponentHighlighted)
    def on_component_tile_highlighted(self, event: ComponentTile.ComponentHighlighted) -> None:
        """Update component preview card with the schema details of highlighted component tile.

        Args:
            event: Component tile highlighted event.
        """
        if event.comp_id and event.comp_id in self._component_classes:
            comp_cls = self._component_classes[event.comp_id]
            preview_card = self.query_one("#component-preview-card", Container)
            preview_card.border_title = f"Store: {comp_cls.__name__}"
            preview_card.border_subtitle = "[a] / Double-Click / Drag to Add"
            preview = self.query_one("#component-preview", Static)
            preview.update(self._format_component_schema_preview(comp_cls))

    @on(ComponentTile.ComponentSelected)
    def on_component_tile_selected(self, event: ComponentTile.ComponentSelected) -> None:
        """Add component from store into active vehicle via double-click, 'a' key, or drag-and-drop.

        Args:
            event: Component tile selected event.
        """
        self.add_component_to_vehicle(event.comp_id)

    @on(OptionList.OptionHighlighted, "#vehicle-components-list")
    def on_vehicle_component_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Display live parameter values of highlighted vehicle component.

        Args:
            event: Textual option highlighted event.
        """
        if self.active_vehicle is None or not event.option_id or not event.option_id.startswith("comp:"):
            return

        _, category, name = event.option_id.split(":", 2)
        comp: BaseModel | None = None
        if category == "MASS":
            comp = self.active_vehicle.mass_properties
        elif category == "BODY":
            comp = self.active_vehicle.bodies.get(name)
        elif category == "AERO":
            comp = self.active_vehicle.aero_surfaces.get(name)
        elif category == "PROP":
            comp = self.active_vehicle.propulsion.get(name)

        if comp is not None:
            preview_card = self.query_one("#component-preview-card", Container)
            preview_card.border_title = f"Component: {name} ({comp.__class__.__name__})"
            preview_card.border_subtitle = "[d] Delete from Vehicle"
            preview = self.query_one("#component-preview", Static)
            preview.update(self._format_installed_component_preview(name, comp))

    @on(VehicleTree.VehicleHighlighted, "#hangar-library-tree")
    def on_hangar_library_node_highlighted(self, event: VehicleTree.VehicleHighlighted) -> None:
        """Update subtitle hint when a vehicle is highlighted in the library.

        Args:
            event: Vehicle highlighted event containing vehicle path.
        """
        hangar_card = self.query_one("#hangar-library-card", Container)
        if event.path is not None:
            hangar_card.border_subtitle = "↵ Load to Workspace"
        else:
            hangar_card.border_subtitle = ""

    @on(VehicleTree.VehicleSelected, "#hangar-library-tree")
    def on_hangar_library_vehicle_selected(self, event: VehicleTree.VehicleSelected) -> None:
        """Load vehicle when confirmed via Enter or double-click.

        Args:
            event: Vehicle selected event containing vehicle path.
        """
        self.load_vehicle(path=event.path)

    @on(Button.Pressed, "#hangar-new-vehicle-btn")
    def on_new_vehicle_btn_pressed(self) -> None:
        """Create a new blank vehicle and mount it in the workspace."""
        idx = 1
        while (self.hangar_root / f"Vehicle_{idx}").exists():
            idx += 1
        name = f"Vehicle_{idx}"
        new_vehicle = BaseVehicleConfig(name=name)
        new_path = self.hangar_root / name / f"{name}.toml"
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_vehicle.to_toml(new_path)
        self.load_vehicle(config=new_vehicle, path=new_path)
        tree = self.query_one("#hangar-library-tree", VehicleTree)
        tree.populate()
        self.notify(f"Created new vehicle {name}", severity="information")

    @on(Button.Pressed, "#hangar-fork-btn")
    def on_fork_vehicle_btn_pressed(self) -> None:
        """Fork the currently highlighted reference example into a new user vehicle."""
        tree = self.query_one("#hangar-library-tree", VehicleTree)
        if tree.cursor_node is None or not isinstance(tree.cursor_node.data, Path):
            self.notify("Select a reference example in the tree first.", severity="warning")
            return
        src_path = tree.cursor_node.data
        if not src_path.resolve().is_relative_to(self.examples_root.resolve()):
            self.notify("Only reference examples can be forked.", severity="warning")
            return

        example_name = src_path.parent.name
        idx = 1
        target_name = f"{example_name}_custom"
        while (self.hangar_root / target_name).exists():
            idx += 1
            target_name = f"{example_name}_custom_{idx}"

        dest_path = self.fork_reference_example(example_name, target_name)
        tree.populate()
        self.load_vehicle(path=dest_path)
        self.notify(f"Forked {example_name} to {target_name}", severity="information")

    @on(events.Click)
    def on_click(self, event: events.Click) -> None:
        """Clear or transfer card focus when clicking across hangar workspace panels.

        Args:
            event: Textual mouse click event.
        """
        componentstore_card = self.query_one("#componentstore-card", Container)
        workspace_card = self.query_one("#workspace-card", Container)
        hangar_card = self.query_one("#hangar-library-card", Container)
        preview_card = self.query_one("#component-preview-card", Container)

        current: Any = event.widget
        clicked_card: Container | None = None
        while current is not None and current is not self:
            if current in (componentstore_card, workspace_card, hangar_card, preview_card):
                clicked_card = current
                break
            current = getattr(current, "parent", None)

        if clicked_card is None:
            self.app.set_focus(None)
        elif clicked_card is componentstore_card:
            tiles = self.query(ComponentTile)
            if tiles:
                tiles.first().focus()
        elif clicked_card is workspace_card:
            self.query_one("#vehicle-components-list", VehicleComponentList).focus()
        elif clicked_card is hangar_card:
            self.query_one("#hangar-library-tree", VehicleTree).focus()

    def refresh_vehicle_library(self) -> None:
        """Scan the filesystem to discover user vehicles and reference examples."""
        tree = self.query_one("#hangar-library-tree", VehicleTree)
        tree.populate()

    def inspect_vehicle(self, vehicle_name: str) -> BaseVehicleConfig | None:
        """Load detailed metadata and component composition for a vehicle.

        Args:
            vehicle_name: Name of the target vehicle to inspect.

        Returns:
            The loaded BaseVehicleConfig instance, or None if loading failed.
        """
        for root in (self.hangar_root, self.examples_root):
            if root.is_dir():
                for path in root.rglob("*.toml"):
                    if path.stem == vehicle_name or path.parent.name == vehicle_name:
                        try:
                            return BaseVehicleConfig.from_toml(path)
                        except (OSError, ValueError, KeyError):
                            return None
        return None

    def fork_reference_example(self, example_name: str, target_name: str) -> Path:
        """Clone a read-only reference example into a new writable user directory.

        Args:
            example_name: Identifier of the source template in Hangar/examples/.
            target_name: Identifier for the new vehicle in Hangar/<target_name>/.

        Returns:
            Destination path to the cloned TOML configuration file.
        """
        src: Path | None = None
        for p in self.examples_root.rglob("*.toml"):
            if p.stem == example_name or p.parent.name == example_name:
                src = p
                break
        if src is None:
            src = self.examples_root / example_name / f"{example_name}.toml"

        dest_dir = self.hangar_root / target_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{target_name}.toml"
        if src.is_file():
            shutil.copy2(src, dest)
            try:
                cfg = BaseVehicleConfig.from_toml(dest)
                cfg.name = target_name
                cfg.to_toml(dest)
            except (OSError, ValueError, KeyError):
                pass
        return dest

    def delete_user_vehicle(self, vehicle_name: str) -> bool:
        """Safely remove a user vehicle configuration from the Hangar directory.

        Args:
            vehicle_name: Identifier of the vehicle to delete.

        Returns:
            True if deletion succeeded, False otherwise.
        """
        target_dir = self.hangar_root / vehicle_name
        if target_dir.is_dir():
            try:
                if not target_dir.resolve().is_relative_to(self.examples_root.resolve()):
                    shutil.rmtree(target_dir)
                    return True
            except (OSError, ValueError):
                return False
        return False

    def switch_to_assembly(self, vehicle_name: str | None = None) -> None:
        """Switch view into assembly mode to edit or construct a vehicle.

        Args:
            vehicle_name: Identifier of an existing vehicle to edit, or None for a new blank canvas.
        """
        self.current_mode = "assembly"
        self.selected_vehicle_name = vehicle_name

    def switch_to_library(self) -> None:
        """Switch view back to the vehicle library browser."""
        self.current_mode = "library"
