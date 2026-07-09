# MELprop-IADE — Agent Memory

Lessons learned, recurring failure modes, and subagent task outcomes.
Append-only; maintained by the orchestrator.

---

## 2026-07-08 — Nightly run (RamP-Fable)

### Lessons carried in from prior sessions (from run prompt / AGENT_CONTEXT.md)
- Never commit subagent work while the test suite is red (prior incident).
- Never hard-reset onto origin/develop when local commits hold real work.
- `docs/ramP/preliminary_analysis_report.md` is STALE — cite
  `docs/ramP/analysis_status.md` instead.
- Single-cone inlet failing MIL-E-5007 at M2.5 is physics, not a bug; do not
  fake inlet physics to make tests pass with too few cones.

### This-run observations
- Fresh-container drift: handoff docs and run prompts can describe WIP/commits
  that do not exist in the current clone. Always run STEP-0 verification
  (`git status`, `git cat-file -t <sha>`, pytest baseline) before acting on a
  described state; log divergences in docs/decision-log.md before Phase 1.
- Test counts in handoff docs go stale quickly (prompt said 62/66, AGENT_CONTEXT
  said 25, actual 36). Trust only a freshly run pytest.

### Nightly-run lessons (2026-07-08/09)
- **Subagent artifact recovery:** Subagent runs killed by user interrupts leave
  no artifacts — always verify expected output files exist before assuming a
  launched agent completed. Git status + pytest count are the ground truth.
- **Sonnet delegation model:** Delegating physics phases (inlet, cycle, mission)
  to sonnet-tier with tightly specified spec + orchestrator-side pytest
  verification worked reliably (75/75, 80/80 first pass). Document physics
  intent clearly; let subagents implement numerics.
- **Doc phase batching:** Combine small doc phases (e.g., tracker update +
  assumptions confirmation + memory log) into one subagent call to save
  cold-start overhead. Markdown files have low parsing cost; parallel edits
  safe if non-overlapping.

### Night-2 lessons (2026-07-09)

- **Stopping early beats stopping mid-write:** the budget guard stop worked
  cleanly this run because the opus agent (Phase 2b) was still in read-only
  exploration when it fired — no partial files, no dangling state to clean
  up. Whenever possible, prefer checking budget headroom *before* a subagent
  starts writing rather than mid-write.
- **blocked_by_budget vs merytoryczne blocked must be distinguished in
  trackers.** A resource-exhaustion stop (resume as-is next session, no
  re-diagnosis) is a fundamentally different signal than a physics/data
  blocker (needs human input or design decision). Conflating the two in
  `analysis_status.md` would cause the next session to waste time
  re-diagnosing a phase that was simply cut short.

## Night-3 STEP-0 (2026-07-09)
- Baseline: 80/80 green (after installing missing runtime deps in fresh
  container: `pytest`, `pydantic`, `pyyaml`, `scipy`, `numpy` — none were
  preinstalled; `analyses/propulsion/inlet_performance.py` imports
  `scipy.optimize`, so scipy is a hard runtime dep despite not being listed
  in CLAUDE.md's "dev deps" note).
- Blocked phases to resume: 2b (combustor_nozzle_cycle.py), 3b (staged
  mission cruise wiring), 4b (movable inlet actuation).
- Active assumptions: A1-A16 tracked in docs/assumptions.md.
- Known urgent items: fin span sign flip (SM +8.99 cal Barrowman vs
  -2.75 cal Teltik CFD at Ma 2.5 — HUMAN_REVIEW, do not resolve
  unilaterally), Grzywka combustor/nozzle model (2b), actuator params (4b).
- Working branch for this session: `claude/dazzling-turing-d91coa` (harness
  -assigned; did not create a separate night3-suffix branch per harness
  branch policy).
- **A checkpoint is a tracker section with the full resume spec, not just a
  status flag.** "BLOCKED_BY_BUDGET" alone tells the next session nothing
  about what to do; the checkpoint must carry the complete task spec (files
  to create, model equations, coefficients, fidelity requirements, tier
  requirement) so the next session can resume Phase 2b directly instead of
  re-deriving it from the original run prompt.

## Night-4 STEP-0 (2026-07-09)
- Pytest baseline: 118 passed, 0 failed (up from 80 at Night-2 start; Night-3
  delivered phases 2b/3b/4b/5/6).
- Working branch: `claude/fervent-albattani-f18spc` (harness-assigned), clean
  tree, at merge tip of PR #13.
- PRs merged since Night-3: PR #13 (combustor_nozzle_cycle Grzywka model,
  staged-mission cruise wiring, movable-spike inlet actuation, stability
  reconciliation, SU2 config generator) and PR #14 (backlog wave 1: dead-link
  audit + test docstrings).
- Stale tracker note: `docs/ramP/analysis_status.md` rows 16–18 still say
  BLOCKED_BY_BUDGET although PR #13 merged that work — refresh scheduled in
  Night-4 KROK 8.
- BLOCKED_BY_HUMAN_REVIEW items: HR-1 fin span 0.6685 m vs Fusion v6
  (3.4–4.8x reduction), HR-2 Teltik CFD geometry version, HR-3 nozzle
  area_ratio 4.0 vs CAD 1.0, HR-4 stage-1 motor datasheet (R-13), HR-5
  Ixx/Iyy/Izz from Fusion GUI, HR-6 max_rpm units decision, HR-7 V3=1474 m/s
  vs ~1047 m/s (+40.8% delta).
- Active assumptions: A1–A16 in `docs/assumptions.md` (A18–A20 planned).
- Night-4 plan: P1-A Barrowman extended sensitivity (sonnet), P1-B V3
  root-cause (opus), P1-C operational envelope (sonnet), P1-D persistent agent
  definitions (haiku), then P2-A/B/C/D.

## Night-4 close-out (2026-07-09)
- All 8 blocks (P1-A/B/C/D, P2-A/B/C/D) + backlog BB1/BB2/BB4/BB5 done; no
  budget stop. Tests 118 → 157 green; every commit gated on a green suite.
- BB1 resolved by P2-A: bare `import SUAVE` succeeds via an empty
  namespace-package stub at repo root (SUAVE/version.py, no __init__.py)
  shadowing trunk/SUAVE — availability probes must deep-import a concrete
  submodule (see analyses/suave/ramp_suave_baseline.py _probe_suave_available).
- Repo convention discovered: *.png is gitignored repo-wide (.gitignore:73);
  plots are regenerable from scripts, only CSV/JSON results are committed.
- Run-prompt path drift: prompt said vehicle/ (actual vehicles/) and
  results/combustor_nozzle_results.json (actual
  analyses/propulsion/combustor_nozzle_cycle_results.json) — STEP-0
  verification caught both before delegation.
