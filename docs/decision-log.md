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

---

## 2026-07-10 — Checkpoint: first PR opened

- **Phase:** PR bootstrap for `knnmelprop/iade` (post Phase 1-5 +
  SU2/OpenVSP addition + preliminary analysis run).
- **Branch / HEAD:** `claude/iade-repo-restructure-00rrro` @ `012f1af`.
- **Files changed this session outside git plumbing:** none beyond what
  was already committed in prior entries — this checkpoint's own work was
  bootstrapping `main` (empty orphan → reset to real root commit
  `2072b0c`, force-pushed) and opening the PR. `agents/memory.md` and this
  file were edited to record it (this commit).
- **Tests:** 208 passed, 0 failed — matches baseline, re-confirmed
  immediately before PR creation.
- **PR:** [`knnmelprop/iade#1`](https://github.com/knnmelprop/iade/pull/1)
  (draft), base `main` @ `2072b0c`, head `claude/iade-repo-restructure-00rrro`
  @ `012f1af`. 194 files changed, +39,328/-10.
- **Untracked leftovers:** none — working tree fully clean
  (`git status --porcelain` empty except this commit's own edits;
  `runs/` correctly gitignored, not a concern).
- **Next human action:** review PR #1 (ADRs, decision log, preliminary
  analysis report), then decide on the still-open items: default-branch/
  branch-protection setup on GitHub, real CODEOWNERS handles, and the
  ranked next-work recommendations in
  `docs/ramP/preliminary_analysis_report_2026-07-10.md` (fin-span CAD
  verification first, per that report).

---

## 2026-07-10 — stage_1 booster diameter: NOT updated — CONFIRMED correct by human

