# MELprop-IADE | src.schemas.vehicle_schema | v0.1.0
"""Pydantic v2 schemas for MELprop-IADE vehicle configurations.

All quantities are SI; unit suffixes are encoded in field names
(``thrust_N``, ``span_m``, ``isp_s``). Configs round-trip to YAML via
:meth:`BaseVehicleConfig.from_yaml` / :meth:`BaseVehicleConfig.to_yaml`.

"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MassProperties(BaseModel):
    """Vehicle mass properties (from CAD or estimate).

    Attributes:
        cg_from_nose_m: Longitudinal centre of gravity measured from the
            nose tip in meters (> 0).
        cg_source: Provenance of the CG value.
    """

    model_config = ConfigDict(extra="forbid")

    cg_from_nose_m: float = Field(..., gt=0.0)
    cg_source: str = ""
    total_mass_kg: Union[float, None] = Field(default=None, gt=0.0)


class BaseVehicleConfig(BaseModel):
    """Common root of every MELprop-IADE vehicle configuration.

    Attributes:
        name: Unique vehicle name.
        vehicle_type: Discriminator — ``"UAV"`` or ``"Rocket"``.
        description: Free-text description.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    vehicle_type: Literal["UAV", "Rocket"]
    description: str = ""

    @classmethod
    def from_yaml(cls, path: str | Path) -> "BaseVehicleConfig":
        """Load and validate a vehicle config from a YAML file.

        Validates the YAML data directly against the calling class.

        Args:
            path: Path to the YAML file.

        Returns:
            A validated config instance.

        Raises:
            ValueError: If ``vehicle_type`` is missing or unknown.
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

