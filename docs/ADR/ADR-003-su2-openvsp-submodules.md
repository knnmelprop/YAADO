# ADR-003 — Add SU2 and OpenVSP as pinned submodules

- **Status:** Accepted and executed (2026-07-10)
- **Deciders:** Human, explicit instruction: *"I want SU2 and OpenVSP
  modules installed for now in the repo."*
- **Related:** `docs/ADR/ADR-002-external-dependencies.md`,
  `docs/EXTERNAL_TOOLS.md`

## Context

ADR-002 deferred AVL, XFOIL, SU2, and OpenVSP as a group, per an earlier
human decision. Mid-session, a pasted "decision-ready brief" proposed
integrating SU2 and OpenVSP immediately with specific version claims
(`v8.5.0`, `3.51.0`) and license verdicts (LGPL-2.1, NASA-1.3). That brief
was **not acted on directly** — its claims were unverified and it
contradicted a locked decision (see `agents/memory.md`'s Phase 1-5 entry
and `docs/decision-log.md`'s Phase 5 blockers list, item 4).

The human then gave an explicit, unambiguous instruction to install SU2
and OpenVSP now. This ADR documents that as the actual authorization, and
independently re-verifies every factual claim the earlier brief made
before acting on it — the brief's content is not treated as evidence,
only as a pointer to go check.

### Independent verification (this session, not taken from the brief)

- `git ls-remote --tags https://github.com/su2code/SU2.git`, sorted:
  latest tag is genuinely `v8.5.0` → commit
  `12eb826f049ef7f67df974dfcb44cf36ee07c0f8`.
- `git ls-remote --tags https://github.com/OpenVSP/OpenVSP.git`, filtered
  to numeric `OpenVSP_x.y.z` tags, sorted: latest is genuinely
  `OpenVSP_3.51.0` → commit `458d26ad88cf0167dcb3d7c70846e771cbf0e841`.
- SU2 license: fetched `LICENSE.md` from the `v8.5.0` tag directly —
  primary license is **LGPL-2.1**, consistent with a public submodule
  reference (also notes some vendored components under other licenses:
  CGNS zlib/libpng, ParMETIS restricted-non-commercial, TecIO proprietary,
  CLI11 BSD-3 — none of that changes the submodule-reference risk profile
  since no code is copied into `iade`, only a pinned pointer).
- OpenVSP license: fetched `LICENSE` from the `OpenVSP_3.51.0` tag
  directly — **NASA Open Source Agreement (NOSA) v1.3**.
- OpenVSP PyPI package: checked `https://pypi.org/pypi/openvsp/json` —
  **404, no such package**. The brief's claim of a `pip install openvsp`
  wheel is **not substantiated**; not added to `requirements.txt`.
  Submodule-only for OpenVSP, same as SUAVE.

## Decision

1. Add `external/su2/` as a submodule pinned to `su2code/SU2` @ tag
   `v8.5.0` (`12eb826f04...`).
2. Add `external/openvsp/` as a submodule pinned to `OpenVSP/OpenVSP` @
   tag `OpenVSP_3.51.0` (`458d26ad88...`).
3. No `requirements.txt` entries added for either — no verified PyPI
   package for OpenVSP, and SU2 is not typically pip-installed (built via
   CMake); running either requires building from the submodule or
   installing a system/binary distribution, neither attempted or verified
   this session.
4. AVL and XFOIL remain deferred, unchanged — this instruction named SU2
   and OpenVSP specifically, not "everything previously deferred." Their
   mirror repos (`avl-mirror`, `xfoil-mirror`) stay empty pending the
   license review already on record (no official git repo for either,
   redistribution-risk concerns noted in the untrusted brief were at
   least directionally plausible but not independently re-verified here
   since they weren't part of this instruction).

## Consequences

- `external/su2` (257 MB once its own recursive sub-submodules — CoolProp,
  eigen, meson, MLPCpp, Mutationpp, etc. — are initialized) and
  `external/openvsp` (412 MB) checked out on disk add real weight to a
  full clone-with-submodules — doesn't affect `iade`'s own `.git` size
  (submodules are separate repos), but is worth knowing before scripting
  CI that does a full recursive checkout.
- Neither tool is runtime-installed or built — this ADR only adds source
  references for browsing/diffing/future build work. `docs/EXTERNAL_TOOLS.md`
  is updated accordingly; do not assume SU2/OpenVSP are actually usable
  from Python yet.
- `scripts/bootstrap_submodules.sh` updated to check both new pins.
