# MELprop-IADE — Branching & Review Conventions

No GitHub-side admin action (branch protection, default branch, required
reviews) is configured by this document — those are human/admin actions
tracked as open items below, not something an agent session can set.

## Branch naming

| Prefix | Purpose |
|---|---|
| `main` | Protected, human-reviewed. **Not yet configured as such on GitHub** — see Open Items. Nothing merges here without human review. |
| `claude/*` | Agent-authored branches (this session's own branch is `claude/iade-repo-restructure-00rrro`). |
| `feature/*` | Human feature work. |
| `fix/*` | Focused bug fixes. |
| `docs/*` | Documentation-only work (no source/test changes). |
| `external-sync/*` | Submodule bumps / pinned-ref updates only (e.g. bumping `external/suave` or `external/pycycle` to a new tag) — kept separate from feature work so a ref bump is a single reviewable diff. |

## Review gate

- `main` requires human review before merge. This is a policy statement in
  this doc, not an enforced GitHub branch-protection rule — enforcing it
  is a GitHub admin action for a human to configure (Settings → Branches →
  branch protection rules on `main`), out of scope for what an agent
  session can do.
- Agent-authored branches (`claude/*`) always go through a PR, never a
  direct push to `main`/`develop`.

## Current state (as of 2026-07-10, this repo — `knnmelprop/iade`)

- Only one branch exists: `claude/iade-repo-restructure-00rrro` (this
  session's work: Phase 1 extraction, Phase 2 external deps, Phase 3
  environment docs).
- No `main` branch exists yet in `knnmelprop/iade` — the repo was empty
  before this session's push. Setting a default branch and branch
  protection are GitHub admin actions for a human (see Open Items).
- No PR has been opened in `knnmelprop/iade` yet — there's no other
  branch to compare against until a `main`/`develop` exists with content.

## Open items (human/admin actions, not done by this session)

1. Decide `main` vs `develop` as the default branch name for
   `knnmelprop/iade` (droneEnv used `develop`; this doc assumes `main` per
   the original task framing, but that's not been explicitly confirmed for
   this specific repo).
2. Set the default branch on GitHub and enable branch protection
   (required review, no direct pushes) — admin action.
3. Merge or otherwise land `claude/iade-repo-restructure-00rrro` onto
   whatever the chosen default branch is, since right now it's the only
   branch and nothing has that role yet.
4. Assign real CODEOWNERS handles — see `.github/CODEOWNERS`, currently
   `[TBD-HUMAN]` placeholders (no project-lead/reviewer role is defined
   anywhere in this repo's docs; not invented here).
