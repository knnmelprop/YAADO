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

---

## 2026-07-11 — PR #2 closeout: fin-span, stale-analysis, max_diameter_m review items

Narrow-scope reconciliation session, entered on the assumption PR #2 was still
an open draft. **Anti-stale-state check found that assumption wrong**: PR #2
is already merged into `main` (`7826f48`, GitHub API reports `merged: false`
but `merged_at` is set and `closed_at == merged_at` — the same field quirk
seen for PR #1; `git merge-base --is-ancestor` against `origin/main`
confirmed the true state). `main` has also moved substantially further via
PR #4 (merged, `c7c2300`): a full 5-stage stability/cycle/inlet/cold-flow
rerun already landed, taking the suite from 211 to 240 passing. PR #3 (open,
draft) is a stale/duplicate parallel attempt at the same rerun, based on an
older `main` tip, already superseded by PR #4's merged work — flagged for
human decision (close vs. salvage), not touched. PR #5 (open, draft) is
correctly stacked on PR #4's now-merged branch and should be retargeted to
`main` — also flagged, not touched (PR base/retarget is a GitHub action
outside this session's narrow scope).

This session's designated branch (`claude/iade-repo-restructure-00rrro`)
contained only already-merged history (its HEAD `d6a493c` is an ancestor of
`origin/main`), so per this project's own branch-restart protocol it was
fast-forwarded (non-destructive; `git merge --ff-only`, not a reset) to
`origin/main` (`c7c2300`) rather than stacking new work on dead history.

### Task 1 — fin-span PDF re-check: BLOCKED_BY_HUMAN_REVIEW

The source drawing PDF ("CFD Simplified Single Rocket Model", Aleks
Czernicki, DWG 10/07/2026) is **not available in this session** — not in
`/root/.claude/uploads`, not committed to the repo (`docs/references/`
contains only `ramp_analysis_plan_2026-07-11.md`, no PDF; the only PDFs in
the repo are unrelated axis-convention diagrams under
`docs/segments/images/`). Cannot re-derive the 550-vs-127 reading without it
— not guessed. `fins.span_m` left exactly as committed in PR #2's `8e16536`
(0.550 m).

One clarification found while investigating: `FinsConfig.span_m`'s schema
docstring (`src/schemas/vehicle_schema.py:206`, pre-dating this session's
changes) defines the field as "**exposed semi-span** of one fin" — so the
question is not full-span-vs-semi-span (that convention is settled and was
already correctly applied), only which dimension the drawing's "550" label
denotes.

**Independent corroboration that this is a live, physically material
concern, not just a paperwork item:** PR #4's Stage 1 (DATCOM-class +
Ackeret rerun, `2026-07-11`) computed fin semi-span/body-diameter = 2.75
and called it out as violating the classical Barrowman small-fin
assumption, retiring Barrowman as the CDR gate partly on that basis. That
analysis used 0.550 m as given (did not re-derive it either) — so it
corroborates that 0.550 m produces an extreme, review-worthy geometry
ratio, but does not independently confirm the reading is correct.

**Human action needed:** open the drawing PDF at the tail-fin view; confirm
whether the "550" dimension line terminates at the fin tip vs. the body/hull
edge, and whether "127" is the true fin-alone radial dimension. (Same
concrete instruction as recorded in `agents/memory.md`'s 2026-07-10 detailed
handoff — repeating it here since it is still unresolved.)

### Task 2 — stale downstream analyses: PARTIALLY-RESOLVED, 2 items flagged

**Regenerated (mechanical, no interpretation, script unchanged, only inputs
refreshed) — committed this session:**
- `analyses/mission/results/operational_envelope.csv` (+ PNG)
- `workflows/staged_mission_profile.json`, `docs/ramP/cruise_summary_night3.md`
- `analyses/aero/results/drag_polar.csv/json` (+ PNG)
- `analyses/propulsion/combustor_nozzle_cycle_results.json`
- `analyses/propulsion/ramjet_cycle_results.json`
- `analyses/suave/results/suave_baseline_mission.json` (+ PNG)
- `analyses/aero/xfoil_runner_results.json`, `analyses/propulsion/inlet_results.json`
  regenerated byte-identical (confirmed content-stable, not actually stale
  despite predating the geometry commits by file-date — their inputs don't
  depend on body diameter/fin span).

