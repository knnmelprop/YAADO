"""Builder and schema definitions for mission profiles composed of ordered segments.

A mission profile defines operational flight phases (boost, climb, cruise,
descent, staging) without duplicating vehicle design parameters. The builder
keeps definitions solver-agnostic so workflows can map them onto SUAVE mission
segments, 3DoF/6DoF trajectory integration, or OpenMDAO optimization phases.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig, ComponentNotFoundError


class BaseMissionSegment(BaseModel):
    """Abstract base schema for all mission flight segments."""

    model_config = ConfigDict(extra="forbid", frozen=True)


    name: str = Field(min_length=1, description="Unique segment name within the mission profile.")


class BoostSegment(BaseMissionSegment):
    """Initial launch and boost phase (rail launch, rocket motor burn).

    Attributes:
        name: Unique segment identifier.
        launch_angle: Rail or launch elevation angle in degrees above horizontal [0, 90].
        azimuth: Launch heading azimuth in degrees [0, 360].
        active_propulsion: Component key of the active booster in ``vehicle.propulsion``.
        rail_length: Optional length of the launch guide rail in meters.
    """

    UNITS: ClassVar[dict[str, str]] = {
        "launch_angle": "deg",
        "azimuth": "deg",
        "rail_length": "m",
    }

    type: Literal["boost"] = Field(default="boost", frozen=True)
    launch_angle: float = Field(
        ge=0.0,
        le=90.0,
        description="Launch rail elevation angle in degrees above horizontal.",
    )
    azimuth: float = Field(
        default=0.0,
        ge=0.0,
        le=360.0,
        description="Launch heading azimuth in degrees clockwise from north.",
    )
    active_propulsion: str | None = Field(
        default=None,
        description="Component key of the active motor in vehicle.propulsion.",
    )
    rail_length: float | None = Field(
        default=None,
        gt=0.0,
        description="Length of the launch guide rail in meters.",
    )


class ClimbSegment(BaseMissionSegment):
    """Climb and acceleration phase.

    Attributes:
        name: Unique segment identifier.
        target_altitude: Target termination altitude in meters.
        target_mach: Optional target Mach number at segment end.
        target_velocity: Optional target true airspeed in m/s at segment end.
        climb_rate: Optional target vertical climb speed in m/s.
        throttle: Commanded engine throttle setting [0.0, 1.0].
        active_propulsion: Component key of the active engine in ``vehicle.propulsion``.
    """

    UNITS: ClassVar[dict[str, str]] = {
        "target_altitude": "m",
        "target_mach": "-",
        "target_velocity": "m/s",
        "climb_rate": "m/s",
        "throttle": "-",
    }

    type: Literal["climb"] = Field(default="climb", frozen=True)
    target_altitude: float = Field(
        ge=0.0,
        description="Target termination altitude in meters.",
    )
    target_mach: float | None = Field(
        default=None,
        gt=0.0,
        description="Target Mach number at segment termination.",
    )
    target_velocity: float | None = Field(
        default=None,
        gt=0.0,
        description="Target true airspeed in m/s at segment termination.",
    )
    climb_rate: float | None = Field(
        default=None,
        gt=0.0,
        description="Target vertical climb speed in m/s.",
    )
    throttle: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Commanded engine throttle fraction [0.0, 1.0].",
    )
    active_propulsion: str | None = Field(
        default=None,
        description="Component key of the active engine in vehicle.propulsion.",
    )

    @model_validator(mode="after")
    def _validate_climb_speed(self) -> ClimbSegment:
        if (
            self.target_mach is None
            and self.target_velocity is None
            and self.climb_rate is None
        ):
            raise ValueError(
                "ClimbSegment requires at least one rate or speed parameter: "
                "'target_mach', 'target_velocity', or 'climb_rate'"
            )
        return self


class CruiseSegment(BaseMissionSegment):
    """Sustained level flight phase.

    Attributes:
        name: Unique segment identifier.
        altitude: Cruising altitude in meters.
        mach: Optional cruising Mach number.
        velocity: Optional cruising true airspeed in m/s.
        distance: Optional cruise ground distance in meters.
        duration: Optional cruise duration in seconds.
        throttle: Commanded engine throttle setting [0.0, 1.0].
        active_propulsion: Component key of the active engine in ``vehicle.propulsion``.
    """

    UNITS: ClassVar[dict[str, str]] = {
        "altitude": "m",
        "mach": "-",
        "velocity": "m/s",
        "distance": "m",
        "duration": "s",
        "throttle": "-",
    }

    type: Literal["cruise"] = Field(default="cruise", frozen=True)
    altitude: float = Field(
        ge=0.0,
        description="Cruising altitude in meters.",
    )
    mach: float | None = Field(
        default=None,
        gt=0.0,
        description="Cruising Mach number.",
    )
    velocity: float | None = Field(
        default=None,
        gt=0.0,
        description="Cruising true airspeed in m/s.",
    )
    distance: float | None = Field(
        default=None,
        gt=0.0,
        description="Cruise ground distance in meters.",
    )
    duration: float | None = Field(
        default=None,
        gt=0.0,
        description="Cruise duration in seconds.",
    )
    throttle: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Commanded engine throttle fraction [0.0, 1.0].",
    )
    active_propulsion: str | None = Field(
        default=None,
        description="Component key of the active engine in vehicle.propulsion.",
    )

    @model_validator(mode="after")
    def _validate_cruise_criteria(self) -> CruiseSegment:
        if self.distance is None and self.duration is None:
            raise ValueError(
                "CruiseSegment requires at least one termination criteria: 'distance' or 'duration'"
            )
        if self.mach is None and self.velocity is None:
            raise ValueError(
                "CruiseSegment requires at least one speed specification: 'mach' or 'velocity'"
            )
        return self


class DescentSegment(BaseMissionSegment):
    """Descent, terminal dive, or glide phase.

    Attributes:
        name: Unique segment identifier.
        target_altitude: Target termination altitude in meters.
        target_mach: Optional target Mach number.
        target_velocity: Optional target true airspeed in m/s.
        descent_rate: Optional vertical descent speed in m/s.
        throttle: Commanded engine throttle setting [0.0, 1.0].
        active_propulsion: Component key of the active engine in ``vehicle.propulsion``.
    """

    UNITS: ClassVar[dict[str, str]] = {
        "target_altitude": "m",
        "target_mach": "-",
        "target_velocity": "m/s",
        "descent_rate": "m/s",
        "throttle": "-",
    }

    type: Literal["descent"] = Field(default="descent", frozen=True)
    target_altitude: float = Field(
        ge=0.0,
        description="Target termination altitude in meters.",
    )
    target_mach: float | None = Field(
        default=None,
        gt=0.0,
        description="Target Mach number.",
    )
    target_velocity: float | None = Field(
        default=None,
        gt=0.0,
        description="Target true airspeed in m/s.",
    )
    descent_rate: float | None = Field(
        default=None,
        gt=0.0,
        description="Target vertical descent speed in m/s.",
    )
    throttle: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Commanded engine throttle fraction [0.0, 1.0].",
    )
    active_propulsion: str | None = Field(
        default=None,
        description="Component key of the active engine in vehicle.propulsion.",
    )

    @model_validator(mode="after")
    def _validate_descent_criteria(self) -> DescentSegment:
        if (
            self.target_mach is None
            and self.target_velocity is None
            and self.descent_rate is None
        ):
            raise ValueError(
                "DescentSegment requires at least one rate or speed parameter: "
                "'target_mach', 'target_velocity', or 'descent_rate'"
            )
        return self


class StagingSegment(BaseMissionSegment):
    """Stage separation or unpowered coast phase.

    Attributes:
        name: Unique segment identifier.
        duration: Coast duration during staging in seconds.
        jettison_component: Optional component name to jettison (e.g. booster casing).
        active_propulsion: Optional component key of the active engine in ``vehicle.propulsion``.
    """

    UNITS: ClassVar[dict[str, str]] = {
        "duration": "s",
    }

    type: Literal["staging"] = Field(default="staging", frozen=True)
    duration: float = Field(
        default=0.0,
        ge=0.0,
        description="Coast duration during staging in seconds.",
    )
    jettison_component: str | None = Field(
        default=None,
        description="Component name to jettison from vehicle.",
    )
    active_propulsion: str | None = Field(
        default=None,
        description="Component key of the active engine in vehicle.propulsion.",
    )


AnyMissionSegment = Annotated[
    BoostSegment | ClimbSegment | CruiseSegment | DescentSegment | StagingSegment,
    Field(discriminator="type"),
]


@dataclass(frozen=True)
class MissionProfile:
    """Immutable mission profile containing an ordered sequence of segments.

    Attributes:
        name: Unique mission profile name.
        segments: Ordered sequence of validated mission segments.
        vehicle_name: Optional target vehicle name.
    """

    name: str
    segments: tuple[AnyMissionSegment, ...]
    vehicle_name: str | None = None

    def validate_against_vehicle(self, vehicle: BaseVehicleConfig) -> None:
        """Verify that all subsystem references in this profile exist on the vehicle.

        Args:
            vehicle: The validated vehicle configuration to check against.

        Raises:
            ComponentNotFoundError: If an active_propulsion or jettison_component
                referenced by a segment is missing from the vehicle.
        """
        for seg in self.segments:
            if (
                seg.active_propulsion is not None
                and seg.active_propulsion not in vehicle.propulsion
            ):
                available = sorted(vehicle.propulsion.keys())
                raise ComponentNotFoundError(
                    f"Segment '{seg.name}' references active_propulsion='{seg.active_propulsion}', "
                    f"but vehicle '{vehicle.name}' has no such propulsion component. "
                    f"Available propulsion components: {available}"
                )

            if isinstance(seg, StagingSegment) and seg.jettison_component is not None:
                all_comps = vehicle.all_components()
                if seg.jettison_component not in all_comps:
                    available_all = sorted(all_comps.keys())
                    raise ComponentNotFoundError(
                        f"Segment '{seg.name}' references jettison_component='{seg.jettison_component}', "
                        f"but vehicle '{vehicle.name}' has no such component. "
                        f"Available components: {available_all}"
                    )


class MissionBuilder:
    """Fluent builder producing an ordered, validated :class:`MissionProfile`.

    Example:
        builder = MissionBuilder("harpoon_sea_skim", vehicle=vehicle)
        profile = (
            builder
            .add_segment(BoostSegment(name="launch", launch_angle=83.0, active_propulsion="launch_booster"))
            .add_segment(StagingSegment(name="booster_sep", duration=0.5, jettison_component="launch_booster"))
            .add_segment(ClimbSegment(name="ingress", target_altitude=300.0, target_mach=0.8, active_propulsion="sustainer"))
            .add_segment(CruiseSegment(name="sea_skim", altitude=15.0, mach=0.85, distance=120000.0, active_propulsion="sustainer"))
            .add_segment(DescentSegment(name="terminal", target_altitude=0.0, target_mach=0.85))
            .build()
        )
    """



    def __init__(
        self,
        mission_name: str,
        vehicle: BaseVehicleConfig | None = None,
    ) -> None:
        """Initialize the mission builder.

        Args:
            mission_name: Non-empty identifier for the mission profile.
            vehicle: Optional validated vehicle configuration to validate against.

        Raises:
            ValueError: If mission_name is empty or whitespace.
        """
        if not mission_name or not mission_name.strip():
            raise ValueError("mission_name cannot be empty")
        self.mission_name = mission_name.strip()
        self.vehicle = vehicle
        self._segments: list[AnyMissionSegment] = []

    def _validate_segment_name(self, name: str) -> None:
        if not name or not name.strip():
            raise ValueError("Segment name cannot be empty")
        if any(s.name == name for s in self._segments):
            raise ValueError(
                f"Segment '{name}' already defined in mission '{self.mission_name}'"
            )

    def add_segment(self, segment: AnyMissionSegment) -> MissionBuilder:
        """Append a pre-instantiated segment model to the mission profile.

        Args:
            segment: A validated segment model instance.

        Returns:
            ``self`` for fluent method chaining.

        Raises:
            ValueError: If a segment with the same name already exists.
            ComponentNotFoundError: If the segment references a vehicle component
                missing from the configured vehicle.
        """
        self._validate_segment_name(segment.name)
        if self.vehicle is not None:
            if (
                segment.active_propulsion is not None
                and segment.active_propulsion not in self.vehicle.propulsion
            ):
                available = sorted(self.vehicle.propulsion.keys())
                raise ComponentNotFoundError(
                    f"Segment '{segment.name}' active_propulsion='{segment.active_propulsion}' "
                    f"not found in vehicle '{self.vehicle.name}'. Available: {available}"
                )
            if isinstance(segment, StagingSegment) and segment.jettison_component is not None:
                all_comps = self.vehicle.all_components()
                if segment.jettison_component not in all_comps:
                    available_all = sorted(all_comps.keys())
                    raise ComponentNotFoundError(
                        f"Segment '{segment.name}' jettison_component='{segment.jettison_component}' "
                        f"not found in vehicle '{self.vehicle.name}'. Available: {available_all}"
                    )
        self._segments.append(segment)
        return self

    def build(self) -> MissionProfile:
        """Return the validated, immutable mission profile.

        Returns:
            The assembled :class:`MissionProfile` instance.

        Raises:
            ValueError: If no segments have been added.
        """
        if not self._segments:
            raise ValueError(
                f"Mission '{self.mission_name}' must contain at least one segment"
            )
        return MissionProfile(
            name=self.mission_name,
            segments=tuple(self._segments),
            vehicle_name=self.vehicle.name if self.vehicle is not None else None,
        )

