# MELprop ramP — Night-2 Run Report (2026-07-09/10)

**Branch:** `claude/melprop-iade-night-run-by9c2l` · **PR:** #12 (open, draft,
mergeable clean).

This is a **short-form report**: the Night-2 run was interrupted mid-phase by
the budget guard firing at 80% of the usage window. See the checkpoint in
`docs/ramP/analysis_status.md` ("Night-2 checkpoint") for the full resume spec.

## Phase table

| Phase | Status | Summary |
|-------|--------|---------|
| 0b | COMPLETED | `stability_margin_report.md` produced: Barrowman CP 4.044 m / 3.855 m (Mach-matched) vs Teltik CFD 1.85 m / 0.92 m; deltas 8.8 / 11.7 cal. CFD-implied SM +0.97 cal @ Ma1.5, **−2.75 cal @ Ma2.5** — sign flip at cruise condition. Verdict upheld: "prawdopodobny artefakt geometrii — wymaga przeglądu zespołu". Two-methods stability gate **FAILS**. |
| 1b | COMPLETED | Inlet completeness audit — PASSED all 4 checks: `DEFAULT_N_CONES_M25 = 4` present at `__init__` line 792 and `setup` line 806; eta 0.8741 ≥ 0.8703 margin (+0.0037); `_2CONE`/`_3CONE` deliberately absent, zero dangling references; JSON output contains PASS verdict. |
| 2b | **BLOCKED_BY_BUDGET** | No files written; clean stop during read-only exploration. Requires opus-tier. |
| 3b | BLOCKED_BY_BUDGET | Depends on 2b (cruise wiring to Grzywka model). |
| 4b | BLOCKED_BY_BUDGET | Movable-inlet actuation parameters. |
| 5b | COMPLETED | PR #12 confirmed open/draft/mergeable-clean; Night-2 commits pushed to the same PR (no new PR opened). |
| 6b / 7b | COMPLETED | This report + tracker/assumptions/decision-log/memory updates. |

## Test suite

**80 passed, 0 failed** — unchanged from the Night-1 end state. Night-2 added
documentation only; no production code was touched, so the count did not move.

## Blockers — distinguish budget vs merytoryczne

- **blocked_by_budget** (resource constraint, resume next session as-is, no
  re-diagnosis needed): Phase 2b (combustor+nozzle Grzywka model), Phase 3b
  (cruise wiring, depends on 2b), Phase 4b (movable-inlet actuation params).
- **merytoryczne (physics/data) blockers:** none *new* this night. Standing
  from Night-1: combustor flame-holder risk (~2400 K vs aluminium melting
  point), suspect fin span (static margin sign flip reinforces urgency, see
  Phase 0b), stage-1 motor datasheet still SZACOWANY.

## TODO_PHYSICAL_PARAM

Unchanged from Night-1: stage-1 motor datasheet, GTM-140 mass/sfc,
`wing.aspect_ratio`, Ixx/Iyy/Izz.

**New this night:**
- Grzywka `T_fuel(Ma)` linear-law coefficients.
- Inlet actuator parameters (`screw_lead_mm`, `motor_torque_Nm`,
  `cone_travel_mm`, `transition_time_s`) — need MATLAB→Python transfer from
  the Grzywka model.

## Combustor results

**NONE this night.** Phase 2b was not executed, so no Thi/Th1/Th2 numbers
exist yet, and the Brayton T2 cross-check has not been run. This is stated
explicitly rather than reporting Night-1's `ramjet_cycle.py` numbers as if
they were the Grzywka model — they are a different, earlier-fidelity model
(station 0-2-4-9) and must not be conflated with Phase 2b's Grzywka
1→2→21→3 model.

## Resume recommendation for next session

Start with **Phase 2b on opus-tier** (full spec preserved in the
`docs/ramP/analysis_status.md` checkpoint — do not substitute sonnet), then
**Phase 3b (sonnet)**, then **Phase 4b (opus)**. Nothing simpler remains
undone — all sonnet-safe items were completed this night.

## Open questions for the team (human-required)

- Fin span vs Fusion CAD — now **URGENT** given the CFD sign flip found in
  Phase 0b.
- Teltik geometry version vs Assembly v6 (are they the same revision?).
- Nozzle Laval decision (area_ratio 4.0 design intent vs cylindrical CAD 1.0).
- Stage-1 motor datasheet.
- Inertia tensor (Ixx/Iyy/Izz) from Fusion GUI.
