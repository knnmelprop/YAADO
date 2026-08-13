# Working context — SU2 ramP stability case

Directory-scoped instructions for work inside this case. The root
`/CLAUDE.md` still applies (SI units, type hints, Google docstrings, module
headers, run pytest after changes). This file adds case specifics.

## What this case is
Steady compressible **supersonic RANS**, external-only, **capped inlet**, for
`ramP + interstage + booster`. Deliverable = the static-stability **sign**
(margin in calibers about the CG), as an independent cross-check of
DATCOM-class + Ackeret. Mach 2.5, AoA sweep {0,4,8}°, two grid levels, SA+SST.

## Hard rules
1. **Never fabricate safety-critical inputs** — CG (`REF_ORIGIN_MOMENT_X`),
   REF_LENGTH, REF_AREA. If unknown, **sweep** and report the neutral point /
   a margin band. A wrong CG flips the stability sign.
2. Non-safety-critical unknowns (freestream at design altitude, etc.) → use the
   documented PROVISIONAL default in the cfg template and label it `ASSUMPTION`.
3. **Interstage is mandatory geometry**, not a defeaturing detail.
4. Inlet is **capped** (wall) — no internal duct flow in a stability case.
5. Result is PROVISIONAL until GCI (grid convergence) **and** SA/SST agreement.
6. Data artifacts (STEP/mesh/results) are **gitignored** — commit code, configs,
   docs, checklists only. Live `.cfg` is generated into gitignored dirs.
7. AVL is invalid here (Ma>0.6) — this case exists precisely because Barrowman
   is retired above Ma 0.7. Cross-check against DATCOM-class + Ackeret, not AVL.

## Where things live
`cfg/` template + markers · `post/postprocess_coeffs.py` · `checklists/` gates ·
`cad/geom/mesh/run/` gitignored data. See `README.md` for the full pipeline.

## Optional subagents (Opus coordinator only)
`case-architect` (repo map, plan-only), `mesh-reviewer` (watertight/markers/y⁺
GO-NO-GO), `su2-config-auditor` (BC/numerics/convergence review). Delegate only
high-volume exploration; do trivial edits yourself.
