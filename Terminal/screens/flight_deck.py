"""Flight Deck view (Tab 3) for solver execution, pipelines, sweeps, and log inspection.

Provides interfaces to configure verified physics solvers (currently Point-Mass 3-DOF),
construct sequential computational pipelines, execute batch parameter sweeps,
and interactively review historical runs stored in FlightLogs.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from rich.markup import escape
from rich.text import Text
from textual import events, on
from textual.binding import Binding, BindingType
from textual.containers import (
    Container,
    Horizontal,
    ScrollableContainer,
    Vertical,
    VerticalScroll,
)
from textual.css.query import NoMatches
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Collapsible, OptionList, Static
from textual.widgets.option_list import Option

from Terminal.widgets import FlightLogsTree, render_flightlog_preview
from YAADO_Core.ComponentStore import (
    AERO_COMPONENTS,
    BODY_COMPONENTS,
    BOOSTER_COMPONENTS,
)
from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.flight_dynamics.containers import PointMassBoostResults
from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
    PointMass3DOFBoostAnalysis,
    format_sweep_csv,
    plot_boost_phase,
    plot_full_flight,
    plot_launch_angle_sweep,
    run_launch_angle_sweep,
)

if TYPE_CHECKING:
    from textual.app import ComposeResult


@dataclass(frozen=True)
class SolverDescriptor:
    """Metadata descriptor for verified physics solvers in YAADO.

    Attributes:
        solver_id: Unique string identifier for the solver method.
        name: Human-readable display name.
        discipline: Engineering discipline category.
        fidelity: Solver fidelity level (Level 0 through Level 3).
        solver_cls: Concrete solver implementation class inheriting from BaseAnalysis.
        description: Methodological and physics summary.
        required_components_desc: Required vehicle components and attributes.
        headline_outputs: Sequence of (field_name, unit_str, display_title) tuples.
        default_params: Canonical default parameters in SI units.
    """

    solver_id: str
    name: str
    discipline: str
    fidelity: FidelityLevel
    solver_cls: type[BaseAnalysis[Any]]
    description: str
    required_components_desc: str
    headline_outputs: tuple[tuple[str, str, str], ...]
    default_params: dict[str, Any]


@dataclass(frozen=True)
class PipelineStage:
    """A configured solver stage in an execution pipeline.

    Attributes:
        descriptor: Metadata descriptor for the solver.
        params: Configured execution parameters in SI units.
    """

    descriptor: SolverDescriptor
    params: dict[str, Any]


REPAIRED_SOLVERS: tuple[SolverDescriptor, ...] = (
    SolverDescriptor(
        solver_id="point_mass_3dof_boost",
        name="Point-Mass 3-DOF Boost",
        discipline="FLIGHT DYNAMICS",
        fidelity=FidelityLevel.LEVEL_0,
        solver_cls=PointMass3DOFBoostAnalysis,
        description=(
            "Integrates vertical-plane point-mass equations of motion for rocket booster stage "
            "from ignition to motor burnout or ground impact under ISA atmosphere and empirical drag."
        ),
        required_components_desc="Booster motor (SolidMotor), body geometry (Fuselage diameter), positive total_mass.",
        headline_outputs=(
            ("burnout_mach", "-", "Burnout Mach"),
            ("burnout_velocity", "m/s", "Burnout Velocity"),
            ("burnout_altitude", "m", "Burnout Altitude"),
            ("apogee_altitude", "m", "Apogee Altitude"),
            ("q_max", "Pa", "Max Dynamic Pressure"),
            ("nominal_burn_time", "s", "Nominal Burn Time"),
            ("range_at_burnout", "m", "Burnout Range"),
            ("final_x", "m", "Final Range"),
            ("flight_time", "s", "Flight Time"),
        ),
        default_params={
            "launch_angle_deg": 83.0,
            "altitude_m": 100.0,
            "stop_at_burnout": True,
        },
    ),
)


def check_solver_compatibility(
    descriptor: SolverDescriptor,
    vehicle: BaseVehicleConfig | None,
) -> tuple[bool, str]:
    """Evaluate whether the given vehicle configuration satisfies the solver's prerequisites.

    Args:
        descriptor: Solver descriptor to evaluate.
        vehicle: Currently loaded vehicle configuration, or None.

    Returns:
        Tuple of (is_compatible, status_message).
    """
    if vehicle is None:
        return False, "No active vehicle loaded in Hangar"

    if descriptor.solver_id == "point_mass_3dof_boost":
        boosters = vehicle.get_components_by_type(BOOSTER_COMPONENTS)
        if not boosters:
            return False, "Missing booster propulsion (SolidMotor / RocketMotor)"

        bodies = vehicle.get_components_by_type(BODY_COMPONENTS)
        if not bodies:
            return False, "Missing fuselage/body component"

        has_diameter = any(
            getattr(b, "diameter", None) is not None for b in bodies.values()
        )
        if not has_diameter:
            return False, "Fuselage/body component missing diameter specification"

        if vehicle.total_mass is None or vehicle.total_mass <= 0:
            return False, "Mass properties missing positive total_mass"

        booster_name = next(iter(boosters.keys()))
        body_name = next(iter(bodies.keys()))
        return True, f"Ready ({booster_name}, {body_name}, {vehicle.total_mass:.1f} kg)"

    return False, "Unknown solver compatibility rule"


def resolve_fins_name(vehicle: BaseVehicleConfig) -> str | None:
    """Auto-detect appropriate aerodynamic fin surface for 3-DOF boost trajectory.

    Args:
        vehicle: Vehicle configuration.

    Returns:
        Name of aerodynamic surface to use for fin drag, or None.
    """
    candidate_fins = vehicle.get_components_by_type(AERO_COMPONENTS)
    if not candidate_fins:
        return None
    for name in candidate_fins:
        if "fin" in name.lower() or "tail" in name.lower():
            return name
    return next(iter(candidate_fins.keys()))


FIDELITY_BADGES: dict[FidelityLevel, str] = {
    FidelityLevel.LEVEL_0: "[L0]",
    FidelityLevel.LEVEL_1: "[L1]",
    FidelityLevel.LEVEL_2: "[L2]",
    FidelityLevel.LEVEL_3: "[L3]",
}


class SolverTile(Widget, can_focus=True):
    """Interactive modular card representing a verified physics solver.

    Attributes:
        descriptor: Metadata descriptor for the solver.
        is_ready: Whether the active vehicle satisfies prerequisites.
        status_msg: Explanation message of vehicle compatibility.
        is_staged: Whether this solver is currently staged in the pipeline.
    """

    ALLOW_SELECT: ClassVar[bool] = False

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("a,enter", "add_to_pipeline", "Add to Pipeline", show=True),
        Binding("r", "run_solver", "Run Solver", show=True),
    ]

    class SolverHighlighted(Message):
        """Dispatched when a solver tile gains focus (updates inspector)."""

        def __init__(
            self, descriptor: SolverDescriptor, is_ready: bool, message: str
        ) -> None:
            super().__init__()
            self.descriptor = descriptor
            self.is_ready = is_ready
            self.message = message

    class SolverSelected(Message):
        """Dispatched when a solver is confirmed for addition via double-click, 'a', or Enter."""

        def __init__(
            self, descriptor: SolverDescriptor, is_ready: bool, message: str
        ) -> None:
            super().__init__()
            self.descriptor = descriptor
            self.is_ready = is_ready
            self.message = message

    class SolverRunRequested(Message):
        """Dispatched when 'r' is pressed to quick-run the solver."""

        def __init__(
            self, descriptor: SolverDescriptor, is_ready: bool, message: str
        ) -> None:
            super().__init__()
            self.descriptor = descriptor
            self.is_ready = is_ready
            self.message = message

    def __init__(
        self,
        descriptor: SolverDescriptor,
        is_ready: bool = False,
        status_msg: str = "",
        is_staged: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the solver tile.

        Args:
            descriptor: Solver metadata descriptor.
            is_ready: Compatibility status flag.
            status_msg: Detailed status or prerequisite message.
            is_staged: Whether solver is currently in pipeline.
            **kwargs: Standard Textual widget keyword arguments.
        """
        super().__init__(**kwargs)
        self.descriptor = descriptor
        self.is_ready = is_ready
        self.status_msg = status_msg
        self.is_staged = is_staged
        if is_staged:
            self.add_class("-staged")

    def update_status(
        self,
        vehicle: BaseVehicleConfig | None,
        staged_ids: Sequence[str] = (),
    ) -> None:
        """Update solver compatibility and staged status against active vehicle.

        Args:
            vehicle: Currently active vehicle configuration.
            staged_ids: Sequence of solver_ids staged in the pipeline.
        """
        self.is_ready, self.status_msg = check_solver_compatibility(
            self.descriptor, vehicle
        )
        self.is_staged = self.descriptor.solver_id in staged_ids
        self.set_class(self.is_staged, "-staged")
        self.refresh()

    def render(self) -> Text:
        """Render two-line aerospace card with fidelity, name, status, and staged badge."""
        fid_badge = FIDELITY_BADGES.get(self.descriptor.fidelity, "[L0]")
        if self.descriptor.fidelity == FidelityLevel.LEVEL_0:
            fid_markup = f"[bold #0284c7]{fid_badge}[/bold #0284c7]"
        elif self.descriptor.fidelity == FidelityLevel.LEVEL_1:
            fid_markup = f"[bold #10b981]{fid_badge}[/bold #10b981]"
        elif self.descriptor.fidelity == FidelityLevel.LEVEL_2:
            fid_markup = f"[bold #f59e0b]{fid_badge}[/bold #f59e0b]"
        else:
            fid_markup = f"[bold #ef4444]{fid_badge}[/bold #ef4444]"

        if self.is_ready:
            status_markup = "[bold #10b981][READY][/bold #10b981]"
            name_markup = f"[bold]{escape(self.descriptor.name)}[/bold]"
        else:
            status_markup = "[bold #f59e0b][INAPPLICABLE][/bold #f59e0b]"
            name_markup = f"[dim]{escape(self.descriptor.name)}[/dim]"

        staged_markup = "  [bold #38bdf8][STAGED][/bold #38bdf8]" if self.is_staged else ""
        return Text.from_markup(f"{fid_markup}  {name_markup}\n{status_markup}{staged_markup}")

    def action_add_to_pipeline(self) -> None:
        """Add this solver to the execution pipeline."""
        self.post_message(
            self.SolverSelected(self.descriptor, self.is_ready, self.status_msg)
        )

    def action_run_solver(self) -> None:
        """Run this solver immediately."""
        self.post_message(
            self.SolverRunRequested(self.descriptor, self.is_ready, self.status_msg)
        )

    def on_focus(self) -> None:
        """Update inspector when tile gains focus."""
        self.post_message(
            self.SolverHighlighted(self.descriptor, self.is_ready, self.status_msg)
        )

    def on_click(self, event: events.Click) -> None:
        """Handle mouse clicks: single click focuses, double click adds to pipeline."""
        event.prevent_default()
        event.stop()
        if event.chain == 2:
            self.action_add_to_pipeline()
        else:
            self.focus()
            self.post_message(
                self.SolverHighlighted(self.descriptor, self.is_ready, self.status_msg)
            )


