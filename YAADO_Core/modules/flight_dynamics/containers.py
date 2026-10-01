"""Typed result containers for flight dynamics analyses.

Provides strongly typed dataclasses for trajectory metrics, samples, and simulation results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from YAADO_Core.Foundation.analysis_base import BaseAnalysisResults
from YAADO_Core.Foundation.units import (
    Dimensionless,
    Meters,
    MetersPerSecond,
    Pascals,
    Seconds,
)


@dataclass(frozen=True)
class TrajectorySamples:
    """Dense evaluation arrays and key trajectory indices."""

    t_s: np.ndarray
    x_m: np.ndarray
    h_m: np.ndarray
    v_ms: np.ndarray
    mach: np.ndarray
    q_pa: np.ndarray
    q_max_idx: int
    apogee_idx: int
    burn_time_s: float
    ground_altitude_m: float = 0.0


@dataclass(frozen=True)
class PointMassBoostResults(BaseAnalysisResults):
    """Strongly typed outputs for 3-DOF point-mass rocket boost trajectory simulation.

    Every field is a typed attribute with semantic SI unit annotations.
    Scalar metrics and units are reflected automatically via :meth:`BaseAnalysisResults.scalars`
    and :meth:`BaseAnalysisResults.units`.
    """

    HEADLINE_METRICS: ClassVar[tuple[str, ...]] = (
        "apogee_altitude",
        "burnout_velocity",
        "burnout_mach",
        "q_max",
        "t_end_s",
        "final_x",
    )

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
    apogee_altitude: Meters
    apogee_time: Seconds
    apogee_range: Meters
    flight_time: Seconds
    flight_range: Meters
    impact_velocity: MetersPerSecond = 0.0
    samples: TrajectorySamples | None = None
    boost_samples: TrajectorySamples | None = None
