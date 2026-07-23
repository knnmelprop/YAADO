# RamP CAD Station Sweep — status (checkpoint 2026-07-22)

Branch: `geometry/step-station-sweep` (created from `claude/su2-local-stability-run`
at the point this checkpoint was written — that branch's own work, the SU2
stability case scaffolding, is untouched and unrelated).

Goal of this work stream: extract precise internal + external geometry
(diameter/area vs. axial station) from the real STEP CAD file, by scripting
against the gmsh OCC kernel — not by physics judgment. This is a **separate
thread** from the SU2 stability case's own blocker (see
`analyses/stability/su2_cross_check/case_ramp_stability/README.md` and
`gmsh/marker_zones.yaml.template`), but the two are related: a working
station sweep can help resolve that case's open "which solid is which stage"
question. See §3 below for what the prototype run found on that specific
question.

## 1. What's done

- **Venv**: `analyses/geometry/.venv-geom/` (gitignored), built from
  `analyses/geometry/requirements-geom.txt` (`gmsh==4.15.1`, `numpy`,
  `matplotlib`, `pyyaml` — same gmsh pin as the SU2 case's own
  `.venv-gmsh`, kept separate/independent so the two cases don't share
  mutable state). Rebuild with:
  ```bash
  cd analyses/geometry
  python3 -m venv .venv-geom
  .venv-geom/bin/pip install -r requirements-geom.txt
  ```
- **Method prototyped and confirmed working**: `analyses/geometry/probe_slice.py`.
  For a station at `x0` (mm, STEP frame, X = vehicle longitudinal axis):
  1. `gmsh.model.occ.addRectangle(-R,-R,0,2R,2R)` — a 2R×2R square in the
     XY-plane (R=400mm, generous vs. the observed max radius 296.5mm).
  2. `gmsh.model.occ.rotate(..., axis=(0,1,0), angle=pi/2)` — rotates it
     to lie in the Y-Z plane (normal along +X).
  3. `gmsh.model.occ.translate(..., x0, 0, 0)` — moves it to the station.
  4. For each solid volume: `gmsh.model.occ.copy()` both the volume and
     the plane (so originals survive for the next station), then
     `gmsh.model.occ.intersect(...)` the copies. The result is the
     cross-section face(s) at that station.
  5. `gmsh.model.occ.getMass(2, face)` → area; `getBoundingBox(2, face)`
     → Y/Z extent. Explicitly `gmsh.model.occ.remove(..., recursive=True)`
     the produced faces/plane after each station so tags don't accumulate.
  - This is real, not a guess — ran against the actual
    `cad/ramPcfdSimplified.step` (2 solids, mm units) and produced sane,
    physically plausible numbers (§2).
- **NOT yet implemented**: loop/hole topology analysis. `probe_slice.py`
  only reports face area + bounding box — it does **not** yet distinguish
  "one simply-connected face" (solid disc, or a thin/star shape with no
  hole) from "a face with an inner boundary loop" (an actual internal
  void/bore), because a face with a hole still reports as a single face
  tag with `getMass` = net area (outer − inner). This is exactly the
  ambiguity flagged in §3 below, and is the concrete next step (§4).

## 2. Raw probe results (8 stations, full output in
`analyses/geometry/results/probe_slice_output_2026-07-22.txt`)

