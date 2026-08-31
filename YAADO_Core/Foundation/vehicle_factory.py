"""Factory translating YAADO vehicle configs into SUAVE vehicles.

SUAVE lives in ``external/suave`` (git submodule, pinned tag 2.5.2 — see
docs/EXTERNAL_TOOLS.md) and may not be installed in every environment, so
the import is guarded — the factory raises a clear error only when SUAVE
is actually needed.

The factory works on the generic :class:`~YAADO_Core.Foundation.vehicle_base.BaseVehicleConfig`
composition (dictionaries of ``propulsion``, ``aero_surfaces`` and ``bodies``
components) rather than a per-project ``vehicle_type`` discriminator: each
component is translated to a SUAVE object based on its own ``type``/class and
appended to the SUAVE vehicle being assembled.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

from YAADO_Core.ComponentStore import Fins, RamjetEngine, SolidMotor, TurbojetEngine, Wings
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig

try:
    import SUAVE as _SUAVE  # type: ignore[import-not-found]

    SUAVE_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    _SUAVE = None
    SUAVE_AVAILABLE = False


class VehicleFactory:
    """Builds SUAVE ``Vehicle`` objects from validated :class:`BaseVehicleConfig` instances.

    Rather than dispatching on a removed ``vehicle_type`` discriminator, the
    factory iterates over the generic composition dictionaries exposed by
    :class:`BaseVehicleConfig` (``propulsion``, ``aero_surfaces``) and
    translates each component to its SUAVE counterpart based on the
    component's own type, appending it to a freshly created SUAVE vehicle.

    Attributes:
        suave: The SUAVE module used to build vehicles. Injectable for
            testing environments where the real SUAVE package is not
            installed; defaults to the globally imported ``SUAVE`` module
            when available.
    """

    def __init__(self, suave_module: ModuleType | Any | None = None) -> None:
        """Initialize the factory.

        Args:
            suave_module: SUAVE module (or a compatible stand-in exposing
                ``Vehicle``, ``Components.Energy.Networks`` and
                ``Components.Wings.Wing``) to build vehicles with. If
                ``None``, the real ``SUAVE`` module is used when it was
                importable at module load time, otherwise ``build`` raises
                ``RuntimeError``.
        """
        self.suave: ModuleType | Any | None = suave_module if suave_module is not None else _SUAVE

    def build(self, vehicle: BaseVehicleConfig) -> Any:
        """Build a SUAVE vehicle from a validated :class:`BaseVehicleConfig`.

        Args:
            vehicle: A validated, vehicle-agnostic configuration exposing
                ``propulsion`` and ``aero_surfaces`` component dictionaries.

        Returns:
            The assembled SUAVE ``Vehicle`` instance.

        Raises:
            RuntimeError: If no SUAVE module (real or injected) is available.
            TypeError: If a component's type has no known SUAVE translation.
        """
        if self.suave is None:
            raise RuntimeError(
                "SUAVE is not importable; run `git submodule update --init` "
                "and add external/suave/trunk to PYTHONPATH, or `pip install "
                "-e external/suave/trunk`"
            )

        suave_vehicle = self.suave.Vehicle()
        suave_vehicle.tag = vehicle.name

        for component in vehicle.propulsion.values():
            network = self._translate_propulsion(component)
            suave_vehicle.append_component(network)

        for component in vehicle.aero_surfaces.values():
            surface = self._translate_aero_surface(component)
            suave_vehicle.append_component(surface)

        return suave_vehicle

    def _translate_propulsion(self, component: Any) -> Any:
        """Translate a propulsion component into a SUAVE energy network.

        Args:
            component: One of ``SolidMotor``, ``RamjetEngine`` or
                ``TurbojetEngine``.

        Returns:
            A SUAVE ``Components.Energy.Networks`` instance carrying the
            component's key performance parameters.

        Raises:
            TypeError: If the component's type is not a supported
                propulsion component.
            NotImplementedError: If the component is a ``SolidMotor``.
                SUAVE 2.5.2 does not ship an energy network for solid-
                propellant motors (available high-speed/rocket networks:
                ``Liquid_Rocket``, ``Ramjet``, ``Scramjet``); translating
                ``SolidMotor`` is a pending follow-up.
        """
        networks = self.suave.Components.Energy.Networks

        if isinstance(component, SolidMotor):
            raise NotImplementedError(
                "SUAVE 2.5.2 ships no energy network for solid-propellant "
                "motors (available high-speed/rocket networks: Liquid_Rocket, "
                "Ramjet, Scramjet); SolidMotor translation is a pending "
                "follow-up."
            )

        if isinstance(component, RamjetEngine):
            network = networks.Ramjet()
            network.tag = component.type
            network.design_mach = component.design_mach
            network.combustor_temp_K = component.combustor_temp_K
            network.nozzle_area_ratio = component.nozzle_area_ratio
            return network

        if isinstance(component, TurbojetEngine):
            network = networks.Turbojet_Super()
            network.tag = component.name
            network.thrust_N = component.thrust_N
            network.sfc_kg_per_Ns = component.sfc_kg_per_Ns
            network.mach_range = component.mach_range
            return network

        raise TypeError(f"No SUAVE translation known for propulsion component type {type(component)!r}")

    def _translate_aero_surface(self, component: Any) -> Any:
        """Translate an aerodynamic surface component into a SUAVE wing.

        Args:
            component: One of ``Wings`` or ``Fins``.

        Returns:
            A SUAVE ``Components.Wings.Wing`` instance carrying the
            component's geometric parameters.

        Raises:
            TypeError: If the component's type is not a supported
                aerodynamic surface component.
        """
        Wing = self.suave.Components.Wings.Wing

        if isinstance(component, Wings):
            wing = Wing()
            wing.tag = component.type
            wing.aspect_ratio = component.aspect_ratio
            wing.sweeps.quarter_chord = component.sweep_deg
            wing.taper = component.taper_ratio
            wing.spans.projected = component.span_m
            wing.dihedral = component.dihedral_deg
            return wing

        if isinstance(component, Fins):
            wing = Wing()
            wing.tag = component.type
            wing.spans.projected = component.span_m
            wing.sweeps.leading_edge = component.sweep_deg
            wing.vertical = True
            return wing

        raise TypeError(f"No SUAVE translation known for aero surface component type {type(component)!r}")
