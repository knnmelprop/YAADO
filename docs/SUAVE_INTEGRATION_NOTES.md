# SUAVE 2.5.2 Integration Notes

**Date:** 2026-08-31
**Scope:** `external/suave/trunk` (git submodule, pinned tag `2.5.2`), installed into an
isolated venv (`/tmp/.../scratchpad/suave-venv`, outside the repo and outside the
project's `uv` environment). Nothing in `external/suave` or the project's `pyproject.toml`
/ `uv.lock` was modified for this exploration.

## (a) Summary

SUAVE 2.5.2 **can** be installed and imported alongside a modern (2026-era) Python/numpy/scipy
stack, but not cleanly with a plain `pip install -e`. Three separate incompatibilities between
SUAVE's ~2022-era code and today's Python 3.11 / scipy have to be worked around at **runtime**
(not by editing SUAVE's source, which is a pinned submodule):

1. `pip install -e` fails outright under default PEP 517 build isolation, because SUAVE's
   `setup.py` does an eager `import numpy` *at build-requirement-gathering time*, and the
   isolated build env pip creates doesn't have numpy in it (even though the target venv does).
   Fix: `pip install --no-build-isolation -e external/suave/trunk`, after numpy/scipy/etc are
   already installed in the venv.
2. SUAVE vendors an old copy of `pint` (its `SUAVE/Plugins/pint`) that does
   `from collections import MutableMapping` — an alias removed from `collections` in
   Python 3.10. Every Python available in this environment (3.10, 3.11, 3.12, 3.13) postdates
   the removal, so there is no "just use an older Python" escape hatch here.
3. SUAVE's `Components/Energy` package eagerly imports two now-removed SciPy symbols at
   import time: `scipy.integrate.cumtrapz` (renamed `cumulative_trapezoid` in SciPy ≥1.14) and
   `scipy.misc.derivative` (removed in SciPy ≥1.12, no direct drop-in — needed a hand-written
   central-difference shim).

None of these are one-off — they sit on SUAVE's *default import chain* (`import SUAVE` alone
triggers all three), so they can't be avoided by only using part of the package. All three
were worked around with **runtime monkeypatches applied before `import SUAVE`** (see §c) — no
submodule files were touched. With those three shims in place, `import SUAVE` succeeds and the
VehicleFactory API surface matches what YAADO's translator expects (see §d). The main residual
risk is that these shims are exploration-grade duct tape, not a sanctioned dependency story;
see §e for the recommendation.

## (b) SUAVE requirements vs. current YAADO env

SUAVE 2.5.2's `setup.py` (`import_tests()` / `requires=`) declares only unpinned deps:
`numpy`, `scipy`, `sklearn` (scikit-learn), `matplotlib`, `plotly`, Python `>=3.6`. It carries
no `requirements.txt` / pinned versions — it was written against whatever was current in
~2021-2022, and its code (not its declared metadata) is what actually breaks.

| Package | SUAVE declares | YAADO env has (`uv run python`) | Conflict? |
|---|---|---|---|
| Python | `>=3.6` | 3.11.15 | Not in metadata, but see below — `collections.MutableMapping` was removed in 3.10, so SUAVE's vendored `pint` is broken on **every** Python this box has (3.10/3.11/3.12/3.13). |
| numpy | unpinned | 2.4.6 | No bare `np.float`/`np.int`/etc. on SUAVE's default import path (those only appear in the `Noise` submodule, 11 occurrences across 6 files — not imported by `import SUAVE` itself). Not a blocker for import, but a landmine for anyone who later imports `SUAVE.Methods.Noise.*`. |
| scipy | unpinned | 1.17.1 | **Yes** — `scipy.integrate.cumtrapz` and `scipy.misc.derivative` are both gone in 1.17.1; both are on SUAVE's eager import chain (via `Storages/Batteries/Constant_Mass/Lithium_Ion.py` and `Distributors/Cryogenic_Lead.py`). |
| matplotlib | unpinned | 3.11.1 | No import-time failures observed. |
| scikit-learn | unpinned | not in YAADO env; installed 1.9.0 fresh in scratch venv | No import-time failures observed. |
| plotly | unpinned | not in YAADO env; installed 7.0.0 fresh in scratch venv | No import-time failures observed. |
| pint | SUAVE vendors its own old copy (`SUAVE/Plugins/pint`) | n/a (not a YAADO dep) | **Yes** — vendored `pint` uses `collections.MutableMapping`, removed in Python 3.10+. |

## (c) Exact installation walkthrough

All commands run inside the isolated venv `.../scratchpad/suave-venv`, never touching the
project's `uv` env.

```bash
python3 -m venv .../scratchpad/suave-venv
.../suave-venv/bin/pip install --upgrade pip
.../suave-venv/bin/pip install numpy scipy matplotlib scikit-learn plotly   # pre-install deps

# Attempt 1 — plain editable install
.../suave-venv/bin/pip install -e external/suave/trunk
```

Attempt 1 fails during "Getting requirements to build editable":

```
ModuleNotFoundError: No module named 'numpy'
...
File "<string>", line 202, in import_tests
ImportError: numpy is required for this package
```

Root cause: pip's default PEP 517 flow builds in an *isolated* temp environment that only has
setuptools in it; SUAVE's `setup.py` does `import numpy` as part of `import_tests()`, called
from `setup()`'s build-requirement-gathering step, which runs in that isolated env — not the
target venv, even though numpy is already installed there.

```bash
# Attempt 2 — disable build isolation (numpy et al. already present in the target venv)
.../suave-venv/bin/pip install --no-build-isolation -e external/suave/trunk
```

This succeeds: `Successfully installed SUAVE-2.5.2`.

```bash
.../suave-venv/bin/python -c "import SUAVE"
```

Fails:

```
File ".../SUAVE/Plugins/pint/compat.py", line 16, in <module>
    from collections import MutableMapping
ImportError: cannot import name 'MutableMapping' from 'collections'
```

Workaround — monkeypatch `collections` **before** importing SUAVE (no submodule file edited):

```python
import collections, collections.abc
collections.MutableMapping = collections.abc.MutableMapping
collections.Mapping = collections.abc.Mapping
collections.Iterable = collections.abc.Iterable
collections.Callable = collections.abc.Callable
```

Retrying `import SUAVE` then fails further down the import chain:

```
File ".../Batteries/Constant_Mass/Lithium_Ion.py", line 19, in <module>
    from scipy.integrate import cumtrapz
ImportError: cannot import name 'cumtrapz' from 'scipy.integrate'
```

Workaround (alias, since `cumulative_trapezoid` is a drop-in replacement):

```python
import scipy.integrate
scipy.integrate.cumtrapz = scipy.integrate.cumulative_trapezoid
```

Retrying again hits a third, non-trivial removal:

```
File ".../Distributors/Cryogenic_Lead.py", line 18, in <module>
    from scipy.misc import derivative
ImportError: cannot import name 'derivative' from 'scipy.misc'
```

`scipy.misc.derivative` has no direct 1:1 replacement in modern SciPy (`scipy.differentiate`
exists but has a different call signature/return type). For this exploration a minimal
central-difference stand-in was used, sufficient only to satisfy the import — **not** validated
for numerical correctness against anything that actually calls it at runtime:

```python
import scipy.misc
def _derivative(func, x0, dx=1.0, n=1, args=(), order=3):
    return (func(x0 + dx, *args) - func(x0 - dx, *args)) / (2 * dx)
scipy.misc.derivative = _derivative
```

With all three shims applied ahead of `import SUAVE`, the import succeeds cleanly
(`SUAVE.__version__ == '2.5.2'`), plus one harmless `DeprecationWarning` from
`pkg_resources` used inside the vendored `pint`.

**Scope check on the two extra scipy breaks:** `cumtrapz` appears in 4 files and
`scipy.misc.derivative` in 1 file across all of `SUAVE/`. Only the two shown above sit on the
*eager* `import SUAVE` chain; the rest are only hit if/when a caller reaches into those
specific modules. There may be **further** deprecated-API landmines in modules YAADO doesn't
currently touch (Noise fidelity models use bare `np.float`/`np.int`, 11 occurrences in 6 files)
— those were not exercised because nothing on the tested import/build path reaches them.

## (d) VehicleFactory API validation (Issue #29)

Probed directly against the real, installed SUAVE 2.5.2 (with the three shims from §c applied):

| Expected by translator | Result |
|---|---|
| `SUAVE.Vehicle()` constructible, has `.tag` | Confirmed — `.tag` defaults to `'vehicle'` |
| `Vehicle.append_component(component)` | Confirmed — signature is exactly `(component)` |
| `SUAVE.Components.Energy.Networks.Turbojet_Super` | Confirmed — exists |
| `SUAVE.Components.Energy.Networks.Ramjet` | Confirmed — exists |
| `SUAVE.Components.Energy.Networks.Liquid_Rocket` | Confirmed — exists |
| `SUAVE.Components.Energy.Networks.Scramjet` | Confirmed — exists |
| Solid-fuel network (for `SolidMotor`) | **Confirmed absent** — no `Solid_Rocket` (or similarly named) network in `SUAVE.Components.Energy.Networks`. This matches the translator's documented `NotImplementedError` for `SolidMotor` — there is genuinely no SUAVE 2.5.2 network to map it to. |
| `SUAVE.Components.Wings.Wing()` has `.tag`, `.taper`, `.aspect_ratio`, `.dihedral`, `.vertical` | Confirmed — all present with sane defaults (`taper=0.0`, `aspect_ratio=0.0`, `dihedral=0.0`, `vertical=False`) |
| `Wing.sweeps.quarter_chord` | Confirmed — present, default `0.0` |
| `Wing.sweeps.leading_edge` | Confirmed — present, default `None` (not `0.0` — worth noting if the translator ever reads it before writing it) |
| `Wing.spans.projected` | Confirmed — present, default `0.0` |

**No mismatches found.** Everything the translator (both the version currently on this branch
and the corrected version on `feature/vehicle-factory-composition`, commit
`b56113723c6720568edb91950285f8851c84b010`, "fix(foundation): correct SUAVE network names
against real SUAVE 2.5.2 source (#29)") relies on is present with the expected shape in the
real package.

Full list of `SUAVE.Components.Energy.Networks` members for reference: `Battery_Cell_Cycler`,
`Battery_Ducted_Fan`, `Battery_Propeller`, `Ducted_Fan`, `Internal_Combustion_Propeller`,
`Internal_Combustion_Propeller_Constant_Speed`, `Lift_Cruise`, `Liquid_Rocket`, `Network`,
`Propulsor_Surrogate`, `PyCycle`, `Ramjet`, `Scramjet`, `Serial_Hybrid_Ducted_Fan`, `Solar`,
`Solar_Low_Fidelity`, `Turboelectric_HTS_Ducted_Fan`, `Turbofan`, `Turbojet_Super`.

### Gated integration test (Issue #29), run against real SUAVE

`YAADO_Core/tests/Foundation/test_vehicle_factory.py` lives on
`feature/vehicle-factory-composition` (not on this branch; repo branch was left untouched —
inspected via `git archive feature/vehicle-factory-composition` into the scratchpad, never
checked out in the repo). It has `pytest.importorskip("SUAVE")`-gated real-SUAVE test alongside
two fake-SUAVE unit tests. Running all three against the isolated venv (shims pre-applied,
plus `pyyaml` installed as an extra dependency of `vehicle_base.py`):

```
YAADO_Core/tests/Foundation/test_vehicle_factory.py::test_build_appends_wing_and_propulsion_with_injected_suave PASSED
YAADO_Core/tests/Foundation/test_vehicle_factory.py::test_build_without_suave_raises_runtime_error PASSED
YAADO_Core/tests/Foundation/test_vehicle_factory.py::test_build_with_real_suave_produces_real_vehicle PASSED
3 passed, 1 warning in 2.02s
```

The one warning is the same harmless `pkg_resources` `DeprecationWarning` from vendored `pint`.

## (e) Recommendation

1. **Keep SUAVE fully out of the main `uv` environment.** It must live in its own isolated
   Python environment (dedicated venv, or a container/devcontainer with SUAVE baked in) — never
   `uv add`/`uv sync`'d into `pyproject.toml`. Its unpinned, ~2022-vintage transitive deps
   (numpy/scipy/scikit-learn/matplotlib/plotly) are exactly the kind of thing that will keep
   fighting with a modern, actively-updated core dependency set like YAADO's.
2. **`pip install -e` is realistic, but not "clean."** It needs `--no-build-isolation`, and
   the resulting import still needs the three runtime shims from §c applied *before* `import
   SUAVE` anywhere in the process (e.g. in a small `suave_compat.py` shim module imported first,
   or a `sitecustomize.py` in the SUAVE venv) — SUAVE's own source cannot be edited since it's a
   pinned submodule. This is a good candidate for a tiny, well-commented, tested
   compatibility shim module living in YAADO (e.g. `YAADO_Core/modules/suave_compat.py`) that
   `VehicleFactory`'s real (non-injected) path imports before `import SUAVE` — turning this
   exploration's monkeypatches into a maintained, documented piece of the codebase rather than
   tribal knowledge.
3. **CI implication:** a CI job that wants to run the real-SUAVE gated test
   (`test_build_with_real_suave_produces_real_vehicle`) needs (a) the SUAVE submodule checked
   out, (b) a separate venv/step with `--no-build-isolation` install plus the compat shim
   pre-imported, and (c) that venv's Python used only for that job — it should not be the same
   interpreter/venv running the rest of the `uv run pytest` suite. Until that shim module and a
   dedicated CI job exist, `test_build_with_real_suave_produces_real_vehicle` will keep
   `SKIPPED`'ing in the normal `uv run pytest` flow (no `SUAVE` importable there) — which is the
   correct, safe default; don't try to make it importable in the shared project env.
3. **Two version pins worth deciding on deliberately, not by accident:** the compat shim only
   works because `scipy.integrate.cumulative_trapezoid` is a genuine drop-in for `cumtrapz`,
   and because the hand-rolled central-difference `derivative` shim was never exercised against
   real solver code in this exploration. Anyone building on this should (a) pin an exact SUAVE
   venv's scipy/numpy versions rather than "whatever's latest," and (b) audit which SUAVE code
   paths YAADO's translator/solvers actually call at runtime (beyond just importing the package)
   before trusting the `derivative` shim's numerics — it was written only to unblock `import
   SUAVE`, not validated for correctness.
4. **Known remaining landmine, not yet hit:** `SUAVE.Methods.Noise.*` uses bare `np.float`
   /`np.int` (11 occurrences, 6 files) which numpy ≥1.24 removed entirely (not just
   deprecated). These modules are not on the default `import SUAVE` path and were not exercised
   here; if YAADO ever needs SUAVE's noise fidelity models, expect another round of this same
   exercise.
