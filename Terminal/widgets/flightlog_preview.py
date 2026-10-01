"""Contextual rich preview generator for FlightLogs artifacts and simulation runs.

Formats structured checkpoints, execution logs, CSV spreadsheets, and visual plots
into Rich renderables suitable for display in cockpit inspection panes.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Literal

from rich import box
from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text

ANALYSIS_DISPLAY_NAMES: dict[str, str] = {
    "point_mass_3dof_boost": "Point-Mass 3-DOF Boost",
    "point_mass_3dof": "Point-Mass 3-DOF",
    "aero_polar": "Aero Polars",
    "mass_estimation": "Mass & Inertia",
}

LOG_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}")


def format_file_size(size_bytes: int) -> str:
    """Format byte size into human-readable unit string.

    Args:
        size_bytes: Raw size in bytes.

    Returns:
        Formatted size string (e.g. '705 B', '112.6 KB', '1.22 MB').
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def format_number(val: Any, unit: str = "") -> str:
    """Format scalar numeric output in SI units with appropriate precision.

    Args:
        val: Numerical value or raw object.
        unit: Canonical SI unit string.

    Returns:
        Formatted string representation.
    """
    if isinstance(val, (int, float)):
        if unit == "-":
            return f"{val:.2f}"
        if abs(val) >= 1000 and unit in ("m", "Pa", "N"):
            return f"{val:,.1f}"
        if abs(val) < 0.01 and val != 0:
            return f"{val:.4e}"
        return f"{val:.2f}"
    return str(val)


def pretty_analysis_title(slug: str) -> str:
    """Retrieve human-readable title for an analysis identifier.

    Args:
        slug: Analysis identifier string.

    Returns:
        Display title string.
    """
    return ANALYSIS_DISPLAY_NAMES.get(slug, slug.replace("_", " ").title())


def generate_thumbnail(image_path: Path, width: int = 40, height: int = 16) -> Text | None:
    """Render a Unicode half-block ANSI truecolor thumbnail for a bitmap image.

    Args:
        image_path: Path to the image file (e.g. PNG).
        width: Character width of the thumbnail.
        height: Character height of the thumbnail (each char cell holds 2 vertical pixels).

    Returns:
        Rich Text instance with truecolor styles, or None if Pillow fails.
    """
    try:
        from PIL import Image
        from rich.color import Color
        from rich.style import Style

        with Image.open(image_path) as img:
            img_rgb = img.convert("RGB")
            resized = img_rgb.resize((width, height * 2))
            text = Text()
            for y in range(0, height * 2, 2):
                for x in range(width):
                    px1 = resized.getpixel((x, y))
                    px2 = resized.getpixel((x, y + 1))
                    if (
                        isinstance(px1, tuple)
                        and isinstance(px2, tuple)
                        and len(px1) >= 3
                        and len(px2) >= 3
                    ):
                        r1, g1, b1 = int(px1[0]), int(px1[1]), int(px1[2])
                        r2, g2, b2 = int(px2[0]), int(px2[1]), int(px2[2])
                        text.append(
                            "▀",
                            style=Style(
                                color=Color.from_rgb(r1, g1, b1),
                                bgcolor=Color.from_rgb(r2, g2, b2),
                            ),
                        )
                    else:
                        text.append(" ")
                text.append("\n")
            return text
    except (ImportError, OSError, ValueError, RuntimeError):
        return None


def _format_artifacts_manifest(run_dir: Path) -> list[str]:
    """Build bullet list of artifacts generated in a simulation run directory.

    Args:
        run_dir: Run directory path.

    Returns:
        List of rich markup lines detailing files and subdirectories.
    """
    lines: list[str] = ["", "[bold cyan]Run Files & Artifacts:[/bold cyan]"]
    if not run_dir.is_dir():
        return lines

    for item in sorted(run_dir.iterdir()):
        if item.name.startswith((".", "__")):
            continue
        if item.is_file():
            size_str = format_file_size(item.stat().st_size)
            lines.append(f"  • [white]{item.name}[/white] [dim]({size_str})[/dim]")
        elif item.is_dir():
            sub_files = [
                f for f in item.iterdir()
                if f.is_file() and not f.name.startswith((".", "__"))
            ]
            lines.append(f"  • [bold blue]{item.name}/[/bold blue] [dim]({len(sub_files)} files)[/dim]")

    lines.append("")
    lines.append(
        "[dim]Expand run in tree to inspect files • Press [bold]o[/bold] to open • Press [bold]f[/bold] to open folder[/dim]"
    )
    return lines


