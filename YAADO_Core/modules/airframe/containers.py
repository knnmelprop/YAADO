"""Typed result containers for airframe analyses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from YAADO_Core.Foundation.analysis_base import BaseAnalysisResults
from YAADO_Core.Foundation.units import (
    CubicMeters,
    Dimensionless,
    Meters,
    SquareMeters,
)


@dataclass(frozen=True)
class SolidSection:
    """Cross-section of one solid of a CAD model.

    Attributes:
        solid: Number of the solid, from 1 in STEP file order.
        area: Material area, holes excluded.
        hole_area: Area of the holes.
        n_faces: Separate pieces of material.
        n_holes: Holes in those pieces.
    """

    solid: int
    area: SquareMeters
    hole_area: SquareMeters
    n_faces: int
    n_holes: int


@dataclass(frozen=True)
class StationSection:
    """Cross-section of a whole CAD model at one station.

    Attributes:
        x: Distance from the forward end of the model.
        area: Material area of all solids, holes excluded.
        outline_area: Area inside the outer outline, with every hole filled.
        equivalent_diameter: Diameter of the circle with ``outline_area``.
        max_radius: Largest distance of the outline from the model axis.
        solids: Cross-section of each solid the plane cuts.
    """

    x: Meters
    area: SquareMeters
    outline_area: SquareMeters
    equivalent_diameter: Meters
    max_radius: Meters
    solids: tuple[SolidSection, ...]


@dataclass(frozen=True)
class EnvelopeCheck:
    """One dimension of the CAD model compared with the vehicle.

    Attributes:
        metric: Name of the dimension.
        measured: Value read off the CAD model.
        expected: Value from the vehicle configuration.
        difference: ``(measured - expected) / expected``.
        matches: Whether the difference is within the tolerance.
    """

    metric: str
    measured: Meters
    expected: Meters
    difference: Dimensionless
    matches: bool


@dataclass(frozen=True)
class GmshSliceResults(BaseAnalysisResults):
    """Cross-sections of a STEP model along its axis.

    Attributes:
        step_file: STEP file that was sliced.
        n_solids: Solids in the file.
        n_stations: Number of stations.
        length: Axial length of the model.
        max_radius: Largest distance of a section outline from the axis.
        axis_offset: Distance of the center of volume from the axis.
        max_outline_area: Largest section outline area.
        equivalent_diameter: Diameter of the circle with ``max_outline_area``.
        volume: Material volume of the solids, from the CAD kernel.
        sliced_volume: Material volume integrated over the stations.
        outline_volume: Volume inside the outer outline, integrated over the stations.
        has_holes: Whether any section has a hole, such as a bore.
        stations: Cross-sections, front to back.
        checks: Comparison with the vehicle.
        assumptions: Conditions that limit how far the results can be trusted.
    """

    HEADLINE_METRICS: ClassVar[tuple[str, ...]] = (
        "length",
        "max_radius",
        "max_outline_area",
        "volume",
    )

    step_file: str
    n_solids: int
    n_stations: int
    length: Meters
    max_radius: Meters
    axis_offset: Meters
    max_outline_area: SquareMeters
    equivalent_diameter: Meters
    volume: CubicMeters
    sliced_volume: CubicMeters
    outline_volume: CubicMeters
    has_holes: bool
    stations: tuple[StationSection, ...]
    checks: tuple[EnvelopeCheck, ...]
    assumptions: tuple[str, ...]
