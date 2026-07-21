# MELprop ramP — Analysis Status

Two-stage supersonic rocket (solid booster + ramjet cruise). Geometry from
Fusion Assembly v6 (`vehicles/ramjet_rocket/fusion_extraction_v6.yaml`).

Status legend: **DONE** (implemented + run) · **STUB** (scaffold + TODO) ·
**TBD** (not started / needs external data).

| # | Analysis | Module | Status | Owner | Date |
|---|----------|--------|--------|-------|------|
| 1 | Vehicle config + schema (v0.2.0) | `src/schemas/vehicle_schema.py`, `vehicles/ramjet_rocket/vehicle_config.yaml` | DONE | vehicle-builder | 2026-07-08 |
| 2 | Static stability (Barrowman + Rogers) | `analyses/stability/barrowman_stability.py` | DONE | aero-analyst | 2026-07-08 |
| 3 | Boost-phase trajectory (3-DOF) | `analyses/trajectory/booster_burnout.py` | DONE | mission-planner | 2026-07-08 |
| 4 | Ramjet inlet (conical spike, M2.5) | `analyses/propulsion/inlet_performance.py` | DONE | propulsion-designer | 2026-07-08 |
| 5 | Fin airfoil polar (XFOIL, M2.5 double-wedge) | `analyses/aero/xfoil_runner.py` | DONE | aero-analyst | 2026-07-09 |
| 6 | AVL stability deck (subsonic) | `analyses/aero/avl_builder.py` | STUB | aero-analyst | 2026-07-08 |
| 7 | SU2 external aero (Mach sweep) | `analyses/cfd/su2_config_template.py` | IN_PROGRESS | aero-analyst | 2026-07-09 |
| 8 | Solid motor selection | `vehicles/ramjet_rocket/motor_database.yaml` | IN_PROGRESS | propulsion-designer | 2026-07-09 |
| 9 | Moments of inertia (Fusion) | — | TBD | vehicle-builder | — |
| 10 | Multi-cone inlet redesign (4-cone, M2.5) | `analyses/propulsion/inlet_performance.py` | DONE | propulsion-designer | 2026-07-08 |
| 11 | Ramjet cycle L2 (combustor+nozzle) | `analyses/propulsion/ramjet_cycle.py` | DONE | propulsion-designer | 2026-07-08 |
| 12 | Staged mission cruise design point | `workflows/ramp_staged_mission.py` | DONE | mission-planner | 2026-07-08 |
| 13 | Static margin review (Barrowman) | `docs/ramP/static_margin_review.md` | DONE | aero-analyst | 2026-07-08 |
| 14 | Stability margin report (Barrowman vs Teltik 2024 CFD) | `docs/ramP/stability_margin_report.md` | DONE | aero-analyst | 2026-07-09 |
| 15 | Inlet completeness audit (Night-2 Phase 1b) | `tests/unit/test_propulsion_inlet.py` | DONE | code-reviewer | 2026-07-09 |
| 16 | Combustor+nozzle Grzywka model (CC→NT→NE, Thi/Th1/Th2) | `analyses/propulsion/combustor_nozzle_cycle.py` | DONE | propulsion-designer | 2026-07-09 |
| 17 | Cruise wiring to Grzywka model (Night-2 Phase 3b) | `workflows/ramp_staged_mission.py` | DONE | mission-planner | 2026-07-09 |
| 18 | Movable-inlet actuation params (Night-2 Phase 4b) | `analyses/propulsion/inlet_performance.py` | DONE | propulsion-designer | 2026-07-09 |
| 20 | Extended Barrowman sensitivity (Galejs body-lift model, fin-span sweep) | `analyses/aero/barrowman_extended.py` | DONE | aero-analyst | 2026-07-09 |
| 21 | Operational envelope (thrust-required envelope, 30 Mach×altitude cells) | `analyses/mission/operational_envelope.py` | DONE | mission-planner | 2026-07-09 |
| 22 | SUAVE baseline mission 0D fallback (reference trajectory for validation) | `analyses/suave/ramp_suave_baseline.py` | DONE | propulsion-designer | 2026-07-09 |
| 23 | Fin polar comparison (Ackeret vs Diederich, supersonic airfoil) | `analyses/aero/fin_polar_comparison.py` | DONE | aero-analyst | 2026-07-09 |
| 24 | V3 root-cause analysis (nozzle area-ratio vs T04 vs gamma effects) | `analyses/propulsion/validation/v3_discrepancy_analysis.md` | ANALYZED | propulsion-designer (P1-B) | 2026-07-09 |
| 25 | Stability reconciliation (geometry audit + fin-span sensitivity sweep, Night-3 Phase 5) | `docs/ramP/stability_reconciliation.md` | DONE | aero-analyst | 2026-07-09 |
| 26 | Launch-angle sweep (5–30°, recommended 5° via booster_burnout.py) | `analyses/trajectory/booster_burnout.py::run_launch_angle_sweep` | DONE | mission-planner | 2026-07-09 |
| 27 | Inlet actuation schedule (4-cone, Ma 2.4–3.5 MIL-E-5007 band, Δθ per cone) | `analyses/propulsion/inlet_actuation.py` | DONE | propulsion-designer | 2026-07-09 |