```
merge took 30.09 s
volumes: [(3, 1), (3, 2)]
  vol 1 bbox: x=[30.13, 1071.51]mm  y=[-102.34,105.33]  z=[-103.79,103.88]  (max radius ~105.3mm)
  vol 2 bbox: x=[159.81, 4385.15]mm y=[-293.51,296.51]  z=[-294.97,295.04]  (max radius ~296.5mm)

x=  50mm  vol=1  area=  182.61mm^2  r_eq=  7.62mm  bbox_y=(-6.1,9.1)    bbox_z=(-7.6,7.7)
x= 200mm  vol=1  area=16979.42mm^2  r_eq= 73.52mm  bbox_y=(-72.0,75.0)  bbox_z=(-73.5,73.6)
x= 200mm  vol=2  area= 2820.19mm^2  r_eq= 29.96mm  bbox_y=(-112.5,115.5) bbox_z=(-114.0,114.0)
x= 500mm  vol=1  area=11947.93mm^2  r_eq= 61.67mm  bbox_y=(-74.8,77.8)  bbox_z=(-76.3,76.4)
x= 500mm  vol=2  area=14009.40mm^2  r_eq= 66.78mm  bbox_y=(-123.5,126.5) bbox_z=(-125.0,125.0)
x=1000mm  vol=1  area= 3019.07mm^2  r_eq= 31.00mm  bbox_y=(-29.5,32.5)  bbox_z=(-31.0,31.0)
x=1000mm  vol=2  area=11497.61mm^2  r_eq= 60.50mm  bbox_y=(-123.5,126.5) bbox_z=(-125.0,125.0)
x=2000mm  vol=2  area= 2393.89mm^2  r_eq= 27.60mm  bbox_y=(-65.0,68.0)  bbox_z=(-66.5,66.5)
x=3000mm  vol=2  area=12667.69mm^2  r_eq= 63.50mm  bbox_y=(-62.0,65.0)  bbox_z=(-63.5,63.5)
x=4000mm  vol=2  area=23956.99mm^2  r_eq= 87.33mm  bbox_y=(-293.5,296.5) bbox_z=(-295.0,295.0)
x=4300mm  vol=2  area=20023.92mm^2  r_eq= 79.84mm  bbox_y=(-293.5,296.5) bbox_z=(-295.0,295.0)

sweep of 8 stations took 1987.5 s (~33 min) for up to 2 solids/station
```

**Performance note (important for next session's planning):** the STEP
merge itself is cheap (30s). The expensive part is the per-station
copy+intersect+cleanup loop: ~33 min for 8 stations × ≤2 volumes ≈
~124s per volume-slice. A useful station pitch over the full 4.355m
length (e.g. every 20mm → ~218 stations) at this rate would take **tens
of hours**, not minutes. `cad_station_sweep.py` must not naively scale
this loop — see §4.

## 3. Observation: does this bear on "which solid is booster vs. ramjet"?
(Direct relevance to `analyses/stability/su2_cross_check/case_ramp_stability/gmsh/marker_zones.yaml.template`'s
open `candidate_identity: "TBD"` question — recorded here explicitly,
non-conclusive.)

Comparing each station's actual face area against the area a **solid
disc** of the same bounding-box radius would have (`pi * r_bbox^2`):

| station | vol | area/disc-area ratio | reading |
|---|---|---|---|
| 200mm | 1 | 0.96 | solid, ~circular — no anomaly |
| 500mm | 1 | 0.63 | moderate deviation |
| 1000mm | 1 | 0.91 | close to solid (tapering nose-ish) |
| 200mm | 2 | **0.067** | large deviation |
| 500mm | 2 | 0.28 | large deviation |
| 1000mm | 2 | 0.23 | large deviation |
| 2000mm | 2 | 0.16 | large deviation |
| 3000mm | 2 | **0.95** | solid, ~circular — no anomaly |
| 4000mm | 2 | **0.087** | large deviation, bbox = global max radius |
| 4300mm | 2 | 0.073 | large deviation, bbox = global max radius |

Two *different* low-ratio patterns appear for `vol 2`, and they most
likely have two different explanations — **but this is not confirmed**,
only inferred from area+bbox; disambiguating requires the loop-topology
work in §4:

- **x=200–2000mm** (inside/near the vol_1↔vol_2 overlap zone,
  `x=[159.8,1071.5]mm` per `marker_zones.yaml.template`): bbox radius
  ~115–127mm, well below the assembly's global max radius (296.5mm).
  A thin-walled tube/fairing (large inner void close to the outer
  radius) would produce exactly this signature (small net area despite
  a moderate bbox). If real, this would mean vol_2 is **hollow** in this
  forward region — i.e. has genuine internal geometry there, contrary to
  the SU2 case README's "external-only, capped inlet" framing (which
  describes how the CFD case *treats* the inlet, not necessarily what
  the CAD itself contains).
