# MELprop-IADE | RamP/IADE — Reconciled Project State | 2026-07-22

**This document supersedes all prior narratives about this repo's state** —
specifically: (1) a Perplexity research thread that claimed PR #3 and PR #5
existed with specific stability/CFD content, (2) a Haiku-generated summary
that described a `develop` branch, a merged PR #13, a branch
`claude/work-summary-status-9qte91`, and stale numbers
(`NOZZLE_AREA_RATIO_DESIGN` still at legacy 4.0/1.0, V3=1474 vs Teltik
1047 as an open/unresolved gap). **Treat both as superseded by this
document; do not re-import their numbers or branch/PR claims into any
future session.**

Everything below was verified against the live repository
(`git fetch --all --prune`, `git log`, `git ls-remote`, GitHub API PR/branch
listings, and live execution of the actual analysis modules on current
`main`) on 2026-07-22, not inferred from commit/PR titles or prior
conversation summaries.

---

## 1. The real branch/PR graph

### Branches that exist right now

| Branch | Tip SHA | Unique commits vs `main` | Status |
|---|---|---|---|
| `main` | `cb9fd87` | — (reference) | Sole authoritative mainline |
| `claude/iade-repo-restructure-00rrro` | `3e59fe4` | 0 | Fully merged; tip is a no-op merge of `main` into itself (PR #11, see §3) |
| `claude/ramp-full-analysis-rerun-up6lcz` | `2fc6ffa` | 0 | Fully merged (via PR #4 then PR #10) |
| `claude/ramp-cfd-pipeline-scaffolding` | `f7fa55a` | 0 | Fully merged (via PR #5 → `up6lcz`, then PR #10 → `main`) |
| `chore/repo-cleanup-and-docs-2026-07-11` | `70a1e1f` | 0 | Fully merged (PR #7) |
| `docs/team-review-2026-07-11` | `969b02f` | 0 | Fully merged (PR #8) |
| `docs/ramp-stage1-ideas-and-cea-findings-2026-07-11` | `3ee28fc` | 0 | Fully merged (PR #9) |
| `claude/ramp-full-analysis-rerun-nkqwp1` | `2fdd654` | **5** | **Deliberately NOT merged** — a competing Stage-1 stability implementation; see §2 |

**`develop` does not exist.** No ref named `develop` appears anywhere in
`git ls-remote origin` (heads, PRs, or otherwise). **`claude/work-summary-status-9qte91`
does not exist** either — same check, no match anywhere in the ref list.

### PRs that exist right now (all 11, via GitHub API, `state=all`)

| # | Title (short) | Head → Base | Real state |
|---|---|---|---|
| 1 | Repo separation, tooling, environment modes | `00rrro` → `main` | Merged 2026-07-10 |
| 2 | Ramjet geometry from CAD + nozzle AR propagation | `00rrro` → `main` | Merged 2026-07-10 |
| 3 | RamP full-analysis rerun (nkqwp1's Stage 1) | `nkqwp1` → `main` | **Closed, NOT merged** (2026-07-21) |
| 4 | RamP full-analysis rerun (up6lcz's Stages 1–5) | `up6lcz` → `main` | Merged 2026-07-11 09:02 |
| 5 | CFD pipeline scaffolding | `cfd-pipeline-scaffolding` → **`up6lcz`** (not `main`) | Merged 2026-07-11, but only into `up6lcz` |
| 6 | PR #2 closeout + real PRD-240 motor data + mass correction | `00rrro` → `main` | Merged 2026-07-21 07:10 |
| 7 | Repo hygiene (CONTRIBUTING.md, archive) | `chore/repo-cleanup...` → `main` | Merged 2026-07-21 |
| 8 | Team review snapshot | `docs/team-review...` → `main` | Merged 2026-07-21 |
| 9 | Preserve nkqwp1's Stage-1 ideas as docs + real CEA findings | `docs/ramp-stage1-ideas...` → `main` | Merged 2026-07-21 |
| 10 | Recover `up6lcz`'s unmerged tip (PR #5 content + HR-10..14 doc) | `up6lcz` → `main` | Merged 2026-07-21 |
| 11 | (no-op, see §3) | `main` → `00rrro` | Merged 2026-07-21, added nothing to `main` |

**Why the API's `merged` boolean looked wrong:** every merged PR above
reports `"state":"closed","merged":false` in the raw API response yet has a
real `merged_at` timestamp. The `merged_at` timestamp is the authoritative
signal (confirmed by cross-checking `git merge-base --is-ancestor` for each
PR's head SHA against `main` — every one with a `merged_at` value is a real
ancestor of `main`). Do not trust the `merged` boolean field from this
API in this repo without a git ancestor check.

**PR #5's real target was `up6lcz`, not `main`** — this is why its content
(DVC scaffold, CI workflow, pytest tiers, the 119-line CFD research doc)
never reached `main` directly on 2026-07-11 despite being reviewed and
merged that day. It reached `main` ten days later, via PR #10, once a
`main`-targeted PR was opened from `up6lcz`'s tip.

Confirmed via `mcp__github__pull_request_read(method=get_files)` (not
inferred from titles): **PR #3** touched 9 files — a full rewrite of
`analyses/stability/{datcom_class_sweep,ackeret_fin_check}.py` (517 + 125
lines changed), a test swap (`test_stability_datcom.py` removed,
`test_stability_datcom_class.py` added, 171 lines), and the session
checkpoint doc. **PR #5** touched 8 files — `.dvc/config` (hand-authored,
since `dvc` itself failed to install in-sandbox), `.dvcignore`, a CI
workflow, `.gitignore` additions for mesh/result binaries, `pytest.ini`
(test-tier markers), and two docs. Both PRs' actual diffs match their
titles/descriptions — no discrepancy found between what either PR claimed
and what it actually changed.

## 2. Why `claude/ramp-full-analysis-rerun-nkqwp1` is not merged (by design, not oversight)

`up6lcz` and `nkqwp1` independently implemented the same Stage-1 DATCOM-class
stability method on 2026-07-11, using the same filenames but different APIs
and one different modeling choice (how to fold the nonlinear body
viscous-crossflow term into the linear static-margin buildup). `up6lcz`'s
version reached `main` first (PR #4). Merging `nkqwp1`'s PR #3 on top would
have silently **overwritten** `main`'s already-reviewed module with a
competing implementation, not added anything. Instead: `nkqwp1`'s unique
value (its alternate crossflow approach, and its discovery that NASA CEA is
buildable in this cloud sandbox) was extracted into PR #9 as documentation;
PR #3 was closed without merging; `nkqwp1`'s branch was deliberately left
alone rather than deleted, so its full commit history remains inspectable.
This is why it still shows 5 commits ahead of `main` — that is the intended
end state, not an oversight.

## 3. The PR #11 anomaly, explained

PR #11 has `head=main`, `base=claude/iade-repo-restructure-00rrro` — backwards
from a normal feature→main PR. Its single commit, `93b1bbe`, is dated
2026-07-11 09:04 and was **already an ancestor of `main` since PR #4 merged
that day** (it touches `docs/ramP/human_review_night4.md`, adding a real
HR-10..HR-14 open-items table — confirmed present on `main` today). PR #11
itself was opened and merged on 2026-07-21, ten days later, but its
auto-generated GitHub description simply reused that old commit's real
metadata (including the original commit's own `Co-Authored-By`/session
footer) because it was a single-commit PR. Net effect on `main`: **none** —
`git log --oneline origin/main..origin/claude/iade-repo-restructure-00rrro`
is empty; PR #11 only brought the old `00rrro` branch up to date with `main`,
introducing no new content anywhere. This is not a fabrication or a
hallucination; it is an inert branch-sync action whose description text is
misleading only if read without checking the underlying commit dates.

## 4. Real current values (live-verified 2026-07-22, current `main` @ `cb9fd87`)

All values below were obtained by importing and executing the actual code on
a fresh checkout, not quoted from PR text.

### `NOZZLE_AREA_RATIO_DESIGN`

- `analyses/propulsion/ramjet_cycle.py:206` → `NOZZLE_AREA_RATIO_DESIGN: float = 1.317`
- `vehicles/ramjet_rocket/vehicle_config.yaml:49` → `nozzle_area_ratio: 1.317`
- **Not** the legacy 4.0 design-intent placeholder, and **not** the 1.0
  cylindrical-CAD-stub value. Both were superseded 2026-07-10 (PR #2,
  commit `7c884ea`) by the real drawing-derived value (throat 0.210 m /
  exit 0.241 m).

### V3 (nozzle-exit velocity) — three real, distinct numbers, not one

| Value | Model | File | Live result | Note |
|---|---|---|---|---|
| **1474.33 m/s** | Legacy Grzywka (`Th2`, full-expansion `p3=p0`) | `analyses/propulsion/combustor_nozzle_cycle.py`, `GrzywkaCombustorNozzleAnalysis._run_condition(2.5, 6000)` | Live-executed, current `main` | Retained on purpose as the historical baseline; unchanged since Night-3 (2026-07-09) |
| **1199.94 m/s** | `cycle_v2` Heiser & Pratt rebuild, real fixed AR=1.317, `gamma_hot=1.28` (PROVISIONAL) | `analyses/propulsion/cycle_v2/hp_stream_thrust_cycle.py`, `evaluate_cycle(CycleInputs())` | Live-executed, current `main`; confirmed altitude-invariant (identical at 6 km and 10 km) | This is `main`'s current authoritative Stage-2 result |
| **1047 m/s** | Teltik 2024 CFD | External reference, cited in `docs/assumptions.md` (A15), `docs/AGENT_CONTEXT.md`, `docs/references/ramp_analysis_plan_2026-07-11.md` | Not repo-computed — a cited literature/thesis data point at Ma2.5/6000 m | Comparison target only |

Deltas (computed fresh, not copied): cycle_v2 vs legacy = **−18.6 %**;
cycle_v2 vs Teltik CFD = **+14.6 %** (down from the legacy model's +40.8 %
gap). The **`gamma_hot=1.28` in `cycle_v2` is still a PROVISIONAL literature
default** (code comment: *"replace with a real NASA-CEA run once the team
confirms equivalence ratio / fuel"*) — this has NOT been done on `main`. A
real NASA-CEA run (γ=1.254 at a lean φ=0.7 design point) exists only as
documentation in `docs/ramP/real_cea_gamma_findings_2026-07-11.md` (from PR
#9), not wired into the code, because the practical impact is small
(<1% on V3, confirmed independently by two sessions) and rewiring a reviewed
module without a fresh test pass was deliberately deferred.

### Static margin (all methods actually run, current `main`, Mach 2.5)

| Method | Result at CG=1.6084 m | Range across CG sweep | File |
|---|---|---|---|
| Barrowman (subsonic extension) | **RETIRED as CDR gate** — historical only, marked out-of-regime in-code (valid only to ~Ma 0.7; fin span/body-dia=2.75 violates the small-fin assumption) | +8.99 cal basic / +4.594 cal extended (both historical) | `analyses/stability/barrowman_stability.py` |
| **DATCOM-class buildup** | **+11.02 cal** (live-recomputed) | **+5.13 to +11.01 cal** (CG fraction 0.37–0.64 × L = 1.611–2.787 m) | `analyses/stability/datcom_class_sweep.py` |
| **Ackeret independent hand-check** | **+9.71 cal** (live-recomputed) | — (single-CG cross-check) | `analyses/stability/ackeret_fin_check.py` |
| Teltik 2024 CFD | −2.75 cal @ Ma2.5 (external reference, `docs/assumptions.md` A15) | — | Not repo-computed |
| SU2 RANS-SST | **Never run.** `BLOCKED_BY_ENVIRONMENT` in every cloud session to date (no session, including this one, has had a buildable SU2 binary) | — | `analyses/stability/su2_cross_check/README.md` (placeholder only) |

**Gate status: NOT satisfied.** Both analytical methods agree with each
other (positive, +5…+11 cal) but conflict in sign with the Teltik CFD
reference (−2.75 cal, unstable). This is logged explicitly on `main`
(`docs/decision-log.md`, "Stage 1 gate is NOT green" addendum) and is
**still unresolved as of this document** — the SU2 tie-break remains the
single next action, and it requires a local (non-cloud-sandbox) environment.
`nkqwp1`'s independent second implementation (documented, not merged, per
§2) reproduces the same +9…+12 cal band and the same conflict with CFD —
corroborating evidence that the disagreement is a fidelity-class limitation
of linear supersonic theory on this vehicle's oversized fins, not an
implementation bug in either session.

### Stage 3 — Inlet and nozzle (current `main`)

- **Inlet** (`analyses/propulsion/inlet_performance_v2.py`, Taylor–Maccoll
  conical flow, supersedes the earlier 2-D wedge stand-in): 42° cone,
  Mach 2.5 → attached shock, β=58.5°, **overall recovery = 0.639** vs the
  MIL-E-5007D reference goal of **0.870** — does not meet the reference
  goal. (The 42° cone attaches up to ~46.1° at Mach 2.5, so it is not a
  detachment problem; the recovery shortfall is a separate loss-chain
  issue.)
- **Nozzle** (`analyses/propulsion/nozzle_expansion_check.py`, same
  `gamma_hot=1.28` as the cycle-v2 Stage-2 rebuild — the coupling the
  research plan required is honored in-code): real AR=1.317 is
  **under-expanded across the entire 4–10 km altitude band checked**
  (p_exit/p0 ≈ 2.98, roughly constant with altitude); a matched AR of
  ≈2.48 would be needed for full expansion at these conditions.

### Test count

`python -m pytest tests/ -q` on a fresh checkout of current `main`
(`cb9fd87`): **251 passed**, 1 warning (expected XFOIL supersonic-fallback
warning), 0 failed. (Scope to `tests/` — root-level `pytest` crashes on
`external/su2`'s own meson test fixtures; this is a known, documented repo
gotcha, not a new issue.)

## 5. What was stale in each prior narrative, and why

### 1. Direct-transcript-confirmed account (PR #2, 11 commits, 211/211 tests, `NOZZLE_AREA_RATIO_DESIGN=1.317`)

**Accurate as far as it goes, now incomplete.** PR #2 and its 211-test
baseline are real and correctly described — this was the state of `main`
as of 2026-07-10, before PR #4's Stage 1–5 rerun and the later PRs #6–#10
added ~40 more tests and the entire `cycle_v2`/DATCOM-class/inlet-v2 body of
work. Not stale in the sense of being wrong; stale in the sense of
describing an earlier point in the same real history. Current count is 251,
not 211.

### 2. Perplexity research thread (PR #3, PR #5 exist with specific content)

**Existence claim was TRUE.** Both PRs genuinely exist, with genuinely
matching content to what a competent read of them would show (confirmed via
direct diff in §1, not assumed). What the Perplexity thread likely got wrong
(not independently verifiable from here, since the thread itself was never
provided to this session) is **where that content ended up**: PR #3 was
never merged (§2), and PR #5 merged into `up6lcz`, not `main`, so a
same-day check of `main` alone would have missed PR #5's content entirely
until PR #10 landed it ten days later. If the Perplexity thread implied
either PR's content was live on `main` as of 2026-07-11, that specific
claim was premature, not fabricated — the content existed in a PR, just not
yet on the mainline branch a casual reader would check.

### 3. Haiku-generated summary (`develop` branch, PR #13 merged, branch `claude/work-summary-status-9qte91`, stale `NOZZLE_AREA_RATIO_DESIGN`/V3 numbers)

**The `develop` branch, PR #13, and `claude/work-summary-status-9qte91`
do not exist anywhere in this repository's git history** (confirmed by
`git ls-remote origin` returning the complete, exhaustive ref list — every
branch head and every PR head/ref, cross-checked against `mcp__github__list_branches`
and `mcp__github__list_pull_requests(state=all)` independently). This
repository has 11 PRs, numbered 1–11, none merged into or based on anything
called `develop`. Two explanations are consistent with the evidence and
cannot be distinguished from here: (a) genuine hallucination — a plausible
sounding branch/PR-number pattern invented because Haiku-tier summarization
is more prone to filling gaps with plausible-sounding specifics under
compression, or (b) cross-contamination with `knnmelprop/droneEnv`, the
original SUAVE fork this repo was extracted from (`docs/decision-log.md`'s
very first entries reference a `develop` branch and PR #11 **in droneEnv**,
a different repository) — a summary that conflated the two repos' PR
numbering would produce exactly this kind of confident-but-wrong branch/PR
reference. Given the specific, repo-appropriate-sounding detail (a
plausible `develop` branch, a plausible next-PR-number-13), (b) is the more
likely explanation, but this cannot be confirmed without the original Haiku
session transcript. **The stale `NOZZLE_AREA_RATIO_DESIGN`/V3 numbers,
however, are readily explained as currency, not fabrication:** if that
summary read a commit or branch state from before 2026-07-10 (PR #2,
commit `7c884ea`), it would correctly report the pre-fix values (4.0
design-intent / 1.0 CAD-stub, V3=1474 with no `cycle_v2` rebuild yet to
compare against) — those were genuinely `main`'s values at an earlier point
in real history, exactly analogous to narrative #1 above, just further out
of date.

## 6. Bottom line

**Narrative #1 (direct-transcript-confirmed) is closest to reality** — it
describes a real, verifiable point in this repo's actual history accurately,
just an earlier one than today's `main`. **Narrative #2 (Perplexity) is
partially real** — PR #3 and PR #5 exist with the content it likely
described, but their disposition (unmerged / merged-into-a-side-branch)
needed the verification this document provides. **Narrative #3 (Haiku
summary) should be discarded going forward** — its `develop`/PR #13/
`work-summary-status-9qte91` claims reference entities that do not exist
in `knnmelprop/iade`, and its numeric claims, even where not fabricated,
are stale relative to fixes that landed as early as 2026-07-10.

**Current authoritative state, in one line:** `main` @ `cb9fd87`, 251 tests
passing, `NOZZLE_AREA_RATIO_DESIGN=1.317`, `cycle_v2` gives V3=1199.94 m/s
(+14.6% vs Teltik CFD's 1047 m/s reference, down from the legacy model's
+40.8%), static margin +5.13…+11.02 cal (DATCOM) / +9.71 cal (Ackeret) at
Mach 2.5 — both positive but still conflicting in sign with Teltik CFD's
−2.75 cal, gate NOT satisfied pending a still-never-run SU2 cross-check.
