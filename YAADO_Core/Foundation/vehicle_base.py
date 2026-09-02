"""Basic vehicle configuration

This class handles importing and exporting the vehicle configuration
"""

from __future__ import annotations

from pathlib import Path

import toml
from pydantic import BaseModel, ConfigDict, Field

from YAADO_Core.ComponentStore import (
    AnyPropulsionComponent,
    AnyAeroComponent,
    AnyBodyComponent,
    MassProperties
)

class BaseVehicleConfig(BaseModel):
    """The universal blueprint for all vehicles.
    
    Attributes:
        name: Unique vehicle name.
        description: Free-text description.
        propulsion: Dictionary of engines and motors.
        aero_surfaces: Dictionary of wings and fins.
        bodies: Dictionary of airframes and fuselages.
        mass_properties: Optional global mass properties (overrides distributed component masses).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = Field(default="not provided")
    
    propulsion: dict[str, AnyPropulsionComponent] = Field(default_factory=dict)
    aero_surfaces: dict[str, AnyAeroComponent] = Field(default_factory=dict)
    bodies: dict[str, AnyBodyComponent] = Field(default_factory=dict)
    mass_properties: MassProperties | None = Field(default=None)

    @classmethod
    def from_toml(cls, path: str | Path) -> "BaseVehicleConfig":
        """Load and validate a vehicle config from a TOML file.

        Args:
            path: Path to the TOML file.

        Returns:
            A validated config instance.

        Raises:
            pydantic.ValidationError: If the data violates the schema.
        """
        raw = toml.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"TOML root of {path} must be a mapping")
        return cls.model_validate(raw)

    def to_toml(self, path: str | Path) -> None:
        """Serialize the config to a TOML file.

        Args:
            path: Destination file path (parent directory must exist).
        """
        data = self.model_dump(mode="json")
        Path(path).write_text(
            toml.dumps(data),
            encoding="utf-8",
        )