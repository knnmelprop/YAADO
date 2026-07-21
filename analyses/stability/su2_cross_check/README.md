# SU2 RANS-SST stability cross-check — BLOCKED_BY_ENVIRONMENT (2026-07-11)

Stage 1 Dispatch B (the authoritative CFD arbiter of the Ma 2.5 static-stability
sign conflict) was **not run** in the 2026-07-11 cloud session:

- No `SU2_CFD` binary is installed in the sandbox.
- The `external/su2` submodule is **not checked out** (`git submodule status`
  shows a leading `-`), and building SU2 from source (C++/meson) is not
  available/feasible in this ephemeral, network-allowlisted cloud container.

**Why it matters:** the two analytical methods (DATCOM-class, Ackeret) both give
large positive static margin (+5…+11 cal) at Ma 2.5, but this **conflicts** with
the Teltik 2024 CFD (−2.75 cal, unstable). SU2 is the tie-breaker; without it the
CDR stability gate is a 2-vs-1 split and **NOT satisfied**. See
`docs/decision-log.md` (Stage 1 orchestrator addendum).

**Next human action:** run this case locally where SU2 can be built:
RANS-SST, y+<1 near-wall mesh, coarse/fine grid pair (grid-convergence),
alpha-sweep {0, 4, 8}°, Mach 2.5 first (add a boost-phase Mach point only if
budget allows). Compare the CFD CP / static-margin **sign** against the
analytical +margin and the Teltik −2.75 cal. Write results here.
