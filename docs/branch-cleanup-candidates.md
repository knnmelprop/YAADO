# Branch Cleanup Candidates — `knnmelprop/droneEnv`

Read-only inventory, 2026-07-10. **No branch was deleted — this is a
classification for human decision only**, per the hard constraint "do not
delete remote branches."

## Important finding: `develop` is missing recent Phase 1 work

`develop`'s HEAD (`a326122`, "Merge pull request #18 from
knnmelprop/claude/iade-repo-restructure-00rrro") only merged the branch as
of its **first** commit (`63d833f`, ADR-001 + migration-plan-phase1.md).
The branch kept moving after that merge point — `ccb73c8` (Step A
consolidation), `6f7fffa` (security note), `31df150` (Step B dry-run
results), `d300aea` (Step B promotion log) are **not** in `develop`.
PR #18 itself shows `state: closed, merged: false` via the GitHub API
despite that merge commit existing in `develop`'s history — the exact
mechanism isn't clear from git/API evidence alone (possibly a manual
merge followed by closing the PR without using GitHub's merge button).
**This needs human attention**: `develop` is currently out of sync with
the tip of `claude/iade-repo-restructure-00rrro`, and nothing in this
session re-merged it, since merging into a shared branch is exactly the
kind of shared-state action this session doesn't take without being
asked.

## Classification (16 branches, excluding `develop` and the active
`claude/iade-repo-restructure-00rrro`)

| Branch | Merged into develop? | Commits ahead | Last commit | Classification |
|---|---|---|---|---|
| `claude/dazzling-turing-d91coa` | Yes | 0 | 2026-07-09 | MERGED — safe cleanup candidate |
| `claude/fervent-albattani-f18spc` | Yes | 0 | 2026-07-09 | MERGED — safe cleanup candidate |
| `claude/melprop-iade-infrastructure-rcqzfg` | Yes | 0 | 2026-07-08 | MERGED — safe cleanup candidate |
| `claude/melprop-iade-night-run-by9c2l` | Yes | 0 | 2026-07-09 | MERGED — safe cleanup candidate |
| `claude-dev-night3` | Yes | 0 | 2026-07-09 | MERGED — safe cleanup candidate |
| `droniada` | Yes | 0 | 2025-08-14 | MERGED — safe cleanup candidate |
| `tuts2` | Yes | 0 | 2025-07-20 | MERGED — safe cleanup candidate |
| `claude/melprop-iade-infrastructure-e5b2cn` | No | 4 | 2026-07-08 | UNKNOWN — unmerged work, needs a human look before any action |
| `cursor/analyze-and-improve-container-structure-3231` | No | 6 | 2026-07-08 | UNKNOWN — recent timestamp near current restructuring work, don't assume stale |
| `cursor/document-configuration-and-suggest-student-improvements-e3d9` | No | 128 | 2026-07-08 | UNKNOWN — same caveat as above |
| `copilot/fix-70a2a66e-a39f-492e-bf95-b856fb18ba0b` | No | 5 | 2025-08-30 | STALE — old, unmerged, likely superseded |
| `cursor/document-configuration-and-suggest-student-improvements-64b7` | No | 126 | 2025-08-14 | STALE — old, unmerged |
| `cursor/fix-docker-container-user-setup-failure-eda6` | No | 128 | 2025-08-14 | STALE — old, unmerged |
| `deVibe2` | No | 129 | 2025-08-30 | STALE — old, unmerged |
| `devibe` | No | 129 | 2025-08-30 | STALE — old, unmerged (near-duplicate name of `deVibe2`, worth a human diff-check before deciding which if either has unique content) |
| `droniada.local` | No | 2 | 2025-08-14 | STALE — old, unmerged, likely a local working copy of the merged `droniada` branch |

## Recommendation (not executed — human decision required)

- **7 MERGED branches** are safe to delete once a human confirms — this
  session does not delete branches under any circumstance.
- **3 UNKNOWN branches** (`claude/melprop-iade-infrastructure-e5b2cn`,
  both `cursor/*-e3d9`/`-3231` branches with 2026-07-08 timestamps) carry
  unmerged commits and share a timestamp window with current work — worth
  a human diff review before deciding merge vs. discard, not blind
  deletion.
- **6 STALE branches** are old (Aug 2025) and unmerged — likely safe to
  delete, but that's still a human call, not an agent one.