class SolversStoreView(VerticalScroll):
    """Scrollable container housing collapsible discipline categories and modular solver tiles."""

    ALLOW_SELECT: ClassVar[bool] = False

    DISCIPLINES: ClassVar[tuple[str, ...]] = (
        "FLIGHT DYNAMICS",
        "PROPULSION",
        "AERODYNAMICS",
        "STRUCTURES & MASS",
    )

    # Message aliases for backwards compatibility
    SolverHighlighted = SolverTile.SolverHighlighted
    SolverSelected = SolverTile.SolverSelected
    SolverRunRequested = SolverTile.SolverRunRequested

    def __init__(
        self,
        solvers: Sequence[SolverDescriptor] = REPAIRED_SOLVERS,
        vehicle: BaseVehicleConfig | None = None,
        staged_ids: Sequence[str] = (),
        **kwargs: Any,
    ) -> None:
        """Initialize the solvers store container.

        Args:
            solvers: Sequence of available verified solvers.
            vehicle: Currently active vehicle configuration.
            staged_ids: Sequence of solver_ids staged in the pipeline.
            **kwargs: Standard Textual widget keyword arguments.
        """
        super().__init__(**kwargs)
        self._solvers: list[SolverDescriptor] = list(solvers)
        self._vehicle: BaseVehicleConfig | None = vehicle
        self._staged_ids: list[str] = list(staged_ids)

    def compose(self) -> ComposeResult:
        """Render collapsible discipline categories with verified solver tiles."""
        disciplines_to_show: list[str] = []
        for disc in self.DISCIPLINES:
            if any(s.discipline == disc for s in self._solvers):
                disciplines_to_show.append(disc)
        for s in self._solvers:
            if s.discipline not in disciplines_to_show:
                disciplines_to_show.append(s.discipline)

        for disc_title in disciplines_to_show:
            solvers_in_disc = [s for s in self._solvers if s.discipline == disc_title]
            cat_id = f"solvers-cat-{disc_title.lower().replace(' ', '-').replace('&', 'and')}"
            with Collapsible(title=disc_title, collapsed=False, id=cat_id):
                for desc in solvers_in_disc:
                    is_ready, msg = check_solver_compatibility(desc, self._vehicle)
                    is_staged = desc.solver_id in self._staged_ids
                    yield SolverTile(
                        descriptor=desc,
                        is_ready=is_ready,
                        status_msg=msg,
                        is_staged=is_staged,
                        id=f"tile-solver-{desc.solver_id}",
                    )

    def update_all_tiles(
        self,
        vehicle: BaseVehicleConfig | None,
        staged_ids: Sequence[str] = (),
    ) -> None:
        """Update compatibility and staged statuses across all mounted solver tiles.

        Args:
            vehicle: Currently active vehicle configuration.
            staged_ids: Sequence of solver_ids staged in the pipeline.
        """
        self._vehicle = vehicle
        self._staged_ids = list(staged_ids)
        for tile in self.query(SolverTile):
            tile.update_status(vehicle, staged_ids)

    def populate(
        self,
        solvers: Sequence[SolverDescriptor],
        vehicle: BaseVehicleConfig | None,
        staged_solver_ids: Sequence[str] = (),
    ) -> None:
        """Populate or update store with solver descriptors.

        Args:
            solvers: Sequence of solver descriptors.
            vehicle: Vehicle configuration or None.
            staged_solver_ids: Sequence of solver IDs staged in pipeline.
        """
        self._solvers = list(solvers)
        self._vehicle = vehicle
        self._staged_ids = list(staged_solver_ids)
        self.update_all_tiles(vehicle, staged_solver_ids)

    def focus_first_solver(self) -> None:
        """Focus the first available solver tile."""
        tiles = self.query(SolverTile)
        if tiles:
            tiles.first().focus()

    def get_focused_tile(self) -> SolverTile | None:
        """Retrieve the currently focused solver tile, if any."""
        for tile in self.query(SolverTile):
            if tile.has_focus:
                return tile
        return None

    def get_focused_or_first_descriptor(self) -> SolverDescriptor | None:
        """Retrieve descriptor of focused tile, or first tile if none focused."""
        tile = self.get_focused_tile()
        if tile is not None:
            return tile.descriptor
        tiles = list(self.query(SolverTile))
        return tiles[0].descriptor if tiles else None

    def action_stage_selected(self) -> None:
        """Stage currently focused solver to pipeline."""
        tile = self.get_focused_tile()
        if tile is not None:
            tile.action_add_to_pipeline()

    def action_run_selected(self) -> None:
        """Run currently focused solver."""
        tile = self.get_focused_tile()
        if tile is not None:
            tile.action_run_solver()


