"""Tests for the extended Barrowman analysis: Galejs body lift and tail-fin sizing.

Expected values are evaluated with explicit arithmetic, independently of the module.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest

from YAADO_Core.Foundation.analysis_base import FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.stability_control.containers import (
    BarrowmanExtendedResults,
    FinSetGeometry,
    RocketGeometry,
)
from YAADO_Core.modules.stability_control.methods.barrowman.barrowman_extended import (
    BarrowmanExtendedAnalysis,
    body_planform,
    extended_build_up,
    find_tail_span,
    format_span_sweep_csv,
    galejs_body_lift,
    plot_span_sweep,
    run_span_sweep,
    static_margin_for_span,
)
from YAADO_Core.modules.stability_control.methods.barrowman.barrowman_stability import (
    compute_stability_at_mach,
)

ALVRJ_PATH = Path("Hangar/examples/ALVRJ/ALVRJ.toml")
HARPOON_PATH = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")

FINS = FinSetGeometry(
    name="tail", count=4, span=0.1, root_chord=0.1, tip_chord=0.1, sweep=0.0, root_le_x=1.4
)


def _rocket(**overrides: object) -> RocketGeometry:
    geometry = RocketGeometry(
        d_ref=0.1,
        nose_type="conical",
        nose_length=0.3,
        nose_base_diameter=0.1,
        total_length=1.5,
        cg_from_nose=0.9,
        fin_sets=(FINS,),
    )
    return replace(geometry, **overrides)  # type: ignore[arg-type]


def test_conical_planform_is_a_triangle_and_a_rectangle() -> None:
    """Cone: triangle 0.5 d L at 2/3 L; cylinder d (L_total - L) at its middle."""
    area, centroid = body_planform(_rocket())
    nose_area, cyl_area = 0.5 * 0.1 * 0.3, 0.1 * 1.2  # = 0.015, 0.12
    expected_centroid = (nose_area * 0.2 + cyl_area * 0.9) / (nose_area + cyl_area)  # = 0.822222
    assert area == pytest.approx(nose_area + cyl_area, rel=1e-6)
    assert centroid == pytest.approx(expected_centroid, rel=1e-6)


def test_ogive_and_hemisphere_planforms() -> None:
    """Tangent ogive lies between a cone and a cylinder; a hemisphere nose is pi R^2 / 2."""
    ogive_area, _ = body_planform(_rocket(nose_type="ogive"))
    assert 0.015 + 0.12 < ogive_area < 0.03 + 0.12
    hemisphere_area, _ = body_planform(_rocket(nose_type="hemispherical", nose_length=0.05))
    assert hemisphere_area == pytest.approx(math.pi * 0.05**2 / 2.0 + 0.1 * 1.45, rel=1e-4)


def test_body_lift_by_hand() -> None:
    """CN_body = 1.1 (A_plan / A_ref) sin^2(alpha); secant slope CN_body / alpha."""
    alpha = math.radians(8.0)
    a_ref = math.pi / 4.0 * 0.1**2  # = 0.00785398
    expected = 1.1 * 0.135 / a_ref * math.sin(alpha) ** 2 / alpha  # = 2.62289
    lift = galejs_body_lift(_rocket(), 8.0)
    assert lift.name == "body_lift"
    assert lift.cn_alpha == pytest.approx(expected, rel=1e-6)
    assert lift.cn_alpha == pytest.approx(2.62289, rel=1e-5)
    assert lift.x_cp == pytest.approx(0.822222, rel=1e-5)


def test_body_lift_vanishes_at_zero_alpha() -> None:
    """At alpha = 0 the extended build-up is the Barrowman one."""
    assert galejs_body_lift(_rocket(), 0.0).cn_alpha == 0.0
    _, _, cp = extended_build_up(_rocket(), 0.3, 0.0)
    assert cp == pytest.approx(compute_stability_at_mach(_rocket(), 0.3).x_cp)


def test_body_lift_pulls_the_cp_toward_the_planform_centroid() -> None:
    """With the centroid ahead of the Barrowman CP, more alpha means less margin."""
    margins = [static_margin_for_span(_rocket(), 0.1, 0.3, a) for a in (0.0, 5.0, 10.0)]
    assert margins[0] > margins[1] > margins[2]


def test_tail_span_search_hits_the_target() -> None:
    """The found span gives the target margin; an unreachable target gives None."""
    span = find_tail_span(_rocket(), 0.3, 5.0, 1.0)
    assert span is not None
    assert static_margin_for_span(_rocket(), span, 0.3, 5.0) == pytest.approx(1.0, abs=1e-6)
    assert find_tail_span(_rocket(), 0.3, 5.0, 50.0) is None


def test_span_sweep_csv_and_figure() -> None:
    """The sweep spans 0.4 to 1.6 times the span; CSV and figure follow it."""
    results = _run(ALVRJ_PATH)
    points = run_span_sweep(results.geometry, 0.3, 5.0)
    assert points[0].span == pytest.approx(0.4 * 0.28)
    assert points[-1].span == pytest.approx(1.6 * 0.28)
    middle = points[len(points) // 2]  # today's span
    assert middle.span == pytest.approx(0.28)
    assert middle.static_margin < middle.static_margin_basic
    lines = format_span_sweep_csv(points).strip().splitlines()
    assert lines[0] == "span,static_margin_basic,static_margin"
    assert len(lines) == len(points) + 1
    assert len(plot_span_sweep(points, results).axes) == 1


def _run(path: Path, **settings: float) -> BarrowmanExtendedResults:
    analysis = BarrowmanExtendedAnalysis()
    analysis.setup(BaseVehicleConfig.from_toml(path), enable_logging=False, **settings)
    return analysis.execute()


def test_analysis_on_alvrj() -> None:
    """ALVRJ at Mach 0.3 and 5 deg: body lift lowers the margin; spans are sized."""
    results = _run(ALVRJ_PATH)
    assert results.fidelity == FidelityLevel.LEVEL_0
    assert results.alpha == 5.0
    assert results.static_margin < results.static_margin_basic
    assert results.static_margin_basic == pytest.approx(_run(ALVRJ_PATH, alpha_deg=0.0).static_margin)
    assert results.tail_fin_set == "aft_control_fins"
    assert results.tail_span == pytest.approx(0.28)
    assert results.neutral_tail_span is not None
    assert results.required_tail_span is not None
    assert results.neutral_tail_span < results.required_tail_span < results.tail_span
    assert [c.name for c in results.components][-1] == "body_lift"


def test_analysis_on_harpoon_sizes_only_the_tail() -> None:
    """Harpoon misses the 10 % rule: the required tail span is larger than today's."""
    results = _run(HARPOON_PATH)
    assert results.required_tail_span is not None
    assert results.required_tail_span > results.tail_span
    assert any("only the aft fin set" in a for a in results.assumptions)


def test_analysis_settings_and_errors() -> None:
    """Large alpha is flagged; bad settings fail."""
    results = _run(ALVRJ_PATH, alpha_deg=20.0, cg_from_nose=2.3, sm_required=0.5)
    assert results.cg == 2.3
    assert results.sm_required == 0.5
    assert any("Angle of attack 20" in a for a in results.assumptions)
    with pytest.raises(ValueError, match="alpha_deg"):
        _run(ALVRJ_PATH, alpha_deg=-1.0)
    with pytest.raises(TypeError, match="Unknown settings"):
        _run(ALVRJ_PATH, alpha=5.0)
