"""Unit tests for YAADO_Core.modules.powerplant.cycle_methods.heiser_pratt."""

import dataclasses
import json
import math
from pathlib import Path

import pytest

from YAADO_Core.ComponentStore import AxisymmetricBody, RamjetEngine
from YAADO_Core.Foundation.analysis_base import FidelityLevel
from YAADO_Core.Foundation.constants import GAMMA_AIR, LHV_KEROSENE
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.powerplant.containers import (
    HeiserPrattInputs,
    HeiserPrattResults,
)
from YAADO_Core.modules.powerplant.cycle_methods.heiser_pratt import (
    HeiserPrattCycleAnalysis,
    area_ratio_from_mach,
    choked_mass_flux,
    evaluate_cycle,
    supersonic_mach_from_area_ratio,
)

HANGAR_EXAMPLES = Path(__file__).resolve().parents[4] / "Hangar" / "examples"


def _inputs(**overrides: float | None) -> HeiserPrattInputs:
    """Build valid cycle inputs with typical ramjet values."""
    values: dict[str, float | None] = {
        "mach": 2.5,
        "altitude": 10000.0,
        "tt4": 2000.0,
        "nozzle_area_ratio": 2.0,
        "eta_inlet": 0.9,
        "pi_cc": 0.9,
        "pi_nozzle": 0.97,
        "eta_b": 0.95,
        "gamma_hot": 1.28,
        "gamma_cold": GAMMA_AIR,
        "fuel_lhv": LHV_KEROSENE,
        "mdot_air": 10.0,
    }
    values.update(overrides)
    return HeiserPrattInputs(**values)  # type: ignore[arg-type]


@pytest.fixture()
def alvrj() -> BaseVehicleConfig:
    """The ALVRJ example vehicle, the only example with a ramjet."""
    return BaseVehicleConfig.from_toml(HANGAR_EXAMPLES / "ALVRJ" / "ALVRJ.toml")


# ---------------------------------------------------------------------------
# Gas-dynamic helpers
# ---------------------------------------------------------------------------


def test_area_ratio_matches_isentropic_table() -> None:
    """A/A* at Mach 2, gamma 1.4, is the tabulated 1.6875."""
    assert area_ratio_from_mach(2.0, 1.4) == pytest.approx(1.6875, abs=1e-4)


def test_supersonic_mach_inverts_area_ratio() -> None:
    """The root search returns the supersonic branch of the area-Mach relation."""
    assert supersonic_mach_from_area_ratio(1.6875, 1.4) == pytest.approx(2.0, abs=1e-3)
    assert supersonic_mach_from_area_ratio(1.0, 1.4) == 1.0


def test_supersonic_mach_rejects_area_ratio_below_one() -> None:
    """No supersonic solution exists below A/A* = 1."""
    with pytest.raises(ValueError, match="no supersonic solution"):
        supersonic_mach_from_area_ratio(0.9, 1.4)


def test_choked_mass_flux_matches_textbook_constant() -> None:
    """For air, mdot*sqrt(Tt)/(A*pt) = 0.0404 in SI units."""
    flux = choked_mass_flux(101325.0, 288.15, 1.4, 287.05287)
    assert flux * math.sqrt(288.15) / 101325.0 == pytest.approx(0.04042, rel=1e-3)


# ---------------------------------------------------------------------------
# Cycle hand checks
# ---------------------------------------------------------------------------


