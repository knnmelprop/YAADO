"""Tetrahedral mesh around a vehicle for inviscid (Euler) flow, made with Gmsh.

Builds the vehicle from its components as one OpenCASCADE solid, cuts it out of a sphere
(half a sphere if the vehicle is symmetric about y = 0), and fills the rest with
tetrahedra. Cells are smallest on the nose tip and the edges of fins and wings and grow
linearly toward the far field. The mesh is written in SU2's format with the markers
``airframe``, ``base``, ``farfield`` and, for half a vehicle, ``symmetry``; the solid is
saved as a STEP file.

Reference:
    Geuzaine, C. and Remacle, J.-F., "Gmsh: a three-dimensional finite element mesh
    generator with built-in pre- and post-processing facilities", International Journal
    for Numerical Methods in Engineering 79(11), 2009.
"""

from __future__ import annotations

import itertools
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.airframe.airfoil_sections import Section
from YAADO_Core.modules.airframe.containers import GmshMeshResults, MarkerMesh
from YAADO_Core.modules.airframe.gmsh_process import (
    GmshError,
    gmsh_problem,
    gmsh_session,
    run_gmsh,
)
from YAADO_Core.modules.airframe.outer_shape import (
    BodyShape,
    OuterShape,
    Panel,
    outer_shape_from_vehicle,
)

MESH_FILENAME = "airframe.su2"
STEP_FILENAME = "airframe.step"

AIRFRAME, BASE, FARFIELD, SYMMETRY = "airframe", "base", "farfield", "symmetry"

#: A fin's root section lies this far below the body surface, over the body radius.
_ROOT_DEPTH = 0.01
#: A fin reaches into the body down to this fraction of the body radius.
_ROOT_REACH = 0.8
#: Cell size over the local surface size at the edges of fins and wings, at sharp body
#: corners and at the nose tip.
_EDGE_SIZE, _CORNER_SIZE, _TIP_SIZE = 1.0 / 3.0, 1.0 / 2.0, 1.0 / 6.0
#: Cells along the mean chord of a panel, over the cells across the body.
_CHORD_CELLS = 1.25
#: Growth of the cell size per distance from a refined edge.
_EDGE_GROWTH = 0.25
#: Growth away from the vehicle at 16 cells per diameter, and its limit. It falls with the
#: cell size, so that more cells per diameter refine the whole volume alike.
_VOLUME_GROWTH, _MAX_VOLUME_GROWTH = 0.2, 0.3
#: Accepted relative difference of the meshed from the CAD surface area.
_AREA_TOLERANCE = 0.05
_LENGTH_TOLERANCE = 1e-5

Triangles = npt.NDArray[np.float64]


@dataclass(frozen=True)
class MeshJob:
    """What the Gmsh child process meshes.

    Attributes:
        shape: Vehicle shape.
        half: Whether only the half at y > 0 is meshed.
        cells_per_diameter: Cells across the body diameter.
        farfield_lengths: Radius of the far field in body lengths.
        mesh_path: SU2 mesh to write.
        step_path: STEP file of the vehicle to write.
    """

    shape: OuterShape
    half: bool
    cells_per_diameter: int
    farfield_lengths: float
    mesh_path: str
    step_path: str


@dataclass(frozen=True)
class MeshedVehicle:
    """What the Gmsh child process returns.

    Attributes:
        n_nodes: Mesh nodes.
        n_tetrahedra: Volume cells.
        markers: Triangles and area of each boundary marker.
        volume: Volume of the whole vehicle from the CAD kernel [m^3].
        wetted_area: Surface area of the whole vehicle without its base [m^2].
        base_area: Area of the base of the whole vehicle [m^2].
        min_quality: Smallest signed inverse condition number of the cells.
        n_poor: Cells with a quality below :attr:`GmshMeshAnalysis.POOR_QUALITY`.
        wall: Corners of the airframe and base triangles, (n, 3, 3).
        symmetry: Corners of the symmetry plane triangles, (n, 3, 3).
    """

    n_nodes: int
    n_tetrahedra: int
    markers: tuple[MarkerMesh, ...]
    volume: float
    wetted_area: float
    base_area: float
    min_quality: float
    n_poor: int
    wall: Triangles
    symmetry: Triangles


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def _body_halves(gmsh: ModuleType, body: BodyShape) -> list[tuple[int, int]]:
    """Revolve the body profile to both sides of y = 0.

    A full revolution would have a seam, along which Gmsh repeats triangles at the nose tip.
    """
    occ = gmsh.model.occ

    def point(x: float, r: float) -> int:
        return int(occ.addPoint(x, 0.0, r))

    tip, nose_base = point(0.0, 0.0), point(body.nose_length, body.nose_radius)
    if body.nose_type == "conical":
        profile = [occ.addLine(tip, nose_base)]
    elif body.nose_type == "ogive":
        center = point(body.nose_length, body.nose_radius - body.ogive_radius)
        profile = [occ.addCircleArc(tip, center, nose_base)]
    else:
        center = point(body.nose_length, 0.0)
        if math.isclose(body.nose_length, body.nose_radius, rel_tol=1e-6):
            profile = [occ.addCircleArc(tip, center, nose_base)]
        else:
            major = tip if body.nose_length > body.nose_radius else nose_base
            profile = [occ.addEllipseArc(tip, center, major, nose_base)]
    previous = nose_base
    if body.radius > body.nose_radius * (1.0 + 1e-9):
        previous = point(body.nose_length, body.radius)
        profile.append(occ.addLine(nose_base, previous))
    rim, base_center = point(body.length, body.radius), point(body.length, 0.0)
    profile += [
        occ.addLine(previous, rim),
        occ.addLine(rim, base_center),
        occ.addLine(base_center, tip),
    ]
    face = occ.addPlaneSurface([occ.addCurveLoop(profile)])
    halves = []
    for source, angle in (([(2, face)], math.pi), (occ.copy([(2, face)]), -math.pi)):
        revolved = occ.revolve(source, 0, 0, 0, 1, 0, 0, angle)
        halves += [entity for entity in revolved if entity[0] == 3]
    return halves


