"""Typed geometry and result containers for stability and control analyses."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import ClassVar, Literal

from YAADO_Core.Foundation.analysis_base import BaseAnalysisResults
from YAADO_Core.Foundation.units import (
    Calibers,
    Degrees,
    Dimensionless,
    Meters,
    PerRadian,
    SquareMeters,
)

NoseType = Literal["ogive", "conical", "hemispherical"]


@dataclass(frozen=True)
class FinSetGeometry:
    """One radial set of identical trapezoidal fins.

    Attributes:
        name: Component name in ``vehicle.aero_surfaces``.
        count: Number of fins in the set.
        span: Exposed semi-span of one fin, from the body surface to the tip.
        root_chord: Root chord.
        tip_chord: Tip chord.
        sweep: Leading-edge sweep angle.
        root_le_x: Axial position of the root leading edge from the nose tip.
    """

    name: str
    count: int
    span: Meters
    root_chord: Meters
    tip_chord: Meters
    sweep: Degrees
    root_le_x: Meters

    @property
    def sweep_length(self) -> Meters:
        """Axial distance from the root leading edge to the tip leading edge."""
        return self.span * math.tan(math.radians(self.sweep))

    @property
    def mean_chord(self) -> Meters:
        """Arithmetic mean of the root and tip chords."""
        return 0.5 * (self.root_chord + self.tip_chord)

    @property
    def panel_area(self) -> SquareMeters:
        """Planform area of one exposed fin panel."""
        return self.span * self.mean_chord


@dataclass(frozen=True)
class RocketGeometry:
    """Slender body-of-revolution with one or more fin sets.

    Axial positions are measured from the nose tip. A nose base narrower than
    the body is joined to it by a step (shoulder) at ``x = nose_length``.

    Attributes:
        d_ref: Body (reference) diameter.
        nose_type: Nose shape.
        nose_length: Axial length of the nose.
        nose_base_diameter: Diameter at the nose base (<= ``d_ref``).
        total_length: Overall body length.
        cg_from_nose: Center of gravity used for the static margin.
        fin_sets: Fin sets, ordered from front to back.
    """

    d_ref: Meters
    nose_type: NoseType
    nose_length: Meters
    nose_base_diameter: Meters
    total_length: Meters
    cg_from_nose: Meters
    fin_sets: tuple[FinSetGeometry, ...]

    @property
    def body_radius(self) -> Meters:
        """Reference body radius."""
        return 0.5 * self.d_ref

    @property
    def reference_area(self) -> SquareMeters:
        """Body cross-section area that all normal-force slopes refer to."""
        return math.pi / 4.0 * self.d_ref**2

    @property
    def fineness_ratio(self) -> Dimensionless:
        """Overall length over body diameter."""
        return self.total_length / self.d_ref

    @property
    def tail_fins(self) -> FinSetGeometry:
        """The aft-most fin set, the main stabilizer."""
        return self.fin_sets[-1]

    def with_tail_fin_span(self, span: float) -> RocketGeometry:
        """Copy of the geometry with a different tail-fin span."""
        return replace(self, fin_sets=(*self.fin_sets[:-1], replace(self.tail_fins, span=span)))


@dataclass(frozen=True)
class ComponentContribution:
    """Normal-force slope and center of pressure of one vehicle component.

    Attributes:
        name: Component name, e.g. ``"nose"``, ``"shoulder"`` or a fin-set name.
        cn_alpha: Normal-force-curve slope, referred to the body cross-section area.
        x_cp: Center of pressure from the nose tip.
    """

    name: str
    cn_alpha: PerRadian
    x_cp: Meters


@dataclass(frozen=True)
class StabilityResult:
    """Component build-up of the vehicle center of pressure at one Mach number.

    Attributes:
        mach: Freestream Mach number.
        components: Per-component contributions.
        cn_alpha_total: Sum of the component slopes.
        x_cp: Slope-weighted center of pressure from the nose tip.
        static_margin: ``(x_cp - cg) / d_ref``. Positive is statically stable.
    """

    mach: Dimensionless
    components: tuple[ComponentContribution, ...]
    cn_alpha_total: PerRadian
    x_cp: Meters
    static_margin: Calibers


@dataclass(frozen=True)
class BarrowmanStabilityResults(BaseAnalysisResults):
    """Barrowman static stability at one Mach number.

    Attributes:
        geometry: Geometry the analysis used.
        mach: Evaluation Mach number.
        cn_alpha: Total normal-force-curve slope.
        cp: Center of pressure from the nose tip.
        cg: Center of gravity from the nose tip.
        static_margin: ``(cp - cg) / d_ref``.
        sm_required: Static margin the design rule asks for.
        margin: ``static_margin - sm_required``. Negative fails the rule.
        fineness_ratio: Overall length over body diameter.
        components: Per-component build-up at ``mach``.
        assumptions: Modeling assumptions this vehicle needed.
    """

    HEADLINE_METRICS: ClassVar[tuple[str, ...]] = (
        "static_margin",
        "sm_required",
        "cp",
        "cg",
        "cn_alpha",
    )

    geometry: RocketGeometry
    mach: Dimensionless
    cn_alpha: PerRadian
    cp: Meters
    cg: Meters
    static_margin: Calibers
    sm_required: Calibers
    margin: Calibers
    fineness_ratio: Dimensionless
    components: tuple[ComponentContribution, ...]
    assumptions: tuple[str, ...] = ()
