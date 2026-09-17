"""Registry of external solvers (AVL, XFOIL, pyCycle, ...).

Central place to declare which external tools a workflow needs and to
check their availability before a run starts, instead of failing halfway
through an analysis.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class SolverInfo:
    """Metadata about an external solver.

    Attributes:
        name: Registry key.
        executable: Executable name looked up on ``PATH`` (empty for
            pure-Python solvers).
        description: One-line human description.
    """

    name: str
    executable: str = ""
    description: str = ""

    def is_available(self) -> bool:
        """Return True if the solver can be used in this environment."""
        if not self.executable:
            return True
        return shutil.which(self.executable) is not None


class SolverRegistry:
    """Registry mapping solver names to :class:`SolverInfo`."""

    def __init__(self) -> None:
        self._solvers: dict[str, SolverInfo] = {}

    def register(self, info: SolverInfo) -> None:
        """Register a solver; overwrites any existing entry of same name.

        Args:
            info: Solver metadata to register.
        """
        self._solvers[info.name] = info

    def is_registered(self, name: str) -> bool:
        """Return True if a solver with the given name is registered.

        Args:
            name: Solver identifier to query.

        Returns:
            True if registered, False otherwise.
        """
        return name in self._solvers

    def get(self, name: str) -> SolverInfo:
        """Return solver info.

        Args:
            name: Identifier of the registered solver.

        Returns:
            The resolved SolverInfo instance.

        Raises:
            KeyError: If the solver is not registered.
        """
        if name not in self._solvers:
            available = sorted(self._solvers.keys())
            raise KeyError(
                f"Solver {name!r} not registered; available: {available}"
            )
        return self._solvers[name]

    def available(self) -> list[str]:
        """Return names of registered solvers usable in this environment."""
        return sorted(n for n, s in self._solvers.items() if s.is_available())

    def all_solvers(self) -> list[str]:
        """Return names of all registered solvers."""
        return sorted(self._solvers.keys())


#: Default global registry instance (initially empty; solvers register upon verification).
DEFAULT_REGISTRY = SolverRegistry()
