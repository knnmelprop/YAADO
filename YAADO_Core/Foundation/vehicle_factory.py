"""Factory translating YAADO vehicle configs into SUAVE vehicles.

SUAVE lives in ``external/suave`` (git submodule, pinned tag 2.5.2 — see
docs/EXTERNAL_TOOLS.md) and may not be installed in every environment, so
the import is guarded — the factory raises a clear error only when SUAVE
is actually needed.
"""

from __future__ import annotations

from typing import Any

try:
    import YAADO_Core.modules.suave_compat  # Apply modern Python shims first
    import SUAVE  # type: ignore[import-not-found]

    SUAVE_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    SUAVE = None
    SUAVE_AVAILABLE = False


class VehicleFactory:
    """Builds SUAVE ``Vehicle`` objects from validated vehicle configs.

    Builder functions are registered per ``vehicle_type`` (``"UAV"``,
    ``"Rocket"``) so each project can plug in its own SUAVE setup without
    modifying core code.
    """

    def __init__(self) -> None:
        self._builders: dict[str, Any] = {}

    def register_builder(self, vehicle_type: str, builder: Any) -> None:
        """Register a callable ``builder(config) -> SUAVE.Vehicle``.

        Args:
            vehicle_type: Config discriminator, e.g. ``"UAV"`` or ``"Rocket"``.
            builder: Callable receiving a validated config object.
        """
        self._builders[vehicle_type] = builder

    def build(self, config: Any) -> Any:
        """Build a SUAVE vehicle from a validated config.

        Args:
            config: A config object exposing a ``vehicle_type`` attribute
                (see ``src.schemas.vehicle_schema``).

        Returns:
            The SUAVE vehicle produced by the registered builder.

        Raises:
            RuntimeError: If SUAVE is not importable.
            KeyError: If no builder is registered for the vehicle type.
        """
        if not SUAVE_AVAILABLE:
            raise RuntimeError(
                "SUAVE is not importable; run `git submodule update --init` "
                "and add external/suave/trunk to PYTHONPATH, or `pip install "
                "-e external/suave/trunk`"
            )
        vehicle_type = getattr(config, "vehicle_type", None)
        if vehicle_type not in self._builders:
            raise KeyError(
                f"No builder registered for vehicle_type={vehicle_type!r}; "
                f"available: {sorted(self._builders)}"
            )
        return self._builders[vehicle_type](config)
