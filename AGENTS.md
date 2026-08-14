# MELprop-IADE — Integrated Aircraft Design Environment

A project by the **KNN MELprop** Student Science Club (Warsaw University of Technology).
The repository is based on a **SUAVE** fork (SUAVE code is included as a git submodule in `external/suave/trunk/SUAVE/`, pinned to version 2.5.2 — DO NOT modify it).

> 🧭 **New agent session?** First, read [`docs/AGENT_CONTEXT.md`](docs/AGENT_CONTEXT.md)
> — it contains the full handoff: repository state, dependency setup, how to run analyses, completed
> work, known issues, and next steps. Live tracker: [`docs/ramP/analysis_status.md`](docs/ramP/analysis_status.md).

## Architecture

```text
core/                    # Foundation — extend via inheritance, DO NOT rewrite
  component_base.py      #   BaseComponent, BaseAnalysis, FidelityLevel (L0–L3),
                         #   AnalysisResults, ComponentRegistry
  vehicle_factory.py     #   SUAVE vehicle factory (builders per vehicle_type)
  mission_builder.py     #   Mission segment builder (solver-agnostic)
  solver_registry.py     #   External solver registry (AVL, XFOIL, ...)
src/schemas/             # Pydantic v2 schemas for vehicle configurations
vehicles/                # YAML vehicle configurations (gtm140_drone/, ramjet_rocket/)
analyses/aerodynamics/   # AVL wrapper, XFOIL, empirical rocket aero
analyses/propulsion/     # pyCycle (ramjet), solid rocket, GTM-140 performance map
workflows/               # OpenMDAO Problems, MDO, staging events
tests/unit/              # pytest
.agents/                 # Subagent definitions (aero-analyst, propulsion-designer, ...)
```

## Two Projects

### Project A — Drone with GTM-140 Engine
- Engine: Jetpol GTM-140 — Polish miniature **turbojet** (turbojet,
  NOT turbofan — no propeller).
- Aerodynamics: fixed wing, subsonic, VLM (AVL); airfoils: XFOIL (low Re).
- Config: `vehicles/gtm140_drone/vehicle_config.yaml`.

### Project B — Two-stage Ramjet Rocket
- Stage 1: post-Soviet solid rocket motor (booster).
- Stage 2: custom designed ramjet, target Mach 2–3.
- Aerodynamics: body-of-revolution + fins, empirical correlations
  (DATCOM-style). **DO NOT use AVL for the supersonic part.**
- Staging event: ramjet takes over propulsion after Stage 1 burnout.
- Config: `vehicles/ramjet_rocket/vehicle_config.yaml`.

## Project Rules (Mandatory)

1. **Always use SI units.** Field names must have a unit suffix (`thrust_N`,
   `span_m`, `isp_s`). Use `openmdao.utils.units` or Pint where possible.
2. **Type hints** are required on all public functions.
3. **Google-style docstrings** (in English) for every public class and method.
4. Every new file must start with: `# MELprop-IADE | [module name] | v0.1.0`.
5. DO NOT commit secrets, tokens, or passwords. The `.env` file (if it exists) must be ignored.
6. DO NOT rewrite code in `core/` — extend it through inheritance.
7. Method limitations: AVL is only for Ma < 0.6 and alpha < 15°; for higher values —
   use empirical correlations.
8. After every change, run: `python -m pytest tests/ -v --tb=short`.
9. Values marked with `# TBD` in YAML files are placeholders — they require real
   data (GTM-140 datasheet, rocket motor documentation) before running analyses.

## Subagents (`.agents/`)

| Agent | Claude model | ChatGPT model | Gemini model | File Scope |
|---|---|---|---|---|
| aero-analyst | latest claude-sonnet | latest terra | latest gemini-pro | `analyses/aerodynamics/`, `tests/test_aero_*.py` |
| propulsion-designer | latest claude-opus | latest sol | latest gemini-pro | `analyses/propulsion/`, `tests/test_propulsion_*.py` |
| vehicle-builder | latest claude-sonnet | latest terra | latest gemini-pro | `src/schemas/`, `vehicles/**`, `tests/test_vehicles_*.py` |
| mission-planner | latest claude-sonnet | latest terra | latest gemini-pro | `workflows/`, `tests/test_missions_*.py` |
| code-reviewer | latest claude-haiku | latest luna | latest gemini-flash | read-only everything, write only to `tests/` |
| docs-writer | latest claude-haiku | latest luna | latest gemini-flash | `notebooks/`, `*.md` |

## Running Tests

```bash
python -m pytest tests/ -v --tb=short
```

Dev dependencies: `pydantic>=2`, `pyyaml`, `pytest`. SUAVE (submodule in `external/suave/`) is
optional for unit tests — SUAVE imports in `core/` are guarded
and the modules will function without it.