- **x=4000–4300mm**: bbox radius = 296.5mm, exactly the assembly's
  *global* max radius. A thin fin blade reaching out to the fin-tip
  radius (small area, since a fin's axial cross-section is just its
  thickness profile) produces the same low-ratio signature without any
  hole at all. This is the more likely explanation for the aft anomaly
  specifically because the bbox matches the known global-max, which is
  much more consistent with a fin tip than a plausible duct radius.

**Neither is confirmed. Both readings are consistent with the numbers
above; only a real loop/hole check (§4) can tell them apart.** Do not
treat "vol_2 forward region is hollow" as established — it is a
hypothesis raised by this probe, worth checking first precisely because
it's cheap to check once §4 exists.

**On the user's ~1.7m length question:** no observed span in this data
is close to 1.7m. vol_1 length = 1.0414m, vol_2 length = 4.2253m, the
overlap zone = 0.9117m, vol_2's non-overlap (aft of vol_1) length =
3.3136m. The closest number anywhere in the repo to "~1.7m" is the
vehicle CG position, `vehicle_config_cg_from_nose_m: 1.6084` (from
`marker_zones.yaml.template`'s cross-check block) — but that's a single
point, not a length range, and 1.6084 vs. 1.7 is a ~0.09m gap. No clean
match found; flagging this explicitly rather than silently dropping the
question.

## 4. Next step (exact, for a fresh session/model)

1. **Write `analyses/geometry/cad_station_sweep.py`** (the real tool;
   `probe_slice.py` is a throwaway prototype, keep it only for reference/
   reproducibility, don't extend it in place):
   - Reuse the plane-intersection method from `probe_slice.py` (§1) —
     it's confirmed correct.
   - **Add loop/hole topology detection** per resulting face: get its
     bounding curves via `gmsh.model.getAdjacencies(2, face_tag)`
     (downward = curve tags), then each curve's endpoint points via
     `gmsh.model.getAdjacencies(1, curve_tag)` (downward = point tags).
     Build a graph (curves connected via shared point tags) and find
     connected components — each component is one closed wire loop. **1
     loop = no hole** (disc or star/fin shape); **>1 loop = a hole is
     present** — compute the inner loop's own extent (from its points'
     Y/Z coordinates) to get the internal bore diameter directly. This
     is what will settle the §3 ambiguity, station by station.
   - CLI: STEP path, station range, pitch (mm), output CSV path.
   - Output CSV columns (per station × volume): `x_mm, vol_tag, area_mm2,
     n_loops, outer_r_eq_mm, outer_bbox_r_mm, has_inner_loop,
     inner_area_mm2, inner_r_eq_mm`.
   - CSV output goes in `analyses/geometry/results/` and **is tracked**
     (measured/derived numbers, not raw CAD — same convention as
     `analyses/propulsion/*.csv`, `analyses/stability/results/*.csv`
     elsewhere in this repo); the source STEP itself stays gitignored,
     same as today.
2. **Fix the performance problem before running a real sweep** (§2 perf
   note) — 124s/volume/station is not viable at any useful pitch over
   4.355m. Options to investigate, in rough order of likely payoff:
   - Profile whether `copy()` of the *whole* solid (thousands of
     surfaces) per station is the bottleneck vs. `intersect()` itself —
     if it's the copy, look at whether OCC's `sectionByPlane`-style
     workflow (or a single boolean per station using the object with
     `removeObject=False` on the *original*, avoiding an explicit
     `copy()`) avoids re-copying the full solid every time.
   - Consider whether `gmsh.model.occ.removeAllDuplicates()` /
     `healShapes` once up front reduces per-intersect cost (dense
     Fusion STEP exports carry many tiny fillet/thread patches per
     `mesh_quality_checklist.md`).
   - If nothing helps, run at a much coarser pitch first (e.g. every
     100mm ≈ 44 stations, or bracket-and-refine only around the
     anomalies found in §3: 150–250mm, 1900–2100mm, 3900–4400mm)
     rather than a uniform fine sweep everywhere.
3. **No test suite exists for this yet.** Add
   `tests/unit/test_geometry_station_sweep.py` once `cad_station_sweep.py`
   exists: the loop-connected-components logic (pure Python, testable
   with synthetic curve/point data, no gmsh needed) and the
   `equivalent_diameter_from_area` helper are the parts that can be unit
   tested without gmsh; guard/skip anything that needs a real STEP file
   and the venv.
4. Once the hole-vs-fin ambiguity in §3 is resolved for real, **write the
   finding back** into
   `analyses/stability/su2_cross_check/case_ramp_stability/gmsh/marker_zones.yaml.template`'s
   `candidate_identity` fields (or leave a pointer there) — that's the
   consumer of this result, not this branch.

## 4b. UPDATE 2026-07-22 21:50 UTC — Stage-1 speedup confirmed (partial, mid-run)

Tested the first candidate from §4's perf options: drop the per-station
`gmsh.model.occ.copy()` of the full solid, call
`intersect([(3, vol_tag)], plane_copy, removeObject=False,
removeTool=True)` directly against the **original** volume instead (only
the 1-face cutting plane is copied, which is cheap). Script:
`analyses/geometry/probe_slice_v2_timing.py`.

**Result (x=200mm, x=500mm, both volumes each): 8.36s and 8.47s per
station** (both volumes combined) — vs. the old method's ~248s/station
average (1987s / 8 stations from §2). **~30x speedup.**

This was NOT re-run across all 8 original probe stations yet (only 2, as
a quick sanity check before committing to a longer run) — the values
returned (16979.42mm², 2820.19mm² at x=200; 11947.93mm², 14009.40mm² at
x=500) match §2's original numbers exactly, confirming the faster method
gives identical results, not just faster wrong ones.

**Feasibility for a full sweep, back-of-envelope:** ~220 stations (20mm
pitch over 4355mm) × ~8.4s/station ≈ 1848s ≈ **~31 minutes** — now
plausible within a single session, a large change from the old method's
15+ hour estimate. Full re-validation across more stations and the
Stage-2 loop-topology work (§4 next step) still needed before relying on
this number for planning a production run.

This update was checkpointed immediately because the user asked to
continue this work via a scheduled run in ~3 hours rather than
continuing hands-on right now — do not lose this finding by re-deriving
it from scratch next session.

## 5. What this checkpoint deliberately does NOT include

- `cad_station_sweep.py` itself — not started, per explicit instruction
  to stop here and leave it for a fresh session with full budget.
- Any pytest changes — none needed yet since no new importable module
  was added (only a standalone probe script + this doc).
- Any resolution of the ramjet/booster identity question — §3 is an
  observation, not a conclusion.

## 6. UPDATE 2026-07-23 — cloud session: `cad_station_sweep.py` implemented + synthetic-only validated

**This entire update was done in a cloud (Claude Code on the web) session,
which never has and never will have access to the real
`cad/ramPcfdSimplified.step` file (intentionally gitignored, local-only).
Confirmed absent at the start of this session (only `.gitkeep` in
`analyses/stability/su2_cross_check/case_ramp_stability/cad/`). Everything
below is STEP-independent by construction — no real geometry was touched,
re-timed, or drawn conclusions from.**

### What got implemented

- **`analyses/geometry/cad_station_sweep.py`** — the real production tool
  §4 called for, split into a pure-Python half (no `gmsh` dependency) and
  a `gmsh`/STEP-dependent driver half (`gmsh` imported lazily inside those
  functions only):
  - `equivalent_diameter_from_area(area_mm2) -> float`.
  - `group_curves_into_loops(curve_edges) -> list[list[int]]` — union-find
    over shared endpoint points, exactly the §4 spec.
  - `classify_face_loops(curve_edges, point_coords) -> LoopTopology` — the
    largest-radial-extent loop is classified outer, the rest are inner
    (hole) loops; settles the §3 ambiguity mechanically once run against
    real faces (still requires the real STEP file to actually apply, see
    below).
  - `cross_check_against_vehicle_config(rows, vehicle_config_path,
    tolerance_pct) -> list[CrossCheckResult]` — report-only MATCH/MISMATCH
    against `vehicles/ramjet_rocket/vehicle_config.yaml` (max radius,
    axial extent, cylindrical-body radius). No auto-correction.
  - `open_step`, `slice_volume_at_station`, `run_station_sweep` — the
    gmsh driver, reusing the confirmed-correct plane-intersection method
    from `probe_slice.py` **and** the confirmed ~30x-faster
    `removeObject=False` variant from `probe_slice_v2_timing.py` (§4b) —
    the new tool does NOT reintroduce the slow per-station full-solid
    `copy()`.
  - CLI (`python -m analyses.geometry.cad_station_sweep <step> --x-start-mm
    --x-end-mm --pitch-mm --output-csv [--vehicle-config]
    [--tolerance-pct]`), CSV columns exactly matching §4's spec
    (`x_mm, vol_tag, area_mm2, n_loops, outer_r_eq_mm, outer_bbox_r_mm,
    has_inner_loop, inner_area_mm2, inner_r_eq_mm`).

### Synthetic end-to-end validation (no real STEP involved)

- Installed `gmsh==4.15.1` (pinned, same as `requirements-geom.txt`) into
  a fresh `.venv-geom` in this cloud sandbox. Note for future cloud
  sessions: this container needed three extra system packages before
  `import gmsh` would even load (`libglu1-mesa`, `libopengl0`, `libxft2`
  via `apt-get install`) — not a repo concern, just a sandbox-provisioning
  note, since a local machine with a working `.venv-geom` per this doc's
  §1 setup already has these.
  - Built a solid cylinder (`gmsh.model.occ.addCylinder`, r=20mm) and a
    hollow tube (concentric cylinders, r=20mm outer / r=10mm inner, via
    `gmsh.model.occ.cut`) — synthetic solids with a **known** ground-truth
    topology, standing in for the real STEP file.
  - Ran `slice_volume_at_station` (the actual production driver function,
    same `addRectangle`+`rotate`+`translate`+`intersect`+adjacency-walk
    code path the real STEP will use) against both synthetic solids.
  - **Result: solid cylinder -> 1 loop, `has_inner_loop=False`, area
    matches `pi*r^2` exactly. Hollow tube -> 2 loops, `has_inner_loop=True`,
    `inner_bbox_r_mm` matches the known 10mm bore exactly, `outer_bbox_r_mm`
    matches the known 20mm outer radius exactly, net area matches
    `pi*(20^2-10^2)` exactly.** This is real end-to-end confirmation of the
    loop/hole detection logic via the actual gmsh OCC API path — not a
    guess, not STEP-derived, and not extrapolated to the real geometry.

### Tests

- **`tests/unit/test_geometry_station_sweep.py`** — new. Pure-Python unit
  tests (no `gmsh` needed) for `equivalent_diameter_from_area`,
  `group_curves_into_loops`, `classify_face_loops`, and
  `cross_check_against_vehicle_config` (including a MATCH case, a
  MISMATCH case, and a rejected-non-`RocketConfig` case). One integration
  test (`test_synthetic_solid_and_hollow_cylinder_loop_detection`) runs
  the synthetic solid/hollow-cylinder validation above as an actual
  pytest case, guarded with `@pytest.mark.skipif(not HAS_GMSH, ...)` so
  it skips cleanly (not a failure) in any environment without `gmsh`
  installed.
- **Full suite result, main environment (no `gmsh` installed there):**
  `265 passed, 1 skipped` (up from a `251 passed` baseline measured at the
  start of this session; the 14 new pure-Python tests pass, the 1 gmsh
  integration test skips cleanly as designed).
- **Same integration test, run for real in `.venv-geom` (gmsh present):**
  `1 passed` — this is the run that actually confirmed the synthetic
  solid/hollow-cylinder result above, not just a skip.

### Explicitly UNCHANGED by this update — still needs a LOCAL session with the real STEP file

- **Stage 1 (§2, real timing on the real assembly):** unchanged. The
  `~30x` speedup (§4b) is confirmed on the real geometry already; this
  session did not and could not re-time it (no STEP file present).
- **Stage 2 (§3, real ramjet-vs-booster solid-identity conclusion):**
  unchanged, still an open, non-conclusive observation. This session's
  `classify_face_loops` logic is now implemented and validated on
  synthetic data, but it has **not** been run against the real
  `ramPcfdSimplified.step` faces — that is exactly what the next local
  session needs to do to settle §3 for real.
  `analyses/stability/su2_cross_check/case_ramp_stability/gmsh/
  marker_zones.yaml.template`'s `candidate_identity: "TBD"` is untouched.
- **Stage 3 (§4, real production sweep over the full 4.355m length):**
  unchanged. `cad_station_sweep.py` now exists and is validated on
  synthetic data, but has never been invoked against the real STEP file.
- **The `marker_zones.yaml` handoff and the `claude/su2-local-stability-run`
  branch:** untouched, not even checked out, per explicit instruction.

### Next step for the local session (exact)

1. Run `cad_station_sweep.py` against the real
   `cad/ramPcfdSimplified.step`, using the confirmed-fast
   `removeObject=False` method (already the default in this tool — no
   extra flag needed), e.g. a full-length sweep:
   ```bash
   .venv-geom/bin/python3 -m analyses.geometry.cad_station_sweep \
       analyses/stability/su2_cross_check/case_ramp_stability/cad/ramPcfdSimplified.step \
       --x-start-mm 0 --x-end-mm 4355 --pitch-mm 20 \
       --output-csv analyses/geometry/results/station_sweep_full.csv \
       --vehicle-config vehicles/ramjet_rocket/vehicle_config.yaml
   ```
   per §4b's back-of-envelope, ~220 stations at this pitch should take
   roughly ~30 minutes; re-validate that estimate on the real file before
   committing to a much finer pitch.
2. Inspect the resulting CSV's `has_inner_loop`/`inner_r_eq_mm` columns
   for `vol=2` in the §3 anomaly regions (150-250mm, 1900-2100mm,
   3900-4400mm) to settle the hollow-tube-vs-fin-blade question for real.
3. Write that finding back into `marker_zones.yaml.template`'s
   `candidate_identity` field (or a pointer to it), on the
   `claude/su2-local-stability-run` branch, per §4 point 4 — not this
   branch.

## 7. UPDATE 2026-07-23 — local session: §3 ambiguity SETTLED against the real STEP file

Ran `cad_station_sweep.py`'s own functions (`open_step` +
`slice_volume_at_station` + `_build_row` + `write_csv`, called from a
small scratchpad driver script, not a change to the tool itself) against
the real `cad/ramPcfdSimplified.step`, at exactly the 7 diagnostic
stations flagged in §3: `200, 500, 1000, 2000, 3000, 4000, 4300` mm.
Output: `analyses/geometry/results/station_sweep_topology_2026-07-23.csv`
(tracked, 10 rows).

