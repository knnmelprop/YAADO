"""Cross-sections of a STEP model along its axis, cut with Gmsh's OpenCASCADE kernel.

Cuts every solid of a STEP file with planes normal to the vehicle axis and measures each
cut: the material area, the area inside the outer outline with bores filled, and the
largest radius. The stations sit in the middle of equal slices, so summing their areas
integrates the volume (midpoint rule), which is checked against the CAD kernel's own
volume. The model's length, diameter and span are compared with the vehicle.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, ClassVar, Literal

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from YAADO_Core.ComponentStore import AERO_COMPONENTS, BODY_COMPONENTS, FIN_COMPONENTS
from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.airframe.containers import (
    EnvelopeCheck,
    GmshSliceResults,
    SolidSection,
    StationSection,
)
from YAADO_Core.modules.airframe.gmsh_process import (
    GmshError,
    gmsh_problem,
    gmsh_session,
    run_gmsh,
)

Axis = Literal["x", "y", "z"]
AXES: tuple[Axis, ...] = ("x", "y", "z")

#: Points sampled on each outline curve to find its largest radius.
_CURVE_SAMPLES = 41
#: The cutting plane reaches this much past the model's bounding box.
_PLANE_MARGIN = 1.2


@dataclass(frozen=True)
class SliceJob:
    """What the Gmsh child process slices.

    Attributes:
        step_file: STEP file.
        axis: Axis of the CAD model that runs along the vehicle.
        reverse: Whether the nose is at the positive end of ``axis``.
        n_stations: Number of stations.
    """

    step_file: str
    axis: Axis
    reverse: bool
    n_stations: int


@dataclass(frozen=True)
class SlicedModel:
    """Measurements of a sliced STEP model.

    Attributes:
        n_solids: Solids in the file.
        length: Axial length of the model [m].
        volume: Volume of the solids from the CAD kernel [m^3].
        axis_offset: Distance of the center of volume from the axis [m].
        stations: Cross-sections, front to back.
    """

    n_solids: int
    length: float
    volume: float
    axis_offset: float
    stations: tuple[StationSection, ...]


def equivalent_diameter(area: float) -> float:
    """Diameter of the circle with the given area [m]."""
    return 2.0 * math.sqrt(max(area, 0.0) / math.pi)


def station_positions(length: float, n_stations: int) -> tuple[float, ...]:
    """Centers of ``n_stations`` equal slices of a model of the given length [m]."""
    pitch = length / n_stations
    return tuple((i + 0.5) * pitch for i in range(n_stations))


def classify_face_loops(
    loops: Sequence[npt.NDArray[np.float64]],
) -> tuple[int, list[int]]:
    """Find the outer loop of a face among its boundary loops.

    Args:
        loops: Sampled (y, z) points of each loop, one (n, 2) array per loop.

    Returns:
        Index of the outer loop, the one with the largest extent, and the indices of the
        others, which are holes.

    Raises:
        ValueError: If there is no loop.
    """
    if not loops:
        raise ValueError("A face needs at least one boundary loop")
    extents = [float(np.linalg.norm(np.ptp(points, axis=0))) for points in loops]
    outer = int(np.argmax(extents))
    return outer, [i for i in range(len(loops)) if i != outer]


def import_step(gmsh: ModuleType, step_file: str) -> list[int]:
    """Load the solids of a STEP file into the current Gmsh model, in meters.

    A file that holds only surfaces is sewn into a solid if they close.

    Returns:
        Volume tags.

    Raises:
        GmshError: If the file cannot be read or holds no solid.
    """
    try:
        entities = gmsh.model.occ.importShapes(step_file, highestDimOnly=True)
    except Exception as exc:
        raise GmshError(f"Gmsh cannot read '{step_file}': {exc}") from exc
    if entities and not any(dim == 3 for dim, _ in entities):
        entities = gmsh.model.occ.healShapes(entities, sewFaces=True, makeSolids=True)
    solids = [tag for dim, tag in entities if dim == 3]
    if not solids:
        raise GmshError(f"'{step_file}' holds no solid: export the CAD model as solid bodies")
    gmsh.model.occ.synchronize()
    return solids


def _orient(gmsh: ModuleType, solids: list[int], axis: Axis, reverse: bool) -> float:
    """Turn the vehicle axis onto x with the nose at x = 0 and return the length [m]."""
    occ = gmsh.model.occ
    tags = [(3, tag) for tag in solids]
    if axis == "y":
        occ.rotate(tags, 0, 0, 0, 0, 0, 1, -math.pi / 2)
    elif axis == "z":
        occ.rotate(tags, 0, 0, 0, 0, 1, 0, math.pi / 2)
    if reverse:
        occ.rotate(tags, 0, 0, 0, 0, 0, 1, math.pi)
    occ.synchronize()
    boxes = [gmsh.model.getBoundingBox(3, tag) for tag in solids]
    x_min, x_max = min(b[0] for b in boxes), max(b[3] for b in boxes)
    occ.translate(tags, -x_min, 0, 0)
    occ.synchronize()
    return x_max - x_min


def _plane_reach(gmsh: ModuleType, solids: list[int]) -> float:
    """Half-width of a cutting plane that covers every section [m]."""
    boxes = [gmsh.model.getBoundingBox(3, tag) for tag in solids]
    return _PLANE_MARGIN * max(max(abs(v) for v in (*b[1:3], *b[4:6])) for b in boxes)


def _loop_points(gmsh: ModuleType, curves: Sequence[int]) -> npt.NDArray[np.float64]:
    """Sampled (y, z) points of the curves of a loop."""
    samples = []
    for curve in curves:
        low, high = gmsh.model.getParametrizationBounds(1, curve)
        parameters = np.linspace(low[0], high[0], _CURVE_SAMPLES)
        samples.append(np.asarray(gmsh.model.getValue(1, curve, parameters)).reshape(-1, 3)[:, 1:])
    return np.vstack(samples)


def _slice_solid(
    gmsh: ModuleType, solid: int, number: int, x: float, reach: float
) -> tuple[SolidSection | None, list[int], float]:
    """Cut one solid at one station.

    Returns:
        The section, or None if the plane misses the solid; the faces that fill its outer
        outlines, which the caller measures and removes; and the largest outline radius [m].
    """
    occ = gmsh.model.occ
    plane = occ.addRectangle(-reach, -reach, 0, 2 * reach, 2 * reach)
    occ.rotate([(2, plane)], 0, 0, 0, 0, 1, 0, math.pi / 2)
    occ.translate([(2, plane)], x, 0, 0)
    cut, _ = occ.intersect([(2, plane)], [(3, solid)], removeObject=True, removeTool=False)
    occ.synchronize()

    area = hole_area = max_radius = 0.0
    n_holes = 0
    filled: list[int] = []
    faces = [tag for dim, tag in cut if dim == 2]
    for face in faces:
        _, loops = occ.getCurveLoops(face)
        points = [_loop_points(gmsh, curves) for curves in loops]
        outer, holes = classify_face_loops(points)
        face_area = occ.getMass(2, face)
        # Only the outline without its holes gives the enclosed area exactly.
        outline = occ.addPlaneSurface([occ.addCurveLoop([int(c) for c in loops[outer]])])
        area += face_area
        hole_area += max(occ.getMass(2, outline) - face_area, 0.0)
        n_holes += len(holes)
        max_radius = max(max_radius, float(np.linalg.norm(points[outer], axis=1).max()))
        filled.append(outline)
    if cut:
        occ.remove(cut, recursive=False)
    if not faces:
        return None, [], 0.0
    return SolidSection(number, area, hole_area, len(faces), n_holes), filled, max_radius


def _outline_area(gmsh: ModuleType, filled: list[int]) -> float:
    """Area of the union of the filled outlines of one station [m^2]; removes them."""
    occ = gmsh.model.occ
    tags = [(2, tag) for tag in filled]
    if len(tags) > 1:
        tags, _ = occ.fuse(tags[:1], tags[1:])
    area = math.fsum(occ.getMass(2, tag) for dim, tag in tags if dim == 2)
    occ.remove(tags, recursive=True)
    return area


def slice_step(job: SliceJob) -> SlicedModel:
    """Slice a STEP model; runs in the Gmsh child process.

    Args:
        job: STEP file and station count.

    Returns:
        The measured sections.

    Raises:
        GmshError: If the file cannot be read, holds no solid or is empty.
    """
    with gmsh_session("slice") as gmsh:
        solids = import_step(gmsh, job.step_file)
        length = _orient(gmsh, solids, job.axis, job.reverse)
        reach = _plane_reach(gmsh, solids)
        volumes = [gmsh.model.occ.getMass(3, tag) for tag in solids]
        centers = [gmsh.model.occ.getCenterOfMass(3, tag) for tag in solids]
        center = np.average(np.asarray(centers), axis=0, weights=volumes)

        stations: list[StationSection] = []
        for x in station_positions(length, job.n_stations):
            sections: list[SolidSection] = []
            filled: list[int] = []
            max_radius = 0.0
            for number, solid in enumerate(solids, start=1):
                section, outlines, radius = _slice_solid(gmsh, solid, number, x, reach)
                if section is not None:
                    sections.append(section)
                    filled += outlines
                    max_radius = max(max_radius, radius)
            outline_area = _outline_area(gmsh, filled) if filled else 0.0
            gmsh.model.occ.synchronize()
            stations.append(
                StationSection(
                    x=x,
                    area=math.fsum(section.area for section in sections),
                    outline_area=outline_area,
                    equivalent_diameter=equivalent_diameter(outline_area),
                    max_radius=max_radius,
                    solids=tuple(sections),
                )
            )
    return SlicedModel(
        n_solids=len(solids),
        length=length,
        volume=math.fsum(volumes),
        axis_offset=math.hypot(center[1], center[2]),
        stations=tuple(stations),
    )


def expected_max_radius(vehicle: BaseVehicleConfig) -> float | None:
    """Largest radius the vehicle's body, fins and wings reach [m], or None without a body."""
    bodies = vehicle.get_components_by_type(BODY_COMPONENTS).values()
    if not bodies:
        return None
    body_radius = max(max(body.diameter, body.max_diameter or 0.0) / 2.0 for body in bodies)
    tip_radii = [
        body_radius + surface.span if isinstance(surface, FIN_COMPONENTS) else surface.span / 2.0
        for surface in vehicle.get_components_by_type(AERO_COMPONENTS).values()
    ]
    return max([body_radius, *tip_radii])


