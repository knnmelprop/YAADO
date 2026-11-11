"""Barrowman build-up with Galejs body lift, and tail-fin span sizing.

Linear Barrowman theory gives a cylinder no normal force, but a real body at an
angle of attack carries viscous cross-flow lift on its side-projected
(planform) area. Galejs adds it back, as OpenRocket does:

    CN_body = K * (A_planform / A_ref) * sin^2(alpha),  K = 1.1

acting at the planform centroid. The term grows with ``alpha^2``, so it is
zero at ``alpha = 0`` and moves the CP forward at the angle of attack of a gust
or a launch in wind. Its secant slope ``CN_body / alpha`` joins the Barrowman
components.

The analysis also sizes the tail fins: the span at which the static margin with
body lift reaches the required value, and the span at which it reaches zero.

References: Galejs, R., *What Barrowman Left Out*, High Power Rocketry 9(3), 1998
(``alpha^2`` form, K about 1.0 to 1.1); Niskanen, S., *Development of an Open
Source Model Rocket Simulation Software*, M.Sc. thesis, Helsinki University of
Technology, 2009, section "Effect of body lift" (``sin^2`` form, K = 1.1).
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import fields
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np
from scipy.optimize import brentq

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.stability_control.containers import (
    BarrowmanExtendedResults,
    ComponentContribution,
    FinSpanSweepPoint,
    RocketGeometry,
)
from YAADO_Core.modules.stability_control.methods.barrowman.barrowman_stability import (
    BarrowmanStabilityAnalysis,
    compute_stability_at_mach,
    geometry_assumptions,
    geometry_from_vehicle,
)


def nose_radius(geometry: RocketGeometry, x: np.ndarray) -> np.ndarray:
    """Nose radius [m] at axial stations ``0 <= x <= nose_length``.

    Conical: straight line. Ogive: tangent ogive. Hemispherical: ellipse with
    semi-axes ``nose_length`` and the base radius.
    """
    length = geometry.nose_length
    r_base = 0.5 * geometry.nose_base_diameter
    if geometry.nose_type == "conical":
        return r_base * x / length
    if geometry.nose_type == "ogive":
        rho = (r_base**2 + length**2) / (2.0 * r_base)
        return np.sqrt(np.maximum(rho**2 - (length - x) ** 2, 0.0)) + r_base - rho
    return r_base * np.sqrt(np.maximum(1.0 - ((length - x) / length) ** 2, 0.0))


def body_planform(geometry: RocketGeometry) -> tuple[float, float]:
    """Side-projected area [m^2] of the body and its centroid [m from the nose tip].

    The nose profile is integrated numerically; the rest of the body is a cylinder
    of the reference diameter.
    """
    x = np.linspace(0.0, geometry.nose_length, BarrowmanExtendedAnalysis.NOSE_PROFILE_POINTS)
    width = 2.0 * nose_radius(geometry, x)
    nose_area = float(np.trapezoid(width, x))
    nose_moment = float(np.trapezoid(width * x, x))

    cylinder_length = geometry.total_length - geometry.nose_length
    cylinder_area = geometry.d_ref * cylinder_length
    cylinder_moment = cylinder_area * (geometry.nose_length + 0.5 * cylinder_length)

    area = nose_area + cylinder_area
    return area, (nose_moment + cylinder_moment) / area


def galejs_body_lift(geometry: RocketGeometry, alpha_deg: float) -> ComponentContribution:
    """Body lift as a component with secant slope ``CN_body / alpha`` [1/rad].

    Args:
        geometry: Rocket geometry.
        alpha_deg: Angle of attack [deg].

    Returns:
        The body-lift contribution, at the planform centroid.
    """
    area, centroid = body_planform(geometry)
    alpha = math.radians(alpha_deg)
    coefficient = BarrowmanExtendedAnalysis.BODY_LIFT_K * area / geometry.reference_area
    secant_slope = coefficient * math.sin(alpha) ** 2 / alpha if alpha > 0.0 else 0.0
    return ComponentContribution("body_lift", secant_slope, centroid)


def extended_build_up(
    geometry: RocketGeometry, mach: float, alpha_deg: float
) -> tuple[tuple[ComponentContribution, ...], float, float]:
    """Barrowman components plus body lift.

    Returns:
        The components, the total secant slope and the CP [m from the nose tip].
    """
    basic = compute_stability_at_mach(geometry, mach)
    components = (*basic.components, galejs_body_lift(geometry, alpha_deg))
    cn_alpha = sum(c.cn_alpha for c in components)
    return components, cn_alpha, sum(c.cn_alpha * c.x_cp for c in components) / cn_alpha


def static_margin_for_span(
    geometry: RocketGeometry, span: float, mach: float, alpha_deg: float
) -> float:
    """Static margin with body lift [cal] for a different tail-fin span."""
    resized = geometry.with_tail_fin_span(span)
    _, _, cp = extended_build_up(resized, mach, alpha_deg)
    return (cp - geometry.cg_from_nose) / geometry.d_ref


def find_tail_span(
    geometry: RocketGeometry, mach: float, alpha_deg: float, target_margin: float
) -> float | None:
    """Smallest tail-fin span [m] whose static margin with body lift is ``target_margin``.

    Searches from ``SPAN_SEARCH_MIN_FRACTION`` to ``SPAN_SEARCH_MAX_FACTOR`` times
    the current span.

    Returns:
        The span, or None if the margin does not cross the target in that range.
    """
    span = geometry.tail_fins.span
    spans = np.linspace(
        BarrowmanExtendedAnalysis.SPAN_SEARCH_MIN_FRACTION * span,
        BarrowmanExtendedAnalysis.SPAN_SEARCH_MAX_FACTOR * span,
        BarrowmanExtendedAnalysis.SPAN_SEARCH_POINTS,
    )

    def gap(s: float) -> float:
        return static_margin_for_span(geometry, s, mach, alpha_deg) - target_margin

    values = [gap(float(s)) for s in spans]
    for i in range(len(spans) - 1):
        if values[i] == 0.0:
            return float(spans[i])
        if values[i] * values[i + 1] < 0.0:
            root: float = brentq(gap, float(spans[i]), float(spans[i + 1]), xtol=1e-9)
            return root
    return None


def run_span_sweep(geometry: RocketGeometry, mach: float, alpha_deg: float) -> list[FinSpanSweepPoint]:
    """Static margins with and without body lift across the tail-fin span range."""
    span = geometry.tail_fins.span
    spans = np.linspace(
        BarrowmanExtendedAnalysis.SWEEP_SPAN_MIN_FACTOR * span,
        BarrowmanExtendedAnalysis.SWEEP_SPAN_MAX_FACTOR * span,
        BarrowmanExtendedAnalysis.SWEEP_POINTS,
    )
    points = []
    for s in spans:
        resized = geometry.with_tail_fin_span(float(s))
        points.append(
            FinSpanSweepPoint(
                span=float(s),
                static_margin_basic=compute_stability_at_mach(resized, mach).static_margin,
                static_margin=static_margin_for_span(geometry, float(s), mach, alpha_deg),
            )
        )
    return points


def format_span_sweep_csv(points: list[FinSpanSweepPoint]) -> str:
    """CSV text of the tail-fin span sweep."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(f.name for f in fields(FinSpanSweepPoint))
    writer.writerows((p.span, p.static_margin_basic, p.static_margin) for p in points)
    return buffer.getvalue()


