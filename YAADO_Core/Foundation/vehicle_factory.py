"""Factory translating YAADO vehicle configs into SUAVE vehicles.

SUAVE lives in ``external/suave`` (git submodule, pinned tag 2.5.2) and is
used as the vehicle representation for multi-disciplinary analyses.

The factory works on the generic :class:`~YAADO_Core.Foundation.vehicle_base.BaseVehicleConfig`
composition: each ``propulsion``, ``aero_surfaces``, and ``bodies`` component
is translated to its corresponding SUAVE object based on discriminator string
dispatch (``component.type``) and appended to the SUAVE vehicle.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any, ClassVar

import YAADO_Core.modules.suave_compat  # noqa: F401  # apply modern-Python shims before importing SUAVE

# isort: split
import SUAVE

from YAADO_Core.ComponentStore import (
    AnyAeroComponent,
    AnyBodyComponent,
    AnyPropulsionComponent,
)
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig


class VehicleFactory:
    """Builds SUAVE ``Vehicle`` objects from validated :class:`BaseVehicleConfig` instances.

    The factory iterates over the generic composition dictionaries exposed by
    :class:`BaseVehicleConfig` (``propulsion``, ``aero_surfaces``, ``bodies``) and
    translates each component to its SUAVE counterpart based on the component's
    discriminator type string, appending it to a freshly created SUAVE vehicle.
    """

    def build(self, vehicle: BaseVehicleConfig) -> Any:
        """Build a SUAVE vehicle from a validated :class:`BaseVehicleConfig`.

        Args:
            vehicle: A validated, vehicle-agnostic configuration exposing
                ``propulsion``, ``aero_surfaces``, and ``bodies`` component dictionaries.

        Returns:
            The assembled SUAVE ``Vehicle`` instance.

        Raises:
            TypeError: If a component's type has no known SUAVE translation.
        """
        suave_vehicle = SUAVE.Vehicle()
        suave_vehicle.tag = vehicle.name

        for prop_name, prop_comp in vehicle.propulsion.items():
            network = self._translate_propulsion(prop_comp, tag=prop_name)
            suave_vehicle.append_component(network)

        for aero_name, aero_comp in vehicle.aero_surfaces.items():
            surface = self._translate_aero_surface(aero_comp, tag=aero_name)
            suave_vehicle.append_component(surface)

        for body_name, body_comp in vehicle.bodies.items():
            body = self._translate_body(body_comp, tag=body_name)
            suave_vehicle.append_component(body)

        if vehicle.mass_properties is not None:
            if vehicle.mass_properties.total_mass is not None:
                suave_vehicle.mass_properties.max_takeoff = vehicle.mass_properties.total_mass
                suave_vehicle.mass_properties.takeoff = vehicle.mass_properties.total_mass
            suave_vehicle.mass_properties.center_of_gravity = [
                [vehicle.mass_properties.cg_from_nose, 0.0, 0.0]
            ]

        return suave_vehicle

    def _translate_propulsion(self, component: AnyPropulsionComponent, tag: str) -> Any:
        """Translate a propulsion component into a SUAVE energy network.

        Args:
            component: A validated propulsion component schema instance.
            tag: Unique component identifier used as the SUAVE network tag.

        Returns:
            The assembled SUAVE energy network.

        Raises:
            TypeError: If the component type has no known translation.
        """
        if component.type not in self._PROPULSION_DISPATCH:
            raise TypeError(
                f"No SUAVE translation known for propulsion component type {component.type!r}"
            )
        return self._PROPULSION_DISPATCH[component.type](self, component, tag)

    def _translate_aero_surface(self, component: AnyAeroComponent, tag: str) -> Any:
        """Translate an aerodynamic surface into a SUAVE wing.

        Args:
            component: A validated aerodynamic component schema instance.
            tag: Unique component identifier used as the SUAVE wing tag.

        Returns:
            The assembled SUAVE wing.

        Raises:
            TypeError: If the component type has no known translation.
        """
        if component.type not in self._AERO_DISPATCH:
            raise TypeError(
                f"No SUAVE translation known for aero surface component type {component.type!r}"
            )
        return self._AERO_DISPATCH[component.type](self, component, tag)

    def _translate_body(self, component: AnyBodyComponent, tag: str) -> Any:
        """Translate a body component into a SUAVE fuselage.

        Args:
            component: A validated body component schema instance.
            tag: Unique component identifier used as the SUAVE fuselage tag.

        Returns:
            The assembled SUAVE fuselage.

        Raises:
            TypeError: If the component type has no known translation.
        """
        if component.type not in self._BODY_DISPATCH:
            raise TypeError(
                f"No SUAVE translation known for body component type {component.type!r}"
            )
        return self._BODY_DISPATCH[component.type](self, component, tag)

    def _translate_turbojet(self, component: Any, tag: str) -> Any:
        network = SUAVE.Components.Energy.Networks.Turbojet_Super()
        network.tag = tag
        network.thrust_N = component.thrust
        network.sfc_kg_per_Ns = component.sfc
        network.mach_range = component.mach_range
        if component.mass is not None and component.mass.total_mass is not None:
            network.mass_properties.mass = component.mass.total_mass
        return network

    def _translate_ramjet(self, component: Any, tag: str) -> Any:
        network = SUAVE.Components.Energy.Networks.Ramjet()
        network.tag = tag
        network.design_mach = component.design_mach
        network.combustor_temp_K = component.combustor_temp
        network.nozzle_area_ratio = component.nozzle_area_ratio
        if component.mass is not None and component.mass.total_mass is not None:
            network.mass_properties.mass = component.mass.total_mass
        return network

    def _translate_solid_motor(self, component: Any, tag: str) -> Any:
        network = SUAVE.Components.Energy.Networks.Network()
        network.tag = tag
        network.thrust_N = component.thrust_mean
        network.thrust_mean_N = component.thrust_mean
        network.thrust_peak_N = component.thrust_peak
        network.isp_s = component.isp_sl
        network.isp_vacuum_s = component.isp_vacuum
        network.burn_time_s = component.burn_time
        network.propellant_mass = component.propellant_mass
        if component.mass is not None and component.mass.total_mass is not None:
            network.mass_properties.mass = component.mass.total_mass
        return network

    def _translate_wing(self, component: Any, tag: str) -> Any:
        wing = SUAVE.Components.Wings.Wing()
        wing.tag = tag
        wing.aspect_ratio = component.aspect_ratio
        wing.sweeps.quarter_chord = math.radians(component.sweep)
        wing.taper = component.taper_ratio
        wing.spans.projected = component.span
        wing.dihedral = math.radians(component.dihedral)
        if component.mass is not None and component.mass.total_mass is not None:
            wing.mass_properties.mass = component.mass.total_mass
        return wing

    def _translate_fins(self, component: Any, tag: str) -> Any:
        wing = SUAVE.Components.Wings.Wing()
        wing.tag = tag
        wing.spans.projected = component.span
        wing.sweeps.leading_edge = math.radians(component.sweep)
        wing.vertical = True
        if component.chord_root is not None:
            wing.chords.root = component.chord_root
        if component.chord_tip is not None:
            wing.chords.tip = component.chord_tip
        if component.mass is not None and component.mass.total_mass is not None:
            wing.mass_properties.mass = component.mass.total_mass
        return wing

    def _translate_axisymmetric_body(self, component: Any, tag: str) -> Any:
        fuselage = SUAVE.Components.Fuselages.Fuselage()
        fuselage.tag = tag
        fuselage.lengths.total = component.length
        if component.nose_length is not None:
            fuselage.lengths.nose = component.nose_length
        fuselage.width = component.diameter
        fuselage.heights.maximum = component.diameter
        fuselage.effective_diameter = component.diameter
        if component.mass is not None:
            if component.mass.total_mass is not None:
                fuselage.mass_properties.mass = component.mass.total_mass
            fuselage.mass_properties.center_of_gravity = [
                [component.mass.cg_from_nose, 0.0, 0.0]
            ]
        return fuselage

    _PROPULSION_DISPATCH: ClassVar[dict[str, Callable[[VehicleFactory, Any, str], Any]]] = {
        "turbojet_engine": _translate_turbojet,
        "ramjet_engine": _translate_ramjet,
        "solid_motor": _translate_solid_motor,
    }

    _AERO_DISPATCH: ClassVar[dict[str, Callable[[VehicleFactory, Any, str], Any]]] = {
        "wing": _translate_wing,
        "fins": _translate_fins,
    }

    _BODY_DISPATCH: ClassVar[dict[str, Callable[[VehicleFactory, Any, str], Any]]] = {
        "axisymmetric_body": _translate_axisymmetric_body,
    }
