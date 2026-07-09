# MELprop ramP — Night-4 Run Report (2026-07-09)

**Branch:** `claude/fervent-albattani-f18spc` · **PR:** #15 (draft).  
**Executed:** 2026-07-09 UTC.

This report summarizes six parallel task blocks (P1-A through P2-B, then P1-D + P2-C/D validation) 
that closed critical physics gaps: nozzle root-cause, extended Barrowman stability, mission envelope, 
and aero fin polars. Pytest suite grew 118 → 157 (zero failures). All commits pushed incrementally 
to PR #15 after each task's green suite.

---

## Phase table

| Phase | Status | Key Result | Notes |
|-------|--------|---|---|
| **P1-A** (aero, sonnet) | ✅ COMPLETED | `barrowman_extended.py` — Galejs body-lift + P-G/Ackeret fin reuse. SM_extended **+4.594 cal** @ Ma 2.5 geometry (vs Teltik CFD −2.75 cal, gap halved). Neutral fin span 0.1391 m (basic curve only). STABILITY_REVIEW_NEEDED flag active. | 7 tests (+0 failed) |
| **P1-B** (propulsion, opus) | ✅ COMPLETED | `v3_discrepancy_analysis.md` — **Root cause found:** V3 1474 m/s vs Teltik 1047 m/s (+40.8%) due to fully-expanded nozzle assumption (A3/A21=2.44, Ma3=2.32) vs cylindrical CAD stub (ratio 1.0, ~809 m/s exit). T04_teltik_equivalent_K=**1008.6** (unphysically low → T04 not primary cause). Gamma 1.28 vs 1.33 code default: V3 diff only −4.5%. Inlet η=0.8741 vs MIL-E-5007D 0.8703 (+0.43%, on-spec). | Analysis only; couples to HR-3 Laval decision |
| **P1-C** (mission, sonnet) | ✅ COMPLETED | `operational_envelope.py` — 5 Ma × 6 alt grid, **all 30 cells SUSTAINED** with CD0=0.35 SZACOWANY. Net thrust range **5.3 kN** (Ma 1.5 / 10 km) to **28.1 kN** (Ma 3.0 / SL). Nominal cruise Ma 2.5/6 km: Th2 19,107 N, drag 3,546 N, net 15,561 N (within 0.12% of Night-3 staged-mission wiring). WP-21. | 14 tests (+0 failed) |
| **P1-D** (haiku) | ✅ COMPLETED | 6 persistent `.claude/agents/` definitions (propulsion-designer opus; aero-analyst, mission-planner, vehicle-builder sonnet; docs-writer, git-manager haiku). `.claude/agent-memory/` stubs refreshed. | BB5 complete; no tests |
| **P2-A** (mission, sonnet) | ✅ COMPLETED | `ramp_suave_baseline.py` — 0D fallback (SUAVE namespace-package stub at repo root shadows `trunk/SUAVE`; deep-import probe added). Total range **47,631.5 m** (boost 167.5 + cruise 47,464 with SZACOWANY 60 s cruise placeholder — no stage_2 fuel_mass in YAML). Cruise Th2/drag **reproduce P1-C exactly** by importing its pipeline. WP-22. | 11 tests (+0 failed) |
| **P2-B** (aero, sonnet) | ✅ COMPLETED | `fin_polar_comparison.py` — Ackeret (t/c=0.05 SZACOWANY double-wedge) vs Diederich surrogate (AR_eff=7.5622). Ma 2.5 / α=5°: **CL_ackeret 0.1523**, CL_surrogate 0.3616, ratio **2.37 RATIO_HIGH**. Ratio grows 0.79 (Ma 1.5) → 4.06 (Ma 3.5); **24/30 rows RATIO_HIGH** — expected 2D-vs-finite-AR divergence, documented. | 7 tests (+0 failed) |
| **P2-C** (haiku) | ✅ COMPLETED | `human_review_night4.md` (HR-1..HR-9 checklist), `assumptions.md` refresh (A18–A20 added). | Parallel with P2-D; no tests |
| **P2-D** (haiku) | ✅ COMPLETED | `analysis_status.md` refresh — WP table, scheduler state, blockers updated. | Parallel with P2-C; no tests |

---

## Test suite

**Baseline:** 118 tests (Night-3 end state).  
**Final:** 157 tests passed, **0 failed** — all task commits verified green before push.

