# ADR-001 — Separate MELprop-IADE from the embedded SUAVE fork

- **Status:** Proposed (Phase 1 planning artifact — filter-repo not yet executed)
- **Date:** 2026-07-09
- **Deciders:** KNN MELprop human review (decisions logged 2026-07-09), agent (planning only)
- **Related:** `docs/migration-plan-phase1.md`, `docs/decision-log.md`, `docs/assumptions.md`

## Context

`knnmelprop/droneEnv` is a fork of SUAVE (suavecode/SUAVE) with MELprop's
IADE work (Project A — GTM-140 drone, Project B — ramP rocket) grafted on
top. Verified facts as of this ADR (branch `claude/iade-repo-restructure-00rrro`,
commit `a0a1b034`):

- **790 commits total**, history starting 2019-03-13 (`8a5a870b`, a SUAVE
  upstream merge). Top committers by count: Racheal Erhard (140), Matthew
  Clarke (135), "planes" (125), Emilio Botero (89), mclarke2 (67), **Claude
  (52)**, Sof222 (41), Aleks Czernicki (26), plus several more SUAVE upstream
  authors. The overwhelming majority of history is SUAVE upstream, not
  MELprop-authored.
- `.git` is **124 MB**; the `regression/` working tree alone is **311 MB**
  (359 files) — SUAVE's own regression-test corpus, referenced by
  `appveyor.yml` (`cd ../regression && coverage run automatic_regression.py`),
  not MELprop-owned.
- Embedded upstream trees still present: `trunk/` (6.5 MB, real vendored
  SUAVE source + `setup.py`/`MANIFEST.in`), `SUAVE/` (8 KB namespace stub
  shadowing `trunk/SUAVE` so bare `import SUAVE` resolves), `Tutorials-2.3.1/`
  (380 KB), `Tutorials252/` (516 KB), `ide/` (8 KB, 1 file), `templates/`
  (48 KB, 7 files) — all SUAVE tutorial/example artifacts.
- `student_competition/` (368 KB, 33 files) is **MELprop-owned** (Droniada
  Sztafeta framework, merged from the former `droniada` branch per
  `doc/AGENT_CONTEXT.md` §1) — it is *not* upstream baggage despite living
  alongside the SUAVE tutorial trees, and must not be dropped by the same
  extraction pass that removes `Tutorials*`/`ide`/`templates`/`regression`.
- `appveyor.yml` is SUAVE's Windows/AppVeyor CI config (installs into
  `trunk`, runs `regression/`) and **contains a plaintext-looking
  `COVERALLS_REPO_TOKEN` value**. It is upstream baggage scheduled for
  removal in this extraction regardless; flagging here because purging it
  from history also purges that token. Whether the token is still live is
  outside this agent's ability to check — recommend treating it as
  compromised and rotating/revoking on the Coveralls side if it is still
  active, independent of the repo-separation work.
- Two doc trees currently coexist: legacy `doc/` (from the SUAVE-tutorial
  era: `AGENT_CONTEXT.md`, `ramP/`, `segments/`, `data/`, `suave_logo.png`,
  a duplicate `PULL_REQUEST_TEMPLATE.md`) and new `docs/` (MELprop's
  `assumptions.md`, `decision-log.md`). 18 files reference `doc/` by path
  (README.md, CLAUDE.md, `.gitignore`, `agents/memory.md`,
  `docs/{assumptions,decision-log}.md`, `.claude/agents/docs-writer.md`,
  `.claude/agent-memory/docs-writer/MEMORY.md`, and several
  `analyses/`/`workflows/`/`tests/` modules) — consolidating requires a
  path move **and** a reference-fixing pass, not just `git mv doc docs`.

## Decision

1. Extract only IADE-owned paths from history using `git filter-repo` with
   a path allowlist (see `migration-plan-phase1.md`), executed against a
   **disposable clone**, never the working copy directly — and only after
   the human-confirmed backup mirror (already created, per human review) is
   verified reachable by whoever runs the command.
