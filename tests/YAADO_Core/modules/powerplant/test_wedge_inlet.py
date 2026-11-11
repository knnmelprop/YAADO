"""Tests for the oblique-shock relations and the multi-ramp inlet analysis.

Reference values are from NACA Report 1135, *Equations, Tables, and Charts for
Compressible Flow* (1953), for gamma = 1.4.
"""

from __future__ import annotations

import itertools
import math
from pathlib import Path

import pytest

from YAADO_Core.Foundation.analysis_base import FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.powerplant.containers import MultiShockInletResults
from YAADO_Core.modules.powerplant.inlet_methods.taylor_maccoll import normal_shock
from YAADO_Core.modules.powerplant.inlet_methods.wedge import (
    MultiShockInletAnalysis,
    equal_normal_mach_deflections,
    format_design_csv,
    oblique_shock_beta_rad,
    oswatitsch_chain,
    plot_design_curves,
    recovery_by_shock_count,
    recovery_vs_mach,
    shock_chain,
    theta_max_rad,
)

ALVRJ_PATH = Path("Hangar/examples/ALVRJ/ALVRJ.toml")


@pytest.mark.parametrize(
    ("mach", "theta_deg", "weak_beta_deg", "strong_beta_deg"),
    [(2.0, 10.0, 39.31, 83.70), (3.0, 20.0, 37.76, 82.15)],
)
def test_oblique_shock_angles_match_naca_1135(
    mach: float, theta_deg: float, weak_beta_deg: float, strong_beta_deg: float
) -> None:
    """Weak and strong shock angles for a given deflection (NACA 1135, Chart 2)."""
    weak = oblique_shock_beta_rad(mach, math.radians(theta_deg))
    strong = oblique_shock_beta_rad(mach, math.radians(theta_deg), weak=False)
    assert weak is not None and strong is not None
    assert math.degrees(weak) == pytest.approx(weak_beta_deg, abs=0.02)
    assert math.degrees(strong) == pytest.approx(strong_beta_deg, abs=0.05)


@pytest.mark.parametrize(("mach", "theta_max_deg", "beta_deg"), [(2.0, 22.97, 64.67), (3.0, 34.07, 65.24)])
def test_maximum_deflection_matches_naca_1135(mach: float, theta_max_deg: float, beta_deg: float) -> None:
    """Detachment deflection and its shock angle (NACA 1135, Chart 2)."""
    beta, theta = theta_max_rad(mach)
    assert math.degrees(theta) == pytest.approx(theta_max_deg, abs=0.02)
    assert math.degrees(beta) == pytest.approx(beta_deg, abs=0.05)
    assert oblique_shock_beta_rad(mach, theta + 1e-3) is None


@pytest.mark.parametrize(("mach", "mach2", "pt_ratio"), [(2.0, 0.5774, 0.7209), (3.0, 0.4752, 0.3283)])
def test_normal_shock_matches_naca_1135(mach: float, mach2: float, pt_ratio: float) -> None:
    """Downstream Mach and total-pressure ratio (NACA 1135, Table II)."""
    result = normal_shock(mach, 1.4)
    assert result[0] == pytest.approx(mach2, abs=1e-4)
    assert result[1] == pytest.approx(pt_ratio, abs=1e-4)


def test_single_ramp_chain_by_hand() -> None:
    """Mach 2, one 10 deg ramp: oblique shock with M1n = 2 sin(39.31 deg), then normal shock."""
    chain = shock_chain(2.0, (10.0,), 0.95)
    m1n = 2.0 * math.sin(math.radians(39.3139))  # = 1.2671
    assert chain.shock_angles[0] == pytest.approx(39.3139, abs=1e-3)
    assert chain.pt_oblique[0] == pytest.approx(normal_shock(m1n, 1.4)[1], rel=1e-4)  # = 0.9846
    assert chain.mach_before_normal == pytest.approx(1.6405, abs=1e-3)  # NACA 1135 Chart 2
    expected = chain.pt_oblique[0] * normal_shock(chain.mach_before_normal, 1.4)[1] * 0.95
    assert chain.recovery == pytest.approx(expected, rel=1e-12)
    assert not chain.detached


