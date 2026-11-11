"""Tests for the DATCOM-class supersonic static stability analysis.

Expected values are evaluated from the linear supersonic equations with explicit
arithmetic, independently of the module.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest

from YAADO_Core.Foundation.analysis_base import FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.stability_control.containers import (
    DatcomStabilityResults,
    FinSetGeometry,
    RocketGeometry,
)
from YAADO_Core.modules.stability_control.methods.datcom.datcom_class_sweep import (
    DatcomStabilityAnalysis,
    datcom_build_up,
    datcom_fin_set,
    format_mach_sweep_csv,
    plot_cp_vs_mach,
    run_mach_sweep,
)

ALVRJ_PATH = Path("Hangar/examples/ALVRJ/ALVRJ.toml")
HARPOON_PATH = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")

# Small test rocket: 4 trapezoidal fins on a 0.1 m body.
FINS = FinSetGeometry(
    name="tail", count=4, span=0.10, root_chord=0.20, tip_chord=0.10, sweep=30.0, root_le_x=1.30
)
A_REF = math.pi / 4.0 * 0.1**2  # = 0.00785398


def _rocket(**overrides: object) -> RocketGeometry:
    geometry = RocketGeometry(
        d_ref=0.1,
        nose_type="conical",
        nose_length=0.4,
        nose_base_diameter=0.1,
        total_length=1.5,
        cg_from_nose=0.8,
        fin_sets=(FINS,),
    )
    return replace(geometry, **overrides)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("mach", "expected"),
    [
        # K_fb (N/2) (4/beta) eta A_panel/A_ref, AR = 2s/c_mean = 2*0.1/0.15 = 1.3333
        (2.0, (4 / 3) * 2.0 * (4.0 / math.sqrt(3.0)) * (1.0 - 1.0 / (2.0 * math.sqrt(3.0) * (4 / 3)))
         * 0.015 / A_REF),  # = 11.76160 * 0.783494 = 9.21520
        (3.0, (4 / 3) * 2.0 * (4.0 / math.sqrt(8.0)) * (1.0 - 1.0 / (2.0 * math.sqrt(8.0) * (4 / 3)))
         * 0.015 / A_REF),  # = 7.20250 * 0.867417 = 6.24760
    ],
)
def test_fin_slope_by_hand(mach: float, expected: float) -> None:
    """Ackeret slope with the Puckett tip loss of the exposed wing."""
    fin = datcom_fin_set(FINS, mach, 0.05, A_REF)
    assert fin.exposed_aspect_ratio == pytest.approx(4.0 / 3.0)
    assert fin.cn_alpha == pytest.approx(expected, rel=1e-12)
    assert not fin.tip_loss_limited


def test_fin_slope_values_for_a_calculator() -> None:
    """The same slopes as plain numbers."""
    assert datcom_fin_set(FINS, 2.0, 0.05, A_REF).cn_alpha == pytest.approx(9.21520, rel=1e-5)
    assert datcom_fin_set(FINS, 3.0, 0.05, A_REF).cn_alpha == pytest.approx(6.24760, rel=1e-5)


def test_tip_loss_floor_close_to_mach_one() -> None:
    """At Mach 1.2, beta * AR = 0.884 < 1: the factor is held at 1/2 and flagged."""
    fin = datcom_fin_set(FINS, 1.2, 0.05, A_REF)
    assert fin.tip_loss_factor == 0.5
    assert fin.tip_loss_limited


def test_fin_cp_is_the_planform_centroid() -> None:
    """Half the MAC at the MAC station equals the trapezoid centroid."""
    x_r = 0.1 * math.tan(math.radians(30.0))  # = 0.057735
    centroid = (x_r * (0.2 + 0.2) + 0.04 + 0.02 + 0.01) / (3.0 * 0.3)  # = 0.103438
    assert datcom_fin_set(FINS, 2.0, 0.05, A_REF).x_cp == pytest.approx(1.3 + centroid, rel=1e-12)


def test_slope_falls_with_mach_and_needs_supersonic_flow() -> None:
    """Above the tip-loss floor the slope falls with Mach; Mach <= 1 is rejected."""
    slopes = [datcom_fin_set(FINS, m, 0.05, A_REF).cn_alpha for m in (1.8, 2.5, 3.5)]
    assert slopes[0] > slopes[1] > slopes[2]
    with pytest.raises(ValueError, match="supersonic"):
        datcom_fin_set(FINS, 1.0, 0.05, A_REF)


def test_build_up_by_hand() -> None:
    """Cone nose at 2/3 L plus the fins, at Mach 2 and a 0.8 m CG."""
    fin_sets, components = datcom_build_up(_rocket(), 2.0)
    cn_fin = 9.21520
    x_fin = 1.3 + 0.103438
    x_cp = (2.0 * (2.0 / 3.0) * 0.4 + cn_fin * x_fin) / (2.0 + cn_fin)  # = 1.20072
    assert [c.name for c in components] == ["nose", "tail"]
    assert components[0].x_cp == pytest.approx(0.4 * 2.0 / 3.0)
    total = sum(c.cn_alpha for c in components)
    assert sum(c.cn_alpha * c.x_cp for c in components) / total == pytest.approx(x_cp, rel=1e-5)
    assert fin_sets[0].name == "tail"


def test_narrow_nose_adds_a_shoulder() -> None:
    """A nose base narrower than the body adds the step term."""
    _, components = datcom_build_up(_rocket(nose_base_diameter=0.08), 2.0)
    assert [c.name for c in components] == ["nose", "shoulder", "tail"]
    assert components[1].cn_alpha == pytest.approx(2.0 * (1.0 - 0.64))


def _run(path: Path, **settings: float) -> DatcomStabilityResults:
    analysis = DatcomStabilityAnalysis()
    analysis.setup(BaseVehicleConfig.from_toml(path), enable_logging=False, **settings)
    return analysis.execute()


def test_analysis_on_alvrj() -> None:
    """ALVRJ at Mach 2.5: typed results, margins and assumptions."""
    results = _run(ALVRJ_PATH, mach=2.5)
    assert results.fidelity == FidelityLevel.LEVEL_1
    assert results.cg == pytest.approx(2.1)
    assert results.static_margin == pytest.approx((results.cp - 2.1) / 0.381)
    assert results.sm_required == pytest.approx(0.1 * 4.57 / 0.381)
    assert results.margin == pytest.approx(results.static_margin - results.sm_required)
    assert results.fin_sets[0].x_cp > 4.0
    assert any("intake_strakes" in a for a in results.assumptions)


def test_analysis_counts_every_fin_set_and_flags_low_mach() -> None:
    """Harpoon wings and tail both count; Mach 1.1 is flagged."""
    results = _run(HARPOON_PATH, mach=1.1)
    assert [f.name for f in results.fin_sets] == ["mid_body_wings", "aft_control_fins"]
    assert any("close to Mach 1" in a for a in results.assumptions)
    assert any("tip-loss factor is held" in a for a in results.assumptions)


def test_analysis_settings_and_errors() -> None:
    """CG and required margin can be set; subsonic Mach and unknown settings fail."""
    results = _run(ALVRJ_PATH, mach=2.0, cg_from_nose=2.5, sm_required=0.5)
    assert results.cg == 2.5
    assert results.sm_required == 0.5
    with pytest.raises(ValueError, match="supersonic"):
        _run(ALVRJ_PATH, mach=0.9)
    with pytest.raises(TypeError, match="Unknown settings"):
        _run(ALVRJ_PATH, cg=2.0)


def test_sweep_csv_and_figure() -> None:
    """The sweep runs from Mach 1.2, the CSV adds the margin, the figure has two panels."""
    geometry = _rocket()
    points = run_mach_sweep(geometry, 3.0)
    assert points[0][0] == pytest.approx(1.2)
    assert points[-1][0] == pytest.approx(3.0)
    lines = format_mach_sweep_csv(points, geometry).strip().splitlines()
    assert lines[0] == "mach,cn_alpha_total_per_rad,x_cp_m,static_margin_cal"
    assert len(lines) == len(points) + 1
    assert len(plot_cp_vs_mach(points, geometry).axes) == 2
