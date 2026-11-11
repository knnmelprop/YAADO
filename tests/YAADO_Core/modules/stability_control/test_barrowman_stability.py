"""Tests for the Barrowman static stability analysis.

The hand checks evaluate the Barrowman equations (NARAM-8, 1966) with explicit
arithmetic, independently of the module, for a small rocket built by hand.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest

from YAADO_Core.ComponentStore import Fins
from YAADO_Core.Foundation.analysis_base import FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.stability_control.containers import (
    BarrowmanStabilityResults,
    FinSetGeometry,
    RocketGeometry,
)
from YAADO_Core.modules.stability_control.methods.barrowman.barrowman_stability import (
    BarrowmanStabilityAnalysis,
    compute_stability_at_mach,
    fin_set_cn_alpha_and_cp,
    format_mach_sweep_csv,
    geometry_from_vehicle,
    nose_cn_alpha_and_cp,
    plot_cp_vs_mach,
    run_mach_sweep,
    transition_cn_alpha_and_cp,
)

ALVRJ_PATH = Path("Hangar/examples/ALVRJ/ALVRJ.toml")
HARPOON_PATH = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")

# Unswept rectangular tail: 4 fins, s = c = 0.1 m, on a 0.1 m body.
SQUARE_FINS = FinSetGeometry(
    name="tail", count=4, span=0.1, root_chord=0.1, tip_chord=0.1, sweep=0.0, root_le_x=1.4
)


def _rocket(**overrides: object) -> RocketGeometry:
    geometry = RocketGeometry(
        d_ref=0.1,
        nose_type="ogive",
        nose_length=0.3,
        nose_base_diameter=0.1,
        total_length=1.5,
        cg_from_nose=0.9,
        fin_sets=(SQUARE_FINS,),
    )
    return replace(geometry, **overrides)  # type: ignore[arg-type]


# --- Hand checks of the component equations (#78) ----------------------------------


@pytest.mark.parametrize(
    ("nose_type", "cp_factor"),
    [("conical", 2.0 / 3.0), ("ogive", 0.466), ("hemispherical", 1.0 / 3.0)],
)
def test_nose_slope_and_cp_by_shape(nose_type: str, cp_factor: float) -> None:
    """Nose CN_alpha = 2 for a full-diameter base; CP = k * L_nose per Barrowman."""
    cn_alpha, x_cp = nose_cn_alpha_and_cp(_rocket(nose_type=nose_type))
    assert cn_alpha == pytest.approx(2.0)
    assert x_cp == pytest.approx(cp_factor * 0.3)


def test_narrow_nose_and_shoulder_share_the_body_slope() -> None:
    """Nose base 0.08 m on a 0.1 m body: nose 2*0.64, step 2*(1 - 0.64), sum 2."""
    geometry = _rocket(nose_base_diameter=0.08)
    cn_nose, _ = nose_cn_alpha_and_cp(geometry)
    cn_step, x_step = transition_cn_alpha_and_cp(geometry)
    assert cn_nose == pytest.approx(1.28)  # 2 * (0.08/0.1)^2
    assert cn_step == pytest.approx(0.72)  # 2 * (1 - 0.64)
    assert x_step == pytest.approx(0.3)  # step sits at the nose base
    assert transition_cn_alpha_and_cp(_rocket())[0] == pytest.approx(0.0)


def test_rectangular_fin_set_by_hand() -> None:
    """Unswept square fins: l_F = s, so the denominator is 1 + sqrt(2)."""
    cn_alpha, x_cp = fin_set_cn_alpha_and_cp(SQUARE_FINS, body_radius=0.05, d_ref=0.1)
    k_fb = 1.0 + 0.05 / (0.1 + 0.05)  # = 1.33333
    expected_cn = k_fb * 4.0 * 4 * (0.1 / 0.1) ** 2 / (1.0 + math.sqrt(1.0 + 1.0))  # = 8.83663
    expected_x = 1.4 + (0.2 - 0.01 / 0.2) / 6.0  # = 1.425
    assert cn_alpha == pytest.approx(expected_cn, rel=1e-12)
    assert cn_alpha == pytest.approx(8.83663, rel=1e-5)
    assert x_cp == pytest.approx(expected_x, rel=1e-12)


def test_swept_trapezoidal_fin_set_by_hand() -> None:
    """ALVRJ tail: N=4, s=0.28, Cr=0.65, Ct=0.15, 60 deg LE sweep, d=0.381 m."""
    fins = FinSetGeometry(
        name="tail", count=4, span=0.28, root_chord=0.65, tip_chord=0.15, sweep=60.0, root_le_x=3.92
    )
    x_r = 0.28 * math.tan(math.radians(60.0))  # = 0.484974
    mid_chord_line = math.sqrt(0.28**2 + (x_r + 0.075 - 0.325) ** 2)  # = 0.365530
    k_fb = 1.0 + 0.1905 / (0.28 + 0.1905)  # = 1.404888
    expected_cn = (
        k_fb * 16.0 * (0.28 / 0.381) ** 2 / (1.0 + math.sqrt(1.0 + (2.0 * mid_chord_line / 0.8) ** 2))
    )  # = 5.15589
    expected_x = 3.92 + x_r * 0.95 / 2.4 + (0.8 - 0.0975 / 0.8) / 6.0  # = 4.22499

    cn_alpha, x_cp = fin_set_cn_alpha_and_cp(fins, body_radius=0.1905, d_ref=0.381)

    assert cn_alpha == pytest.approx(expected_cn, rel=1e-12)
    assert cn_alpha == pytest.approx(5.15589, rel=1e-5)
    assert x_cp == pytest.approx(expected_x, rel=1e-12)
    assert x_cp == pytest.approx(4.22499, rel=1e-5)


def test_fin_slope_grows_with_aspect_ratio() -> None:
    """A longer span at the same chord gives a larger slope per unit fin area."""
    short, _ = fin_set_cn_alpha_and_cp(SQUARE_FINS, body_radius=0.05, d_ref=0.1)
    long, _ = fin_set_cn_alpha_and_cp(replace(SQUARE_FINS, span=0.2), 0.05, 0.1)
    assert long / 0.2 > short / 0.1


def test_subsonic_fin_slope_by_hand() -> None:
    """Square fins at Mach 0.6: beta = 0.8 scales the aspect-ratio term (Diederich)."""
    cn_alpha, _ = fin_set_cn_alpha_and_cp(SQUARE_FINS, 0.05, 0.1, mach=0.6)
    expected = (4.0 / 3.0) * 16.0 / (1.0 + math.sqrt(1.0 + 0.8**2))  # = 9.35417
    assert cn_alpha == pytest.approx(expected, rel=1e-12)
    assert cn_alpha == pytest.approx(9.35417, rel=1e-5)


def test_low_aspect_ratio_fins_gain_less_than_prandtl_glauert() -> None:
    """A low-aspect-ratio fin set barely changes with subsonic Mach."""
    at_rest, _ = fin_set_cn_alpha_and_cp(SQUARE_FINS, 0.05, 0.1)
    at_m08, _ = fin_set_cn_alpha_and_cp(SQUARE_FINS, 0.05, 0.1, mach=0.79)
    assert 1.0 < at_m08 / at_rest < 1.0 / math.sqrt(1.0 - 0.79**2)


def test_supersonic_fin_slope_by_hand() -> None:
    """Square fins at Mach 2: Ackeret 4/beta, Puckett tip loss for AR = 2s/c = 2, N/2 panels."""
    beta = math.sqrt(3.0)  # = 1.732051
    eta = 1.0 - 1.0 / (2.0 * beta * 2.0)  # = 0.855662
    a_ref = math.pi / 4.0 * 0.1**2  # = 0.00785398
    expected = (4.0 / 3.0) * 2.0 * (4.0 / beta) * eta * 0.01 / a_ref  # = 6.70930
    cn_alpha, _ = fin_set_cn_alpha_and_cp(SQUARE_FINS, 0.05, 0.1, mach=2.0)
    assert cn_alpha == pytest.approx(expected, rel=1e-12)
    assert cn_alpha == pytest.approx(6.70930, rel=1e-5)


def test_tip_loss_is_held_at_its_floor_close_to_mach_one() -> None:
    """Below beta * AR = 1 the tip-loss factor stays at 1/2."""
    narrow = replace(SQUARE_FINS, span=0.02)  # AR = 0.4, beta * AR < 1 at Mach 1.6
    beta = math.sqrt(1.6**2 - 1.0)
    a_ref = math.pi / 4.0 * 0.1**2
    expected = (1.0 + 0.05 / 0.07) * 2.0 * (4.0 / beta) * 0.5 * 0.002 / a_ref
    assert fin_set_cn_alpha_and_cp(narrow, 0.05, 0.1, mach=1.6)[0] == pytest.approx(expected)


def test_transonic_bridge_is_continuous_and_rejects_negative_mach() -> None:
    """The bridge meets both regimes at its ends; the CP does not move with Mach."""
    for edge in (0.8, 1.5):
        below, x_below = fin_set_cn_alpha_and_cp(SQUARE_FINS, 0.05, 0.1, mach=edge - 1e-9)
        above, x_above = fin_set_cn_alpha_and_cp(SQUARE_FINS, 0.05, 0.1, mach=edge + 1e-9)
        assert below == pytest.approx(above, rel=1e-6)
        assert x_below == x_above
    with pytest.raises(ValueError):
        fin_set_cn_alpha_and_cp(SQUARE_FINS, 0.05, 0.1, mach=-0.1)


def test_total_cp_and_static_margin_by_hand() -> None:
    """Slope-weighted CP of nose and fins at Mach 0, and the margin in calibers."""
    geometry = _rocket()
    cn_fin = 1.3333333333333333 * 16.0 / (1.0 + math.sqrt(2.0))  # = 8.83663
    x_cp = (2.0 * 0.466 * 0.3 + cn_fin * 1.425) / (2.0 + cn_fin)  # = 1.18786

    point = compute_stability_at_mach(geometry, 0.0)

    assert [c.name for c in point.components] == ["nose", "tail"]
    assert point.cn_alpha_total == pytest.approx(2.0 + cn_fin)
    assert point.x_cp == pytest.approx(x_cp)
    assert point.static_margin == pytest.approx((x_cp - 0.9) / 0.1)  # = 2.8786


def test_forward_fin_set_moves_cp_forward() -> None:
    """Adding canards ahead of the CG reduces the static margin."""
    canards = replace(SQUARE_FINS, name="canards", span=0.05, root_le_x=0.4)
    tail_only = compute_stability_at_mach(_rocket(), 0.3)
    with_canards = compute_stability_at_mach(_rocket(fin_sets=(canards, SQUARE_FINS)), 0.3)
    assert with_canards.x_cp < tail_only.x_cp
    assert [c.name for c in with_canards.components] == ["nose", "canards", "tail"]


def test_mach_sweep_csv_and_figure() -> None:
    """The sweep starts at Mach 0, its CSV has one row per point and the plot returns."""
    points = run_mach_sweep(_rocket(), 2.0)
    assert points[0].mach == 0.0
    assert points[-1].mach == pytest.approx(2.0)
    lines = format_mach_sweep_csv(points).strip().splitlines()
    assert lines[0] == "mach,cn_alpha_total_per_rad,x_cp_m,static_margin_cal"
    assert len(lines) == len(points) + 1
    fig = plot_cp_vs_mach(points, _rocket())
    assert len(fig.axes) == 2


# --- Geometry from the vehicle configuration (#79) ---------------------------------


def test_geometry_from_alvrj_places_unpositioned_fins_at_the_tail() -> None:
    """ALVRJ: one fin set without a position sits flush with the body end."""
    geometry = geometry_from_vehicle(BaseVehicleConfig.from_toml(ALVRJ_PATH))
    assert geometry.d_ref == pytest.approx(0.381)
    assert geometry.nose_type == "ogive"
    assert geometry.cg_from_nose == pytest.approx(2.1)
    assert [f.name for f in geometry.fin_sets] == ["aft_control_fins"]
    assert geometry.tail_fins.root_le_x == pytest.approx(4.57 - 0.65)


def test_geometry_from_harpoon_orders_fin_sets_front_to_back() -> None:
    """Harpoon: wings and tail fins both count; Wings-type surfaces do not."""
    geometry = geometry_from_vehicle(BaseVehicleConfig.from_toml(HARPOON_PATH))
    assert [f.name for f in geometry.fin_sets] == ["mid_body_wings", "aft_control_fins"]
    assert geometry.fin_sets[0].root_le_x == pytest.approx(1.5)
    assert geometry.tail_fins.name == "aft_control_fins"


def test_geometry_cg_override() -> None:
    """An explicit CG replaces the vehicle mass properties."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_PATH)
    assert geometry_from_vehicle(vehicle, cg_from_nose=2.5).cg_from_nose == 2.5


