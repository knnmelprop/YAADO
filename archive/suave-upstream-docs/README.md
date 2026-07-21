# Archived: SUAVE upstream documentation leftovers

These four files (`1_README.md`, `prior_components.txt`,
`git_branching.txt`, `suave_config`) are SUAVE's own upstream
documentation — its own README, its own changelog of removed SUAVE
components, its own generic git-branching guide, and its own Doxygen
config. They describe the upstream SUAVE project, not MELprop-IADE.

## Why they were here at all

They were not an accident. `docs/migration-plan-phase1.md` explicitly
lists them as part of the deliberate wholesale `doc/` → `docs/` merge
during this repo's Phase 1 extraction from `knnmelprop/droneEnv` — the
whole `doc/` directory was consolidated into `docs/` in one move, with
cleanup of SUAVE-only content deferred rather than done at extraction
time.

## Why they were moved here (2026-07-11 repo-cleanup pass)

Verified zero references anywhere in this repo's tracked content (code,
tests, docs, configs) before moving. Moved with `git mv` (history
preserved, not deleted) rather than removed outright, per this project's
"when in doubt, treat as load-bearing" cleanup policy — if any of these
turn out to matter for attribution or reference later, they're still
here and still in git history under their original path via `git log
--follow`.

`docs/suave_logo.png` was considered for the same treatment but left in
place: it's explicitly exempted from `.gitignore`'s `*.png` rule
(`!/docs/suave_logo.png`), suggesting deliberate intent to use it as
branding/attribution at some point, even though nothing currently embeds
it. Not moved, not deleted — flagged in the cleanup session's report
instead.
