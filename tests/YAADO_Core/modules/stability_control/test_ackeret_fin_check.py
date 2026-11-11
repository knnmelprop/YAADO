"""Tests for the Ackeret supersonic fin check.

Expected values are evaluated from the linearized supersonic equations with
explicit arithmetic, independently of the module.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest

from YAADO_Core.Foundation.analysis_base import FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.stability_control.containers import (
    AckeretFinResults,
    FinSetGeometry,
    RocketGeometry,
)
from YAADO_Core.modules.stability_control.methods.ackeret.ackeret_fin_check import (
    AckeretFinAnalysis,
    ackeret_build_up,
    ackeret_fin_set,
    format_mach_sweep_csv,
    plot_method_comparison,
    run_mach_sweep,
)

ALVRJ_PATH = Path("Hangar/examples/ALVRJ/ALVRJ.toml")
HARPOON_PATH = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")

# ALVRJ tail fins and body.
ALVRJ_FINS = FinSetGeometry(
    name="tail", count=4, span=0.28, root_chord=0.65, tip_chord=0.15, sweep=60.0, root_le_x=3.92
)
R_ALVRJ = 0.1905
A_REF_ALVRJ = math.pi / 4.0 * 0.381**2  # = 0.114009


def test_fin_set_slope_by_hand() -> None:
    """ALVRJ tail at Mach 2.5: a_2D = 4/beta, AR = s/c_mean, N/2 loaded panels."""
    beta = math.sqrt(2.5**2 - 1.0)  # = 2.291288
    slope = (4.0 / beta) / (1.0 + 2.0 / (0.28 / 0.4))  # = 0.452600
    k_fb = 1.0 + 0.1905 / (0.28 + 0.1905)  # = 1.404888
    expected = k_fb * 2.0 * slope * (0.28 * 0.4) / A_REF_ALVRJ  # = 1.249294

    fin = ackeret_fin_set(ALVRJ_FINS, 2.5, R_ALVRJ, A_REF_ALVRJ)

    assert fin.slope_2d == pytest.approx(4.0 / beta, rel=1e-12)
    assert fin.panel_aspect_ratio == pytest.approx(0.7, rel=1e-12)
    assert fin.cn_alpha == pytest.approx(expected, rel=1e-12)
    assert fin.cn_alpha == pytest.approx(1.249294, rel=1e-5)


def test_fin_set_cp_is_the_planform_centroid() -> None:
    """Uniform supersonic loading puts the CP at the trapezoid's area centroid."""
    x_r = 0.28 * math.tan(math.radians(60.0))  # = 0.484974
    x_centroid = (x_r * (0.65 + 0.30) + 0.65**2 + 0.65 * 0.15 + 0.15**2) / (3.0 * 0.8)  # = 0.418011
    fin = ackeret_fin_set(ALVRJ_FINS, 2.5, R_ALVRJ, A_REF_ALVRJ)
    assert fin.x_cp == pytest.approx(3.92 + x_centroid, rel=1e-12)
    assert fin.x_cp == pytest.approx(4.338011, rel=1e-6)


def test_rectangular_fin_cp_is_at_half_chord() -> None:
    """For an unswept rectangular fin the centroid is at 50 % chord."""
    fins = replace(ALVRJ_FINS, root_chord=0.4, tip_chord=0.4, sweep=0.0)
    assert ackeret_fin_set(fins, 2.0, R_ALVRJ, A_REF_ALVRJ).x_cp == pytest.approx(3.92 + 0.2)


def test_three_fins_carry_one_and_a_half_panels() -> None:
    """Sum of sin^2 over N equally spaced fins is N/2, so 3 fins give 3/4 of 4 fins."""
    four = ackeret_fin_set(ALVRJ_FINS, 2.0, R_ALVRJ, A_REF_ALVRJ).cn_alpha
    three = ackeret_fin_set(replace(ALVRJ_FINS, count=3), 2.0, R_ALVRJ, A_REF_ALVRJ).cn_alpha
    assert three == pytest.approx(0.75 * four)


def test_leading_edge_normal_mach() -> None:
    """M cos(sweep) tells whether the leading edge is supersonic."""
    fin = ackeret_fin_set(ALVRJ_FINS, 2.5, R_ALVRJ, A_REF_ALVRJ)
    assert fin.normal_mach_le == pytest.approx(1.25)


def test_slope_falls_with_mach() -> None:
    """The supersonic slope decreases as 1/beta."""
    slopes = [ackeret_fin_set(ALVRJ_FINS, m, R_ALVRJ, A_REF_ALVRJ).cn_alpha for m in (1.5, 2.0, 3.0)]
    assert slopes[0] > slopes[1] > slopes[2]


