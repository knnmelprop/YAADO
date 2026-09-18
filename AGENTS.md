# YAADO — System Prompt & Context for Agents

This file provides critical context, repository architecture, and mandatory rules for all AI agents operating in the YAADO (Yet Another Aerospace Design Optimizer) repository.

> 🧭 **New agent session?** First, read `CONTRIBUTING.md` and `ONBOARDING.md`. They contain the full handoff: data-status discipline, branching rules, and conventions.

## Project Scope (Crucial Context)
YAADO is a **general, vehicle-agnostic preliminary design and MDO framework** intended for use by Polish Science Clubs. It acts as a strict, user-friendly superstructure over complex physics engines (SUAVE, SU2, pyCycle). 
* **Do NOT hardcode solvers to specific vehicles.** 
* **Do NOT import from `Hangar/` inside `YAADO_Core/`.** 

While the repository currently contains reference configurations in `Hangar/examples/` (like the AGM-84 Harpoon and ALVRJ), the core framework (`YAADO_Core/`) must remain entirely generic and capable of analyzing any vehicle defined by the Pydantic schemas.

## Architecture

```text
├── YAADO_Core/              # Core Framework
│   ├── Foundation/          # BaseVehicleConfig, BaseAnalysis, FidelityLevel (L0–L3)
│   ├── FlightDeck/          # Mission & Optimization Orchestrator
│   ├── ComponentStore/      # Pydantic v2 schemas (strict type validation)
│   ├── modules/             # Swappable physics solvers
│   │   ├── wind_tunnel/     # AVL, XFOIL, SU2, empirical correlations
│   │   ├── powerplant/      # pyCycle, generic engine maps
│   │   ├── flight_dynamics/ # Trajectory simulators
│   │   ├── stability_control/# Datcom, Barrowman
│   │   └── airframe/        # Geometry generation (OpenVSP) and meshing (Gmsh)
│
├── tests/                   # Pytest unit suite mirroring entire repo structure
├── Terminal/                # CLI, vehicle assembly, template generation
├── Hangar/                  # User workspace: Declarative vehicle TOML configs
├── FlightLogs/              # User workspace: Output data, logs, and custom study scripts
└── external/                # Git submodules (SUAVE, pyCycle, SU2, OpenVSP)
```

## General Project Rules (Mandatory)

1. **Always use SI units.** All internal variables, solvers, and Pydantic schema fields store canonical SI units as floats without unit suffixes in field names (`thrust`, `span`, `total_mass`). Component schemas declare canonical units via `UNITS: ClassVar[dict[str, str]]`, and `AnalysisResults` carries units in a dedicated `units: dict[str, str]` dictionary. Unit conversion for user input at the CLI boundary might use `openmdao.utils.units` (do not use Pint).
2. **Type hints** are required on all public functions.
3. **Google-style docstrings** (in English) for every public class and method.
4. **Inheritance for Solvers, Composition for Data:** Extend solvers by inheriting from `BaseAnalysis`. However, vehicles and Pydantic schemas must be built using Composition (Lego bricks), not deep inheritance trees.
5. After every change, run tests: `uv run pytest --tb=short`.

## Obligatory Coding Principles (Mandatory)

These are necessary to keep the repository scalabale and maintainable.

* **Kill untyped dictionaries; use typed containers**:
  * Do not use untyped dictionaries for internal state or multi-variable returns. Use typed, frozen dataclasses (e.g. `TrajectorySamples`, `TrajectoryMetrics`).
  * Remove dictionary emulation methods (`to_dict`, `from_dict`, `__getitem__`, `get`, `__contains__`) and "backwards compatibility" shims. The framework does not need them; `FlightLogger` / `YaadoJSONEncoder` serializes dataclasses natively via `asdict()`.
  * Do not churn metadata dictionaries in loops. Sweeps and ODE routines should only extract and return the raw numbers or dataclasses needed, avoiding repeated 40-key documentation dict allocations.
  * Strip out filler comments, self-evident docstrings, and essays in comments.

* **Single source of truth & centralized constants**:
  * Import universal physics constants (`G0`, `R_AIR`, `P0_ISA`, etc.) from `YAADO_Core.Foundation.constants`. Do not define loose duplicates at the top of files. If any constants are missing they must be added to `YAADO_Core.Foundation.constants`.
  * ALWAYS centralized atmosphere models from `YAADO_Core.Foundation.atmosphere` (`isa_atmosphere` for scalar, `isa_atmosphere_array` for vectorized).

* **Component resolving (no hardcoded schemas)**:
  * Scripts must operate on generic registry tuples and union types in `ComponentStore` (e.g. `BOOSTER_COMPONENTS` / `AnyBoosterComponent`, `BODY_COMPONENTS` / `AnyBodyComponent`, `AERO_COMPONENTS` / `AnyAeroComponent`).
  * NEVER hardcode specific leaf classes (like `SolidMotor` or `Fuselage`) in logic or type annotations. Subsystem discovery must use `isinstance(comp, SUBSYSTEM_COMPONENTS)`.
  * NEVER import vehicle schemas from `Hangar/` into `YAADO_Core/`.

* **Strict data contracts & mypy/ruff compliance**:
  * AVOID dual-path typing: NEVER accept `T | Mapping[str, Any]` and NEVER write `if isinstance(x, dict): ... else: ...` to accommodate loose mock tests. Fix the tests to supply the typed dataclass/model.
  * AVOID redundant runtime type casting (e.g. unnecessary `float(...)` or `int(...)` calls in hot ODE loops). If Mypy complains about types, fix the upstream return signatures (e.g. separating scalar vs. vectorized functions).
  * When external libraries require function attributes (like SciPy's `solve_ivp` event callables `terminal` and `direction`), attach them via `setattr()` to satisfy static checkers cleanly.
  * The scripts must pass mypy and ruff checks with zero errors.

* **Single entry-point**:
  * No standalone `argparse` blocks, CLI scripts, or runnable `if __name__ == "__main__":` blocks. All execution goes through the main YAADO CLI (`Terminal/`).

* **Verification on real TOML configurations**:
  * Make sure the method can actually run by testing it on an actual TOML file from `Hangar/examples/` (or via vehicle factory), not just synthetic unit mocks.
  * Ensure the full test suite passes: `uv run pytest --tb=short`.
  * The `pytest` test suite MUST NOT involve generation of any files in `FlightLogs/`.

## Running Tests

```bash
uv run pytest --tb=short
```

Dev dependencies are managed via `uv`. Submodules in `external/` are required for full execution, but core tests mock or gracefully handle missing binaries where possible.