def _render_checkpoint(results_file: Path, run_dir: Path | None = None) -> RenderableType:
    """Format results.json checkpoint into telemetry metrics and file manifest.

    Args:
        results_file: Path to results.json file.
        run_dir: Containing run directory, defaults to parent of results_file.

    Returns:
        Rich Text instance containing formatted metrics.
    """
    containing_dir = run_dir or results_file.parent
    try:
        with open(results_file, encoding="utf-8") as f:
            res = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return Text(f"Error parsing {results_file.name}: {exc}", style="bold red")

    vehicle = res.get("vehicle_name", containing_dir.parent.name)
    analysis_name = res.get("analysis_name", containing_dir.name)
    fidelity = res.get("fidelity", "")
    data: dict[str, Any] = res.get("data", {})
    units_map: dict[str, str] = res.get("units", {})
    details: dict[str, Any] = res.get("details", {})
    headline_keys: list[str] = res.get("headline_metrics", [])

    if not headline_keys:
        candidate_headlines = (
            "apogee_altitude",
            "burnout_velocity",
            "burnout_mach",
            "q_max",
            "nominal_burn_time",
            "range_at_burnout",
            "final_x",
        )
        headline_keys = [k for k in candidate_headlines if k in data]

    pretty_analysis = pretty_analysis_title(analysis_name)
    lines: list[str] = [
        f"[bold #38bdf8]{pretty_analysis.upper()}[/bold #38bdf8]  [dim]Vehicle: {vehicle}[/dim]",
        f"[dim]Run: {containing_dir.name}  •  Fidelity: {fidelity}[/dim]",
        "",
    ]

    if headline_keys:
        lines.append("[bold cyan]Headline Metrics:[/bold cyan]")
        for k in headline_keys:
            if k in data:
                val = data[k]
                unit = units_map.get(k, "")
                val_str = format_number(val, unit)
                extra_str = ""
                if unit == "m" and isinstance(val, (int, float)) and abs(val) >= 1000:
                    extra_str = f" ({val / 1000:.2f} km)"
                elif unit == "Pa" and isinstance(val, (int, float)) and abs(val) >= 1000:
                    extra_str = f" ({val / 1000:.2f} kPa)"
                unit_str = f" {unit}" if unit and unit != "-" else ""
                label = k.replace("_", " ").title()
                lines.append(f"  • [bold]{label}:[/bold] {val_str}{unit_str}{extra_str}")
        lines.append("")

    remaining_keys = [k for k in sorted(data.keys()) if k not in headline_keys]
    if remaining_keys:
        lines.append("[bold cyan]Telemetry Metrics:[/bold cyan]")
        for k in remaining_keys:
            val = data[k]
            unit = units_map.get(k, "")
            unit_str = f" {unit}" if unit and unit != "-" else ""
            val_str = format_number(val, unit)
            label = k.replace("_", " ").title()
            lines.append(f"  • {label}: {val_str}{unit_str}")

    stopped_reason = details.get("stopped_reason")
    if stopped_reason:
        reason_str = str(stopped_reason).replace("_", " ").title()
        lines.append(f"\n[bold]Flight Termination:[/bold] {reason_str}")

    # Append run files manifest
    lines.extend(_format_artifacts_manifest(containing_dir))

    return Text.from_markup("\n".join(lines))