def plot_span_sweep(points: list[FinSpanSweepPoint], results: BarrowmanExtendedResults) -> Figure:
    """Plot static margin against tail-fin span, with and without body lift.

    Args:
        points: Output of :func:`run_span_sweep`.
        results: Results of the run, for the current and required spans.

    Returns:
        The matplotlib Figure instance.
    """
    import matplotlib.pyplot as plt

    spans = [p.span for p in points]
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.plot(spans, [p.static_margin_basic for p in points], ls="--", lw=2.0, label="Barrowman")
    ax.plot(
        spans,
        [p.static_margin for p in points],
        lw=2.0,
        label=f"With body lift at {results.alpha:g} deg",
    )
    ax.axhline(0.0, color="k", lw=0.8)
    ax.axhline(results.sm_required, color="tab:red", ls=":", label="Required margin")
    ax.axvline(results.tail_span, color="tab:gray", ls=":", label="Current span")
    if results.required_tail_span is not None:
        ax.plot(results.required_tail_span, results.sm_required, "o", color="tab:red",
                label=f"Required span {results.required_tail_span:.3f} m")
    ax.set_xlabel(f"Exposed span of '{results.tail_fin_set}' [m]")
    ax.set_ylabel("Static margin [cal]")
    ax.set_title(f"Tail-fin span sizing at Mach {results.mach:g}")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


