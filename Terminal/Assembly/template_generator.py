from pydantic import BaseModel

from YAADO_Core import ComponentStore
from YAADO_Core.Foundation import BaseVehicleConfig


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