- Time-boxed session asked to update `stage_1.geometry.assembly_diameter_m`
  (0.250) to 0.241m, citing "booster flange = Ø241mm" from the Czernicki
  drawing. **Not applied**, on the grounds that this session's own read
  of the drawing attributed Ø241mm to the ramjet nozzle exit diameter
  (already `stage_2.nozzle_exit_diameter_m=0.241`), not a booster
  flange. **Human confirmed immediately after**: "The outer diameter is
  0.25, and internal channel nozzle 0.241." `stage_1.geometry.
  assembly_diameter_m=0.250` stays unchanged, correct as-is; 0.241 is
  the nozzle, not the booster. No further action needed on this item.

---

## 2026-07-11 — Stage 1 — Barrowman supersonic retired as CDR stability gate

**Decision:** Barrowman's supersonic static-margin result (+8.99 cal basic /
+4.594 cal extended at Ma 2.5) is **RETIRED as the CDR stability gate** and
marked **HISTORICAL / OUT-OF-REGIME**, not reconciled with the Teltik CFD
(-2.75 cal @ Ma 2.5). Supersonic stability analysis is replaced by a
three-method gate:

1. **DATCOM-class supersonic component buildup** (`datcom_class_sweep.py`)
   — intermediate fidelity, Mach 1.2–3.0.
2. **Ackeret / slender-body independent fin CP hand-check** (`ackeret_fin_check.py`)
   — closed-form cross-check.
3. **SU2 RANS-SST** (authoritative, deferred where SU2 is not buildable).

**Rationale:**

1. **Barrowman slender-body theory is validated only to ~Mach 0.7**. The
   ramP cruise condition (Mach 2.5) is well outside this validated envelope.

2. **The ramP fins violate the small-fin assumption**:
   - Fin semi-span: 0.550 m
   - Body diameter: 0.200 m
   - Ratio: 0.550 / 0.200 = **2.75** (fin extends ~2.67× a body diameter
     from the centerline).
   - Classical Barrowman assumes fins are "small perturbations" on the body
     (fin span comparable to or smaller than body radius).

**Implementation (2026-07-11 session, aero-analyst subagent):**

- **New modules:**
  - `analyses/stability/datcom_class_sweep.py`: DATCOM/RASAero-style
    supersonic component buildup. Sweeps Mach [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    × CG fractions [0.37, 0.45, 0.55, 0.64] of total length (CG is
    TBD_PHYSICAL_PARAM — uncertain, not definitive). Body terms: nose cone
    (supersonic CP factor 2/3, NOT 0.466 ogive), shoulder transition (reused
    from Barrowman). Fin terms: Ackeret 2D slope `4/beta`, Puckett
    rectangular-tip finite-span correction (PROVISIONAL), fin-body
    interference `K_fb=1+R/(s+R)`, supersonic fin CP at 50% MAC. Outputs:
    CSV (24 grid points), JSON summary, PNG (SM vs Mach, lines per CG).
  - `analyses/stability/ackeret_fin_check.py`: Independent Ackeret
    slender-body fin CP hand-check at Ma 2.5, config CG. Classical low-AR
    downwash correction (NOT Puckett, genuinely independent method). Outputs:
    Markdown report (`ackeret_fin_check.md`).
  - **Tests:** `tests/unit/test_stability_datcom.py` (11 tests: sweep grid
    coverage, CSV columns, SM monotonic with CG, beta guards at M=1,
    components positive, Ackeret vs DATCOM fin CP agreement within one
    caliber at Ma 2.5). All 11 tests pass. Full suite: 222 passed (was 211,
    +11).

- **Barrowman module marked HISTORICAL:**
  - `analyses/stability/barrowman_stability.py`: Added module-level
    "SUPERSONIC REGIME: HISTORICAL / OUT-OF-REGIME (2026-07-11 decision)"
    section documenting the retirement rationale. Added docstring note in
    `fin_mach_correction_factor()` (supersonic branch) stating numerics are
    UNCHANGED (for historical reproducibility) but output is not used as a
    CDR gate. No numeric changes to Barrowman; it remains executable for
    historical comparison.

**Results (DATCOM-class sweep at Ma 2.5, all CG positions):**

- **Static margin range: +5.13 to +11.01 calibers** (CG sweep 0.37–0.64 L).
- **Stability conclusion: STABLE across the entire CG sweep.** Margin is
  positive at all supersonic Mach values (1.5, 2.0, 2.5, 3.0) and all CG
  positions tested.
- **Ackeret vs DATCOM fin CP agreement:** Fin CP location is **byte-identical**
  (both methods use 50% MAC + sweep formula for the supersonic fin CP).
  Fin CN_alpha differs (11.595 DATCOM vs 7.590 Ackeret, due to different
  tip-loss models: Puckett vs classical low-AR downwash), but **both agree
  on sign** (fins push CP aft, stabilizing) and **CP location** (4.425253 m
  from nose, exactly the same).

**Source references:**

- Research findings: `docs/references/ramp_analysis_plan_2026-07-11.md` (Section 1).
- Theory: Missile-DATCOM (1997), RASAero II methodology, Puckett (1946)
  supersonic tip-loss, Ackeret (1925) linearized supersonic theory, Kopal
  (1947) conical-flow CP factor.

**Next steps (per research plan):**

- Stage 2 (ramjet cycle, V3 gap): rebuild on Heiser & Pratt stream-thrust
  framework with NASA-CEA-derived γ per station.
- Stage 3 (inlet): Taylor–Maccoll 42°/60° cone, MIL-E-5007D recovery check.
- Stage 4 (nozzle): over/under-expansion check with corrected γ (coupled to
  Stage 2 cycle analysis).

### Orchestrator addendum (2026-07-11) — Stage 1 gate is NOT green: 2 analytical vs 1 CFD sign conflict is UNRESOLVED

The DATCOM-class and Ackeret results above **agree with each other** (both give
large POSITIVE static margin: DATCOM +5.13 to +11.01 cal over the CG sweep,
Ackeret +9.71 cal at the config CG). But that agreement does **not** clear the
CDR stability gate, and this entry exists so the "STABLE across the entire CG
sweep" line above is not read as a resolved verdict:

- **Both analytical methods still CONFLICT WITH the Teltik 2024 CFD** (CP 0.92 m
  from nose ⇒ **−2.75 cal, UNSTABLE at Ma 2.5**, assumptions A15). The sign
  disagreement that motivated retiring Barrowman is therefore **not** resolved
  by replacing Barrowman with two more linear methods — it is reproduced by them.
- **Why they agree with Barrowman and not CFD (structural, not a bug):** all
  three linear methods place the fin CP far aft (4.425 m, essentially at the
  tail) with the fins dominating CN_alpha, so the net CP sits well aft of any
  swept CG ⇒ big positive margin. The fins are very large (semi-span/body-dia =
  2.75); linear supersonic theory cannot capture the nonlinear fin-effectiveness
  loss / shock–boundary-layer separation on such fins that the CFD shows moving
  the net CP forward to 0.92 m. This is a **fidelity-class limitation of every
  analytical method here**, which is exactly why the research plan makes SU2 the
  authoritative arbiter — not a reason to trust the analytical +margin.
- **The CDR gate = all THREE methods agree on sign AND positive margin.** Status
  is a **2-analytical-vs-1-CFD split**, and the tie-breaker (SU2 RANS-SST,
  Stage 1 Dispatch B) is **BLOCKED_BY_ENVIRONMENT** this session (no SU2 binary;
  submodule `external/su2` not checked out; heavy C++/meson build not available
  in the cloud sandbox). **Gate verdict: NOT SATISFIED — pending SU2.**
- **Next human action:** run the SU2 RANS-SST cross-check locally (where the
  submodule can be built) at Ma 2.5, y+<1, alpha-sweep, per Stage 1 Dispatch B.
  Until then, treat the vehicle's Ma 2.5 static stability as **UNRESOLVED**, not
  as the analytical +5…+11 cal. Do not gate CDR on the analytical margin.

## 2026-07-11 — Stage 2 — Ramjet cycle / V3 rebuilt (Heiser & Pratt, station-wise gamma)

New model `analyses/propulsion/cycle_v2/hp_stream_thrust_cycle.py` (Heiser &
Pratt stream-thrust station cycle) added alongside the untouched legacy Grzywka
model. Carries cold gamma (1.40) through inlet, hot gamma (swept 1.20–1.40,
nominal 1.28 CEA-class PROVISIONAL, A19) through combustor+nozzle, and expands
through the REAL area ratio AR=1.317 (not fully-expanded).

**Result (nominal gamma_hot=1.28):** V3 = 1200 m/s (was 1474 legacy, −18.6 %);
delta vs Teltik CFD 1047 m/s cut from **+40.8 % to +14.6 %**. Exit under-expanded
(p_e/p0 ≈ 3.0) ⇒ explicit pressure-thrust term 3585 N that the legacy
fully-expanded model omitted. Th hierarchy Thi≥Th1≥Th2 = 11801/11606/11439 N.

**Key finding (nuances the research hypothesis):** V3 moves only ~0.5 % across
the whole gamma sweep at fixed geometry — **gamma is a WEAK lever**. The nozzle
**area-ratio geometry correction (implied 2.44 → real 1.317) is what closed
~26 of the ~41 gap-points**, not gamma. A residual +14.6 % vs CFD remains and is
the expected home of 1-D-model limitations (nozzle BL/divergence, real-gas /
variable-cp, spillage) — to be closed by a real CEA run and/or SU2, NOT by
tuning gamma. HR-7 status: `RECALCULATED_WITH_CORRECTED_GAMMA_AND_GEOMETRY`,
still pending independent verification (CEA/SU2 both BLOCKED_BY_ENVIRONMENT).

Gate: pytest green; V3>0 all gamma; V3 monotonic (weakly increasing) with gamma;
combustor exit hotter than inlet; thrust hierarchy holds. Files:
`analyses/propulsion/validation/v3_recalc_post_geometry_and_gamma.{md,csv}`,
`gamma_sensitivity.{py,csv}`, `tests/unit/test_gamma_sensitivity.py`.

## 2026-07-11 — Stage 3 — Inlet (Taylor–Maccoll) + Nozzle (coupled to Stage 2 gamma)

**Inlet** (`analyses/propulsion/inlet_performance_v2.py`, supersedes the wedge
model in `inlet_performance.py`): proper Taylor–Maccoll conical flow for the
external cone. Key correction — a 2-D wedge detaches at ~29.8° at M2.5 (the old
model), but the axisymmetric conical shock stays attached to ~46.1°, so the
as-drawn **42° cone is ATTACHED at design** (solver validated vs Anderson:
M2.0/20°→β=37.80°). Findings:

- 42° cone @ M2.5: attached but a strong near-normal shock (β=58.5°, pt=0.66) →
  overall recovery **0.639 vs MIL-E-5007D reference 0.870** (a GOAL, not a hard
  limit). The 21° (included-angle) reading gives 0.667 — also below. Both single
  external-cone readings fall short at every Mach, consistent with the design's
  established need for the staged **4-cone chain** (0.874, A9). The as-drawn
  42°/60° two-surface intake's true recovery needs the internal duct area
  schedule (not in the drawing) → PROVISIONAL.
- **Off-design/starting: the 42° cone DETACHES at M2.0** → bow shock, subcritical
  spillage, buzz risk. Minimum starting Mach ≈ 2.1 → a hard constraint on the
  booster→ramjet **staging Mach** the old wedge model could not surface.
- Also flagged: no boundary-layer bleed modeled (recovery optimistic);
  shock-on-lip unverified (cowl-lip position not in drawing) → PROVISIONAL.

**Nozzle** (`analyses/propulsion/nozzle_expansion_check.py`): uses the SAME
Stage 2 γ (1.28), NOT 1.4. AR=1.317 is **under-expanded (p_e/p0 ≈ 3.0) across
the whole 4–10 km band** (constant, since pt0 ∝ p0 at fixed Mach). Matched AR
would be ≈2.48 — essentially the legacy model's implied AR≈2.44, confirming the
old cycle silently assumed a fully-expanded nozzle (why legacy V3 was inflated).
Design lever: lengthening toward AR≈2.5 raises exit momentum and cuts the
under-expansion loss, traded against mass and off-design over-expansion.

Gate: pytest green (237). Files: `inlet_performance_v2.{py,md,csv}`,
`nozzle_expansion_check.{py,md,csv}`, `tests/unit/test_inlet_nozzle_v2.py`.

## 2026-07-11 — Stage 4 — Cold-flow instrumentation plan + CO2-surrogate limitation

Wrote `docs/cold_flow_test_plan.md` (AIP total-pressure rake on equal-area radii,
centerbody/cowl static taps, high-speed Z-type Schlieren + Kulite dynamic
pressure for buzz, test matrix incl. the M2.5→1.8 start/buzz sweep that probes
the predicted ~M2.1 detachment). The plan is scoped to measure shock structure,
recovery, and buzz DIRECTLY, to cross-check the Taylor–Maccoll prediction.

Wrote `analyses/cold_flow/co2_surrogate_mismatch.py` + `_note.md`: quantifies why
cold CO2 + optics verify shocks/recovery but NOT reacting mixing. Screening
result — cold CO2 is ~11× denser than hot kerosene products and carries ~11× the
momentum-flux ratio at equal injection velocity, so penetration/mixing is not
representative. Documented as a KNOWN LIMITATION (qualitative/screening only),
explicitly NOT a validated capability; cold-flow mixing must not feed the cycle
model as a validated combustor input.

Gate: pytest green (240). +3 tests.

## 2026-07-11 — Stage 5 — Integration, validation, handoff

Full `pytest tests/` green: **240 passed** (baseline 211 → +11 stability, +6
cycle, +9 inlet/nozzle, +3 cold-flow). Import audit: all 8 new/touched modules
import cleanly. Per-stage commits pushed to `claude/ramp-full-analysis-rerun-up6lcz`
(draft PR #4). Environment: venv/system-pip (pinned deps installed fresh);
pycycle NOT installed (not needed for the plain-Python H&P model); **SU2 and
NASA-CEA both BLOCKED_BY_ENVIRONMENT** (no binaries, submodule not built).

**No `vehicle_config.yaml` changes** — nothing was CONFIRMED this session:
stability is an unresolved analytical-vs-CFD split, cycle/inlet results rest on
PROVISIONAL γ / interpretation. CG and MOI remain `TBD_PHYSICAL_PARAM` (swept,
not defaulted). Assumptions register updated with the full PROVISIONAL table
(A21–A25); `agents/memory.md` and `docs/ramP/analysis_status.md` updated with the
handoff and next human actions.

**Net verdict:** the V3 gap is largely explained (geometry, not γ); the inlet and
nozzle have concrete, actionable findings (starting Mach ≈2.1; under-expanded,
matched AR≈2.48); the **stability sign conflict is the one open safety-critical
item and needs SU2 run locally**. Nothing is presented as more settled than the
physics supports.
