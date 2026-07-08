# MELprop-IADE | src.schemas.vehicle_schema | v0.1.0
"""Pydantic v2 schemas for MELprop-IADE vehicle configurations.

All quantities are SI; unit suffixes are encoded in field names
(``thrust_N``, ``span_m``, ``isp_s``). Configs round-trip to YAML via
:meth:`BaseVehicleConfig.from_yaml` / :meth:`BaseVehicleConfig.to_yaml`.

Two concrete vehicle types exist:

- :class:`UAVConfig` — Project A, fixed-wing drone with the Jetpol
  GTM-140 turbojet.
- :class:`RocketConfig` — Project B, two-stage rocket (solid booster +
  ramjet cruise stage).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WingConfig(BaseModel):
    """Fixed-wing planform definition.

    Attributes:
        aspect_ratio: Wing aspect ratio b^2/S (dimensionless, > 0).
        sweep_deg: Quarter-chord sweep in degrees (-10..70).
        taper_ratio: Tip/root chord ratio (0 < taper <= 1).
        span_m: Wing span in meters (> 0).
        airfoil_root: Root airfoil designation (e.g. ``"NACA2412"``).
        airfoil_tip: Tip airfoil designation.
    """

    model_config = ConfigDict(extra="forbid")

    aspect_ratio: float = Field(..., gt=0.0, le=50.0)
    sweep_deg: float = Field(..., ge=-10.0, le=70.0)
    taper_ratio: float = Field(..., gt=0.0, le=1.0)
    span_m: float = Field(..., gt=0.0)
    airfoil_root: str
    airfoil_tip: str


class TurbojetConfig(BaseModel):
    """Small turbojet engine definition (e.g. Jetpol GTM-140).

    Attributes:
        type: Discriminator, always ``"turbojet"``.
        name: Engine designation.
        thrust_N: Static sea-level thrust in newtons (> 0).
        sfc_kg_per_Ns: Thrust-specific fuel consumption in kg/(N*s) (> 0).
        mass_kg: Dry engine mass in kilograms (> 0).
        mach_range: Operational (min, max) Mach numbers, increasing,
            subsonic (max <= 1.0 for a small turbojet).
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["turbojet"] = "turbojet"
    name: str
    thrust_N: float = Field(..., gt=0.0)
    sfc_kg_per_Ns: float = Field(..., gt=0.0)
    mass_kg: float = Field(..., gt=0.0)
    mach_range: tuple[float, float]

    @field_validator("mach_range")
    @classmethod
    def _mach_range_valid(cls, v: tuple[float, float]) -> tuple[float, float]:
        """Require 0 <= mach_min < mach_max <= 1.0."""
        lo, hi = v
        if lo < 0.0:
            raise ValueError("mach_range minimum must be >= 0")
        if hi <= lo:
            raise ValueError("mach_range must be increasing (min < max)")
        if hi > 1.0:
            raise ValueError("small turbojet mach_range maximum must be <= 1.0")
        return v


class SolidRocketConfig(BaseModel):
    """Solid rocket booster definition (Project B, stage 1).

    Attributes:
        type: Discriminator, always ``"solid_rocket"``.
        isp_s: Specific impulse in seconds (100..300 for solid propellant).
        propellant_mass_kg: Propellant mass in kilograms (> 0).
        burn_time_s: Burn duration in seconds (> 0).
        thrust_N: Average thrust in newtons (> 0).
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["solid_rocket"] = "solid_rocket"
    isp_s: float = Field(..., ge=100.0, le=300.0)
    propellant_mass_kg: float = Field(..., gt=0.0)
    burn_time_s: float = Field(..., gt=0.0)
    thrust_N: float = Field(..., gt=0.0)

    @model_validator(mode="after")
    def _thrust_consistent_with_isp(self) -> "SolidRocketConfig":
        """Cross-check: thrust ≈ mdot * Isp * g0 within a factor of 3.

        Catches unit mistakes (kN vs N, minutes vs seconds) early while
        leaving room for regressive/progressive thrust profiles.
        """
        g0 = 9.80665  # m/s^2
        mdot = self.propellant_mass_kg / self.burn_time_s
        thrust_ideal_N = mdot * self.isp_s * g0
        if not (thrust_ideal_N / 3.0 <= self.thrust_N <= thrust_ideal_N * 3.0):
            raise ValueError(
                f"thrust_N={self.thrust_N:.0f} inconsistent with "
                f"mdot*Isp*g0={thrust_ideal_N:.0f} N (check units)"
            )
        return self


class RamjetConfig(BaseModel):
    """Ramjet engine definition (Project B, stage 2).

    Attributes:
        type: Discriminator, always ``"ramjet"``.
        design_mach: Design-point Mach number (1.5..6; ramjets do not
            produce net thrust below ~Mach 1.5).
        fuel_type: Fuel designation (e.g. ``"kerosene"``).
        combustor_temp_K: Combustor exit total temperature in kelvin
            (1200..2600, bounded by material/dissociation limits).
        nozzle_area_ratio: Nozzle exit/throat area ratio (>= 1).
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["ramjet"] = "ramjet"
    design_mach: float = Field(..., ge=1.5, le=6.0)
    fuel_type: str
    combustor_temp_K: float = Field(..., ge=1200.0, le=2600.0)
    nozzle_area_ratio: float = Field(..., ge=1.0)