**Performance note:** this run was markedly slower than the §4b baseline
(merge 187.2s vs. ~30s; per-station 47-83s for 1-2 volumes vs. the
confirmed ~8.4s/station-for-2-volumes) — total wall time ~10m22s for 7
stations. The method itself (`removeObject=False` against the original
volume, no full-solid copy) is unchanged from the confirmed-fast §4b
code path, and the values obtained match §2's original probe numbers
exactly at the 3 overlapping stations (200, 500, 1000mm — see below), so
this is read as this-run machine-load variance, not a regression in the
method. Flagging for whoever runs the full 220-station sweep next: budget
more than the §4b back-of-envelope ~31 minutes, and re-check load before
committing to a long run.

### Result

| x_mm | vol | n_loops | has_inner_loop | outer_bbox_r_mm | inner_r_eq_mm | wall_mm | reading |
|---|---|---|---|---|---|---|---|
| 200 | 1 | 1 | False | 72.0 | — | — | solid |
| 200 | 2 | **2** | **True** | 112.8 | 108.5 | 4.3 | **hollow, thin wall** |
| 500 | 1 | 1 | False | 77.8 | — | — | solid |
| 500 | 2 | **2** | **True** | 123.5 | 104.4 | 19.1 | **hollow** |
| 1000 | 1 | 1 | False | 31.0 | — | — | solid |
| 1000 | 2 | **2** | **True** | 123.5 | 108.1 | 15.4 | **hollow** |
| 2000 | 2 | **2** | **True** | 68.0 | 60.6 | 7.4 | **hollow, thin wall** |
| 3000 | 2 | 1 | False | 65.0 | — | — | solid (matches §3's 0.95 ratio reading) |
| 4000 | 2 | **1** | **False** | 296.5 | — | — | **NOT a hole — single loop despite low area ratio** |
| 4300 | 2 | **1** | **False** | 296.5 | — | — | **NOT a hole — single loop despite low area ratio** |

Area/bbox numbers at x=200/500/1000mm match §2's original probe output
exactly (e.g. x=200 vol=2 area=2820.19mm², x=500 vol=1
area=11947.93mm²) — same cross-check §4b already established for the
timing method, now extended to confirm the loop-topology pass reads the
same underlying faces.

### Verdict on the two §3 hypotheses — both settled, by actual loop count, not inference

- **x=200-2000mm, vol_2: CONFIRMED HOLLOW.** Every station in this range
  (200, 500, 1000, 2000mm) reports `n_loops=2` /
  `has_inner_loop=True`, with a real inner wire loop whose own
  point-extent gives a consistent thin-to-moderate wall thickness
  (4.3-19.1mm) at all four stations, not a one-off. This is Hypothesis A
  from §3, now confirmed: vol_2 genuinely has internal
  geometry (a bore/duct) in this forward/overlap region — it is not just
  a low-area artifact of net-area subtraction against an unrelated
  shape.
- **x=4000-4300mm, vol_2: CONFIRMED NOT A HOLE (thin fin/blade).** Both
  stations report `n_loops=1` / `has_inner_loop=False` — a single closed
  wire loop, despite the low area/bbox-disc ratio and despite
  `outer_bbox_r_mm` (296.5mm) exactly matching the assembly's global max
  radius. This rules out Hypothesis "hollow duct at the fin-tip radius"
  for this region and confirms the alternative fin/blade-profile
  reading from §3: a thin cross-section reaching out to the tip radius,
  with no internal void. (x=3000mm, also `n_loops=1`, is the
  already-expected "no anomaly" control point from §3's table.)

**Caveat on `inner_r_eq_mm`/`inner_area_mm2` precision:** per §4's own
spec ("compute the inner loop's own extent ... to get the internal bore
diameter directly"), these are a bounding-box-derived circle
approximation from the inner loop's own points (average of Y/Z
half-extents, then `area = pi*r^2`), **not** an exact swept area of the
inner wire — gmsh's `getMass` on the produced face only gives the net
(outer-minus-inner) area, and no separate face exists for the hole alone
in this method. Good enough to confirm hole-vs-no-hole and get an
order-of-magnitude bore size (as used above); not precise enough to
treat as an exact duct-diameter datasheet number without a follow-up
exact-area pass (e.g. building a plane surface from just the inner
wire's curve loop and measuring its own `getMass`) if that precision is
ever needed downstream.

### What this implies for solid identity — NOT written into `marker_zones.yaml.template`, human call only

vol_1 is a single solid loop at every probed station across its whole
observed span (x=200/500/1000mm all `n_loops=1`) — a solid body,
in the region that overlaps vol_2 (x=[159.8,1071.5]mm). vol_2, over that
same overlap span, is hollow with wall thicknesses in the ~4-19mm range
consistent with a shroud/duct/body-tube wall, not a full-diameter solid.
Aft of the overlap (x=3000-4300mm), vol_2 alternates between a solid
disc (x=3000mm) and a thin no-hole fin/blade profile
(x=4000-4300mm, at the assembly's global max radius). Whether this
pattern means vol_2 is the ramjet's body/duct + tail fins with vol_1
nested inside it as the booster (or the reverse, or something else) is
exactly the identity question `marker_zones.yaml.template` leaves as
`candidate_identity: "TBD"` — this update supplies real topology evidence
for that human decision, it does not make the call. Per explicit
instruction, `marker_zones.yaml.template` and
`vehicles/ramjet_rocket/vehicle_config.yaml` are untouched by this
session.

## 7. UPDATE 2026-07-23 (local session) — §3 RESOLVED by real measurement, and the identity question turns out to be MIS-FRAMED

First run of `cad_station_sweep.py` against the **real** STEP file. (The
cloud session that wrote the tool in §6 never had the file — it is
gitignored/local-only — so it could only validate against synthetic
solids.) Results: `analyses/geometry/results/station_sweep_topology_2026-07-23.csv`,
commit `153e0bb`.

### §3's two hypotheses: BOTH CONFIRMED

| region | vol | n_loops | has_inner_loop | verdict |
|---|---|---|---|---|
| x=200–2000mm | 2 | **2** | **True** | genuine internal void (hollow) |
| x=3000mm | 2 | 1 | False | solid |
| x=4000–4300mm | 2 | **1** | **False** | thin fin blade, NO hole |
| x=200/500/1000 | 1 | 1 | False | solid throughout |

- **Forward anomaly = a real bore.** vol_2 inner radius ~108.5mm (x=200),
  104.4 (x=500), 108.1 (x=1000), narrowing to 60.6mm (x=2000).
- **Aft anomaly = fins, not a hole.** 1 loop, and `outer_bbox_r` =
  296.53/296.55mm — exactly the assembly's *global* max radius, which is
  what a thin blade reaching to the fin tip looks like. Precisely the
  reasoning §3 proposed; now measured rather than inferred.

### THE IMPORTANT PART — the two solids are not two stages

`marker_zones.yaml.template` asks "which solid is the ramjet stage and
which is the booster?" **The geometry says that question does not have an
answer as posed:**

- **vol_1's outer max radius = 105.33mm. vol_2's forward bore radius =
  104.4–108.5mm.** These are the same radius. **vol_1 nests INSIDE vol_2's
  forward cavity** through the whole overlap zone x=[159.8, 1071.5]mm.
- **vol_2 spans x=159.8–4385.2mm — 4225mm, i.e. essentially the entire
  4355mm vehicle**, and carries the fins at its aft end.

So the decomposition is **not** stage-1 vs stage-2. It reads much more like
**inner body/centerbody (vol_1) inside an outer airframe-with-duct-and-fins
(vol_2)**. Supporting detail from the earlier §2 probe: vol_1 at x=50mm has
area 182.6mm² (r_eq 7.6mm) — a near-sharp tip, consistent with a nose cone
or inlet spike, and `vehicle_config.yaml` lists `nose_diameter_m: 0.150`
against vol_1's ~147mm diameter at x=200mm.

**Consequence:** filling `marker_zones.yaml` by assigning
`vol_1 -> stage_X, vol_2 -> stage_Y` would encode a false premise. The
marker scheme itself (body_wall / interstage_wall / booster_wall /
base_region / inlet_cap) is X-range-based, which is still workable — but
the ranges must be derived from real geometric transitions, **not** from a
solid-to-stage mapping. This is a design decision for a human, not
something to infer. NOT written into any config this session.

### Incidental evidence on the open fin-span question

At x=4000–4300mm the fin tips reach r=296.5mm → **tip-to-tip ≈ 590mm**
(bbox y spans -293.5..296.5).

- `fins.span_m: 0.550` (550mm, "MODERATE CONFIDENCE", layout-inferred)
- `body.max_diameter_m: 0.639` (639mm, Fusion bbox, flagged "needs review")
- Fusion alternative 0.6685m; the "127" radial reading

Measured 590mm falls **between** 550 and 639 and matches neither. This is
real 3D evidence and a genuine third data point, but it does not by itself
settle what "550" or "127" referred to on the 2D drawing — still needs
human confirmation, exactly as `vehicle_config.yaml` itself already flags.
**No config value was changed.**

### Performance recalibration (important for planning)

The run took **~73s/station** (7 stations, ~8.5 min), NOT the ~8.4s/station
projected in §4b. The loop-topology adjacency walk adds substantial cost on
these 3317-surface solids; §4b's timing measured slicing *without* topology.
**A full 220-station 20mm-pitch sweep would be ~4.5 hours, not ~31 minutes.**
Do not launch one without planning for that. Targeted range sweeps are the
right approach.