def test_geometry_rejects_vehicle_without_fins() -> None:
    """A vehicle with no fin set cannot use Barrowman."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_PATH)
    vehicle.aero_surfaces.pop("aft_control_fins")
    with pytest.raises(ValueError, match="no fin set"):
        geometry_from_vehicle(vehicle)


def test_geometry_rejects_two_unpositioned_fin_sets() -> None:
    """Two fin sets cannot both default to the aft end."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_PATH)
    vehicle.aero_surfaces["canards"] = Fins(
        count=4, span=0.1, sweep=30.0, chord_root=0.2, chord_tip=0.1
    )
    with pytest.raises(ValueError, match="root_le_from_nose"):
        geometry_from_vehicle(vehicle)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [("nose_diameter", 0.5, "wider than the body"), ("length", 1.5, "slender-body")],
)
def test_geometry_rejects_unsupported_bodies(field: str, value: float, message: str) -> None:
    """A flared nose or a stubby body is outside the method."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_PATH)
    setattr(vehicle.bodies["fuselage"], field, value)
    with pytest.raises(ValueError, match=message):
        geometry_from_vehicle(vehicle)


def test_geometry_requires_a_cg() -> None:
    """Without mass properties anywhere, the CG must be passed in."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_PATH)
    vehicle.mass_properties = None
    vehicle.bodies["fuselage"].mass = None
    with pytest.raises(ValueError, match="cg_from_nose"):
        geometry_from_vehicle(vehicle)