def _section_wire(
    gmsh: ModuleType, panel: Panel, section: Section, le: float, offset: float, chord: float
) -> int:
    """Closed wire of a section at a distance from the axis."""
    occ = gmsh.model.occ
    span, normal = panel.span_direction, panel.normal

    def point(x: float, z: float) -> int:
        return int(
            occ.addPoint(
                le + x * chord,
                offset * span[1] + z * chord * normal[1],
                offset * span[2] + z * chord * normal[2],
            )
        )

    leading_edge, trailing_edge = point(*section.upper[0]), point(*section.upper[-1])
    curves: list[int] = []
    for side in (section.upper, section.lower):
        points = [leading_edge, *(point(*p) for p in side[1:-1]), trailing_edge]
        if section.straight:
            lines = [occ.addLine(a, b) for a, b in itertools.pairwise(points)]
        else:
            lines = [occ.addSpline(points)]
        curves += lines if side is section.upper else [-line for line in reversed(lines)]
    return int(occ.addWire(curves, checkClosed=True))


@dataclass(frozen=True)
class _RootSection:
    """Section of a panel where it leaves the body.

    Attributes:
        offset: Distance from the axis [m].
        inner_offset: Distance from the axis where the panel ends inside the body [m].
        le: Axial position of the leading edge [m].
        chord: Chord [m].
    """

    offset: float
    inner_offset: float
    le: float
    chord: float


def root_section(panel: Panel, body: BodyShape) -> _RootSection:
    """Place a panel's root section just below the body surface.

    A section on the surface itself would leave a sliver of a face along the root, where
    the body curves away under the thickness of the fin. The edges are extended straight
    inward, except for a trailing edge that would come out of the base.
    """
    if panel.is_wing:
        return _RootSection(panel.root_offset, panel.root_offset, panel.root_le, panel.root_chord)
    half_thickness = panel.root_thickness / 2.0
    offset = math.sqrt(max(body.radius**2 - half_thickness**2, 0.0)) - _ROOT_DEPTH * body.radius
    root_te, tip_te = panel.root_le + panel.root_chord, panel.tip_le + panel.tip_chord
    inward = (panel.root_offset - offset) / (panel.tip_offset - panel.root_offset)
    le = panel.root_le - inward * (panel.tip_le - panel.root_le)
    te = root_te - inward * (tip_te - root_te)
    if te > body.length >= root_te - _LENGTH_TOLERANCE * body.length:
        te = root_te
    narrowest = min(body.radius_at(max(panel.root_le, 0.0)), body.radius_at(min(root_te, body.length)))
    inner = max(min(_ROOT_REACH * narrowest - half_thickness, _ROOT_REACH * offset), 0.0)
    return _RootSection(offset, inner, le, te - le)


def _panel_solid(gmsh: ModuleType, panel: Panel, body: BodyShape) -> int:
    """Solid of a fin or wing half."""
    occ = gmsh.model.occ
    root = root_section(panel, body)
    offsets = (root.offset,) if panel.is_wing else (root.inner_offset, root.offset)
    wires = [
        _section_wire(gmsh, panel, panel.root_section, root.le, offset, root.chord)
        for offset in offsets
    ]
    wires.append(
        _section_wire(
            gmsh, panel, panel.tip_section, panel.tip_le, panel.tip_offset, panel.tip_chord
        )
    )
    lofted = occ.addThruSections(wires, makeSolid=True, makeRuled=True)
    return next(tag for dim, tag in lofted if dim == 3)


