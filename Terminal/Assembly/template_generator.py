"""Vehicle template generator.

Provides utilities for generating declarative vehicle TOML templates in the
Hangar workspace, either as unpopulated skeleton files or prefilled from schema
examples.
"""

from pathlib import Path

from pydantic import BaseModel

from YAADO_Core import ComponentStore
from YAADO_Core.Foundation import BaseVehicleConfig


class VehicleTemplateGenerator:
    """Generates vehicle configuration templates and assembles components.

    Handles creation of declarative TOML templates in the Hangar directory,
    supporting both unpopulated production skeletons and example-prefilled models.
    """

    @classmethod
    def generate_template(
        cls,
        name: str,
        component_classes: list[type[BaseModel]],
        pre_filled: bool = False,
    ) -> None:
        """Generate and write a vehicle TOML template file to the Hangar directory.

        Args:
            name: Name of the vehicle configuration and output directory.
            component_classes: List of Pydantic component model classes to include.
            pre_filled: If True, populates fields with example values from the schema.
                If False, creates an unvalidated skeleton structure with empty fields.
        """
        instantiated_components = []

        for comp_cls in component_classes:
            if pre_filled:
                instantiated_components.append(cls.prefill_component_values(comp_cls))
            else:
                instantiated_components.append(comp_cls.model_construct())

        template_vehicle = cls.assemble_vehicle(name, instantiated_components)

        output_dir = Path("Hangar") / name
        output_dir.mkdir(parents=True, exist_ok=True)
        template_vehicle.to_toml(output_dir / f"{name}.toml")

    @classmethod
    def assemble_vehicle(
        cls,
        name: str,
        components: list[BaseModel],
    ) -> BaseVehicleConfig:
        """Assemble instantiated component models into a BaseVehicleConfig instance.

        Args:
            name: Name of the vehicle.
            components: List of instantiated Pydantic component models.

        Returns:
            BaseVehicleConfig populated with components routed to their appropriate subsystem.

        Raises:
            TypeError: If an unrecognized component instance is provided.
        """
        template_vehicle = BaseVehicleConfig(name=name)

        for idx, comp in enumerate(components):
            if isinstance(comp, ComponentStore.AERO_COMPONENTS):
                template_vehicle.aero_surfaces[f"aero_{idx}"] = comp
            elif isinstance(comp, ComponentStore.BODY_COMPONENTS):
                template_vehicle.bodies[f"body_{idx}"] = comp
            elif isinstance(comp, ComponentStore.PROPULSION_COMPONENTS):
                template_vehicle.propulsion[f"engine_{idx}"] = comp
            elif isinstance(comp, ComponentStore.MassProperties):
                template_vehicle.mass_properties = comp
            else:
                raise TypeError(f"Unknown component: {type(comp)}")

        return template_vehicle

    @classmethod
    def prefill_component_values(
        cls,
        component_class: type[BaseModel],
    ) -> BaseModel:
        """Instantiate a component model populated with values from its schema examples.

        Args:
            component_class: Pydantic component class to instantiate.

        Returns:
            Instantiated component model with fields populated from schema examples.
        """
        kwargs = {}
        for field_name, field_info in component_class.model_fields.items():
            if field_name == "type":
                continue

            kwargs[field_name] = field_info.examples[0] # type: ignore

        return component_class(**kwargs)