class BarrowmanExtendedAnalysis(BaseAnalysis[BarrowmanExtendedResults]):
    """Static margin with Galejs body lift, and the tail-fin span that meets the rule.

    Example:
        analysis = BarrowmanExtendedAnalysis()
        analysis.setup(vehicle, mach=0.3, alpha_deg=8.0)
        results = analysis.execute()
        span = results.required_tail_span
    """

    fidelity = FidelityLevel.LEVEL_0

    #: Galejs body-lift coefficient [-].
    BODY_LIFT_K: ClassVar[float] = 1.1

    DEFAULT_MACH: ClassVar[float] = BarrowmanStabilityAnalysis.DEFAULT_MACH
    DEFAULT_ALPHA_DEG: ClassVar[float] = 5.0

    #: Above this angle of attack linear theory and the body-lift term are poor [deg].
    MAX_RELIABLE_ALPHA_DEG: ClassVar[float] = 15.0

    NOSE_PROFILE_POINTS: ClassVar[int] = 401

    #: Tail-fin span search for the required and neutral spans, as factors on the span.
    SPAN_SEARCH_MIN_FRACTION: ClassVar[float] = 0.01
    SPAN_SEARCH_MAX_FACTOR: ClassVar[float] = 5.0
    SPAN_SEARCH_POINTS: ClassVar[int] = 100

    #: Tail-fin span sweep for the figure, as factors on the span.
    SWEEP_SPAN_MIN_FACTOR: ClassVar[float] = 0.4
    SWEEP_SPAN_MAX_FACTOR: ClassVar[float] = 1.6
    SWEEP_POINTS: ClassVar[int] = 25

    def __init__(self, name: str = "barrowman_extended") -> None:
        super().__init__(name)
        self._geometry: RocketGeometry | None = None
        self._mach = self.DEFAULT_MACH
        self._alpha_deg = self.DEFAULT_ALPHA_DEG
        self._sm_required = 0.0
        self._assumptions: tuple[str, ...] = ()

    @property
    def geometry(self) -> RocketGeometry:
        """Geometry bound by :meth:`setup`.

        Raises:
            RuntimeError: Before :meth:`setup`.
        """
        if self._geometry is None:
            raise RuntimeError(f"Analysis '{self.name}' has not been setup yet.")
        return self._geometry

    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        body_name: str | None = None,
        mach: float = DEFAULT_MACH,
        alpha_deg: float = DEFAULT_ALPHA_DEG,
        cg_from_nose: float | None = None,
        sm_required: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Resolve the geometry and the evaluation settings.

        Args:
            vehicle: Vehicle with one axisymmetric body and at least one fin set.
            body_name: Body to use if the vehicle has more than one.
            mach: Evaluation Mach number.
            alpha_deg: Angle of attack for the body lift [deg].
            cg_from_nose: Center of gravity [m]. Defaults to the vehicle's.
            sm_required: Required static margin [cal]. Defaults to the Barrowman
                rule, a fraction of the body length.
            **kwargs: Not accepted; present for the ``BaseAnalysis`` signature.

        Raises:
            TypeError: If an unknown setting is passed.
            ValueError: If a setting is out of range or the vehicle lacks what the
                method needs.
        """
        if kwargs:
            raise TypeError(f"Unknown settings for '{self.name}': {sorted(kwargs)}")
        if mach < 0.0:
            raise ValueError(f"mach must be >= 0, got {mach}")
        if not 0.0 <= alpha_deg < 90.0:
            raise ValueError(f"alpha_deg must be in [0, 90), got {alpha_deg}")

        geometry = geometry_from_vehicle(vehicle, body_name=body_name, cg_from_nose=cg_from_nose)
        assumptions = geometry_assumptions(vehicle, geometry)
        if mach > BarrowmanStabilityAnalysis.MACH_SUBSONIC_LIMIT:
            assumptions.append(
                f"Mach {mach:g} is above {BarrowmanStabilityAnalysis.MACH_SUBSONIC_LIMIT:g}: "
                "Barrowman is a subsonic method, so the result is an estimate."
            )
        if alpha_deg > self.MAX_RELIABLE_ALPHA_DEG:
            assumptions.append(
                f"Angle of attack {alpha_deg:g} deg is above {self.MAX_RELIABLE_ALPHA_DEG:g} deg: "
                "the fin terms are linear, so the result is an estimate."
            )
        if len(geometry.fin_sets) > 1:
            assumptions.append(
                f"Span sizing changes only the aft fin set '{geometry.tail_fins.name}'."
            )

        self._geometry = geometry
        self._mach = mach
        self._alpha_deg = alpha_deg
        self._sm_required = (
            BarrowmanStabilityAnalysis.SM_REQUIRED_LENGTH_FRACTION * geometry.fineness_ratio
            if sm_required is None
            else sm_required
        )
        self._assumptions = tuple(assumptions)
        self.logger.info(
            "Configured extended Barrowman for vehicle '%s' (M=%.2f, alpha=%.1f deg, CG=%.3f m)",
            vehicle.name,
            mach,
            alpha_deg,
            geometry.cg_from_nose,
        )
        for assumption in self._assumptions:
            self.logger.warning(assumption)

    def _compute(self, **kwargs: Any) -> BarrowmanExtendedResults:
        """Evaluate the build-up with body lift and size the tail fins."""
        geometry = self.geometry
        basic = compute_stability_at_mach(geometry, self._mach)
        components, cn_alpha, cp = extended_build_up(geometry, self._mach, self._alpha_deg)
        area, centroid = body_planform(geometry)
        static_margin = (cp - geometry.cg_from_nose) / geometry.d_ref

        def span_for(target: float) -> float | None:
            return find_tail_span(geometry, self._mach, self._alpha_deg, target)

        results = BarrowmanExtendedResults(
            name=self.name,
            fidelity=self.fidelity,
            geometry=geometry,
            mach=self._mach,
            alpha=self._alpha_deg,
            body_planform_area=area,
            body_planform_centroid=centroid,
            body_cn_alpha=components[-1].cn_alpha,
            components=components,
            cn_alpha=cn_alpha,
            cp=cp,
            cp_basic=basic.x_cp,
            cg=geometry.cg_from_nose,
            static_margin=static_margin,
            static_margin_basic=basic.static_margin,
            sm_required=self._sm_required,
            margin=static_margin - self._sm_required,
            tail_fin_set=geometry.tail_fins.name,
            tail_span=geometry.tail_fins.span,
            required_tail_span=span_for(self._sm_required),
            neutral_tail_span=span_for(0.0),
            assumptions=self._assumptions,
        )
        self.logger.info(
            "Body lift CN_alpha=%.3f /rad at %.3f m; SM=%.2f cal (Barrowman %.2f); "
            "required tail span=%s m",
            results.body_cn_alpha,
            results.body_planform_centroid,
            results.static_margin,
            results.static_margin_basic,
            "none" if results.required_tail_span is None else f"{results.required_tail_span:.4f}",
        )
        return results

    def validate_results(self, results: BarrowmanExtendedResults) -> bool:
        """Check finite values, positive slopes and a CP on the vehicle.

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        if not all(math.isfinite(value) for value in results.scalars().values()):
            return False
        if any(c.cn_alpha < 0.0 for c in results.components) or results.cn_alpha <= 0.0:
            return False
        aft_end = max(
            results.geometry.total_length,
            *(f.root_le_x + f.sweep_length + f.tip_chord for f in results.geometry.fin_sets),
        )
        return 0.0 <= results.cp <= aft_end