def build_vehicle(gmsh: ModuleType, shape: OuterShape) -> int:
    """Build the vehicle in the current Gmsh model.

    Args:
        gmsh: The ``gmsh`` module with an open model.
        shape: Vehicle shape.

    Returns:
        Volume tag of the vehicle as one solid.

    Raises:
        GmshError: If the parts do not join into one solid.
    """
    occ = gmsh.model.occ
    # Joining the two halves of the body into one face would bring the seam back.
    gmsh.option.setNumber("Geometry.OCCUnionUnify", 0)
    first, *rest = _body_halves(gmsh, shape.body)
    rest += [(3, _panel_solid(gmsh, panel, shape.body)) for panel in shape.panels]
    solids, _ = occ.fuse([first], rest)
    solids = [entity for entity in solids if entity[0] == 3]
    if len(solids) != 1:
        raise GmshError(
            f"The fins and wings of '{shape.vehicle}' do not all touch the body: "
            f"the vehicle falls into {len(solids)} parts"
        )
    return int(solids[0][1])


def write_step(gmsh: ModuleType, vehicle: int, path: str) -> None:
    """Save the vehicle solid, without the curves it was built from, as a STEP file."""
    gmsh.model.occ.synchronize()
    gmsh.model.setVisibility(gmsh.model.getEntities(), 0)
    gmsh.model.setVisibility([(3, vehicle)], 1, recursive=True)
    gmsh.option.setNumber("Geometry.OCCExportOnlyVisible", 1)
    gmsh.write(path)
    gmsh.model.setVisibility(gmsh.model.getEntities(), 1)


# ---------------------------------------------------------------------------
# Boundary and cell sizes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Boundary:
    """Surface tags of the flow domain."""

    airframe: list[int]
    base: list[int]
    farfield: list[int]
    symmetry: list[int]

    def named(self) -> list[tuple[str, list[int]]]:
        """Markers with at least one surface."""
        markers = [
            (AIRFRAME, self.airframe),
            (BASE, self.base),
            (FARFIELD, self.farfield),
            (SYMMETRY, self.symmetry),
        ]
        return [(name, tags) for name, tags in markers if tags]


def _classify_boundary(
    gmsh: ModuleType, domain: list[tuple[int, int]], shape: OuterShape, farfield_radius: float
) -> _Boundary:
    """Sort the surfaces around the flow domain by their bounding boxes."""
    tolerance = _LENGTH_TOLERANCE * shape.body.length
    boundary = _Boundary([], [], [], [])
    for dim, tag in gmsh.model.getBoundary(domain, oriented=False):
        x0, y0, z0, x1, y1, z1 = gmsh.model.getBoundingBox(dim, tag)
        if max(abs(y0), abs(y1)) < tolerance:
            boundary.symmetry.append(tag)
        elif max(abs(y0), abs(y1), abs(z0), abs(z1)) > 0.5 * farfield_radius:
            boundary.farfield.append(tag)
        elif min(x0, x1) > shape.body.length - tolerance and x1 < shape.body.length + tolerance:
            boundary.base.append(tag)
        else:
            boundary.airframe.append(tag)
    return boundary


def _panel_of_point(shape: OuterShape, point: npt.NDArray[np.float64]) -> Panel | None:
    """The panel a point lies on, or None if it lies on the body."""
    for panel in shape.panels:
        offset = float(np.dot(point, panel.span_direction))
        height = abs(float(np.dot(point, panel.normal)))
        lowest = shape.body.radius if not panel.is_wing else 0.0
        on_body = math.hypot(point[1], point[2]) <= shape.body.radius_at(point[0]) * 1.001
        if (
            not on_body
            and lowest * 0.999 < offset < panel.tip_offset * 1.001
            and height < 0.75 * panel.root_thickness
        ):
            return panel
    return None


def _edge_segments(
    panel: Panel, body: BodyShape, surface_size: float
) -> list[tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], float]]:
    """Leading edge, trailing edge and tip chord of a panel, each with its cell size."""
    span = np.asarray(panel.span_direction)
    root = root_section(panel, body)
    axis = np.array([1.0, 0.0, 0.0])

    def place(section: Section, index: int, le: float, offset: float, chord: float) -> Triangles:
        x, z = section.upper[index]
        return (le + x * chord) * axis + offset * span + z * chord * np.asarray(panel.normal)

    ends = [
        (
            place(panel.root_section, index, root.le, root.offset, root.chord),
            place(panel.tip_section, index, panel.tip_le, panel.tip_offset, panel.tip_chord),
        )
        for index in (0, -1)
    ]
    edge = _EDGE_SIZE * surface_size
    nose_radius = panel.root_section.leading_edge_radius * panel.mean_chord
    leading = min(max(0.7 * nose_radius, edge / 4.0), edge) if nose_radius > 0.0 else edge
    return [
        (*ends[0], leading),
        (*ends[1], edge),
        (ends[0][1], ends[1][1], _CORNER_SIZE * surface_size),
    ]


def _distance_to_segment(point: Triangles, start: Triangles, end: Triangles) -> float:
    """Distance of a point from a line segment [m]."""
    along = end - start
    t = float(np.clip(np.dot(point - start, along) / np.dot(along, along), 0.0, 1.0))
    return float(np.linalg.norm(point - start - t * along))


class _SizeFields:
    """Background mesh size: the smallest of several Gmsh size fields.

    Fields on surfaces and edges size the walls; the volume grows away from the meshed walls.
    """

    def __init__(self, gmsh: ModuleType, walls: list[int], largest: float) -> None:
        self._gmsh = gmsh
        self._field = gmsh.model.mesh.field
        self._walls = walls
        self._largest = largest
        self._tags: list[int] = []

    def on_surfaces(self, surfaces: list[int], size: float) -> None:
        """Keep cells on surfaces at or below a size."""
        tag = self._field.add("Constant")
        self._field.setNumbers(tag, "SurfacesList", surfaces)
        self._field.setNumber(tag, "IncludeBoundary", 1)
        self._field.setNumber(tag, "VIn", size)
        self._field.setNumber(tag, "VOut", self._largest)
        self._tags.append(tag)

    def near(
        self, entities: str, tags: list[int], size: float, outer_size: float, reach: float, sampling: int
    ) -> None:
        """Grow wall cells from ``size`` at points or curves to ``outer_size`` at ``reach``."""
        distance = self._field.add("Distance")
        self._field.setNumbers(distance, entities, tags)
        if sampling:
            self._field.setNumber(distance, "Sampling", sampling)
        tag = self._field.add("Threshold")
        self._field.setNumber(tag, "InField", distance)
        self._field.setNumber(tag, "SizeMin", size)
        self._field.setNumber(tag, "SizeMax", outer_size)
        self._field.setNumber(tag, "DistMin", size)
        self._field.setNumber(tag, "DistMax", max(reach, 1.5 * size))
        self._field.setNumber(tag, "StopAtDistMax", 1)
        restricted = self._field.add("Restrict")
        self._field.setNumber(restricted, "InField", tag)
        self._field.setNumbers(restricted, "SurfacesList", self._walls)
        self._field.setNumber(restricted, "IncludeBoundary", 1)
        self._tags.append(restricted)

    def away_from_walls(self, reach: float) -> None:
        """Grow cells linearly from the meshed walls to the largest size at ``reach``."""
        boundary = self._gmsh.model.getBoundary(
            [(2, tag) for tag in self._walls], combined=False, oriented=False
        )
        tag = self._field.add("Extend")
        self._field.setNumbers(tag, "SurfacesList", self._walls)
        self._field.setNumbers(tag, "CurvesList", sorted({curve for _, curve in boundary}))
        self._field.setNumber(tag, "DistMax", reach)
        self._field.setNumber(tag, "SizeMax", self._largest)
        self._field.setNumber(tag, "Power", 1)
        self._tags.append(tag)

    def apply(self) -> None:
        """Make the smallest of the fields the background mesh size."""
        tag = self._field.add("Min")
        self._field.setNumbers(tag, "FieldsList", self._tags)
        self._field.setAsBackgroundMesh(tag)
        for option in ("ExtendFromBoundary", "FromPoints", "FromCurvature"):
            self._gmsh.option.setNumber(f"Mesh.MeshSize{option}", 0)


