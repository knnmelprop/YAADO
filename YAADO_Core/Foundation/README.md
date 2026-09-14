# Foundation

This directory contains the core abstractions, data contracts, and runtime infrastructure for the entire `YAADO_Core` framework. All custom physics solvers, structural modules, mission tools, and telemetry loggers across the repository are built on top of these base classes.

## Architectural Overview

| Module | Primary Class / Function | Purpose |
|---|---|---|
| [`analysis_base.py`](analysis_base.py) | `BaseAnalysis`, `AnalysisResults`, `FidelityLevel` | Solver execution contract, uniform result container, and fidelity ladder. |
| [`solver_registry.py`](solver_registry.py) | `SolverRegistry`, `SolverInfo` | External tool dependency tracker (AVL, XFOIL, SU2, pyCycle). |
| [`vehicle_base.py`](vehicle_base.py) | `BaseVehicleConfig` | Global declarative I/O manager and Pydantic schema for vehicle configurations. |
| [`vehicle_factory.py`](vehicle_factory.py) | `suave_vehicle_from_config` | Superstructure translating declarative vehicle configs into `SUAVE.Vehicle` models. |
| [`flight_logger.py`](flight_logger.py) | `FlightLogger` | Run telemetry, diagnostic text logging, visual artifact management, and checkpoints. |
| [`mission_builder.py`](mission_builder.py) | `MissionBuilder`, `MissionSegment` | Solver-agnostic ordered mission profile builder (climb, cruise, boost). |

## 1. Analysis & Data Contracts (`analysis_base.py`, `solver_registry.py`)

`YAADO` uses explicit, decoupled data handoffs between computational modules.

### 1.1 `BaseAnalysis`
Every solver—whether a simple empirical equation or a massive CFD wrapper—must inherit from `BaseAnalysis`:
* **`setup(vehicle, operating_state)`**: Extracts geometry and initializes underlying solvers.
* **`execute()`**: Solves the physics and returns an `AnalysisResults` container.

### 1.2 `AnalysisResults`
Solvers are forbidden from returning loose floats or undocumented dictionaries. They **must** return an `AnalysisResults` dataclass:
* **`data`**: Purely numerical scalar outputs in **SI units** (e.g., `{"thrust_N": 450.0, "CL": 0.35}`).
* **`metadata`**: Free-form context (e.g., station tables, polar arrays, solver assumptions, warnings).

### 1.3 `FidelityLevel`
Analyses declare their fidelity on a standardized ladder (`LEVEL_0` to `LEVEL_3`) so that optimization workflows can swap low-fidelity empirical methods with high-fidelity CFD without breaking downstream pipelines.

### 1.4 `SolverRegistry`
A central registry declaring which external binaries a workflow requires. It checks availability on the system `PATH` before execution begins, avoiding mid-run crashes.

## 2. Vehicle Abstraction & SUAVE Factory (`vehicle_base.py`, `vehicle_factory.py`)

`YAADO_Core` acts as a vehicle-agnostic superstructure over complex physics engines like `SUAVE`.

### 2.1 `BaseVehicleConfig`
The universal blueprint for all vehicles, validated via Pydantic v2 schemas. It manages reading from and serializing to declarative TOML vehicle definitions in the `Hangar/` workspace.

### 2.2 `VehicleFactory` & SUAVE Integration
Users define their vehicles declaratively without touching SUAVE code. `vehicle_factory.py` validates the configuration and automatically synthesizes a fully wired `SUAVE.Vehicle` object in the background.

## 3. Telemetry & Checkpointing (`flight_logger.py`)

`FlightLogger` is the centralized telemetry, artifact, and checkpoint manager for all YAADO analyses. It eliminates ad-hoc `print()` statements and keeps `YAADO_Core/` pure by routing all runtime outputs to the user-facing `FlightLogs/` workspace.

### 3.1 Directory Architecture

Whenever an analysis runs, `FlightLogger` organizes its outputs under:

```text
FlightLogs/
└── {vehicle_name}/
    └── {analysis_name}_{YYYY-MM-DD_HHMM}/
        ├── execution.log       # Timestamped diagnostic logs (replacing print)
        ├── results.json        # Serialized AnalysisResults checkpoint
        ├── figures/            # Matplotlib visual artifacts (.png)
        └── artifacts/          # Tabular sweeps, CSVs, or solver export scripts
```

### 3.2 Core Capabilities

1. **Diagnostic Logging (Replacing `print()`):**
   Provides structured severity levels (`debug`, `info`, `warning`, `error`, `exception`) with timestamped formatting in `execution.log`. Keeps terminal output clean via an optional `log_to_console` flag.
2. **Visual Data Management:**
   Saves matplotlib plots directly to `figures/` using `save_figure(fig, "polar.png")` and automatically closes figures to eliminate memory leaks during parameter sweeps.
3. **Simulation Checkpointing:**
   Serializes `AnalysisResults` to `results.json` using `save_results()` so downstream analyses (e.g., flight dynamics loading precomputed aerodynamic polars) can resume studies with zero re-computation.
4. **Zero-Overhead Optimization Mode:**
   When running inside tight OpenMDAO optimization loops or Monte Carlo iterations, setting `enabled=False` bypasses all disk I/O, figure rendering, and file handlers with zero performance penalty.

## 4. Mission Profile Definition (`mission_builder.py`)

### 4.1 `MissionBuilder` & `MissionSegment`
Defines an ordered mission profile (e.g., climb, cruise, boost, stage separation) as plain, solver-agnostic records. These records are later mapped onto SUAVE mission segments or OpenMDAO trajectory phases during mission evaluation.