def test_ideal_ramjet_matches_closed_form_hand_calculation() -> None:
    """One gas, no losses, perfectly expanded: the classic ideal ramjet.

    Hand values at sea level, Mach 2, Tt4 = 2000 K, mdot_air = 1 kg/s:
    V0 = 2 * 340.294 = 680.59 m/s, Tt0 = 288.15 * 1.8 = 518.67 K,
    f = 1004.685 * (2000 - 518.67) / (43e6 - 1004.685 * 2000) = 0.036308,
    Ve = V0 * sqrt(Tt4 / Tt0) = 1336.4 m/s, F = 1.036308 * Ve - V0 = 704.4 N.
    """
    results = evaluate_cycle(
        _inputs(
            mach=2.0,
            altitude=0.0,
            tt4=2000.0,
            nozzle_area_ratio=area_ratio_from_mach(2.0, GAMMA_AIR),
            eta_inlet=1.0,
            pi_cc=1.0,
            pi_nozzle=1.0,
            eta_b=1.0,
            gamma_hot=GAMMA_AIR,
            mdot_air=1.0,
        )
    )

    assert results.v0 == pytest.approx(680.59, rel=1e-3)
    assert results.tt0 == pytest.approx(518.67, rel=1e-3)
    assert results.fuel_air_ratio == pytest.approx(0.036308, rel=1e-3)
    assert results.mach_exit == pytest.approx(2.0, abs=1e-6)
    assert results.v_exit == pytest.approx(1336.4, rel=1e-3)
    assert results.p_exit_over_p0 == pytest.approx(1.0, rel=1e-6)
    assert results.pressure_thrust == pytest.approx(0.0, abs=1e-2)
    assert results.thrust_real == pytest.approx(704.4, rel=1e-3)
    assert results.thrust_ideal == pytest.approx(results.thrust_real, rel=1e-9)
    assert results.thrust_cc_loss == pytest.approx(results.thrust_real, rel=1e-9)


def test_total_pressure_chain() -> None:
    """Stations 2 and 4 apply the recovery and the combustor loss in sequence."""
    results = evaluate_cycle(_inputs())

    assert results.pt2 == pytest.approx(0.9 * results.pt0)
    assert results.pt4 == pytest.approx(0.9 * results.pt2)


def test_loss_models_differ_by_their_closed_form_terms() -> None:
    """The same mass flow and exit velocity leave only pressure terms between models.

    The nozzle loss scales the exit pressure at fixed area. The combustor loss
    scales total pressure and inversely the throat area, so p_exit * A_exit is
    unchanged and only the ambient term ``p0 * A_exit`` differs.
    """
    inputs = _inputs()
    results = evaluate_cycle(inputs)

    p_exit_no_nozzle_loss = results.p_exit / inputs.pi_nozzle
    nozzle_loss_term = (1.0 - inputs.pi_nozzle) * p_exit_no_nozzle_loss * results.a_exit
    assert results.thrust_cc_loss - results.thrust_real == pytest.approx(nozzle_loss_term)

    a_exit_ideal = results.a_exit * inputs.pi_cc
    ambient_term = results.p0 * (results.a_exit - a_exit_ideal)
    assert results.thrust_ideal - results.thrust_cc_loss == pytest.approx(ambient_term)


def test_throat_area_sets_the_mass_flow() -> None:
    """A throat area gives the flow that an explicit mdot_air reproduces."""
    from_throat = evaluate_cycle(_inputs(mdot_air=None, throat_area=0.05))
    assert from_throat.a_throat == pytest.approx(0.05)

    from_flow = evaluate_cycle(_inputs(mdot_air=from_throat.mdot_air))
    assert from_flow.a_throat == pytest.approx(0.05)
    assert from_flow.thrust_real == pytest.approx(from_throat.thrust_real)


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"mach": 1.0}, "mach"),
        ({"nozzle_area_ratio": 0.9}, "nozzle_area_ratio"),
        ({"eta_inlet": 0.0}, "eta_inlet"),
        ({"pi_cc": 1.1}, "pi_cc"),
        ({"pi_nozzle": -0.5}, "pi_nozzle"),
        ({"eta_b": 1.5}, "eta_b"),
        ({"gamma_hot": 1.0}, "gamma_hot"),
        ({"mdot_air": None}, "exactly one"),
        ({"throat_area": 0.05}, "exactly one"),
        ({"mdot_air": -1.0}, "mdot_air"),
    ],
)
def test_inputs_reject_values_outside_the_model(overrides: dict, match: str) -> None:
    """Out-of-range inputs fail at construction."""
    with pytest.raises(ValueError, match=match):
        _inputs(**overrides)


def test_cycle_rejects_tt4_below_recovered_temperature() -> None:
    """No heat can be added if the combustor exit is colder than the inlet."""
    with pytest.raises(ValueError, match="must exceed"):
        evaluate_cycle(_inputs(tt4=400.0))


def test_cycle_rejects_unreachable_tt4() -> None:
    """The burner energy balance has no solution for a too-weak fuel."""
    with pytest.raises(ValueError, match="not reachable"):
        evaluate_cycle(_inputs(fuel_lhv=1.0e6))


