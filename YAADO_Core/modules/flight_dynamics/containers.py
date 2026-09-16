"""Typed result containers for flight dynamics analyses.

Provides strongly typed dataclasses for trajectory metrics, samples, and simulation results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from YAADO_Core.Foundation.analysis_base import BaseAnalysisResults
from YAADO_Core.Foundation.units import (
    Dimensionless,
    Meters,
    MetersPerSecond,
    Pascals,
    Seconds,
)

if TYPE_CHECKING:
    from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import TrajectorySamples


@dataclass(frozen=True)
class PointMassBoostResults(BaseAnalysisResults):
    """Strongly typed outputs for 3-DOF point-mass rocket boost trajectory simulation.

    Every field is a typed attribute with semantic SI unit annotations.
    Scalar metrics and units are reflected automatically via :meth:`BaseAnalysisResults.scalars`
    and :meth:`BaseAnalysisResults.units`.
    """

    burnout_time: Seconds
    burnout_velocity: MetersPerSecond
    burnout_mach: Dimensionless
    burnout_altitude: Meters
    q_max: Pascals
    range_at_burnout: Meters
    nominal_burn_time: Seconds
    ground_impact_before_burnout: bool
    burnout_vx: MetersPerSecond
    burnout_vh: MetersPerSecond
    stopped_reason: str
    ground_impact: bool
    t_end_s: Seconds
    final_x: Meters
    final_h: Meters
    final_v: MetersPerSecond
    final_mach: Dimensionless
    apogee_altitude: Meters | None = None
    apogee_time: Seconds | None = None
    apogee_range: Meters | None = None
    flight_time: Seconds | None = None
    flight_range: Meters | None = None
    impact_velocity: MetersPerSecond | None = None
    samples: TrajectorySamples | None = None
    boost_samples: TrajectorySamples | None = None
