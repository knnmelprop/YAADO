# MELprop-IADE — Agent Context & Repository Handoff

> Onboarding for the next agent session. Read this together with the root
> [`CLAUDE.md`](../CLAUDE.md) (architecture + hard rules) and
> [`docs/ramP/analysis_status.md`](ramP/analysis_status.md) (live task tracker).
> Last updated: 2026-07-09.

---

## 1. What this repo is

A fork of **SUAVE** (aircraft-design toolbox, in `trunk/SUAVE/` — **do not modify**)
extended by KNN MELprop (Politechnika Warszawska) into an integrated design
environment (**MELprop-IADE**) for two vehicles:

- **Project A — GTM-140 drone**: fixed-wing UAV with the Jetpol GTM-140 miniature
  **turbojet** (not a turbofan — no propeller). Subsonic, VLM/AVL + XFOIL.
- **Project B — ramP rocket**: two-stage supersonic rocket — solid booster +
  ramjet cruise stage. Empirical/DATCOM-style aero (no AVL supersonic), conical
  spike inlet, staging at booster burnout.

The repo also carries teaching material merged from the former `droniada` branch:
`Tutorials252/`, `Tutorials-2.3.1/`, `student_competition/` (Droniada Sztafeta
framework), and `.devcontainer/` (Codespaces).

---

## 2. Repository layout (MELprop additions)

```
core/                         # Foundation — EXTEND via inheritance, never rewrite
  component_base.py           #   BaseComponent, BaseAnalysis, FidelityLevel(L0-L3),
                              #   AnalysisResults, ComponentRegistry
  vehicle_factory.py          #   SUAVE vehicle factory (guarded SUAVE import)
  mission_builder.py          #   Solver-agnostic mission-segment builder
  solver_registry.py          #   External-solver registry (AVL, XFOIL, ...)
src/schemas/vehicle_schema.py # Pydantic v2 config models (schema v0.2.0)
vehicles/
  gtm140_drone/vehicle_config.yaml
  ramjet_rocket/vehicle_config.yaml         # schema-validated engineering config
  ramjet_rocket/fusion_extraction_v6.yaml   # RAW Fusion export (source of truth)
  ramjet_rocket/motor_database.yaml         # candidate solid motors
analyses/
  aerodynamics/avl_wrapper.py    # AVLAnalysis (Helmbold fallback) — Project A
  stability/barrowman_stability.py   # Barrowman + Rogers CP/static margin — DONE
  trajectory/booster_burnout.py      # 3-DOF boost sim (scipy) — DONE
  propulsion/inlet_performance.py    # conical-spike inlet vs MIL-E-5007 — DONE
  aero/xfoil_runner.py               # STUB (fin airfoil polar)
  aero/avl_builder.py                # STUB (AVL deck generation)
  cfd/su2_config_template.py         # STUB (SU2 Mach sweep)
workflows/                     # (empty) OpenMDAO problems / MDO / staging events
tests/unit/                    # pytest: test_schemas, test_aero_avl, test_propulsion_inlet
docs/ramP/                      # analysis_status.md, preliminary_analysis_report.md
.claude/agents/                # 6 subagent definitions
```

---

## 3. Environment setup (IMPORTANT — deps are NOT vendored)

Fresh containers have **none** of the Python deps installed. Install before doing
anything:

```bash
pip install pydantic pytest pyyaml numpy scipy matplotlib
```

- **SUAVE** (from `trunk/`) is **optional** for unit tests — imports in `core/`
  are guarded (`try/except ImportError`), so schema/analysis modules run without it.
  `VehicleFactory.build()` raises a clear error only if SUAVE is actually needed.
- **AVL / XFOIL / SU2 / gmsh / pyCycle / OpenMDAO** binaries are **not** installed.
  All analyses either provide analytical fallbacks (AVL→Helmbold) or are pure-Python
  low-order models. The external-solver wrappers are stubs (see §6).
- Python 3.11 in the current image; the `.devcontainer/` pins 3.9 for SUAVE.

---

## 4. How to run things

```bash
# Tests (run after EVERY change — project rule #8)
python -m pytest tests/ -v --tb=short          # 25 tests, all passing

# Analyses (each writes a JSON + PNG next to itself)
python3 analyses/stability/barrowman_stability.py
python3 analyses/trajectory/booster_burnout.py
python3 analyses/propulsion/inlet_performance.py
```

Run scripts from the repo root (a root `conftest.py` puts the repo on `sys.path`;
scripts also self-bootstrap `sys.path` for direct execution).

Load a vehicle config:

```python
from src.schemas.vehicle_schema import BaseVehicleConfig
cfg = BaseVehicleConfig.from_yaml("vehicles/ramjet_rocket/vehicle_config.yaml")
# dispatches on vehicle_type -> UAVConfig | RocketConfig
```

