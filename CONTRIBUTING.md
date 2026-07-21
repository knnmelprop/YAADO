# Contributing to MELprop-IADE

This repo is currently **internal** to KNN MELprop (Politechnika
Warszawska) — this guide is for team members and agent sessions working
in it, not a public contribution guide (that's a separate, future
decision; see `docs/FUTURE_PUBLIC_READINESS_NOTES.md`).

## Environment setup

Three documented modes exist — pick one, see each doc for exactly what's
verified vs. unverified in it (don't assume a mode works end-to-end
beyond what's explicitly stated there):

| Mode | Setup doc |
|---|---|
| Devcontainer / Codespaces | [`.devcontainer/`](.devcontainer/) |
| Native Python venv | [`docs/environment-native.md`](docs/environment-native.md) |
| Conda | [`environment-conda.yml`](environment-conda.yml) |

After cloning, always run first:
```bash
git submodule update --init --recursive   # or: scripts/bootstrap_submodules.sh
```

## Branch naming and PRs

See [`docs/BRANCHING.md`](docs/BRANCHING.md) for the full convention
(`claude/*`, `feature/*`, `fix/*`, `docs/*`, `external-sync/*`). In short:
name your branch for what it does, never push directly to `main`, always
go through a PR.

## Commit messages

No strict format is enforced, but existing history favors: a short
imperative summary line (`fix:`, `feat:`, `docs:`, `chore:` prefixes are
common but not mandatory), followed by a body explaining *why*, not just
*what* — especially for anything that changes a PROVISIONAL/CONFIRMED/
SZACOWANY status or a numeric value in a vehicle config. If your change
supersedes an earlier assumption or decision, say so explicitly and
reference the relevant `HR-#`/`A#`/ADR — see
[`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) for what those mean.

## Before opening a PR

```bash
python -m pytest tests/ -v --tb=short
```

Always scope to `tests/` — running bare `pytest` from the repo root can
collect fixtures from vendored submodules under `external/` (e.g. SU2's
own meson test cases) and crash with an unrelated `INTERNALERROR`. This
is a known environment quirk, not a real test failure.

Both `python -m pytest tests/ -q` and a scoped variant should show a
clean pass count. If your change touches `analyses/`, `workflows/`, or
`vehicles/*.yaml`, check whether it makes any *other* committed result
stale (a geometry or motor-data change can silently invalidate a cached
CSV/JSON elsewhere) — see recent `docs/decision-log.md` entries for what
"chasing the full cascade" has looked like in practice in this repo.

## The PROVISIONAL / CONFIRMED / SZACOWANY / TBD_PHYSICAL_PARAM discipline

**This is the part of contributing here that's unusual, and it is not
optional or "just formatting."** Read
[`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) in full before touching any
file that carries one of these markers. The short version:

- A number in a vehicle config marked `SZACOWANY` is an estimate standing
  in for real data — it is not permitted to silently become "the real
  value" just because a PR reads more cleanly without the caveat.
- A result in analysis code marked `PROVISIONAL` has not cleared its
  verification gate (multi-method agreement for stability, mesh-quality +
  GCI for CFD, etc.) — do not remove that marker or upgrade it to
  "confirmed" language without the gate actually being cleared and a
  `docs/decision-log.md` entry recording how.
- `TBD_PHYSICAL_PARAM` (e.g. CG, moments of inertia, real motor Isp) means
  genuinely unknown, safety-relevant data. It gets swept or bounded in
  analysis (a range of plausible values), never defaulted to a single
  guessed number. If you're tempted to "just pick a reasonable value" to
  unblock a PR — don't; flag it and move on, the same way every session
  in this project's history has been expected to.
- If your own analysis or research (including anything an AI assistant
  produced for you) suggests one of these markers should change, that's
  great — but the change itself is a decision that belongs in
  `docs/decision-log.md` with the reasoning, not a silent edit. Preserving
  this discipline is more important than making a PR diff look tidy.

## A specific, repeated failure mode to avoid: trusting unverified input

Read the last section of [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md).
This project has, more than once, been handed a confident-sounding pasted
document, chat summary, or prior-agent claim about repo state that turned
out to be wrong on verification (wrong PR numbers, invented "resolved"
statuses, a numbering convention that doesn't exist, a module described
as merged when it's actually on an unmerged branch). Before acting on any
such claim — including ones in an issue, a PR description, or a prompt
handed to an agent session — check it against `git log`, `git status`,
and the actual files. This applies to humans and agents equally.
