# MELprop-IADE | STEP -> classified, meshed, .su2 export | v0.1.0
"""Classify STEP surfaces into markers, build the farfield, mesh, export .su2.

Two modes:

``--classify-only`` (safe, no ``marker_zones.yaml`` required):
    Loads the STEP, tags every surface with its parent volume and the
    geometric cap-candidate heuristic from ``00_inventory_step.py``, and
    writes ``mesh/inventory/classification.csv``. No meshing, no farfield.
    Use this to sanity-check the geometry read before committing to a full
    run.

Full mesh mode (default; requires a filled-in ``gmsh/marker_zones.yaml``):
    1. Import the STEP, heal small slivers (Fusion STEP exports are dense
       with tiny fillet/thread patches — see ``mesh_quality_checklist.md``).
    2. Build a farfield sphere sized to >=15 body-diameters (checklist gate)
       and boolean-subtract the vehicle solids to get the fluid domain.
    3. Tag physical groups for every marker in ``markers.md`` from the
       confirmed X-zones in ``marker_zones.yaml``.
    4. Size fields: distance-based refinement at nose/interstage/base, plus
       a BoundaryLayer field on the wall markers sized via ``isa_yplus.py``
       for the target y+.
    5. Generate the 3-D mesh and write ``mesh/ramp_stability_<level>.su2``.

Requires the ``gmsh`` Python module + PyYAML (see ``requirements-gmsh.txt``).

Usage:
    python3 01_classify_and_mesh.py --classify-only cad/ramPcfdSimplified.step
    python3 01_classify_and_mesh.py --level coarse --mach 2.5 --altitude-m 10000 \\
        cad/ramPcfdSimplified.step
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import gmsh
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from isa_yplus import first_cell_height_m  # noqa: E402

CASE_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_MARKERS = (
    "body_wall",
    "interstage_wall",
    "booster_wall",
    "base_region",
    "inlet_cap",
)


def classify_only(step_path: Path, out_dir: Path) -> None:
    """Tag every surface by parent volume + cap heuristic; write a CSV.

    Args:
        step_path: Path to the STEP file.
        out_dir: Directory for ``classification.csv`` (created if missing).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    try:
        gmsh.model.add("classify")
        gmsh.merge(str(step_path))
        gmsh.model.occ.synchronize()

        vols = gmsh.model.getEntities(3)
        vol_bbox = {tag: gmsh.model.getBoundingBox(3, tag) for _, tag in vols}
        global_xmin = min(b[0] for b in vol_bbox.values())
        global_xmax = max(b[3] for b in vol_bbox.values())

        rows = []
        for dim, tag in gmsh.model.getEntities(2):
            xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(dim, tag)
            up, _ = gmsh.model.getAdjacencies(dim, tag)
            parent = up[0] if len(up) else -1
            x_extent = xmax - xmin
            near_end = abs(xmin - global_xmin) < 5.0 or abs(xmax - global_xmax) < 5.0
            rows.append(
                {
                    "surf_tag": tag,
                    "parent_vol": parent,
                    "x_min_mm": xmin,
                    "x_max_mm": xmax,
                    "cap_candidate": x_extent < 1.0 and near_end,
                }
            )
        path = out_dir / "classification.csv"
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"Classified {len(rows)} surfaces across {len(vols)} volumes.")
        print(f"Wrote {path}")
        print("No marker assignment performed (classify-only). "
              "Fill gmsh/marker_zones.yaml and re-run without --classify-only.")
    finally:
        gmsh.finalize()


def _load_marker_zones(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found. Copy gmsh/marker_zones.yaml.template to "
            f"gmsh/marker_zones.yaml and fill in the confirmed zones/markers."
        )
    with path.open() as f:
        cfg = yaml.safe_load(f)
    missing = [m for m in REQUIRED_MARKERS if cfg.get("markers", {}).get(m) is None]
    if missing:
        raise ValueError(
            f"marker_zones.yaml has unconfirmed (null) markers: {missing}. "
            f"These must be filled in by a human before a full mesh run "
            f"(see the file's header comment) — refusing to guess."
        )
    return cfg