---

## 5. Architecture & extension rules (must follow)

1. **Never rewrite `core/` or `trunk/SUAVE/`.** Extend `core/` by subclassing
   `BaseAnalysis` / `BaseComponent`; return results as `AnalysisResults`.
2. **SI units always**, encoded in field names (`thrust_N`, `span_m`, `isp_s`).
3. **Type hints** on all public functions; **Google-style docstrings** (English)
   with a theory reference for physics code.
4. Every new file starts with: `# MELprop-IADE | <module.path> | v0.1.0`.
5. **Method applicability:** AVL only for Mach < 0.6 and |α| < 15°; above that use
   empirical correlations. Never AVL for the supersonic rocket.
6. `# TBD` / `# SZACOWANY` in YAML = placeholder needing real data before analyses
   are trustworthy.
7. Fidelity ladder: L0 analytical/handbook, L1 linear (VLM/XFOIL/DATCOM),
   L2 Euler CFD / 1-D cycle, L3 RANS/FEM.

The config schema is **Pydantic v2**, `extra="forbid"` (unknown keys rejected).
Adding config fields means editing `src/schemas/vehicle_schema.py` **and** updating
`tests/unit/test_schemas.py`. Current models: `UAVConfig`, `RocketConfig`,
`WingConfig`, `TurbojetConfig`, `BoosterStage`(→`BoosterGeometry`,
`SolidRocketPropulsion`), `RamjetConfig`, `BodyConfig`, `FinConfig`,
`MassProperties`; standalone `SolidRocketConfig` retains a thrust-consistency guard.

---

## 6. Work completed this session (Project B — ramP)

Geometry comes from **Fusion 360 Assembly v6** (corrected cm→m, Y-axis
longitudinal). Key numbers: total length 4.377 m, body Ø 0.250 m, conical nose
0.293 m / base 0.150 m, 4 rectangular fins span 0.6685 m chord 0.1768 m, total mass
355.02 kg, CG 1.6084 m from nose. Raw export preserved in `fusion_extraction_v6.yaml`.

| Analysis | Module | Result | Verdict |
|---|---|---|---|
| Static stability | `analyses/stability/barrowman_stability.py` | CP 4.128 m, SM 10.08 cal, fineness 17.5 | ✅ PASS |
| Boost trajectory | `analyses/trajectory/booster_burnout.py` | M 1.03, q_max 75 kPa, range 771 m | ⚠️ see §7 |
| Ramjet inlet | `analyses/propulsion/inlet_performance.py` | η 0.661 vs MIL-E-5007 0.870 | ❌ FAIL (expected) |

Outputs (JSON + 150-DPI PNG) live beside each script; consolidated write-up in
`docs/ramP/preliminary_analysis_report.md`.

**Project A** foundation (earlier): `AVLAnalysis` wrapper with Helmbold fallback,
GTM-140 config, schema, 6 subagents, initial tests.

History: merged into `develop` via **PR #8** (former PR #9 content consolidated in;
#9 closed).

