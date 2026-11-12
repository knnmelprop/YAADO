"""Tests for the Ackeret polar functions and the typed XFOILAnalysis."""

import dataclasses
import warnings
from pathlib import Path

import pytest

from YAADO_Core.ComponentStore.aero_surfaces import Fins, Wings
from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.solver_registry import (
    DEFAULT_REGISTRY,
    SolverInfo,
    SolverRegistry,
)
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig, ComponentNotFoundError
from YAADO_Core.modules.wind_tunnel.containers import PolarCurve, XfoilPolarResults
from YAADO_Core.modules.wind_tunnel.methods.xfoil import xfoil_runner
from YAADO_Core.modules.wind_tunnel.methods.xfoil.xfoil_runner import (
    XFOILAnalysis,
    ackeret_polar,
    naca_4_digit_thickness,
)


@pytest.mark.parametrize(
    ("mach", "alpha_deg", "t_c", "expected_cl", "expected_cd"),
    [
        # Reference values independently evaluated from Anderson's Ackeret formulas.
        (2.0, 5.0, 0.1, 0.20153326269269087, 0.040528316392067186),
        # At zero incidence, lift is zero but thickness wave drag remains.
        (3.0, 0.0, 0.1, 0.0, 0.014048571663723437),
        # Negative incidence reverses lift while drag remains positive.
        (2.5, -4.0, 0.06, -0.1218758614839569, 0.01477817377181453),
    ],
)
def test_ackeret_polar_matches_hand_checked_reference_values(
    mach: float,
    alpha_deg: float,
    t_c: float,
    expected_cl: float,
    expected_cd: float,
) -> None:
    """Compare lift and drag with independently calculated textbook values."""
    cl, cd = ackeret_polar(mach, alpha_deg, t_c)

    assert cl == pytest.approx(expected_cl, rel=1e-9, abs=1e-12)
    assert cd == pytest.approx(expected_cd, rel=1e-9, abs=1e-12)


@pytest.mark.parametrize("mach", [0.8, 1.0])
def test_ackeret_polar_rejects_mach_at_or_below_unity(mach: float) -> None:
    """Ackeret theory must reject subsonic flow and the Mach 1 singularity."""
    with pytest.raises(ValueError, match="Mach > 1"):
        ackeret_polar(mach, alpha_deg=5.0, t_c=0.1)


REPO_ROOT = Path(__file__).resolve().parents[4]


def _vehicle() -> BaseVehicleConfig:
    fins = Fins(count=4, span=0.08, sweep=30.0, chord_root=0.15, chord_tip=0.05)
    wing = Wings(
        aspect_ratio=2.0, sweep=30.0, taper_ratio=0.5, span=0.5, airfoil_root="NACA0008"
    )
    return BaseVehicleConfig(name="polar_test", aero_surfaces={"fins": fins, "wing": wing})


def _run(vehicle: BaseVehicleConfig, **kwargs: object) -> XfoilPolarResults:
    analysis = XFOILAnalysis()
    analysis.setup(vehicle, enable_logging=False, **kwargs)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return analysis.execute()


def test_analysis_is_typed_level_1_base_analysis() -> None:
    assert issubclass(XFOILAnalysis, BaseAnalysis)
    assert XFOILAnalysis.fidelity == FidelityLevel.LEVEL_1


def test_results_are_frozen_typed_and_resolve_all_aero_components() -> None:
    results = _run(_vehicle(), mach_list=[2.0, 3.0], alpha_deg_list=[0.0, 5.0])

    assert isinstance(results, XfoilPolarResults)
    assert [a.component_name for a in results.airfoils] == ["fins", "wing"]
    assert all(len(a.curves) == 2 for a in results.airfoils)
    with pytest.raises(dataclasses.FrozenInstanceError):
        results.method = "x"  # type: ignore[misc]


def test_polar_values_match_ackeret_hand_check() -> None:
    results = _run(_vehicle(), mach_list=[2.0], alpha_deg_list=[5.0], thickness_to_chord=0.1)

    curve = results.airfoils[0].curves[0]
    assert curve.cl[0] == pytest.approx(0.20153326269269087, rel=1e-9)
    assert curve.cd[0] == pytest.approx(0.040528316392067186, rel=1e-9)
    assert curve.cl_over_cd[0] == pytest.approx(0.20153326269269087 / 0.040528316392067186)


def test_thickness_resolution_order() -> None:
    results = _run(_vehicle())
    by_name = {a.component_name: a for a in results.airfoils}
    assert by_name["wing"].thickness_to_chord == pytest.approx(0.08)  # from NACA0008
    assert by_name["fins"].thickness_to_chord == xfoil_runner.DEFAULT_THICKNESS_TO_CHORD

    overridden = _run(_vehicle(), thickness_to_chord=0.12)
    assert {a.thickness_to_chord for a in overridden.airfoils} == {0.12}