## Night-2 checkpoint (2026-07-09, budget guard at 80%)

**Update (2026-07-09 Night-3/Night-4):** Phase 2b/3b/4b were completed in Night-3 and merged via PR #13 (combustor_nozzle_cycle.py, workflows/ramp_staged_mission.py, inlet_performance.py movable-inlet params). Checkpoint retained below for historical reference.

Night-2 run was halted **cleanly** mid **Phase 2b** by the budget guard firing
at 80% of the usage window. The Phase 2b subagent (propulsion-designer,
opus-tier) was stopped while still in its **read-only exploration** step —
**before any file was written**. Verified clean stop: `git status` tree
clean, no partial/dangling files, full suite **80/80 tests green**.

**Resume point:** next session should resume **Night-2 Phase 2b** from its
full task spec below (do not re-diagnose, do not restart from Phase 0):

- Create `analyses/propulsion/combustor_nozzle_cycle.py` <!-- TODO: dead link, target missing as of 2026-07-09 --> +
  `tests/unit/test_propulsion_combustor_nozzle.py` <!-- TODO: dead link, target missing as of 2026-07-09 -->.
- Model: Grzywka 2022, stations **1 → 2 → 21 → 3** (CC → NT → NE).
- Loss coefficients: `pi_CC = 0.8924` (1→2), `pi_nozzle = 0.97` (2→3).
- Nozzle throat area **D21 is dynamic** (a function of `V`, `H`), with
  `Ma_throat = 1` always enforced — never hard-code D21 as a constant.
- Report **three thrust models**: Thi, Th1, Th2 (Grzywka §6.2.2) — all three,
  always, never collapse to a single thrust number.
- Cross-check against a Brayton-cycle T2 estimate; flag if delta > 5%.
- Log V3 vs Teltik 2024 CFD (~1047 m/s at Ma 2.5 / 6000 m) delta.
- Check the nozzle area ratio against the YAML value (4.0).
- **Requires opus-tier** per the run plan — do not substitute sonnet for this
  phase.

## Night-3 checkpoint (2026-07-09)

