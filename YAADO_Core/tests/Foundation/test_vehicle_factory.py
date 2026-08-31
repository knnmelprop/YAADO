"""Tests for :mod:`YAADO_Core.Foundation.vehicle_factory`.

SUAVE is not installed in this environment, so these tests inject a
lightweight fake SUAVE module that mimics the small surface area the
factory relies on (``Vehicle``, ``Components.Energy.Networks.*``,
``Components.Wings.Wing`` and ``append_component``).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from YAADO_Core.ComponentStore import Wings, TurbojetEngine
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.Foundation.vehicle_factory import VehicleFactory


class _FakeSweeps:
    def __init__(self) -> None:
        self.quarter_chord: float | None = None
        self.leading_edge: float | None = None


class _FakeSpans:
    def __init__(self) -> None:
        self.projected: float | None = None


class _FakeWing:
    """Stand-in for ``SUAVE.Components.Wings.Wing``."""

    def __init__(self) -> None:
        self.tag: str | None = None
        self.sweeps = _FakeSweeps()
        self.spans = _FakeSpans()
        self.aspect_ratio: float | None = None
        self.taper: float | None = None
        self.dihedral: float | None = None
        self.vertical: bool = False


class _FakeNetwork:
    """Generic stand-in for a SUAVE energy network."""

    def __init__(self) -> None:
        self.tag: str | None = None


class _FakeVehicle:
    """Stand-in for ``SUAVE.Vehicle``."""

    def __init__(self) -> None:
        self.tag: str | None = None
        self.components: list[Any] = []

    def append_component(self, component: Any) -> None:
        self.components.append(component)


def make_fake_suave() -> SimpleNamespace:
    """Build a fake SUAVE module exposing the factory's required surface."""
    networks = SimpleNamespace(
        Ramjet=_FakeNetwork,
        Turbojet_Super=_FakeNetwork,
    )
    components = SimpleNamespace(
        Energy=SimpleNamespace(Networks=networks),
        Wings=SimpleNamespace(Wing=_FakeWing),
    )
    return SimpleNamespace(Vehicle=_FakeVehicle, Components=components)


def make_generic_vehicle_config() -> BaseVehicleConfig:
    """Build a minimal, generically valid vehicle config with one wing and one engine."""
    wing = Wings(
        aspect_ratio=8.0,
        sweep_deg=5.0,
        taper_ratio=0.5,
        span_m=10.0,
        dihedral_deg=3.0,
        airfoil_root="NACA2412",
    )
    engine = TurbojetEngine(
        name="generic-turbojet",
        thrust_N=5000.0,
        sfc_kg_per_Ns=2.0e-5,
        mach_range=(0.0, 0.9),
    )
    return BaseVehicleConfig(
        name="generic-test-vehicle",
        propulsion={"main_engine": engine},
        aero_surfaces={"main_wing": wing},
    )


def test_build_appends_wing_and_propulsion_with_injected_suave() -> None:
    """build() should translate and append both a wing and an engine network."""
    fake_suave = make_fake_suave()
    factory = VehicleFactory(suave_module=fake_suave)
    config = make_generic_vehicle_config()

    result = factory.build(config)

    assert isinstance(result, _FakeVehicle)
    assert result.tag == "generic-test-vehicle"
    assert len(result.components) == 2

    wings = [c for c in result.components if isinstance(c, _FakeWing)]
    networks = [c for c in result.components if isinstance(c, _FakeNetwork)]
    assert len(wings) == 1
    assert len(networks) == 1

    wing = wings[0]
    assert wing.aspect_ratio == pytest.approx(8.0)
    assert wing.spans.projected == pytest.approx(10.0)
    assert wing.sweeps.quarter_chord == pytest.approx(5.0)

    network = networks[0]
    assert network.tag == "generic-turbojet"


def test_build_without_suave_raises_runtime_error() -> None:
    """build() must raise a clear RuntimeError when SUAVE is unavailable."""
    factory = VehicleFactory(suave_module=None)
    factory.suave = None  # explicitly simulate "SUAVE not importable"
    config = make_generic_vehicle_config()

    with pytest.raises(RuntimeError, match="SUAVE is not importable"):
        factory.build(config)


def test_build_with_real_suave_produces_real_vehicle() -> None:
    """Integration test: build() against the real SUAVE package (skipped if not installed).

    This exercises VehicleFactory() with no injected stand-in, so it only
    runs once SUAVE 2.5.2 is actually installed in the environment (e.g.
    `pip install -e external/suave/trunk`); until then it is skipped, not
    failed.
    """
    suave = pytest.importorskip("SUAVE")

    factory = VehicleFactory()
    config = make_generic_vehicle_config()

    result = factory.build(config)

    assert result.tag == "generic-test-vehicle"

    # SUAVE's Vehicle sorts appended components into typed containers
    # (see SUAVE.Vehicle.Vehicle._component_root_map): networks land in
    # `.networks`, wings land in `.wings`.
    networks = list(result.networks.values())
    assert any(isinstance(n, suave.Components.Energy.Networks.Turbojet_Super) for n in networks)

    wings = list(result.wings.values())
    assert any(isinstance(w, suave.Components.Wings.Wing) for w in wings)
