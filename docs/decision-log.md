# MELprop-IADE — Decision Log

Append-only, dated entries with source references (thesis/paper names, WP IDs,
phase numbers). Maintained by the orchestrator agent; team decisions are
recorded here only after a human confirms them.

---

## 2026-07-08 — Nightly run (RamP-Fable) — STEP 0 state verification

- **Fresh-container case recognized (STEP 0 / ZASADA #0).** The uncommitted WIP
  described in the run prompt (+528 lines `analyses/propulsion/inlet_performance.py`,
  +159 lines `tests/unit/test_propulsion_inlet.py`, multi-cone inlet redesign) does
  **not** exist in this environment: `git status` clean, `git diff --stat` empty.
  Phase 1 is therefore executed **from scratch**, not as a continuation.
- **Phase 3 (git-state resolution) is moot as originally specified.** Commits
  `b2cc871d` ("aero stubs") and `65631dad` ("handoff doc") do not exist in this
  clone; the equivalent work is already in history (e.g. `9f4c476e` "docs: add
  AGENT_CONTEXT.md handoff") and merged into `develop` via PR #11 (`6759fdb4` =
  current `origin/develop` HEAD). No rebase needed. Adapted Phase 3: develop on
  the designated branch `claude/melprop-iade-night-run-by9c2l` (already at
  `origin/develop` HEAD), push, open a **new draft PR** (never reuse merged PRs).
- **Baseline test state:** 36/36 passing (`pytest tests/ -v`), not 62/66 as the
  prompt assumed and not 25 as AGENT_CONTEXT.md §4 states — both counts are
  stale relative to this clone. No failing multi-cone tests exist yet.
- **Environment:** Python 3.11.15 (container), not 3.9 (the 3.9 pin lives in
  `.devcontainer/` for SUAVE). Deps installed per AGENT_CONTEXT.md §3:
  pydantic, pytest, pyyaml, numpy, scipy, matplotlib. SUAVE/AVL/XFOIL/pyCycle
  binaries not installed — pure-Python low-order models only (consistent with
  the run SCOPE: no CFD/FEA execution).
- **Budget/model note:** run executes on `claude-fable-5` as lead orchestrator.
  Phases 1 and 4 (hard physics) are executed directly by the Fable-tier lead
  rather than spawning a cold `propulsion-designer` subagent — a fresh subagent
  re-derives all context (more expensive on this plan) and the lead already
  holds the full repo state; this satisfies the "Fable-tier only for Phases
  1 and 4" budget rule. Narrow doc/test tasks are done inline for the same
  reason. `/status`-style programmatic usage introspection is not available
  inside this harness; the 200-turn hard cap and clean per-phase commits are
  the effective stop mechanisms.
