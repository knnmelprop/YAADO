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
