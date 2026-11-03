# YAADO Terminal

`Terminal/` is YAADO's single entry point. The `yaado` command opens an interactive cockpit built on [`Textual`](https://textual.textualize.io/) for vehicle assembly, solver runs and FlightLogs inspection; `yaado -b` runs the same solvers as a one-liner for scripts and batch jobs.

## Launching the Cockpit

Run from the repository root:

```bash
uv run yaado
```

(or plain `yaado` with the project's virtual environment activated).

> [!IMPORTANT]
> Saved vehicles and solver outputs are written to `Hangar/` and `FlightLogs/` relative to the current directory, so launch from the repository root to keep them where the cockpit lists them.

> [!TIP]
> The cockpit needs a terminal of at least 110 columns by 28 rows; below that it hides the UI and asks you to maximize the window.

## Cockpit Tabs

| Tab | Key | Purpose |
|---|---|---|
| Main | `m` | Landing dashboard: solver readiness, active vehicle summary, recent FlightLogs runs. |
| Hangar | `h` | Browse vehicles in `Hangar/`, fork the read-only references in `Hangar/examples/`, and assemble or edit vehicles from the Component Store. |
| Flight Deck | `f` | Tune solver parameters, stage and run pipelines, and review past runs in `FlightLogs/`. |

Global keys are `q` (quit), `d` (toggle dark/light theme) and the tab keys above. Keys of the focused panel take precedence and are always listed in the footer:

| Panel | Keys |
|---|---|
| Vehicle library | `enter` select, `n` new, `c` copy, `r` rename, `d` delete |
| Component Store | `a` add to vehicle |
| Flight Deck (any panel) | `x` run pipeline, `c` clear pipeline, `b` back to inspector |
| Flight Deck solver tile | `a` / `enter` add to pipeline, `r` run solver |
| Flight Deck pipeline stage | `d` delete stage |
| FlightLogs browser | `enter` open, `o` open file externally, `f` open folder, `d` delete run |

## Bare Mode (`-b`)

`yaado -b` runs a single solver in one line, with no prompts, no TUI and no rich rendering. It uses the same execution path as the Flight Deck (`Terminal/solvers.py`), so results and FlightLogs artifacts are identical.

```bash
# List solvers, their parameters, defaults and units
yaado -b --list-solvers

# Run a solver; prints headline outputs and the FlightLogs run directory
yaado -b --vehicle Hangar/examples/ALVRJ/ALVRJ.toml --solver point_mass_3dof_boost

# Override parameters and print machine-readable JSON instead
yaado -b --vehicle Hangar/examples/ALVRJ/ALVRJ.toml --solver point_mass_3dof_boost \
         --set launch_angle_deg=45 --set stop_at_burnout=false --json
```

| Option | Effect |
|---|---|
| `--vehicle TOML` | Vehicle configuration file to analyze. |
| `--solver ID` | Solver to run (see `--list-solvers`). |
| `--set NAME=VALUE` | Override a solver parameter, in the unit listed by `--list-solvers`. Repeatable. |
| `--json` | Print all scalar results, units, parameters and the run directory as JSON. |
| `--no-log` | Write nothing to `FlightLogs/`. |
| `--no-sweep` | Skip the parameter sweep (and its figure and CSV) saved with logged runs. |
| `--list-solvers` | List the solver catalog, then exit. |

Exit status is `0` on success, `1` if the vehicle cannot be loaded or the solver fails, and `2` for invalid arguments. Errors go to stderr, so stdout stays clean for piping.

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

To expose a new verified solver, add its `SolverDescriptor` to `REPAIRED_SOLVERS` and its prerequisites to `check_solver_compatibility` in `solvers.py`; it then appears in the Flight Deck and in `yaado -b --list-solvers`.