def _set_cell_sizes(
    gmsh: ModuleType, shape: OuterShape, boundary: _Boundary, job: MeshJob, farfield_radius: float
) -> None:
    """Choose the cell sizes of the surfaces, the edges and the volume."""
    body = shape.body
    walls = [*boundary.airframe, *boundary.base]
    body_size = 2.0 * body.radius / job.cells_per_diameter
    growth = _VOLUME_GROWTH * GmshMeshAnalysis.DEFAULT_CELLS_PER_DIAMETER / job.cells_per_diameter
    fields = _SizeFields(gmsh, walls, min(growth, _MAX_VOLUME_GROWTH) * farfield_radius)
    fields.on_surfaces(walls, body_size)

    panel_sizes = {
        panel: min(body_size, panel.mean_chord / (_CHORD_CELLS * job.cells_per_diameter))
        for panel in shape.panels
    }
    panel_faces: dict[Panel, list[int]] = {panel: [] for panel in shape.panels}
    for tag in boundary.airframe:
        panel = _panel_of_point(shape, np.asarray(gmsh.model.occ.getCenterOfMass(2, tag)))
        if panel is not None:
            panel_faces[panel].append(tag)
    for panel, faces in panel_faces.items():
        if faces:
            fields.on_surfaces(faces, panel_sizes[panel])

    curves = [
        tag
        for _, tag in gmsh.model.getBoundary([(2, t) for t in walls], combined=False, oriented=False)
    ]
    middles = {}
    for tag in sorted(set(curves)):
        low, high = gmsh.model.getParametrizationBounds(1, tag)
        ends = np.asarray(
            gmsh.model.getValue(1, tag, [low[0], 0.5 * (low[0] + high[0]), high[0]])
        ).reshape(3, 3)
        middles[tag] = ends
    tolerance = 1e-3 * body.radius
    for panel in shape.panels:
        size = panel_sizes[panel]
        for start, end, edge_size in _edge_segments(panel, body, size):
            length = float(np.linalg.norm(end - start))
            on_edge = [
                tag
                for tag, points in middles.items()
                if all(_distance_to_segment(p, start, end) < tolerance for p in points)
            ]
            if on_edge:
                sampling = int(np.clip(2.0 * length / edge_size, 20, 2000))
                reach = edge_size + (size - edge_size) / _EDGE_GROWTH
                fields.near("CurvesList", on_edge, edge_size, size, reach, sampling)

    corners = [body.length]
    if body.nose_type == "conical" or body.nose_radius < body.radius:
        corners.append(body.nose_length)
    rims = [
        tag
        for tag, points in middles.items()
        if any(np.all(np.abs(points[:, 0] - x) < tolerance) for x in corners)
    ]
    corner_size = _CORNER_SIZE * body_size
    sampling = int(np.clip(4.0 * math.pi * body.radius / corner_size, 40, 2000))
    fields.near(
        "CurvesList", rims, corner_size, body_size,
        corner_size + (body_size - corner_size) / _EDGE_GROWTH, sampling,
    )
    tips = [tag for _, tag in gmsh.model.getEntitiesInBoundingBox(*[-tolerance] * 3, *[tolerance] * 3, 0)]
    if tips:
        tip_size = (_CORNER_SIZE if body.nose_type == "hemispherical" else _TIP_SIZE) * body_size
        fields.near("PointsList", tips, tip_size, body_size, 0.7 * body.nose_length, 0)
    fields.away_from_walls(farfield_radius)
    fields.apply()


# ---------------------------------------------------------------------------
# Mesh
# ---------------------------------------------------------------------------


def _marker_triangles(gmsh: ModuleType, tags: list[int]) -> npt.NDArray[np.int64]:
    """Node numbers of the triangles of surfaces, (n, 3)."""
    parts = []
    for tag in tags:
        _, nodes = gmsh.model.mesh.getElementsByType(2, tag)
        parts.append(np.asarray(nodes, dtype=np.int64).reshape(-1, 3))
    return np.vstack(parts) if parts else np.empty((0, 3), dtype=np.int64)


def _face_keys(faces: npt.NDArray[np.int64], n_nodes: int) -> npt.NDArray[np.int64]:
    """One number per face, whatever the order of its nodes."""
    ordered = np.sort(faces, axis=1)
    return ordered[:, 0] * n_nodes**2 + ordered[:, 1] * n_nodes + ordered[:, 2]


def boundary_is_closed(
    tetrahedra: npt.NDArray[np.int64], triangles: npt.NDArray[np.int64]
) -> bool:
    """Whether the triangles are exactly the faces that belong to one tetrahedron.

    Args:
        tetrahedra: Node numbers of the cells, (n, 4).
        triangles: Node numbers of the boundary triangles, (m, 3).

    Returns:
        True for a watertight mesh with every boundary face on one marker.
    """
    n_nodes = int(tetrahedra.max()) + 1
    if n_nodes >= 2**21:
        return True
    faces = np.vstack([np.delete(tetrahedra, i, axis=1) for i in range(4)])
    keys, counts = np.unique(_face_keys(faces, n_nodes), return_counts=True)
    expected = np.sort(_face_keys(triangles, n_nodes))
    return bool(counts.max() <= 2) and np.array_equal(keys[counts == 1], expected)


