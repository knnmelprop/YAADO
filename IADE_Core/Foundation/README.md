# Foundation

This directory contains the core abstractions and data contracts for the entire `IADE_Core` framework. All custom physics solvers, structural modules, and mission tools across the repository are built on top of these base classes.

## The Data Contract Architecture

`IADE` uses explicit, decoupled data handoffs between modules.

This architecture relies on two strict rules defined in `analysis_base.py`:

### 1. `BaseAnalysis`
Every solver—whether it is a simple empirical equation or a massive CFD wrapper—must inherit from `BaseAnalysis`.
* Modules must implement a `setup()` method to receive inputs (usually bound from the declarative YAML vehicle configurations).
* Modules must implement an `execute()` method to run the math and output the results.

### 2. `AnalysisResults`
When `execute()` finishes, it is strictly forbidden from returning loose floats or custom objects. It **must** return an `AnalysisResults` dataclass. This acts as a universal "shipping container" containing:
* `data`: A dictionary of purely numerical scalar outputs in strict **SI units** (e.g., `{"thrust_N": 450.0}`).
* `metadata`: A dictionary for free-form context (e.g., warnings, mesh sizes, solver assumptions).

Because this contract is composed entirely of primitive Python dictionaries, it serializes instantly to JSON. Modules dump their `AnalysisResults` to the `FlightLogs/` directory, where downstream modules can load them directly from disk.

## Vehicle Factory & SUAVE Integration

`IADE_Core` acts as a user-friendly superstructure over the highly complex `SUAVE` flight mechanics engine.

Users define their aircraft using simple, declarative YAML files in the `Hangar/` workspace. The `vehicle_factory.py` script takes those validated YAML configurations and automatically translates them into `SUAVE.Vehicle` objects in the background.

# Vehicle Base (`vehicle_base.py`)

The purpose of this method is to be a global I/O manager for all vehicle configurations. It contains the list of all available modules as well.