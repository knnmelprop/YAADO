# MELprop-IADE | analyses.geometry.probe_slice | v0.1.0
"""Throwaway prototype for the STEP plane-slicing approach (NOT the final tool).

Confirms the method: build a Y-Z rectangle at each X-station, rotate it
perpendicular to the vehicle's longitudinal (X) axis, and boolean-intersect
copies of it against copies of each solid volume via the gmsh OCC kernel to
get the cross-section face(s) (area + bounding box) at that station.

This script is intentionally minimal (no CLI, no CSV, no loop/hole
topology analysis, hard-coded STEP path) -- it exists only to validate that
the intersect approach works and to time it against the real
``ramPcfdSimplified.step`` before writing the real
``cad_station_sweep.py`` tool. See ``results/probe_slice_output_2026-07-22.txt``
for a captured run and ``docs/geometry/status.md`` for the interpretation
and the next-step plan.

Run (from a venv with ``gmsh`` installed, e.g. ``.venv-geom``)::

    .venv-geom/bin/python3 probe_slice.py
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
gmsh.model.add("probe")
t0 = time.time()
gmsh.merge(STEP)
gmsh.model.occ.synchronize()
print("merge took", time.time()-t0, "s")

vols = gmsh.model.getEntities(3)
print("volumes:", vols)
for dim, tag in vols:
    bb = gmsh.model.getBoundingBox(dim, tag)
    print(f"  vol {tag} bbox={bb}")

R = 400.0  # half-extent mm, generous vs max observed radius ~296.5mm

def slice_at(x0, vol_tags):
    # Build a Y-Z plane rectangle at X=x0
    rect = gmsh.model.occ.addRectangle(-R, -R, 0, 2*R, 2*R)
    gmsh.model.occ.rotate([(2, rect)], 0, 0, 0, 0, 1, 0, math.pi/2)
    gmsh.model.occ.translate([(2, rect)], x0, 0, 0)
    gmsh.model.occ.synchronize()
    results = []
    for vt in vol_tags:
        # copy solid + copy plane, intersect (non-destructive to originals)
        vcopy = gmsh.model.occ.copy([(3, vt)])
        pcopy = gmsh.model.occ.copy([(2, rect)])
        gmsh.model.occ.synchronize()
        out, _ = gmsh.model.occ.intersect(vcopy, pcopy, removeObject=True, removeTool=True)
        gmsh.model.occ.synchronize()
        faces = [t for d, t in out if d == 2]
        info = []
        for f in faces:
            area = gmsh.model.occ.getMass(2, f)
            bb = gmsh.model.getBoundingBox(2, f)
            info.append((f, area, bb))
        results.append((vt, info))
        # cleanup produced faces so they don't pile up for next station
        if out:
            gmsh.model.occ.remove(out, recursive=True)
            gmsh.model.occ.synchronize()
    gmsh.model.occ.remove([(2, rect)], recursive=True)
    gmsh.model.occ.synchronize()
    return results

vol_tags = [t for _, t in vols]
stations = [50, 200, 500, 1000, 2000, 3000, 4000, 4300]
t0 = time.time()
for x0 in stations:
    res = slice_at(x0, vol_tags)
    for vt, info in res:
        for f, area, bb in info:
            r_eq = math.sqrt(area/math.pi) if area > 0 else 0.0
            print(f"x={x0:6.1f}mm vol={vt} face={f} area={area:10.2f}mm^2 r_eq={r_eq:7.2f}mm bbox_y=({bb[1]:.1f},{bb[4]:.1f}) bbox_z=({bb[2]:.1f},{bb[5]:.1f})")
    if not res or all(len(info)==0 for _, info in res):
        print(f"x={x0:6.1f}mm: no intersection (outside all volumes)")
print("sweep of", len(stations), "stations took", time.time()-t0, "s")

gmsh.finalize()
