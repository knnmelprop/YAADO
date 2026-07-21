
MELprop-IADE
=======

**Integrated Aerospace Design Environment** — Koło Naukowe MELprop,
Politechnika Warszawska. An aircraft/rocket design analysis environment
built around a pinned fork of [SUAVE](http://suave.stanford.edu), with
project-specific modules for two vehicles:

- **Project A** — a fixed-wing drone powered by the Jetpol GTM-140, a
  Polish miniature turbojet (foundation/schema stage; no flight
  simulation yet).
- **Project B ("ramP")** — a two-stage supersonic rocket: a solid-fuel
  booster stage plus a ramjet cruise stage, target Mach 2–3.

**Project phase:** heading toward CDR (Critical Design Review). The
current, live state of what's confirmed vs. still open is **not** this
README — it's [`docs/decision-log.md`](docs/decision-log.md) (append-only
history of every real finding and decision) and
[`docs/assumptions.md`](docs/assumptions.md) (the active assumptions
register). Treat any specific status or number quoted in this README as a
snapshot that can go stale; those two files are the sources of truth.

> **Note:** this repo was extracted from a SUAVE fork
> (`knnmelprop/droneEnv`) into a standalone repo. SUAVE is now a pinned
> external dependency (`external/suave/`, git submodule — see
> [`docs/EXTERNAL_TOOLS.md`](docs/EXTERNAL_TOOLS.md)), not this repo's
> identity — the SUAVE-authored content further down (badges, citation,
> contributor list) describes and attributes the upstream project
> MELprop-IADE depends on, not this repo itself.

## Getting started

New agent session? Read
[`docs/AGENT_CONTEXT.md`](docs/AGENT_CONTEXT.md) first — the full
handoff (repo state, dependency setup, how to run analyses, known issues,
next steps).

For everyone: see [`CONTRIBUTING.md`](CONTRIBUTING.md) for environment
setup (three modes: devcontainer, native venv, conda), branch/commit
conventions, and — importantly — this project's PROVISIONAL/CONFIRMED/
SZACOWANY data-status discipline, explained fully in
[`docs/CONVENTIONS.md`](docs/CONVENTIONS.md).

Quick start:
```bash
git submodule update --init --recursive   # or: scripts/bootstrap_submodules.sh
pip install -r requirements.txt
python -m pytest tests/ -v --tb=short
```

## Where to look for what

| Question | Where |
|---|---|
| What's confirmed vs. still open, right now? | [`docs/decision-log.md`](docs/decision-log.md), [`docs/assumptions.md`](docs/assumptions.md) |
| What do HR-#, A#, ADR-### mean? | [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) |
| How do I contribute / what's the branch convention? | [`CONTRIBUTING.md`](CONTRIBUTING.md), [`docs/BRANCHING.md`](docs/BRANCHING.md) |
| External tool pins (SUAVE, pyCycle, SU2, OpenVSP, AVL/XFOIL) | [`docs/EXTERNAL_TOOLS.md`](docs/EXTERNAL_TOOLS.md) |
| Why is the repo structured this way? | [`docs/ADR/`](docs/ADR/) (ADR-001 repo separation, ADR-002 external deps, ADR-003 SU2/OpenVSP) |
| ramP (Project B) analysis tracker / results log | [`docs/ramP/analysis_status.md`](docs/ramP/analysis_status.md), [`docs/ramP/results_registry.md`](docs/ramP/results_registry.md) |
| Session lessons / handoff notes | [`agents/memory.md`](agents/memory.md) |
| Public-release readiness (license swap, etc. — **not actioned yet**) | [`docs/FUTURE_PUBLIC_READINESS_NOTES.md`](docs/FUTURE_PUBLIC_READINESS_NOTES.md) |

## Repository layout

```
core/                    # Foundation — extend via inheritance, don't rewrite
src/schemas/               # Pydantic v2 vehicle-config schemas
vehicles/                  # Vehicle YAML configs (gtm140_drone/, ramjet_rocket/)
analyses/                  # Aero, propulsion, stability, trajectory, mission, CFD
workflows/                  # OpenMDAO/mission-builder problem definitions
tests/unit/                 # pytest
docs/                       # Decision log, assumptions, ADRs, conventions
agents/                     # Session memory / handoff notes
.claude/agents/               # Subagent definitions (per-domain file scopes)
```

