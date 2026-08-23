"""Basic vehicle configuration

This class handles importing and exporting the vehicle configuration
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from IADE_Core.ComponentStore import AnyComponent

class BaseVehicleConfig(BaseModel):
    """The universal blueprint for all vehicles.
    Attributes:
        name: Unique vehicle name.
        description: Free-text description.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = Field(default="not provided")
    components: dict[str, AnyComponent] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "BaseVehicleConfig":
        """Load and validate a vehicle config from a YAML file.

        Args:
            path: Path to the YAML file.

        Returns:
            A validated config instance.

        Raises:
            pydantic.ValidationError: If the data violates the schema.
        """
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"YAML root of {path} must be a mapping")
        return cls.model_validate(raw)

    def to_yaml(self, path: str | Path) -> None:
        """Serialize the config to a YAML file.

        Args:
            path: Destination file path (parent directory must exist).
        """
        data = self.model_dump(mode="json")
        Path(path).write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )