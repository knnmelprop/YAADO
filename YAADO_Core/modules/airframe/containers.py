"""Typed result containers for airframe analyses.

Provides frozen dataclasses for the Gmsh STEP cross-section station sweep.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from YAADO_Core.Foundation.analysis_base import BaseAnalysisResults
from YAADO_Core.Foundation.units import Dimensionless, Meters, SquareMeters


@dataclass(frozen=True)
class StationSlice:
    """Cross-section of one solid volume at one axial station (one face).

    ``inner_*`` fields are estimates from the largest inner loop's extent
    and are zero when the face has no inner loop.
    """

    x: Meters
    volume_tag: int
    area: SquareMeters
    n_loops: int
    outer_equivalent_radius: Meters
    outer_bbox_radius: Meters
    has_inner_loop: bool
    inner_area: SquareMeters
    inner_equivalent_radius: Meters


@dataclass(frozen=True)
class EnvelopeCheck:
    """One comparison between a sweep-derived length and the vehicle config."""

    metric: str
    extracted: Meters
    reference: Meters
    diff_pct: Dimensionless
    verdict: str


@dataclass(frozen=True)
class GmshSliceResults(BaseAnalysisResults):
    """Outputs of the Gmsh STEP cross-section station sweep."""

    HEADLINE_METRICS: ClassVar[tuple[str, ...]] = (
        "max_outer_radius",
        "max_area",
        "axial_extent",
        "station_count",
    )

    max_outer_radius: Meters
    max_area: SquareMeters
    axial_extent: Meters
    station_count: int
    has_inner_loops: bool
    stations: tuple[StationSlice, ...]
    envelope_checks: tuple[EnvelopeCheck, ...]
