# AGENT BRIEF — RamP / IADE (current as of 2026-07-23, post marker_zones.yaml)

Compact state for agents. Full detail: `docs/HANDOFF_2026-07-23.md`.

## ⚠️ TWO BRANCHES — read this before you start

This work stream is currently **split across two diverged branches**, deliberately
NOT merged (standing repo rule: never merge/rebase/delete branches unless a human
asks — past sessions collided that way). A fresh agent needs to know about BOTH:

- **`geometry/step-station-sweep`** (pushed, clean, HEAD `b4e75c1` as of this
  entry) — the geometry tool, the real-STEP measurements, and all the docs
  you're reading now (`docs/geometry/status.md`, `docs/HANDOFF_2026-07-23.md`,
  this file, `docs/decision-log.md`).
- **`claude/su2-local-stability-run`** (pushed, clean, HEAD `1ab4850`) — the SU2
  CFD case itself (`analyses/stability/su2_cross_check/case_ramp_stability/`),
  including **`gmsh/marker_zones.yaml`, now filled in** (commit `1ab4850`,
  2026-07-23) using the geometry findings below. This branch does NOT have the
  geometry-tool commits or these docs on it — only the filled marker file.
- **Before meshing or running SU2, check out `claude/su2-local-stability-run`**,
  not this branch — that's where `marker_zones.yaml` and the CFD case configs
  live. Whether/when to merge the two branches is a human call, not yet made.

## Goal
Determine RamP static stability sign supersonically (static margin, calibers)
via SU2 CFD. Barrowman retired >Ma 0.7 as invalid for this vehicle.

## DO NOT REDO — these are already done
| Claim you may be told | Reality |
|---|---|
| "SU2 was never built" | **FALSE.** Built + validated: `~/.local/su2-8.5.0/bin/` (6 binaries). Single-core (`-Dwith-mpi=disabled`). |
| "Sweep tool needs writing" | **FALSE.** `analyses/geometry/cad_station_sweep.py` (633 ln) + tests exist. |
| "Solid identity unknown" | Measured. But the *question* is mis-framed — see below. |
| "`marker_zones.yaml` is unfilled" | **FALSE as of `1ab4850`** on `claude/su2-local-stability-run`. Filled from measured transitions, framed as geometric zones (not a stage split). See below. |

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

## THE BLOCKER — RESOLVED 2026-07-23, commit `1ab4850` on `claude/su2-local-stability-run`
`gmsh/marker_zones.yaml`'s `.template` asked "which solid is ramjet vs booster"
— **that question was invalid**: vol_1 is inside vol_2, and vol_2 spans 4225 of
4355mm. It is centerbody-inside-airframe, not stage-1 vs stage-2. Answering it
as posed would have silently flipped the static-margin sign (the whole
deliverable), so it was deliberately left unfilled until real transitions were
measured (see §"Established facts" above).

**What was written** (marker *names* kept as-is — `body_wall`, `booster_wall`
etc. are referenced verbatim in `cfg/ramp_stability_supersonic_RANS.cfg.template`
and `cfg/markers.md` forbids renaming after meshing; only the *ranges* and the
`candidate_identity` framing changed):
- `inlet_cap`: x=[30.1, 160.0]mm
- `body_wall`: x=[160.0, 2400.0]mm (forward ducted section, real internal bore)
- `interstage_wall`: x=[2400.0, 2500.0]mm (bore-closure transition)
- `booster_wall`: x=[2500.0, 3600.0]mm (uniform barrel, constant section)
- `base_region`: x=[3600.0, 4385.15]mm (fin root to vehicle end)

`candidate_identity` for both solids now states the real centerbody-inside-
airframe finding, explicitly NOT a stage-1/stage-2 assignment. **Not yet
validated**: `.venv-gmsh` doesn't exist anywhere in the repo, so
`01_classify_and_mesh.py --classify-only` has never been run against this
filled file — first real invocation should be treated as a possible bug
surface, not a rubber stamp.

