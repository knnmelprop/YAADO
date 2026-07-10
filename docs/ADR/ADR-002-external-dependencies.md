# ADR-002 — External dependency model (SUAVE, pyCycle, AVL/XFOIL/SU2/OpenVSP)

- **Status:** Accepted and executed (2026-07-10) — SUAVE and pyCycle
  submodules added at the pinned commits below, human-approved separately
  from the general Phase 2 go-ahead as this ADR required. AVL/XFOIL/SU2/
  OpenVSP remain deferred, unchanged from the original proposal.
- **Date:** 2026-07-10
- **Deciders:** KNN MELprop human review (decisions logged 2026-07-09/10 in
  `knnmelprop/droneEnv`'s `docs/decision-log.md`), agent (planning + ref
  verification)
- **Related:** `docs/ADR/ADR-001-repo-separation.md`,
  `docs/EXTERNAL_TOOLS.md`, `docs/migration-plan-phase1.md`

## Context

Phase 1 extracted `knnmelprop/iade` from `knnmelprop/droneEnv` with all
embedded upstream source (`SUAVE/`, `trunk/`, `Tutorials*`, `ide/`,
`templates/`, `regression/`) dropped from history. `knnmelprop/iade` today
has **no SUAVE, no pyCycle, no AVL/XFOIL/SU2/OpenVSP** — `core/`'s guarded
imports report them unavailable, exactly as designed, and the 208-test
suite passes without any of them installed.

Two pinned refs were decided by human review before this ADR (see
`droneEnv`'s decision-log, 2026-07-09):
- SUAVE: pin to whatever the previously-embedded `trunk/` corresponded to,
  no version bump.
- pyCycle: pin to tag `4.1.2`, `om-pycycle==4.1.2` on PyPI.

Neither ref was handed over as a literal SHA — this ADR resolves them
against real upstream tags rather than guessing:

- `trunk/SUAVE/version.py` and `trunk/setup.py` in `droneEnv` both read
  `version = '2.5.2'` (a generated file + the source of truth in
  `setup.py`'s `version` variable, consistent with each other).
- `git ls-remote --tags https://github.com/suavecode/SUAVE.git` confirms a
  tag literally named `2.5.2` (not `v2.5.2`) at commit
  `6554d2b3d1e7c2f1d4ba572aec99e1fd69d34a93`. Neighboring tags `2.5.0`/
  `2.5.1` are different commits, so this is unambiguous.
- **Caveat:** this match is by version string, not a byte-for-byte tree
  diff against the tag. `droneEnv`'s fork may carry local patches on top of
  the `2.5.2` release that this ADR has not verified. If Phase 2 execution
  finds the pinned tag's tree differs meaningfully from what
  `droneEnv`'s history had, stop and report rather than silently
  reconciling — that is new information, not something this ADR decided.
- `git ls-remote --tags https://github.com/OpenMDAO/pyCycle.git` confirms
  tag `4.1.2` at commit `5a6fe40059211312f4b6d86d1a2bb1d913073ce8`.

AVL, XFOIL, SU2, and OpenVSP pins remain **explicitly deferred** (human
decision, `droneEnv` decision-log 2026-07-09) — `knnmelprop/avl-mirror` and
`knnmelprop/xfoil-mirror` exist as intentionally-empty placeholder repos,
to be populated after a license review, in a future phase. This ADR does
not attempt to resolve those refs.

## Decision

1. **pyCycle** gets two independent mechanisms, per the locked decision —
   these must not be conflated:
   - `external/pycycle/` as a git submodule pinned to
     `https://github.com/OpenMDAO/pyCycle` @ tag `4.1.2`
     (`5a6fe40059211312f4b6d86d1a2bb1d913073ce8`), for source browsing/diff/
     upstream inspection.
   - `om-pycycle==4.1.2` as a `requirements.txt` runtime entry (installed
     via pip from PyPI), for actually running ramjet-cycle analyses.
2. **SUAVE** moves to `external/suave/` as a git submodule pinned to
   `https://github.com/suavecode/SUAVE` @ tag `2.5.2`
   (`6554d2b3d1e7c2f1d4ba572aec99e1fd69d34a93`). SUAVE is **not** a runtime
   `requirements.txt` pip entry — it has no PyPI package matching this
   fork's usage pattern; `core/vehicle_factory.py`'s guarded import expects
   a local, importable SUAVE tree, which the submodule at `external/suave/`
   provides once initialized (`git submodule update --init`). This is the
   "SUAVE becomes an external dependency identity-wise" change: `iade`'s
   own identity, README, and CLAUDE.md no longer describe the repo *as* a
   SUAVE fork — SUAVE is a submodule dependency like any other. (Actually
   updating that framing language in `README.md`/`CLAUDE.md` is **not**
   done by this ADR — flagged as a follow-up in Consequences.)
3. AVL, XFOIL, SU2, OpenVSP: **no submodule, no pin, no requirements entry**
   in this phase. `docs/EXTERNAL_TOOLS.md` carries an explicit "DEFERRED"
   row for each so the gap is visible rather than silently absent.
4. `.gitmodules` and the `external/` submodule adds are **drafted only** in
   this ADR / `docs/EXTERNAL_TOOLS.md`. Actually running
   `git submodule add` (which fetches ~2 external repos over the network
   and mutates the working tree + `.gitmodules`) is held for a separate,
   explicit approval — consistent with how Phase 1's `filter-repo` and the
   push to `knnmelprop/iade` were each gated individually rather than
   inferred from a general "continue."

## Consequences

- Until submodules are actually added and initialized, `knnmelprop/iade`
  still cannot run SUAVE-dependent or pyCycle-dependent analyses — the
  208-test unit suite is unaffected (it never depended on either), but
  anything invoking `VehicleFactory.build()` for a SUAVE-backed vehicle, or
  a pyCycle-based ramjet cycle, will continue to raise the same guarded
  "unavailable" errors it does today.
- `external/suave/` at `2.5.2` may not be identical to what was actually
  vendored in `droneEnv`'s `trunk/` (see caveat above) — this needs a
  diff-check as part of Phase 2 execution, not assumed clean.
- README.md/CLAUDE.md still frame the project as "a fork of SUAVE" in
  prose (inherited verbatim from `droneEnv` through the Phase 1
  extraction). This ADR does not fix that language — it's a documentation
  follow-up, tracked here so it isn't lost, not executed now.
- `avl-mirror`/`xfoil-mirror` stay empty; no code in `iade` can reference
  them as submodules yet since there is nothing at a pinned ref to point
  to.

## Open questions carried forward (not decided here)

- Byte-level verification that `suavecode/SUAVE@2.5.2` matches what
  `droneEnv` actually vendored.
- Timeline/owner for the AVL/XFOIL/SU2/OpenVSP license review that gates
  populating the mirror repos.
- Whether/when to update `README.md`/`CLAUDE.md` framing language now that
  SUAVE is a submodule dependency rather than the repo's identity.