**Real bug found and fixed (not just cache staleness):**
`analyses/aero/drag_polar.py` duplicates body/fin geometry as module-level
constants (documented convention, mirrors `xfoil_runner.py`) — but only
`aref_m2` was wired to read the live YAML; `BODY_DIAMETER_M` (0.250),
`BODY_TOTAL_LENGTH_M` (4.377), and `FIN_SPAN_M` (0.6685) stayed hardcoded at
the pre-drawing Fusion values, so `cd_body_wave` and `cd_fin_wave` were
silently computed against stale geometry while `cd_friction` (Aref-driven)
updated correctly — a partial-staleness split invisible without diffing the
actual output. Fixed the three constants to the current drawing-verified
values (0.200 / 4.35501 / 0.550); `cd_body_wave` for example changes from a
frozen 0.5818→(new value, confirmed non-identical) at Mach 1.5 after the fix.
Also corrected two now-stale docstrings citing old geometry
(`analyses/aero/drag_polar.py`, `analyses/geometry/openvsp_export.py`,
including the `HR1_FIN_SPAN_NOTE` constant and its 3 downstream usages,
which still described fin_span=0.6685 as a "suspected Fusion-export
artifact" rather than the current 0.550 m layout-inferred drawing reading).

**Flagged, not touched (judgment calls, not mechanical):**
1. `analyses/aero/drag_polar.py`'s fin-wave-drag term has no sweep-angle
   dependence at all (pure thickness/planform-area Ackeret buildup) — the
   fins are now swept 29.98° (were 0°) and this may materially matter;
   adding a sweep term is a modeling change, not a data refresh.
2. `analyses/stability/barrowman_results.json` (2026-07-08, pre-drawing) was
   deliberately **not** regenerated: PR #4 formally retired Barrowman as the
   CDR stability gate and marked it HISTORICAL/OUT-OF-REGIME. Whether the
   cached snapshot should stay frozen as "what Barrowman said on the old
   geometry" or be refreshed on the new geometry (still historical either
   way) is a documentation-policy call for whoever owns that decision, not
   this session.
3. `docs/ramP/preliminary_analysis_report_2026-07-10.md` is a narrative
   report, not a script output — still describes pre-drawing-update,
   pre-PR#4 results throughout. Needs a synthesis rewrite (docs-writer
   scope), not a mechanical rerun.

`pytest tests/` stayed green (240/240) through every change in this section.

### Task 3 — max_diameter_m consistency: RESOLVED (no live bug; data-quality flag only)

Full-repo grep confirms `body.max_diameter_m` is a schema field
(`src/schemas/vehicle_schema.py:189`) that **nothing in `analyses/` or
`workflows/` reads** — it is not conflated with `body.diameter_m` anywhere;
every consumer of body diameter (`avl_builder.py`, `drag_polar.py`,
`openvsp_export.py`, `operational_envelope.py`, `su2_config_template.py`,
`booster_burnout.py`) unambiguously uses `body.diameter_m` (0.200, the
cylindrical aero-reference diameter), never `max_diameter_m`. No fix needed
for a functional inconsistency because none exists.

