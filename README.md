
MELprop-IADE
=======

> **Note (Phase 1/2, 2026-07-10):** this repo was extracted from a SUAVE
> fork (`knnmelprop/droneEnv`) into a standalone MELprop-IADE repo. SUAVE
> is now a pinned external dependency (`external/suave/`, submodule, see
> `docs/EXTERNAL_TOOLS.md`), not this repo's identity — the SUAVE-authored
> content below (badges, citation, contributor list) describes the
> upstream project MELprop-IADE depends on and builds attribution for it,
> not this repo itself. See "Stan projektu" further down for the
> MELprop-IADE project description.

[SUAVE: An Aerospace Vehicle Environment for Designing Future Aircraft](http://suave.stanford.edu)
-------

SUAVE is a multi-fidelity conceptual design environment.
Its purpose is to credibly produce conceptual-level design conclusions
for future aircraft incorporating advanced technologies.

[![Build status](https://ci.appveyor.com/api/projects/status/h33v9tottm2t5b9a?svg=true)](https://ci.appveyor.com/project/planes/suave)
[![Coverage Status](https://coveralls.io/repos/github/suavecode/SUAVE/badge.svg?branch=develop)](https://coveralls.io/github/suavecode/SUAVE?branch=develop)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.5661107.svg)](https://doi.org/10.5281/zenodo.5661107)

License: LGPL-2.1

Guides and Forum available at [suave.stanford.edu](http://suave.stanford.edu).


Contributing Developers
-----------------------
* Andrew Wendorff
* Anil Variyar
* Carlos Ilario
* Emilio Botero
* Francisco Capristan
* Jordan Smart
* Juan Alonso
* Luke Kulik
* Matthew Clarke
* Michael Colonno
* Michael Kruger
* Michael Vegh
* Pedro Goncalves
* Racheal Erhard
* Rick Fenrich
* Tarik Orra
* Theo St. Francis
* Tim MacDonald
* Tim Momose
* Tom Economon
* Trent Lukaczyk
* Walter Maier

Contributing Institutions
-------------------------
* Stanford University Aerospace Design Lab ([adl.stanford.edu](http://adl.stanford.edu))
* Embraer ([www.embraer.com](http://www.embraer.com))
* NASA ([www.nasa.gov](http://www.nasa.gov))

Simple Setup (SUAVE itself, standalone)
------------

```
git clone https://github.com/suavecode/SUAVE.git
cd SUAVE/trunk
python setup.py install
```

More information available at [download](http://suave.stanford.edu/download.html).

**For MELprop-IADE (this repo), see the Environment Setup section below
instead** — SUAVE is one pinned dependency among several, not installed
standalone.


Requirements
------------

numpy, scipy, matplotlib, pip, scikit-learn, plotly


Developer Install
-----------------

See [develop](http://suave.stanford.edu/download/develop_install.html).

Citing SUAVE
-----------------

This respository may be cited via BibTex as:

```
@software{SUAVEGit,
  author = {
    Wendorff, A. and
    Variyar, A. and
    Ilario, C. and
    Botero, E. and
    Capristan, F. and
    Smart, J. and 
    Alonso, J. and
    Kulik, L. and
    Clarke, M. and
    Colonno, M. and 
    Kruger, M. and
    Vegh, J. M. and 
    Goncalves, P. and
    Erhard, R. and
    Fenrich, R. and
    Orra, T. and 
    St. Francis, T. and
    MacDonald, T. and
    Momose, T. and
    Economon, T. and
    Lukaczyk, T. and
    Maier, W.
},
  title = {SUAVE: An Aerospace Vehicle Environment for Designing Future Aircraft},
  url = {https://github.com/suavecode/SUAVE},
  version = {2.1},
  year = {2020},
}
```
The most recent publication covering the general capabilities of SUAVE was presented at the 18th AIAA/ISSMO Multidisciplinary Analysis and Optimization Conference and may be cited via BibTex as:

```
@inbook{SUAVE2017,
author = {Timothy MacDonald and Matthew Clarke and Emilio M. Botero and Julius M. Vegh and Juan J. Alonso},
title = {SUAVE: An Open-Source Environment Enabling Multi-Fidelity Vehicle Optimization},
booktitle = {18th AIAA/ISSMO Multidisciplinary Analysis and Optimization Conference},
chapter = {},
pages = {},
doi = {10.2514/6.2017-4437},
URL = {https://arc.aiaa.org/doi/abs/10.2514/6.2017-4437},
eprint = {https://arc.aiaa.org/doi/pdf/10.2514/6.2017-4437}
}
```

---

## Stan projektu (Night-4, 2026-07-09)

**MELprop-IADE** (Koło Naukowe MELprop, Politechnika Warszawska) is an integrated aircraft design environment forking SUAVE with specialized modules for Polish educational and research projects.

**Test status**: 157 green (pytest); blocks: none (Night-4 complete).  
**Project A (GTM-140 drone)**: foundation only (vehicle config schema, no flight sim yet).  
**Project B (ramP—ramjet rocket, two-stage)**: stability under geometry audit (HR-1/HR-2 flagged), V3 exit velocity root-caused to nozzle CAD assumption (HR-3), operational envelope all-SUSTAINED pending real drag polar.

**Key documentation**:
- [Analysis Status Tracker](docs/ramP/analysis_status.md) — Mach×altitude×analysis completion grid.
- [Results Registry](docs/ramP/results_registry.md) — Unified artifact log (Nights 1–4 JSON/CSV).
- [Nightly Run Report (2026-07-11)](docs/ramP/nightly_run_report_2026-07-11.md) — Agent outputs summary.
- [Human Review (Night-4)](docs/ramP/human_review_night4.md) — Flagged issues, next steps.
- [External Tools Registry](docs/EXTERNAL_TOOLS.md) — pinned refs, submodule vs pip rationale.
- [Repo-separation ADR](docs/ADR/ADR-001-repo-separation.md) / [External-dependency ADR](docs/ADR/ADR-002-external-dependencies.md)

## Environment Setup

Three documented modes — pick one. See each doc for exactly what's
verified vs unverified; don't assume a mode works beyond what's stated.

| Mode | Setup doc | Status |
|---|---|---|
| Devcontainer / Codespaces | [`.devcontainer/`](.devcontainer/) | Config fixed for Phase 1/2 paths (`external/suave/` not `trunk/`); **not** container-built/run in this session — unverified end-to-end. |
| Native Python venv | [`docs/environment-native.md`](docs/environment-native.md) | **Partially verified**: `pip install -r requirements.txt` + `pytest` confirmed 208/208 green this session (Python 3.11.15). SUAVE/pyCycle editable installs **not** tested. |
| Conda | [`environment-conda.yml`](environment-conda.yml) | **Unverified** — no conda available in this session; package list derived from the verified pip set, not run through `conda env create`. |

After cloning, always run first:
```bash
git submodule update --init --recursive   # or: scripts/bootstrap_submodules.sh
```