# ---------------------------------------------------------------------------
# Analysis on real vehicle configurations
# ---------------------------------------------------------------------------


def test_analysis_runs_on_alvrj_toml(alvrj: BaseVehicleConfig) -> None:
    """Mach, Tt4 and the nozzle come from the TOML and reproduce its geometry."""
    engine = alvrj.find_single_component(RamjetEngine)
    analysis = HeiserPrattCycleAnalysis()
    analysis.setup(alvrj, enable_logging=False)
    results = analysis.execute()

    assert isinstance(results, HeiserPrattResults)
    assert results.fidelity is FidelityLevel.LEVEL_2
    assert results.inputs.mach == engine.design_mach
    assert results.inputs.tt4 == engine.combustor_temp
    assert results.inputs.nozzle_area_ratio == engine.nozzle_area_ratio

    assert engine.nozzle_throat_diameter is not None
    assert engine.nozzle_exit_diameter is not None
    assert results.a_throat == pytest.approx(math.pi / 4.0 * engine.nozzle_throat_diameter**2)
    assert results.a_exit == pytest.approx(math.pi / 4.0 * engine.nozzle_exit_diameter**2)

    # Hand value: cp_hot = 1312.0, cp_cold = 1004.7, Tt0 = 524.8 K,
    # f = (1312.0 * 2150 - 1004.7 * 524.8) / (0.95 * 43e6 - 1312.0 * 2150) = 0.0603.
    assert results.fuel_air_ratio == pytest.approx(0.0603, abs=2e-4)
    assert results.thrust_real == pytest.approx(14450.0, rel=0.01)
    assert results.underexpanded
    assert results.thrust_real < results.thrust_cc_loss < results.thrust_ideal

    # The required capture stream must fit inside the body's frontal area.
    body = alvrj.find_single_component(AxisymmetricBody)
    assert 0.0 < results.capture_area < math.pi / 4.0 * body.diameter**2


@pytest.mark.parametrize("example", ["AGM-84_HARPOON"])
def test_analysis_rejects_vehicle_without_ramjet(example: str) -> None:
    """A turbojet vehicle gets a clear error, not a fabricated ramjet result."""
    vehicle = BaseVehicleConfig.from_toml(HANGAR_EXAMPLES / example / f"{example}.toml")
    with pytest.raises(ValueError, match="no component matching"):
        HeiserPrattCycleAnalysis().setup(vehicle, enable_logging=False)


def test_settings_override_vehicle_values(alvrj: BaseVehicleConfig) -> None:
    """Keyword settings replace the design-point values from the vehicle."""
    analysis = HeiserPrattCycleAnalysis()
    analysis.setup(alvrj, enable_logging=False, mach=3.0, tt4=1900.0, altitude_m=15000.0, mdot_air=12.0)
    results = analysis.execute()

    assert results.inputs.mach == 3.0
    assert results.inputs.tt4 == 1900.0
    assert results.mdot_air == 12.0
    assert results.t0 == pytest.approx(216.65, abs=0.1)  # stratosphere, above the old model's limit


def test_unknown_setting_is_rejected(alvrj: BaseVehicleConfig) -> None:
    """A mistyped setting must not silently fall back to a default."""
    with pytest.raises(TypeError, match="eta_inlett"):
        HeiserPrattCycleAnalysis().setup(alvrj, enable_logging=False, eta_inlett=0.8)


def test_mass_flow_is_required_without_throat(generic_ramjet_vehicle: BaseVehicleConfig) -> None:
    """Without a throat diameter the flow must be passed explicitly."""
    analysis = HeiserPrattCycleAnalysis()
    with pytest.raises(ValueError, match="nozzle_throat_diameter"):
        analysis.setup(generic_ramjet_vehicle, enable_logging=False)

    analysis.setup(generic_ramjet_vehicle, enable_logging=False, mdot_air=15.0)
    assert analysis.execute().mdot_air == 15.0