# --- Typed analysis (#80) ----------------------------------------------------------


def _run(path: Path, **settings: float) -> BarrowmanStabilityResults:
    analysis = BarrowmanStabilityAnalysis()
    analysis.setup(BaseVehicleConfig.from_toml(path), enable_logging=False, **settings)
    return analysis.execute()


def test_analysis_on_alvrj_matches_hand_build_up() -> None:
    """ALVRJ at Mach 0.3: nose + tail fins with the Diederich term."""
    results = _run(ALVRJ_PATH)

    # Barrowman numerator K_fb * 4N (s/d)^2 and the beta-scaled l_F term at Mach 0.3
    numerator = (1.0 + 0.1905 / 0.4705) * 16.0 * (0.28 / 0.381) ** 2  # = 12.14025
    lf_term = 2.0 * math.sqrt(1.0 - 0.3**2) * 0.365530 / 0.8  # = 0.871733
    cn_fin = numerator / (1.0 + math.sqrt(1.0 + lf_term**2))  # = 5.21794
    x_cp = (2.0 * 0.466 * 0.95 + cn_fin * 4.224990) / (2.0 + cn_fin)  # = 3.19390
    assert results.fidelity == FidelityLevel.LEVEL_0
    assert results.mach == 0.3
    assert results.cn_alpha == pytest.approx(2.0 + cn_fin, rel=1e-5)
    assert results.cp == pytest.approx(x_cp, rel=1e-5)
    assert results.cg == pytest.approx(2.1)
    assert results.static_margin == pytest.approx((x_cp - 2.1) / 0.381, rel=1e-4)  # = 2.896
    assert results.sm_required == pytest.approx(0.1 * 4.57 / 0.381)
    assert results.margin == pytest.approx(results.static_margin - results.sm_required)
    assert any("flush with the aft end" in a for a in results.assumptions)
    assert any("intake_strakes" in a for a in results.assumptions)


