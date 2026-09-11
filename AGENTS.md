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

## Project Rules (Mandatory)

1. **Always use SI units.** All internal variables, solvers, and Pydantic schema fields store canonical SI units as floats without unit suffixes in field names (`thrust`, `span`, `total_mass`). Component schemas declare canonical units via `UNITS: ClassVar[dict[str, str]]`, and `AnalysisResults` carries units in a dedicated `units: dict[str, str]` dictionary. Unit conversion for user input at the CLI boundary uses `openmdao.utils.units` (do not use Pint).
2. **Type hints** are required on all public functions.
3. **Google-style docstrings** (in English) for every public class and method.
4. **No specific project logic in Core:** `YAADO_Core` must operate on base Pydantic models. Never import a specific project schema from `Hangar/` into a core solver.
5. **Inheritance for Solvers, Composition for Data:** Extend solvers by inheriting from `BaseAnalysis`. However, vehicles and Pydantic schemas must be built using Composition (Lego bricks), not deep inheritance trees.
6. After every change, run tests: `uv run pytest --tb=short`.

## Running Tests

```bash
uv run pytest --tb=short
```

Dev dependencies are managed via `uv`. Submodules in `external/` are required for full execution, but core tests mock or gracefully handle missing binaries where possible.
