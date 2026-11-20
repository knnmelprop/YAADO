"""Shared fixtures for the flight dynamics tests: a generic solid rocket and a full flight."""

from __future__ import annotations

import pytest

from YAADO_Core.ComponentStore import MassProperties
from YAADO_Core.ComponentStore.aero_surfaces import Fins
from YAADO_Core.ComponentStore.body import AxisymmetricBody
from YAADO_Core.ComponentStore.propulsion import SolidMotor
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.flight_dynamics.containers import PointMassBoostResults
from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
    PointMass3DOFBoostAnalysis,
)


def build_generic_rocket() -> BaseVehicleConfig:
    """Build a minimal, schema-valid sounding rocket (20 kg at launch, 8 kg propellant)."""
    motor = SolidMotor(
        isp_sl=180.0,
        isp_vacuum=210.0,
        propellant_mass=8.0,
        burn_time=4.0,
        thrust_mean=180.0 * (8.0 / 4.0) * 9.80665,
        thrust_peak=180.0 * (8.0 / 4.0) * 9.80665 * 1.2,
        propellant_density=1750.0,
    )
    body = AxisymmetricBody(
        length=2.0,
        diameter=0.15,
        nose_length=0.4,
        nose_diameter=0.15,
        total_length=2.0,
    )
    fins = Fins(count=4, span=0.08, sweep=30.0, chord_root=0.15, chord_tip=0.05)
    return BaseVehicleConfig(
        name="generic_test_sounding_rocket",
        propulsion={"stage_1": motor},
        bodies={"body": body},
        aero_surfaces={"fins": fins},
        mass_properties=MassProperties(cg_from_nose=1.2, total_mass=20.0),
    )


@pytest.fixture(scope="module")
def generic_rocket() -> BaseVehicleConfig:
    """The generic rocket (module-scoped, treated as read-only)."""
    return build_generic_rocket()


@pytest.fixture(scope="module")
def full_flight(generic_rocket: BaseVehicleConfig) -> PointMassBoostResults:
    """A full 3-DOF flight of the generic rocket from launch to ground impact."""
    analysis = PointMass3DOFBoostAnalysis()
    analysis.setup(generic_rocket, stop_at_burnout=False, enable_logging=False)
    return analysis.execute()