def test_component_names_selects_subset_and_rejects_unknown() -> None:
    results = _run(_vehicle(), component_names=["wing"])
    assert [a.component_name for a in results.airfoils] == ["wing"]

    analysis = XFOILAnalysis()
    with pytest.raises(ComponentNotFoundError):
        analysis.setup(_vehicle(), enable_logging=False, component_names=["nope"])


def test_vehicle_without_aero_surfaces_is_rejected() -> None:
    with pytest.raises(ValueError, match="no aerodynamic surfaces"):
        XFOILAnalysis().setup(BaseVehicleConfig(name="empty"), enable_logging=False)


@pytest.mark.parametrize("mach", [1.0, 1.05, 0.8, 1.2, 4.0])
def test_setup_rejects_mach_outside_envelope(mach: float) -> None:
    with pytest.raises(ValueError, match="Mach"):
        XFOILAnalysis().setup(_vehicle(), enable_logging=False, mach_list=[mach])


def test_setup_rejects_bad_alpha_and_thickness() -> None:
    with pytest.raises(ValueError, match="alpha"):
        XFOILAnalysis().setup(_vehicle(), enable_logging=False, alpha_deg_list=[15.0])
    with pytest.raises(ValueError, match="thickness_to_chord"):
        XFOILAnalysis().setup(_vehicle(), enable_logging=False, thickness_to_chord=0.0)


def test_execute_before_setup_raises() -> None:
    with pytest.raises(RuntimeError, match="before setup"):
        XFOILAnalysis().execute()


def test_missing_xfoil_binary_is_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty registry or a missing executable only flips the availability flag."""
    monkeypatch.setattr(xfoil_runner, "DEFAULT_REGISTRY", SolverRegistry())
    assert _run(_vehicle()).xfoil_binary_available is False

    registry = SolverRegistry()
    registry.register(SolverInfo("xfoil", executable="definitely-not-a-real-xfoil-binary"))
    monkeypatch.setattr(xfoil_runner, "DEFAULT_REGISTRY", registry)
    assert _run(_vehicle()).xfoil_binary_available is False

    registry.register(SolverInfo("xfoil"))  # pure-Python stand-in: always available
    assert _run(_vehicle()).xfoil_binary_available is True
    assert DEFAULT_REGISTRY is not registry


def test_execute_warns_about_ackeret_fallback() -> None:
    analysis = XFOILAnalysis()
    analysis.setup(_vehicle(), enable_logging=False)
    with pytest.warns(UserWarning, match="Ackeret"):
        analysis.execute()


def test_headline_scalars_and_units() -> None:
    results = _run(_vehicle())
    scalars = results.scalars()
    assert set(XfoilPolarResults.headline_metrics()) <= set(scalars)
    assert results.units()["max_lift_to_drag"] == "-"
    assert scalars["min_drag_coefficient"] > 0.0
    assert scalars["max_lift_to_drag"] > 0.0


def test_validate_results_detects_tampering() -> None:
    analysis = XFOILAnalysis()
    analysis.setup(_vehicle(), enable_logging=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = analysis.execute()
    assert analysis.validate_results(results)

    curve = results.airfoils[0].curves[0]
    bad_curve = PolarCurve(curve.mach, curve.alpha, tuple(c + 0.1 for c in curve.cl), curve.cd)
    bad_airfoil = dataclasses.replace(results.airfoils[0], curves=(bad_curve,))
    bad = dataclasses.replace(results, airfoils=(bad_airfoil,))
    assert not analysis.validate_results(bad)


@pytest.mark.parametrize(
    ("designation", "expected"),
    [("NACA0006", 0.06), ("naca 2412", 0.12), ("NACA63-212", None), (None, None)],
)
def test_naca_4_digit_thickness(designation: str | None, expected: float | None) -> None:
    assert naca_4_digit_thickness(designation) == expected


def test_runs_on_real_toml_configuration() -> None:
    vehicle = BaseVehicleConfig.from_toml(
        REPO_ROOT / "Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml"
    )
    results = _run(vehicle)

    names = {a.component_name for a in results.airfoils}
    assert {"mid_body_wings", "aft_control_fins", "planar_equivalent"} <= names
    planar = next(a for a in results.airfoils if a.component_name == "planar_equivalent")
    assert planar.airfoil == "NACA0006"
    assert planar.thickness_to_chord == pytest.approx(0.06)