## Running tests

```bash
python -m pytest tests/ -v --tb=short
```
Always scope to `tests/` — a bare `pytest` from the repo root can collect
fixtures from vendored submodules under `external/` (e.g. SU2's own meson
test cases) and crash with an unrelated `INTERNALERROR`.

---

## SUAVE — the underlying framework

[SUAVE: An Aerospace Vehicle Environment for Designing Future Aircraft](http://suave.stanford.edu)

SUAVE is a multi-fidelity conceptual design environment. Its purpose is
to credibly produce conceptual-level design conclusions for future
aircraft incorporating advanced technologies.

[![Build status](https://ci.appveyor.com/api/projects/status/h33v9tottm2t5b9a?svg=true)](https://ci.appveyor.com/project/planes/suave)
[![Coverage Status](https://coveralls.io/repos/github/suavecode/SUAVE/badge.svg?branch=develop)](https://coveralls.io/github/suavecode/SUAVE?branch=develop)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.5661107.svg)](https://doi.org/10.5281/zenodo.5661107)

License: LGPL-2.1 (SUAVE's own license, applies to the vendored
`external/suave/` submodule — see [`LICENSE`](LICENSE) and
[`docs/FUTURE_PUBLIC_READINESS_NOTES.md`](docs/FUTURE_PUBLIC_READINESS_NOTES.md)
for this repo's own license status, which is a separate, not-yet-decided
question).

Guides and forum: [suave.stanford.edu](http://suave.stanford.edu).

### Contributing developers (SUAVE upstream)

Andrew Wendorff, Anil Variyar, Carlos Ilario, Emilio Botero, Francisco
Capristan, Jordan Smart, Juan Alonso, Luke Kulik, Matthew Clarke, Michael
Colonno, Michael Kruger, Michael Vegh, Pedro Goncalves, Racheal Erhard,
Rick Fenrich, Tarik Orra, Theo St. Francis, Tim MacDonald, Tim Momose, Tom
Economon, Trent Lukaczyk, Walter Maier.

### Contributing institutions (SUAVE upstream)

Stanford University Aerospace Design Lab ([adl.stanford.edu](http://adl.stanford.edu)),
Embraer ([www.embraer.com](http://www.embraer.com)), NASA ([www.nasa.gov](http://www.nasa.gov)).

### Installing SUAVE standalone (not this repo)

```bash
git clone https://github.com/suavecode/SUAVE.git
cd SUAVE/trunk
python setup.py install
```
More information: [suave.stanford.edu/download](http://suave.stanford.edu/download.html).
**For MELprop-IADE itself, use the Getting Started section above instead**
— SUAVE is one pinned dependency among several, not installed standalone.

### Citing SUAVE

```bibtex
@software{SUAVEGit,
  author = {
    Wendorff, A. and Variyar, A. and Ilario, C. and Botero, E. and
    Capristan, F. and Smart, J. and Alonso, J. and Kulik, L. and
    Clarke, M. and Colonno, M. and Kruger, M. and Vegh, J. M. and
    Goncalves, P. and Erhard, R. and Fenrich, R. and Orra, T. and
    St. Francis, T. and MacDonald, T. and Momose, T. and Economon, T. and
    Lukaczyk, T. and Maier, W.
  },
  title = {SUAVE: An Aerospace Vehicle Environment for Designing Future Aircraft},
  url = {https://github.com/suavecode/SUAVE},
  version = {2.1},
  year = {2020},
}
```

```bibtex
@inbook{SUAVE2017,
  author = {Timothy MacDonald and Matthew Clarke and Emilio M. Botero and Julius M. Vegh and Juan J. Alonso},
  title = {SUAVE: An Open-Source Environment Enabling Multi-Fidelity Vehicle Optimization},
  booktitle = {18th AIAA/ISSMO Multidisciplinary Analysis and Optimization Conference},
  doi = {10.2514/6.2017-4437},
  URL = {https://arc.aiaa.org/doi/abs/10.2514/6.2017-4437},
}
```
