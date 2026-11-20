"""Tests for the OpenMDAO launch-angle optimizer.

Each 3-DOF full flight takes about 4 s, so the checks use a 1 deg grid around the
optimum and a coarse global grid instead of a 1 deg grid over all bounds.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tests.YAADO_Core.modules.flight_dynamics.test_point_mass_3dof import (
    _build_generic_solid_rocket,
)
from YAADO_Core.FlightDeck.launch_angle_optimizer import (
    DEFAULT_ANGLE_BOUNDS_DEG,
    LaunchAngleOptimum,
    optimize_launch_angle,
)
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import (
    BoosterParams,
    derive_trajectory_metrics,
    integrate_boost_phase,
    resolve_booster_params_from_vehicle,
)


def flight_range_at(params: BoosterParams, angle_deg: float) -> float:
    """Ground range of a direct full-flight run at one launch angle."""
    p = replace(params, launch_angle_deg=angle_deg)
    metrics, _, _ = derive_trajectory_metrics(integrate_boost_phase(p), p)
    return metrics.final_x


@pytest.fixture(scope="module")
def vehicle() -> BaseVehicleConfig:
    """The generic solid rocket used by the 3-DOF tests."""
    return _build_generic_solid_rocket()


@pytest.fixture(scope="module")
def full_flight_params(vehicle: BaseVehicleConfig) -> BoosterParams:
    """Booster parameters for full-flight runs."""
    return resolve_booster_params_from_vehicle(vehicle, stop_at_burnout=False)


@pytest.fixture(scope="module")
def optimum(vehicle: BaseVehicleConfig) -> LaunchAngleOptimum:
    """The optimizer result, computed once for all tests."""
    return optimize_launch_angle(vehicle)


def test_optimum_agrees_with_one_degree_grid(
    optimum: LaunchAngleOptimum, full_flight_params: BoosterParams
) -> None:
    """Angle within 1 deg of the best 1 deg grid point; range not below it minus 0.1%."""
    centre = round(optimum.launch_angle_deg)
    grid = {
        float(a): flight_range_at(full_flight_params, float(a))
        for a in range(centre - 4, centre + 5)
    }
    best_angle = max(grid, key=lambda a: grid[a])
    assert abs(optimum.launch_angle_deg - best_angle) <= 1.0
    assert optimum.flight_range >= grid[best_angle] * (1.0 - 1e-3)


def test_optimum_beats_coarse_global_grid(
    optimum: LaunchAngleOptimum, full_flight_params: BoosterParams
) -> None:
    """The optimum is not worse than runs spread over the whole angle range."""
    for angle in (10.0, 25.0, 60.0, 80.0):
        assert optimum.flight_range >= flight_range_at(full_flight_params, angle)


def test_optimum_range_matches_direct_run(
    optimum: LaunchAngleOptimum, full_flight_params: BoosterParams
) -> None:
    """The reported range is the range of a direct run at the reported angle."""
    direct = flight_range_at(full_flight_params, optimum.launch_angle_deg)
    assert optimum.flight_range == pytest.approx(direct, rel=1e-9)


def test_optimum_is_inside_bounds(optimum: LaunchAngleOptimum) -> None:
    """The optimum is strictly inside the bounds, not on them."""
    lower, upper = DEFAULT_ANGLE_BOUNDS_DEG
    assert lower + 1.0 < optimum.launch_angle_deg < upper - 1.0


def test_simulation_count_is_reported(optimum: LaunchAngleOptimum) -> None:
    """The count includes the finite-difference runs and is a small number."""
    assert 3 <= optimum.n_simulations <= 60


def test_optimum_is_frozen(optimum: LaunchAngleOptimum) -> None:
    """The result is an immutable dataclass."""
    with pytest.raises(AttributeError):
        optimum.launch_angle_deg = 1.0  # type: ignore[misc]


def test_creates_no_reports_folder(
    vehicle: BaseVehicleConfig, optimum: LaunchAngleOptimum
) -> None:
    """OpenMDAO reports are switched off: no ``reports`` folder appears in the working directory."""
    assert optimum.n_simulations > 0
    assert not (Path.cwd() / "reports").exists()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"bounds_deg": (60.0, 10.0)},
        {"bounds_deg": (-5.0, 80.0)},
        {"bounds_deg": (10.0, 95.0)},
        {"initial_angle_deg": 89.0},
    ],
)
def test_invalid_arguments_raise(
    vehicle: BaseVehicleConfig, kwargs: dict[str, object]
) -> None:
    """Bad bounds or a start angle outside them raise ValueError before any simulation."""
    with pytest.raises(ValueError):
        optimize_launch_angle(vehicle, **kwargs)  # type: ignore[arg-type]


def test_rejects_non_vehicle() -> None:
    """A non-vehicle argument raises TypeError."""
    with pytest.raises(TypeError):
        optimize_launch_angle("not a vehicle")  # type: ignore[arg-type]
