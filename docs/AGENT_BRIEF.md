# AGENT BRIEF — RamP / IADE (current as of 2026-07-23, post marker_zones.yaml)

Compact state for agents. Full detail: `docs/HANDOFF_2026-07-23.md`.

## ⚠️ TWO BRANCHES, TWO DRAFT PRs — read this before you start

This work stream is currently **split across two diverged branches**, deliberately
NOT merged (standing repo rule: never merge/rebase/delete branches unless a human
asks — past sessions collided that way). Both are now open as separate draft PRs
against the real default branch (`claude/iade-repo-restructure-00rrro`, confirmed
via `gh repo view` — NOT `main`, though the two happen to be at the same commit
right now):
- **PR #13** — `geometry/step-station-sweep`: the geometry tool + measurements.
- **PR #14** — `claude/su2-local-stability-run`: the SU2 case, `marker_zones.yaml`,
  the gmsh mesher bug fix. Each PR body cross-links the other.

A fresh agent needs to know about BOTH branches/PRs:

- **`geometry/step-station-sweep`** (pushed, clean, HEAD `9a1bab1` as of this
  entry) — the geometry tool, the real-STEP measurements, and all the docs
  you're reading now (`docs/geometry/status.md`, `docs/HANDOFF_2026-07-23.md`,
  this file, `docs/decision-log.md`).
- **`claude/su2-local-stability-run`** (pushed, clean, HEAD `b445eb3`) — the SU2
  CFD case itself (`analyses/stability/su2_cross_check/case_ramp_stability/`),
  including **`gmsh/marker_zones.yaml`, filled in** (commit `1ab4850`,
  2026-07-23) using the geometry findings below, plus a real gmsh
  `BoundaryLayer`-field bug fix (commit `b445eb3` — see "Next actions" §2).
  This branch does NOT have the geometry-tool commits or these docs on it —
  only the CFD case itself.
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
1. ~~Build `.venv-gmsh`, validate marker_zones.yaml with `--classify-only`~~ —
   **DONE, 2026-07-23.** `.venv-gmsh` now exists on `claude/su2-local-stability-run`
   (built by a separate concurrent local session, not committed — venvs are
   gitignored, rebuild per that branch's case README if missing).
2. **`01_classify_and_mesh.py --level coarse …` was attempted for real, 2026-07-23
   — partial result, NOT a clean pass:**
   - **Real bug found and fixed** (commit `b445eb3`, `claude/su2-local-stability-run`):
     gmsh's `BoundaryLayer` mesh field is **2D-only** in this build — it does
     not support a 3D `SurfacesList`/`FacesList` option at all (raises "Unknown
     option", not a silent no-op). There is no 3D anisotropic prism-layer field
     available via this gmsh Python API on an OCC-kernel model. **Consequence:
     this mesher cannot currently produce a wall-resolved y+~1 viscous mesh** —
     only isotropic Distance/Threshold refinement near walls, which is orders
     of magnitude coarser than the y1 first-cell height `isa_yplus.py`
     computes. The fix replaces the broken call with an explicit stderr
     warning reporting both numbers, so this isn't silently assumed away.
   - **The mesh run itself did not finish.** It reached ~94% of surface
     meshing (surface 3127 of ~3317) after 30+ min, then the session running
     it was cut off (parent process gone, no `EXIT_CODE` line, no mesh output
     file in `mesh/`) — same "killed by usage limit / session end" pattern
     already seen on the RANS smoke test below. **Re-run to actually get a
     first coarse mesh is still the next concrete step.** Budget more than 30
     min; consider running detached/nohup'd so a session boundary doesn't
     kill it.
   - **Do not assume a valid mesh exists.** `01_classify_and_mesh.py`'s
     full-mesh path has now been exercised further than ever before, but has
     still never actually completed and produced output.
3. Once a coarse mesh exists: figure out a real path to a wall-resolved
   viscous mesh given finding above (options to investigate: gmsh's
   `Mesh.BoundaryLayerFanElements`/extrusion-based approaches, exporting to
   another tool for prism-layer generation, or accepting isotropic refinement
   with a documented y+ caveat for a first-pass inviscid/coarse RANS check).
4. Supersonic RANS smoke test — **never ran** (agent killed by usage limit). Use `runs/su2_rans_check/` config + `MACH_NUMBER=2.5`, `ENTROPY_FIX_COEFF=0.1`, `MUSCL_FLOW=YES`, `SLOPE_LIMITER_FLOW=VENKATAKRISHNAN`, `CFL_NUMBER=1.0`, `CFL_ADAPT=YES`, `ITER=50`.
5. SU2 turbulent validation meshes are **absent** from `TestCases/rans/*` (configs only). Fetch from `su2code/TestCases` before trusting RANS physics.
6. **(HUMAN)** Decide whether/when to merge `geometry/step-station-sweep` into `claude/su2-local-stability-run` (or vice versa) so this work stream lives on one branch. Not done by any session so far — see the branch-split note at the top of this file.

## Environment gotcha, again: sessions get cut off mid-run, don't trust silence as success
Two separate long-running local processes this project has hit so far (the
RANS smoke test, and now the coarse mesh above) were killed by a session/usage
boundary **mid-execution**, not by a script error — no traceback, no
`EXIT_CODE` line, just the process and its parent gone. Long gmsh/SU2 runs
(mesh generation, RANS solves) should be treated as likely to outlive a single
session. Prefer `nohup ... &` / a detached background process with a log file
you can check across sessions over a foreground run tied to one session's
lifetime, and always check the log for an actual completion marker before
treating a "finished" process as having produced a real result.

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
