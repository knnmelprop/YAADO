# MELprop-IADE | tests.unit.test_aero_xfoil_fallback | v0.1.0
"""Unit tests for analyses.aero.xfoil_runner (Ackeret supersonic fallback)."""

import math
import warnings
from pathlib import Path

import pytest

from IADE_Core.modules.aero.xfoil_runner import (
    MAX_MACH,
    MIN_MACH,
    XFOILAnalysis,
    XfoilCase,
    ackeret_polar,
    main as xfoil_main,
)
from IADE_Core.FlightDeck.component_base import FidelityLevel


def test_ackeret_cl_matches_hand_calculation() -> None:
    """CL at Ma 2.5, alpha 5 deg matches the hand-computed Ackeret value.

    CL = 4 * alpha_rad / sqrt(Ma^2 - 1)
       = 4 * 0.0872665 / sqrt(5.25) ~= 0.15234
    """
    cl, _ = ackeret_polar(mach=2.5, alpha_deg=5.0, t_c=0.06)
    alpha_rad = math.radians(5.0)
    expected = 4.0 * alpha_rad / math.sqrt(2.5**2 - 1.0)
    assert cl == pytest.approx(expected, rel=1e-9)
    assert cl == pytest.approx(0.15234, rel=1e-3)


def test_ackeret_cd_includes_thickness_and_alpha_terms() -> None:
    """CD combines wave drag due to lift (alpha^2) and thickness (tau^2)."""
    mach, alpha_deg, t_c = 2.5, 5.0, 0.1697
    _, cd = ackeret_polar(mach, alpha_deg, t_c)

    alpha_rad = math.radians(alpha_deg)
    tau_rad = math.atan(t_c)
    beta = math.sqrt(mach**2 - 1.0)
    expected_cd = 4.0 * (alpha_rad**2 + tau_rad**2) / beta

    assert cd == pytest.approx(expected_cd, rel=1e-9)
    assert cd > 0.0


def test_ackeret_rejects_subsonic_mach() -> None:
    """Ackeret theory is undefined at/below Mach 1."""
    with pytest.raises(ValueError, match="Mach"):
        ackeret_polar(mach=1.0, alpha_deg=2.0, t_c=0.06)
    with pytest.raises(ValueError, match="Mach"):
        ackeret_polar(mach=0.8, alpha_deg=2.0, t_c=0.06)


def test_setup_rejects_out_of_envelope_mach_and_alpha() -> None:
    """setup() must reject Mach <= 1.05 and Mach/alpha outside the fin envelope."""
    analysis = XFOILAnalysis()

    with pytest.raises(ValueError, match="Mach"):
        analysis.setup(XfoilCase(mach_list=[1.0], alpha_deg_list=[0.0]))

    with pytest.raises(ValueError, match="Mach"):
        analysis.setup(XfoilCase(mach_list=[4.0], alpha_deg_list=[0.0]))

    with pytest.raises(ValueError, match="alpha"):
        analysis.setup(XfoilCase(mach_list=[2.5], alpha_deg_list=[15.0]))

    # Boundary values should be accepted.
    analysis.setup(XfoilCase(mach_list=[MIN_MACH, MAX_MACH], alpha_deg_list=[-10.0, 10.0]))


def test_execute_before_setup_raises() -> None:
    """execute() without setup() must raise RuntimeError."""
    with pytest.raises(RuntimeError):
        XFOILAnalysis().execute()


def test_execute_falls_back_to_ackeret_and_warns() -> None:
    """No xfoil binary in this sandbox -> Ackeret fallback fires with a warning."""
    analysis = XFOILAnalysis()
    analysis.setup(XfoilCase(mach_list=[2.5], alpha_deg_list=[5.0]))

    with pytest.warns(UserWarning, match="Ackeret"):
        results = analysis.execute()

    assert results.metadata["method"] == "ackeret_linearized_supersonic"
    assert results.fidelity == FidelityLevel.LEVEL_1
    assert analysis.validate_results(results)


def test_execute_output_structure_is_json_safe_nested_dict() -> None:
    """Results.data nests as {mach_str: {alpha_str: {CL, CD, CL_over_CD}}}."""
    analysis = XFOILAnalysis()
    case = XfoilCase(mach_list=[2.0, 3.0], alpha_deg_list=[-5.0, 0.0, 5.0])
    analysis.setup(case)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = analysis.execute()

    assert set(results.data.keys()) == {"2", "3"}
    for mach_key in results.data:
        assert set(results.data[mach_key].keys()) == {"-5", "0", "5"}
        for alpha_key, coeffs in results.data[mach_key].items():
            assert isinstance(alpha_key, str)
            assert set(coeffs.keys()) == {"CL", "CD", "CL_over_CD"}
            assert isinstance(coeffs["CL"], float)
            assert isinstance(coeffs["CD"], float)

    # alpha = 0 must give CL == 0 (symmetric double-wedge, no camber).
    assert results.data["2"]["0"]["CL"] == pytest.approx(0.0, abs=1e-12)


def test_main_writes_json_and_png(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """main() writes a results JSON and a polar-grid PNG next to the module."""
    import IADE_Core.modules.aero.xfoil_runner as xfoil_runner_module

    json_path = tmp_path / "xfoil_runner_results.json"
    png_path = tmp_path / "xfoil_runner_polar.png"
    monkeypatch.setattr(xfoil_runner_module, "_RESULTS_JSON_PATH", json_path)
    monkeypatch.setattr(xfoil_runner_module, "_POLAR_PNG_PATH", png_path)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        output = xfoil_main()

    assert json_path.exists()
    assert png_path.exists()
    assert png_path.stat().st_size > 0
    assert "data" in output and "metadata" in output
