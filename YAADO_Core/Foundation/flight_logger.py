"""FlightLogger subsystem for run telemetry, artifact management, and checkpointing.

This module manages execution logs, matplotlib visual figures, auxiliary artifacts,
and simulation checkpoints organized under the ``FlightLogs/{vehicle_name}/{analysis_name}_{datetime}/``
hierarchy.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

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
            - Enums -> enum value.
            - datetime/date objects -> ISO 8601 string.
        """
        # NumPy arrays
        if hasattr(o, "tolist") and callable(o.tolist):
            return o.tolist()
        # NumPy scalars (float64, int32, bool_)
        if hasattr(o, "item") and callable(o.item):
            return o.item()
        # Enums (e.g. FidelityLevel)
        if isinstance(o, Enum):
            return o.value
        # Pydantic v2 models
        if isinstance(o, BaseModel):
            return o.model_dump(mode="json")
        # Pathlib paths
        if isinstance(o, Path):
            return str(o)
        # datetime / date objects
        if isinstance(o, (datetime, date)):
            return o.isoformat()
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
    def _write_summary_csv(
        self,
        data: dict[str, Any],
        units: dict[str, str],
        filepath: Path,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Write a human-readable CSV summary table with metrics and bottom metadata table.

        Args:
            data: Dictionary of scalar outputs in SI units.
            units: Dictionary of units mapping metric names to their SI unit symbol.
            filepath: Destination file path for the CSV.
            metadata: Optional dictionary of metadata to append in a secondary table.
        """
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # Table 1: Primary Metrics
            writer.writerow(["metric", "value", "unit"])
            for key, val in data.items():
                unit = units.get(key, "-")
                try:
                    num_val = float(val)
                    val_str = (
                        f"{int(num_val)}"
                        if num_val.is_integer()
                        else f"{num_val:.6g}"
                    )
                except (ValueError, TypeError):
                    val_str = str(val)
                writer.writerow([key, val_str, unit])

            # Table 2: Execution & Checkpoint Metadata (placed at bottom for Excel sorting)
            writer.writerow([])
            writer.writerow(["metadata", "value", "unit"])
            writer.writerow(["vehicle", self.vehicle_name, "-"])
            writer.writerow(["analysis", self.analysis_name, "-"])
            writer.writerow(["timestamp", self.timestamp_str, "-"])

            if metadata:
                for m_key, m_val in metadata.items():
                    # Only serialize primitive scalar metadata to avoid polluting CSV
                    if isinstance(m_val, (int, float, bool, str)):
                        writer.writerow([m_key, str(m_val), "-"])

    def save_results(
        self,
        results: AnalysisResults,
        filename: str = "results.json",
        indent: int = 2,
    ) -> Path | None:
        """Save analysis outputs as a structured JSON checkpoint and summary CSV.

        Writes scalar SI outputs, explicit units metadata, free-form metadata,
        vehicle name, and timestamp into ``self.output_dir / filename`` using
        ``YaadoJSONEncoder``, and writes ``summary.csv`` alongside it.

        Args:
            results: AnalysisResults container.
            filename: Checkpoint filename. Defaults to "results.json".
            indent: JSON indentation level. Defaults to 2.

        Returns:
            Resolved Path to the written JSON checkpoint, or None if disabled.
        """
        if not self.enabled:
            return None

        from YAADO_Core.Foundation.analysis_base import AnalysisResults

        if not isinstance(results, AnalysisResults):
            raise TypeError(
                f"Unsupported results type: {type(results).__name__}; "
                "save_results strictly requires an AnalysisResults instance."
            )

        target_path = self.output_dir / filename
        if not target_path.suffix:
            target_path = target_path.with_suffix(".json")

        target_path.parent.mkdir(parents=True, exist_ok=True)

        fidelity_val = getattr(results.fidelity, "value", results.fidelity)
        data_dict = results.data
        units_dict = results.units
        metadata_dict = results.metadata
        analysis_name = results.name or self.analysis_name

        payload = {
            "vehicle_name": self.vehicle_name,
            "analysis_name": analysis_name,
            "timestamp": self.timestamp_str,
            "fidelity": fidelity_val,
            "data": data_dict,
            "units": units_dict,
            "metadata": metadata_dict,
        }

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, cls=YaadoJSONEncoder, indent=indent)

        # Automatically write summary.csv alongside results.json
        if isinstance(data_dict, dict) and data_dict:
            summary_csv_path = self.output_dir / "summary.csv"
            full_meta = {"fidelity": fidelity_val, **metadata_dict}
            self._write_summary_csv(
                data=data_dict,
                units=units_dict,
                filepath=summary_csv_path,
                metadata=full_meta,
            )

        self.info("Saved results checkpoint to %s", target_path)
        return target_path

    def load_results(self, filename: str = "results.json") -> AnalysisResults:
        """Load an AnalysisResults checkpoint from this run directory.

        Args:
            filename: Checkpoint filename in ``self.output_dir``. Defaults to "results.json".

        Returns:
            Reconstructed AnalysisResults dataclass with data, units, and metadata.

        Raises:
            FileNotFoundError: If the specified checkpoint file does not exist.
            ValueError: If the checkpoint JSON is missing 'fidelity' or contains an invalid fidelity level.
        """
        from YAADO_Core.Foundation.analysis_base import AnalysisResults, FidelityLevel

        target_path = self.output_dir / filename
        if not target_path.suffix:
            target_path = target_path.with_suffix(".json")

        if not target_path.is_file():
            raise FileNotFoundError(f"Results checkpoint not found at: {target_path}")

        with open(target_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        if "fidelity" not in payload:
            raise ValueError(f"Corrupted checkpoint in {target_path}: missing 'fidelity' key")

        try:
            fidelity = FidelityLevel(payload["fidelity"])
        except ValueError as err:
            valid_levels = [lvl.value for lvl in FidelityLevel]
            raise ValueError(
                f"Corrupted checkpoint in {target_path}: invalid fidelity level {payload['fidelity']!r}. "
                f"Must be one of {valid_levels}."
            ) from err

        return AnalysisResults(
            name=payload.get("analysis_name", self.analysis_name),
            fidelity=fidelity,
            data=payload.get("data", {}),
            metadata=payload.get("metadata", {}),
            units=payload.get("units", {}),
        )

    # -------------------------------------------------------------------------
    # Auxiliary Artifact Management
    # -------------------------------------------------------------------------

    def save_artifact(
        self,
        filename: str,
        content: str | bytes,
    ) -> Path | None:
        """Save an auxiliary file (CSV sweeps, tables, meshes) to artifacts/.

        Args:
            filename: Destination filename within ``self.artifacts_dir``.
            content: String (text/CSV) or bytes (binary data) to write.

        Returns:
            Resolved Path to the saved artifact, or None if logging is disabled.
        """
        if not self.enabled:
            return None

        target_path = self.artifacts_dir / filename
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, bytes):
            target_path.write_bytes(content)
        elif isinstance(content, str):
            target_path.write_text(content, encoding="utf-8")
        else:
            raise TypeError(f"content must be str or bytes, got {type(content)}")

        self.debug("Saved artifact %s to %s", filename, target_path)
        return target_path

    # -------------------------------------------------------------------------
    # Lifecycle & Cleanup
    # -------------------------------------------------------------------------

    def close(self) -> None:
        """Flush and close all logging handlers cleanly."""
        for h in list(self.logger.handlers):
            h.flush()
            if isinstance(h, logging.FileHandler):
                h.close()
            self.logger.removeHandler(h)