class PipelineList(OptionList):
    """Interactive execution pipeline stage list."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("delete,backspace,d", "delete_stage", "Delete Stage", show=True),
    ]

    class StageRemoved(Message):
        """Dispatched when a pipeline stage is removed."""

        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def action_delete_stage(self) -> None:
        """Delete highlighted stage from the pipeline."""
        if self.highlighted is not None:
            self.post_message(self.StageRemoved(self.highlighted))


class FlightDeckView(Container):
    """Execution dashboard and simulation run inspector.

    Attributes:
        logs_root: Path to the root directory storing simulation run artifacts.
        active_vehicle: Currently loaded BaseVehicleConfig instance.
        active_vehicle_path: Source file path for active_vehicle if saved to disk.
        pipeline: List of staged pipeline steps.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("c", "clear_pipeline", "Clear Pipeline", show=True),
        Binding("x", "run_pipeline", "Run Pipeline", show=True),
        Binding("b", "show_inspector", "Back to Inspector", show=True),
    ]

    def __init__(
        self,
        logs_root: Path = Path("FlightLogs"),
        selected_vehicle_name: str | None = None,
        active_vehicle: BaseVehicleConfig | None = None,
        active_vehicle_path: Path | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Flight Deck view.

        Args:
            logs_root: Path to the FlightLogs directory.
            selected_vehicle_name: Initial vehicle name selected for analysis.
            active_vehicle: Pre-loaded vehicle configuration.
            active_vehicle_path: Path to vehicle configuration file.
            **kwargs: Standard Textual container keyword arguments.
        """
        super().__init__(**kwargs)
        self.logs_root = logs_root
        self.selected_vehicle_name = selected_vehicle_name
        self.active_vehicle = active_vehicle
        self.active_vehicle_path = active_vehicle_path
        self.pipeline: list[PipelineStage] = []
        self._current_highlighted_descriptor: SolverDescriptor | None = (
            REPAIRED_SOLVERS[0] if REPAIRED_SOLVERS else None
        )
        self._selected_flightlog_path: Path | None = None

    def compose(self) -> ComposeResult:
        """Render the run setup pane, execution console drawer, and historical logs browser.

        Yields:
            Child widgets comprising the Flight Deck interface.
        """
        with Horizontal(id="flightdeck-layout"):
            # Left column: Available Solvers catalog
            solvers_card = Container(id="flightdeck-solvers-card", classes="cockpit-card")
            solvers_card.border_title = "Available Solvers"
            solvers_card.border_subtitle = "\\[a]/↵ Add  r Run"
            with solvers_card:
                yield SolversStoreView(id="solvers-store-view")
                with Horizontal(classes="flightdeck-btn-row"):
                    btn_stage = Button(
                        "+ Add (a)", id="solver-stage-btn", classes="flightdeck-action-btn"
                    )
                    btn_stage.can_focus = False
                    yield btn_stage
                    btn_run = Button(
                        "Run (r)", id="solver-run-btn", classes="flightdeck-action-btn -last"
                    )
                    btn_run.can_focus = False
                    yield btn_run

            # Middle column: Solver Inspector / Results & Analysis Pipeline
            with Vertical(id="flightdeck-middle-column", classes="cockpit-col"):
                results_card = Container(
                    id="flightdeck-results-card", classes="cockpit-card"
                )
                results_card.border_title = "Solver Inspector"
                results_card.border_subtitle = "\\[a]/↵ Add  r Run"
                with results_card, ScrollableContainer(id="flightdeck-results-scroll"):
                    yield Static("", id="flightdeck-results-content")

                pipeline_card = Container(
                    id="flightdeck-pipeline-card", classes="cockpit-card"
                )
                pipeline_card.border_title = "Analysis Pipeline"
                pipeline_card.border_subtitle = "↵ Add  c Clear  x Run"
                with pipeline_card:
                    yield PipelineList(id="flightdeck-pipeline-list")
                    with Horizontal(classes="flightdeck-btn-row"):
                        btn_clear = Button(
                            "Clear (c)", id="pipeline-clear-btn", classes="flightdeck-action-btn"
                        )
                        btn_clear.can_focus = False
                        yield btn_clear
                        btn_exec = Button(
                            "Run Pipeline (x)",
                            id="pipeline-run-btn",
                            classes="flightdeck-action-btn -last",
                        )
                        btn_exec.can_focus = False
                        yield btn_exec

            # Right column: Previous runs & historical logs
            runs_card = Container(id="flightdeck-runs-card", classes="cockpit-card")
            runs_card.border_title = "FlightLogs History"
            runs_card.border_subtitle = "↵ View  o Open  f Folder  d Delete"
            with runs_card:
                yield FlightLogsTree(id="flightdeck-runs-tree", logs_root=self.logs_root)

    def on_mount(self) -> None:
        """Initialize active vehicle and solvers list on startup."""
        from Terminal.app import YaadoApp

        if isinstance(self.app, YaadoApp) and self.app.active_vehicle is not None:
            self.set_active_vehicle(self.app.active_vehicle, self.app.active_vehicle_path)
        else:
            self.refresh_solvers_list()
            self._refresh_pipeline_ui()

    def focus_first_solver(self) -> None:
        """Focus the first available solver tile."""
        try:
            solvers_store = self.query_one("#solvers-store-view", SolversStoreView)
            solvers_store.focus_first_solver()
        except NoMatches:
            pass

    def set_active_vehicle(
        self,
        vehicle: BaseVehicleConfig | None,
        path: Path | None = None,
    ) -> None:
        """Update active vehicle reference and re-evaluate solver compatibility.

        Args:
            vehicle: Loaded vehicle configuration, or None.
            path: Source file path on disk, or None.
        """
        self.active_vehicle = vehicle
        self.active_vehicle_path = path
        if vehicle is not None:
            self.selected_vehicle_name = vehicle.name
        self.refresh_solvers_list()
        self._refresh_pipeline_ui()

    def refresh_solvers_list(self) -> None:
        """Re-render the available solvers list and update inspector."""
        try:
            solvers_store = self.query_one("#solvers-store-view", SolversStoreView)
            staged_ids = [s.descriptor.solver_id for s in self.pipeline]
            solvers_store.update_all_tiles(self.active_vehicle, staged_ids=staged_ids)
            if self._current_highlighted_descriptor is not None:
                is_ready, msg = check_solver_compatibility(
                    self._current_highlighted_descriptor, self.active_vehicle
                )
                self._render_solver_inspector(
                    self._current_highlighted_descriptor, is_ready, msg
                )
            elif REPAIRED_SOLVERS:
                first = REPAIRED_SOLVERS[0]
                self._current_highlighted_descriptor = first
                is_ready, msg = check_solver_compatibility(first, self.active_vehicle)
                self._render_solver_inspector(first, is_ready, msg)
        except NoMatches:
            pass

    def _render_solver_inspector(
        self, descriptor: SolverDescriptor, is_ready: bool, message: str
    ) -> None:
        """Render solver specifications and vehicle compatibility into the results card.

        Args:
            descriptor: Solver metadata descriptor.
            is_ready: Whether vehicle satisfies prerequisites.
            message: Status explanation message.
        """
        try:
            results_card = self.query_one("#flightdeck-results-card", Container)
            results_card.border_title = "Solver Inspector"
            results_card.border_subtitle = "\\[a]/↵ Add  r Run"

            fid_label = (
                descriptor.fidelity.name.replace("_", " ").title()
                if hasattr(descriptor.fidelity, "name")
                else "Level 0"
            )
            lines: list[str] = [
                (
                    f"[bold #38bdf8]{descriptor.name.upper()}[/bold #38bdf8]  "
                    f"[bold #0284c7][{fid_label}][/bold #0284c7]  "
                    f"[dim]{descriptor.discipline}[/dim]"
                ),
                "",
            ]

            if self.active_vehicle is not None:
                veh_name = escape(self.active_vehicle.name)
                if is_ready:
                    status_str = f"[bold #10b981][READY][/bold #10b981]  [dim]{escape(message)}[/dim]"
                else:
                    status_str = f"[bold #f59e0b][INAPPLICABLE][/bold #f59e0b]  [dim]{escape(message)}[/dim]"
                lines.append(f"[bold]Active Vehicle:[/bold] {veh_name}  {status_str}")
            else:
                lines.append(
                    "[bold]Active Vehicle:[/bold] [dim]None loaded[/dim]  "
                    "[bold #f59e0b][INAPPLICABLE][/bold #f59e0b]  "
                    "[dim]Load a vehicle in Hangar to enable execution[/dim]"
                )

            stage_indices = [
                str(idx)
                for idx, s in enumerate(self.pipeline, start=1)
                if s.descriptor.solver_id == descriptor.solver_id
            ]
            if stage_indices:
                pipeline_status = f"[bold #38bdf8]Staged in Pipeline (Stage {', '.join(stage_indices)})[/bold #38bdf8]"
            else:
                pipeline_status = "[dim]Not staged in pipeline[/dim]"
            lines.append(f"[bold]Pipeline Status:[/bold] {pipeline_status}")

            lines.append("")
            lines.append("[bold cyan]Description:[/bold cyan]")
            lines.append(f"  {descriptor.description}")
            lines.append("")
            lines.append("[bold cyan]Requirements:[/bold cyan]")
            lines.append(f"  {descriptor.required_components_desc}")
            lines.append("")
            lines.append("[bold cyan]Nominal Parameters:[/bold cyan]")
            for p_key, p_val in descriptor.default_params.items():
                p_label = p_key.replace("_", " ").title()
                lines.append(f"  • {p_label}: {p_val}")
            lines.append("")
            lines.append("[bold cyan]Primary Outputs:[/bold cyan]")
            for _, f_unit, f_label in descriptor.headline_outputs:
                unit_str = f" [{f_unit}]" if f_unit and f_unit != "-" else ""
                lines.append(f"  • {f_label}{unit_str}")
            lines.append("")
            lines.append(
                "[dim]Press [bold]r[/bold] to run solver • Press [bold]a[/bold] or [bold]↵ Enter[/bold] to stage into pipeline[/dim]"
            )

            content = self.query_one("#flightdeck-results-content", Static)
            content.remove_class("-wide-table")
            content.update("\n".join(lines))
            self._scroll_results_to_top()
        except NoMatches:
            pass

    def _render_run_results(
        self,
        descriptor: SolverDescriptor,
        results: Any,
        run_dir: Path | None = None,
    ) -> None:
        """Render execution telemetry metrics into results card.

        Args:
            descriptor: Executed solver descriptor.
            results: Strongly typed results object returned by the solver.
            run_dir: Directory where run artifacts were saved, if any.
        """
        try:
            results_card = self.query_one("#flightdeck-results-card", Container)
            results_card.border_title = "Simulation Telemetry"
            results_card.border_subtitle = "b Inspector  r Re-run"

            veh_name = self.active_vehicle.name if self.active_vehicle else "Unknown"
            lines: list[str] = [
                "[bold #10b981]SIMULATION EXECUTION COMPLETE[/bold #10b981]",
                f"[bold]{escape(descriptor.name)}[/bold]  •  Vehicle: {escape(veh_name)}",
                "",
                "[bold cyan]Headline Metrics:[/bold cyan]",
            ]

            for f_name, f_unit, f_label in descriptor.headline_outputs:
                if hasattr(results, f_name):
                    val = getattr(results, f_name)
                    if isinstance(val, (int, float)):
                        val_str = self._format_number(val, f_unit)
                        extra_str = ""
                        if f_unit == "m" and abs(val) >= 1000:
                            extra_str = f" ({val / 1000:.2f} km)"
                        elif f_unit == "Pa" and abs(val) >= 1000:
                            extra_str = f" ({val / 1000:.2f} kPa)"
                        unit_str = f" {f_unit}" if f_unit and f_unit != "-" else ""
                        lines.append(f"  • [bold]{f_label}:[/bold] {val_str}{unit_str}{extra_str}")
                    else:
                        lines.append(f"  • [bold]{f_label}:[/bold] {val}")

            if run_dir is not None:
                lines.append("")
                lines.append(f"[bold cyan]Artifacts Saved:[/bold cyan] [dim]{run_dir}[/dim]")

            lines.append("")
            lines.append(
                "[dim]Press [bold]b[/bold] to return to solver inspector • Press [bold]r[/bold] to re-run[/dim]"
            )

            content = self.query_one("#flightdeck-results-content", Static)
            content.remove_class("-wide-table")
            content.update("\n".join(lines))
            self._scroll_results_to_top()
        except NoMatches:
            pass

    def _render_historical_log(self, path: Path) -> None:
        """Format historical simulation run telemetry or artifact into results card.

        Args:
            path: Path to historical run directory or specific artifact file.
        """
        try:
            results_card = self.query_one("#flightdeck-results-card", Container)
            if path.is_file():
                results_card.border_title = f"File: {path.name}"
            else:
                results_card.border_title = f"Historical: {path.name}"
            results_card.border_subtitle = "o Open  f Folder  b Inspector"

            content = self.query_one("#flightdeck-results-content", Static)
            is_csv = path.is_file() and path.suffix.lower() == ".csv"
            content.set_class(is_csv, "-wide-table")
            content.update(render_flightlog_preview(path))
            self._scroll_results_to_top()
        except NoMatches:
            pass

    def _scroll_results_to_top(self) -> None:
        """Scroll the results container back to the top and left."""
        try:
            scroll = self.query_one("#flightdeck-results-scroll", ScrollableContainer)
            scroll.scroll_to(x=0, y=0, animate=False)
        except NoMatches:
            pass

    @staticmethod
    def _format_number(val: Any, unit: str = "") -> str:
        """Format numerical value with appropriate precision and scaling."""
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            return str(val)
        num = float(val)
        if num == 0.0:
            return "0"
        if unit == "Pa" and abs(num) >= 1000:
            return f"{num / 1000:.2f}"
        if abs(num) < 0.001 or abs(num) >= 1e6:
            return f"{num:.3e}"
        if abs(num) >= 100:
            return f"{num:.1f}"
        return f"{num:.3f}".rstrip("0").rstrip(".")

    def _refresh_pipeline_ui(self) -> None:
        """Update the pipeline option list."""
        try:
            pipeline_list = self.query_one("#flightdeck-pipeline-list", PipelineList)
            pipeline_list.clear_options()
            if not self.pipeline:
                pipeline_list.add_option(
                    Option(
                        "[dim]Pipeline is empty. Highlight a solver and press ↵ Enter to stage.[/dim]",
                        id="empty",
                        disabled=True,
                    )
                )
                return

            for idx, stage in enumerate(self.pipeline, start=1):
                is_ready, _ = check_solver_compatibility(stage.descriptor, self.active_vehicle)
                status_tag = (
                    "[bold #10b981][READY][/bold #10b981]"
                    if is_ready
                    else "[bold #f59e0b][INAPPLICABLE][/bold #f59e0b]"
                )
                label = f"Stage {idx}: [bold]{escape(stage.descriptor.name)}[/bold]  {status_tag}"
                pipeline_list.add_option(Option(prompt=label, id=f"stage_{idx}"))
        except NoMatches:
            pass

    def _notify(self, message: str, severity: str = "information") -> None:
        """Display notification message if active application context is available."""
        try:
            self.notify(message, severity=severity)  # type: ignore[arg-type]
        except (LookupError, RuntimeError, AttributeError):
            pass

    def stage_solver(self, descriptor: SolverDescriptor) -> None:
        """Stage a solver into the sequential pipeline.

        Args:
            descriptor: Metadata descriptor for the solver to add.
        """
        stage = PipelineStage(descriptor=descriptor, params=dict(descriptor.default_params))
        self.pipeline.append(stage)
        self._refresh_pipeline_ui()
        self.refresh_solvers_list()
        self._notify(
            f"Staged {descriptor.name} (Stage {len(self.pipeline)})",
            severity="information",
        )

    def run_solver(
        self, descriptor: SolverDescriptor, enable_logging: bool = True
    ) -> PointMassBoostResults | None:
        """Run a single solver on the active vehicle.

        Args:
            descriptor: Solver to execute.
            enable_logging: Whether FlightLogger creates disk artifacts. Defaults to True.

        Returns:
            The analysis results if successful, or None on failure.
        """
        if self.active_vehicle is None:
            self._notify(
                "No vehicle loaded. Please load a vehicle in Hangar.", severity="error"
            )
            return None

        is_ready, msg = check_solver_compatibility(descriptor, self.active_vehicle)
        if not is_ready:
            self._notify(f"Cannot run {descriptor.name}: {msg}", severity="error")
            return None

        try:
            solver = descriptor.solver_cls(descriptor.solver_id)
            params = dict(descriptor.default_params)
            if descriptor.solver_id == "point_mass_3dof_boost":
                fins_name = resolve_fins_name(self.active_vehicle)
                if fins_name:
                    params["fins_name"] = fins_name

            solver.setup(self.active_vehicle, enable_logging=enable_logging, **params)
            results = solver.execute()

            if enable_logging and hasattr(solver, "logger") and solver.logger.enabled:
                if descriptor.solver_id == "point_mass_3dof_boost" and isinstance(results, PointMassBoostResults):
                    ground_alt = params.get(
                        "ground_altitude_m", PointMass3DOFBoostAnalysis.DEFAULT_GROUND_ALTITUDE_M
                    )
                    stop_at_burnout = params.get(
                        "stop_at_burnout", PointMass3DOFBoostAnalysis.DEFAULT_STOP_AT_BURNOUT
                    )
                    if results.boost_samples is not None:
                        fig_boost = plot_boost_phase(
                            results.boost_samples,
                            burn_time_s=results.nominal_burn_time,
                            ground_altitude_m=ground_alt,
                        )
                        solver.logger.save_figure(fig_boost, "boost_phase.png", show=False)
                    if not stop_at_burnout and results.samples is not None:
                        fig_full = plot_full_flight(
                            results.samples,
                            burn_time_s=results.nominal_burn_time,
                            ground_altitude_m=ground_alt,
                        )
                        solver.logger.save_figure(fig_full, "full_flight.png", show=False)

                    sweep_angles = PointMass3DOFBoostAnalysis.DEFAULT_SWEEP_ANGLES_DEG
                    sweep_results = run_launch_angle_sweep(
                        self.active_vehicle,
                        angles_deg=sweep_angles,
                        altitude_m=params.get(
                            "altitude_m", PointMass3DOFBoostAnalysis.DEFAULT_ALTITUDE_M
                        ),
                        ground_altitude_m=ground_alt,
                        fins_name=params.get("fins_name"),
                        motor_name=params.get("motor_name"),
                        body_name=params.get("body_name"),
                        stop_at_burnout=stop_at_burnout,
                        t_max_s=params.get("t_max_s", PointMass3DOFBoostAnalysis.DEFAULT_T_MAX_S),
                    )
                    sweep_fig = plot_launch_angle_sweep(sweep_results, ground_altitude_m=ground_alt)
                    solver.logger.save_figure(sweep_fig, "launch_angle_sweep.png", show=False)
                    solver.logger.save_artifact("launch_angle_sweep.csv", format_sweep_csv(sweep_results))

                solver.logger.save_results(results)

            self._selected_flightlog_path = None
            output_dir = (
                solver.logger.output_dir
                if enable_logging and hasattr(solver, "logger") and solver.logger.enabled
                else None
            )
            self._render_run_results(descriptor, results, output_dir)
            burnout_mach = getattr(results, "burnout_mach", 0.0)
            self._notify(
                f"Completed {descriptor.name} (Mach {burnout_mach:.2f})",
                severity="information",
            )

            # Refresh flight logs tree
            try:
                tree = self.query_one("#flightdeck-runs-tree", FlightLogsTree)
                tree.populate()
            except NoMatches:
                pass

            return results
        except (RuntimeError, ValueError, KeyError, OSError, TypeError) as exc:
            self._notify(f"Execution error: {exc}", severity="error")
            return None

    def action_quick_run(self) -> None:
        """Execute the currently focused solver on the active vehicle."""
        try:
            store = self.query_one("#solvers-store-view", SolversStoreView)
            tile = store.get_focused_tile()
            if tile is not None:
                self.run_solver(tile.descriptor)
            else:
                self._notify(
                    "No solver selected. Click a solver to select it.", severity="warning"
                )
        except NoMatches:
            pass

    def action_stage_solver(self) -> None:
        """Stage the currently focused solver to the pipeline."""
        try:
            store = self.query_one("#solvers-store-view", SolversStoreView)
            tile = store.get_focused_tile()
            if tile is not None:
                self.stage_solver(tile.descriptor)
            else:
                self._notify(
                    "No solver selected. Click a solver to select it.", severity="warning"
                )
        except NoMatches:
            pass

    def action_clear_pipeline(self) -> None:
        """Clear all staged steps in the execution pipeline."""
        self.pipeline.clear()
        self._refresh_pipeline_ui()
        self.refresh_solvers_list()
        self._notify("Pipeline cleared", severity="information")

    def action_run_pipeline(self) -> None:
        """Execute all stages in the pipeline sequentially."""
        if not self.pipeline:
            self._notify("Pipeline is empty", severity="warning")
            return
        if self.active_vehicle is None:
            self._notify(
                "No vehicle loaded. Please load a vehicle in Hangar.", severity="error"
            )
            return

        for stage in self.pipeline:
            self.run_solver(stage.descriptor)

    def action_show_inspector(self) -> None:
        """Switch results card back to inspector view for current highlighted solver."""
        self._selected_flightlog_path = None
        if self._current_highlighted_descriptor is not None:
            is_ready, msg = check_solver_compatibility(
                self._current_highlighted_descriptor, self.active_vehicle
            )
            self._render_solver_inspector(
                self._current_highlighted_descriptor, is_ready, msg
            )

    @on(SolverTile.SolverHighlighted)
    def _on_solver_highlighted(
        self, event: SolverTile.SolverHighlighted
    ) -> None:
        """Handle solver highlighted in catalog list."""
        self._selected_flightlog_path = None
        self._current_highlighted_descriptor = event.descriptor
        self._render_solver_inspector(event.descriptor, event.is_ready, event.message)

    @on(SolverTile.SolverSelected)
    def _on_solver_selected(
        self, event: SolverTile.SolverSelected
    ) -> None:
        """Handle solver confirmation (via double-click, 'a', or Enter) to stage in pipeline."""
        self.stage_solver(event.descriptor)

    @on(SolverTile.SolverRunRequested)
    def _on_solver_run_requested(
        self, event: SolverTile.SolverRunRequested
    ) -> None:
        """Handle 'r' key on solver catalog (runs solver)."""
        self.run_solver(event.descriptor)

    @on(PipelineList.StageRemoved)
    def _on_stage_removed(self, event: PipelineList.StageRemoved) -> None:
        """Handle removal of a stage from the pipeline."""
        if 0 <= event.index < len(self.pipeline):
            removed = self.pipeline.pop(event.index)
            self._refresh_pipeline_ui()
            self.refresh_solvers_list()
            self._notify(f"Removed Stage {event.index + 1}: {removed.descriptor.name}")

    @on(FlightLogsTree.FlightLogHighlighted)
    def _on_flightlog_highlighted(
        self, event: FlightLogsTree.FlightLogHighlighted
    ) -> None:
        """Handle hover/highlight over historical flight log or artifact file."""
        if event.path is not None:
            try:
                tree = self.query_one("#flightdeck-runs-tree", FlightLogsTree)
                if tree.cursor_node and tree.cursor_node.data == event.path:
                    self._selected_flightlog_path = event.path
            except NoMatches:
                pass
            self._render_historical_log(event.path)
        else:
            self._restore_flightdeck_preview()

    @on(FlightLogsTree.FlightLogSelected)
    def _on_flightlog_selected(
        self, event: FlightLogsTree.FlightLogSelected
    ) -> None:
        """Handle selection of historical flight log or artifact file."""
        if event.path is not None:
            self._selected_flightlog_path = event.path
            self._render_historical_log(event.path)

    def _restore_flightdeck_preview(self) -> None:
        """Restore preview of persistently selected flight log, or solver inspector."""
        if self._selected_flightlog_path is not None:
            self._render_historical_log(self._selected_flightlog_path)
        elif self._current_highlighted_descriptor is not None:
            is_ready, msg = check_solver_compatibility(
                self._current_highlighted_descriptor, self.active_vehicle
            )
            self._render_solver_inspector(
                self._current_highlighted_descriptor, is_ready, msg
            )

    @on(FlightLogsTree.FlightLogDeleted)
    def _on_flightlog_deleted(self, event: FlightLogsTree.FlightLogDeleted) -> None:
        """Handle run deletion by resetting inspection if active run was deleted."""
        if self._selected_flightlog_path is not None and (
            self._selected_flightlog_path == event.path
            or str(self._selected_flightlog_path).startswith(str(event.path))
        ):
            self._selected_flightlog_path = None
            self.action_show_inspector()

    @on(events.Leave, "#flightdeck-runs-card")
    def _on_runs_card_leave(self) -> None:
        """Restore persistent flightlog preview or inspector when mouse leaves runs card."""
        self._restore_flightdeck_preview()

    @on(Button.Pressed, "#solver-stage-btn")
    def _on_stage_btn_pressed(self) -> None:
        """Handle click on Stage button."""
        self.action_stage_solver()

    @on(Button.Pressed, "#solver-run-btn")
    def _on_run_btn_pressed(self) -> None:
        """Handle click on Run button."""
        self.action_quick_run()

    @on(Button.Pressed, "#pipeline-clear-btn")
    def _on_clear_btn_pressed(self) -> None:
        """Handle click on Clear button."""
        self.action_clear_pipeline()

    @on(Button.Pressed, "#pipeline-run-btn")
    def _on_pipeline_run_btn_pressed(self) -> None:
        """Handle click on Run Pipeline button."""
        self.action_run_pipeline()
