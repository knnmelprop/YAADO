# YAADO Terminal

`Terminal/` is YAADO's single entry point: the `yaado` command opens the Textual cockpit, and `yaado -b` runs solvers as a one-liner. This file is for developers; usage is described in [GUIDE.md](GUIDE.md).

## Package Layout

| Path | Role |
|---|---|
| [`cli.py`](cli.py) | `yaado` entry point: starts the cockpit, or bare mode with `-b`. |
| [`solvers.py`](solvers.py) | UI-free solver catalog, compatibility rules and execution shared by the Flight Deck and bare mode. |
| [`app.py`](app.py) | Textual application: tab navigation, global keys and the active vehicle. |
| [`screens/`](screens/) | The Main, Hangar and Flight Deck tab views. |
| [`widgets/`](widgets/) | Reusable widgets: vehicle and FlightLogs trees, Component Store, parameter forms, modals, previews. |
| [`Assembly/`](Assembly/) | Vehicle template generation and assembly (see its [README](Assembly/README.md)). |
| [`formatting.py`](formatting.py) | Compact value, unit and aerospace-symbol formatting for labels. |
| [`system_utils.py`](system_utils.py) | Opens files and folders in the operating system's default applications. |
| [`theme.tcss`](theme.tcss) | Textual stylesheet. |

## How It Fits Together

- `cli.py` imports `Terminal.app` only when no `-b` is given, so bare mode never loads Textual. Keep Textual and `rich` imports out of `cli.py` and `solvers.py`.
- `execute_solver()` in `solvers.py` is the only execution path: `FlightDeckView.run_solver` and bare mode both call it. It checks vehicle compatibility, merges parameter overrides over the catalog defaults, runs the solver and saves its FlightLogs artifacts.
- `SolverParam.parse()` holds the value parsing and bound checks used by both the Flight Deck form and `--set`.
- `FlightLogger` and `HangarView` write `FlightLogs/` and `Hangar/` relative to the current directory, while the vehicle and FlightLogs trees resolve them from the repository root.

## Adding a Solver

Add its `SolverDescriptor` to `REPAIRED_SOLVERS` and its prerequisites to `check_solver_compatibility` in `solvers.py`; it then appears in the Flight Deck and in `yaado -b --list-solvers`.

## Tests

Tests live in `tests/Terminal/`, mirroring this package. They must not write to `FlightLogs/`: logged runs should `monkeypatch.chdir(tmp_path)` first, or run with `enable_logging=False` / `--no-log`.