**Night-3 (2026-07-09)** — branch `claude-dev-night3`, phases 2–7 completed (P1 combustor
already DONE via PR #13), test suite **154/154 green**. Commits (one per phase):
- P2 (cruise wiring Th1 + net margin): 3584f0fa
- P3 (inlet actuation schedule 4-cone): 8e65b39d
- P4 (motor database HTPB candidates): 546a55e7
- P5 (fin polar Ackeret fallback): e7629e76
- P6 (SU2 config generator Ma x AoA): 9a3c00b8
- P7 (launch-angle sweep): 8a05c714

Highlights: Grzywka cycle at Ma 2.5 delivers Th1 = 12107.9 N (vs Th2 = 12009.0 N,
hierarchy holds); V3 = 1474.3 m/s exceeds Teltik CFD ~1047 m/s by +40.8% (HUMAN_REVIEW;
root-caused by Night-4 P1-B as the fully-expanded-nozzle assumption, see below).
Inlet actuation achieves MIL-E-5007 on [2.4, 3.5] Mach band; unattainable below ~2.4
with current geometry. Launch angle 5° recommended (burnout alt 45.3 m, q_max 131.75 kPa).
Tree clean, no budget cuts. Ran concurrently with Night-4 (below); branches merged.

### Night-4 (2026-07-09)

**Branch:** `claude/fervent-albattani-f18spc`, **PR #15** (draft). Pytest: 118 baseline → 157 passed, 0 failed.

**P1-A (aero, sonnet):** `analyses/aero/barrowman_extended.py` — Galejs body-lift + reused P-G/Ackeret fin. YAML Ma 2.5: SM_extended +4.594 cal (gap to Teltik CFD halved but +7.344 cal remain); STABILITY_REVIEW_NEEDED flag stands. 7 tests.

**P1-B (propulsion, opus):** `analyses/propulsion/validation/v3_discrepancy_analysis.md` — V3 root cause: fully-expanded nozzle assumption (A3/A21=2.44, Ma3=2.32) vs cylindrical CAD stub (ratio 1.0, ~809 m/s). T04 and gamma ruled out. HR-3 Laval nozzle decision pending. 0 new tests (analysis-only).

**P1-C (mission, sonnet):** `analyses/mission/operational_envelope.py` — 5Ma×6alt grid, all 30 cells SUSTAINED with CD0=0.35 SZACOWANY. Net thrust 5.3–28.1 kN (Ma1.5/10km–Ma3.0/SL). WP-21. 14 tests.

**P1-D (haiku):** 6 agent definitions + memory stubs refreshed. BB5 complete.

**P2-A (mission, sonnet):** `analyses/suave/ramp_suave_baseline.py` — 0D fallback (SUAVE stub). Range 47,631.5 m (boost 167.5 + cruise 47,464 with SZACOWANY 60 s placeholder). WP-22. 11 tests.

**P2-B (aero, sonnet):** `analyses/aero/fin_polar_comparison.py` — Ackeret vs Diederich surrogate. Ma2.5/α=5°: CL_ackeret 0.1523 vs CL_surrogate 0.3616 (ratio 2.37 RATIO_HIGH); 24/30 cells RATIO_HIGH. 7 tests. WP-23.

---

## 7. Known issues / caveats (READ before trusting numbers)

1. **Stage-1 propulsion is estimated (`SZACOWANY`), and internally inconsistent.**
   75 kg propellant / 6 s at Isp 207–230 s ⇒ ~25.4 kN *mean* thrust, but the YAML
   lists `thrust_peak_N: 12000` (a peak below the mean is impossible). The trajectory
   uses the impulse-consistent 25.4 kN and flags this. **Needs a real motor datasheet**
   (the R-13 in Fusion is a geometry mockup only).
2. **RESOLVED — 0° horizontal launch is non-viable as modeled** — with gravity, no lift,
   and h₀=100 m the rocket hits the ground at t≈4.53 s (before 6 s burnout). A
   launch-angle sensitivity sweep (`analyses/trajectory/booster_burnout.py::run_launch_angle_sweep`,
   angles 5–30°) confirms every swept angle avoids premature ground impact; the module
   reports `recommended_launch_angle_deg = 5.0` (the smallest swept viable angle,
   burnout Mach ≈1.37, burnout altitude ≈45 m) in `burnout_state.json`. Full per-angle
   results (burnout Mach/altitude/range, max q, ground-impact flag) are in
   `analyses/trajectory/launch_angle_sweep.csv` / `.png`. The module's own nominal run
   still defaults to the near-vertical 83° rail-launch angle documented above.
3. **Inlet actuation schedule** (Night-3, `analyses/propulsion/inlet_actuation.py`):
   4-cone variable geometry now achieves MIL-E-5007 (η ≥ 0.870) **contiguously on
   Mach [2.4, 3.5]** only. Below ~Ma 2.4, current geometry cannot meet standard even
   with full deflection. Fixed single-cone design obsolete; use actuation schedule
   for cruise band (Ma 2.4–3.5) and accept penalty below Ma 2.4.
4. **Nozzle** in Fusion is cylindrical (area ratio 1.0) — needs a Laval redesign for
   the cruise stage.
5. **Config reconciliation:** the schema-validated `vehicle_config.yaml` (with
   estimates) was chosen over an alternative authoritative export with `null`
   propulsion (user decision "overwrite with mine"). The raw export is retained in
   `fusion_extraction_v6.yaml`. If future work needs the null-propulsion authoritative
   config as the loaded file, restructure deliberately.
6. **Moments of inertia** Ixx/Iyy/Izz — not available via the Fusion API; pull from GUI.
7. **Barrowman caveat:** the fin set is huge (span 2.67× body Ø), so CP is far aft and
   the margin is very large / possibly over-stable; transonic band is linearly bridged
   (not CFD) — corroborate near Mach 1 with SU2 / wind tunnel before sign-off.
8. **V3 nozzle root cause (Night-4):** exit velocity 1474 m/s vs Teltik CFD 1047 m/s 
   (+40.8%) traced to fully-expanded-nozzle assumption (A3/A21=2.44, Ma3=2.32) vs actual 
   cylindrical CAD stub (ratio 1.0, near-sonic exit ~809 m/s). T04 and gamma ruled out; 
   HR-3 Laval nozzle decision pending (`analyses/propulsion/validation/v3_discrepancy_analysis.md`).
9. **Extended Barrowman SM gap:** at YAML geometry Ma 2.5, SM_extended +4.594 cal 
   vs Teltik CFD −2.75 cal — gap halved from original basic analysis but still 
   +7.344 cal; geometry audit required (Night-4 P1-A, `analyses/aero/results/SM_sensitivity_*.csv`).
10. **Operational envelope unconstrained:** all 30 grid cells (Ma 1.5–3.5 × 0–10 km) 
    marked SUSTAINED with CD0=0.35 SZACOWANY drag; real wave+friction polar needed 
    before envelope is trustworthy (Night-4 P1-C).

---

## 8. Subagents (`.claude/agents/`)

Delegate domain work to the matching subagent (they carry scope + rules):

| Agent | Model | Scope |
|---|---|---|
| aero-analyst | claude-sonnet-4-5 | `analyses/aerodynamics/`, `analyses/aero/`, `tests/test_aero_*` |
| propulsion-designer | claude-opus-4-5 | `analyses/propulsion/`, `tests/test_propulsion_*` |
| vehicle-builder | claude-sonnet-4-5 | `src/schemas/`, `vehicles/**`, `tests/test_vehicles_*` |
| mission-planner | claude-sonnet-4-5 | `workflows/`, `analyses/trajectory/`, `tests/test_missions_*` |
| code-reviewer | claude-haiku-4-5 | read-only all, write only `tests/` |
| docs-writer | claude-haiku-4-5 | `notebooks/`, `*.md` |

When spawning them in parallel on a shared working tree, have them **write files
only and NOT run git**; the orchestrator commits (one commit per task) to avoid races.

---

## 9. Git & workflow conventions

- Develop on branch **`claude/melprop-iade-infrastructure-rcqzfg`**; base/default is
  **`develop`**. `droniada` was consolidated into `develop` via PR #8 (merged) — don't
  reuse it.
- If your PR is already merged, start fresh: `git fetch origin develop &&
  git checkout -B claude/melprop-iade-infrastructure-rcqzfg origin/develop`, then add
  new work on top. Never stack new commits on already-merged history without rebasing.
- `git push -u origin <branch>`; open a **draft** PR if none is open for the branch.
- Commit messages: conventional prefixes (`feat(ramP):`, `fix:`, `docs:`), imperative,
  explain the *why*. Run `pytest` before committing. Never commit secrets or `.env`.

---

## 10. Suggested next steps (priority order)

1. Obtain the **stage-1 motor datasheet** → replace `SZACOWANY` values, resolve the
   thrust inconsistency, re-run the trajectory.
2. Re-run trajectory with a **positive launch angle / lift**; extend to the full
   staged mission (booster burnout → ramjet takeover) via `core/mission_builder.py`.
3. **Redesign the inlet** (multi-shock/isentropic) to meet MIL-E-5007; then model the
   full ramjet cycle (combustor + Laval nozzle), e.g. via pyCycle.
4. Implement the stubs: **XFOIL** fin polar (M 2.5 double-wedge), **AVL** subsonic
   deck, **SU2** Mach sweep [0.8–3.0] to corroborate the transonic CP and drag.
5. Fill GTM-140 (Project A) real data from the Jetpol datasheet; wire AVL subprocess.
6. Extract **moments of inertia** from Fusion GUI into the config.

Keep `docs/ramP/analysis_status.md` updated as items move STUB/TBD → DONE.

### Night-5 recommended actions

1. **Team:** HR-1 / HR-2 fin-span CAD verification. Now equipped with body-lift-corrected 
   sensitivity data (`analyses/aero/results/SM_sensitivity_fin_span.csv`) showing how SM 
   varies with span near the YAML geometry.

2. **Team:** HR-3 **Laval nozzle decision**. Decide on area_ratio design intent (e.g., 4.0) 
   vs cylindrical CAD stub (ratio 1.0). Then agents re-run `combustor_nozzle_cycle` with 
   finite area ratio and re-validate V3 vs Teltik data.

3. **Agents:** Real **drag polar** (wave + friction buildup, Ma 1.5–3.5 sweep) to replace 
   CD0=0.35 SZACOWANY. Then re-run operational envelope (`analyses/mission/operational_envelope.py`) 
   and SUAVE baseline (`analyses/suave/ramp_suave_baseline.py`) to populate sustainable cruise cells.

4. **Agents:** **Stage-2 fuel mass budget** — replace the 60 s SZACOWANY cruise placeholder 
   with real mass and range trade. Wire into SUAVE baseline to close the mission loop.
