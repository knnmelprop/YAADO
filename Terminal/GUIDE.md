# YAADO Terminal Guide

YAADO runs from the terminal in two ways: an interactive cockpit for building vehicles and exploring results, and a one-line bare mode for scripts and batch jobs.

## Interactive Cockpit

Run from the repository root:

```bash
uv run yaado
```

(or plain `yaado` with the project's virtual environment activated).

> [!IMPORTANT]
> Saved vehicles and solver outputs are written to `Hangar/` and `FlightLogs/` relative to the current directory, so launch from the repository root to keep them where the cockpit lists them.

> [!TIP]
> The cockpit needs a terminal of at least 110 columns by 28 rows; below that it hides the UI and asks you to maximize the window.

The cockpit has three tabs, and the footer always shows the keys available in the focused panel:

- **Main**: landing dashboard with solver readiness, the active vehicle and recent FlightLogs runs.
- **Hangar**: browse vehicles in `Hangar/`, fork the read-only references in `Hangar/examples/`, and assemble or edit vehicles from the Component Store.
- **Flight Deck**: tune solver parameters, stage and run pipelines, and review past runs in `FlightLogs/`.

## Bare Mode (`-b`)

`yaado -b` runs a single solver in one line, with no prompts and no UI. Results and FlightLogs artifacts are identical to a Flight Deck run.

```bash
# List solvers, their parameters, defaults and units
yaado -b --list-solvers

# Run a solver; prints headline outputs and the FlightLogs run directory
yaado -b --vehicle Hangar/examples/ALVRJ/ALVRJ.toml --solver point_mass_3dof_boost

# Override parameters and print machine-readable JSON instead
yaado -b --vehicle Hangar/examples/ALVRJ/ALVRJ.toml --solver point_mass_3dof_boost \
         --set launch_angle_deg=45 --set stop_at_burnout=false --json

# Ramjet cycle: Mach, combustor temperature and mass flow come from the vehicle unless set
yaado -b --vehicle Hangar/examples/ALVRJ/ALVRJ.toml --solver heiser_pratt_cycle \
         --set altitude_m=12000 --set eta_inlet=0.8

# Static stability: static margin at Mach 0.5 with the burnout CG
yaado -b --vehicle Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml --solver barrowman_stability \
         --set mach=0.5 --set cg_from_nose=2.2

# Body lift at 8 deg angle of attack, and the tail-fin span that meets the required margin
yaado -b --vehicle Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml --solver barrowman_extended \
         --set alpha_deg=8

# Supersonic static margin (DATCOM-class build-up) at Mach 2.5
yaado -b --vehicle Hangar/examples/ALVRJ/ALVRJ.toml --solver datcom_class_stability --set mach=2.5

# Supersonic cross-check: Ackeret fins against Barrowman at Mach 2.5
yaado -b --vehicle Hangar/examples/ALVRJ/ALVRJ.toml --solver ackeret_fin_check --set mach=2.5
```

| Option | Effect |
|---|---|
| `--vehicle TOML` | Vehicle configuration file to analyze. |
| `--solver ID` | Solver to run (see `--list-solvers`). |
| `--set NAME=VALUE` | Override a solver parameter, in the unit listed by `--list-solvers`. Repeatable. Defaults in `<angle brackets>` come from the vehicle or fuel. |
| `--json` | Print all scalar results, units, parameters and the run directory as JSON. |
| `--no-log` | Write nothing to `FlightLogs/`. |
| `--no-sweep` | Skip the parameter sweep (and its figure and CSV) saved with logged runs. |
| `--list-solvers` | List the solver catalog, then exit. |

For the ramjet cycle, set real losses on the engine in the vehicle TOML (see the [module README](../YAADO_Core/modules/powerplant/cycle_methods/README.md)). `--set` overrides them, and the run warns about each loss that falls back to a placeholder.

For static stability, give each fin set its position with `root_le_from_nose` in the vehicle TOML (see the [module README](../YAADO_Core/modules/stability_control/methods/barrowman/README.md)). A single fin set without it is placed flush with the aft end of the body, and the run says so.

Logged runs are saved to `FlightLogs/<vehicle>/<solver>_<timestamp>/` under the current directory. Exit status is `0` on success, `1` if the vehicle cannot be loaded or the solver fails, and `2` for invalid arguments. Errors go to stderr, so stdout stays clean for piping.
