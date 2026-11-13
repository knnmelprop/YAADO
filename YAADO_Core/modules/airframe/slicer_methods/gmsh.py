"""Gmsh STEP cross-section station sweep.

Sweeps axial (X) stations along a STEP assembly, intersects a Y-Z plane with
each solid volume and classifies each face's boundary loops to detect inner
bores. :class:`GmshStationSweepAnalysis` wraps the sweep as a
:class:`BaseAnalysis`. ``gmsh`` is imported lazily inside the driver
functions, so the pure-Python helpers work without it.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from YAADO_Core.ComponentStore import BODY_COMPONENTS, AnyBodyComponent
from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.airframe.containers import (
    EnvelopeCheck,
    GmshSliceResults,
    StationSlice,
)

MM_PER_M: float = 1000.0

#: Half-extent (mm) of the square cutting plane built at each station; must
#: exceed the largest expected cross-section radius.
DEFAULT_HALF_EXTENT_MM: float = 400.0

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


def cross_check_against_body(
    stations: Sequence[StationSlice],
    body: AnyBodyComponent,
    tolerance_pct: float = 10.0,
) -> tuple[EnvelopeCheck, ...]:
    """Compare sweep-derived envelope lengths against a vehicle body component.

    Report-only: flags MATCH/MISMATCH, never modifies anything. Checks are
    skipped when the relevant body field is unset.

    Args:
        stations: Sweep slices (SI units).
        body: Body component from the vehicle config.
        tolerance_pct: Max percent deviation before a check is a MISMATCH.

    Returns:
        One :class:`EnvelopeCheck` per check with data (empty if no stations).
    """
    if not stations:
        return ()

    checks: list[EnvelopeCheck] = []

    def _check(metric: str, extracted: float, reference: float | None) -> None:
        if reference is None or reference <= 0.0:
            return
        diff_pct = abs(extracted - reference) / reference * 100.0
        verdict = "MATCH" if diff_pct <= tolerance_pct else "MISMATCH"
        checks.append(EnvelopeCheck(metric, extracted, reference, diff_pct, verdict))

    max_diameter = body.max_diameter
    _check(
        "max_radius",
        max(s.outer_bbox_radius for s in stations),
        max_diameter / 2.0 if max_diameter else None,
    )
    xs = [s.x for s in stations]
    _check("axial_extent", max(xs) - min(xs), body.total_length or body.length)

    nose_length = body.nose_length or 0.0
    aft_radii = sorted(s.outer_bbox_radius for s in stations if s.x > nose_length)
    if aft_radii:
        _check("cylindrical_body_radius", aft_radii[len(aft_radii) // 2], body.diameter / 2.0)

    return tuple(checks)


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
        the real vehicle assembly's two solids, per
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
) -> list[StationSlice]:
    """Cut ``vol_tag`` with a Y-Z plane at ``x_mm`` and analyze each face.

    Only the cutting plane is copied; the intersect runs against the
    original volume with ``removeObject=False`` (much faster than copying
    the solid). Produced faces and the plane are removed before returning
    so gmsh tags do not accumulate across stations.

    Args:
        vol_tag: A gmsh 3D (volume) entity tag from :func:`open_step`.
        x_mm: Station axial position (STEP frame, X = vehicle longitudinal
            axis), in mm.
        half_extent_mm: Half-extent of the square cutting plane; must
            exceed the largest expected cross-section radius.

    Returns:
        One :class:`StationSlice` (SI units) per cross-section face at this
        station. Empty if the station is outside the volume's axial extent.
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
    results: list[StationSlice] = []
    for face_tag in faces:
        area_mm2 = gmsh.model.occ.getMass(2, face_tag)
        curve_edges, point_coords = _face_boundary_graph(face_tag)
        topology = classify_face_loops(curve_edges, point_coords)
        results.append(build_station_slice(x_mm, vol_tag, area_mm2, topology))

    if produced:
        gmsh.model.occ.remove(produced, recursive=True)
    gmsh.model.occ.remove([(2, rect)], recursive=True)
    gmsh.model.occ.synchronize()
    return results


def build_station_slice(
    x_mm: float, vol_tag: int, area_mm2: float, topology: LoopTopology
) -> StationSlice:
    """Convert one sliced face (mm, mm^2) into an SI :class:`StationSlice`.

    The inner area/radius are estimated from the largest inner loop's extent
    (see :class:`LoopTopology`), since no separate inner face is measurable.
    """
    outer_r_eq_mm = equivalent_diameter_from_area(area_mm2) / 2.0
    inner_r_mm = topology.inner_bbox_r_mm if topology.has_inner_loop else 0.0
    return StationSlice(
        x=x_mm / MM_PER_M,
        volume_tag=vol_tag,
        area=area_mm2 / MM_PER_M**2,
        n_loops=topology.n_loops,
        outer_equivalent_radius=outer_r_eq_mm / MM_PER_M,
        outer_bbox_radius=topology.outer_bbox_r_mm / MM_PER_M,
        has_inner_loop=topology.has_inner_loop,
        inner_area=math.pi * (inner_r_mm / MM_PER_M) ** 2,
        inner_equivalent_radius=inner_r_mm / MM_PER_M,
    )


