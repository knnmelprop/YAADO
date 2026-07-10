# Phase 1 — History Extraction Plan

Status: **planning only — nothing in this file has been executed.**
No `git mv`, no `git filter-repo`, no push has happened yet. See
`docs/ADR/ADR-001-repo-separation.md` for the reasoning behind each
inclusion/exclusion decision below.

Source repo: `knnmelprop/droneEnv`, branch `claude/iade-repo-restructure-00rrro`
@ `a0a1b034`. Target repo: `knnmelprop/iade` (confirmed empty, 0 commits).
Backup: human-confirmed local `git clone --mirror` taken before this run —
**not independently re-verified by the agent**, per instruction.

---

## Step A — Pre-filter cleanup (run in-place on the current branch, normal commits)

These are ordinary, reversible commits on `droneEnv` itself — no history
rewrite, no filter-repo. They must land **before** Step B so the filter-repo
path allowlist only has to name `docs/`, not `doc/` + `docs/`.

1. **Consolidate `doc/` → `docs/`** via `git mv doc/* docs/` (preserves
   per-file history/blame). Merges in: `AGENT_CONTEXT.md`, `ramP/` (9 files),
   `segments/`, `data/`, `1_README.md`, `suave_logo.png`, `suave_config`,
   `git_branching.txt`.
   - Delete `doc/PULL_REQUEST_TEMPLATE.md` (keep root `PULL_REQUEST_TEMPLATE.md`
     only — human decision #4).
   - Fix the 18 known cross-references to `doc/` in the same or an
     immediately-following commit: `README.md`, `CLAUDE.md`, `.gitignore`
     (`/doc/html`, `/doc/latex`, `!/doc/suave_logo.png` → `/docs/...`),
     `agents/memory.md`, `docs/assumptions.md`, `docs/decision-log.md`,
     `.claude/agents/docs-writer.md`, `.claude/agent-memory/docs-writer/MEMORY.md`,
     and code references in `analyses/aero/barrowman_extended.py`,
     `analyses/trajectory/booster_burnout.py`, `analyses/cfd/su2_config_template.py`,
     `workflows/ramp_staged_mission.py`, `tests/unit/test_barrowman_extended.py`,
     `tests/unit/test_trajectory_launch_angle.py`,
     `analyses/aero/results/SM_sensitivity_fin_span.csv` (data file — verify
     whether the `doc/` string there is a path reference or incidental text
     before editing).
   - Run `python -m pytest tests/ -v --tb=short` — must stay at 208/208
     before committing (project rule #8 / "never commit if tests are red").
2. Commit message convention: `docs: consolidate doc/ into docs/, fix cross-references`.

**This step is not executed yet.** It requires its own go-ahead the same as
Step B, since it touches 18+ files even though each change is low-risk.

---

## Step B — History extraction (git filter-repo, disposable clone only)

### Owned paths (kept)

Per the explicit Phase-1 scope, **plus** two additions justified in
ADR-001 (`student_competition/`, `conftest.py` — both MELprop-owned/required,
not on the original literal list but dropping either destroys real work or
breaks every test collection):

```
core/
src/
vehicles/
analyses/
workflows/
agents/
.claude/
docs/
tests/
student_competition/      # ADDED — MELprop-owned (Droniada Sztafeta), not SUAVE baggage
CLAUDE.md
README.md
.gitignore
INSTALL
conftest.py               # ADDED — required for tests/ to import repo root
LICENSE                   # kept as-is per human decision #5 (left untouched)
PULL_REQUEST_TEMPLATE.md  # root copy only, after Step A dedup
.devcontainer/            # kept per target structure; reworked (not removed) in Phase 3
```

### Removed from history (upstream/vendor baggage)

```
SUAVE/            # namespace stub shadowing trunk/SUAVE
trunk/            # vendored SUAVE source (setup.py, MANIFEST.in, trunk/SUAVE/)
Tutorials-2.3.1/
Tutorials252/
ide/              # SUAVE IDE-plugin readme, 1 file
templates/        # SUAVE example templates, 7 files
regression/       # SUAVE regression-test corpus, 311 MB / 359 files
appveyor.yml      # SUAVE Windows/AppVeyor CI config (also drops the embedded Coveralls token, see ADR-001)
```

### ⚠️ Not yet classified — do not run the command until these are resolved

Everything above is either explicitly given or has an unambiguous
justification. Nothing else in the repo root was on either list from the
original task framing. Re-scanning the current tree turned up no further
unclassified top-level paths — the two lists above now account for every
top-level entry. **This section is intentionally empty after ADR-001's
additions; kept as a placeholder so a future re-run of this plan doesn't
skip the check.**

### Exact command block (for human approval — NOT executed)

```bash
# 1. Take a disposable working clone — never run filter-repo on the
#    directory anyone is actively using, and never on the backup mirror.
git clone /home/user/droneEnv /home/user/iade-extraction-work
cd /home/user/iade-extraction-work

# 2. Confirm Step A (doc/ -> docs/ consolidation) has already landed on
#    the branch being cloned, and that pytest is green, before proceeding.
python -m pytest tests/ -v --tb=short

# 3. Run the extraction. --force is required because this is a clone with
#    an `origin` remote already set; filter-repo insists on this flag
#    precisely to stop accidental in-place runs.
git filter-repo --force \
  --path core \
  --path src \
  --path vehicles \
  --path analyses \
  --path workflows \
  --path agents \
  --path .claude \
  --path docs \
  --path tests \
  --path student_competition \
  --path CLAUDE.md \
  --path README.md \
  --path .gitignore \
  --path INSTALL \
  --path conftest.py \
  --path LICENSE \
  --path PULL_REQUEST_TEMPLATE.md \
  --path .devcontainer

# 4. Inspect the result BEFORE pushing anywhere:
git log --oneline | wc -l          # expect << 790; report exact number
git log --diff-filter=A --name-only --pretty=format: | sort -u > /tmp/kept_files.txt
wc -l /tmp/kept_files.txt          # sanity check against expected owned set
du -sh .git                        # expect well under the current 124 MB

# 5. STOP. Do not add a remote / push to knnmelprop/iade yet — that is a
#    separate, explicit approval gate per the task's hard constraints
#    ("do not push rewritten history until explicitly told").
```

### Stop conditions during execution (per project stop rules)

If any of these occur, halt and report instead of improvising:
- `git filter-repo` exits non-zero or reports an unexpected empty result set.
- Post-filter `git log --oneline | wc -l` is 0 or implausibly small/large.
- `pytest` collection count in the filtered clone differs from 208 (the
  verified current baseline) once `PYTHONPATH`/deps are restored.
- Any of the 18 cross-reference fixes from Step A turn out to be
  incomplete when re-checked in the filtered clone (broken links to
  `docs/ramP/...` are a signal Step A wasn't fully applied first).

---

## Validation checklist (post-filter, pre-push)

- [ ] `git log --oneline | wc -l` reported and sane (expect roughly the
      number of MELprop-authored commits touching owned paths — likely a
      small fraction of 790; exact number depends on how filter-repo
      collapses empty commits, report it rather than assume).
- [ ] `du -sh .git` shrunk substantially from 124 MB (the 311 MB
      `regression/` and 6.5 MB `trunk/` should no longer be reachable in
      any historical blob).
- [ ] `python -m pytest tests/ -v --tb=short` → 208 passed, 0 failed, in
      the filtered clone (after reinstalling `pydantic>=2, pyyaml, pytest,
      scipy, matplotlib`).
- [ ] No remaining `import SUAVE` / `trunk.SUAVE` references resolve
      ambiguously (guarded imports in `core/` should simply report SUAVE
      unavailable, as they already do — verified this run via
      `test_probe_suave_available_is_false_in_this_container`).
- [ ] No `.gitignore` or doc cross-reference still points at `doc/`
      (should already be zero if Step A ran first).
- [ ] `docs/decision-log.md` gets an entry recording the filter-repo run
      (commit count before/after, `.git` size before/after, timestamp).

---

## Explicitly out of scope for this phase (confirmed by human review)

- No `external/` submodules wired yet (Phase 2).
- No AVL/XFOIL/SU2/OpenVSP pins (deferred to Phase 2+, logged in ADR-001).
- `avl-mirror` / `xfoil-mirror` stay empty (logged as intentional
  placeholders, human decision #3).
- No push to `knnmelprop/iade` (separate approval gate).
- No license file changes (human decision #5 — PolyForm Noncommercial
  1.0.0 is a forward-looking note in ADR-001 only).
