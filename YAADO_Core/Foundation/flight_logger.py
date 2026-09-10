"""FlightLogger subsystem for run telemetry, artifact management, and checkpointing.

This module manages execution logs, matplotlib visual figures, auxiliary artifacts,
and simulation checkpoints organized under the ``FlightLogs/{vehicle_name}/{analysis_name}_{datetime}/``
hierarchy.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import matplotlib.figure

    from YAADO_Core.Foundation.analysis_base import AnalysisResults


class YaadoJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder supporting NumPy, Pydantic, Enums, and Path objects.

    Extends standard library ``json.JSONEncoder`` to ensure physics solver outputs,
    numerical arrays, and metadata serialize cleanly without manual conversion.
    """

    def default(self, o: Any) -> Any:
        """Serialize custom objects to JSON-compatible primitives.

        Handles:
            - NumPy floats and ints -> Python float / int.
            - NumPy ndarrays -> list via ``.tolist()``.
            - Pydantic models -> dict via ``.model_dump(mode="json")``.
            - Path objects -> str.
            - Enums -> enum value or name.
            - datetime objects -> ISO 8601 string.
        """
        # Functionality: To be implemented in next step.
        return super().default(o)


class FlightLogger:
    """Centralized manager for run logs, figures, artifacts, and checkpoints.

    Organizes all simulation outputs into a standardized directory structure:
    ``FlightLogs/{vehicle_name}/{analysis_name}_{datetime}/`` containing:
    - ``execution.log``: Timestamped text logs (INFO, WARNING, ERROR, DEBUG).
    - ``results.json``: Checkpoint containing scalar data and metadata.
    - ``figures/``: Generated visual artifacts (plots, polars, charts).
    - ``artifacts/``: Tabular sweeps, CSVs, or solver export scripts.

    Args:
        vehicle_name: Name of the vehicle configuration being analyzed.
        analysis_name: Name of the analysis method or solver.
        enabled: If False, disables all disk I/O, figure rendering, and file
            logging for high-speed optimization loops (OpenMDAO/sweeps).
        log_to_console: Whether to attach a console StreamHandler. Defaults to False.
        show_figures: Whether save_figure automatically shows pop-up windows. Defaults to False.
        log_level: Minimum severity level to capture. Defaults to logging.INFO.
    """

    def __init__(
        self,
        vehicle_name: str,
        analysis_name: str,
        enabled: bool = True,
        log_to_console: bool = False,
        show_figures: bool = False,
        log_level: int = logging.INFO,
    ) -> None:
        """Initialize the FlightLogger with vehicle, analysis, and datetime directory paths."""
        self.vehicle_name = vehicle_name
        self.analysis_name = analysis_name
        self.enabled = enabled
        self.log_to_console = log_to_console
        self.show_figures = show_figures
        self.log_level = log_level

        # Format datetime string for folder naming: e.g. "2026-09-09_215332"
        self.timestamp_str = datetime.now().strftime("%Y-%m-%d_%H%M")  # noqa: DTZ005

        # Folder layout: FlightLogs/{vehicle_name}/{analysis_name}_{datetime}/
        self.run_folder_name = f"{analysis_name}_{self.timestamp_str}"
        self.output_dir = Path("FlightLogs") / vehicle_name / self.run_folder_name
        self.figures_dir = self.output_dir / "figures"
        self.artifacts_dir = self.output_dir / "artifacts"
        self.log_file_path = self.output_dir / "execution.log"

        self.logger = logging.getLogger(f"YAADO.{vehicle_name}.{analysis_name}")
        self._setup_directories()
        self._setup_logging()

    def _setup_directories(self) -> None:
        """Create output, figures, and artifacts directories if logging is enabled.

        When ``self.enabled`` is True, ensures that ``self.output_dir``,
        ``self.figures_dir``, and ``self.artifacts_dir`` exist on disk using
        ``mkdir(parents=True, exist_ok=True)``. Does nothing when disabled.
        """
        if not self.enabled:
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def _setup_logging(self) -> None:
        """Configure file and console logging handlers on the underlying logger.

        Flushes, closes, and removes any stale ``FileHandler`` instances from
        previous runs on this logger before attaching a fresh ``FileHandler``
        pointing to ``self.log_file_path`` with timestamped formatting:
        ``%(asctime)s [%(levelname)s] [%(name)s]: %(message)s``.
        If ``self.log_to_console`` is True, attaches a ``logging.StreamHandler``.
        """
        self.logger.setLevel(self.log_level)

        if not self.enabled:
            return

        self.logger.propagate = False

        # Clean up any previous FileHandlers from earlier runs on this logger
        for h in list(self.logger.handlers):
            if isinstance(h, logging.FileHandler):
                h.flush()
                h.close()
                self.logger.removeHandler(h)

        # Attach clean FileHandler for this specific run
        file_handler = logging.FileHandler(self.log_file_path, encoding="utf-8")
        file_handler.setLevel(self.log_level)
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        self._file_handler = file_handler

        # Configure console StreamHandler
        if self.log_to_console:
            has_console = any(
                isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
                for h in self.logger.handlers
            )
            if not has_console:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(self.log_level)
                console_formatter = logging.Formatter(
                    "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
                )
                console_handler.setFormatter(console_formatter)
                self.logger.addHandler(console_handler)
                self._console_handler = console_handler
        else:
            # If console is disabled, ensure any old console handler is removed
            for h in list(self.logger.handlers):
                if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
                    self.logger.removeHandler(h)

    # -------------------------------------------------------------------------
    # Diagnostic / Text Logging Methods
    # -------------------------------------------------------------------------

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an informational message to execution.log and console (if active).

        Args:
            msg: Log message string (supports %-style format specifiers).
            *args: Formatting arguments for ``msg``.
            **kwargs: Extra arguments forwarded to ``logging.Logger.info``.
        """
        if self.enabled:
            self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a warning message (e.g. low stability margin, solver fallback).

        Args:
            msg: Warning message string.
            *args: Formatting arguments for ``msg``.
            **kwargs: Extra arguments forwarded to ``logging.Logger.warning``.
        """
        if self.enabled:
            self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an error message indicating an analysis failure or invalid input.

        Args:
            msg: Error message string.
            *args: Formatting arguments for ``msg``.
            **kwargs: Extra arguments forwarded to ``logging.Logger.error``.
        """
        if self.enabled:
            self.logger.error(msg, *args, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a detailed diagnostic message for debugging solver internals.

        Args:
            msg: Debug message string.
            *args: Formatting arguments for ``msg``.
            **kwargs: Extra arguments forwarded to ``logging.Logger.debug``.
        """
        if self.enabled:
            self.logger.debug(msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an error message accompanied by the current exception traceback.

        Args:
            msg: Error description to accompany the traceback.
            *args: Formatting arguments for ``msg``.
            **kwargs: Extra arguments forwarded to ``logging.Logger.exception``.
        """
        if self.enabled:
            self.logger.exception(msg, *args, **kwargs)

    # -------------------------------------------------------------------------
    # Visual Artifact Management
    # -------------------------------------------------------------------------

    def save_figure(
        self,
        fig: matplotlib.figure.Figure,
        filename: str,
        dpi: int = 150,
        transparent: bool = False,
        show: bool = False,
        close: bool = True,
    ) -> Path | None:
        """Save a matplotlib figure to the run's figures directory and optionally display/close it.

        Args:
            fig: Matplotlib Figure instance to save.
            filename: Target filename (e.g., 'polar_grid.png'). Defaults to '.png'
                extension if none is provided.
            dpi: Image resolution in dots per inch. Defaults to 150.
            transparent: Whether background should be transparent. Defaults to False.
            show: Whether to display the figure in an interactive pop-up window
                before closing.
            close: Whether to close the figure after saving/displaying. Defaults to True.

        Returns:
            Resolved Path to the saved figure, or None if logging is disabled.
        """
        import matplotlib.pyplot as plt

        saved_path = None

        if self.enabled:
            target_path = self.figures_dir / filename
            if not target_path.suffix:
                target_path = target_path.with_suffix(".png")

            target_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(target_path, dpi=dpi, transparent=transparent, bbox_inches="tight")
            self.debug("Saved figure %s to %s", filename, target_path)
            saved_path = target_path

        should_show = self.show_figures and show
        if should_show:
            try:
                plt.show()
            except (RuntimeError, ImportError, AttributeError, OSError) as e:
                self.warning("Unable to display interactive figure pop-up: %s", e)

        if close:
            plt.close(fig)

        return saved_path

    # -------------------------------------------------------------------------
    # Checkpointing & Result Serialization
    # -------------------------------------------------------------------------

    def save_results(
        self,
        results: AnalysisResults | dict[str, Any],
        filename: str = "results.json",
        indent: int = 2,
    ) -> Path | None:
        """Save analysis outputs as a structured JSON checkpoint.

        Functionality:
            1. Converts ``results`` to a dictionary containing ``vehicle_name``,
               ``analysis_name``, ``timestamp_utc``, ``fidelity``, ``data``, and
               ``metadata``.
            2. Serializes dictionary into ``self.output_dir / filename`` using
               ``YaadoJSONEncoder`` to safely encode NumPy arrays, NumPy floats,
               and Pydantic schemas.
            3. Logs an informational message confirming the saved checkpoint path.
            4. Returns the resolved Path, or None if logging is disabled.

        Args:
            results: AnalysisResults container or dictionary of results.
            filename: Checkpoint filename. Defaults to "results.json".
            indent: JSON indentation level. Defaults to 2.

        Returns:
            Resolved Path to the written JSON checkpoint, or None if disabled.
        """
        pass

    def load_results(self, filename: str = "results.json") -> AnalysisResults:
        """Load an AnalysisResults checkpoint from this run directory.

        Functionality:
            1. Reads the JSON file at ``self.output_dir / filename``.
            2. Parses the JSON structure and reconstructs an ``AnalysisResults``
               dataclass (restoring ``name``, ``fidelity``, scalar ``data`` dict,
               and nested ``metadata`` dict).
            3. Enables downstream analyses to consume precomputed physics without
               re-running simulations.

        Args:
            filename: Checkpoint filename in ``self.output_dir``. Defaults to "results.json".

        Returns:
            Reconstructed AnalysisResults dataclass.

        Raises:
            FileNotFoundError: If the specified checkpoint file does not exist.
        """
        pass

    # -------------------------------------------------------------------------
    # Auxiliary Artifact Management
    # -------------------------------------------------------------------------

    def save_artifact(
        self,
        filename: str,
        content: str | bytes,
    ) -> Path | None:
        """Save an auxiliary file (CSV sweeps, tables, meshes) to artifacts/.

        Functionality:
            Writes raw string (text/CSV) or bytes (binary data) into
            ``self.artifacts_dir / filename``, creating the parent directory if needed.
            Returns the saved Path, or None if logging is disabled.

        Args:
            filename: Destination filename within ``self.artifacts_dir``.
            content: String (text/CSV) or bytes (binary data) to write.

        Returns:
            Resolved Path to the saved artifact, or None if logging is disabled.
        """
        pass

    # -------------------------------------------------------------------------
    # Lifecycle & Cleanup
    # -------------------------------------------------------------------------

    def close(self) -> None:
        """Flush and close all logging handlers cleanly.

        Functionality:
            Iterates through all handlers attached to ``self.logger``, flushes
            their buffers, closes underlying file streams, and removes handlers
            to prevent open file descriptor leaks.
        """
        pass