Night-3 run completed **cleanly, full budget used** (not cut mid-phase). Phases 2–7
executed (P1 combustor already DONE via PR #13). Full test suite **154/154 green**.
Tree clean. Six commits, one per phase:

| Phase | Description | Commit | Result |
|-------|-------------|--------|--------|
| P2 | Combustor + nozzle Grzywka cycle | 546a55e7 | Th1=12107.9N, V3=1474.3 m/s; CFD delta +40.8% (HUMAN_REVIEW) |
| P3 | Cruise wiring (switch to Th1) | 8e65b39d | Thrust margin ±10121N (drag CD0=0.35) / ±9656N (Teltik CFD) |
| P4 | Inlet actuation 4-cone schedule | e7629e76 | MIL-E-5007 on [2.4, 3.5] Mach, Δθ = 3.5/8.3/15.2/24.3 deg per cone |
| P5 | Fin polar (Ackeret fallback) | 3584f0fa | CL=0.1523, CD with τ=0.1697 (Fusion t/c) at Ma2.5 α=5°; XFOIL pending binary |
| P6 | Motor database (3 HTPB candidates) | 9a3c00b8 | 20–30 kN mean, 5–8 s, Isp 205–230 s, all SZACOWANY |
| P7 | Launch-angle sweep (5–30°) | 8a05c714 | Recommended 5° (burnout alt 45.3 m, q_max 131.75 kPa); 0° non-viable |

**Work item status update:**
- WP 5 (XFOIL fin polar) → **DONE** (Ackeret fallback; full XFOIL delegation pending binary availability)
- WP 7 (SU2 Mach sweep) → **IN_PROGRESS** (generator module complete; runner pending SU2 binary)
- WP 8 (Motor selection) → **IN_PROGRESS** (3 candidates populated in motor_database.yaml; awaiting real R-13 datasheet)

**Next session (Night-4) recommended priorities:**
1. AVL builder stub → subsonic deck generation (WP 6 subsonic CLα/Cmα).
2. SU2 runner once binary available (WP 7; Mach [0.8–3.0] external aero).
3. Real motor datasheet ingestion and trajectory re-run (WP 8).
4. Moments of inertia extraction from Fusion GUI (WP 9).
5. Nozzle Laval design decision (cylindrical stub 1.0 ratio vs YAML 4.0 ratio).
6. Housekeeping: add `runs/` to `.gitignore` (team decision pending).

**⚠️ HUMAN_REVIEW flags for Night-4:**
- V3 exit velocity CFD delta +40.8% — exceeds known 20–30% MATLAB-vs-CFD scatter band.
- Fin-span sign-flip standing (see static_margin_review.md).

## Open data gaps
- **Motor datasheet** — stage-1 propulsion is still `SZACOWANY` (estimated).
  RESOLVED 2026-07-08: `thrust_peak_N`/`thrust_mean_N` are now independent,
  schema-validated fields (peak >= mean enforced, cross-checked against
  Isp*mdot*g0); the previous 12 kN "peak" was below the impulse-consistent
  ~25.4 kN mean, which is physically impossible. Still needs a real
  R-13-class datasheet to replace the SZACOWANY values.
- **Moments of inertia** Ixx/Iyy/Izz — Fusion 360 exposes the inertia tensor
  ONLY in the GUI Physical Properties panel, not via its scripting API. Manual
  extraction required: open Fusion Assembly v6, right-click main component →
  "Physical Properties", copy Ixx/Iyy/Izz values (units: kg·m²) from the panel
  into `mass_properties:` section of `vehicle_config.yaml`. Cannot be automated.
- **Ramjet cycle** (combustor/nozzle performance) — RESOLVED 2026-07-08 at L2 fidelity (station 0-2-4-9 cycle; single-method result, MATLAB baseline unavailable, CFD delta +20-30% open).
- **Nozzle geometry discrepancy** — vehicle_config.yaml nozzle_area_ratio 4.0 vs Fusion v6 cylindrical stub (expansion_ratio 1.0); thrust 12.31 kN (matched) vs 9.85 kN (cylindrical). Needs Laval nozzle design decision.
- **Fin span suspect** (static margin 10.08 cal, ~7-8x span reduction would hit 1.5-2 cal) — likely Fusion export artifact, needs team review (see static_margin_review.md).

## Night-4 checkpoint (2026-07-09)

**Test suite:** pytest 118 → 157 green (all DONE phases passing).

**Completed blocks:** P1-A (extended Barrowman, fin-span sensitivity) · P1-B (V3 root-cause: nozzle area-ratio PRIMARY, not T04) · P1-C (operational envelope, 30 Mach×altitude cells sustained) · P1-D (pending human review) · P2-A (SUAVE baseline 0D) · P2-B (fin polar Ackeret vs Diederich) · P2-C (pending human review) · P2-D (pending human review).

**No BLOCKED_BY_BUDGET items remain.** Rows 16/17/18 transitioned to DONE (PR #13 merged Night-3).

**Human-review items:** 9 items listed in docs/ramP/human_review_night4.md (HR-1 through HR-9), blocks: stability geometry (fin span, HR-1), CFD mesh revision confirmation (HR-2), nozzle design decision (HR-3, PRIMARY root cause), stage-1 motor datasheet (HR-4), moments of inertia extraction (HR-5); non-blocking but ACTIVE: max_rpm units convention (HR-6), T04 source confirmation (HR-7), gamma_products composition (HR-8), drag-polar for nominal cruise selection (HR-9).

**Artifact note:** PNG plots (barrowman_extended.png, envelope.png, v3_discrepancy.png, etc.) are gitignored repo-wide; regenerate by running analysis scripts directly (e.g., `python analyses/aero/barrowman_extended.py`).

## 2026-07-11 rerun checkpoint (post-research, cloud sandbox)

Full analysis suite rerun on the corrected geometry (body 0.200 m, fins 0.550 m
/ 29.98°, nozzle AR 1.317). Suite 211 → **240 green**. Draft PR #4. Per-stage
commits. SU2 + CEA `BLOCKED_BY_ENVIRONMENT`.

| # | Rerun analysis | Module | Status | Result |
|---|---|---|---|---|
| S1 | Stability (retire Barrowman gate) | `analyses/stability/datcom_class_sweep.py`, `ackeret_fin_check.py` | DONE (gate NOT satisfied) | DATCOM +5.13..+11.01 cal & Ackeret +9.71 cal, but conflict with Teltik CFD −2.75 cal; SU2 arbiter BLOCKED |
| S2 | Ramjet cycle / V3 (H&P, station γ) | `analyses/propulsion/cycle_v2/hp_stream_thrust_cycle.py` | DONE | V3=1200 m/s; +40.8%→+14.6% vs CFD; γ weak, geometry closed the gap; HR-7 RECALCULATED |
| S3a | Inlet (Taylor–Maccoll) | `analyses/propulsion/inlet_performance_v2.py` | DONE | 42° attached@M2.5 (0.639<MIL 0.870), DETACHES@M2.0 → min start Mach ≈2.1 |
| S3b | Nozzle expansion (coupled γ) | `analyses/propulsion/nozzle_expansion_check.py` | DONE | under-expanded p_e/p0≈3 across 4–10 km; matched AR≈2.48 |
| S4 | Cold-flow test plan + CO2 mismatch | `docs/cold_flow_test_plan.md`, `analyses/cold_flow/co2_surrogate_mismatch.py` | DONE | verifies shocks/recovery; NOT reacting mixing (~11× density & momentum-flux mismatch) |

**Open safety-critical item:** Ma2.5 static stability sign conflict — run SU2
locally to break the 2-analytical-vs-1-CFD tie. Do not gate CDR on the
analytical +margin. See docs/decision-log.md (Stage 1 orchestrator addendum) and
agents/memory.md (next human actions).
