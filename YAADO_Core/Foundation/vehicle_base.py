"""Universal declarative vehicle configuration schema and component query manager.

This module provides :class:`BaseVehicleConfig`, the universal blueprint for all
vehicles analyzed in YAADO. It validates vehicle definitions loaded from declarative
TOML files in ``Hangar/`` and exposes generic composition query APIs for solvers.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TypeVar, overload

import toml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from YAADO_Core.ComponentStore import (
    AnyAeroComponent,
    AnyBodyComponent,
    AnyComponent,
    AnyPropulsionComponent,
    MassProperties,
)

T = TypeVar("T")


class ComponentNotFoundError(KeyError, ValueError):
    """Raised when a requested component is not found on the vehicle."""


class BaseVehicleConfig(BaseModel):
    """The universal declarative blueprint for all YAADO vehicles.

    Attributes:
        name: Unique vehicle name.
        description: Free-text description.
        propulsion: Dictionary of engines, motors, and propulsive networks.
        aero_surfaces: Dictionary of wings, fins, and control surfaces.
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

    @model_validator(mode="after")
    def _validate_unique_component_names(self) -> BaseVehicleConfig:
        """Ensure component names are globally unique across all stores."""
        prop_names = set(self.propulsion.keys())
        aero_names = set(self.aero_surfaces.keys())
        body_names = set(self.bodies.keys())

        overlap_prop_aero = prop_names & aero_names
        overlap_prop_body = prop_names & body_names
        overlap_aero_body = aero_names & body_names

        overlaps = overlap_prop_aero | overlap_prop_body | overlap_aero_body
        if overlaps:
            raise ValueError(
                f"Duplicate component names found across categories: {sorted(overlaps)}. "
                "Component names must be globally unique within the vehicle."
            )
        return self

    @property
    def total_mass(self) -> float | None:
        """Total vehicle mass in kilograms if defined in mass_properties."""
        if self.mass_properties is not None and self.mass_properties.total_mass is not None:
            return self.mass_properties.total_mass
        return None

    def all_components(self) -> dict[str, AnyComponent]:
        """Return a unified dictionary of all named components across bodies, aero_surfaces, and propulsion.

        Returns:
            Dictionary mapping component names to their validated component instances.
        """
        merged: dict[str, AnyComponent] = {}
        merged.update(self.bodies)
        merged.update(self.aero_surfaces)
        merged.update(self.propulsion)
        return merged

    def get_components_by_type(
        self, component_types: type[T] | tuple[type[T], ...]
    ) -> dict[str, T]:
        """Filter components by type across all categories.

        Args:
            component_types: A single component type or tuple of types (e.g. ``AERO_COMPONENTS``).

        Returns:
            Dictionary of matching component names to instances.
        """
        return {
            name: comp
            for name, comp in self.all_components().items()
            if isinstance(comp, component_types)
        }

    @overload
    def get_component(self, name: str, expected_type: None = None) -> AnyComponent: ...

    @overload
    def get_component(self, name: str, expected_type: type[T] | tuple[type[T], ...]) -> T: ...

    def get_component(
        self, name: str, expected_type: type[T] | tuple[type[T], ...] | None = None
    ) -> AnyComponent | T:
        """Retrieve a component by name, optionally verifying its type.

        Args:
            name: Identifier of the component.
            expected_type: Optional component type or tuple of types to enforce.

        Returns:
            The resolved component instance.

        Raises:
            KeyError: If the component name is not found on the vehicle.
            TypeError: If the component does not match ``expected_type``.
        """
        all_comps = self.all_components()
        if name not in all_comps:
            available = sorted(all_comps.keys())
            raise ComponentNotFoundError(
                f"Component '{name}' not found on vehicle '{self.name}'. "
                f"Available components: {available}"
            )
        comp = all_comps[name]
        if expected_type is not None and not isinstance(comp, expected_type):
            expected_names = (
                tuple(t.__name__ for t in expected_type)
                if isinstance(expected_type, tuple)
                else expected_type.__name__
            )
            raise TypeError(
                f"Component '{name}' on vehicle '{self.name}' is {type(comp).__name__}, "
                f"expected {expected_names}."
            )
        return comp

    def find_single_component(
        self,
        component_types: type[T] | tuple[type[T], ...],
        name: str | None = None,
    ) -> T:
        """Resolve a single component by type, with optional explicit name override.

        If ``name`` is provided, retrieves that specific component and verifies its type.
        If ``name`` is omitted, auto-resolves if exactly one matching component exists.

        Args:
            component_types: Single component type or tuple of candidate types.
            name: Optional explicit component name.

        Returns:
            The resolved component instance.

        Raises:
            KeyError: If ``name`` is specified but not found on the vehicle.
            TypeError: If ``name`` is specified but does not match ``component_types``.
            ValueError: If ``name`` is omitted and either no matching components exist
                or multiple matching components exist.
        """
        if name is not None:
            return self.get_component(name, expected_type=component_types)

        candidates = self.get_components_by_type(component_types)
        expected_names = (
            tuple(t.__name__ for t in component_types)
            if isinstance(component_types, tuple)
            else component_types.__name__
        )
        if not candidates:
            raise ValueError(
                f"Vehicle '{self.name}' has no component matching {expected_names}."
            )
        if len(candidates) > 1:
            candidate_keys = sorted(candidates.keys())
            raise ValueError(
                f"Vehicle '{self.name}' has multiple components matching {expected_names}: {candidate_keys}. "
                "Please specify an explicit component name."
            )
        return next(iter(candidates.values()))

    @classmethod
    def from_toml(cls, path: str | Path) -> BaseVehicleConfig:
        """Load and validate a vehicle config from a TOML file.

        Args:
            path: Path to the TOML file.

        Returns:
            A validated config instance.

        Raises:
            FileNotFoundError: If the specified file does not exist.
            ValueError: If the TOML root is not a mapping or syntax is invalid.
            pydantic.ValidationError: If the data violates the schema.
        """
        target_path = Path(path)
        if not target_path.is_file():
            raise FileNotFoundError(f"Vehicle TOML configuration not found: {target_path}")

        try:
            with open(target_path, "rb") as f:
                raw = tomllib.load(f)
        except tomllib.TOMLDecodeError as err:
            raise ValueError(f"Failed to parse TOML from {target_path}: {err}") from err

        if not isinstance(raw, dict):
            raise ValueError(f"TOML root of {target_path} must be a mapping")  # noqa: TRY004

        return cls.model_validate(raw)

    def to_toml(self, path: str | Path) -> None:
        """Serialize the config to a TOML file.

        Args:
            path: Destination file path (parent directory will be created if needed).
        """
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        data = self.model_dump(mode="json", exclude_none=True)
        target_path.write_text(
            toml.dumps(data),
            encoding="utf-8",
        )