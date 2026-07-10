# MELprop-IADE — Native Python environment (Mode 2 of 3)

One of three documented environment modes (see `README.md`'s environment
matrix): devcontainer/Codespaces (Mode 1), **native venv (this doc)**, and
conda (`environment-conda.yml`, Mode 3).

## Setup

```bash
git clone https://github.com/knnmelprop/iade.git
cd iade
git submodule update --init --recursive   # pulls external/suave, external/pycycle

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

To use SUAVE itself (not just run the MELprop unit suite, which doesn't
require it):

```bash
cd external/suave/trunk
pip install -e .   # or: python setup.py develop
cd ../../..
```

## Running tests

```bash
python -m pytest tests/ -v --tb=short
```

## What's verified vs unverified (as of 2026-07-10)

- **Verified, this session:** `pip install pydantic>=2 pyyaml pytest scipy
  matplotlib` followed by `python -m pytest tests/` gives **208 passed, 0
  failed** on Python 3.11.15 in this exact repo checkout — this is the
  real command history from Phase 0/1/2 verification, not a claim made
  without running it. `om-pycycle==4.1.2` was **not** installed/tested in
  this session (the unit suite doesn't require it).
- **Unverified:** `pip install -e external/suave/trunk` (or `setup.py develop`).
  SUAVE 2.5.2's own `INSTALL`/`setup.py` targets an older Python/setuptools
  combination than this environment's Python 3.11 — it may need `numpy`/
  `scipy` version pins from `.devcontainer/requirements.txt` (which
  constrains `numpy>=1.21.6,<1.25.0`, `scipy>=1.7.3,<1.11.0`) rather than
  the unpinned versions `requirements.txt` installs. Do not assume this
  works until someone actually runs it and reports back.
- **Unverified:** `pip install -e external/pycycle` / `om-pycycle==4.1.2`
  install and any pyCycle-backed ramjet-cycle run. Not attempted this
  session.
- **Unverified:** Python version compatibility beyond 3.11 (e.g., 3.9, to
  match `.devcontainer/devcontainer.json`'s pinned interpreter).

## Known constraint

If you need SUAVE actually importable (not just the guarded-import unit
suite, which runs fine without it), you may need a **separate virtualenv**
pinned to SUAVE 2.5.2's expected numpy/scipy range
(`.devcontainer/requirements.txt` has the known-working pins from the old
SUAVE-tutorial devcontainer) rather than this repo's root
`requirements.txt`, which was written against MELprop's own code and has
not been cross-checked for SUAVE 2.5.2 compatibility. This conflict is
flagged, not resolved, in this pass — a real SUAVE-backed run is needed to
confirm whether the two dependency sets are actually compatible in one
environment.
