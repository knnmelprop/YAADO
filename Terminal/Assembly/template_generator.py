import os
from pydantic import BaseModel

from YAADO_Core import ComponentStore
from YAADO_Core.Foundation import BaseVehicleConfig


def generate_template(name: str, component_classes: list[Type[BaseModel]], pre_filled: bool = False) -> None:
    instantiated_components = []
    
    for comp_cls in component_classes:
        if pre_filled:
            instantiated_components.append(prefill_component_values(comp_cls))
        else:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                instantiated_components.append(comp_cls.model_construct())
            
    template_vehicle = assemble_vehicle(name, instantiated_components)

    os.makedirs(f"Hangar/{name}/", exist_ok=True)
    template_vehicle.to_toml(f"Hangar/{name}/{name}.toml")


def assemble_vehicle(name: str, components: list[BaseModel]) -> BaseVehicleConfig:
    template_vehicle = BaseVehicleConfig(name=name)
    
    for idx, comp in enumerate(components):
        if isinstance(comp, ComponentStore.AERO_COMPONENTS):
            template_vehicle.aero_surfaces[f"aero_{idx}"] = comp        # type: ignore
        elif isinstance(comp, ComponentStore.BODY_COMPONENTS):
            template_vehicle.bodies[f"body_{idx}"] = comp               # type: ignore
        elif isinstance(comp, ComponentStore.PROPULSION_COMPONENTS):
            template_vehicle.propulsion[f"engine_{idx}"] = comp         # type: ignore
        elif isinstance(comp, ComponentStore.MassProperties):
            template_vehicle.mass_properties = comp                     # type: ignore
        else:
            raise TypeError(f"Unknown component: {type(comp)}")

    return template_vehicle


def prefill_component_values(component_class: Type[BaseModel]) -> BaseModel:
    kwargs = {}

    for field_name, field_info in component_class.model_fields.items():
        if field_name == "type":
            continue
            
        kwargs[field_name] = field_info.examples[0] 

    return component_class(**kwargs)
