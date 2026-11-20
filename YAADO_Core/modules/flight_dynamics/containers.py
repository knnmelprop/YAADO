"""Typed result containers for flight dynamics analyses.

Provides strongly typed dataclasses for trajectory metrics, samples, and simulation results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from YAADO_Core.Foundation.analysis_base import BaseAnalysisResults
from YAADO_Core.Foundation.units import (
    Degrees,
    Dimensionless,
    Kilograms,
    Meters,
    MetersPerSecond,
    MetersPerSecond2,
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
class LaunchAngleSweepPoint:
    """Typed metrics for one launch-angle sweep point.

    Full-flight metrics are None when the sweep stops at motor burnout.
    """

    launch_angle_deg: Degrees
    burnout_mach: Dimensionless
    burnout_altitude: Meters
    burnout_range: Meters
    q_max: Pascals
    ground_impact_flag: bool
    apogee_altitude: Meters | None
    flight_time: Seconds | None
    flight_range: Meters | None


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


@dataclass(frozen=True)
class ParachuteConfig:
    """Parachute inputs for the descent analysis (there is no recovery schema yet).

    Attributes:
        drogue_cd: Drag coefficient of the drogue, based on its reference area.
        drogue_diameter: Drogue reference diameter [m]; area is ``pi / 4 * d^2``.
        main_cd: Drag coefficient of the main parachute.
        main_diameter: Main parachute reference diameter [m].
        main_deployment_altitude: Main deployment altitude above the ground plane [m].
        descent_speed_limit: Optional limit for the landing speed [m/s] (for example
            from competition rules); ``None`` means no limit is checked.
    """

    drogue_cd: Dimensionless
    drogue_diameter: Meters
    main_cd: Dimensionless
    main_diameter: Meters
    main_deployment_altitude: Meters
    descent_speed_limit: MetersPerSecond | None = None

    def __post_init__(self) -> None:
        """Validate the parachute inputs.

        Raises:
            ValueError: If a coefficient, diameter or altitude is not positive, or the
                speed limit is given and not positive.
        """
        for name in (
            "drogue_cd",
            "drogue_diameter",
            "main_cd",
            "main_diameter",
            "main_deployment_altitude",
        ):
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be positive.")
        if self.descent_speed_limit is not None and self.descent_speed_limit <= 0.0:
            raise ValueError("descent_speed_limit must be positive.")


@dataclass(frozen=True)
class DescentSamples:
    """Dense arrays of the descent, from apogee to landing."""

    t_s: np.ndarray
    x_m: np.ndarray
    h_m: np.ndarray
    vx_ms: np.ndarray
    vh_ms: np.ndarray
    speed_ms: np.ndarray
    main_open_idx: int


@dataclass(frozen=True)
class ParachuteDescentResults(BaseAnalysisResults):
    """Outputs of the parachute descent after apogee.

    Attributes:
        mass: Vehicle mass during the descent (burnout mass) [kg].
        apogee_altitude: Altitude where the descent starts [m].
        drogue_descent_speed: Speed just before the main opens [m/s] (equal to the
            speed at the end of the drogue phase).
        main_descent_speed: Speed at touchdown under the main [m/s].
        descent_time: Time from apogee to landing [s].
        main_deployment_time: Time from apogee to main opening [s].
        landing_x: Downrange position at landing [m].
        peak_deceleration: Largest parachute drag deceleration ``D / m``, which occurs
            when the main opens [m/s^2].
        landing_speed_within_limit: Whether the touchdown speed is within the user's
            limit; None if no limit was given.
        samples: Dense time history of the descent.
    """

    HEADLINE_METRICS: ClassVar[tuple[str, ...]] = (
        "drogue_descent_speed",
        "main_descent_speed",
        "descent_time",
        "landing_x",
        "peak_deceleration",
    )

    mass: Kilograms
    apogee_altitude: Meters
    drogue_descent_speed: MetersPerSecond
    main_descent_speed: MetersPerSecond
    descent_time: Seconds
    main_deployment_time: Seconds
    landing_x: Meters
    peak_deceleration: MetersPerSecond2
    landing_speed_within_limit: bool | None = None
    samples: DescentSamples | None = None
