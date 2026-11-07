"""Command-line entry point for YAADO.

``yaado`` opens the interactive Textual cockpit. ``yaado -b`` runs one solver as a
one-liner with no prompts or UI rendering, printing plain text or JSON to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from Terminal.solvers import (
    REPAIRED_SOLVERS,
    SolverDescriptor,
    SolverRun,
    execute_solver,
)
from YAADO_Core.Foundation.flight_logger import YaadoJSONEncoder
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig

_SOLVERS_BY_ID: dict[str, SolverDescriptor] = {d.solver_id: d for d in REPAIRED_SOLVERS}


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``yaado`` command.

    Returns:
        Parser covering the cockpit launch and all bare-mode options.
    """
    parser = argparse.ArgumentParser(
        prog="yaado",
        description="Open the YAADO cockpit, or run a solver without the UI using -b.",
        epilog=(
            "example:\n"
            "  yaado -b --vehicle Hangar/examples/ALVRJ/ALVRJ.toml \\\n"
            "           --solver point_mass_3dof_boost --set launch_angle_deg=45"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-b", "--bare", action="store_true", help="run without the interactive UI"
    )

    bare = parser.add_argument_group("bare mode options (require -b)")
    bare.add_argument("--vehicle", type=Path, metavar="TOML", help="vehicle configuration file")
    bare.add_argument(
        "--solver",
        choices=tuple(_SOLVERS_BY_ID),
        metavar="ID",
        help=f"solver to run: {', '.join(_SOLVERS_BY_ID)}",
    )
    bare.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="override a solver parameter, in the unit shown by --list-solvers (repeatable)",
    )
    bare.add_argument("--json", action="store_true", help="print results as JSON")
    bare.add_argument("--no-log", action="store_true", help="write nothing to FlightLogs/")
    bare.add_argument(
        "--no-sweep",
        action="store_true",
        help="skip the parameter sweep saved alongside logged runs",
    )
    bare.add_argument(
        "--list-solvers",
        action="store_true",
        help="list solvers and their parameters, then exit",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the ``yaado`` command: the Textual cockpit, or bare mode with ``-b``.

    Args:
        argv: Command-line arguments. Defaults to ``sys.argv[1:]``.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.bare:
        sys.exit(run_bare(parser, args))
    if any(value for name, value in vars(args).items() if name != "bare"):
        parser.error("solver options require -b")

    # Imported here so bare mode never loads Textual.
    from Terminal.app import YaadoApp

    sys.exit(YaadoApp().run())


def run_bare(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    """Execute one bare-mode invocation.

    Usage errors exit through ``parser.error`` with status 2.

    Args:
        parser: Parser used to report usage errors.
        args: Parsed command-line arguments.

    Returns:
        Process exit status: 0 on success, 1 if loading or solving failed.
    """
    if args.list_solvers:
        print(format_solver_list(REPAIRED_SOLVERS))
        return 0
    if args.vehicle is None or args.solver is None:
        parser.error("-b needs --vehicle and --solver (or --list-solvers)")

    descriptor = _SOLVERS_BY_ID[args.solver]
    try:
        params = parse_overrides(descriptor, args.overrides)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        vehicle = BaseVehicleConfig.from_toml(args.vehicle)
        run = execute_solver(
            descriptor,
            vehicle,
            params,
            enable_logging=not args.no_log,
            run_sweep=not args.no_sweep,
        )
    except (RuntimeError, ValueError, KeyError, OSError, TypeError) as exc:
        print(f"yaado: error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(format_run_json(descriptor, vehicle, run))
    else:
        print(format_run_text(descriptor, vehicle, run))
    return 0


def parse_overrides(descriptor: SolverDescriptor, overrides: Sequence[str]) -> dict[str, Any]:
    """Parse ``NAME=VALUE`` strings against the solver's parameter definitions.

    Args:
        descriptor: Solver whose parameters are being overridden.
        overrides: Raw ``NAME=VALUE`` strings from ``--set``.

    Returns:
        Parsed values keyed by parameter name.

    Raises:
        ValueError: On a malformed pair, an unknown name, or an invalid value.
    """
    param_defs = {p.name: p for p in descriptor.parameters}
    params: dict[str, Any] = {}
    for item in overrides:
        name, sep, raw = item.partition("=")
        param = param_defs.get(name.strip())
        if not sep or param is None:
            raise ValueError(
                f"--set {item!r}: expected NAME=VALUE with NAME one of {', '.join(param_defs)}"
            )
        try:
            params[param.name] = param.parse(raw)
        except ValueError as exc:
            raise ValueError(f"--set {param.name}: {exc}") from None
    return params


def format_solver_list(solvers: Sequence[SolverDescriptor]) -> str:
    """Format the solver catalog with each solver's tunable parameters and defaults.

    Args:
        solvers: Solver descriptors to list.

    Returns:
        Plain-text listing, one block per solver.
    """
    blocks: list[str] = []
    for d in solvers:
        rows = [
            (p.name, f"<{p.placeholder}>" if p.default is None else str(p.default), p.unit, p.description)
            for p in d.parameters
        ]
        header = f"{d.solver_id}  [L{d.fidelity.value}] {d.name}"
        blocks.append("\n".join([header, *_align(rows, indent="  ")]))
    return "\n\n".join(blocks)


def format_run_text(
    descriptor: SolverDescriptor, vehicle: BaseVehicleConfig, run: SolverRun
) -> str:
    """Format a finished run as aligned ``name value [unit]`` lines.

    Args:
        descriptor: Solver that produced the run.
        vehicle: Analyzed vehicle configuration.
        run: Outcome returned by :func:`execute_solver`.

    Returns:
        Plain-text summary of the headline outputs and the FlightLogs directory.
    """
    rows = [("solver", descriptor.solver_id), ("vehicle", vehicle.name)]
    for field_name, unit, _label in descriptor.headline_outputs:
        value = getattr(run.results, field_name)
        value_str = f"{value:.6g}" if isinstance(value, float) else str(value)
        rows.append((field_name, value_str if unit == "-" else f"{value_str} {unit}"))
    if run.output_dir is not None:
        rows.append(("flightlog", str(run.output_dir)))
    return "\n".join(_align(rows))


def format_run_json(
    descriptor: SolverDescriptor, vehicle: BaseVehicleConfig, run: SolverRun
) -> str:
    """Format a finished run as a JSON object with all scalar results and their units.

    Args:
        descriptor: Solver that produced the run.
        vehicle: Analyzed vehicle configuration.
        run: Outcome returned by :func:`execute_solver`.

    Returns:
        Indented JSON string.
    """
    payload = {
        "solver": descriptor.solver_id,
        "vehicle": vehicle.name,
        "params": run.params,
        "results": run.results.scalars(),
        "units": run.results.units(),
        "flightlog": run.output_dir,
    }
    return json.dumps(payload, cls=YaadoJSONEncoder, indent=2)


def _align(rows: Sequence[tuple[str, ...]], indent: str = "") -> list[str]:
    """Pad every column but the last to its widest cell."""
    if not rows:
        return []
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]) - 1)]
    lines = []
    for row in rows:
        cells = [cell.ljust(width) for cell, width in zip(row, widths, strict=False)]
        lines.append(indent + "  ".join([*cells, row[-1]]).rstrip())
    return lines