def _render_execution_log(log_file: Path, max_lines: int = 180) -> RenderableType:
    """Format execution.log file with highlighted severity levels and timestamps.

    Args:
        log_file: Path to log file.
        max_lines: Maximum number of recent lines to display.

    Returns:
        Rich Text instance containing colorized log output.
    """
    try:
        raw_text = log_file.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return Text(f"Unable to read log file {log_file.name}: {exc}", style="bold red")

    lines = raw_text.splitlines()
    text = Text()

    # Header
    size_str = format_file_size(log_file.stat().st_size)
    text.append(f"LOG: {log_file.name}\n", style="bold #38bdf8")
    text.append(
        f"Location: {log_file.parent.name}/{log_file.name}  •  Size: {size_str}  •  Lines: {len(lines)}\n",
        style="dim",
    )

    if not lines:
        text.append("\n(Log file is empty)\n", style="dim italic")
        return text

    visible_lines = lines
    if len(lines) > max_lines:
        skipped = len(lines) - max_lines
        text.append(
            f"\n[dim]--- Showing last {max_lines} lines (skipped {skipped} earlier lines • Press 'o' to view full file in editor) ---[/dim]\n\n"
        )
        visible_lines = lines[-max_lines:]
    else:
        text.append("\n")

    for line in visible_lines:
        if "[ERROR]" in line or "Traceback" in line:
            text.append(line + "\n", style="bold #ef4444")
        elif "[WARNING]" in line:
            text.append(line + "\n", style="#f59e0b")
        elif "[INFO]" in line:
            # Highlight INFO tag and message
            match = LOG_TIMESTAMP_PATTERN.match(line)
            if match:
                ts = match.group(0)
                rest = line[len(ts):]
                text.append(ts, style="dim")
                text.append(rest + "\n", style="#10b981")
            else:
                text.append(line + "\n", style="#10b981")
        elif "[DEBUG]" in line:
            text.append(line + "\n", style="dim #94a3b8")
        else:
            text.append(line + "\n")

    text.append(
        "\nPress 'o' to open in system text editor  •  Press 'f' to open containing folder\n",
        style="dim",
    )
    return text


def _format_csv_cell(val: str) -> tuple[str, Literal["left", "right"]]:
    """Format raw CSV string cell into a clean representation and column justification.

    Args:
        val: Raw string value from CSV file.

    Returns:
        Tuple of (formatted_string, alignment) where alignment is 'right' or 'left'.
    """
    v = val.strip()
    if not v:
        return "", "left"
    try:
        fval = float(v)
        # Small floating point numbers in scientific notation
        if abs(fval) < 1e-4 and fval != 0.0:
            return f"{fval:.3e}", "right"
        # Large numbers with thousand separators
        if abs(fval) >= 10000:
            if fval.is_integer() and "." not in v:
                return f"{int(fval):,}", "right"
            return f"{fval:,.2f}".rstrip("0").rstrip("."), "right"
        # Pure integers
        if fval.is_integer() and "." not in v:
            return f"{int(fval)}", "right"
        # General floats: max 4 significant decimal places, trim trailing zeroes
        formatted = f"{fval:.4f}".rstrip("0").rstrip(".")
        return formatted, "right"
    except ValueError:
        return v, "left"


