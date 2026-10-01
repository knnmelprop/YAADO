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
from rich.markup import escape
from textual import events, on
from textual.binding import Binding, BindingType
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from Terminal.Assembly.template_generator import VehicleTemplateGenerator
from Terminal.formatting import (
    _format_compact_value_and_unit,
)
from Terminal.widgets import (
    ComponentStoreView,
    ComponentTile,
    ConfirmModal,
    DynamicSchemaForm,
    InputModal,
    VehicleTree,
)
from YAADO_Core.ComponentStore import (
    AERO_COMPONENTS,
    BODY_COMPONENTS,
    PROPULSION_COMPONENTS,
    MassProperties,
)
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.timer import Timer


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


FIELD_SYMBOLS: dict[str, str] = {
    # General & Identifiers
    "name": "name",
    # Geometry
    "length": "L",
    "diameter": "D",
    "span": "b",
    "aspect_ratio": "AR",
    "taper_ratio": "λ",
    "sweep": "Λ",
    "dihedral": "Γ",
    "root_chord": "cr",
    "tip_chord": "ct",
    "area": "S",
    "count": "n",
    # Mass & CG
    "total_mass": "m",
    "dry_mass": "m_dry",
    "propellant_mass": "m_prop",
    "cg_from_nose": "x_cg",
    # Propulsion & Aero
    "thrust": "T",
    "thrust_mean": "T",
    "thrust_max": "T_max",
    "burn_time": "tb",
    "isp_sl": "Isp",
    "specific_impulse": "Isp",
    "sfc": "SFC",
    "design_mach": "M",
    "combustor_temp": "T_comb",
    "fuel_type": "fuel",
}