@pytest.mark.parametrize("mach", [0.8, 1.0])
def test_subsonic_mach_is_rejected(mach: float) -> None:
    """Ackeret theory has no subsonic or sonic solution."""
    with pytest.raises(ValueError, match="supersonic"):
        ackeret_fin_set(ALVRJ_FINS, mach, R_ALVRJ, A_REF_ALVRJ)


def test_build_up_uses_barrowman_nose() -> None:
    """Nose slope 2 at 0.466 L for an ogive, followed by every fin set front to back."""
    canards = replace(ALVRJ_FINS, name="canards", span=0.1, root_le_x=1.2)
    geometry = RocketGeometry(
        d_ref=0.381,
        nose_type="ogive",
        nose_length=0.95,
        nose_base_diameter=0.381,
        total_length=4.57,
        cg_from_nose=2.1,
        fin_sets=(canards, ALVRJ_FINS),
    )
    fin_sets, components = ackeret_build_up(geometry, 2.0)
    assert [c.name for c in components] == ["nose", "canards", "tail"]
    assert components[0].cn_alpha == pytest.approx(2.0)
    assert components[0].x_cp == pytest.approx(0.466 * 0.95)
    assert [f.name for f in fin_sets] == ["canards", "tail"]


def _run(path: Path, **settings: float) -> AckeretFinResults:
    analysis = AckeretFinAnalysis()
    analysis.setup(BaseVehicleConfig.from_toml(path), enable_logging=False, **settings)
    return analysis.execute()


def test_analysis_on_alvrj_matches_hand_build_up() -> None:
    """ALVRJ at Mach 2.5: nose + Ackeret tail fins, CG from the TOML."""
    results = _run(ALVRJ_PATH, mach=2.5)
    cn_fin = 1.249294
    x_cp = (2.0 * 0.4427 + cn_fin * 4.338011) / (2.0 + cn_fin)  # = 1.940379
    assert results.fidelity == FidelityLevel.LEVEL_0
    assert results.cn_alpha == pytest.approx(2.0 + cn_fin, rel=1e-5)
    assert results.cp == pytest.approx(x_cp, rel=1e-5)
    assert results.static_margin == pytest.approx((x_cp - 2.1) / 0.381, rel=1e-4)  # = -0.419
    assert results.barrowman_static_margin > results.static_margin
    assert abs(results.tail_fin_cp_difference) < AckeretFinAnalysis.CP_DIFFERENCE_WARNING


def test_analysis_flags_subsonic_leading_edges_and_low_mach() -> None:
    """Harpoon mid-body wings (60 deg sweep) have a subsonic leading edge at Mach 1.15."""
    results = _run(HARPOON_PATH, mach=1.15)
    assert any("'mid_body_wings' has a subsonic leading edge" in a for a in results.assumptions)
    assert any("close to Mach 1" in a for a in results.assumptions)
    assert [f.name for f in results.fin_sets] == ["mid_body_wings", "aft_control_fins"]


def test_analysis_cg_override() -> None:
    """A forward CG raises the static margin of both methods by the same amount."""
    aft = _run(ALVRJ_PATH, mach=2.0)
    forward = _run(ALVRJ_PATH, mach=2.0, cg_from_nose=1.719)
    shift = (2.1 - 1.719) / 0.381  # = 1.0 cal
    assert forward.static_margin - aft.static_margin == pytest.approx(shift)
    assert forward.barrowman_static_margin - aft.barrowman_static_margin == pytest.approx(shift)


def test_analysis_rejects_subsonic_mach_and_unknown_settings() -> None:
    """The check runs only above Mach 1, and only with known settings."""
    with pytest.raises(ValueError, match="supersonic"):
        _run(ALVRJ_PATH, mach=0.9)
    with pytest.raises(TypeError, match="Unknown settings"):
        _run(ALVRJ_PATH, altitude=1000.0)


def test_sweep_csv_and_figure() -> None:
    """The comparison sweep covers 1.2 to the requested Mach and plots two panels."""
    geometry = _run(ALVRJ_PATH).geometry
    points = run_mach_sweep(geometry, 3.0)
    assert points[0].mach == pytest.approx(1.2)
    assert points[-1].mach == pytest.approx(3.0)
    lines = format_mach_sweep_csv(points).strip().splitlines()
    assert lines[0].startswith("mach,ackeret_fin_cn_alpha,barrowman_fin_cn_alpha")
    assert len(lines) == len(points) + 1
    assert len(plot_method_comparison(points, 2.0).axes) == 2