2. Consolidate `doc/` → `docs/` via `git mv` **as its own commit**, on the
   current branch, *before* the filter-repo pass, with a follow-up commit
   fixing the 18 known cross-references. This keeps blame/history for the
   moved files intact (`git mv` + normal commit, not filter-repo) and keeps
   the filter-repo pass simpler (single `docs/` path instead of `doc/` +
   `docs/`).
3. Deduplicate `PULL_REQUEST_TEMPLATE.md`: keep the root copy, delete
   `doc/PULL_REQUEST_TEMPLATE.md` in the same consolidation commit.
4. `SUAVE` stops being the repo's identity. `trunk/SUAVE` is pinned
   **exactly at its currently-embedded commit** (no version bump — human
   decision) and will move to `external/suave/` as a submodule in Phase 2;
   it is dropped from the extracted history in this phase, not carried
   forward as vendored source.
5. `pyCycle` is pinned to tag `4.1.2` (submodule ref) with a matching
   `om-pycycle==4.1.2` runtime pin (Phase 2 — recorded here so Phase 2
   doesn't have to re-derive it).
6. AVL, XFOIL, SU2, OpenVSP pins are **explicitly deferred** to Phase 2+.
   `knnmelprop/avl-mirror` and `knnmelprop/xfoil-mirror` exist as
   intentionally-empty placeholder repos; they will be populated with
   upstream source only after a license review, in a future phase. This is
   a logged decision, not an oversight.
7. `LICENSE` (SUAVE's LGPL-2.1 text) is **left as-is** in this phase. The
   target IADE license (**PolyForm Noncommercial 1.0.0**) is recorded here
   as a forward-looking intent only — it is **not applied** until a
   separate, explicit licensing decision is made (this ADR does not
   authorize a license change).
8. `ide/`, `templates/`, `regression/`, `appveyor.yml` are treated as
   upstream SUAVE baggage and **excluded** from the owned-path allowlist
   (same bucket as `SUAVE/`, `trunk/`, `Tutorials*`).
9. `student_competition/` and `conftest.py` are treated as **MELprop-owned**
   and **added** to the owned-path allowlist (not on the literal list given
   in the original task framing, but dropping either would destroy real
   MELprop work — `student_competition/` — or silently break every pytest
   run — `conftest.py`, which is what makes the repo root importable for
   the whole `tests/` suite). `.devcontainer/` is likewise kept: it is
   explicitly named in the target top-level structure and will be reworked
   (not removed) in Phase 3.

## Consequences

- Most of the repo's 790-commit history (SUAVE upstream authorship) is
  **not preserved** in the new `knnmelprop/iade` repo after extraction —
  accepted per human decision ("loss of part of the old history is
  acceptable if the result is a cleaner independent IADE repo").
- The AppVeyor Coveralls token disappears from the extracted history as a
  side effect of dropping `appveyor.yml`; it is **not** independently
  purged from `knnmelprop/droneEnv`'s existing history — that repo is left
  as-is per "do not rewrite history until explicitly told."
- Until Phase 2, the new `knnmelprop/iade` repo will have no SUAVE, AVL,
  XFOIL, pyCycle, SU2, or OpenVSP present at all — it will not run
  SUAVE-dependent analyses out of the box. This is expected and matches
  the phased plan.
- The `doc/` → `docs/` consolidation touches 18 files outside `doc/`
  itself; this is real, reviewable work and is called out as a discrete
  step in the migration plan rather than folded silently into filter-repo.

## Open questions carried forward (not decided here)

- Final IADE license mode/date (PolyForm Noncommercial 1.0.0 intent noted,
  not applied).
- Whether the (possibly dead) Coveralls token needs rotation on the
  service side.
- Exact `external/` submodule wiring and pinned refs for AVL/XFOIL/SU2/
  OpenVSP (Phase 2).
