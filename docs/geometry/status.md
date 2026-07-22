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