class BodyConfig(BaseModel):
    """Axisymmetric rocket body definition.

    Attributes:
        length_m: Total body length in meters (> 0).
        diameter_m: Body diameter in meters (> 0).
        nose_type: Nose shape (``"ogive"``, ``"conical"`` or ``"hemispherical"``).
    """

    model_config = ConfigDict(extra="forbid")

    length_m: float = Field(..., gt=0.0)
    diameter_m: float = Field(..., gt=0.0)
    nose_type: Literal["ogive", "conical", "hemispherical"] = "ogive"

    @model_validator(mode="after")
    def _slenderness(self) -> "BodyConfig":
        """Require fineness ratio L/D >= 5 (slender-body aero assumption)."""
        if self.length_m / self.diameter_m < 5.0:
            raise ValueError(
                "fineness ratio L/D < 5: slender-body empirical aero invalid"
            )
        return self


class FinConfig(BaseModel):
    """Rocket fin set definition.

    Attributes:
        count: Number of fins (3..8).
        span_m: Exposed semi-span of one fin in meters (> 0).
        sweep_deg: Leading-edge sweep in degrees (0..75).
    """

    model_config = ConfigDict(extra="forbid")

    count: int = Field(..., ge=3, le=8)
    span_m: float = Field(..., gt=0.0)
    sweep_deg: float = Field(..., ge=0.0, le=75.0)


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

        When called on :class:`BaseVehicleConfig`, the concrete class is
        chosen from the ``vehicle_type`` key; when called on a subclass,
        that subclass validates directly.

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
        if cls is BaseVehicleConfig:
            dispatch: dict[str, type[BaseVehicleConfig]] = {
                "UAV": UAVConfig,
                "Rocket": RocketConfig,
            }
            vehicle_type = raw.get("vehicle_type")
            if vehicle_type not in dispatch:
                raise ValueError(
                    f"Unknown vehicle_type {vehicle_type!r}; "
                    f"expected one of {sorted(dispatch)}"
                )
            return dispatch[vehicle_type].model_validate(raw)
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


class UAVConfig(BaseVehicleConfig):
    """Project A — fixed-wing UAV with a small turbojet.

    Attributes:
        wing: Wing planform definition.
        propulsion: Turbojet engine definition (Jetpol GTM-140).
    """

    vehicle_type: Literal["UAV"] = "UAV"
    wing: WingConfig
    propulsion: TurbojetConfig


class RocketConfig(BaseVehicleConfig):
    """Project B — two-stage rocket: solid booster + ramjet cruise stage.

    Attributes:
        stage_1: Solid rocket booster definition.
        stage_2: Ramjet cruise-stage definition.
        body: Axisymmetric body definition.
        fins: Fin set definition.
    """

    vehicle_type: Literal["Rocket"] = "Rocket"
    stage_1: SolidRocketConfig
    stage_2: RamjetConfig
    body: BodyConfig
    fins: FinConfig


#: Union of all concrete vehicle configs, for type annotations downstream.
VehicleConfig = Union[UAVConfig, RocketConfig]
