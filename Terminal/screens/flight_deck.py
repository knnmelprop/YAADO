"""Flight Deck view (Tab 3) for solver execution, pipelines, sweeps, and log inspection.

Provides interfaces to configure physics solvers discovered via SolverRegistry,
construct sequential computational pipelines, execute batch parameter sweeps,
and interactively review historical runs stored in FlightLogs.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from textual.containers import Container

if TYPE_CHECKING:
    from textual.app import ComposeResult



class FlightDeckView(Container):
    """Execution dashboard and simulation run inspector.

    Attributes:
        logs_root: Path to the root directory storing simulation run artifacts.
        selected_vehicle_name: The vehicle currently selected for analysis.
    """

    def __init__(
        self,
        logs_root: Path = Path("FlightLogs"),
        selected_vehicle_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Flight Deck view.

        Args:
            logs_root: Path to the FlightLogs directory.
            selected_vehicle_name: Initial vehicle selected for analysis.
            **kwargs: Standard Textual container keyword arguments.
        """
        super().__init__(**kwargs)
        self.logs_root = logs_root
        self.selected_vehicle_name = selected_vehicle_name

    def compose(self) -> ComposeResult:
        """Render the run setup pane, execution console drawer, and historical logs browser.

        Yields:
            Child widgets comprising the Flight Deck interface.
        """
        yield from ()

    def list_available_solvers(self) -> list[str]:
        """Query SolverRegistry for registered and verified analysis methods.

        Returns:
            List of usable solver names in the current environment.
        """

    def execute_solver_async(self, solver_name: str, params: dict[str, Any]) -> None:
        """Launch a solver run inside a non-blocking background worker thread.

        Args:
            solver_name: Identifier of the solver method to execute.
            params: Dictionary of solver input arguments in canonical SI units.
        """

    def execute_pipeline_async(self, pipeline_steps: list[tuple[str, dict[str, Any]]]) -> None:
        """Execute a chained sequence of computational solvers in a background thread.

        Args:
            pipeline_steps: Ordered list of (solver_name, parameter_dict) stages.
        """

    def execute_sweep_async(self, solver_name: str, sweep_variable: str, values: list[float]) -> None:
        """Execute a batch parameter sweep across a range of values in a background thread.

        Args:
            solver_name: Identifier of the solver to sweep.
            sweep_variable: Name of the independent variable being varied.
            values: List of parameter values to evaluate in SI units.
        """

    def load_historical_run(self, run_directory: Path) -> dict[str, Any]:
        """Load summary tables, figures, and execution logs from a past run directory.

        Args:
            run_directory: Path to a specific run folder in FlightLogs/.

        Returns:
            Dictionary containing parsed results, log paths, and figure paths.
        """
