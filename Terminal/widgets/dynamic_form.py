"""Dynamic schema-driven parameter form generator with live Pydantic validation.

Reflects Pydantic v2 component models from ComponentStore to generate interactive
input forms with real-time field validation, SI unit badges, description tooltips,
and automatic saving to the active vehicle upon valid configuration.
"""

from __future__ import annotations

import typing
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, ValidationError
from rich.markup import escape
from textual import on
from textual.containers import Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Select, Static

from YAADO_Core.ComponentStore.mass import MassProperties

if TYPE_CHECKING:
    from textual.app import ComposeResult


class DynamicSchemaForm(VerticalScroll):
    """Dynamic form generating interactive input widgets from a Pydantic model class.

    Attributes:
        model_class: Target Pydantic component model class being configured.
        current_name: Identifier of the component being edited.
        current_category: Subsystem group ('BODY', 'AERO', 'PROP', 'MASS', 'STORE').
        is_installed: True if editing an installed vehicle component, False if store catalog template.
    """

    ALLOW_SELECT: ClassVar[bool] = False

    class FormChanged(Message):
        """Dispatched whenever any field in the form changes and undergoes validation."""

        def __init__(
            self,
            form: DynamicSchemaForm,
            comp_cls: type[BaseModel],
            name: str | None,
            category: str | None,
            is_installed: bool,
            is_valid: bool,
            validated_instance: BaseModel | None,
            errors: dict[str, str],
            is_user_edit: bool = False,
        ) -> None:
            super().__init__()
            self.form = form
            self.comp_cls = comp_cls
            self.name = name
            self.category = category
            self.is_installed = is_installed
            self.is_valid = is_valid
            self.validated_instance = validated_instance
            self.errors = errors
            self.is_user_edit = is_user_edit

        @property
        def control(self) -> DynamicSchemaForm:
            return self.form

    def __init__(
        self,
        model_class: type[BaseModel] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.model_class: type[BaseModel] | None = model_class
        self.current_name: str | None = None
        self.current_category: str | None = None
        self.is_installed: bool = False
        self.initial_instance: BaseModel | None = None
        self.current_validated_instance: BaseModel | None = None
        self.is_valid: bool = True
        self._field_inputs: dict[str, Input | Select[str]] = {}
        self._field_types: dict[str, Any] = {}
        self._errors: dict[str, str] = {}
        self._is_populating: bool = False

    def compose(self) -> ComposeResult:
        """Render initial empty message when no component is selected."""
        yield Static(
            "[dim]Highlight a component in the store or workspace to inspect and edit its parameters.[/dim]",
            id="form-empty-label",
        )

    async def load_model(
        self,
        model_class: type[BaseModel],
        initial_values: BaseModel | None = None,
        name: str | None = None,
        category: str | None = None,
        is_installed: bool = False,
    ) -> None:
        """Rebuild the form inputs for a target component class or active vehicle instance.

        Args:
            model_class: Target Pydantic component model class.
            initial_values: Optional existing component instance populated with current values.
            name: Name of the component in the vehicle or template name.
            category: Subsystem group identifier ('BODY', 'AERO', 'PROP', 'MASS', 'STORE').
            is_installed: True if editing an installed vehicle component, False if store catalog.
        """
        self._is_populating = True
        self.model_class = model_class
        self.initial_instance = initial_values
        self.current_name = name or model_class.__name__
        self.current_category = category
        self.is_installed = is_installed
        self.current_validated_instance = initial_values
        self._field_inputs.clear()
        self._field_types.clear()
        self._errors.clear()
        self.is_valid = True

        await self.remove_children()

        rows_to_mount: list[Widget] = []
        units = getattr(model_class, "UNITS", {})

        for field_name, f_info in model_class.model_fields.items():
            if field_name == "type":
                continue
            if field_name == "control_surfaces":
                continue

            ann = f_info.annotation
            origin = typing.get_origin(ann)
            args = typing.get_args(ann)
            is_literal = (origin is typing.Literal)
            is_optional = (type(None) in args)

            # Determine initial value
            current_val: Any = None
            if initial_values is not None:
                current_val = getattr(initial_values, field_name, None)
            elif f_info.examples:
                current_val = f_info.examples[0]
            elif f_info.default is not None and str(f_info.default) != "PydanticUndefined":
                current_val = f_info.default

            if field_name == "mass":
                mass_val = getattr(current_val, "total_mass", None) if current_val else None
                cg_val = getattr(current_val, "cg_from_nose", None) if current_val else None

                inp_mass = Input(
                    value="" if mass_val is None else str(mass_val),
                    placeholder="None",
                    id="input-mass_total_mass",
                    classes="form-input",
                    tooltip="Component total mass in kilograms",
                )
                self._field_inputs["mass_total_mass"] = inp_mass
                self._field_types["mass_total_mass"] = float
                rows_to_mount.append(
                    Horizontal(
                        Static("Mass (Total)", classes="form-label"),
                        inp_mass,
                        Static("kg", classes="form-unit"),
                        Static("Component total mass", classes="form-hint"),
                        classes="form-row",
                    )
                )

                inp_cg = Input(
                    value="" if cg_val is None else str(cg_val),
                    placeholder="None",
                    id="input-mass_cg_from_nose",
                    classes="form-input",
                    tooltip="Longitudinal CG distance from nose in meters",
                )
                self._field_inputs["mass_cg_from_nose"] = inp_cg
                self._field_types["mass_cg_from_nose"] = float
                rows_to_mount.append(
                    Horizontal(
                        Static("Mass (CG)", classes="form-label"),
                        inp_cg,
                        Static("m", classes="form-unit"),
                        Static("CG distance from nose", classes="form-hint"),
                        classes="form-row",
                    )
                )
                continue

            label_text = field_name.replace("_", " ").title()
            unit_str = units.get(field_name, "")
            if not unit_str and field_name != "name":
                unit_str = "-"
            hint_str = escape(f_info.description or "") if f_info.description else ""

            input_widget: Input | Select[str]
            if is_literal:
                choices = list(args)
                sel_val = current_val if current_val in choices else choices[0]
                input_widget = Select.from_values(
                    choices,
                    value=sel_val,
                    allow_blank=False,
                    id=f"select-{field_name}",
                    classes="form-select",
                )
            elif origin is tuple and len(args) == 2 and args[0] is float:
                t_val = f"{current_val[0]}, {current_val[1]}" if isinstance(current_val, (tuple, list)) else ""
                input_widget = Input(
                    value=t_val,
                    placeholder="e.g. 0.2, 0.85",
                    id=f"input-{field_name}",
                    classes="form-input",
                )
            else:
                str_val = "" if current_val is None else str(current_val)
                placeholder_val = "None" if is_optional else ""
                is_str_field = (
                    ann is str
                    or (is_optional and str in args)
                    or isinstance(current_val, str)
                )
                input_classes = "form-input form-input-wide" if is_str_field else "form-input"
                input_widget = Input(
                    value=str_val,
                    placeholder=placeholder_val,
                    id=f"input-{field_name}",
                    classes=input_classes,
                )

            if f_info.description:
                input_widget.tooltip = f_info.description

            self._field_inputs[field_name] = input_widget
            self._field_types[field_name] = ann

            unit_widget = (
                Static(unit_str, classes="form-unit")
                if unit_str
                else Static("", classes="form-unit form-unit-empty")
            )
            rows_to_mount.append(
                Horizontal(
                    Static(label_text, classes="form-label"),
                    input_widget,
                    unit_widget,
                    Static(hint_str, classes="form-hint"),
                    classes="form-row",
                )
            )

        status_footer = Static("", id="form-validation-status")
        rows_to_mount.append(status_footer)

        await self.mount_all(rows_to_mount)
        self._is_populating = False
        self._validate_and_notify(is_user_edit=False)

    def _parse_field_value(self, field_name: str, raw_val: Any, target_type: Any) -> Any:
        """Parse raw text input string into the typed target representation."""
        if raw_val is None or (isinstance(raw_val, str) and raw_val == ""):
            f_info = self.model_class.model_fields.get(field_name) if self.model_class else None
            if f_info is not None:
                args = typing.get_args(f_info.annotation)
                if type(None) in args:
                    return None
                if f_info.default is not None and str(f_info.default) != "PydanticUndefined":
                    return f_info.default
            origin = typing.get_origin(target_type)
            if origin is typing.Union and type(None) in typing.get_args(target_type):
                return None
            return ""

        if not isinstance(raw_val, str):
            return raw_val

        origin = typing.get_origin(target_type)
        if origin is tuple:
            try:
                parts = [float(p.strip()) for p in raw_val.split(",") if p.strip()]
                return tuple(parts)
            except ValueError:
                return raw_val

        args = typing.get_args(target_type)
        if target_type is float or (origin is typing.Union and float in args):
            try:
                return float(raw_val)
            except ValueError:
                return raw_val

        if target_type is int or (origin is typing.Union and int in args):
            try:
                return int(raw_val)
            except ValueError:
                return raw_val

        return raw_val

    @on(Input.Changed)
    def _on_input_changed(self, event: Input.Changed) -> None:
        """Validate on input change."""
        event.stop()
        if self._is_populating:
            return
        self._validate_and_notify(is_user_edit=True)

    @on(Select.Changed)
    def _on_select_changed(self, event: Select.Changed) -> None:
        """Validate on select change."""
        event.stop()
        if self._is_populating:
            return
        self._validate_and_notify(is_user_edit=True)

    def _validate_and_notify(self, is_user_edit: bool = False) -> None:
        """Collect form values, validate against Pydantic schema, and post FormChanged."""
        if self.model_class is None:
            return

        payload: dict[str, Any] = {}
        if "type" in self.model_class.model_fields:
            payload["type"] = self.model_class.model_fields["type"].default

        if "control_surfaces" in self.model_class.model_fields:
            if self.initial_instance and getattr(self.initial_instance, "control_surfaces", None) is not None:
                payload["control_surfaces"] = getattr(self.initial_instance, "control_surfaces", [])
            else:
                payload["control_surfaces"] = []

        mass_total_str: str | None = None
        mass_cg_str: str | None = None

        for field_name, input_widget in self._field_inputs.items():
            if field_name == "mass_total_mass":
                mass_total_str = input_widget.value.strip() if isinstance(input_widget, Input) else None
                continue
            if field_name == "mass_cg_from_nose":
                mass_cg_str = input_widget.value.strip() if isinstance(input_widget, Input) else None
                continue

            raw_val: Any
            if isinstance(input_widget, Select):
                raw_val = input_widget.value
                if raw_val is Select.BLANK or raw_val is Select.NULL:
                    raw_val = None
            else:
                raw_val = input_widget.value.strip()

            target_type = self._field_types.get(field_name, str)
            payload[field_name] = self._parse_field_value(field_name, raw_val, target_type)

        if "mass" in self.model_class.model_fields:
            if mass_total_str or mass_cg_str:
                try:
                    t_mass = float(mass_total_str) if mass_total_str else None
                    init_mass = getattr(self.initial_instance, "mass", None) if self.initial_instance else None
                    if mass_cg_str:
                        cg_val = float(mass_cg_str)
                    elif init_mass and getattr(init_mass, "cg_from_nose", None) is not None:
                        cg_val = float(init_mass.cg_from_nose)
                    else:
                        cg_val = 0.1
                    cg_src = getattr(init_mass, "cg_source", "not provided") if init_mass else "not provided"
                    payload["mass"] = MassProperties(total_mass=t_mass, cg_from_nose=cg_val, cg_source=cg_src)
                except ValueError:
                    payload["mass"] = "invalid"
            else:
                payload["mass"] = None

        try:
            validated = self.model_class.model_validate(payload)
            self.current_validated_instance = validated
            self.is_valid = True
            self._errors.clear()

            for inp in self._field_inputs.values():
                inp.remove_class("-invalid")

            if is_user_edit and self.initial_instance is not None and validated == self.initial_instance:
                is_user_edit = False

            self._update_status_display(is_valid=True)
            self.post_message(
                self.FormChanged(
                    form=self,
                    comp_cls=self.model_class,
                    name=self.current_name,
                    category=self.current_category,
                    is_installed=self.is_installed,
                    is_valid=True,
                    validated_instance=validated,
                    errors={},
                    is_user_edit=is_user_edit,
                )
            )
        except ValidationError as err:
            self.is_valid = False
            self._errors.clear()
            for e in err.errors():
                loc = str(e["loc"][0]) if e["loc"] else "unknown"
                self._errors[loc] = e["msg"]

            for field_name, inp in self._field_inputs.items():
                if field_name in self._errors or (field_name.startswith("mass_") and "mass" in self._errors):
                    inp.add_class("-invalid")
                else:
                    inp.remove_class("-invalid")

            self._update_status_display(is_valid=False)
            self.post_message(
                self.FormChanged(
                    form=self,
                    comp_cls=self.model_class,
                    name=self.current_name,
                    category=self.current_category,
                    is_installed=self.is_installed,
                    is_valid=False,
                    validated_instance=None,
                    errors=self._errors,
                    is_user_edit=is_user_edit,
                )
            )

    def _update_status_display(self, is_valid: bool) -> None:
        """Update inline validation error status text."""

        try:
            status_label = self.query_one("#form-validation-status", Static)
            if is_valid:
                status_label.update("")
            elif self._errors:
                first_k = next(iter(self._errors))
                status_label.update(f"[red]▲ {escape(first_k)}: {escape(self._errors[first_k])}[/red]")
        except NoMatches:
            pass

    def extract_validated_model(self) -> BaseModel:
        """Extract and instantiate the validated Pydantic model from current form inputs.

        Returns:
            A strictly validated Pydantic component instance.

        Raises:
            ValidationError: If one or more fields contain invalid values.
        """
        if self.current_validated_instance is not None and self.is_valid:
            return self.current_validated_instance
        raise ValidationError.from_exception_data(title="DynamicSchemaForm", line_errors=[])