def mesh_vehicle(job: MeshJob) -> MeshedVehicle:
    """Build and mesh a vehicle; runs in the Gmsh child process.

    Args:
        job: Shape, resolution and output files.

    Returns:
        Size and quality of the mesh.

    Raises:
        GmshError: If the geometry cannot be built or the mesh is not watertight.
    """
    shape, body = job.shape, job.shape.body
    with gmsh_session("mesh") as gmsh:
        occ = gmsh.model.occ
        vehicle = build_vehicle(gmsh, shape)
        write_step(gmsh, vehicle, job.step_path)
        volume = occ.getMass(3, vehicle)
        radius = job.farfield_lengths * body.length
        domain = [(3, occ.addSphere(body.length / 2.0, 0, 0, radius))]
        if job.half:
            # Cutting a full sphere keeps the symmetry plane in one piece.
            box = occ.addBox(-2.0 * radius, 0, -2.0 * radius, 5.0 * radius, 2.0 * radius, 4.0 * radius)
            domain, _ = occ.intersect(domain, [(3, box)])
        domain, _ = occ.cut(domain, [(3, vehicle)])
        occ.synchronize()
        if len(domain) != 1:
            raise GmshError(f"The flow around '{shape.vehicle}' falls into {len(domain)} volumes")

        boundary = _classify_boundary(gmsh, domain, shape, radius)
        if not boundary.airframe or not boundary.farfield or bool(boundary.symmetry) != job.half:
            raise GmshError(f"The boundary around '{shape.vehicle}' could not be identified")
        for name, tags in boundary.named():
            gmsh.model.addPhysicalGroup(2, tags, name=name)
        gmsh.model.addPhysicalGroup(3, [tag for _, tag in domain], name="fluid")
        sides = 2.0 if job.half else 1.0
        areas = {
            name: math.fsum(occ.getMass(2, tag) for tag in tags) for name, tags in boundary.named()
        }

        _set_cell_sizes(gmsh, shape, boundary, job, radius)
        gmsh.option.setNumber("Mesh.Algorithm", 6)
        gmsh.option.setNumber("Mesh.Algorithm3D", 1)
        gmsh.model.mesh.generate(3)
        # The default optimizer leaves slivers along fin roots; Netgen's removes them.
        gmsh.model.mesh.optimize("Netgen")

        node_tags, coordinates, _ = gmsh.model.mesh.getNodes()
        positions = np.empty((int(node_tags.max()) + 1, 3))
        positions[np.asarray(node_tags, dtype=np.int64)] = np.asarray(coordinates).reshape(-1, 3)
        cell_tags, cell_nodes = gmsh.model.mesh.getElementsByType(4)
        tetrahedra = np.asarray(cell_nodes, dtype=np.int64).reshape(-1, 4)
        triangles = {name: _marker_triangles(gmsh, tags) for name, tags in boundary.named()}
        if not boundary_is_closed(tetrahedra, np.vstack(list(triangles.values()))):
            raise GmshError(f"The mesh around '{shape.vehicle}' is not watertight")

        markers = []
        for name, nodes in triangles.items():
            corners = positions[nodes]
            normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
            area = float(np.linalg.norm(normals, axis=1).sum() / 2.0)
            markers.append(MarkerMesh(name, len(nodes), area))
            if name in (AIRFRAME, BASE) and abs(area / areas[name] - 1.0) > _AREA_TOLERANCE:
                raise GmshError(
                    f"The meshed {name} area {area:.4g} m^2 misses the CAD area {areas[name]:.4g} m^2"
                )
        quality = np.asarray(gmsh.model.mesh.getElementQualities(cell_tags, "minSICN"))
        gmsh.write(job.mesh_path)

        wall = np.vstack([triangles[name] for name in (AIRFRAME, BASE) if name in triangles])
        return MeshedVehicle(
            n_nodes=len(np.unique(tetrahedra)),
            n_tetrahedra=len(tetrahedra),
            markers=tuple(markers),
            volume=volume,
            wetted_area=sides * areas[AIRFRAME],
            base_area=sides * areas.get(BASE, 0.0),
            min_quality=float(quality.min()),
            n_poor=int((quality < GmshMeshAnalysis.POOR_QUALITY).sum()),
            wall=positions[wall],
            symmetry=positions[triangles.get(SYMMETRY, np.empty((0, 3), dtype=np.int64))],
        )


