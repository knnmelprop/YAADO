"""Shared pytest fixtures for the powerplant module test suite.

Provides a generic, validating :class:`BaseVehicleConfig` carrying a
single :class:`RamjetEngine` propulsion component, used by every
powerplant analysis test to exercise the unified
``setup(vehicle, operating_state)`` contract without hardcoding any
project-specific YAML.
"""

from __future__ import annotations

import pytest

from YAADO_Core.ComponentStore.propulsion import RamjetEngine
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig

#: Default design Mach for the generic ramjet fixture, matching the
#: module-level MACH_DESIGN constants used across the powerplant solvers.
GENERIC_DESIGN_MACH: float = 2.5

#: Default combustor-exit total temperature [K] for the generic ramjet
#: fixture, matching the module-level TT4_DEFAULT_K / COMBUSTOR_EXIT_TEMP_DEFAULT_K.
GENERIC_COMBUSTOR_TEMP_K: float = 2000.0

#: Default nozzle area ratio for the generic ramjet fixture, matching
#: NOZZLE_AREA_RATIO_DESIGN.
GENERIC_NOZZLE_AREA_RATIO: float = 1.317


def build_generic_ramjet_vehicle() -> BaseVehicleConfig:
    """Build a generic, validating vehicle with a single ramjet engine.

    Returns:
        A :class:`BaseVehicleConfig` with one ``RamjetEngine`` propulsion
        component using values consistent with this module's design-point
        defaults.
    """
    return BaseVehicleConfig(
        name="generic_ramjet_test_vehicle",
        description="Generic vehicle fixture for powerplant module tests.",
        propulsion={
            "stage2_ramjet": RamjetEngine(
                design_mach=GENERIC_DESIGN_MACH,
                combustor_temp_K=GENERIC_COMBUSTOR_TEMP_K,
                nozzle_area_ratio=GENERIC_NOZZLE_AREA_RATIO,
            )
        },
    )


@pytest.fixture()
def generic_ramjet_vehicle() -> BaseVehicleConfig:
    """Pytest fixture wrapping :func:`build_generic_ramjet_vehicle`."""
    return build_generic_ramjet_vehicle()