def _render_csv_table(csv_file: Path, max_rows: int = 50) -> RenderableType:
    """Format tabular CSV file into a bordered Rich table with readable column widths.

    Enforces minimum column widths calculated from header and cell content with no_wrap,
    enabling smooth horizontal scrolling in wide tables rather than squishing columns.

    Args:
        csv_file: Path to CSV file.
        max_rows: Maximum data rows to render before truncation.

    Returns:
        Rich Table or Group renderable.
    """
    try:
        with open(csv_file, encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = list(reader)
    except OSError as exc:
        return Text(f"Unable to read CSV file {csv_file.name}: {exc}", style="bold red")

    if not rows:
        return Text(f"CSV {csv_file.name} is empty.", style="dim italic")

    header = rows[0]
    data_rows = [r for r in rows[1:] if any(r)]
    visible_rows = data_rows[:max_rows]

    # Pre-format cells to determine natural column widths
    formatted_data: list[list[str]] = []
    col_justifications: list[Literal["left", "right"]] = ["left"] * len(header)

    for row in visible_rows:
        padded_row = list(row) + [""] * (len(header) - len(row))
        formatted_row: list[str] = []
        for col_idx, cell in enumerate(padded_row[:len(header)]):
            cell_str, align = _format_csv_cell(cell)
            formatted_row.append(cell_str)
            if cell_str and align == "right":
                col_justifications[col_idx] = "right"
        formatted_data.append(formatted_row)

    table = Table(
        title=f"Data Table: {csv_file.name}",
        box=box.ROUNDED,
        border_style="#334155",
        header_style="bold #38bdf8",
    )

    for col_idx, col_name in enumerate(header):
        label = col_name.strip().replace("_", " ").title()
        max_content_len = len(label)
        for f_row in formatted_data:
            if col_idx < len(f_row):
                max_content_len = max(max_content_len, len(f_row[col_idx]))
        min_w = max_content_len + 2
        table.add_column(
            label,
            no_wrap=True,
            min_width=min_w,
            justify=col_justifications[col_idx],
            style="#f8fafc",
        )

    for f_row in formatted_data:
        table.add_row(*f_row)

    caption_lines: list[str] = []
    if len(data_rows) > max_rows:
        overflow = len(data_rows) - max_rows
        caption_lines.append(
            f"Showing first {max_rows} of {len(data_rows)} rows ({overflow} omitted)."
        )

    if len(header) > 5:
        caption_lines.append(
            "Wide Table: Scroll horizontally (Shift + Wheel / Scrollbar) to view all columns."
        )

    caption_lines.append(
        "Press 'o' to open in system spreadsheet  •  Press 'f' to open folder"
    )

    table.caption = "\n" + "\n".join(caption_lines)
    table.caption_style = "dim"
    table.caption_justify = "left"
    return table


def _render_image_figure(fig_file: Path) -> RenderableType:
    """Format figure metadata and system viewer launch action.

    Args:
        fig_file: Path to figure image (e.g. PNG).

    Returns:
        Rich Group or Text renderable.
    """
    size_str = format_file_size(fig_file.stat().st_size)
    header = Text()
    header.append(f"FIGURE: {fig_file.name}\n", style="bold #38bdf8")

    dim_str = ""
    try:
        from PIL import Image

        with Image.open(fig_file) as img:
            dim_str = f"Dimensions: {img.size[0]} x {img.size[1]} px  •  "
    except (ImportError, OSError, ValueError, RuntimeError):
        dim_str = ""

    header.append(f"{dim_str}Size: {size_str}  •  Path: {fig_file.parent.name}/{fig_file.name}\n\n", style="dim")

    action_text = Text()
    action_text.append(
        "Figure is opened in system default image viewer.\n\n",
        style="bold #10b981",
    )
    action_text.append(
        "Press 'o' or Enter to open again  •  Press 'f' to open containing figures folder\n",
        style="dim",
    )

    return Group(header, action_text)


def _render_generic_directory(dir_path: Path) -> RenderableType:
    """Format directory listing of files and subdirectories.

    Args:
        dir_path: Target directory path.

    Returns:
        Rich Text instance containing directory manifest.
    """
    lines: list[str] = [
        f"[bold #38bdf8]DIRECTORY:[/bold #38bdf8] [bold]{dir_path.name}/[/bold]",
        f"[dim]Location: {dir_path}[/dim]",
        "",
        "[bold cyan]Contents:[/bold cyan]",
    ]

    try:
        items = sorted(dir_path.iterdir())
        files = [i for i in items if i.is_file() and not i.name.startswith((".", "__"))]
        dirs = [i for i in items if i.is_dir() and not i.name.startswith((".", "__"))]

        for d in dirs:
            sub_count = len([f for f in d.iterdir() if f.is_file()])
            lines.append(f"  • [bold blue]{d.name}/[/bold blue] [dim]({sub_count} files)[/dim]")

        for f in files:
            size_str = format_file_size(f.stat().st_size)
            lines.append(f"  • [white]{f.name}[/white] [dim]({size_str})[/dim]")

        if not files and not dirs:
            lines.append("  [dim](Directory is empty)[/dim]")
    except OSError as exc:
        lines.append(f"  [red]Error reading directory: {exc}[/red]")

    lines.append("")
    lines.append(
        "[dim]Press [bold]o[/bold] or [bold]f[/bold] to open directory in system file manager[/dim]"
    )
    return Text.from_markup("\n".join(lines))


def _render_vehicle_directory(v_dir: Path) -> RenderableType:
    """Format summary of historical runs under a vehicle directory.

    Args:
        v_dir: Vehicle logs folder path.

    Returns:
        Rich Text instance containing vehicle run history overview.
    """
    runs = [
        d for d in sorted(v_dir.iterdir(), reverse=True)
        if d.is_dir() and not d.name.startswith((".", "__"))
    ]

    lines: list[str] = [
        f"[bold #38bdf8]VEHICLE RUNS:[/bold #38bdf8] [bold]{v_dir.name}[/bold]",
        f"[dim]Total recorded simulation runs: {len(runs)}[/dim]",
        "",
        "[bold cyan]Historical Runs:[/bold cyan]",
    ]

    for run_dir in runs:
        res_file = run_dir / "results.json"
        analysis_label = pretty_analysis_title(run_dir.name.split("_202")[0])
        ts_part = run_dir.name.split("_")[-2:]
        ts_str = " ".join(ts_part) if len(ts_part) == 2 else run_dir.name

        summary_part = ""
        if res_file.is_file():
            try:
                with open(res_file, encoding="utf-8") as f:
                    rdata = json.load(f).get("data", {})
                    if "burnout_mach" in rdata:
                        summary_part = f" • Mach {rdata['burnout_mach']:.2f}"
                    elif "apogee_altitude" in rdata:
                        summary_part = f" • Apogee {rdata['apogee_altitude'] / 1000:.1f} km"
            except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
                summary_part = ""

        lines.append(f"  • [white]{analysis_label}[/white] [dim]({ts_str}{summary_part})[/dim]")

    if not runs:
        lines.append("  [dim](No simulation runs recorded yet)[/dim]")

    lines.append("")
    lines.append(
        "[dim]Select or expand a run in the tree to inspect telemetry and artifacts[/dim]"
    )
    return Text.from_markup("\n".join(lines))


def render_flightlog_preview(path: Path | None) -> RenderableType:
    """Entrypoint: Generate contextual Rich renderable preview for any FlightLog item.

    Supports:
    - ``None`` -> Placeholder prompt.
    - Run folder -> Structured telemetry metrics & file manifest.
    - ``results.json`` -> Structured telemetry metrics & file manifest.
    - ``execution.log`` -> Formatted execution log with severity tags.
    - ``*.csv`` -> Bordered data table.
    - Bitmap figures (``.png``, ``.jpg``, etc.) -> Metadata, ANSI thumbnail & launcher.
    - Subdirectories (``figures/``, ``artifacts/``) -> Folder manifest.
    - Vehicle directory -> List of simulation runs.
    - Other files -> Generic text preview.

    Args:
        path: Path to target file or directory, or None.

    Returns:
        Rich RenderableType object suitable for ``Static.update(...)``.
    """
    if path is None:
        return Text.from_markup(
            "[dim]Select a simulation run or artifact to inspect telemetry and files.[/dim]"
        )

    if not path.exists():
        return Text(f"Target does not exist: {path}", style="bold red")

    # If it is a file:
    if path.is_file():
        suffix = path.suffix.lower()
        if path.name == "results.json":
            return _render_checkpoint(path)
        if suffix == ".json":
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                return Text(json.dumps(data, indent=2), style="cyan")
            except (json.JSONDecodeError, OSError, TypeError) as e:
                return Text(f"Invalid JSON in {path.name}: {e}", style="red")
        if suffix == ".log":
            return _render_execution_log(path)
        if suffix == ".csv":
            return _render_csv_table(path)
        if suffix in (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".svg"):
            return _render_image_figure(path)

        # Fallback text file preview
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()[:100]
            return Text("\n".join(lines))
        except OSError as exc:
            return Text(f"Unable to preview file {path.name}: {exc}", style="dim")

    # If it is a directory:
    if path.is_dir():
        # Check if it is a run directory (has results.json or execution.log)
        results_file = path / "results.json"
        if results_file.is_file():
            return _render_checkpoint(results_file, run_dir=path)
        log_file = path / "execution.log"
        if log_file.is_file():
            # A run directory that didn't complete results.json
            return _render_execution_log(log_file)

        # Check if it is a vehicle directory (parent is logs root)
        if path.parent.name == "FlightLogs":
            return _render_vehicle_directory(path)

        # Otherwise generic folder (e.g. figures/, artifacts/)
        return _render_generic_directory(path)

    return Text(f"Unsupported item: {path.name}", style="dim")