def test_analysis_on_harpoon_counts_both_fin_sets() -> None:
    """Harpoon wings pull the CP forward of the tail-only value."""
    results = _run(HARPOON_PATH)
    assert [c.name for c in results.components] == ["nose", "mid_body_wings", "aft_control_fins"]
    assert results.cg < results.cp < 3.84
    assert results.static_margin < results.sm_required


def test_analysis_settings_override_vehicle_values() -> None:
    """Mach, CG and the required margin can all be set for one run."""
    results = _run(ALVRJ_PATH, mach=1.5, cg_from_nose=2.6, sm_required=0.5)
    assert results.cg == 2.6
    assert results.sm_required == 0.5
    assert results.cn_alpha > _run(ALVRJ_PATH, cg_from_nose=2.6).cn_alpha  # supersonic fins
    assert any("subsonic method" in a for a in results.assumptions)


def test_analysis_rejects_unknown_settings() -> None:
    """A misspelled setting is an error, not silently ignored."""
    with pytest.raises(TypeError, match="Unknown settings"):
        _run(ALVRJ_PATH, mach_number=0.5)


def test_analysis_rejects_negative_mach() -> None:
    """Mach must be zero or positive."""
    with pytest.raises(ValueError, match="mach"):
        _run(ALVRJ_PATH, mach=-1.0)


def test_execute_before_setup_fails() -> None:
    """The template method refuses to compute without a vehicle."""
    with pytest.raises(RuntimeError):
        BarrowmanStabilityAnalysis().execute()


def test_scalars_and_units_are_reported() -> None:
    """Typed fields expose their SI and caliber units to the logger."""
    results = _run(ALVRJ_PATH)
    units = results.units()
    assert units["static_margin"] == "cal"
    assert units["cn_alpha"] == "1/rad"
    assert units["cp"] == "m"
    assert set(BarrowmanStabilityResults.headline_metrics()) <= set(results.scalars())
