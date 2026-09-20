# Foundation

This directory contains the core abstractions, data contracts, and runtime infrastructure for the entire `YAADO_Core` framework. All custom physics solvers, structural modules, mission tools, and telemetry loggers across the repository are built on top of these base classes.

## Architectural Overview

| Module | Primary Class / Function | Purpose |
|---|---|---|
| [`analysis_base.py`](analysis_base.py) | `BaseAnalysis`, `BaseAnalysisResults`, `FidelityLevel` | Solver execution contract, typed result container base, and fidelity ladder. |
| [`units.py`](units.py) | Semantic SI Types (`Meters`, `Seconds`, `Newtons`, etc.) | Semantic type aliases using `typing.Annotated` for canonical SI physics fields. |
| [`solver_registry.py`](solver_registry.py) | `SolverRegistry`, `SolverInfo` | External tool dependency tracker (AVL, XFOIL, SU2, pyCycle). |
| [`vehicle_base.py`](vehicle_base.py) | `BaseVehicleConfig` | Global declarative I/O manager and Pydantic schema for vehicle configurations. |
| [`vehicle_factory.py`](vehicle_factory.py) | `VehicleFactory` | Superstructure translating declarative vehicle configs into `SUAVE.Vehicle` models. |
| [`flight_logger.py`](flight_logger.py) | `FlightLogger`, `YaadoJSONEncoder` | Run telemetry, diagnostic text logging, visual artifact management, and checkpoints. |
| [`mission_builder.py`](mission_builder.py) | `MissionBuilder`, `MissionProfile`, `AnyMissionSegment` | Solver-agnostic ordered mission profile builder and typed segment schemas. |


## 1. Analysis & Data Contracts (`analysis_base.py`, `units.py`, `solver_registry.py`)

`YAADO` uses explicit, decoupled data handoffs between computational modules.

### 1.1 `BaseAnalysis`
Every solver—whether a simple empirical equation or a massive CFD wrapper—inherits from `BaseAnalysis[TResult]`, adhering to the Template Method pattern:
* **`setup(vehicle, **kwargs)`**: Initializes `FlightLogger`, sets setup state flags, and delegates vehicle geometry extraction to the internal `_setup(vehicle, **kwargs)` hook.
* **`execute(**kwargs) -> TResult`**: Enforces prior setup, runs numerical computation via `_compute(**kwargs)`, verifies results via `validate_results(results)`, and returns the strongly-typed container.

### 1.2 `BaseAnalysisResults` & Semantic SI Units
Solvers are strictly forbidden from returning loose floats or untyped dictionaries (`data: dict`, `metadata: dict`). Instead, each discipline module defines frozen dataclasses inheriting from `BaseAnalysisResults`:
* **Typed Fields**: Physics metrics are explicit dataclass fields rather than string keys in a dictionary.
* **Semantic SI Units (`units.py`)**: Quantities are typed using semantic aliases such as `thrust: Newtons`, `burn_time: Seconds`, `velocity: MetersPerSecond`. Units are attached via `typing.Annotated[float, "unit_str"]`.
* **Reflection-Based Discovery**: Methods `scalars()` and `units()` inspect dataclass fields and annotations dynamically, enabling automated serialization without manual dictionary maintenance.

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
        ├── results.json        # Serialized BaseAnalysisResults checkpoint
        ├── summary.csv         # Formatted CSV metrics and execution metadata
        ├── figures/            # Matplotlib visual artifacts (.png)
        └── artifacts/          # Tabular sweeps, CSVs, or solver export scripts
```

### 3.2 Core Capabilities

1. **Diagnostic Logging (Replacing `print()`):**
   Provides structured severity levels (`debug`, `info`, `warning`, `error`, `exception`) with timestamped formatting in `execution.log`. Keeps terminal output clean via an optional `log_to_console` flag.
2. **Visual Data Management:**
   Saves matplotlib plots directly to `figures/` using `save_figure(fig, "polar.png")` and automatically closes figures to eliminate memory leaks during parameter sweeps. Headless-safe by default.
3. **Simulation Checkpointing:**
   Serializes `BaseAnalysisResults` to `results.json` and generates `summary.csv` using `save_results()`. Downstream analyses can restore typed results using `load_results(filename, result_cls)` with zero recomputation.
4. **Zero-Overhead Optimization Mode:**
   When running inside tight OpenMDAO optimization loops or Monte Carlo iterations, setting `enabled=False` bypasses all disk I/O, figure rendering, and file handlers with zero performance penalty.
5. **Context Manager Protocol:**
   Supports Python context management (`with FlightLogger(...) as logger:`) to guarantee proper closing and flushing of file handlers.

## 4. Mission Profile Definition (`mission_builder.py`)

### 4.1 `MissionBuilder`, `MissionProfile` & Typed Segments
Defines an ordered mission profile (e.g., boost, climb, cruise, descent, staging) as strongly-typed, immutable schemas without duplicating vehicle design parameters (`BaseVehicleConfig` remains the Single Source of Truth).

Segment schemas are validated via Pydantic v2 models with strict canonical SI units:
* **`BoostSegment`**: Launch angle, azimuth, rail length, active booster reference.
* **`ClimbSegment`**: Target altitude, target Mach/velocity, climb rate, throttle.
* **`CruiseSegment`**: Cruising altitude, Mach/velocity, distance or duration termination.
* **`DescentSegment`**: Target altitude, descent speed, throttle.
* **`StagingSegment`**: Coast duration, jettisoned component key.

`MissionBuilder` accepts pre-validated segment models directly via `.add_segment(...)`, enforces segment name uniqueness across the profile, and cross-validates subsystem references (`active_propulsion`, `jettison_component`) against the vehicle before producing an immutable `MissionProfile`. Segments are accessed directly via the strongly-typed `profile.segments` tuple:

```python
builder = MissionBuilder("harpoon_sea_skim", vehicle=vehicle)
profile = (
    builder
    .add_segment(BoostSegment(name="launch", launch_angle=83.0, active_propulsion="launch_booster"))
    .add_segment(StagingSegment(name="booster_sep", duration=0.5, jettison_component="launch_booster"))
    .add_segment(ClimbSegment(name="ingress", target_altitude=300.0, target_mach=0.8, active_propulsion="sustainer"))
    .add_segment(CruiseSegment(name="sea_skim", altitude=15.0, mach=0.85, distance=120000.0, active_propulsion="sustainer"))
    .add_segment(DescentSegment(name="terminal", target_altitude=0.0, target_mach=0.85))
    .build()
)

# Segments stored as an immutable tuple
assert len(profile.segments) == 5
assert profile.segments[0].name == "launch"
```