class GmshMeshAnalysis(BaseAnalysis[GmshMeshResults]):
    """Tetrahedral Euler mesh around a vehicle, built from its components.

    Example:
        analysis = GmshMeshAnalysis()
        analysis.setup(vehicle, cells_per_diameter=16)
        results = analysis.execute()
        n_cells = results.n_tetrahedra
    """

    fidelity = FidelityLevel.LEVEL_2

    DEFAULT_CELLS_PER_DIAMETER: ClassVar[int] = 16
    DEFAULT_FARFIELD_LENGTHS: ClassVar[float] = 8.0
    DEFAULT_FIN_THICKNESS_RATIO: ClassVar[float] = 0.04
    DEFAULT_DOMAIN: ClassVar[str] = "auto"
    MIN_CELLS_PER_DIAMETER: ClassVar[int] = 6
    MAX_CELLS_PER_DIAMETER: ClassVar[int] = 64
    MIN_FARFIELD_LENGTHS: ClassVar[float] = 2.0
    DOMAINS: ClassVar[tuple[str, ...]] = ("auto", "half", "full")
    #: Cells below this quality are counted and reported.
    POOR_QUALITY: ClassVar[float] = 0.05

    def __init__(self, name: str = "gmsh_euler_mesh") -> None:
        super().__init__(name)
        self._shape: OuterShape | None = None
        self._half = False
        self._cells_per_diameter = self.DEFAULT_CELLS_PER_DIAMETER
        self._farfield_lengths = self.DEFAULT_FARFIELD_LENGTHS

    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        surfaces: str | None = None,
        cells_per_diameter: int = DEFAULT_CELLS_PER_DIAMETER,
        farfield_lengths: float = DEFAULT_FARFIELD_LENGTHS,
        domain: str = DEFAULT_DOMAIN,
        fin_roll_deg: float | None = None,
        fin_thickness_ratio: float = DEFAULT_FIN_THICKNESS_RATIO,
        body_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Resolve the vehicle shape and the mesh settings.

        Args:
            vehicle: Vehicle with one axisymmetric body.
            surfaces: Comma-separated lifting surfaces to mesh, or ``none`` for the body
                alone. Defaults to every surface that is placed.
            cells_per_diameter: Cells across the body diameter; sets the whole mesh.
            farfield_lengths: Radius of the far field in body lengths.
            domain: ``half`` or ``full`` vehicle. ``auto`` takes half if it is symmetric.
            fin_roll_deg: Angle of the first fin from up [deg]. Defaults to a cross for an
                even set and one fin up for an odd set.
            fin_thickness_ratio: Thickness over chord of fins that give none.
            body_name: Body to use if the vehicle has more than one.
            **kwargs: Not accepted; present for the ``BaseAnalysis`` signature.

        Raises:
            TypeError: If an unknown setting is passed.
            RuntimeError: If Gmsh is not available.
            ValueError: If the shape cannot be resolved or a setting is out of range.
        """
        if kwargs:
            raise TypeError(f"Unknown settings for '{self.name}': {sorted(kwargs)}")
        problem = gmsh_problem()
        if problem is not None:
            raise RuntimeError(problem)
        if not self.MIN_CELLS_PER_DIAMETER <= cells_per_diameter <= self.MAX_CELLS_PER_DIAMETER:
            raise ValueError(
                f"cells_per_diameter must be within {self.MIN_CELLS_PER_DIAMETER} and "
                f"{self.MAX_CELLS_PER_DIAMETER}, got {cells_per_diameter}"
            )
        if farfield_lengths < self.MIN_FARFIELD_LENGTHS:
            raise ValueError(f"farfield_lengths must be at least {self.MIN_FARFIELD_LENGTHS:g}")
        if domain not in self.DOMAINS:
            raise ValueError(f"domain must be one of {', '.join(self.DOMAINS)}, got '{domain}'")

        shape = outer_shape_from_vehicle(
            vehicle,
            body_name=body_name,
            surfaces=parse_surfaces(surfaces),
            fin_roll=fin_roll_deg,
            fin_thickness_ratio=fin_thickness_ratio,
        )
        if shape.max_radius > 0.4 * farfield_lengths * shape.body.length:
            raise ValueError("The span is too large for this far field: raise farfield_lengths")
        if domain == "half" and not shape.has_symmetry_plane:
            raise ValueError(
                "The vehicle is not symmetric about its vertical plane with this fin roll: "
                "use domain=full"
            )
        self._shape = shape
        self._half = domain == "half" or (domain == "auto" and shape.has_symmetry_plane)
        self._cells_per_diameter = cells_per_diameter
        self._farfield_lengths = farfield_lengths
        self.logger.info(
            "Meshing '%s' (%s): body and %d panels, %d cells per diameter",
            vehicle.name,
            "half" if self._half else "full",
            len(shape.panels),
            cells_per_diameter,
        )

    def _compute(self) -> GmshMeshResults:
        """Mesh the vehicle in a child process and save the mesh and the CAD model."""
        if self.logger.enabled:
            return self._mesh(self.logger.artifacts_dir)
        with tempfile.TemporaryDirectory(prefix="yaado_mesh_") as folder:
            return self._mesh(Path(folder))

    def _mesh(self, folder: Path) -> GmshMeshResults:
        """Mesh into a folder."""
        shape = self._shape
        if shape is None:
            raise RuntimeError(f"Analysis '{self.name}' has no shape; call setup() first")
        job = MeshJob(
            shape=shape,
            half=self._half,
            cells_per_diameter=self._cells_per_diameter,
            farfield_lengths=self._farfield_lengths,
            mesh_path=str((folder / MESH_FILENAME).resolve()),
            step_path=str((folder / STEP_FILENAME).resolve()),
        )
        outcome = run_gmsh(mesh_vehicle, job, cancel_token=self.cancel_token)
        mesh = outcome.value
        self.logger.save_artifact("gmsh.log", outcome.log)
        if self.logger.enabled:
            self.logger.save_figure(plot_mesh(mesh, shape), "mesh.png", show=False)
        self.logger.info(
            "%d nodes, %d tetrahedra, worst quality %.3f", mesh.n_nodes, mesh.n_tetrahedra, mesh.min_quality
        )
        assumptions = list(shape.assumptions)
        if mesh.n_poor:
            assumptions.append(
                f"{mesh.n_poor} of {mesh.n_tetrahedra} cells have a quality below "
                f"{self.POOR_QUALITY:g} (worst {mesh.min_quality:.2g})."
            )
        markers = {marker.name: marker for marker in mesh.markers}
        return GmshMeshResults(
            name=self.name,
            fidelity=self.fidelity,
            mesh_file=MESH_FILENAME,
            step_file=STEP_FILENAME,
            is_half=self._half,
            surfaces=tuple(dict.fromkeys(panel.surface for panel in shape.panels)),
            left_out=shape.left_out,
            cells_per_diameter=self._cells_per_diameter,
            n_nodes=mesh.n_nodes,
            n_tetrahedra=mesh.n_tetrahedra,
            n_wall_triangles=sum(markers[name].n_triangles for name in (AIRFRAME, BASE) if name in markers),
            markers=mesh.markers,
            min_quality=mesh.min_quality,
            n_poor=mesh.n_poor,
            farfield_radius=self._farfield_lengths * shape.body.length,
            volume=mesh.volume,
            wetted_area=mesh.wetted_area,
            base_area=mesh.base_area,
            assumptions=tuple(assumptions),
        )

    def validate_results(self, results: GmshMeshResults) -> bool:
        """Check for cells that all have a positive volume and a real vehicle.

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        return results.n_tetrahedra > 0 and results.min_quality > 0.0 and results.volume > 0.0