def _abbreviate_field(field_name: str) -> str:
    """Return compact aerospace symbol or standard abbreviation for a schema field name."""
    if field_name in FIELD_SYMBOLS:
        return FIELD_SYMBOLS[field_name]
    parts = field_name.split("_")
    if len(parts) > 1:
        initials = "".join(p[0] for p in parts if p).upper()
        if 2 <= len(initials) <= 4:
            return initials
    return field_name[:4]





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
        self._auto_save_timer: Timer | None = None
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
            componentstore_card.border_subtitle = "\\[a] / Double-Click / Drag to Add"
            with componentstore_card:
                yield ComponentStoreView(id="component-store-view")

            # Right column
            with Vertical(id="hangar-right-column", classes="cockpit-col"):
                with Horizontal(id="panel-and-hangar"):
                    workspace_card = Container(id="workspace-card", classes="cockpit-card")
                    workspace_card.border_title = "Vehicle"
                    workspace_card.border_subtitle = "\\[d] Delete"
                    with workspace_card:
                        yield Static("", id="workspace-header")
                        yield VehicleComponentList(id="vehicle-components-list")

                    hangar_card = Container(id="hangar-library-card", classes="cockpit-card")
                    hangar_card.border_title = "Hangar"
                    hangar_card.border_subtitle = "↵ Load  c  r  d"
                    with hangar_card:
                        yield VehicleTree(id="hangar-library-tree")
                        with Vertical(id="hangar-library-buttons"):
                            with Horizontal(classes="hangar-btn-row"):
                                btn_new = Button("+ New", id="hangar-new-btn", classes="hangar-action-btn")
                                btn_new.can_focus = False
                                yield btn_new
                                btn_copy = Button("Copy", id="hangar-copy-btn", classes="hangar-action-btn -last")
                                btn_copy.can_focus = False
                                yield btn_copy
                            with Horizontal(classes="hangar-btn-row"):
                                btn_rename = Button("Rename", id="hangar-rename-btn", classes="hangar-action-btn")
                                btn_rename.can_focus = False
                                yield btn_rename
                                btn_del = Button("Delete", id="hangar-delete-btn", classes="hangar-action-btn hangar-btn-danger -last")
                                btn_del.can_focus = False
                                yield btn_del

                # Right column bottom: Component parameters
                component_stat_card = Container(id="component-preview-card", classes="cockpit-card")
                component_stat_card.border_title = "Component Parameters"
                with component_stat_card:
                    yield DynamicSchemaForm(id="component-form")

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
        self._update_hangar_border_subtitle()

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

    def _format_headline_specs(self, comp: BaseModel) -> str:
        """Format declared headline fields and units into compact aerospace badges.

        Args:
            comp: Pydantic component model instance.

        Returns:
            Space-separated compact headline specs string.
        """
        units: dict[str, str] = getattr(comp, "UNITS", {})
        headline: tuple[str, ...] = getattr(comp, "HEADLINE_FIELDS", ())
        parts: list[str] = []
        for f in headline:
            if f == "name":
                continue
            val = getattr(comp, f, None)
            if val is None:
                continue
            sym = _abbreviate_field(f)
            unit = units.get(f, "")
            val_str, unit_str = _format_compact_value_and_unit(val, unit)
            parts.append(f"{sym}={val_str}{unit_str}")
        return "  ".join(parts)

    def _format_component_option_prompt(
        self, category: str, name: str, comp: BaseModel
    ) -> str:
        """Format an OptionList row with aligned columns for category, name, class, and headline specs.

        Args:
            category: Subsystem category string ('BODY', 'AERO', 'PROP', 'MASS').
            name: Component identifier string.
            comp: Pydantic component model instance.

        Returns:
            Rich-formatted string aligned into neat columns.
        """
        badge_colors = {
            "BODY": "#3b82f6",
            "AERO": "#0284c7",
            "PROP": "#f59e0b",
            "MASS": "#94a3b8",
        }
        color = badge_colors.get(category, "#94a3b8")
        cls_name = comp.__class__.__name__
        specs = self._format_headline_specs(comp)
        specs_str = f"  [#64748b]│[/#64748b]  [#94a3b8]{specs}[/#94a3b8]" if specs else ""
        return (
            f"[bold {color}]\\[{category}][/bold {color}]  "
            f"[bold]{name:<18}[/bold]  "
            f"[dim]{cls_name:<16}[/dim]"
            f"{specs_str}"
        )

    def _refresh_workspace(self) -> None:
        """Refresh workspace header and component list."""
        workspace_card = self.query_one("#workspace-card", Container)
        workspace_header = self.query_one("#workspace-header", Static)
        comp_list = self.query_one("#vehicle-components-list", VehicleComponentList)

        if self.active_vehicle is None:
            workspace_card.border_title = "Vehicle Workspace"
            workspace_card.border_subtitle = "No Vehicle Loaded"
            workspace_header.update("[dim]No vehicle loaded. Select from library or click '+ New'.[/dim]")
            comp_list.clear_options()
            comp_list.add_option(Option("[dim]No components loaded.[/dim]", disabled=True))
            return

        vehicle = self.active_vehicle
        workspace_card.border_title = f"Vehicle: {vehicle.name}"
        comp_count = len(vehicle.all_components())
        if vehicle.mass_properties is not None:
            comp_count += 1
        workspace_card.border_subtitle = f"{comp_count} Components • \\[d] Delete"

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

        comp_list.clear_options()
        has_items = False

        for name, body_comp in vehicle.bodies.items():
            has_items = True
            prompt = self._format_component_option_prompt("BODY", name, body_comp)
            comp_list.add_option(Option(prompt, id=f"comp:BODY:{name}"))

        for name, aero_comp in vehicle.aero_surfaces.items():
            has_items = True
            prompt = self._format_component_option_prompt("AERO", name, aero_comp)
            comp_list.add_option(Option(prompt, id=f"comp:AERO:{name}"))

        for name, prop_comp in vehicle.propulsion.items():
            has_items = True
            prompt = self._format_component_option_prompt("PROP", name, prop_comp)
            comp_list.add_option(Option(prompt, id=f"comp:PROP:{name}"))

        if vehicle.mass_properties is not None:
            has_items = True
            prompt = self._format_component_option_prompt("MASS", "mass_properties", vehicle.mass_properties)
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
            try:
                from Terminal.screens.flight_deck import FlightDeckView

                fd = self.app.query_one(FlightDeckView)
                fd.set_active_vehicle(self.active_vehicle, self.active_vehicle_path)
            except NoMatches:
                pass

        try:
            tree = self.query_one("#hangar-library-tree", VehicleTree)
            if self.active_vehicle_path is not None:
                tree.select_by_path(self.active_vehicle_path)
        except NoMatches:
            # Tree may not yet be mounted during initial load
            pass

        self._refresh_workspace()
        self._update_hangar_border_subtitle()

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

    def _save_active_vehicle_if_writable(self) -> bool:
        """Save active vehicle to disk if path is set.

        Returns:
            True if saved successfully to disk, False otherwise.
        """
        if self.active_vehicle is None:
            return False
        if self.active_vehicle_path is None:
            name = self.active_vehicle.name or "Custom_Vehicle"
            self.active_vehicle_path = self.hangar_root / name / f"{name}.toml"
        try:
            self.active_vehicle_path.parent.mkdir(parents=True, exist_ok=True)
            self.active_vehicle.to_toml(self.active_vehicle_path)
            return True
        except (OSError, ValueError) as exc:
            self.notify(f"Auto-save failed: {exc}", severity="warning")
            return False

    def _clear_auto_save_badge(self) -> None:
        """Revert preview card subtitle to default after auto-save indicator timeout."""
        try:
            preview_card = self.query_one("#component-preview-card", Container)
            preview_card.border_subtitle = ""
        except (NoMatches, KeyError):
            pass

    def add_component_to_vehicle(self, comp_cls_name: str | None) -> None:
        """Instantiate and attach a component from the store to the active vehicle.

        Args:
            comp_cls_name: Class name of the component to add.
        """
        if not comp_cls_name or comp_cls_name not in self._component_classes:
            return

        comp_cls = self._component_classes[comp_cls_name]
        try:
            form = self.query_one("#component-form", DynamicSchemaForm)
            if form.model_class == comp_cls and form.is_valid and form.current_validated_instance is not None:
                new_comp = form.current_validated_instance.model_copy(deep=True)
            else:
                new_comp = VehicleTemplateGenerator.prefill_component_values(comp_cls)
        except (ValueError, KeyError, TypeError, AttributeError):
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
        workspace_card.border_subtitle = f"Added {comp_cls.__name__} \\[{key}]"

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

    @on(ComponentTile.ComponentSelected)
    def on_component_tile_selected(self, event: ComponentTile.ComponentSelected) -> None:
        """Add component from store into active vehicle via double-click, 'a' key, or drag-and-drop.

        Args:
            event: Component tile selected event.
        """
        self.add_component_to_vehicle(event.comp_id)

    @on(OptionList.OptionHighlighted, "#vehicle-components-list")
    def on_vehicle_component_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Display and edit live parameter values of highlighted vehicle component.

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
            if self._auto_save_timer is not None:
                self._auto_save_timer.stop()
                self._auto_save_timer = None
            preview_card = self.query_one("#component-preview-card", Container)
            preview_card.border_title = f"Component Parameters: {name} ({comp.__class__.__name__})"
            preview_card.border_subtitle = ""
            form = self.query_one("#component-form", DynamicSchemaForm)
            self.run_worker(
                form.load_model(
                    comp.__class__,
                    initial_values=comp,
                    name=name,
                    category=category,
                    is_installed=True,
                ),
                exclusive=True,
                group="form_loader",
            )

    @on(DynamicSchemaForm.FormChanged)
    def on_form_changed(self, event: DynamicSchemaForm.FormChanged) -> None:
        """Handle real-time component parameter updates and auto-save valid configurations.

        Args:
            event: Dynamic schema form changed event.
        """
        preview_card = self.query_one("#component-preview-card", Container)

        if not event.is_valid:
            if event.errors:
                first_k = next(iter(event.errors))
                preview_card.border_subtitle = f"[red]▲ {escape(first_k)}: {escape(event.errors[first_k])}[/red]"
            return

        if not event.validated_instance:
            return

        if not getattr(event, "is_user_edit", False):
            preview_card.border_subtitle = ""
            return

        if self.active_vehicle is None or not event.name or not event.category:
            return

        # Update the component in the active vehicle model
        if event.category == "BODY" and isinstance(event.validated_instance, BODY_COMPONENTS):
            self.active_vehicle.bodies[event.name] = event.validated_instance
        elif event.category == "AERO" and isinstance(event.validated_instance, AERO_COMPONENTS):
            self.active_vehicle.aero_surfaces[event.name] = event.validated_instance
        elif event.category == "PROP" and isinstance(event.validated_instance, PROPULSION_COMPONENTS):
            self.active_vehicle.propulsion[event.name] = event.validated_instance
        elif event.category == "MASS" and isinstance(event.validated_instance, MassProperties):
            self.active_vehicle.mass_properties = event.validated_instance
        else:
            return

        # Auto-save to TOML on disk
        saved = self._save_active_vehicle_if_writable()

        # Update option prompt in list to reflect live edits
        comp_list = self.query_one("#vehicle-components-list", VehicleComponentList)
        opt_id = f"comp:{event.category}:{event.name}"
        try:
            new_prompt = self._format_component_option_prompt(
                event.category, event.name, event.validated_instance
            )
            comp_list.replace_option_prompt(opt_id, new_prompt)
        except (KeyError, IndexError, ValueError):
            pass

        # Update workspace header without resetting options list
        workspace_header = self.query_one("#workspace-header", Static)
        mass_str = (
            f"  [dim]•[/dim]  [bold #94a3b8]{self.active_vehicle.total_mass:.1f} kg[/bold #94a3b8]"
            if self.active_vehicle.total_mass is not None
            else ""
        )
        n_body = len(self.active_vehicle.bodies)
        n_aero = len(self.active_vehicle.aero_surfaces)
        n_prop = len(self.active_vehicle.propulsion)
        header_text = (
            f"[bold white]{self.active_vehicle.name}[/bold white]"
            f"{mass_str}  [dim]•[/dim]  "
            f"[bold #3b82f6]{n_body} Body[/bold #3b82f6]  [dim]•[/dim]  "
            f"[bold #0284c7]{n_aero} Aero[/bold #0284c7]  [dim]•[/dim]  "
            f"[bold #f59e0b]{n_prop} Prop[/bold #f59e0b]"
        )
        workspace_header.update(header_text)

        if saved:
            preview_card.border_subtitle = "[green]● Auto-saved[/green]"
            if self._auto_save_timer is not None:
                self._auto_save_timer.stop()
            self._auto_save_timer = self.set_timer(3.0, self._clear_auto_save_badge)
        else:
            preview_card.border_subtitle = ""

    def _update_hangar_border_subtitle(self, target_path: Path | None = None) -> None:
        """Update subtitle hint when a vehicle is targeted or cursor changes in the library.

        Args:
            target_path: Optional explicit vehicle path from hover or highlight event.
        """
        try:
            hangar_card = self.query_one("#hangar-library-card", Container)
            tree = self.query_one("#hangar-library-tree", VehicleTree)
        except NoMatches:
            return

        effective_path = target_path
        if (
            effective_path is None
            and tree.cursor_node is not None
            and isinstance(tree.cursor_node.data, Path)
            and tree.cursor_node.data.is_file()
        ):
            effective_path = tree.cursor_node.data

        if effective_path is not None and isinstance(effective_path, Path) and effective_path.is_file():
            hangar_card.border_subtitle = "↵ Load  c  r  d"
        else:
            hangar_card.border_subtitle = "n  c  r  d"

    @on(VehicleTree.VehicleHighlighted, "#hangar-library-tree")
    def on_hangar_library_node_highlighted(self, event: VehicleTree.VehicleHighlighted) -> None:
        """Update subtitle hint when a vehicle is highlighted in the library.

        Args:
            event: Vehicle highlighted event containing vehicle path.
        """
        self._update_hangar_border_subtitle(event.path)

    @on(VehicleTree.VehicleSelected, "#hangar-library-tree")
    def on_hangar_library_vehicle_selected(self, event: VehicleTree.VehicleSelected) -> None:
        """Load vehicle when confirmed via Enter or double-click.

        Args:
            event: Vehicle selected event containing vehicle path.
        """
        self.load_vehicle(path=event.path)

    def create_new_vehicle_interactive(self) -> None:
        """Prompt user for a name and create a new blank vehicle."""
        idx = 1
        while (self.hangar_root / f"Vehicle_{idx}").exists():
            idx += 1
        suggested = f"Vehicle_{idx}"

        def on_name_submitted(name: str | None) -> None:
            if not name:
                return
            clean_name = re.sub(r"[^\w\-\.]", "_", name.strip())
            if not clean_name:
                self.notify("Vehicle name cannot be empty.", severity="error")
                return
            target_dir = self.hangar_root / clean_name
            if target_dir.exists():
                self.notify(f"A vehicle named '{clean_name}' already exists in Hangar/.", severity="error")
                return
            target_dir.mkdir(parents=True, exist_ok=True)
            new_path = target_dir / f"{clean_name}.toml"
            new_vehicle = BaseVehicleConfig(name=clean_name)
            new_vehicle.to_toml(new_path)
            tree = self.query_one("#hangar-library-tree", VehicleTree)
            tree.populate(select_path=new_path)
            self.load_vehicle(config=new_vehicle, path=new_path)
            self.notify(f"Created new vehicle '{clean_name}'", severity="information")

        self.app.push_screen(
            InputModal(title="New Vehicle", prompt="Enter vehicle name:", default_value=suggested),
            callback=on_name_submitted,
        )

    def copy_vehicle_interactive(self, target_path: Path | None = None) -> None:
        """Prompt user for a new name and duplicate the selected or active vehicle.

        Args:
            target_path: Optional explicit file path of the vehicle to copy.
        """
        if target_path is None:
            tree = self.query_one("#hangar-library-tree", VehicleTree)
            if tree.cursor_node is not None and isinstance(tree.cursor_node.data, Path) and tree.cursor_node.data.is_file():
                target_path = tree.cursor_node.data
            elif self.active_vehicle_path is not None and self.active_vehicle_path.is_file():
                target_path = self.active_vehicle_path

        if target_path is None or not target_path.is_file():
            self.notify("Select a vehicle in the library or workspace to copy.", severity="warning")
            return

        src_name = target_path.stem
        suggested = f"{src_name}_copy"
        idx = 1
        while (self.hangar_root / suggested).exists():
            idx += 1
            suggested = f"{src_name}_copy_{idx}"

        def on_copy_name_submitted(new_name: str | None) -> None:
            if not new_name:
                return
            clean_name = re.sub(r"[^\w\-\.]", "_", new_name.strip())
            if not clean_name:
                self.notify("Vehicle name cannot be empty.", severity="error")
                return
            dest_dir = self.hangar_root / clean_name
            if dest_dir.exists():
                self.notify(f"A vehicle named '{clean_name}' already exists in Hangar/.", severity="error")
                return
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / f"{clean_name}.toml"

            # Copy auxiliary files if present in source folder
            src_dir = target_path.parent
            if (
                src_dir.is_dir()
                and src_dir.resolve() != self.hangar_root.resolve()
                and src_dir.resolve() != self.examples_root.resolve()
            ):
                for item in src_dir.iterdir():
                    if item.is_file() and item.name != target_path.name:
                        shutil.copy2(item, dest_dir / item.name)

            shutil.copy2(target_path, dest_path)
            try:
                cfg = BaseVehicleConfig.from_toml(dest_path)
                cfg.name = clean_name
                cfg.to_toml(dest_path)
            except (OSError, ValueError, KeyError):
                pass

            tree = self.query_one("#hangar-library-tree", VehicleTree)
            tree.populate(select_path=dest_path)
            self.load_vehicle(path=dest_path)
            self.notify(f"Copied '{src_name}' to '{clean_name}'", severity="information")

        self.app.push_screen(
            InputModal(title="Copy Vehicle", prompt=f"Enter name for copy of '{src_name}':", default_value=suggested),
            callback=on_copy_name_submitted,
        )

    def rename_vehicle_interactive(self, target_path: Path | None = None) -> None:
        """Prompt user for a new name and rename the target vehicle on disk and in workspace.

        Args:
            target_path: Optional explicit file path of the vehicle to rename.
        """
        if target_path is None:
            tree = self.query_one("#hangar-library-tree", VehicleTree)
            if tree.cursor_node is not None and isinstance(tree.cursor_node.data, Path) and tree.cursor_node.data.is_file():
                target_path = tree.cursor_node.data
            elif self.active_vehicle_path is not None and self.active_vehicle_path.is_file():
                target_path = self.active_vehicle_path

        if target_path is None or not target_path.is_file():
            self.notify("Select a vehicle to rename first.", severity="warning")
            return

        if target_path.resolve().is_relative_to(self.examples_root.resolve()):
            self.notify(
                "Reference examples in Hangar/examples/ are read-only and cannot be renamed. Use 'Copy' instead.",
                severity="warning",
            )
            return

        old_name = target_path.stem

        def on_rename_submitted(new_name: str | None) -> None:
            if not new_name or new_name.strip() == old_name:
                return
            clean_name = re.sub(r"[^\w\-\.]", "_", new_name.strip())
            if not clean_name:
                self.notify("Vehicle name cannot be empty.", severity="error")
                return
            dest_dir = self.hangar_root / clean_name
            if dest_dir.exists():
                self.notify(f"A vehicle named '{clean_name}' already exists in Hangar/.", severity="error")
                return

            old_dir = target_path.parent
            was_active = (
                self.active_vehicle_path == target_path
                or (self.active_vehicle is not None and self.active_vehicle.name == old_name)
            )

            try:
                if old_dir.name == old_name and old_dir.resolve() != self.hangar_root.resolve():
                    old_dir.rename(dest_dir)
                    new_path = dest_dir / f"{clean_name}.toml"
                    old_file_in_new = dest_dir / target_path.name
                    if old_file_in_new.exists() and old_file_in_new != new_path:
                        old_file_in_new.rename(new_path)
                else:
                    new_path = old_dir / f"{clean_name}.toml"
                    target_path.rename(new_path)

                cfg = BaseVehicleConfig.from_toml(new_path)
                cfg.name = clean_name
                cfg.to_toml(new_path)

                if was_active:
                    self.active_vehicle = cfg
                    self.active_vehicle_path = new_path
                    from Terminal.app import YaadoApp
                    if isinstance(self.app, YaadoApp):
                        self.app.active_vehicle = cfg
                        self.app.active_vehicle_path = new_path
                    self._refresh_workspace()

                tree = self.query_one("#hangar-library-tree", VehicleTree)
                tree.populate(select_path=new_path)
                self.notify(f"Renamed vehicle to '{clean_name}'", severity="information")
            except OSError as exc:
                self.notify(f"Failed to rename vehicle: {exc}", severity="error")

        self.app.push_screen(
            InputModal(title="Rename Vehicle", prompt=f"Enter new name for '{old_name}':", default_value=old_name),
            callback=on_rename_submitted,
        )

    def delete_vehicle_interactive(self, target_path: Path | None = None) -> None:
        """Prompt user for confirmation and delete the target user vehicle.

        Args:
            target_path: Optional explicit file path of the vehicle to delete.
        """
        if target_path is None:
            tree = self.query_one("#hangar-library-tree", VehicleTree)
            if tree.cursor_node is not None and isinstance(tree.cursor_node.data, Path) and tree.cursor_node.data.is_file():
                target_path = tree.cursor_node.data
            elif self.active_vehicle_path is not None and self.active_vehicle_path.is_file():
                target_path = self.active_vehicle_path

        if target_path is None or not target_path.is_file():
            self.notify("Select a vehicle to delete first.", severity="warning")
            return

        if target_path.resolve().is_relative_to(self.examples_root.resolve()):
            self.notify(
                "Reference examples in Hangar/examples/ are read-only and cannot be deleted.",
                severity="warning",
            )
            return

        target_name = target_path.stem

        def on_confirmed(confirmed: bool | None) -> None:
            if not confirmed:
                return

            was_active = (
                self.active_vehicle_path == target_path
                or (self.active_vehicle is not None and self.active_vehicle.name == target_name)
            )

            parent_dir = target_path.parent
            try:
                if parent_dir.name == target_name and parent_dir.resolve() != self.hangar_root.resolve():
                    shutil.rmtree(parent_dir, ignore_errors=True)
                else:
                    target_path.unlink(missing_ok=True)

                if was_active:
                    self.active_vehicle = None
                    self.active_vehicle_path = None
                    from Terminal.app import YaadoApp
                    if isinstance(self.app, YaadoApp):
                        self.app.active_vehicle = None
                        self.app.active_vehicle_path = None

                tree = self.query_one("#hangar-library-tree", VehicleTree)
                tree.populate()

                if was_active:
                    first = tree.select_first_vehicle()
                    if first:
                        self.load_vehicle(path=first)
                    else:
                        self._refresh_workspace()

                self.notify(f"Deleted vehicle '{target_name}'", severity="information")
            except OSError as exc:
                self.notify(f"Failed to delete vehicle: {exc}", severity="error")

        self.app.push_screen(
            ConfirmModal(
                title="Delete Vehicle",
                message=f"Are you sure you want to permanently delete '{target_name}'?\nThis will remove its directory from Hangar/.",
                confirm_label="Delete",
                is_destructive=True,
            ),
            callback=on_confirmed,
        )

    @on(Button.Pressed, "#hangar-new-btn, #hangar-new-vehicle-btn")
    def on_new_vehicle_btn_pressed(self) -> None:
        """Handle New Vehicle button click."""
        self.create_new_vehicle_interactive()

    @on(Button.Pressed, "#hangar-copy-btn, #hangar-fork-btn")
    def on_copy_vehicle_btn_pressed(self) -> None:
        """Handle Copy/Fork Vehicle button click."""
        self.copy_vehicle_interactive()

    @on(Button.Pressed, "#hangar-rename-btn")
    def on_rename_vehicle_btn_pressed(self) -> None:
        """Handle Rename Vehicle button click."""
        self.rename_vehicle_interactive()

    @on(Button.Pressed, "#hangar-delete-btn")
    def on_delete_vehicle_btn_pressed(self) -> None:
        """Handle Delete Vehicle button click."""
        self.delete_vehicle_interactive()

    @on(VehicleTree.NewVehicleRequested)
    def on_tree_new_vehicle(self) -> None:
        """Handle 'n' key pressed inside vehicle tree."""
        self.create_new_vehicle_interactive()

    @on(VehicleTree.CopyVehicleRequested)
    def on_tree_copy_vehicle(self, event: VehicleTree.CopyVehicleRequested) -> None:
        """Handle 'c' key pressed inside vehicle tree."""
        self.copy_vehicle_interactive(event.path)

    @on(VehicleTree.RenameVehicleRequested)
    def on_tree_rename_vehicle(self, event: VehicleTree.RenameVehicleRequested) -> None:
        """Handle 'r' key pressed inside vehicle tree."""
        self.rename_vehicle_interactive(event.path)

    @on(VehicleTree.DeleteVehicleRequested)
    def on_tree_delete_vehicle(self, event: VehicleTree.DeleteVehicleRequested) -> None:
        """Handle 'd' or Delete key pressed inside vehicle tree."""
        self.delete_vehicle_interactive(event.path)

    @on(events.Click, "#workspace-header")
    def on_workspace_header_clicked(self) -> None:
        """Allow renaming active vehicle by clicking its title header."""
        if self.active_vehicle is not None:
            self.rename_vehicle_interactive(self.active_vehicle_path)

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