## Unresolved — report, never auto-fix
- Barrel measures **130.0mm** dia vs `vehicle_config.yaml` `body.diameter_m: 0.200` (**70mm gap**, field marked drawing-verified). Flagged in `marker_zones.yaml` comments, not resolved.
- Fin tip-to-tip **~590mm** vs config 550mm / 639mm — matches neither.
- 14 small circular members (r≈4.24mm) ringing x=2100mm at duct wall radius. Uninterpreted. Flagged in `marker_zones.yaml` comments, not resolved.
- **Never modify `vehicles/ramjet_rocket/vehicle_config.yaml`.** Report only.

## Next actions, in order
1. **First**, on `claude/su2-local-stability-run`: build a `.venv-gmsh` (repo
   convention, see that branch's case README) and run
   `01_classify_and_mesh.py --classify-only cad/ramPcfdSimplified.step` to
   sanity-check the newly-filled `marker_zones.yaml` actually loads and
   classifies before trusting it for a real mesh.
2. `01_classify_and_mesh.py --level coarse …` — **full-mesh path has NEVER run**; treat first invocation as a crash test.
3. Supersonic RANS smoke test — **never ran** (agent killed by usage limit). Use `runs/su2_rans_check/` config + `MACH_NUMBER=2.5`, `ENTROPY_FIX_COEFF=0.1`, `MUSCL_FLOW=YES`, `SLOPE_LIMITER_FLOW=VENKATAKRISHNAN`, `CFL_NUMBER=1.0`, `CFL_ADAPT=YES`, `ITER=50`.
4. SU2 turbulent validation meshes are **absent** from `TestCases/rans/*` (configs only). Fetch from `su2code/TestCases` before trusting RANS physics.
5. **(HUMAN)** Decide whether/when to merge `geometry/step-station-sweep` into `claude/su2-local-stability-run` (or vice versa) so this work stream lives on one branch. Not done by any session so far — see the branch-split note at the top of this file.

## Environment gotchas (hard-won)
- `cmd | tee log | tail -N` returns **tail's** exit code. Use `set -o pipefail`. A build once reported "exit 0" while failing.
- No `python`, only `python3` (Homebrew 3.14). **pytest NOT installed** anywhere local — "265 passed" came from another env. Verify by direct assertion and say so.
- PEP 668: `pip install --user` blocked. Use venvs: `analyses/geometry/.venv-geom`, case's `.venv-gmsh`.
- Homebrew `gmsh` CLI has **no Python bindings**. PyPI `gmsh==4.15.1` needed separately.
- **STEP is gitignored (14MB).** Cloud/remote sessions cannot see it — real-geometry work must run locally. This is why the tool sat synthetic-only for a session.
- `.gitignore` globally ignores `*.cfg`, `*.su2`. Tracked configs are `*.cfg.template`.
- **Single working tree.** Parallel agents must NOT `git checkout` — it yanks the tree from under others. Confine parallel work to `runs/` (gitignored).
- **2026-07-23: hit this for real.** A concurrent, unrelated session ran
  `git merge --no-ff claude/port-runner-improvements` in this same working
  tree while a subagent tried to `git checkout`; the checkout correctly
  refused (hung/timed out) rather than fight it. The merge process finished
  seconds later and left a **stale `.git/index.lock`** behind (0 bytes, no
  process holding it) that blocked all further git writes until manually
  `rm`'d after confirming no process held it. If you hit a checkout hang or
  an "Unable to create '.git/index.lock': File exists" error, check
  `ps aux | grep git` before assuming it's safe to remove — only remove it
  once you've confirmed nothing is actively using it.

## Cost model (corrected — old docs are wrong by ~10x)
Station sweep with loop topology: **~35–73 s/station**, NOT the ~8.4 s/station in
`status.md` §4b (that timed slicing without the topology walk). STEP merge alone
30–224 s. **Full 220-station sweep ≈ 4.5 h, not ~31 min.** Use targeted ranges.

## Rules
- Never fabricate safety-critical values (CG, mass, thrust). Sweep/bound instead.
- Report MATCH/MISMATCH against config; never auto-correct.
- Don't merge/rebase/delete branches unless asked — past sessions collided that way.