def check_envelope(
    model: SlicedModel, vehicle: BaseVehicleConfig, tolerance: float
) -> tuple[EnvelopeCheck, ...]:
    """Compare the sliced model's length, body diameter and span with the vehicle.

    The body diameter is the median equivalent diameter of the sections behind the nose,
    so fins on less than half of the body do not change it.

    Args:
        model: Sliced model.
        vehicle: Vehicle with one axisymmetric body; without one there is nothing to compare.
        tolerance: Largest accepted relative difference.

    Returns:
        One check per dimension that both sides have.
    """
    bodies = list(vehicle.get_components_by_type(BODY_COMPONENTS).values())
    if len(bodies) != 1:
        return ()
    body = bodies[0]
    pairs: list[tuple[str, float, float | None]] = [
        ("length", model.length, body.total_length or body.length),
        ("max radius", max(s.max_radius for s in model.stations), expected_max_radius(vehicle)),
    ]
    aft = [s.equivalent_diameter for s in model.stations if s.x > (body.nose_length or 0.0)]
    if aft:
        pairs.append(("body diameter", float(np.median(aft)), body.diameter))
    return tuple(
        EnvelopeCheck(
            metric=metric,
            measured=measured,
            expected=expected,
            difference=(measured - expected) / expected,
            matches=abs(measured - expected) <= tolerance * expected,
        )
        for metric, measured, expected in pairs
        if expected
    )


