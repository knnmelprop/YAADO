"""Interactive parameter tuning form for physics solvers in Flight Deck.

Provides dynamic form controls (inputs, toggles, SI unit badges) allowing users to
tune solver operating conditions and see compact aerospace symbols update live in
the execution pipeline list.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from rich.markup import escape
from textual import on, work
from textual.containers import Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Select, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from Terminal.screens.flight_deck import SolverDescriptor


@dataclass(frozen=True)
class SolverParam:
    """Metadata and validation rules for a tunable solver parameter.

    Attributes:
        name: Internal parameter keyword name passed to solver.setup().
        label: Human-readable form label.
        symbol: Compact aerospace symbol (e.g. γ₀, h₀, M, α).
        unit: Canonical SI unit string (e.g. deg, m, s).
        param_type: Python type (float, int, bool, str).
        default: Default value in canonical SI units.
        description: Informative parameter explanation tooltip/hint.
        min_value: Optional minimum numerical bound.
        max_value: Optional maximum numerical bound.
    """

    name: str
    label: str
    symbol: str
    unit: str
    param_type: type
    default: Any
    description: str = ""
    min_value: float | None = None
    max_value: float | None = None



class SolverParamsForm(VerticalScroll):
    """Interactive form for tuning solver parameters and operating conditions."""

    class ParamChanged(Message):
        """Dispatched whenever a parameter value is changed and validated."""

        def __init__(
            self,
            form: SolverParamsForm,
            name: str,
            value: Any,
            is_valid: bool,
            stage_index: int | None = None,
        ) -> None:
            super().__init__()
            self.form = form
            self.name = name
            self.value = value
            self.is_valid = is_valid
            self.stage_index = stage_index

        @property
        def control(self) -> SolverParamsForm:
            return self.form

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.descriptor: SolverDescriptor | None = None
        self.current_params: dict[str, Any] = {}
        self.stage_index: int | None = None
        self._param_defs: dict[str, SolverParam] = {}
        self._is_populating: bool = False
        self._widgets_mounted: bool = False

    def compose(self) -> ComposeResult:
        """Compose initial placeholder."""
        yield Static(
            "[dim]Select a solver or pipeline stage to configure parameters.[/dim]",
            id="solver-form-placeholder",
        )

    def _build_header_text(
        self,
        descriptor: SolverDescriptor,
        stage_index: int | None,
        is_ready: bool,
        compatibility_msg: str,
        vehicle_name: str | None,
    ) -> str:
        fid_label = (
            descriptor.fidelity.name.replace("_", " ").title()
            if hasattr(descriptor.fidelity, "name")
            else "Level 0"
        )

        header_lines: list[str] = []
        if stage_index is not None:
            header_lines.append(
                f"[bold #38bdf8]PIPELINE STAGE {stage_index}: {descriptor.name.upper()}[/bold #38bdf8]  "
                f"[bold #0284c7][{fid_label}][/bold #0284c7]"
            )
            header_lines.append(
                "[dim]Tuned parameters update this pipeline stage in real time[/dim]"
            )
        else:
            header_lines.append(
                f"[bold #38bdf8]{descriptor.name.upper()}[/bold #38bdf8]  "
                f"[bold #0284c7][{fid_label}][/bold #0284c7]  "
                f"[dim]{descriptor.discipline}[/dim]"
            )

        header_lines.append("")

        if vehicle_name:
            status_tag = (
                f"[bold #10b981][READY][/bold #10b981]  [dim]{escape(compatibility_msg)}[/dim]"
                if is_ready
                else f"[bold #f59e0b][INAPPLICABLE][/bold #f59e0b]  [dim]{escape(compatibility_msg)}[/dim]"
            )
            header_lines.append(f"[bold]Active Vehicle:[/bold] {escape(vehicle_name)}  {status_tag}")
        else:
            header_lines.append(
                "[bold]Active Vehicle:[/bold] [dim]None loaded[/dim]  "
                "[bold #f59e0b][INAPPLICABLE][/bold #f59e0b]  "
                "[dim]Load a vehicle in Hangar to enable execution[/dim]"
            )

        header_lines.append("")
        header_lines.append("[bold cyan]Description:[/bold cyan]")
        header_lines.append(f"  {descriptor.description}")
        header_lines.append("")
        header_lines.append("[bold cyan]Requirements:[/bold cyan]")
        header_lines.append(f"  {descriptor.required_components_desc}")
        header_lines.append("")
        header_lines.append("[bold cyan]Solver Parameters (Tune & Run):[/bold cyan]")
        return "\n".join(header_lines)

    def _build_footer_text(
        self,
        descriptor: SolverDescriptor,
        stage_index: int | None,
    ) -> str:
        output_lines: list[str] = ["", "[bold cyan]Primary Outputs:[/bold cyan]"]
        for _, f_unit, f_label in descriptor.headline_outputs:
            u_str = f" [{f_unit}]" if f_unit and f_unit != "-" else ""
            output_lines.append(f"  • {f_label}{u_str}")

        output_lines.append("")
        if stage_index is not None:
            output_lines.append(
                "[dim]Parameters update stage in real time • Press [bold]r[/bold] to run stage • Press [bold]b[/bold] to return to solver inspector[/dim]"
            )
        else:
            output_lines.append(
                "[dim]Press [bold]r[/bold] to run with current parameters • Press [bold]a[/bold] or [bold]↵ Enter[/bold] to stage into pipeline[/dim]"
            )
        return "\n".join(output_lines)

    def _update_in_place(
        self,
        descriptor: SolverDescriptor,
        stage_index: int | None,
        is_ready: bool,
        compatibility_msg: str,
        vehicle_name: str | None,
    ) -> None:
        try:
            header = self.query_one("#solver-form-header", Static)
            header.update(
                self._build_header_text(
                    descriptor, stage_index, is_ready, compatibility_msg, vehicle_name
                )
            )

            for param in descriptor.parameters:
                val = self.current_params.get(param.name, param.default)
                if param.param_type is bool:
                    sel = self.query_one(f"#param-inp-{param.name}", Select)
                    if sel.value != str(val):
                        sel.value = str(val)
                else:
                    inp = self.query_one(f"#param-inp-{param.name}", Input)
                    if inp.value != str(val):
                        inp.value = str(val)
                err = self.query_one(f"#param-err-{param.name}", Static)
                err.update("")
                err.add_class("-hidden")

            footer = self.query_one("#solver-form-footer", Static)
            footer.update(self._build_footer_text(descriptor, stage_index))
        except NoMatches:
            pass

    @work(exclusive=True, group="solver_form")
    async def load_solver(
        self,
        descriptor: SolverDescriptor,
        params: dict[str, Any],
        stage_index: int | None = None,
        is_ready: bool = True,
        compatibility_msg: str = "",
        vehicle_name: str | None = None,
    ) -> None:
        """Populate the form controls for a solver descriptor and its active parameters.

        Args:
            descriptor: Solver metadata descriptor.
            params: Dictionary of parameter values to prefill.
            stage_index: Optional 1-based index if editing a pipeline stage.
            is_ready: Whether active vehicle satisfies requirements.
            compatibility_msg: Compatibility or failure explanation.
            vehicle_name: Active vehicle name, if loaded.
        """
        self._is_populating = True
        self.stage_index = stage_index
        self.current_params = dict(params)

        if self.descriptor == descriptor and self._widgets_mounted:
            self._update_in_place(
                descriptor, stage_index, is_ready, compatibility_msg, vehicle_name
            )
            self._is_populating = False
            return

        self.descriptor = descriptor
        self._param_defs = {p.name: p for p in descriptor.parameters}

        await self.remove_children()

        widgets_to_mount: list[Widget] = [
            Static(
                self._build_header_text(
                    descriptor, stage_index, is_ready, compatibility_msg, vehicle_name
                ),
                id="solver-form-header",
                classes="solver-form-header",
            )
        ]

        # Mount parameter inputs
        for param in descriptor.parameters:
            val = self.current_params.get(param.name, param.default)
            label_text = f"{param.label} [{param.symbol}]:"

            input_widget: Input | Select[str]
            if param.param_type is bool:
                input_widget = Select.from_values(
                    ["True", "False"],
                    value=str(val),
                    allow_blank=False,
                    id=f"param-inp-{param.name}",
                    classes="form-select",
                )
            else:
                input_widget = Input(
                    value=str(val),
                    id=f"param-inp-{param.name}",
                    classes="form-input",
                )

            unit_str = param.unit if param.unit != "bool" else ""
            hint_str = escape(param.description)

            row = Horizontal(
                Static(label_text, classes="form-label"),
                input_widget,
                Static(unit_str, classes="form-unit"),
                Static(hint_str, classes="form-hint"),
                classes="form-row",
            )
            widgets_to_mount.append(row)
            widgets_to_mount.append(
                Static("", id=f"param-err-{param.name}", classes="form-error -hidden")
            )

        widgets_to_mount.append(
            Static(
                self._build_footer_text(descriptor, stage_index),
                id="solver-form-footer",
                classes="solver-form-footer",
            )
        )

        await self.mount_all(widgets_to_mount)
        self._widgets_mounted = True
        self._is_populating = False
        self.scroll_home(animate=False)


    @on(Input.Changed)
    def _on_input_changed(self, event: Input.Changed) -> None:
        """Handle parameter input field changes with live validation."""
        if self._is_populating or not event.input.id or not event.input.id.startswith("param-inp-"):
            return
        param_name = event.input.id.removeprefix("param-inp-")
        param_def = self._param_defs.get(param_name)
        if param_def is None:
            return

        val_str = event.value.strip()
        error_widget = self.query_one(f"#param-err-{param_name}", Static)

        try:
            if param_def.param_type is int:
                parsed_val: Any = int(val_str)
            else:
                parsed_val = float(val_str)

            if param_def.min_value is not None and parsed_val < param_def.min_value:
                raise ValueError(f"Value must be >= {param_def.min_value}")
            if param_def.max_value is not None and parsed_val > param_def.max_value:
                raise ValueError(f"Value must be <= {param_def.max_value}")

            event.input.remove_class("-invalid")
            error_widget.update("")
            error_widget.add_class("-hidden")
            self.current_params[param_name] = parsed_val
            self.post_message(
                self.ParamChanged(self, param_name, parsed_val, is_valid=True, stage_index=self.stage_index)
            )
        except ValueError as exc:
            event.input.add_class("-invalid")
            error_widget.update(f"  [red]• {exc}[/red]")
            error_widget.remove_class("-hidden")
            self.post_message(
                self.ParamChanged(self, param_name, val_str, is_valid=False, stage_index=self.stage_index)
            )

    @on(Select.Changed)
    def _on_select_changed(self, event: Select.Changed) -> None:
        """Handle boolean toggle select changes."""
        if self._is_populating or not event.select.id or not event.select.id.startswith("param-inp-"):
            return
        param_name = event.select.id.removeprefix("param-inp-")
        bool_val = (event.value == "True")
        self.current_params[param_name] = bool_val
        self.post_message(
            self.ParamChanged(self, param_name, bool_val, is_valid=True, stage_index=self.stage_index)
        )