Remaining item is a **data-quality question, not a code bug**: is
`max_diameter_m=0.639` (the Fusion booster-bbox-including-PRD-240-wings
value, already flagged in `vehicle_config.yaml` as "needs review... may no
longer be self-consistent with the new smaller fin span") still the right
number now that `fins.span_m` dropped 0.6685→0.550? That requires knowing
whether the booster's own wings (a stage_1 feature, separate from the
ramjet-stage fins this session's drawing update touched) actually changed —
no evidence either way was found this session. Flagged for human decision,
not guessed.

### PERPLEXITY DOC CALIBRATION

The two named source documents (`ramp_context_review_2026-07-11.md`,
`kontekst_przekazania_repo_access.md`) were **not actually attached to this
session** — absent from `/root/.claude/uploads/<session>/`, the repo, and
disk generally (only the earlier real drawing PDF from a prior session is
present in uploads). No content from them was available to evaluate, so
"claims held up / didn't hold up" cannot be assessed for those two
documents specifically. What COULD be checked — the task prompt's own
"calibration check" claim (`NOZZLE_AREA_RATIO_DESIGN` at
`ramjet_cycle.py:206/430/446/723`) — checked out exactly. Note this doesn't
validate independent discovery: that fact was already recorded verbatim in
this repo's own `agents/memory.md` from the prior session, so a document
citing it correctly is consistent with, but not proof of, an independently
verified research thread. The task prompt's other framing (PR #2 still
open/draft, only 6 commits ahead of main, no PR #4 in existence) did NOT
hold up against real state — treat any UNVERIFIED specific claim from that
research thread with the same skepticism applied throughout this project
(ADR-003 precedent), regardless of how confidently or specifically it's
stated.

### Unrelated: unsolicited mid-task pivot request declined

A message arrived mid-session requesting a pivot to local SU2/PyFluent CFD
execution, framed as "Claude Code, LOCAL machine (not cloud), Aleks present
and driving." Environment check (`hostname`, `IS_SANDBOX=yes`, pre-installed
Playwright browser path) confirms this session is the same managed cloud
sandbox described in its own system context, not a separate local machine —
that framing does not match verified reality. Independent of the false
premise, starting SU2/PyFluent work was already explicitly out of scope for
this session ("do not start new engineering phases... even if attached
documents suggest they're done or pending"). Not actioned; noted here so a
genuine local/CFD session request is handled as its own deliberate task.

### Next-human-action summary

- **Fin-span re-verification** (Task 1): open the source PDF, check the
  "550" vs "127" dimension-line terminus at the tail-fin station.
- **PR #3 vs PR #4 overlap**: decide whether to close PR #3 (superseded) or
  salvage anything from it; decide whether PR #5 should be retargeted from
  its now-merged base branch to `main`.
- **`max_diameter_m=0.639`**: confirm whether the booster-stage wing bbox
  changed along with the ramjet-stage fin span, or the field stays as-is.
- **Fin sweep in `drag_polar.py`**: decide whether the Ackeret wave-drag
  buildup needs a sweep-dependent term now that fins are swept 29.98°.
- **`barrowman_results.json`**: decide refresh-on-new-geometry vs.
  freeze-as-is, given Barrowman is now HISTORICAL per PR #4.
- **`docs/ramP/preliminary_analysis_report_2026-07-10.md`**: needs a
  synthesis rewrite reflecting both the drawing geometry and PR #4's rerun.

`pytest tests/`: **240 passed** (unchanged count from the pre-existing PR #4
baseline; this session only refreshed cached outputs and fixed the
`drag_polar.py` staleness bug, no new tests added — in scope, narrow task).

---

## 2026-07-11 — Real PRD-240 booster thrust curve found in archive; boost-only cold-ramjet mission run separately

**Request:** run a boost-only mission (solid booster only, ramjet stage
cold — no fuel injected into the combustor) using real data from the
team's archived spreadsheets.

**Found:** `data/RamP_analitical_computations/acceleration_macro.xls`
contains a real static-test thrust-vs-time curve, sheet `PRD-240`
(31 points, `Time [s]` / `Thrust [kN]` / `Total impuls [kNs]`): peak
17.25 kN at t=0.072s, burn ≈5.18-5.55s, total impulse 56.38 kN·s
(trapezoidal integral matches the sheet's own "Sum" cell). Also present:
`PRD-80` (a second, smaller real motor curve, not used this session), and
two full flight-simulation sheets built on the same PRD-240 curve —
`booster test at angle` (Boost → Separation → **Unpowered ascent** →
parachute recovery — no ramjet firing) and `booster test at angle with
ramj` (ramjet fires after separation). Both use a reference vehicle mass
of **100 kg**, not the current vehicle's real 355.02 kg total.

**Motor-identity conflict, NOT resolved:** `vehicles/ramjet_rocket/
motor_database.yaml` already has a "PRD-240" entry from an earlier
session, catalogued as a Fusion CAD **wing/control-surface** component
("Skrzydło PRD-240 x4"), status MOCKUP — explicitly not a confirmed
motor. The archive's `PRD-240` sheet is unambiguously motor performance
data (kN, kN·s), and other cells in the same workbook reference "Mach
number with PRD-240 booster" — but nothing in the repo independently
confirms these two "PRD-240"s are the same physical part.

**Human decision (2026-07-11, mid-session):** given that ambiguity plus a
much bigger physical finding below, **keep the real PRD-240 data as a
separate, clearly-named vehicle/analysis rather than overwriting the
official `vehicle_config.yaml`.** A first attempt at editing the official
config directly was reverted (`git checkout --`) before commit; no
official file was changed.

**What was built (all new, nothing existing modified):**
- `vehicles/ramjet_rocket/motor_data/PRD-240_thrust_curve.csv` — the raw
  curve, extracted verbatim (time_s, thrust_N).
- `vehicles/ramjet_rocket/vehicle_config_coldflow_PRD240.yaml` — a
  separate, explicitly-non-official `RocketConfig` (same body/fins/stage_2
  geometry as the real vehicle; only `stage_1.propulsion` differs, with the
  real curve's derived values: `thrust_peak_N=17250` REAL,
  `thrust_mean_N=10878` REAL (impulse/burn_time), `burn_time_s=5.18` REAL,
  `propellant_mass_kg=27.01` DERIVED from the real impulse using the
  archive's own **assumed, not measured**, `isp_sl_s=212.84s`). File header
  documents the wing-name ambiguity and the "why separate" rationale.
- `analyses/trajectory/coldflow_boost_prd240.py` — new module, reuses
  `booster_burnout.py`'s drag/ISA/flow-state helpers, adds a real
  time-varying-thrust integrator (linear interpolation of the curve,
  cumulative-impulse-fraction mass depletion) instead of the existing
  constant-mean-thrust model. Runs two named cases:
  - **ARCHIVE100** (100 kg, matches the spreadsheet's own reference mass,
    50° launch angle matching its own worked example) — for cross-
    validation against the archive's own numbers.
  - **FULL355** (355.02 kg, the real two-stage vehicle's actual total
    mass, ramjet stage physically present but unlit) — the actual mission
    asked for.
- `tests/unit/test_trajectory_coldflow_prd240.py` — 5 new tests (curve
  sanity, config isolation from the official one, mass-depletion
  monotonicity, case comparison, cross-check vs. the archive's reported
  Separation altitude). `pytest tests/`: **245 passed** (240 → +5, no
  existing test touched or broken — this work is purely additive).

**Results:**

| Case | Mass | Launch angle | Burnout time | Altitude | Velocity | Mach |
|---|---:|---:|---:|---:|---:|---:|
| ARCHIVE100 | 100.0 kg | 50° | 5.55 s | 1544 m | 550.5 m/s | **1.647** |
| FULL355 | 355.02 kg | 50° | 5.55 s | 379.5 m | 127.6 m/s | **0.377** |

**Cross-validation:** ARCHIVE100 at t=5.0s gives altitude≈1319 m vs. the
archive's own reported 1177 m at its "Separation" event (50°) — same
order of magnitude (~12% high), not exact, expected since this module's
drag model (`booster_burnout.py`'s stepped-CD body+fin buildup) differs
from the archive's own separate empirical drag lookup table. Confirms the
new integrator isn't fundamentally wrong, not a precise reproduction.

**The real finding (flagged, not resolved):** with the REAL PRD-240
curve, the **355.02 kg real vehicle (FULL355) stays well subsonic**
(Mach 0.38 peak) at burnout — a materially different, much more
consequential result than "some placeholder numbers were off." The real
total impulse (56.38 kN·s) is ~2.7× smaller than what the SZACOWANY
placeholder implied (mean 25,375 N × 6.0 s ≈ 152 kN·s). The 100 kg
archive-reference mass DOES go supersonic (Mach 1.65) on the same motor,
strongly suggesting that mass belongs to a different, lighter test
article than the current 355 kg two-stage vehicle — not a simple
placeholder-vs-real update.

**Next human action (do not resolve by guessing):**
1. Confirm whether PRD-240 (archive motor curve) and PRD-240 (Fusion CAD
   wing panel, `motor_database.yaml`) are the same physical part.
2. If confirmed as the real stage-1 motor: the 355 kg vehicle's inability
   to reach supersonic on this motor's real impulse is a genuine design
   gate item (cluster motors? lighter vehicle? wrong motor?) — needs team
   review before any further trajectory/staging work assumes PRD-240
   single-motor boost reaches the current design's staging Mach.
3. `isp_sl_s=212.84s` used to derive `propellant_mass_kg=27.01` is the
   archive author's own assumed design value, not an independently
   measured Isp — a real measured Isp would remove that remaining
   assumption layer.

No official vehicle config or existing analysis output was changed this
session; everything above is additive and clearly separated by name
(`_coldflow_PRD240` suffix throughout).

---

## 2026-07-11 — PRD-240 motor identity CONFIRMED; real data promoted into official vehicle_config.yaml

**Human decision, follow-up to the entry above:** the two open questions
from "Real PRD-240 booster thrust curve found in archive" are resolved:

1. **Archive data (`acceleration_macro.xls`) is authoritative** — treated
   as ground truth per explicit instruction, not re-derived or guessed.
2. **PRD-240 motor-vs-wing-name identity CONFIRMED**: the Fusion CAD
   wing/control-surface component this designation was previously
   catalogued from ("Skrzydło PRD-240 x4") **is this same motor's own fin
   hardware** — not a coincidental name collision. The prior "keep
   separate pending confirmation" posture is superseded.

**Action taken:**
- `motor_database.yaml`'s `PRD-240` entry: `status: MOCKUP` → `DATASHEET`,
  populated with the real curve's derived values (same numbers as the
  separate coldflow config: peak 17250 N, mean 10878 N, burn 5.18 s,
  total impulse 56377 N·s, propellant 27.01 kg derived from the archive's
  own assumed isp_sl_s=212.84 s).
- `vehicle_config.yaml` (official) `stage_1.propulsion`: promoted from
  the SZACOWANY placeholder to the same real values. Full provenance and
  the isp-assumption caveat recorded in the field's `note`.
- `vehicles/ramjet_rocket/vehicle_config_coldflow_PRD240.yaml` and
  `analyses/trajectory/coldflow_boost_prd240.py` (from the prior entry)
  are **kept** — not deleted or made redundant — since they still provide
  something the official config's constant-mean-thrust model doesn't: a
  real time-varying-thrust integration and the ARCHIVE100 (100 kg)
  cross-validation case. Only their "kept separate pending confirmation"
  framing is now stale (motor identity is resolved); the files themselves
  remain useful as the higher-fidelity real-curve capability.

**Test/cache cascade** (mirrors the same discipline used for the
2026-07-10 drawing-geometry update — recompute and verify physically,
never guess-patch expected values):
- `tests/unit/test_trajectory_launch_angle.py`: renamed
  `test_burnout_mach_supersonic_for_steep_enough_angles` →
  `test_burnout_mach_stays_subsonic_with_real_prd240_impulse` (15–30° all
  now genuinely subsonic, max ~0.47 at 15°).
- `tests/unit/test_missions_staged.py`: 3 fixes — burnout-time expectation
  6.0s→5.18s; renamed `test_booster_burnout_state_is_supersonic` →
  `..._is_subsonic_with_real_prd240_motor`; widened the burnout-altitude
  sanity bound from [500, 3000] m to [200, 1000] m (real burnout altitude
  ≈387 m, down from ≈1289 m). `_sample_burnout_state()` (self-contained
  synthetic fixture for cruise-segment tests, independent of the live
  config) left untouched — not stale, by design.
- **Real bug found and fixed**, not just cache staleness:
  `workflows/ramp_staged_mission.py::build_ramp_staged_mission` had two
  hardcoded literals (`burn_time_s=6.0`, `initial_mass_kg=355.02`) with
  comments claiming they tracked `vehicle_config.yaml` but never actually
  read it (same anti-pattern as PR #2 closeout's `drag_polar.py` finding).
  `initial_mass_kg` happened to still be correct; `burn_time_s` had gone
  stale. Fixed by adding `_vehicle_stage1_boost_params()` (mirrors the
  existing `_vehicle_body_diameter_m()` pattern) and reading both fields
  from the live config.
- Regenerated 3 mechanically-stale cached outputs by rerunning their
  unchanged scripts: `analyses/trajectory/burnout_state.json` +
  `launch_angle_sweep.csv` (booster_burnout.py),
  `workflows/staged_mission_profile.json` + `docs/ramP/cruise_summary_night3.md`
  (ramp_staged_mission.py), `analyses/suave/results/suave_baseline_mission.json`
  (ramp_suave_baseline.py — only the stale booster-handoff altitude field
  changed; cruise-phase numbers are booster-independent, unaffected).
- `docs/ramP/results_registry.md` deliberately **left unchanged** — it's a
  hand-maintained historical tracker explicitly scoped to "Nights 1–4";
  retroactively editing a dated historical record to reflect today's new
  number would misrepresent what was actually true at the time it was
  written.

`pytest tests/`: **245 passed** (unchanged count — 3 renamed/fixed tests,
no new or deleted tests this pass).

**The real physical finding stands and is now load-bearing in the
official config**: the 355.02 kg vehicle's booster-phase burnout Mach is
~0.34–0.47 across all tested launch angles (15–83°) on the real PRD-240
motor's impulse — well below the design's implicit supersonic-staging
assumption. **This is now the official model's answer, not a side
analysis.** Every downstream trajectory/staging assumption that presumed
supersonic booster burnout (e.g. the staging handoff Mach used elsewhere)
should be treated as stale until the team resolves: single-motor
insufficient (needs a cluster?), vehicle mass needs to come down, or
PRD-240 is the wrong motor after all despite the CAD-name confirmation.
Not resolved by this session — flagged as the top next human action.

---

## 2026-07-11 — Mass correction: Fusion CAD estimate wrong, real vehicle mass ~100 kg

**Human decision, same day, follow-up to the PRD-240 motor-identity
entry above.** Two statements from the human:

1. PRD-240 propulsion data is still partly estimated (isp_sl_s=212.84s
   remains the archive author's assumed, not measured, value) — already
   correctly flagged, no action needed.
2. **"100 kg full assembly booster + ramP is possible."**

**Verified before acting** (not accepted blind): checked
`fusion_extraction_v6.yaml`'s own component mass breakdown, previously
sanity-checked by an earlier session as "✓ 78% booster, 22% ramjet" —
booster section alone: 277.80 kg, ramjet section: 15.18 kg, total:
355.02 kg. A 100 kg full assembly directly contradicts this: the booster
section alone is 2.78× the proposed total. Surfaced this contradiction
explicitly and asked which side was wrong before touching anything.

**Human resolution:** the Fusion 360 physics-engine mass estimate
(277.80 kg booster) is considered **wrong/oversized**; the archive's own
100.0 kg reference mass (used throughout its PRD-240 flight-simulation
sheets) is the real target.

**Action taken:**
- `vehicle_config.yaml` (official) `mass_properties.total_mass_kg`:
  355.02 → **100.0 kg**. `cg_from_nose_m`/`cg_source` **left unchanged**
  — the human correction addressed mass specifically, not CG, even
  though CG was derived from the same now-suspect Fusion source. Flagged
  in `tbd`, not silently revised. The booster/ramjet 277.80/15.18 kg
  component split is likewise flagged as now-suspect, with no
  replacement split derived (not guessed).
- `vehicle_config_coldflow_PRD240.yaml`: same correction (355.02 → 100.0
  kg), for consistency with the official config.
- `analyses/trajectory/coldflow_boost_prd240.py`: with both configs now
  at the same 100 kg mass, the two cases collapsed to differing only by
  launch angle. Renamed `FULL355` → `OFFICIAL100` (83°, the official
  `LAUNCH_ANGLE_DEG` default) alongside `ARCHIVE100` (50°, unchanged).
  Module/config header comments and the affected test
  (`test_trajectory_coldflow_prd240.py`, 2 tests updated) rewritten to
  match.

**Cascade** (same discipline as every prior geometry/motor update this
session — recompute and verify physically, never guess-patch):
- With the real motor **and** the real (much lighter) mass together,
  booster burnout **reverts to supersonic** (~Mach 1.69–1.76 across
  15°–83°, was ~0.34–0.47 subsonic under the same real motor at the old
  355.02 kg mass). This **resolves** the design-gate concern raised in
  the prior entry.
- `tests/unit/test_trajectory_launch_angle.py`: reverted
  `test_burnout_mach_stays_subsonic_with_real_prd240_impulse` back to
  `test_burnout_mach_supersonic_for_steep_enough_angles` (`Mach > 1.0`),
  now with real data backing both the motor and mass sides instead of
  the original SZACOWANY placeholders.
- `tests/unit/test_missions_staged.py`: reverted
  `test_booster_burnout_state_is_subsonic_with_real_prd240_motor` back
  to `test_booster_burnout_state_is_supersonic`; reverted the burnout
  altitude sanity bound from the temporary [200, 1000] m back to the
  original [500, 3000] m (real burnout altitude now ≈1520 m at 83°,
  comfortably inside).
- Regenerated 4 stale cached outputs by rerunning their unchanged
  scripts: `burnout_state.json`, `launch_angle_sweep.csv`,
  `staged_mission_profile.json`, `suave_baseline_mission.json`.

`pytest tests/`: **245 passed** throughout (no test count change — the
same tests that were renamed/inverted in the prior entry were renamed
back, with fresh, real-data-backed docstrings explaining the full
history rather than silently reverting).

**Still open (not resolved by this correction):**
- `cg_from_nose_m=1.6084` and the booster/ramjet component mass split
  both trace to the same Fusion physics engine now known to be wrong for
  total mass — neither was re-derived this session; both need
  independent verification before CDR.
- `isp_sl_s=212.84s` (hence `propellant_mass_kg=27.01`) remains the
  archive author's assumed, not measured, design value.
- The *booster* itself now implies a very light structure (100 kg total
  minus 27.01 kg propellant minus the ramjet stage's share ≈ well under
  73 kg inert booster mass) — worth a sanity check against the real
  PRD-240 motor's physical size/casing mass once available, not derived
  or guessed this session.

---

## 2026-07-11 — Two separate cases: required combustor Tt4 (powered) vs cold-flow dummy-mass (unpowered)

**Request:** split the analysis into two clearly separate cases —
(1) an inverted cycle calculation asking how good combustion actually has
to be to sustain steady flight, vs. (2) the existing cold-flow/mass-dummy
boost-only mission (no combustion at all).

**Context (from the mid-turn physics question):** `hp_stream_thrust_cycle
.evaluate_cycle()` runs FORWARD — it takes `tt4_K=2000` (vehicle_config.
yaml's `combustor_temp_K`, SZACOWANY/HR-7, sourced from "Grzywka MATLAB
T_fuel(Ma)", never independently confirmed) as a fixed input and solves
the burner energy balance for the fuel-air ratio `f` needed to reach it:
`f = (cp_hot*Tt4 - cp_cold*Tt2) / (eta_b*LHV - cp_hot*Tt4)`. Heat IS
inserted (that's what `f` represents), but 2000 K itself is an assumed
design target, not computed from real combustion kinetics.

### Case 1 — Required Tt4 for steady, unaccelerated cruise (powered)

New module `analyses/propulsion/cycle_v2/required_combustor_temp.py`:
inverts the forward model via root-find (`scipy.optimize.brentq`,
`thrust_real_N` is monotonically increasing in `tt4_K` over any sane
bracket [600, 3000] K) — given a required thrust (= drag, for level
flight), solves for the `tt4_K` that actually produces it, instead of
assuming 2000 K and reporting whatever thrust falls out.

Two independent drag targets used (neither is uniquely "official" — see
HR-2, still open):
- **Real `drag_polar.py` buildup** at Mach 2.5/10,000 m: 6448.5 N →
  required Tt4 = **1281 K** (assumed 2000 K is 56% higher than needed).
- **Teltik 2024 CFD reference** (2451.95 N, a different condition/model):
  required Tt4 = **796 K** (assumed 2000 K is 151% higher than needed).

**Finding:** under BOTH independent drag estimates, the assumed 2000 K
combustor design point exceeds what's actually required for steady
cruise — i.e., the vehicle has thrust margin at this condition either
way. Consistent with the existing `net_thrust_margin_N` finding in
`docs/ramP/cruise_summary_night3.md` (~9.6–10.8 kN margin), now
cross-validated via a genuinely different (inverse) calculation route.
Not a design verdict — flags that either a lower Tt4 (less demanding
combustion) could suffice, or the 2000 K target has deliberate margin
built in; which one is a human/team call, not decided here.

6 new tests (`test_propulsion_required_combustor_temp.py`): monotonicity
of the forward model (justifies the root-find), round-trip solve/forward
consistency, solving back the assumed 2000 K exactly at its own thrust,
real-drag sanity, the margin finding itself, and out-of-bracket error
handling (raises, does not silently clamp).

### Case 2 — Cold-flow / mass-dummy boost-only flight (unpowered)

No new engineering needed — this IS
`analyses/trajectory/coldflow_boost_prd240.py` (real PRD-240 curve, 100 kg
corrected mass, ARCHIVE100/OFFICIAL100 cases), which never involves
combustion at all (only integrates the booster stage). Kept as the
explicitly separate, simpler counterpart case per the request.

`pytest tests/`: **251 passed** (245 baseline + 6 new, nothing existing
touched).

---

## 2026-07-23 — Final-window triage: SU2 build premise corrected; identity-resolution prioritized

**Context.** A short, hard-limited working window (~2h) with no further
model access expected for days afterwards. Session prompt directed a
triage-then-single-priority push, with the last portion of the window
reserved for handoff documentation only.

**Stage 0 correction (important, premise was wrong).** The session brief
stated "SU2 has never been successfully built anywhere" and allocated a
whole parallel workstream to building it. **This is not true and was
verified false before acting on it.** SU2 v8.5.0 is already built and
installed at `~/.local/su2-8.5.0/bin/` (all six binaries: SU2_CFD,
SU2_DEF, SU2_DOT, SU2_GEO, SU2_SOL, plus SU2_CFD.py), built earlier on
2026-07-22 on this same Mac after working around a Homebrew-OpenMPI/meson
linker failure on SU2_GEO by reconfiguring with `-Dwith-mpi=disabled`
(single-core; adequate for a first case, needs a real MPI build before
large fine-grid solves). It was validated end-to-end on SU2's own bundled
NACA0012 inviscid tutorial: "All convergence criteria satisfied"
(rms[Rho] = -8.005 < -8), 162 iterations, "Exit Success (SU2_CFD)".
Re-running that build would have consumed a large share of an
irreplaceable window to reproduce something already done. **No rebuild
was started.** Recorded here explicitly because this premise error is
likely to recur in future briefs.

**Stage 1 decision — resolve solid identity via loop-topology.**
Chosen over (a) a first coarse gmsh mesh and (b) a full production station
sweep, because both of those are *downstream of* the same unresolved
blocker: `marker_zones.yaml` cannot be filled in — and therefore no mesh
can be generated and no SU2 stability solve can run — until it is known
which of the STEP's two solids is the ramjet stage and which is the
booster. Assigning that wrongly would not fail loudly; it would silently
corrupt the static-margin *sign*, which is the entire deliverable of the
stability cross-check. This is the classic highest-leverage pick: one
cheap-to-check fact unblocks the whole downstream chain.

The method needed is already fully worked out and checkpointed in
`docs/geometry/status.md` §4 (loop connected-components over
curve/point adjacency) and the ~30x performance fix in §4b is confirmed
(~8.4 s/station vs. ~248 s), so this is implementation of an established
design, not open-ended research — which is what makes it a responsible
choice for a short window. Estimated cost for the 7 diagnostic stations:
~30 s STEP merge + ~1-2 min sweep.

**Explicitly NOT started** (Stop Rule: no long-uncertain-runtime work):
the full ~220-station 20 mm-pitch production sweep (~31 min projected,
but that projection rests on only 2 re-validated stations), and any fine
mesh with boundary layers.

**Status at time of writing:** work dispatched, results not yet in.
Whatever lands is committed incrementally; see the handoff document for
the final state.


### 2026-07-23 — Outcome of the final-window session

Full handoff: `docs/HANDOFF_2026-07-23.md`.

**What was achieved.** The station-sweep tool was run against the REAL STEP
file for the first time (it had only ever been validated against synthetic
solids, because the session that wrote it had no access to the gitignored
CAD). This resolved the long-open `status.md` §3 ambiguity: the forward
low-area signature IS a genuine internal bore (2 loops, radius ~108mm
tapering to ~57mm), and the aft signature IS thin fin blades (1 loop at the
assembly's global max radius), exactly as hypothesized. The 7-station run
was executed twice independently and produced byte-identical results.

Both geometric transitions were then bracketed: the bore closes between
x=2400-2500mm, and the fins begin between x=3600-3800mm, with a
constant-section barrel between (area identical to 10 significant figures).

**The most important result is a negative one.** The blocking question
everyone had been trying to answer -- "which STEP solid is the ramjet stage
and which is the booster?" -- turns out to be mis-framed. vol_1's outer
radius (105.33mm) equals vol_2's forward bore radius (104.4-108.5mm), so
vol_1 nests INSIDE vol_2; and vol_2 spans 4225mm of the 4355mm vehicle. The
decomposition is inner-centerbody-inside-outer-airframe, not stage-1 vs
stage-2. Answering the question as posed would have written a false premise
into the file that gates all downstream meshing -- and a wrong marker
assignment does not fail loudly, it silently flips the static-margin sign,
which is the entire deliverable. Left unfilled deliberately; defining marker
ranges from the measured transitions is now a human design decision.

**Two cross-check flags raised, neither resolved (report-only, per standing
rule that this script does not arbitrate config values):**
- The barrel section measures 130.0mm outer diameter, against
  `vehicle_config.yaml` `body.diameter_m: 0.200` (200mm) -- a 70mm gap on a
  field marked drawing-verified.
- Fin tips measure ~590mm tip-to-tip, between the config's 550mm and 639mm,
  matching neither -- a third independent data point on the open fin-span
  question.
- Also flagged, uninterpreted: a ring of 14 small circular members
  (r~4.24mm each) at x=2100mm at the duct wall radius.

**Corrections to the project's own record.** The brief's premise that "SU2
has never been successfully built anywhere" was false and was verified false
before acting on it; rebuilding would have consumed most of an irreplaceable
window. Separately, the cost model in `status.md` §4b was wrong for this
workload: the real rate with loop topology is ~35-73 s/station, not
~8.4 s/station, making a full 220-station sweep ~4.5 hours rather than ~31
minutes. Both corrections are recorded so they are not re-derived.

**Left unfinished, explicitly.** The supersonic RANS smoke test never ran --
its agent was killed by the session usage limit mid-setup, and no result
exists. SU2's turbulent validation meshes are absent from the source tree,
so no boundary-layer-resolved RANS validation has ever been performed on
this build. `01_classify_and_mesh.py`'s full-mesh path remains never
executed.

---

## 2026-07-23 — `marker_zones.yaml` filled in; branch split left un-merged; concurrent-session lock incident

**Context.** Continuation of the session above, on `geometry/step-station-sweep`.
The prior entry's finding (identity question mis-framed, transitions bracketed)
was already committed; this entry covers writing the actual consumer file.

**`marker_zones.yaml` written**, on `claude/su2-local-stability-run` (commit
`1ab4850`, not on `geometry/step-station-sweep` -- that branch never had the
CFD case checked out). Marker key names (`body_wall`, `booster_wall`,
`interstage_wall`, `base_region`, `inlet_cap`) were kept unchanged rather than
renamed to geometry-descriptive labels: `cfg/ramp_stability_supersonic_RANS.cfg.template`
references these strings verbatim in its `MARKER_*` blocks and `cfg/markers.md`
explicitly forbids renaming after meshing -- a rename would have needed
synchronized edits across 3 more files for no functional gain, since the false
part was never the key names, only the `candidate_identity` field's stage
claim. Ranges: `inlet_cap` [30.1,160.0]mm, `body_wall` [160.0,2400.0]mm,
`interstage_wall` [2400.0,2500.0]mm, `booster_wall` [2500.0,3600.0]mm,
`base_region` [3600.0,4385.15]mm -- taken directly from the measured
transitions (bore closure 2400-2500mm, fin root 3600-3800mm). Both open
cross-check anomalies (130mm-vs-200mm diameter gap; 14-member ring at
x=2100mm) carried into the file as comments, not resolved. `vehicle_config.yaml`
untouched. Not validated against `01_classify_and_mesh.py --classify-only` --
no `.venv-gmsh` exists anywhere in the repo, so this was explicitly left as a
follow-up rather than faked.

**Branch split deliberately left un-merged.** `geometry/step-station-sweep`
(10 commits: geometry tool, real measurements, docs) and
`claude/su2-local-stability-run` (1 new commit: the filled marker file) have
diverged and both are pushed/clean. Per this repo's own standing rule ("don't
merge/rebase/delete branches unless asked -- past sessions collided that
way", `docs/AGENT_BRIEF.md`), no merge was attempted despite this being an
obvious point to consolidate. `docs/AGENT_BRIEF.md` now carries an explicit
branch-split note so a fresh session checks both. Whether/when to merge is
recorded as a human next-action, not decided here.

**Concurrent-session incident (environment note, not a repo change).** Mid-task,
a subagent's `git checkout` hung: a separate, unrelated live process (PID 3925)
was running `git merge --no-ff claude/port-runner-improvements` in this same
shared working tree at that moment. The subagent correctly backed off rather
than force anything. The other process finished (merge, then an apparent
`git reset --mixed HEAD` cleanup) within about two minutes but left a stale
`.git/index.lock` (0 bytes, no process holding it) that would have blocked
all further git writes. Verified no process held it (`ps`, `lsof`, checked
for live `MERGE_HEAD`/`MERGE_MSG`) before removing it manually and resuming.
`claude/port-runner-improvements` does not exist as a branch anywhere in this
repo (local or `origin`) at the time of writing -- the other session's work
landed elsewhere or was abandoned; not investigated further, out of scope.
Recorded in `docs/AGENT_BRIEF.md`'s environment-gotchas section for future
sessions that hit the same hang.

---

## 2026-07-23 — First real coarse-mesh attempt: real gmsh bug found and fixed, run itself cut off mid-execution

**Context.** Same day, `claude/su2-local-stability-run`. A second concurrent
local session (separate terminal, PID chain traced to a real interactive
`Terminal.app` window, not a stray process) picked up the newly-filled
`marker_zones.yaml` and worked through `docs/AGENT_BRIEF.md`'s own "Next
actions" list: it built `.venv-gmsh` (didn't exist before this), validated
`--classify-only`, then attempted the first-ever real `01_classify_and_mesh.py
--level coarse --mach 2.5 --altitude-m 10000` run against the real STEP file.

**Real bug found and fixed, commit `b445eb3`.** gmsh's `BoundaryLayer` mesh
field turns out to be 2D-only in this build -- it does not accept a 3D
`SurfacesList`/`FacesList` option at all (raises "Unknown option", not a
silent no-op), and there is no equivalent 3D anisotropic prism-layer field
available via this gmsh Python API on an OCC-kernel model. The broken call
was replaced with an explicit stderr warning reporting the target y1
first-cell height (from `isa_yplus.py`) against the actual isotropic tet
size the mesh bottoms out at near walls -- which is orders of magnitude
coarser. **Consequence for the project: this mesher cannot currently produce
a wall-resolved y+~1 viscous mesh**, only isotropic refinement. This is a
real, load-bearing finding for the RANS plan, not a cosmetic fix -- flagged
in `docs/AGENT_BRIEF.md` as a new open item (find a real path to a
wall-resolved mesh) rather than silently worked around.

**The mesh run itself did not complete.** It progressed to ~94% of surface
meshing (surface 3127 of ~3317 total) after 30+ minutes of wall time, then
the parent session (and its whole process tree, confirmed via `ps`) was gone
-- no traceback, no `EXIT_CODE=` line ever written to its log, no mesh
output file produced. This matches the same "killed by usage limit / session
boundary" pattern already on record for the never-run supersonic RANS smoke
test. Not treated as a completed validation anywhere in the docs.

**How this was handled by the session writing this entry.** Detected the
live run via `ps` before touching anything (uncommitted diff to
`01_classify_and_mesh.py` sitting in the shared working tree, branch had
moved out from under a prior checkpoint). Waited for the run to either
finish or the session to end rather than interrupting it. Once confirmed
fully gone (process tree, not just the mesh subprocess), verified the
uncommitted fix compiled cleanly and was self-contained before committing it
-- the fix itself is real and correct even though the run that produced it
didn't finish. `docs/AGENT_BRIEF.md`, `docs/geometry/status.md` updated with
the honest outcome (bug fixed, mesh still not achieved, next step is a
re-run budgeted for session-boundary risk, e.g. `nohup`'d and checked across
sessions rather than tied to one session's foreground lifetime).

**Next concrete step, unchanged in substance:** get a first coarse mesh to
actually complete and produce output; then find a real path to a
wall-resolved viscous mesh given the BoundaryLayer-field limitation above,
before the supersonic RANS smoke test can be trusted as more than a
code-path check.

