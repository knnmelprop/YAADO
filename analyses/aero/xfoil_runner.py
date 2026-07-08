# MELprop-IADE | analyses.aero.xfoil_runner | v0.1.0
"""XFOIL batch-run stub for the stabilizer fin airfoil.

The MELprop ramjet rocket uses rectangular steel fins with a maximum
thickness of 30 mm over a 176.8 mm chord (t/c ~ 0.17). At the cruise
design point the fins operate at Mach 2.5, where a sharp double-wedge
(diamond) section is preferred to minimise wave drag. XFOIL is a
low-speed (incompressible/weakly-compressible) panel + boundary-layer
code and is therefore only valid for the *subsonic* portions of the
flight envelope (boost initiation, recovery); the supersonic fin loads
must come from linearised supersonic theory or CFD (see
``analyses/cfd/su2_config_template.py``).

Theory reference:
    Ames Research Staff, "Equations, Tables, and Charts for Compressible
    Flow", NACA Report 1135 (1953) — supersonic wave-drag of thin
    sections. Drela, M., "XFOIL: An Analysis and Design System for Low
    Reynolds Number Airfoils", NACA TN 1428-style low-Re methodology.

TODO:
    * Locate/validate the ``xfoil`` binary (see core.solver_registry).
    * Emit an XFOIL command deck (double-wedge coordinates, Re/Mach sweep).
    * Drive XFOIL via subprocess with a batch command file.
    * Parse the polar output (CL, CD, CM vs alpha) into AnalysisResults.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.component_base import AnalysisResults, BaseAnalysis, FidelityLevel

#: Fin section geometry (Fusion Assembly v6).
FIN_CHORD_M = 0.1768
FIN_THICKNESS_MAX_M = 0.030
FIN_DESIGN_MACH = 2.5


@dataclass
class XfoilCase:
    """Single XFOIL run specification.

    Attributes:
        reynolds: Chord Reynolds number.
        mach: Freestream Mach number (XFOIL valid only for M < ~0.7).
        alpha_deg_range: (start, stop, step) angle-of-attack sweep [deg].
    """

    reynolds: float
    mach: float
    alpha_deg_range: tuple[float, float, float] = (-6.0, 12.0, 1.0)
    extra_commands: list[str] = field(default_factory=list)


class XfoilRunner(BaseAnalysis):
    """Stub XFOIL driver for the fin airfoil polar.

    Inherits the MELprop analysis contract; the actual XFOIL integration
    is not yet implemented (see module ``TODO``).
    """

    fidelity = FidelityLevel.LEVEL_1

    def __init__(self, name: str = "xfoil_fin_polar") -> None:
        super().__init__(name)
        self._case: XfoilCase | None = None

    def setup(self, case: XfoilCase) -> None:
        """Bind a run case.

        Args:
            case: XFOIL case specification.

        Raises:
            NotImplementedError: XFOIL invocation is not implemented yet.
        """
        self._case = case
        self._is_setup = True

    def execute(self) -> AnalysisResults:
        """Run XFOIL and return the polar.

        Raises:
            NotImplementedError: Always, until the binary integration and
                polar parser are implemented.
        """
        raise NotImplementedError(
            "XfoilRunner.execute is a stub; implement subprocess call to the "
            "xfoil binary and polar parsing (see module TODO)."
        )