def parse_surfaces(text: str | None) -> tuple[str, ...] | None:
    """Surfaces named in a comma-separated setting; None for a blank, () for ``none``."""
    if text is None or not text.strip():
        return None
    names = tuple(name.strip() for name in text.split(",") if name.strip())
    return () if names == ("none",) else names


def plot_mesh(mesh: MeshedVehicle, shape: OuterShape) -> Figure:
    """Plot the surface mesh from the side and the back, and the volume mesh around the nose.

    Args:
        mesh: Meshed vehicle.
        shape: Its shape.

    Returns:
        The figure.
    """
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection

    def draw(ax: Any, triangles: Triangles, axes: tuple[int, int], color: str, depth: int) -> None:
        order = np.argsort(triangles[:, :, depth].mean(axis=1))
        ax.add_collection(
            PolyCollection(
                list(triangles[order][:, :, axes]),
                facecolors=color,
                edgecolors="0.25",
                linewidths=0.15,
            )
        )
        ax.set_aspect("equal")
        ax.autoscale_view()

    body = shape.body
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.0), width_ratios=(2.5, 1.0))
    draw(axes[0, 0], mesh.wall, (0, 2), "lightsteelblue", 1)
    axes[0, 0].set(xlabel="x [m]", ylabel="z [m]", title="Surface mesh from starboard")
    draw(axes[0, 1], mesh.wall, (1, 2), "lightsteelblue", 0)
    axes[0, 1].set(xlabel="y [m]", ylabel="z [m]", title="From behind")
    around = mesh.symmetry if len(mesh.symmetry) else mesh.wall
    title = "Symmetry plane" if len(mesh.symmetry) else "Surface mesh"
    draw(axes[1, 0], around, (0, 2), "white", 1)
    margin = 1.5 * shape.max_radius
    axes[1, 0].set(xlabel="x [m]", ylabel="z [m]", title=f"{title} around the vehicle")
    axes[1, 0].set_xlim(-margin, body.length + margin)
    axes[1, 0].set_ylim(-2.0 * margin, 2.0 * margin)
    draw(axes[1, 1], around, (0, 2), "white", 1)
    axes[1, 1].set(xlabel="x [m]", ylabel="z [m]", title="Nose")
    axes[1, 1].set_xlim(-0.3 * body.nose_length, 1.2 * body.nose_length)
    axes[1, 1].set_ylim(-0.75 * body.nose_length, 0.75 * body.nose_length)
    fig.suptitle(f"{shape.vehicle}: {mesh.n_tetrahedra:,} tetrahedra, {mesh.n_nodes:,} nodes")
    fig.tight_layout()
    return fig
