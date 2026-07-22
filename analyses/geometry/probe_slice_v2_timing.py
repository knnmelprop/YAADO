# MELprop-IADE | analyses.geometry.probe_slice_v2_timing | v0.1.0
"""Stage-1 performance-fix probe (2026-07-22, mid-checkpoint).

Same plane-intersection method as ``probe_slice.py``, with ONE change:
drops the per-station ``gmsh.model.occ.copy()`` of the full solid volume,
and instead calls ``intersect([(3, vt)], plane, removeObject=False,
removeTool=True)`` directly against the original volume (still copies
only the tiny 1-face cutting plane, which is cheap). ``removeObject=False``
keeps the original volume intact for the next station without an
up-front deep copy of its full B-Rep (thousands of faces).

Measured result (this run, x=200mm and x=500mm, 2 volumes each):
``dt=8.36s`` and ``dt=8.47s`` per station (both volumes combined) vs. the
old ``probe_slice.py`` method's ~248s/station average (1987s / 8
stations) -- **roughly a 30x speedup**. See
``docs/geometry/status.md`` for the full write-up and the resulting
feasibility verdict for a full-length sweep.

This is a timing probe only, not the final tool -- keep for reference,
do not extend in place (see ``cad_station_sweep.py`` once written).
"""

import math
import time

import gmsh

STEP = (
    "/Users/aleksczernicki/Desktop/dev/iade/analyses/stability/su2_cross_check/"
    "case_ramp_stability/cad/ramPcfdSimplified.step"
)

gmsh.initialize()
gmsh.option.setNumber("General.Terminal", 0)
gmsh.model.add("probe_v2q")
t0 = time.time()
gmsh.merge(STEP)
gmsh.model.occ.synchronize()
print("merge took", time.time() - t0, "s", flush=True)

vols = gmsh.model.getEntities(3)
vol_tags = [t for _, t in vols]

R = 400.0

def slice_at_v2(x0, vol_tags):
    rect = gmsh.model.occ.addRectangle(-R, -R, 0, 2*R, 2*R)
    gmsh.model.occ.rotate([(2, rect)], 0, 0, 0, 0, 1, 0, math.pi/2)
    gmsh.model.occ.translate([(2, rect)], x0, 0, 0)
    gmsh.model.occ.synchronize()
    results = []
    for vt in vol_tags:
        pcopy = gmsh.model.occ.copy([(2, rect)])
        gmsh.model.occ.synchronize()
        out, _ = gmsh.model.occ.intersect([(3, vt)], pcopy, removeObject=False, removeTool=True)
        gmsh.model.occ.synchronize()
        faces = [t for d, t in out if d == 2]
        info = []
        for f in faces:
            area = gmsh.model.occ.getMass(2, f)
            info.append((f, area))
        results.append((vt, info))
        if out:
            gmsh.model.occ.remove(out, recursive=True)
            gmsh.model.occ.synchronize()
    gmsh.model.occ.remove([(2, rect)], recursive=True)
    gmsh.model.occ.synchronize()
    return results

for x0 in [200, 500]:
    st = time.time()
    res = slice_at_v2(x0, vol_tags)
    dt = time.time() - st
    print(f"x={x0} dt={dt:.2f}s res={res}", flush=True)
gmsh.finalize()