def test_multiple_ramjets_need_an_engine_name() -> None:
    """Two ramjets are ambiguous until one is named."""
    small = RamjetEngine(design_mach=2.0, combustor_temp=1800.0, nozzle_area_ratio=1.5)
    large = RamjetEngine(design_mach=3.0, combustor_temp=2100.0, nozzle_area_ratio=3.0)
    vehicle = BaseVehicleConfig(name="twin", propulsion={"small": small, "large": large})

    analysis = HeiserPrattCycleAnalysis()
    with pytest.raises(ValueError, match="multiple components"):
        analysis.setup(vehicle, enable_logging=False, mdot_air=10.0)

    analysis.setup(vehicle, enable_logging=False, mdot_air=10.0, engine_name="large")
    assert analysis.execute().inputs.mach == 3.0


def test_other_fuels_need_explicit_properties() -> None:
    """Kerosene defaults must not be applied silently to another fuel."""
    engine = RamjetEngine(
        design_mach=2.5, fuel_type="JP-10", combustor_temp=2000.0, nozzle_area_ratio=2.0
    )
    vehicle = BaseVehicleConfig(name="jp10", propulsion={"ramjet": engine})

    analysis = HeiserPrattCycleAnalysis()
    with pytest.raises(ValueError, match="JP-10"):
        analysis.setup(vehicle, enable_logging=False, mdot_air=10.0)

    analysis.setup(vehicle, enable_logging=False, mdot_air=10.0, gamma_hot=1.27, fuel_lhv=42.1e6)
    assert analysis.execute().inputs.fuel_lhv == 42.1e6


# ---------------------------------------------------------------------------
# BaseAnalysis contract
# ---------------------------------------------------------------------------


def test_execute_before_setup_raises() -> None:
    """The lifecycle is enforced by BaseAnalysis."""
    with pytest.raises(RuntimeError, match="before setup"):
        HeiserPrattCycleAnalysis().execute()


def test_results_are_frozen_and_expose_si_units(alvrj: BaseVehicleConfig) -> None:
    """Scalars and units reflect from the typed fields."""
    analysis = HeiserPrattCycleAnalysis()
    analysis.setup(alvrj, enable_logging=False)
    results = analysis.execute()

    with pytest.raises(dataclasses.FrozenInstanceError):
        results.thrust_real = 0.0  # type: ignore[misc]

    assert "inputs" not in results.scalars()
    assert "underexpanded" not in results.scalars()
    units = results.units()
    assert units["thrust_real"] == "N"
    assert units["mdot_air"] == "kg/s"
    assert units["a_exit"] == "m^2"
    assert units["fuel_air_ratio"] == "-"
    assert set(results.headline_metrics()) <= set(results.scalars())


@pytest.mark.parametrize(
    "broken",
    [
        {"fuel_air_ratio": -0.01},
        {"mach_exit": 0.9},
        {"thrust_real": math.nan},
        {"thrust_real": 1.0e9},
        {"thrust_ideal": 0.0},
    ],
)
def test_validate_results_flags_unphysical_output(alvrj: BaseVehicleConfig, broken: dict) -> None:
    """Non-physical values fail the checks; good results pass."""
    analysis = HeiserPrattCycleAnalysis()
    analysis.setup(alvrj, enable_logging=False)
    results = analysis.execute()

    assert analysis.validate_results(results)
    assert not analysis.validate_results(dataclasses.replace(results, **broken))


def test_logger_writes_results_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, alvrj: BaseVehicleConfig
) -> None:
    """Results, including the nested inputs, serialize through FlightLogger."""
    monkeypatch.chdir(tmp_path)
    analysis = HeiserPrattCycleAnalysis()
    analysis.setup(alvrj, enable_logging=True)
    results = analysis.execute()

    path = analysis.logger.save_results(results)
    analysis.logger.close()

    assert path is not None
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert "Thrust ideal/cc-loss/real" in analysis.logger.log_file_path.read_text(encoding="utf-8")
    assert saved["data"]["thrust_real"] == pytest.approx(results.thrust_real)
    assert saved["units"]["thrust_real"] == "N"
    assert saved["details"]["inputs"]["mach"] == results.inputs.mach


def test_disabled_logger_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, alvrj: BaseVehicleConfig
) -> None:
    """Diskless runs create no files."""
    monkeypatch.chdir(tmp_path)
    analysis = HeiserPrattCycleAnalysis()
    analysis.setup(alvrj, enable_logging=False)
    analysis.execute()

    assert list(tmp_path.iterdir()) == []
