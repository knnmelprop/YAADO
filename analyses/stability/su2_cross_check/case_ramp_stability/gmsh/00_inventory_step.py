# MELprop-IADE | gmsh STEP geometry inventory | v0.1.0
"""Inventory a STEP file's volumes and surfaces via the Gmsh OCC kernel.

Read-only reconnaissance step. Produces two CSVs (volumes, surfaces) under
``mesh/inventory/`` for human review — this repo's convention is to never
guess safety-adjacent geometry identity (which solid is which rocket stage,
where the interstage boundary sits) from bounding boxes alone. Run this
first, inspect the STEP visually (Gmsh GUI or Fusion) or cross-reference
``vehicles/ramjet_rocket/vehicle_config.yaml``, then fill in
``gmsh/marker_zones.yaml`` before running ``01_classify_and_mesh.py``.

Requires the ``gmsh`` Python module (see ``requirements-gmsh.txt``); it is
NOT the same as the Homebrew ``gmsh`` CLI package, which does not ship the
Python bindings. Install into a dedicated venv, e.g.::

    python3 -m venv .venv-gmsh && .venv-gmsh/bin/pip install -r gmsh/requirements-gmsh.txt
    .venv-gmsh/bin/python3 gmsh/00_inventory_step.py cad/<file>.step

Usage:
    python3 00_inventory_step.py <path/to/model.step>
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import gmsh


def inventory(step_path: Path, out_dir: Path) -> None:
    """Load a STEP file and write volume/surface bounding-box CSVs.

    Args:
        step_path: Path to the STEP file to inspect.
        out_dir: Directory to write ``volumes.csv`` and ``surfaces.csv`` into
            (created if missing).

    Raises:
        FileNotFoundError: If ``step_path`` does not exist.
    """
    if not step_path.is_file():
        raise FileNotFoundError(step_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    try:
        gmsh.model.add("inventory")
        gmsh.merge(str(step_path))
        gmsh.model.occ.synchronize()

        vols = gmsh.model.getEntities(3)
        vol_rows = []
        for dim, tag in vols:
            xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(dim, tag)
            volume_mm3 = gmsh.model.occ.getMass(dim, tag)
            max_radius_mm = max(
                (ymax - ymin) / 2.0, (zmax - zmin) / 2.0, (ymax * 0 + 1e-9)
            )
            vol_rows.append(
                {
                    "vol_tag": tag,
                    "x_min_mm": xmin,
                    "x_max_mm": xmax,
                    "y_min_mm": ymin,
                    "y_max_mm": ymax,
                    "z_min_mm": zmin,
                    "z_max_mm": zmax,
                    "approx_max_radius_mm": max(
                        (ymax - ymin) / 2.0, (zmax - zmin) / 2.0
                    ),
                    "volume_mm3": volume_mm3,
                }
            )

        surfs = gmsh.model.getEntities(2)
        global_xmin = min(r["x_min_mm"] for r in vol_rows)
        global_xmax = max(r["x_max_mm"] for r in vol_rows)
        surf_rows = []
        for dim, tag in surfs:
            xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(dim, tag)
            area_mm2 = gmsh.model.occ.getMass(dim, tag)
            up, _down = gmsh.model.getAdjacencies(dim, tag)
            parent_vol = up[0] if len(up) else -1
            # Cap-candidate heuristic: near-planar in X (thin X-extent) AND
            # sitting at the global assembly extreme. This is a geometric
            # observation, not an identity assignment — confirm visually.
            x_extent = xmax - xmin
            near_global_end = (
                abs(xmin - global_xmin) < 5.0 or abs(xmax - global_xmax) < 5.0
            )
            cap_candidate = x_extent < 1.0 and near_global_end
            surf_rows.append(
                {
                    "surf_tag": tag,
                    "parent_vol": parent_vol,
                    "x_min_mm": xmin,
                    "x_max_mm": xmax,
                    "y_min_mm": ymin,
                    "y_max_mm": ymax,
                    "z_min_mm": zmin,
                    "z_max_mm": zmax,
                    "area_mm2": area_mm2,
                    "cap_candidate": cap_candidate,
                }
            )

        _write_csv(out_dir / "volumes.csv", vol_rows)
        _write_csv(out_dir / "surfaces.csv", surf_rows)

        print(f"Volumes: {len(vol_rows)}  Surfaces: {len(surf_rows)}")
        for r in vol_rows:
            print(
                f"  vol {r['vol_tag']}: x=({r['x_min_mm']:.1f},{r['x_max_mm']:.1f}) "
                f"max_radius={r['approx_max_radius_mm']:.1f} mm "
                f"volume={r['volume_mm3']/1e9:.6f} m^3"
            )
        n_caps = sum(1 for r in surf_rows if r["cap_candidate"])
        print(f"  cap-candidate surfaces (near assembly ends): {n_caps}")
        print(f"Wrote {out_dir/'volumes.csv'} and {out_dir/'surfaces.csv'}")
    finally:
        gmsh.finalize()


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path/to/model.step>", file=sys.stderr)
        raise SystemExit(2)
    step_file = Path(sys.argv[1])
    inventory(step_file, step_file.resolve().parents[1] / "mesh" / "inventory")
