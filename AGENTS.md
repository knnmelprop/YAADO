# YAADO — System Prompt & Context for Agents

This file provides critical context, repository architecture, and mandatory rules for all AI agents operating in the YAADO (Yet Another Aerospace Design Optimizer) repository.

> 🧭 **New agent session?** First, read `CONTRIBUTING.md` and `ONBOARDING.md`. They contain the full handoff: data-status discipline, branching rules, and conventions.

## Project Scope (Crucial Context)
YAADO is a **general, vehicle-agnostic preliminary design and MDO framework** intended for use by Polish Science Clubs. It acts as a strict, user-friendly superstructure over complex physics engines (SUAVE, SU2, pyCycle). 
* **Do NOT hardcode solvers to specific vehicles.** 
* **Do NOT import from `Hangar/` inside `YAADO_Core/`.** 

While the repository currently contains reference configurations in `Hangar/` (like the generic_uav and generic_rocket), the core framework (`YAADO_Core/`) must remain entirely generic and capable of analyzing any vehicle defined by the Pydantic schemas.

## Architecture

```text
├── YAADO_Core/              # Core Framework
│   ├── Foundation/          # BaseComponent, BaseAnalysis, FidelityLevel (L0–L3)
│   ├── FlightDeck/          # OpenMDAO Problems, mission evaluation logic
│   ├── ComponentStore/      # Pydantic v2 schemas (strict type validation)
│   ├── modules/             # Swappable physics solvers
│   │   ├── wind_tunnel/     # AVL, XFOIL, SU2, empirical correlations
│   │   ├── powerplant/      # pyCycle, generic engine maps
│   │   ├── flight_dynamics/ # Trajectory simulators
│   │   ├── stability_control/# Datcom, Barrowman
│   │   └── airframe/        # Geometry generation (OpenVSP) and meshing (Gmsh)
│   └── tests/               # Pytest unit suite mirroring modules/
│
├── Hangar/                  # User workspace: Declarative vehicle YAML configs
├── FlightLogs/              # User workspace: Output data, logs, and custom study scripts
└── external/                # Git submodules (SUAVE, pyCycle, SU2, OpenVSP)
```

## Project Rules (Mandatory)

1. **Always use SI units.** Field names must have a unit suffix (`thrust_N`, `span_m`, `isp_s`). Use `openmdao.utils.units` or Pint where possible.
2. **Type hints** are required on all public functions.
3. **Google-style docstrings** (in English) for every public class and method.
4. **No specific project logic in Core:** `YAADO_Core` must operate on base Pydantic models. Never import a specific project schema from `Hangar/` into a core solver.
5. **Inheritance for Solvers, Composition for Data:** Extend solvers by inheriting from `BaseAnalysis`. However, vehicles and Pydantic schemas must be built using Composition (Lego bricks), not deep inheritance trees.
6. After every change, run tests: `uv run pytest YAADO_Core/tests/ --tb=short`.

## Running Tests

```bash
uv run pytest YAADO_Core/tests/ --tb=short
```

Dev dependencies are managed via `uv`. Submodules in `external/` are required for full execution, but core tests mock or gracefully handle missing binaries where possible.
