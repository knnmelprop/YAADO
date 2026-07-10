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

---

## 2026-07-08/09 — Nightly run summary (RamP-Fable)

**Execution:** Autonomous nightly run, orchestrated by Fable-tier lead + subagents
(propulsion-designer, mission-planner, aero-analyst on sonnet; docs-writer haiku).
Branch `claude/melprop-iade-night-run-by9c2l`, draft PR #12.

**Phase outcomes:**
- **Phase 0–1:** Multi-cone inlet (4-cone default, eta 0.8741 vs 0.8703 MIL-E-5007 PASS; 2/3 cones at 0.799/0.849 confirmed FAIL)
- **Phase 2:** 36 → 80 passing tests (full suite green; progression 48 after Phase 1, 75 after Phase 4, 80 final)
- **Phase 3:** Adapted to fresh-container case (no dangling commits b2cc871d/65631dad; equivalent work in PR #11); new draft PR #12 opened
- **Phase 4:** L2 ramjet cycle (1-D, station 0-2-4-9; thrust 12.31 kN matched nozzle vs 9.85 kN cylindrical CAD; TSFC 5.52e-5 kg/(N·s); Isp 1846 s placeholder-driven)
- **Phase 5:** Cruise design point quasi-steady (22.06 s cruise, 16.5 km range from 15 kg SZACOWANY fuel)
- **Phase 6:** Static margin review (10.08 cal verdict; fins 97% of CN_alpha; suspected Fusion export artifact, "wymaga przeglądu zespołu")
- **Phase 7:** Documentation and this report

**Key discrepancies logged:**
- Nozzle area_ratio: YAML 4.0 (design intent) vs Fusion v6 cylindrical (1.0); thrust delta 2.46 kN
- Fin span: static margin result (~10 cal) suggests 7–8x span reduction vs CAD; suspected geometry error
- Flame-holder material: Fusion v6 lists Steel vs aluminium risk note; requires human check

**Budget adjustment:** Forced mid-run switch to sonnet/haiku subagents for phases 5–7 (Fable lead retained phases 1, 4 for physics hold) to stay within token limits. Test-driven: no red commits.

**Propagation:** Full handoff via updated AGENT_CONTEXT.md, this report, and annotated assumptions register. Next session: human review of fin/nozzle geometry, obtain motor datasheet + Fusion inertia tensor.

---

## 2026-07-09 — Night-2 run (RamP-Fable, cut at 80% budget guard)

- **STEP-0 verification:** tree clean and synced with `origin`, full suite
  **80/80 tests green**, PR #12 confirmed open/draft/mergeable-clean at start,
  Night-1 report present and consulted before acting.
- **Phase 0b key finding:** `stability_margin_report.md` compares Barrowman
  (analytical) vs Teltik 2024 CFD stability margins. Teltik CP values (1.85 m
  @ Ma1.5, 0.92 m @ Ma2.5) imply SM **+0.97 cal @ Ma1.5** but
  **−2.75 cal @ Ma2.5** — a **sign flip at the cruise condition** relative to
  Barrowman's +8.99 cal. The two-methods stability gate **FAILS**. This
  elevates the standing "fin span suspect" item to **urgent team review**.
- **Phase 1b audit:** inlet completeness audit **PASSED** (4-cone default
  wired correctly at both `__init__` and `setup`, eta margin +0.0037 vs
  MIL-E-5007, no dangling 2-/3-cone references, JSON verdict PASS).
- **Budget guard fired at 80%** of the usage window during Phase 2b
  (combustor+nozzle Grzywka model), while the subagent was still in read-only
  exploration — **no files were written**. Phases 2b/3b/4b are therefore
  **blocked_by_budget** with a clean checkpoint: no partial/dangling files,
  suite still 80/80 green. Full resume spec logged in
  `docs/ramP/analysis_status.md`.
- **PR #12** continues as the single open PR for this workstream; Night-2
  doc commits were pushed onto it rather than opening a new PR.

---

## 2026-07-09 — Phase 1 Step A (IADE repo-separation) — security note

- **SECURITY NOTE:** `appveyor.yml` (removed from history in Phase 1 Step B,
  not yet executed) contained a plaintext `COVERALLS_REPO_TOKEN`. Token
  rotation on the Coveralls side is a human action item, tracked outside
  this repo. The token will be purged from history as part of Phase 1
  Step B `git filter-repo` when approved.

---

## 2026-07-10 — Phase 5 final validation

- **pytest baseline vs current:** unchanged, 208 passed / 0 failed,
  throughout Phase 2 (submodule add), Phase 3 (environment docs), Phase 4
  (branch docs), and Phase 5 (path-reference fixes below).
- **Import-path / trunk-reference audit:** grepped the full tree
  (excluding `external/` submodules and `.git/`) for `trunk` and
  `import SUAVE`. Found and fixed 6 live-operational-doc references that
  were a real correctness bug, not cosmetic: `.devcontainer/
  devcontainer.json` (`postCreateCommand` did `cd trunk; ...`, would have
  failed container build), `CLAUDE.md`, and all 5 `.claude/agents/*.md`
  (said "Never modify `trunk/SUAVE/`", a path that no longer exists).
  Also fixed docstrings/error messages in `core/vehicle_factory.py` and
  `analyses/suave/*.py`. **Correction caught mid-fix:** the SUAVE
  submodule's installable path is `external/suave/trunk/`, not
  `external/suave/` (upstream `suavecode/SUAVE` has its own internal
  `trunk/` layout) — first-pass edits said `external/suave` everywhere
  and had to be corrected after actually inspecting the submodule
  contents. All fixed paths verified against the real submodule tree, not
  assumed.
- **No direct reliance on removed `trunk/` paths remains** in any
  MELprop-authored or operational-doc file (confirmed by the audit
  above). Historical/log docs (`docs/ADR/*`, `docs/migration-plan-
  phase1.md`, `docs/AGENT_CONTEXT.md`, nightly reports, `agents/
  memory.md`'s older entries) still say `trunk/` where they're
  describing what *used to be true* — left as-is, since rewriting history
  logs to read as if the past matched the present would be inaccurate.
- **Docs updated to match reality:** README.md environment matrix +
  SUAVE-identity framing note, ADR-002 status flipped from Proposed to
  Accepted-and-executed, EXTERNAL_TOOLS.md flipped from draft to applied.
- **`agents/memory.md`:** appended (not rewritten) with this session's
  lessons — filter-repo path-list gaps, submodule internal-layout gotcha,
  operational-doc staleness as a correctness bug, and how the two
  mid-session untrusted/stale-replay messages were handled.

### Unresolved blockers (explicit list, none resolved by this session)

1. `knnmelprop/droneEnv`'s `develop` is missing 3 of 4 commits from
   `claude/iade-repo-restructure-00rrro` despite PR #18 showing
   `merged: false` with a merge commit present — needs human
   investigation and a decision on how to reconcile (see droneEnv's
   `docs/decision-log.md`, Phase 4 entry).
2. GitHub admin actions not performed (by design — out of scope for this
   session): no default branch set on `knnmelprop/iade`, no branch
   protection on any branch, no CODEOWNERS-enforcing review rule.
3. `.github/CODEOWNERS` handles are all `[TBD-HUMAN]` — no reviewer role
   is defined anywhere in this project's docs; needs real GitHub handles.
4. **UPDATED 2026-07-10, resolved for SU2/OpenVSP:** human gave explicit
   instruction "I want SU2 and OpenVSP modules installed for now in the
   repo." Added both as pinned submodules (`external/su2` @ `v8.5.0`,
   `external/openvsp` @ `OpenVSP_3.51.0`) per ADR-003, with every factual
   claim from the earlier mid-session brief (tags, licenses, PyPI
   availability) independently re-verified rather than trusted — one
   claim (OpenVSP pip wheel) did not hold up and was not acted on.
   **AVL/XFOIL remain deferred** — the instruction named SU2/OpenVSP
   specifically, not the full original deferred set. Mirrors
   (`avl-mirror`, `xfoil-mirror`) still empty.
5. SUAVE's `external/suave/trunk` editable install
   (`pip install -e external/suave/trunk`) is unverified — SUAVE 2.5.2's
   own `setup.py` targets an older Python/setuptools combination than
   this environment's Python 3.11; may need the numpy/scipy pins from
   `.devcontainer/requirements.txt` rather than root `requirements.txt`'s
   unpinned versions. Nobody has actually run this yet.
6. pyCycle's `om-pycycle==4.1.2` install and any pyCycle-backed run are
   unverified — not attempted this session (unit suite doesn't need it).
7. `environment-conda.yml` is unverified — no conda available in this
   session; never run through `conda env create`.
8. Devcontainer mode is unverified end-to-end — fixed the known-broken
   `trunk/` path, but no container was actually built/run this session.
9. `external/suave`'s match to what `droneEnv` originally vendored is by
   version string only, not a byte-level tree diff (ADR-002 caveat,
   still open).
10. `LICENSE` is still SUAVE's LGPL-2.1, unchanged, per human decision.
    PolyForm Noncommercial 1.0.0 remains a forward-looking note in
    ADR-001 only — no license decision has been made or applied.
11. README.md/CLAUDE.md still substantially frame the project in SUAVE
    terms (badges, "Simple Setup" for standalone SUAVE, contributor/
    citation blocks) — a clarifying note was added, but the full identity
    rewrite ADR-002 flagged as a follow-up was not done this session.
