# MELprop-IADE — External Tools Registry

Every external dependency `iade` relies on, how it's tracked, and who owns
keeping it current. See `docs/ADR/ADR-002-external-dependencies.md` for the
reasoning behind each entry. **Status as of 2026-07-10: none of the
submodules below have actually been added to the working tree yet** — this
table is the Phase 2 plan, pending a separate explicit approval to run
`git submodule add`.

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
- Once submodules are actually added, `git submodule update --init
  --recursive` becomes a required post-clone step — this needs to be added
  to `scripts/bootstrap_submodules.sh` (Phase 3 deliverable, not yet
  written) and documented in the environment-mode docs.
