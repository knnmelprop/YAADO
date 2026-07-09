# MELprop-IADE — Agent Memory

Lessons learned, recurring failure modes, and subagent task outcomes.
Append-only; maintained by the orchestrator.

---

## 2026-07-08 — Nightly run (RamP-Fable)

### Lessons carried in from prior sessions (from run prompt / AGENT_CONTEXT.md)
- Never commit subagent work while the test suite is red (prior incident).
- Never hard-reset onto origin/develop when local commits hold real work.
- `doc/ramP/preliminary_analysis_report.md` is STALE — cite
  `doc/ramP/analysis_status.md` instead.
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
- **A checkpoint is a tracker section with the full resume spec, not just a
  status flag.** "BLOCKED_BY_BUDGET" alone tells the next session nothing
  about what to do; the checkpoint must carry the complete task spec (files
  to create, model equations, coefficients, fidelity requirements, tier
  requirement) so the next session can resume Phase 2b directly instead of
  re-deriving it from the original run prompt.
