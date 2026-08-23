"""Registry of external solvers (AVL, XFOIL, pyCycle, ...).

Central place to declare which external tools a workflow needs and to
check their availability before a run starts, instead of failing halfway
through an analysis.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass
class SolverInfo:
    """Metadata about an external solver.

    Attributes:
        name: Registry key, e.g. ``"avl"``.
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
        """Register a solver; overwrites any existing entry of same name."""
        self._solvers[info.name] = info

    def get(self, name: str) -> SolverInfo:
        """Return solver info.

        Raises:
            KeyError: If the solver is not registered.
        """
        if name not in self._solvers:
            raise KeyError(
                f"Solver {name!r} not registered; available: {sorted(self._solvers)}"
            )
        return self._solvers[name]

    def available(self) -> list[str]:
        """Return names of registered solvers usable in this environment."""
        return sorted(n for n, s in self._solvers.items() if s.is_available())


#: Default registry pre-populated with the solvers used by MELprop-IADE.
DEFAULT_REGISTRY = SolverRegistry()
DEFAULT_REGISTRY.register(SolverInfo("avl", "avl", "Athena Vortex Lattice (VLM)"))
DEFAULT_REGISTRY.register(SolverInfo("xfoil", "xfoil", "XFOIL 2-D airfoil analysis"))
DEFAULT_REGISTRY.register(
    SolverInfo("helmbold", "", "Analytical finite-wing lift-slope correlation")
)
