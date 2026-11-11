"""Tests for the Taylor-Maccoll conical shock and the single-cone inlet analysis."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from YAADO_Core.Foundation.analysis_base import FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.powerplant.containers import ConicalInletResults
from YAADO_Core.modules.powerplant.inlet_methods.taylor_maccoll import (
    ConicalInletAnalysis,
    format_mach_sweep_csv,
    inlet_recovery,
    max_attached_cone_half_angle,
    mil_e_5007d_recovery,
    normal_shock,
    oblique_shock,
    plot_recovery_vs_mach,
    run_mach_sweep,
    solve_conical_shock,
)

ALVRJ_PATH = Path("Hangar/examples/ALVRJ/ALVRJ.toml")


# Values from issue #130 (own Taylor-Maccoll solution; tolerance 0.05 deg).
@pytest.mark.parametrize(
    ("half_angle_deg", "mach", "shock_angle_deg"),
    [
        (9.46, 1.5, 42.51),
        (9.46, 2.0, 31.01),
        (5.71, 2.0, 30.16),
        (4.09, 2.0, 30.04),
        (4.09, 3.0, 19.58),
        (4.09, 5.0, 11.94),
        (14.04, 2.0, 33.29),
    ],
)
def test_conical_shock_angle_including_thin_cones(
    half_angle_deg: float, mach: float, shock_angle_deg: float
) -> None:
    """The weak attached shock is found, also for cones only a few degrees thick."""
    shock = solve_conical_shock(mach, math.radians(half_angle_deg))
    assert shock is not None
    assert shock.shock_angle == pytest.approx(shock_angle_deg, abs=0.05)
    assert 1.0 < shock.mach_cone_surface < shock.mach_behind_shock < mach


def test_too_blunt_cone_has_a_detached_shock() -> None:
    """A 42 deg cone at Mach 1.5 is beyond the attached limit."""
    assert solve_conical_shock(1.5, math.radians(42.0)) is None


def test_max_attached_half_angle_brackets_the_solutions() -> None:
    """Just below the limit the shock is attached, just above it is not."""
    limit = max_attached_cone_half_angle(2.0)
    assert math.degrees(limit) == pytest.approx(40.5, abs=0.5)  # Anderson, Fig. 10.4
    assert solve_conical_shock(2.0, limit - math.radians(0.3)) is not None
    assert solve_conical_shock(2.0, limit + math.radians(0.3)) is None


def test_normal_shock_by_hand() -> None:
    """Mach 2 normal shock in air: M2 = 0.5774, pt2/pt1 = 0.7209 (Anderson, App. B)."""
    mach2, pt_ratio = normal_shock(2.0, 1.4)
    assert mach2 == pytest.approx(math.sqrt((1.0 + 0.2 * 4.0) / (1.4 * 4.0 - 0.2)))
    assert mach2 == pytest.approx(0.5774, abs=1e-4)
    assert pt_ratio == pytest.approx(0.7209, abs=1e-4)
    assert normal_shock(0.8, 1.4) == (0.8, 1.0)


def test_oblique_shock_reduces_to_normal_shock_at_ninety_degrees() -> None:
    """A 90 deg oblique shock turns nothing and loses what a normal shock loses."""
    delta, _, pt_ratio = oblique_shock(2.0, math.radians(90.0), 1.4)
    assert delta == pytest.approx(0.0, abs=1e-12)
    assert pt_ratio == pytest.approx(normal_shock(2.0, 1.4)[1])


def test_mil_e_5007d_reference() -> None:
    """1 - 0.075 (M - 1)^1.35 above Mach 1, and 1 below."""
    assert mil_e_5007d_recovery(2.5) == pytest.approx(1.0 - 0.075 * 1.5**1.35)  # = 0.87036
    assert mil_e_5007d_recovery(0.9) == 1.0


def test_recovery_chain_multiplies_the_losses() -> None:
    """Recovery = conical shock x terminal normal shock x diffuser."""
    shock, pt_normal, recovery = inlet_recovery(2.5, 21.0, 0.97)
    assert shock is not None
    assert pt_normal == pytest.approx(normal_shock(shock.mach_behind_shock, 1.4)[1])
    assert recovery == pytest.approx(shock.pt_ratio * pt_normal * 0.97)


def test_detached_recovery_is_the_normal_shock_bound() -> None:
    """Above the attached limit, the bow shock is bounded by a normal shock."""
    shock, _, recovery = inlet_recovery(1.5, 42.0, 0.97)
    assert shock is None
    assert recovery == pytest.approx(normal_shock(1.5, 1.4)[1] * 0.97)


def _run(**settings: float) -> ConicalInletResults:
    analysis = ConicalInletAnalysis()
    analysis.setup(BaseVehicleConfig.from_toml(ALVRJ_PATH), enable_logging=False, **settings)
    return analysis.execute()


def test_analysis_on_alvrj_at_design_mach() -> None:
    """ALVRJ ramjet: Mach comes from design_mach, the spike angle from the setting."""
    results = _run(cone_half_angle_deg=21.0)
    assert results.fidelity == FidelityLevel.LEVEL_0
    assert results.mach == 2.6
    assert results.shock_angle is not None
    assert results.recovery_margin == pytest.approx(results.recovery - results.mil_e_5007d_recovery)
    assert any("placeholder" in a for a in results.assumptions)
    assert any("below the MIL-E-5007D" in a for a in results.assumptions)


def test_analysis_reports_detachment() -> None:
    """A blunt spike at low Mach is reported as detached."""
    results = _run(cone_half_angle_deg=42.0, mach=1.5, pi_diffuser=1.0)
    assert results.shock is None
    assert results.shock_angle is None
    assert any("Detached shock" in a for a in results.assumptions)
    assert not any("placeholder" in a for a in results.assumptions)


def test_analysis_reads_the_spike_from_the_vehicle() -> None:
    """spike_half_angle on the ramjet is used when no setting is given."""
    vehicle = BaseVehicleConfig.from_toml(ALVRJ_PATH)
    vehicle.propulsion["sustainer"].spike_half_angle = 15.0
    analysis = ConicalInletAnalysis()
    analysis.setup(vehicle, enable_logging=False)
    assert analysis.execute().cone_half_angle == 15.0


def test_analysis_errors() -> None:
    """No spike angle, a subsonic Mach or an unknown setting is an error."""
    with pytest.raises(ValueError, match="spike_half_angle"):
        _run()
    with pytest.raises(ValueError, match="supersonic"):
        _run(cone_half_angle_deg=20.0, mach=0.9)
    with pytest.raises(TypeError, match="Unknown settings"):
        _run(cone_half_angle_deg=20.0, altitude_m=1000.0)


def test_mach_sweep_csv_and_figure() -> None:
    """The sweep runs from Mach 1.2 and marks attached points."""
    results = _run(cone_half_angle_deg=21.0)
    points = run_mach_sweep(results)
    assert points[0].mach == pytest.approx(1.2)
    assert points[-1].mach == pytest.approx(1.5 * 2.6)
    assert points[-1].attached
    lines = format_mach_sweep_csv(points).strip().splitlines()
    assert lines[0] == "mach,recovery,mil_e_5007d_recovery,attached"
    assert len(plot_recovery_vs_mach(points, results).axes) == 1