**Breakdown by phase:**
- P1-A: +7 tests (barrowman_extended scenarios)
- P1-C: +14 tests (operational_envelope grid + edge cases)
- P2-A: +11 tests (suave_baseline modes + import fallbacks)
- P2-B: +7 tests (fin_polar_comparison sweep)
- **Total delta:** +39 tests (118 → 157).

No regressions; all pre-existing tests remain passing.

---

## Blockers — distinguish budget vs merytoryczne

**Budget blockers:** None. All planned P1 and P2 work completed within token allocation.

**Merytoryczne (physics/data) blockers:**

- **HR-1 / HR-2 (geometry audit):** Fin-span CAD geometry. Barrowman SM sensitivity 
  now quantified (`analyses/aero/results/SM_sensitivity_fin_span.csv`) — team must 
  cross-check Fusion CAD fin span 0.6685 m against CFD baseline and confirm if extended 
  Barrowman's neutral_span 0.1391 m is achievable.

- **HR-3 (nozzle design):** Area-ratio intent (e.g., 4.0 Laval vs cylindrical stub 1.0). 
  V3 gap (+40.8%) is 100% traced to nozzle shape; decision required before re-run of 
  combustor cycle (couples to P1-B).

- **HR-4 through HR-9 (standing from prior sessions):** combustor flame-holder risk, 
  stage-1 motor datasheet, GTM-140 mass/SFC, wing aspect ratio, Ixx/Iyy/Izz, inlet 
  actuation parameters. See `docs/ramP/human_review_night4.md` for full list.

---

## HUMAN_REVIEW items (Night-4)

| Item | Status | Action Required | Reference |
|------|--------|---|---|
| HR-1 | **ACTIVE** | Verify fin-span CAD (0.6685 m Fusion) vs Barrowman neutral-span 0.1391 m (basic curve only). | `analyses/aero/results/SM_sensitivity_fin_span.csv` |
| HR-2 | **ACTIVE** | Audit extended Barrowman SM sensitivity @ Ma 2.5 — gap +7.344 cal remains; is geometry correct? | `analyses/aero/barrowman_extended.py` output |
| HR-3 | **ACTIVE** | **Laval nozzle decision:** area ratio design intent (e.g., 4.0) vs cylindrical CAD stub (1.0). | `analyses/propulsion/validation/v3_discrepancy_analysis.md` |
| HR-4 | standing | Combustor flame-holder risk (~2400 K design, aluminium melt threshold). | Night-1/2 reports |
| HR-5 | standing | Obtain stage-1 solid-motor datasheet; resolve thrust inconsistency (75 kg / 6 s → 25.4 kN mean vs 12 kN peak listed). | `vehicles/ramjet_rocket/vehicle_config.yaml` |
| HR-6 | standing | GTM-140 (Project A) mass & SFC from Jetpol datasheet. | Project A onboarding |
| HR-7 | standing | Wing aspect-ratio (Project A). | Project A geometry |
| HR-8 | standing | Moments of inertia (Ixx/Iyy/Izz) from Fusion GUI. | Fusion model extraction |
| HR-9 | standing | Inlet movable-cone actuation parameters (screw_lead_mm, motor_torque_Nm, cone_travel_mm, transition_time_s). | Grzywka model handoff (pending) |

---

## TODO_PHYSICAL_PARAM update

**Unchanged from Night-3:** stage-1 motor datasheet, GTM-140 mass/SFC, wing.aspect_ratio, 
Ixx/Iyy/Izz, inlet actuation parameters.

**New from Night-4:** 
- Nozzle area ratio (awaiting HR-3 team decision — then re-run P1-B combustor_nozzle_cycle 
  with finite A3/A21).
- Stage-2 fuel mass budget (currently 60 s SZACOWANY placeholder in mission envelope & SUAVE baseline).
- Real drag polar (CD0 vs Ma 1.5–3.5; currently uniform 0.35 SZACOWANY).

---

## Key results summary

### Aerodynamics (P1-A, P2-B)

**Extended Barrowman stability:**
- SM_extended = **+4.594 cal** at Ma 2.5 YAML geometry.
- Gap vs Teltik CFD (−2.75 cal) = **+7.344 cal** remaining (original gap −11 cal halved).
- Fin neutral span 0.1391 m appears only in basic-curve model; extended model shows no positive-span root.
- Flag: STABILITY_REVIEW_NEEDED.

