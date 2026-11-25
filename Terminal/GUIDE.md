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

Flight Deck solvers run in the background, so you can keep using the cockpit while a slow solver such as XFOIL runs. The results card shows the solver that is running, and the results replace it when the solver finishes. Only one run at a time is possible: the run buttons are disabled until it finishes. To cancel the run, press `k` or `Esc` on the Flight Deck. XFOIL and Gmsh are stopped at once; the other solvers are quick and stop when their calculation ends. A cancelled solver saves no FlightLogs run, and the later stages of a pipeline do not run. If you quit during a run, YAADO cancels it and exits at once.

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

# Parametric cycle per unit air flow: specific thrust, TSFC and efficiencies at Mach 3
yaado -b --vehicle Hangar/examples/ALVRJ/ALVRJ.toml --solver mattingly_cycle --set mach=3 --set tt4=2200

# Nozzle throat and exit sized for full expansion, for a 0.05 m^2 inlet capture area
yaado -b --vehicle Hangar/examples/ALVRJ/ALVRJ.toml --solver grzywka_nozzle --set capture_area=0.05

# Inlet recovery of a 21 deg conical spike at the ramjet's design Mach
yaado -b --vehicle Hangar/examples/ALVRJ/ALVRJ.toml --solver conical_inlet --set cone_half_angle_deg=21

# Multi-ramp inlet: optimum 4-ramp schedule, or given ramp angles as a comma list
yaado -b --vehicle Hangar/examples/ALVRJ/ALVRJ.toml --solver multi_shock_inlet --set n_oblique_shocks=4
yaado -b --vehicle Hangar/examples/ALVRJ/ALVRJ.toml --solver multi_shock_inlet --set deflections_deg=8,9,10

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

# XFOIL section polar of one surface; fins need an airfoil
yaado -b --vehicle Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml --solver xfoil_polar \
         --set surface=planar_equivalent --set mach=0.3
yaado -b --vehicle Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml --solver xfoil_polar \
         --set surface=aft_control_fins --set airfoil=NACA0010 --set alpha_end_deg=20

# SU2 Euler decks for a 3 x 3 Mach and angle-of-attack grid at 10 km
yaado -b --vehicle Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml --solver su2_euler_decks \
         --set mach_list=0.8,1.5,2.5 --set alpha_list_deg=-2,0,4 --set altitude_m=10000

# Euler mesh of the vehicle for SU2, and a STEP file of it
yaado -b --vehicle Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml --solver gmsh_euler_mesh \
         --set cells_per_diameter=12 --set fin_thickness_ratio=0.05

# Cross-sections of a STEP model, compared with the vehicle
yaado -b --vehicle Hangar/examples/ALVRJ/ALVRJ.toml --solver gmsh_step_slicer \
         --set step_file=Hangar/geometry/airframe.step --set axis=x
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

For the XFOIL polar, pick the wing or fin set with `--set surface=NAME`, unless the vehicle has only one. The `xfoil` executable must be on `PATH`; on Ubuntu and Debian the packaged build needs a wrapper (see the [module README](../YAADO_Core/modules/wind_tunnel/methods/xfoil/README.md#installing-xfoil)).

For the Euler mesh, give each wing its position with `root_le_from_nose`, and fins an `airfoil` or a `thickness_ratio`, in the vehicle TOML (see the [module README](../YAADO_Core/modules/airframe/mesher_methods/README.md)). An unplaced wing is left out, and fins without a thickness get `fin_thickness_ratio`; the run says so. The SU2 decks for the mesh are for half a vehicle unless you set `half_model=false`.

For the STEP slicer, put the CAD model in `Hangar/geometry` or any other `Hangar` folder, exported as solid bodies (see the [module README](../YAADO_Core/modules/airframe/slicer_methods/README.md)).

For static stability, give each fin set its position with `root_le_from_nose` in the vehicle TOML (see the [module README](../YAADO_Core/modules/stability_control/methods/barrowman/README.md)). A single fin set without it is placed flush with the aft end of the body, and the run says so.

Logged runs are saved to `FlightLogs/<vehicle>/<solver>_<timestamp>/` under the current directory. Exit status is `0` on success, `1` if the vehicle cannot be loaded or the solver fails, and `2` for invalid arguments. Errors go to stderr, so stdout stays clean for piping.