class GmshSliceAnalysis(BaseAnalysis[GmshSliceResults]):
    """Cross-section areas and radii of a STEP model along the vehicle axis.

    Example:
        analysis = GmshSliceAnalysis()
        analysis.setup(vehicle, step_file="Hangar/geometry/airframe.step")
        results = analysis.execute()
        areas = [station.outline_area for station in results.stations]
    """

    fidelity = FidelityLevel.LEVEL_0

    DEFAULT_AXIS: ClassVar[Axis] = "x"
    DEFAULT_N_STATIONS: ClassVar[int] = 60
    DEFAULT_TOLERANCE: ClassVar[float] = 0.05
    MAX_STATIONS: ClassVar[int] = 2000
    #: A larger gap between the sliced and the CAD volume is reported.
    VOLUME_TOLERANCE: ClassVar[float] = 0.02
    #: A larger offset of the model from its axis, over the largest radius, is reported.
    AXIS_OFFSET_TOLERANCE: ClassVar[float] = 0.02

    def __init__(self, name: str = "gmsh_step_slicer") -> None:
        super().__init__(name)
        self._job = SliceJob("", self.DEFAULT_AXIS, False, self.DEFAULT_N_STATIONS)
        self._vehicle = BaseVehicleConfig(name="unset")
        self._tolerance = self.DEFAULT_TOLERANCE

    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        step_file: str | None = None,
        axis: str = DEFAULT_AXIS,
        reverse: bool = False,
        n_stations: int = DEFAULT_N_STATIONS,
        tolerance: float = DEFAULT_TOLERANCE,
        **kwargs: Any,
    ) -> None:
        """Check the STEP file and the stations.

        Args:
            vehicle: Vehicle the model is compared with.
            step_file: STEP file of the vehicle.
            axis: CAD axis that runs along the vehicle: ``x``, ``y`` or ``z``.
            reverse: Whether the nose is at the positive end of ``axis``.
            n_stations: Number of stations.
            tolerance: Largest accepted relative difference from the vehicle.
            **kwargs: Not accepted; present for the ``BaseAnalysis`` signature.

        Raises:
            TypeError: If an unknown setting is passed.
            RuntimeError: If Gmsh is not available.
            ValueError: If the file does not exist or a setting is out of range.
        """
        if kwargs:
            raise TypeError(f"Unknown settings for '{self.name}': {sorted(kwargs)}")
        problem = gmsh_problem()
        if problem is not None:
            raise RuntimeError(problem)
        if not step_file:
            raise ValueError(
                "No STEP file: put one in Hangar/geometry, or set step_file=PATH in bare mode"
            )
        path = Path(step_file).expanduser()
        if not path.is_file():
            raise ValueError(f"STEP file '{step_file}' does not exist")
        matching = [known for known in AXES if known == axis]
        if not matching:
            raise ValueError(f"axis must be one of {', '.join(AXES)}, got '{axis}'")
        if not 2 <= n_stations <= self.MAX_STATIONS:
            raise ValueError(f"n_stations must be within 2 and {self.MAX_STATIONS}")
        if not 0.0 < tolerance < 1.0:
            raise ValueError(f"tolerance must be within 0 and 1, got {tolerance}")

        self._job = SliceJob(str(path.resolve()), matching[0], reverse, n_stations)
        self._vehicle = vehicle
        self._tolerance = tolerance
        self.logger.info("Slicing %s along %s at %d stations", path, axis, n_stations)

    def _compute(self) -> GmshSliceResults:
        """Slice the model in a child process and compare it with the vehicle."""
        outcome = run_gmsh(slice_step, self._job, cancel_token=self.cancel_token)
        model = outcome.value
        self.logger.save_artifact("gmsh.log", outcome.log)

        pitch = model.length / self._job.n_stations
        sliced_volume = pitch * math.fsum(station.area for station in model.stations)
        max_outline_area = max(station.outline_area for station in model.stations)
        max_radius = max(station.max_radius for station in model.stations)
        checks = check_envelope(model, self._vehicle, self._tolerance)

        assumptions: list[str] = []
        gap = abs(sliced_volume - model.volume) / model.volume
        if gap > self.VOLUME_TOLERANCE:
            assumptions.append(
                f"The sections miss {gap:.1%} of the CAD volume: use more stations."
            )
        if model.axis_offset > self.AXIS_OFFSET_TOLERANCE * max_radius:
            assumptions.append(
                f"The model's center of volume is {model.axis_offset:.4g} m off the {self._job.axis} "
                "axis: radii are measured from that axis."
            )
        for check in checks:
            self.logger.info(
                "%s: model %.4f m, vehicle %.4f m (%+.1f%%)",
                check.metric,
                check.measured,
                check.expected,
                100.0 * check.difference,
            )
            if not check.matches:
                assumptions.append(
                    f"The model's {check.metric} is {check.measured:.4g} m, but the vehicle "
                    f"has {check.expected:.4g} m ({check.difference:+.1%})."
                )

        return GmshSliceResults(
            name=self.name,
            fidelity=self.fidelity,
            step_file=self._job.step_file,
            n_solids=model.n_solids,
            n_stations=len(model.stations),
            length=model.length,
            max_radius=max_radius,
            axis_offset=model.axis_offset,
            max_outline_area=max_outline_area,
            equivalent_diameter=equivalent_diameter(max_outline_area),
            volume=model.volume,
            sliced_volume=sliced_volume,
            outline_volume=pitch * math.fsum(s.outline_area for s in model.stations),
            has_holes=any(solid.n_holes for s in model.stations for solid in s.solids),
            stations=model.stations,
            checks=checks,
            assumptions=tuple(assumptions),
        )

    def validate_results(self, results: GmshSliceResults) -> bool:
        """Check for a real model and an outline no smaller than its material.

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        return (
            results.length > 0.0
            and results.volume > 0.0
            and results.max_outline_area > 0.0
            and all(s.outline_area >= s.area * (1.0 - 1e-6) for s in results.stations)
        )


def format_sections_csv(results: GmshSliceResults) -> str:
    """Stations as CSV, one row per solid the plane cuts."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        ["x_m", "area_m2", "outline_area_m2", "equivalent_diameter_m", "max_radius_m",
         "solid", "solid_area_m2", "solid_hole_area_m2", "solid_faces", "solid_holes"]
    )
    for s in results.stations:
        for solid in s.solids:
            writer.writerow(
                [f"{s.x:.6g}", f"{s.area:.6g}", f"{s.outline_area:.6g}",
                 f"{s.equivalent_diameter:.6g}", f"{s.max_radius:.6g}", solid.solid,
                 f"{solid.area:.6g}", f"{solid.hole_area:.6g}", solid.n_faces, solid.n_holes]
            )
    return buffer.getvalue()


