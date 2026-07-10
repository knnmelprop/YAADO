# MELprop-IADE — External Tools Registry

Every external dependency `iade` relies on, how it's tracked, and who owns
keeping it current. See `docs/ADR/ADR-002-external-dependencies.md` for the
reasoning behind each entry. **Status as of 2026-07-10: SUAVE and pyCycle
submodules have been added and pinned** (human-approved separately from
the general Phase 2 go-ahead, per ADR-002's own requirement). AVL, XFOIL,
SU2, OpenVSP remain deferred, unchanged.

| Tool | Source URL | Pinned ref | Install mode | Update owner | Submodule vs pip-only |
|---|---|---|---|---|---|
| SUAVE | `https://github.com/suavecode/SUAVE` | tag `2.5.2` (`6554d2b3d1e7c2f1d4ba572aec99e1fd69d34a93`) — matched by version string against `droneEnv`'s previously-vendored `trunk/SUAVE`, not byte-verified (see ADR-002 caveat) | Submodule at `external/suave/`, `git submodule update --init`; no PyPI package used | [TBD-HUMAN] | Submodule only. No published package fits how `core/vehicle_factory.py` imports it (expects a local importable tree); pinning a submodule keeps the fork's exact source browsable/diffable. |
| pyCycle | `https://github.com/OpenMDAO/pyCycle` | tag `4.1.2` (`5a6fe40059211312f4b6d86d1a2bb1d913073ce8`) | **Both**: submodule at `external/pycycle/` (source browsing/diff/upstream inspection) **and** `requirements.txt` entry `om-pycycle==4.1.2` (actual runtime install via pip) | [TBD-HUMAN] | Both, deliberately, per locked human decision — these are two separate mechanisms and must not be conflated (submodule ≠ what gets installed at runtime; requirements.txt entry ≠ a way to inspect upstream source/diffs). |
| AVL | [TBD — deferred] | [TBD — deferred] | [TBD — deferred] | [TBD-HUMAN] | **DEFERRED** to Phase 2+ (human decision, `droneEnv` decision-log 2026-07-09). `knnmelprop/avl-mirror` exists as an intentionally-empty placeholder repo, to be populated after a license review. No pin exists yet — not guessed. |
| XFOIL | [TBD — deferred] | [TBD — deferred] | [TBD — deferred] | [TBD-HUMAN] | **DEFERRED**, same basis as AVL. `knnmelprop/xfoil-mirror` exists as an intentionally-empty placeholder repo. |
| SU2 | [TBD — deferred] | [TBD — deferred] | [TBD — deferred] | [TBD-HUMAN] | **DEFERRED** to Phase 2+. No mirror repo exists yet for SU2; not addressed by this run. |
| OpenVSP | [TBD — deferred] | [TBD — deferred] | [TBD — deferred] | [TBD-HUMAN] | **DEFERRED** to Phase 2+. No mirror repo exists yet for OpenVSP; not addressed by this run. |

## Notes

- **Never guess a pinned ref.** Every ref in this table above is either
  matched against a real, verifiable upstream tag (SUAVE, pyCycle — see
  ADR-002 for how each was resolved) or explicitly marked `[TBD — deferred]`
  with the human decision that put it there. No ref here was invented.
- **Update owner** columns are `[TBD-HUMAN]` — no project lead/reviewer
  role is defined anywhere in this repo's docs (consistent with
  `droneEnv`'s `docs/assumptions.md` A6: "No defined Project Lead/reviewer
  exists... agent never invents one"). A human needs to assign real owners
  before this table is considered complete.
- `git submodule update --init --recursive` is now a required post-clone
  step, since `external/suave` and `external/pycycle` are real gitlinks.
  Wired into `scripts/bootstrap_submodules.sh` (Phase 3) and the
  environment-mode docs.
- Neither submodule's Python package is installed into the environment by
  adding the submodule alone — SUAVE needs `external/suave/trunk` added to
  `PYTHONPATH` (or `pip install -e external/suave/trunk`, unverified — SUAVE
  2.5.2 targets an older Python/setuptools combination per its own
  `INSTALL`/`setup.py`, not tested in this run) and pyCycle's runtime
  install is the separate `om-pycycle==4.1.2` pip entry in
  `requirements.txt`, not the submodule.