def test_chain_without_ramps_is_a_normal_shock() -> None:
    """Zero ramps: the whole compression is one normal shock."""
    assert shock_chain(2.0, (), 1.0).recovery == pytest.approx(0.7209, abs=1e-4)


def test_detached_ramp_ends_the_oblique_compression() -> None:
    """A 25 deg ramp at Mach 2 is beyond 22.97 deg; the normal shock stands at Mach 2."""
    chain = shock_chain(2.0, (25.0, 5.0), 1.0)
    assert chain.detached
    assert chain.deflections == ()
    assert chain.recovery == pytest.approx(0.7209, abs=1e-4)


def test_equal_normal_mach_schedule() -> None:
    """Every oblique shock of the schedule has the chosen normal Mach number."""
    deflections = equal_normal_mach_deflections(2.5, 3, 1.3)
    assert deflections is not None
    chain = shock_chain(2.5, deflections, 1.0)
    for mach, beta in zip(chain.mach_stages[:-1], chain.shock_angles, strict=True):
        assert mach * math.sin(math.radians(beta)) == pytest.approx(1.3, rel=1e-6)
    assert equal_normal_mach_deflections(1.5, 3, 1.6) is None


def test_oswatitsch_optimum_reproduces_the_old_four_shock_preset() -> None:
    """At Mach 2.5 the optimum matches the presets the old module found by Nelder-Mead."""
    chain = oswatitsch_chain(2.5, 4, 0.92)
    assert chain.deflections == pytest.approx((7.61, 8.45, 9.32, 9.64), abs=0.01)
    assert chain.recovery == pytest.approx(0.8741, abs=1e-4)


def test_more_shocks_recover_more() -> None:
    """The optimum recovery rises with the number of oblique shocks."""
    recoveries = [r for _, r in recovery_by_shock_count(2.5, 1.0, 5)]
    assert all(b > a for a, b in itertools.pairwise(recoveries))


def _run(**settings: object) -> MultiShockInletResults:
    analysis = MultiShockInletAnalysis()
    analysis.setup(BaseVehicleConfig.from_toml(ALVRJ_PATH), enable_logging=False, **settings)
    return analysis.execute()


def test_analysis_optimum_on_alvrj() -> None:
    """ALVRJ at its design Mach 2.6 with four optimum ramps meets MIL-E-5007D."""
    results = _run(n_oblique_shocks=4)
    assert results.fidelity == FidelityLevel.LEVEL_0
    assert results.mach == 2.6
    assert results.optimized
    assert len(results.chain.deflections) == 4
    assert results.recovery_margin > 0.0
    assert results.total_turning == pytest.approx(sum(results.chain.deflections))
    assert any("placeholder" in a for a in results.assumptions)


def test_analysis_with_given_ramps() -> None:
    """Given ramps replace the optimum; a weak schedule is flagged below the reference."""
    results = _run(deflections_deg=(8.0, 9.0, 10.0), pi_diffuser=0.97)
    assert not results.optimized
    assert results.chain.deflections == (8.0, 9.0, 10.0)
    assert any("below the MIL-E-5007D" in a for a in results.assumptions)


def test_analysis_errors() -> None:
    """Subsonic Mach, too many shocks, a bad ramp or an unknown setting fail."""
    with pytest.raises(ValueError, match="supersonic"):
        _run(mach=0.9)
    with pytest.raises(ValueError, match="n_oblique_shocks"):
        _run(n_oblique_shocks=20)
    with pytest.raises(ValueError, match="deflection"):
        _run(deflections_deg=(50.0,))
    with pytest.raises(TypeError, match="Unknown settings"):
        _run(n_cones=4)


def test_design_curves_csv_and_figure() -> None:
    """Both design curves are written and plotted."""
    results = _run(n_oblique_shocks=3)
    by_count = recovery_by_shock_count(results.mach, 0.97, 4)
    by_mach = recovery_vs_mach(results)
    assert [n for n, _ in by_count] == [0, 1, 2, 3, 4]
    assert by_mach[0][0] == pytest.approx(1.2)
    text = format_design_csv(by_count, by_mach)
    assert text.startswith("n_oblique_shocks,optimum_recovery")
    assert "mach,recovery_fixed_ramps,mil_e_5007d_recovery" in text
    assert len(plot_design_curves(by_count, by_mach, results).axes) == 2
