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


@dataclass(frozen=True)
class AckeretFinSlope:
    """Linearized supersonic normal-force slope of one fin set.

    Attributes:
        name: Fin set name.
        slope_2d: Ackeret 2-D section slope ``4 / beta``.
        cn_alpha: Fin-set slope with body interference, referred to the body
            cross-section area.
        x_cp: Planform centroid from the nose tip (uniform loading).
        normal_mach_le: Mach number normal to the leading edge, ``M cos(sweep)``.
            Below 1 the leading edge is subsonic and 2-D Ackeret theory overpredicts.
    """

    name: str
    slope_2d: PerRadian
    cn_alpha: PerRadian
    x_cp: Meters
    normal_mach_le: Dimensionless


@dataclass(frozen=True)
class AckeretSweepPoint:
    """Ackeret and Barrowman static margins at one supersonic Mach number."""

    mach: Dimensionless
    ackeret_fin_cn_alpha: PerRadian
    barrowman_fin_cn_alpha: PerRadian
    ackeret_static_margin: Calibers
    barrowman_static_margin: Calibers


@dataclass(frozen=True)
class AckeretFinResults(BaseAnalysisResults):
    """Supersonic static stability with 2-D Ackeret fins, checked against Barrowman.

    The nose and shoulder use the slender-body terms of the Barrowman build-up;
    every fin set uses two-dimensional Ackeret theory without tip loss.

    Attributes:
        geometry: Geometry the analysis used.
        mach: Evaluation Mach number (> 1).
        fin_sets: Ackeret slope and CP of each fin set, front to back.
        components: Whole-vehicle build-up with the Ackeret fins.
        cn_alpha: Total normal-force-curve slope.
        cp: Center of pressure from the nose tip.
        cg: Center of gravity from the nose tip.
        static_margin: ``(cp - cg) / d_ref`` with Ackeret fins.
        barrowman_cp: Center of pressure of the Barrowman build-up at ``mach``.
        barrowman_static_margin: Static margin of the Barrowman build-up at ``mach``.
        tail_fin_cp_difference: Ackeret minus Barrowman CP of the tail fins.
        assumptions: Modeling assumptions this vehicle and Mach number needed.
    """

    HEADLINE_METRICS: ClassVar[tuple[str, ...]] = (
        "static_margin",
        "barrowman_static_margin",
        "cp",
        "barrowman_cp",
        "tail_fin_cp_difference",
    )

    geometry: RocketGeometry
    mach: Dimensionless
    fin_sets: tuple[AckeretFinSlope, ...]
    components: tuple[ComponentContribution, ...]
    cn_alpha: PerRadian
    cp: Meters
    cg: Meters
    static_margin: Calibers
    barrowman_cp: Meters
    barrowman_static_margin: Calibers
    tail_fin_cp_difference: Calibers
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class DatcomFinSlope:
    """DATCOM-class supersonic normal-force slope of one fin set.

    Attributes:
        name: Fin set name.
        slope_2d: Ackeret 2-D section slope ``4 / beta``.
        exposed_aspect_ratio: Aspect ratio of the two exposed panels joined at the root.
        tip_loss_factor: Supersonic tip-loss factor on the section slope.
        tip_loss_limited: True when ``beta * AR < 1`` and the factor sits at its floor.
        cn_alpha: Fin-set slope referred to the body cross-section area.
        x_cp: Planform centroid from the nose tip.
    """

    name: str
    slope_2d: PerRadian
    exposed_aspect_ratio: Dimensionless
    tip_loss_factor: Dimensionless
    tip_loss_limited: bool
    cn_alpha: PerRadian
    x_cp: Meters


@dataclass(frozen=True)
class DatcomStabilityResults(BaseAnalysisResults):
    """DATCOM-class supersonic static stability at one Mach number.

    Attributes:
        geometry: Geometry the analysis used.
        mach: Evaluation Mach number (> 1).
        fin_sets: Supersonic slope and CP of each fin set, front to back.
        components: Whole-vehicle build-up.
        cn_alpha: Total normal-force-curve slope.
        cp: Center of pressure from the nose tip.
        cg: Center of gravity from the nose tip.
        static_margin: ``(cp - cg) / d_ref``.
        sm_required: Static margin the design rule asks for.
        margin: ``static_margin - sm_required``. Negative fails the rule.
        assumptions: Modeling assumptions this vehicle and Mach number needed.
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
    fin_sets: tuple[DatcomFinSlope, ...]
    components: tuple[ComponentContribution, ...]
    cn_alpha: PerRadian
    cp: Meters
    cg: Meters
    static_margin: Calibers
    sm_required: Calibers
    margin: Calibers
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class FinSpanSweepPoint:
    """Static margins for one tail-fin span."""

    span: Meters
    static_margin_basic: Calibers
    static_margin: Calibers


@dataclass(frozen=True)
class BarrowmanExtendedResults(BaseAnalysisResults):
    """Barrowman build-up with Galejs body lift, and tail-fin span sizing.

    Attributes:
        geometry: Geometry the analysis used.
        mach: Evaluation Mach number.
        alpha: Angle of attack the body lift is evaluated at.
        body_planform_area: Side-projected area of the body.
        body_planform_centroid: Centroid of that area from the nose tip.
        body_cn_alpha: Secant slope ``CN_body / alpha`` of the body lift at ``alpha``.
        components: Build-up including the body lift.
        cn_alpha: Total secant normal-force slope at ``alpha``.
        cp: Center of pressure with body lift.
        cp_basic: Center of pressure of the plain Barrowman build-up.
        cg: Center of gravity from the nose tip.
        static_margin: Static margin with body lift.
        static_margin_basic: Static margin of the plain Barrowman build-up.
        sm_required: Static margin the design rule asks for.
        margin: ``static_margin - sm_required``. Negative fails the rule.
        tail_fin_set: Name of the fin set whose span is sized.
        tail_span: Current exposed span of that fin set.
        required_tail_span: Span at which ``static_margin`` reaches ``sm_required``,
            or None if no span in the search range does.
        neutral_tail_span: Span at which ``static_margin`` is zero, or None.
        assumptions: Modeling assumptions this vehicle and condition needed.
    """

    HEADLINE_METRICS: ClassVar[tuple[str, ...]] = (
        "static_margin",
        "static_margin_basic",
        "sm_required",
        "cp",
        "tail_span",
    )

    geometry: RocketGeometry
    mach: Dimensionless
    alpha: Degrees
    body_planform_area: SquareMeters
    body_planform_centroid: Meters
    body_cn_alpha: PerRadian
    components: tuple[ComponentContribution, ...]
    cn_alpha: PerRadian
    cp: Meters
    cp_basic: Meters
    cg: Meters
    static_margin: Calibers
    static_margin_basic: Calibers
    sm_required: Calibers
    margin: Calibers
    tail_fin_set: str
    tail_span: Meters
    required_tail_span: Meters | None
    neutral_tail_span: Meters | None
    assumptions: tuple[str, ...] = ()