def build_mesh(
    step_path: Path,
    zones_path: Path,
    out_dir: Path,
    level: str,
    mach: float,
    altitude_m: float,
    y_plus_target: float,
) -> Path:
    """Build the farfield fluid domain, tag markers, mesh, export .su2.

    Args:
        step_path: Path to the vehicle STEP file.
        zones_path: Path to a filled-in ``marker_zones.yaml``.
        out_dir: Output directory for the mesh (typically ``mesh/``).
        level: ``"coarse"`` or ``"fine"`` — controls the global mesh-size
            scale factor.
        mach: Freestream Mach number, for y+ first-cell sizing.
        altitude_m: ISA design altitude, metres, for y+ first-cell sizing.
        y_plus_target: Target dimensionless wall distance for the first cell.

    Returns:
        Path to the written ``.su2`` mesh file.
    """
    cfg = _load_marker_zones(zones_path)
    zones = cfg["zones"]
    markers = cfg["markers"]
    global_xmin_mm, global_xmax_mm = cfg["observed"]["global_assembly_x_mm"]
    body_length_m = (global_xmax_mm - global_xmin_mm) / 1000.0
    max_radius_mm = max(
        cfg["observed"]["vol_1"]["approx_max_radius_mm"],
        cfg["observed"]["vol_2"]["approx_max_radius_mm"],
    )
    max_diameter_m = 2.0 * max_radius_mm / 1000.0

    scale = {"coarse": 1.0, "fine": 0.5}[level]
    y1 = first_cell_height_m(mach, altitude_m, body_length_m, y_plus_target)

    out_dir.mkdir(parents=True, exist_ok=True)
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 1)
    try:
        gmsh.model.add(f"ramp_stability_{level}")
        gmsh.merge(str(step_path))
        gmsh.model.occ.synchronize()
        gmsh.model.occ.removeAllDuplicates()
        gmsh.model.occ.synchronize()

        vehicle_vols = [tag for _, tag in gmsh.model.getEntities(3)]

        # Farfield: sphere centred on the body, radius >= 15 body-diameters
        # (mesh_quality_checklist.md), extra downstream margin for the wake.
        centre_x_mm = (global_xmin_mm + global_xmax_mm) / 2.0
        farfield_radius_mm = max(15.0 * max_diameter_m * 1000.0, 5.0 * body_length_m * 1000.0)
        sphere = gmsh.model.occ.addSphere(
            centre_x_mm, 0.0, 0.0, farfield_radius_mm
        )
        gmsh.model.occ.synchronize()

        fluid, _ = gmsh.model.occ.cut(
            [(3, sphere)], [(3, t) for t in vehicle_vols], removeTool=True
        )
        gmsh.model.occ.synchronize()

        # --- Physical groups -------------------------------------------------
        surf_by_marker: dict[str, list[int]] = {m: [] for m in REQUIRED_MARKERS}
        for dim, tag in gmsh.model.getEntities(2):
            xmin, _, _, xmax, _, _ = gmsh.model.getBoundingBox(dim, tag)
            xc = (xmin + xmax) / 2.0
            up, _ = gmsh.model.getAdjacencies(dim, tag)
            if not up:  # farfield sphere surface (no parent solid)
                continue
            for name in REQUIRED_MARKERS:
                lo, hi = markers[name]
                if lo <= xc <= hi:
                    surf_by_marker[name].append(tag)
                    break

        for name, tags in surf_by_marker.items():
            if tags:
                pg = gmsh.model.addPhysicalGroup(2, tags)
                gmsh.model.setPhysicalName(2, pg, name)
            else:
                print(f"WARNING: no surfaces matched marker '{name}' — check "
                      f"marker_zones.yaml ranges.", file=sys.stderr)

        farfield_tags = [
            tag for dim, tag in gmsh.model.getEntities(2)
            if not gmsh.model.getAdjacencies(dim, tag)[0]
        ]
        if farfield_tags:
            pg = gmsh.model.addPhysicalGroup(2, farfield_tags)
            gmsh.model.setPhysicalName(2, pg, "farfield")

        vol_pg = gmsh.model.addPhysicalGroup(3, [v[1] for v in fluid])
        gmsh.model.setPhysicalName(3, vol_pg, "fluid")

        # --- Mesh sizing fields ------------------------------------------------
        wall_surfs = [
            tag for name in REQUIRED_MARKERS for tag in surf_by_marker[name]
        ]
        dist_field = gmsh.model.mesh.field.add("Distance")
        gmsh.model.mesh.field.setNumbers(dist_field, "SurfacesList", wall_surfs)

        base_size_mm = 20.0 * scale
        refined_size_mm = 2.0 * scale
        thresh_field = gmsh.model.mesh.field.add("Threshold")
        gmsh.model.mesh.field.setNumber(thresh_field, "InField", dist_field)
        gmsh.model.mesh.field.setNumber(thresh_field, "SizeMin", refined_size_mm)
        gmsh.model.mesh.field.setNumber(thresh_field, "SizeMax", base_size_mm)
        gmsh.model.mesh.field.setNumber(thresh_field, "DistMin", 5.0)
        gmsh.model.mesh.field.setNumber(thresh_field, "DistMax", 200.0)
        gmsh.model.mesh.field.setAsBackgroundMesh(thresh_field)

        # Boundary layer on wall markers, first-cell height from ISA/y+ calc.
        bl_field = gmsh.model.mesh.field.add("BoundaryLayer")
        gmsh.model.mesh.field.setNumbers(bl_field, "SurfacesList", wall_surfs)
        gmsh.model.mesh.field.setNumber(bl_field, "hwall_n", y1 * 1000.0)  # mm
        gmsh.model.mesh.field.setNumber(bl_field, "ratio", 1.2)
        gmsh.model.mesh.field.setNumber(bl_field, "thickness", 5.0 * scale)
        gmsh.model.mesh.field.setNumber(bl_field, "Quads", 0)
        gmsh.model.mesh.field.setAsBoundaryLayer(bl_field)

        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)

        gmsh.model.mesh.generate(3)

        out_path = out_dir / f"ramp_stability_{level}.su2"
        gmsh.write(str(out_path))
        print(f"y+={y_plus_target} first-cell height = {y1*1e6:.2f} um "
              f"at Mach {mach}, altitude {altitude_m} m")
        print(f"Wrote {out_path}")
        return out_path
    finally:
        gmsh.finalize()


def _main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("step_file", type=Path)
    p.add_argument("--classify-only", action="store_true")
    p.add_argument("--level", choices=["coarse", "fine"], default="coarse")
    p.add_argument("--mach", type=float, default=2.5)
    p.add_argument("--altitude-m", type=float, default=10000.0)
    p.add_argument("--y-plus", type=float, default=1.0)
    p.add_argument("--zones", type=Path, default=None)
    a = p.parse_args()

    inventory_dir = CASE_ROOT / "mesh" / "inventory"
    if a.classify_only:
        classify_only(a.step_file, inventory_dir)
        return

    zones_path = a.zones or (Path(__file__).resolve().parent / "marker_zones.yaml")
    build_mesh(
        a.step_file,
        zones_path,
        CASE_ROOT / "mesh",
        a.level,
        a.mach,
        a.altitude_m,
        a.y_plus,
    )


if __name__ == "__main__":
    _main()
