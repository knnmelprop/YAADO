# MELprop-IADE | analyses.geometry.cad_station_sweep | v0.1.0
"""Production STEP cross-section station sweep.

For a real STEP assembly, sweeps a series of axial (X) stations along the
vehicle, boolean-intersects a Y-Z cutting plane against each solid volume at
every station (the method prototyped and confirmed in ``probe_slice.py``,
sped up ~30x in ``probe_slice_v2_timing.py`` by intersecting directly
against the original volume instead of a full deep copy -- see
``docs/geometry/status.md`` sections 1 and 4b), and additionally classifies
each resulting cross-section face's boundary-curve topology into loops to
detect internal holes/bores (``docs/geometry/status.md`` section 4, the
concrete next step after the timing prototype).

Module layout
-------------
This module is deliberately split into two halves:

- **Pure-Python helpers** (:func:`equivalent_diameter_from_area`,
  :func:`group_curves_into_loops`, :func:`classify_face_loops`,
  :func:`cross_check_against_vehicle_config`) have no ``gmsh``/STEP
  dependency and are unit-tested directly with hand-built synthetic data in
  ``tests/unit/test_geometry_station_sweep.py``.
- **gmsh/STEP-dependent driver functions** (:func:`open_step`,
  :func:`slice_volume_at_station`, :func:`run_station_sweep`) call into the
  ``gmsh`` OCC kernel and require a real STEP file. ``gmsh`` is imported
  lazily inside these functions so the pure-Python half of this module
  stays importable in environments without ``gmsh`` installed (same
  guarded-import convention as SUAVE imports elsewhere in this repo's
  ``core/`` package).

**No real STEP file is committed to this repo** (the actual vehicle CAD,
``analyses/stability/su2_cross_check/case_ramp_stability/cad/
ramPcfdSimplified.step``, is intentionally gitignored -- raw CAD/mesh data
is never committed, per project convention). Running this tool against the
real geometry, and resolving the ramjet-vs-booster solid-identity question
it can help settle (``docs/geometry/status.md`` section 3), both require a
local session with that file. See ``docs/geometry/status.md`` for the full
status and next-step plan.

CLI usage (from a venv with ``gmsh`` installed, e.g. ``.venv-geom``)::

    .venv-geom/bin/python3 -m analyses.geometry.cad_station_sweep \\
        path/to/model.step \\
        --x-start-mm 0 --x-end-mm 4355 --pitch-mm 20 \\
        --output-csv analyses/geometry/results/station_sweep.csv \\
        --vehicle-config Hangar/ramjet_rocket/vehicle_config.yaml
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

#: Half-extent (mm) of the square cutting-plane rectangle built at each
#: station; must exceed the largest expected cross-section radius. Matches
#: the ``R = 400.0`` value used in ``probe_slice.py`` /
#: ``probe_slice_v2_timing.py`` (generous vs. the observed max radius of
#: ~296.5mm on the real ramP assembly).
DEFAULT_HALF_EXTENT_MM: float = 400.0

#: Output CSV column order, matching ``docs/geometry/status.md`` section 4's
#: spec exactly.
CSV_COLUMNS: tuple[str, ...] = (
    "x_mm",
    "vol_tag",
    "area_mm2",
    "n_loops",
    "outer_r_eq_mm",
    "outer_bbox_r_mm",
    "has_inner_loop",
    "inner_area_mm2",
    "inner_r_eq_mm",
)

#: Repository root, resolved from this file's location (matches the
#: convention in ``analyses/geometry/openvsp_export.py``).
REPO_ROOT: Path = Path(__file__).resolve().parents[4]


# ---------------------------------------------------------------------------
# Pure-Python helpers -- no gmsh / STEP dependency, unit-testable directly.
# ---------------------------------------------------------------------------


def equivalent_diameter_from_area(area_mm2: float) -> float:
    """Compute the diameter of a circle with the same area.

    Args:
        area_mm2: Cross-section area in mm^2 (>= 0).

    Returns:
        Equivalent diameter in mm, ``d = 2 * sqrt(area / pi)``. Returns
        ``0.0`` for non-positive input rather than raising, since a
        degenerate (outside-the-solid) station legitimately has zero area.
    """
    if area_mm2 <= 0.0:
        return 0.0
    return 2.0 * math.sqrt(area_mm2 / math.pi)


def group_curves_into_loops(
    curve_edges: Sequence[tuple[int, tuple[int, int]]],
) -> list[list[int]]:
    """Group a face's boundary curves into closed wire loops.

    Two curves belong to the same loop if they are connected via a chain of
    shared endpoint points -- built as a union-find graph over point tags,
    per ``docs/geometry/status.md`` section 4's exact spec. A full circular
    curve (gmsh reports these as a single curve whose two endpoints are the
    same point tag) forms a loop by itself.

    Args:
        curve_edges: One ``(curve_tag, (point_a, point_b))`` pair per
            boundary curve of a single face.

    Returns:
        One list of curve tags per closed loop found (order of loops and
        of curve tags within a loop is not significant to callers, who
        should extract points/extent, not depend on ordering).
    """
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for _curve_tag, (point_a, point_b) in curve_edges:
        union(point_a, point_b)

    loops_by_root: dict[int, list[int]] = {}
    for curve_tag, (point_a, _point_b) in curve_edges:
        root = find(point_a)
        loops_by_root.setdefault(root, []).append(curve_tag)

    return list(loops_by_root.values())


@dataclass(frozen=True)
class LoopTopology:
    """Classified loop topology for one face's boundary curves.

    Attributes:
        n_loops: Number of independent closed wire loops found. ``1`` means
            a simply-connected face (solid disc, or a thin/star shape with
            no hole); ``> 1`` means at least one inner boundary loop (an
            internal void/bore) is present.
        has_inner_loop: ``n_loops > 1``.
        outer_curves: Curve tags of the largest-extent (outer) loop.
        inner_loops: Curve-tag lists of the remaining loops, ordered by
            descending extent (largest inner loop first).
        outer_bbox_r_mm: Max radial distance (from the station axis, i.e.
            the Y-Z plane origin) of any point on the outer loop.
        inner_bbox_r_mm: Max radial distance of any point on the largest
            inner loop, or ``0.0`` if there is no inner loop. Since only
            the outer face's net area is measurable via ``getMass`` (holes
            are not separately-tagged faces), this extent is used directly
            as the bore radius estimate, per
            ``docs/geometry/status.md`` section 4 ("compute the inner
            loop's own extent ... to get the internal bore diameter
            directly").
    """

    n_loops: int
    has_inner_loop: bool
    outer_curves: list[int]
    inner_loops: list[list[int]]
    outer_bbox_r_mm: float
    inner_bbox_r_mm: float


def classify_face_loops(
    curve_edges: Sequence[tuple[int, tuple[int, int]]],
    point_coords: Mapping[int, tuple[float, float]],
) -> LoopTopology:
    """Classify a face's boundary loops into outer vs. inner (hole) loops.

    The loop with the largest point-extent (max radial distance from the
    station axis) is the outer boundary; every other loop is an inner
    (hole) boundary. This disambiguates "one simply-connected face" from
    "a face with an inner boundary loop" -- the exact ambiguity flagged in
    ``docs/geometry/status.md`` section 3, where a hollow-tube cross
    section and a thin fin-blade cross section both produce a low
    area/bbox-disc ratio and cannot be told apart from area + bbox alone.

    Args:
        curve_edges: One ``(curve_tag, (point_a, point_b))`` pair per
            boundary curve of the face, as accepted by
            :func:`group_curves_into_loops`.
        point_coords: Map of point tag -> ``(y_mm, z_mm)``, station-local
            coordinates (X is the station's own axial position, already
            projected out).

    Returns:
        A :class:`LoopTopology`. If ``curve_edges`` is empty, returns a
        topology with ``n_loops=0``.
    """
    loops = group_curves_into_loops(curve_edges)
    if not loops:
        return LoopTopology(0, False, [], [], 0.0, 0.0)

    points_by_curve: dict[int, tuple[int, int]] = dict(curve_edges)

    def loop_extent_mm(curves: list[int]) -> float:
        radii = []
        for curve_tag in curves:
            for point_tag in points_by_curve[curve_tag]:
                coord = point_coords.get(point_tag)
                if coord is not None:
                    radii.append(math.hypot(coord[0], coord[1]))
        return max(radii) if radii else 0.0

    loops_by_extent = sorted(
        ((loop_extent_mm(curves), curves) for curves in loops),
        key=lambda item: item[0],
        reverse=True,
    )
    outer_extent_mm, outer_curves = loops_by_extent[0]
    inner = loops_by_extent[1:]

    return LoopTopology(
        n_loops=len(loops),
        has_inner_loop=len(inner) > 0,
        outer_curves=outer_curves,
        inner_loops=[curves for _extent, curves in inner],
        outer_bbox_r_mm=outer_extent_mm,
        inner_bbox_r_mm=inner[0][0] if inner else 0.0,
    )


@dataclass(frozen=True)
class CrossCheckResult:
    """One MATCH/MISMATCH comparison between sweep data and vehicle_config.yaml.

    Attributes:
        metric: Short name of the compared quantity.
        extracted_mm: Value derived from the sweep rows, in mm.
        config_mm: Corresponding value from ``vehicle_config.yaml``, in mm.
        diff_pct: ``abs(extracted - config) / config * 100``.
        verdict: ``"MATCH"`` if ``diff_pct <= tolerance_pct``, else
            ``"MISMATCH"``.
    """

    metric: str
    extracted_mm: float
    config_mm: float
    diff_pct: float
    verdict: str


def cross_check_against_vehicle_config(
    rows: Sequence[Mapping[str, object]],
    vehicle_config_path: str | Path,
    tolerance_pct: float = 10.0,
) -> list[CrossCheckResult]:
    """Compare sweep-derived envelope numbers against ``vehicle_config.yaml``.

    Report-only, per explicit instruction: this never modifies the YAML or
    the sweep rows, it only flags MATCH/MISMATCH for a human to act on.
    Three checks, each skipped if the relevant config field is absent:

    - Max ``outer_bbox_r_mm`` across all rows vs. half of
      ``body.max_diameter_m``.
    - Axial extent (``max(x_mm) - min(x_mm)``) vs.
      ``body.total_length_m`` (falling back to ``body.length_m``).
    - Median ``outer_bbox_r_mm`` among rows aft of the nose (``x_mm >
      nose_length_mm``) vs. half of ``body.diameter_m`` (the cylindrical
      body section's nominal radius).

    Args:
        rows: Sweep rows as produced by :func:`run_station_sweep` (or any
            mapping sequence with at least ``x_mm`` and ``outer_bbox_r_mm``
            keys).
        vehicle_config_path: Path to a ``RocketConfig`` YAML (Project B's
            ``Hangar/ramjet_rocket/vehicle_config.yaml``).
        tolerance_pct: Max allowed percent deviation before a check is
            flagged MISMATCH.

    Returns:
        One :class:`CrossCheckResult` per check that had data to compare
        (empty list if ``rows`` is empty).

    Raises:
        TypeError: If ``vehicle_config_path`` does not load as a
            ``RocketConfig`` (e.g. the GTM-140 drone config was passed).
    """
    from Hangar.ramjet_rocket.rocket_schema import RocketConfig
    from pydantic import ValidationError

    try:
        config = RocketConfig.from_yaml(vehicle_config_path)
    except ValidationError as e:
        raise TypeError(
            f"{vehicle_config_path} did not load as a RocketConfig "
            f"({e}); this cross-check is for Project B only"
        )

    if not rows:
        return []

    results: list[CrossCheckResult] = []

    def _check(metric: str, extracted_mm: float, config_mm: float | None) -> None:
        if config_mm is None or config_mm <= 0.0:
            return
        diff_pct = abs(extracted_mm - config_mm) / config_mm * 100.0
        verdict = "MATCH" if diff_pct <= tolerance_pct else "MISMATCH"
        results.append(CrossCheckResult(metric, extracted_mm, config_mm, diff_pct, verdict))

    body = config.body
    max_bbox_r_mm = max(float(row["outer_bbox_r_mm"]) for row in rows)
    config_max_r_mm = body.max_diameter_m * 1000.0 / 2.0 if body.max_diameter_m else None
    _check("max_radius_mm", max_bbox_r_mm, config_max_r_mm)

    x_values_mm = [float(row["x_mm"]) for row in rows]
    sweep_length_mm = max(x_values_mm) - min(x_values_mm)
    total_length_m = body.total_length_m or body.length_m
    _check("axial_extent_mm", sweep_length_mm, total_length_m * 1000.0)

    nose_length_mm = (body.nose_length_m or 0.0) * 1000.0
    cylindrical_rows = [row for row in rows if float(row["x_mm"]) > nose_length_mm]
    if cylindrical_rows:
        body_radii_mm = sorted(float(row["outer_bbox_r_mm"]) for row in cylindrical_rows)
        median_body_r_mm = body_radii_mm[len(body_radii_mm) // 2]
        _check(
            "cylindrical_body_radius_mm",
            median_body_r_mm,
            body.diameter_m * 1000.0 / 2.0,
        )

    return results


# ---------------------------------------------------------------------------
# gmsh / STEP-dependent driver functions -- require a real .step file.
# ---------------------------------------------------------------------------


def open_step(step_path: str | Path) -> list[int]:
    """Initialize gmsh and merge a STEP file, returning its solid volume tags.

    ``gmsh`` is imported lazily so this module stays importable without it.

    Args:
        step_path: Path to the ``.step``/``.stp`` CAD file.

    Returns:
        Volume tags for every 3D solid entity found (e.g. ``[1, 2]`` for
        the real ramP assembly's two solids, per
        ``docs/geometry/status.md`` section 1).

    Note:
        Caller owns the resulting gmsh session and must eventually call
        ``gmsh.finalize()`` -- :func:`run_station_sweep` does this
        automatically.
    """
    import gmsh

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("cad_station_sweep")
    gmsh.merge(str(step_path))
    gmsh.model.occ.synchronize()
    return [tag for _dim, tag in gmsh.model.getEntities(3)]


def _face_boundary_graph(
    face_tag: int,
) -> tuple[list[tuple[int, tuple[int, int]]], dict[int, tuple[float, float]]]:
    """Walk one face's curve/point adjacency into loop-classifier input.

    Uses ``gmsh.model.getAdjacencies(2, face_tag)`` for the face's
    bounding curves and ``gmsh.model.getAdjacencies(1, curve_tag)`` for
    each curve's endpoint points, per ``docs/geometry/status.md`` section
    4's exact spec.

    Args:
        face_tag: A gmsh 2D (face) entity tag, already in the current
            model (an active gmsh session is assumed).

    Returns:
        ``(curve_edges, point_coords)`` ready to pass to
        :func:`classify_face_loops`; ``point_coords`` values are
        ``(y_mm, z_mm)`` (the X/station coordinate is dropped).
    """
    import gmsh

    _up, curve_tags = gmsh.model.getAdjacencies(2, face_tag)
    curve_edges: list[tuple[int, tuple[int, int]]] = []
    point_coords: dict[int, tuple[float, float]] = {}
    for curve_tag in curve_tags:
        _curve_up, point_tags = gmsh.model.getAdjacencies(1, int(curve_tag))
        point_a, point_b = int(point_tags[0]), int(point_tags[-1])
        curve_edges.append((int(curve_tag), (point_a, point_b)))
        for point_tag in (point_a, point_b):
            if point_tag not in point_coords:
                coord = gmsh.model.getValue(0, point_tag, [])
                point_coords[point_tag] = (float(coord[1]), float(coord[2]))
    return curve_edges, point_coords


def slice_volume_at_station(
    vol_tag: int,
    x_mm: float,
    half_extent_mm: float = DEFAULT_HALF_EXTENT_MM,
) -> list[dict]:
    """Cut ``vol_tag`` with a Y-Z plane at ``x_mm`` and analyze each face.

    Reuses the plane-intersection method confirmed in ``probe_slice.py``
    (build a rectangle, rotate into the Y-Z plane, translate to the
    station, intersect against the solid), with the ~30x-faster variant
    from ``probe_slice_v2_timing.py``: only the cutting plane is copied
    (``gmsh.model.occ.copy``); the intersect runs directly against the
    original volume with ``removeObject=False`` instead of deep-copying
    the full solid's B-Rep every station. Adds the loop/hole topology
    classification (``docs/geometry/status.md`` section 4's next step) on
    top of that confirmed method.

    Produced faces and the cutting plane are removed before returning so
    gmsh entity tags do not accumulate across stations, matching both
    prototype scripts' cleanup behavior.

    Args:
        vol_tag: A gmsh 3D (volume) entity tag from :func:`open_step`.
        x_mm: Station axial position (STEP frame, X = vehicle longitudinal
            axis), in mm.
        half_extent_mm: Half-extent of the square cutting plane; must
            exceed the largest expected cross-section radius.

    Returns:
        One dict (``{"area_mm2": float, "topology": LoopTopology}``) per
        cross-section face produced at this station for this volume.
        Empty if the station is outside the volume's axial extent.
    """
    import gmsh

    rect = gmsh.model.occ.addRectangle(
        -half_extent_mm, -half_extent_mm, 0, 2 * half_extent_mm, 2 * half_extent_mm
    )
    gmsh.model.occ.rotate([(2, rect)], 0, 0, 0, 0, 1, 0, math.pi / 2)
    gmsh.model.occ.translate([(2, rect)], x_mm, 0, 0)
    gmsh.model.occ.synchronize()

    plane_copy = gmsh.model.occ.copy([(2, rect)])
    gmsh.model.occ.synchronize()
    produced, _ = gmsh.model.occ.intersect(
        [(3, vol_tag)], plane_copy, removeObject=False, removeTool=True
    )
    gmsh.model.occ.synchronize()

    faces = [tag for dim, tag in produced if dim == 2]
    results: list[dict] = []
    for face_tag in faces:
        area_mm2 = gmsh.model.occ.getMass(2, face_tag)
        curve_edges, point_coords = _face_boundary_graph(face_tag)
        topology = classify_face_loops(curve_edges, point_coords)
        results.append({"area_mm2": area_mm2, "topology": topology})

    if produced:
        gmsh.model.occ.remove(produced, recursive=True)
    gmsh.model.occ.remove([(2, rect)], recursive=True)
    gmsh.model.occ.synchronize()
    return results


def _build_row(x_mm: float, vol_tag: int, area_mm2: float, topology: LoopTopology) -> dict:
    """Assemble one CSV-ready row from a sliced face's area + topology.

    ``outer_r_eq_mm`` is the equivalent radius of the face's own measured
    (net) area -- the same quantity ``probe_slice.py`` printed as ``r_eq``,
    disambiguated here from the new ``inner_r_eq_mm`` column.
    ``inner_r_eq_mm``/``inner_area_mm2`` are estimated by treating the
    largest inner loop's own point-extent as the bore radius directly (see
    :class:`LoopTopology`'s ``inner_bbox_r_mm`` docstring) since no separate
    inner face is available to measure area from.
    """
    outer_r_eq_mm = equivalent_diameter_from_area(area_mm2) / 2.0
    inner_r_eq_mm = topology.inner_bbox_r_mm if topology.has_inner_loop else 0.0
    inner_area_mm2 = math.pi * inner_r_eq_mm**2 if topology.has_inner_loop else 0.0
    return {
        "x_mm": x_mm,
        "vol_tag": vol_tag,
        "area_mm2": area_mm2,
        "n_loops": topology.n_loops,
        "outer_r_eq_mm": outer_r_eq_mm,
        "outer_bbox_r_mm": topology.outer_bbox_r_mm,
        "has_inner_loop": topology.has_inner_loop,
        "inner_area_mm2": inner_area_mm2,
        "inner_r_eq_mm": inner_r_eq_mm,
    }


def run_station_sweep(
    step_path: str | Path,
    x_start_mm: float,
    x_end_mm: float,
    pitch_mm: float,
    half_extent_mm: float = DEFAULT_HALF_EXTENT_MM,
) -> list[dict]:
    """Run the full station sweep against a real STEP file.

    Opens the STEP file once, walks every station in
    ``[x_start_mm, x_end_mm]`` at ``pitch_mm`` spacing for every solid
    volume, and always finalizes the gmsh session (even on error).

    Args:
        step_path: Path to the ``.step``/``.stp`` CAD file.
        x_start_mm: First station's axial position, mm.
        x_end_mm: Last station's axial position, mm (inclusive, subject to
            rounding to a whole number of ``pitch_mm`` steps).
        pitch_mm: Spacing between consecutive stations, mm (> 0).
        half_extent_mm: Half-extent of the square cutting plane; must
            exceed the largest expected cross-section radius.

    Returns:
        One row (dict, keys matching :data:`CSV_COLUMNS`) per
        station x volume x face.

    Raises:
        ValueError: If ``pitch_mm <= 0`` or ``x_end_mm < x_start_mm``.
    """
    if pitch_mm <= 0.0:
        raise ValueError("pitch_mm must be > 0")
    if x_end_mm < x_start_mm:
        raise ValueError("x_end_mm must be >= x_start_mm")

    import gmsh

    vol_tags = open_step(step_path)
    rows: list[dict] = []
    try:
        n_stations = int(round((x_end_mm - x_start_mm) / pitch_mm)) + 1
        for i in range(n_stations):
            x_mm = x_start_mm + i * pitch_mm
            for vol_tag in vol_tags:
                for face in slice_volume_at_station(vol_tag, x_mm, half_extent_mm):
                    rows.append(_build_row(x_mm, vol_tag, face["area_mm2"], face["topology"]))
    finally:
        gmsh.finalize()
    return rows


def write_csv(rows: Sequence[Mapping[str, object]], output_path: str | Path) -> Path:
    """Write sweep rows to CSV using the :data:`CSV_COLUMNS` order.

    Args:
        rows: Rows as produced by :func:`run_station_sweep`.
        output_path: Destination CSV path (parent directories created).

    Returns:
        The resolved output path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row[column] for column in CSV_COLUMNS})
    return output_path


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point: run a station sweep and write it to CSV.

    Args:
        argv: Argument vector (``sys.argv[1:]`` if omitted).

    Returns:
        Process exit code (``0`` on success).
    """
    parser = argparse.ArgumentParser(
        description=(
            "Sweep a STEP CAD file's cross-section area + loop/hole "
            "topology at axial stations."
        )
    )
    parser.add_argument("step_path", type=Path, help="Path to the .step CAD file")
    parser.add_argument("--x-start-mm", type=float, required=True)
    parser.add_argument("--x-end-mm", type=float, required=True)
    parser.add_argument("--pitch-mm", type=float, required=True)
    parser.add_argument(
        "--half-extent-mm", type=float, default=DEFAULT_HALF_EXTENT_MM
    )
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument(
        "--vehicle-config",
        type=Path,
        default=None,
        help="Optional vehicle_config.yaml for a MATCH/MISMATCH cross-check",
    )
    parser.add_argument("--tolerance-pct", type=float, default=10.0)
    args = parser.parse_args(argv)

    if not args.step_path.is_file():
        parser.error(f"STEP file not found: {args.step_path}")

    rows = run_station_sweep(
        args.step_path, args.x_start_mm, args.x_end_mm, args.pitch_mm, args.half_extent_mm
    )
    output_path = write_csv(rows, args.output_csv)
    print(f"Wrote {len(rows)} rows to {output_path}")

    if args.vehicle_config is not None:
        checks = cross_check_against_vehicle_config(rows, args.vehicle_config, args.tolerance_pct)
        for check in checks:
            print(
                f"[{check.verdict}] {check.metric}: "
                f"extracted={check.extracted_mm:.2f}mm "
                f"config={check.config_mm:.2f}mm "
                f"diff={check.diff_pct:.1f}%"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
