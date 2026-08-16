# MELprop-IADE | IADE_Core.mission_builder | v0.1.0
"""Builder for mission profiles composed of ordered segments.

A mission is an ordered list of segments (climb, cruise, boost, staging
event, ...). The builder keeps the definition solver-agnostic: segments
are plain records that a workflow later maps onto SUAVE mission segments
or an OpenMDAO trajectory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MissionSegment:
    """Single mission segment definition.

    Attributes:
        name: Unique segment name within the mission.
        segment_type: Kind of segment, e.g. ``"climb"``, ``"cruise"``,
            ``"boost"``, ``"staging_event"``.
        parameters: Segment parameters in SI units (altitude_m, mach, ...).
    """

    name: str
    segment_type: str
    parameters: dict[str, Any] = field(default_factory=dict)


class MissionBuilder:
    """Fluent builder producing an ordered mission profile.

    Example:
        >>> mission = (
        ...     MissionBuilder("endurance")
        ...     .add_segment("climb_1", "climb", altitude_end_m=1000.0)
        ...     .add_segment("cruise_1", "cruise", mach=0.3)
        ...     .build()
        ... )
    """

    def __init__(self, mission_name: str) -> None:
        self.mission_name = mission_name
        self._segments: list[MissionSegment] = []

    def add_segment(
        self, name: str, segment_type: str, **parameters: Any
    ) -> "MissionBuilder":
        """Append a segment and return ``self`` for chaining.

        Raises:
            ValueError: If a segment with the same name already exists.
        """
        if any(s.name == name for s in self._segments):
            raise ValueError(f"Segment {name!r} already defined in mission")
        self._segments.append(MissionSegment(name, segment_type, dict(parameters)))
        return self

    def build(self) -> list[MissionSegment]:
        """Return the ordered list of segment definitions."""
        return list(self._segments)