def plot_sections(results: GmshSliceResults) -> Figure:
    """Plot the area distribution and the radii along the model.

    Args:
        results: Sliced model.

    Returns:
        The figure.
    """
    import matplotlib.pyplot as plt

    x = [s.x for s in results.stations]
    fig, (ax_area, ax_radius) = plt.subplots(2, 1, figsize=(9.0, 7.0), sharex=True)
    ax_area.plot(x, [s.outline_area for s in results.stations], label="Outline (holes filled)")
    ax_area.plot(x, [s.area for s in results.stations], "--", label="Material")
    ax_area.set_ylabel("Cross-section area [m²]")
    ax_area.set_ylim(bottom=0.0)
    ax_area.legend()
    ax_radius.plot(x, [s.equivalent_diameter / 2.0 for s in results.stations], label="Equivalent radius")
    ax_radius.plot(x, [s.max_radius for s in results.stations], "--", label="Largest radius")
    ax_radius.set_ylabel("Radius [m]")
    ax_radius.set_xlabel("Distance from the forward end [m]")
    ax_radius.set_xlim(0.0, results.length)
    ax_radius.set_ylim(bottom=0.0)
    ax_radius.legend()
    for ax in (ax_area, ax_radius):
        ax.grid(True, alpha=0.3)
    fig.suptitle(f"Cross-sections of {Path(results.step_file).name}")
    fig.tight_layout()
    return fig