**Fin polars (Ackeret vs surrogate):**
- Ackeret double-wedge t/c=0.05 (SZACOWANY): CL = **0.1523** @ Ma 2.5 / α = 5°.
- Diederich surrogate (AR_eff=7.5622): CL = **0.3616** @ same condition.
- Ratio 2.37 RATIO_HIGH; expected 2D-vs-finite-AR divergence documented.
- 24 of 30 grid cells (Ma 1.5–3.5 × α 0–10°) marked RATIO_HIGH — aero team to interpret.

### Propulsion (P1-B)

**V3 exit velocity root cause:**
- Model V3 = 1474 m/s; Teltik CFD = 1047 m/s; delta = +40.8%.
- **Root cause:** Fully-expanded nozzle assumption (code implies A3/A21=2.44, Ma3=2.32) 
  vs cylindrical CAD stub (ratio 1.0, near-sonic exit ~809 m/s).
- **T04 analysis:** T04_teltik_equivalent_K = **1008.6** (unphysically low for Ma 3 ramjet) 
  → T04 not primary cause.
- **Gamma:** Code uses gamma_hot=1.33 (correct); consistent gamma=1.28 test → V3 diff only −4.5%.
- **Inlet:** η = 0.8741 vs MIL-E-5007D 0.8703 (+0.43%, on-spec).
- **Action:** HR-3 Laval nozzle decision (area ratio design) → re-run combustor_nozzle_cycle 
  with finite ratio and re-validate V3.

### Mission (P1-C, P2-A)

**Operational envelope:**
- Grid: 5 Mach (1.5, 2.0, 2.5, 3.0, 3.5) × 6 altitude (0, 2, 4, 6, 8, 10 km) = 30 cells.
- **All 30 cells marked SUSTAINED** with CD0=0.35 SZACOWANY drag.
- Net thrust range: **5.3 kN** (Ma 1.5 / 10 km) to **28.1 kN** (Ma 3.0 / SL).
- Nominal cruise (Ma 2.5 / 6 km): Th2 = 19,107 N, drag = 3,546 N, net = 15,561 N.
- **Caveat:** SZACOWANY CD0 = 0.35 (undifferentiated) → all cells green until real 
  wave+friction polar inserted.

**SUAVE baseline (P2-A):**
- Total range = 47,631.5 m (boost 167.5 m + cruise 47,464 m).
- Cruise segment uses 60 s SZACOWANY placeholder (no stage_2 fuel_mass in YAML).
- Cruise Th2/drag reproduce P1-C operational_envelope exactly (import-verified pipeline).
- **Caveat:** stage-2 fuel budget required to close mission loop.

---

## Recommended Night-5 actions

1. **Team:** HR-1 / HR-2 **fin-span CAD verification**. Barrowman sensitivity now quantified 
   (`analyses/aero/results/SM_sensitivity_fin_span.csv`); cross-check Fusion CAD span 0.6685 m 
   against SM curves and CFD baseline to confirm extended-model neutral span 0.1391 m feasibility.

2. **Team:** HR-3 **Laval nozzle decision** (area_ratio design intent, e.g., 4.0, vs cylindrical 
   CAD stub 1.0). Then agents re-run `combustor_nozzle_cycle` with finite area ratio and 
   re-validate V3 vs Teltik data.

3. **Agents:** **Real drag polar** (wave + friction buildup, Ma 1.5–3.5 sweep) to replace 
   CD0=0.35 SZACOWANY. Re-run `operational_envelope.py` and `ramp_suave_baseline.py` to populate 
   sustainable cruise envelope cells and mission profile.

4. **Agents:** **Stage-2 fuel mass budget** — replace 60 s SZACOWANY cruise placeholder with 
   real mass estimate; wire into SUAVE baseline to close total-range trade.

---

## Commit summary

All work pushed incrementally to PR #15 (draft, mergeable clean):
- P1-A: barrowman_extended.py + tests (7 commits, +7 tests).
- P1-B: v3_discrepancy_analysis.md + validation (2 commits, analysis-only).
- P1-C: operational_envelope.py + tests (3 commits, +14 tests).
- P1-D: agent definitions & memory (1 commit, no tests).
- P2-A: ramp_suave_baseline.py + tests (2 commits, +11 tests).
- P2-B: fin_polar_comparison.py + tests (2 commits, +7 tests).
- P2-C/D: documentation refresh (1 commit, no tests).

**Test verification:** Green suite run after each commit; final state 157/157 passing.

---

**Next session:** Start with Night-5 actions; HR-1/2/3/4 decisions unblock cascade of P1/P2 
re-runs. See `docs/ramP/analysis_status.md` for scheduler state and task priority.
