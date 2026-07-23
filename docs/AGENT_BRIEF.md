# AGENT BRIEF — RamP / IADE (current as of 2026-07-23)

Compact state for agents. Full detail: `docs/HANDOFF_2026-07-23.md`.
Branch: `geometry/step-station-sweep` (pushed, clean).

## Goal
Determine RamP static stability sign supersonically (static margin, calibers)
via SU2 CFD. Barrowman retired >Ma 0.7 as invalid for this vehicle.

## DO NOT REDO — these are already done
| Claim you may be told | Reality |
|---|---|
| "SU2 was never built" | **FALSE.** Built + validated: `~/.local/su2-8.5.0/bin/` (6 binaries). Single-core (`-Dwith-mpi=disabled`). |
| "Sweep tool needs writing" | **FALSE.** `analyses/geometry/cad_station_sweep.py` (633 ln) + tests exist. |
| "Solid identity unknown" | Measured. But the *question* is mis-framed — see Blocker. |

## Established facts (measured, 2 independent runs agree byte-identical)
- STEP `cad/ramPcfdSimplified.step`: 2 solids, mm, X=longitudinal, total 4355.02mm.
- vol_1: x=30.13–1071.51, max r 105.33mm, **solid** (1 loop everywhere).
- vol_2: x=159.81–4385.15, max r 296.5mm.
- **vol_1 nests INSIDE vol_2** (vol_1 outer r 105.33 ≈ vol_2 bore r 104.4–108.5).
- Internal bore: x≈160→2400mm, r 108→57mm. **Closes x=2400–2500.**
- Barrel: x=2500→3600, r_eq 63.50mm, outer r 65.00mm (constant to 10 sig figs).
- Fins: begin **x=3600–3800**, tips r=296.5mm by x=4000. 1 loop = blades, no holes.
- SU2 RANS SA **and** SST execute cleanly (300 iters, exit 0, no NaN) — but only
  as a **code-path check** on an inviscid mesh at **subsonic** M=0.15.

## THE BLOCKER (human decision, not a measurement)
`gmsh/marker_zones.yaml` is unfilled **on purpose**. Its `.template` asks
"which solid is ramjet vs booster" — **that question is invalid**: vol_1 is
inside vol_2, and vol_2 spans 4225 of 4355mm. It is centerbody-inside-airframe,
not stage-1 vs stage-2.

**Do not answer it as posed.** A wrong marker assignment does not crash — it
silently flips the static-margin sign, i.e. the entire deliverable. Marker
X-ranges must derive from the measured transitions above. Stage-derived marker
*names* (`booster_wall` etc.) may themselves need renaming to geometric ones.

## Unresolved — report, never auto-fix
- Barrel measures **130.0mm** dia vs `vehicle_config.yaml` `body.diameter_m: 0.200` (**70mm gap**, field marked drawing-verified).
- Fin tip-to-tip **~590mm** vs config 550mm / 639mm — matches neither.
- 14 small circular members (r≈4.24mm) ringing x=2100mm at duct wall radius. Uninterpreted.
- **Never modify `vehicles/ramjet_rocket/vehicle_config.yaml`.** Report only.

## Next actions, in order
1. **(HUMAN)** Define marker X-ranges → write `marker_zones.yaml`. Proposal in HANDOFF §5.
2. `01_classify_and_mesh.py --level coarse …` — **full-mesh path has NEVER run**; treat first invocation as a crash test.
3. Supersonic RANS smoke test — **never ran** (agent killed by usage limit). Use `runs/su2_rans_check/` config + `MACH_NUMBER=2.5`, `ENTROPY_FIX_COEFF=0.1`, `MUSCL_FLOW=YES`, `SLOPE_LIMITER_FLOW=VENKATAKRISHNAN`, `CFL_NUMBER=1.0`, `CFL_ADAPT=YES`, `ITER=50`.
4. SU2 turbulent validation meshes are **absent** from `TestCases/rans/*` (configs only). Fetch from `su2code/TestCases` before trusting RANS physics.

## Environment gotchas (hard-won)
- `cmd | tee log | tail -N` returns **tail's** exit code. Use `set -o pipefail`. A build once reported "exit 0" while failing.
- No `python`, only `python3` (Homebrew 3.14). **pytest NOT installed** anywhere local — "265 passed" came from another env. Verify by direct assertion and say so.
- PEP 668: `pip install --user` blocked. Use venvs: `analyses/geometry/.venv-geom`, case's `.venv-gmsh`.
- Homebrew `gmsh` CLI has **no Python bindings**. PyPI `gmsh==4.15.1` needed separately.
- **STEP is gitignored (14MB).** Cloud/remote sessions cannot see it — real-geometry work must run locally. This is why the tool sat synthetic-only for a session.
- `.gitignore` globally ignores `*.cfg`, `*.su2`. Tracked configs are `*.cfg.template`.
- **Single working tree.** Parallel agents must NOT `git checkout` — it yanks the tree from under others. Confine parallel work to `runs/` (gitignored).

## Cost model (corrected — old docs are wrong by ~10x)
Station sweep with loop topology: **~35–73 s/station**, NOT the ~8.4 s/station in
`status.md` §4b (that timed slicing without the topology walk). STEP merge alone
30–224 s. **Full 220-station sweep ≈ 4.5 h, not ~31 min.** Use targeted ranges.

## Rules
- Never fabricate safety-critical values (CG, mass, thrust). Sweep/bound instead.
- Report MATCH/MISMATCH against config; never auto-correct.
- Don't merge/rebase/delete branches unless asked — past sessions collided that way.