def run_station_sweep(
    step_path: str | Path,
    x_start: float,
    x_end: float,
    pitch: float,
    half_extent: float = DEFAULT_HALF_EXTENT_MM / MM_PER_M,
) -> list[StationSlice]:
    """Run the full station sweep against a STEP file.

    Opens the STEP file once, walks every station in ``[x_start, x_end]`` at
    ``pitch`` spacing for every solid volume, and always finalizes gmsh.

    Args:
        step_path: Path to the ``.step``/``.stp`` file (assumed in mm).
        x_start: First station's axial position, m.
        x_end: Last station's axial position, m (inclusive, rounded to a
            whole number of ``pitch`` steps).
        pitch: Station spacing, m (> 0).
        half_extent: Half-extent of the square cutting plane, m; must exceed
            the largest expected cross-section radius.

    Returns:
        One :class:`StationSlice` per station x volume x face.

    Raises:
        ValueError: If ``pitch <= 0`` or ``x_end < x_start``.
    """
    if pitch <= 0.0:
        raise ValueError("pitch must be > 0")
    if x_end < x_start:
        raise ValueError("x_end must be >= x_start")

    import gmsh

    vol_tags = open_step(step_path)
    slices: list[StationSlice] = []
    try:
        n_stations = round((x_end - x_start) / pitch) + 1
        for i in range(n_stations):
            x_mm = (x_start + i * pitch) * MM_PER_M
            for vol_tag in vol_tags:
                slices.extend(
                    slice_volume_at_station(vol_tag, x_mm, half_extent * MM_PER_M)
                )
    finally:
        gmsh.finalize()
    return slices


class GmshStationSweepAnalysis(BaseAnalysis[GmshSliceResults]):
    """Gmsh STEP cross-section station sweep.

    Slices a STEP assembly at axial stations and reports area, equivalent
    radius and inner-bore estimates per station. Geometry-derived, no
    physics solver -> ``FidelityLevel.LEVEL_0``. Requires ``gmsh`` at
    :meth:`execute` time only.

    Example:
        analysis = GmshStationSweepAnalysis()
        analysis.setup(vehicle, step_path="model.step", x_start=0.0, x_end=4.0, pitch=0.02)
        results = analysis.execute()
    """

    fidelity = FidelityLevel.LEVEL_0

    DEFAULT_TOLERANCE_PCT: float = 10.0

    def __init__(self, name: str = "gmsh_station_sweep") -> None:
        super().__init__(name)
        self._step_path: Path | None = None
        self._x_start: float = 0.0
        self._x_end: float = 0.0
        self._pitch: float = 0.0
        self._half_extent: float = DEFAULT_HALF_EXTENT_MM / MM_PER_M
        self._tolerance_pct: float = self.DEFAULT_TOLERANCE_PCT
        self._body: AnyBodyComponent | None = None

    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        step_path: str | Path | None = None,
        x_start: float = 0.0,
        x_end: float | None = None,
        pitch: float | None = None,
        half_extent: float = DEFAULT_HALF_EXTENT_MM / MM_PER_M,
        body_name: str | None = None,
        tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
        **kwargs: Any,
    ) -> None:
        """Bind the sweep range and, if the vehicle has one, a body for cross-checks.

        Args:
            vehicle: Vehicle config; its body (if any) is used for the envelope check.
            step_path: Path to the STEP file (required).
            x_start: First station, m.
            x_end: Last station, m (required).
            pitch: Station spacing, m (required, > 0).
            half_extent: Cutting-plane half-extent, m.
            body_name: Body to check against when the vehicle has several.
            tolerance_pct: MATCH/MISMATCH tolerance in percent.

        Raises:
            ValueError: If a required argument is missing, ``pitch <= 0`` or
                ``x_end < x_start``.
        """
        if step_path is None or x_end is None or pitch is None:
            raise ValueError("step_path, x_end and pitch are required")
        if pitch <= 0.0:
            raise ValueError("pitch must be > 0")
        if x_end < x_start:
            raise ValueError("x_end must be >= x_start")

        self._step_path = Path(step_path)
        self._x_start, self._x_end, self._pitch = x_start, x_end, pitch
        self._half_extent = half_extent
        self._tolerance_pct = tolerance_pct

        if body_name is not None or vehicle.get_components_by_type(BODY_COMPONENTS):
            self._body = vehicle.find_single_component(BODY_COMPONENTS, body_name)
        else:
            self._body = None

        self.logger.info(
            "Configured Gmsh station sweep for '%s': x=[%.3f, %.3f] m, pitch=%.4f m",
            vehicle.name,
            x_start,
            x_end,
            pitch,
        )

    def _compute(self) -> GmshSliceResults:
        """Run the sweep and assemble typed results."""
        if self._step_path is None:
            raise RuntimeError(
                f"Analysis '{self.name}' must be setup before computation. Call setup() first."
            )
        if not self._step_path.is_file():
            raise FileNotFoundError(f"STEP file not found: {self._step_path}")

        stations = tuple(
            run_station_sweep(
                self._step_path, self._x_start, self._x_end, self._pitch, self._half_extent
            )
        )
        checks = (
            cross_check_against_body(stations, self._body, self._tolerance_pct)
            if self._body is not None
            else ()
        )
        for check in checks:
            self.logger.info(
                "[%s] %s: extracted=%.4f m reference=%.4f m diff=%.1f%%",
                check.verdict,
                check.metric,
                check.extracted,
                check.reference,
                check.diff_pct,
            )

        return GmshSliceResults(
            name=self.name,
            fidelity=self.fidelity,
            max_outer_radius=max((s.outer_bbox_radius for s in stations), default=0.0),
            max_area=max((s.area for s in stations), default=0.0),
            axial_extent=(
                max(s.x for s in stations) - min(s.x for s in stations) if stations else 0.0
            ),
            station_count=len({s.x for s in stations}),
            has_inner_loops=any(s.has_inner_loop for s in stations),
            stations=stations,
            envelope_checks=checks,
        )

    def validate_results(self, results: GmshSliceResults) -> bool:
        """Require at least one slice with finite, non-negative geometry."""
        return bool(results.stations) and all(
            math.isfinite(s.area) and s.area >= 0.0 for s in results.stations
        )
