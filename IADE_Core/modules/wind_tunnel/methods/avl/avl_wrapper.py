# MELprop-IADE | analyses.aerodynamics.avl_wrapper | v0.1.0
"""AVL (Athena Vortex Lattice) wrapper for subsonic fixed-wing analysis.

Applicability limits (enforced in :meth:`AVLAnalysis.setup`): Mach < 0.6
and angle of attack < 15 degrees. When the ``avl`` executable is not on
``PATH``, the analysis falls back to analytical correlations: the
Helmbold equation for the finite-wing lift-curve slope and a parabolic
drag polar for induced drag.
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from IADE_Core.Foundation.component_base import AnalysisResults, BaseAnalysis, FidelityLevel
from Hangar.gtm140_drone.drone_schema import UAVConfig

#: AVL applicability limits (linear potential-flow method).
MAX_MACH = 0.6
MAX_ALPHA_DEG = 15.0

#: Oswald efficiency placeholder for the parabolic drag polar. TBD —
#: replace with an AVL-derived value once real geometry is fixed.
_OSWALD_E = 0.85

#: Zero-lift drag coefficient placeholder. TBD — from component buildup.
_CD0 = 0.025

#: Zero-lift pitching-moment placeholder for a cambered section (NACA 24xx).
_CM0 = -0.05


def helmbold_cl_alpha(aspect_ratio: float, sweep_deg: float = 0.0) -> float:
    """Finite-wing lift-curve slope from the Helmbold equation.

    ``a = 2*pi*AR / (2 + sqrt(AR^2/cos^2(sweep) + 4))`` with a simple
    sweep correction; valid for subsonic, moderate-AR wings.

    Args:
        aspect_ratio: Wing aspect ratio (> 0).
        sweep_deg: Quarter-chord sweep in degrees.

    Returns:
        Lift-curve slope in 1/rad.
    """
    ar = aspect_ratio
    cos_sweep = math.cos(math.radians(sweep_deg))
    return 2.0 * math.pi * ar / (2.0 + math.sqrt((ar / cos_sweep) ** 2 + 4.0))


def avl_is_available() -> bool:
    """Return True if the ``avl`` executable is on ``PATH``."""
    return shutil.which("avl") is not None


class AVLAnalysis(BaseAnalysis):
    """Subsonic wing aerodynamics via AVL, with analytical fallback.

    Produces ``CL``, ``CD``, ``CL_alpha`` (1/rad) and ``CM`` for a given
    UAV configuration and flight condition. Results are cross-checked
    against the reference slope ``2*pi/(1 + 2/AR)`` (± 20 %).

    Example:
        >>> analysis = AVLAnalysis()
        >>> analysis.setup(uav_config, mach=0.3, alpha_deg=4.0)
        >>> results = analysis.execute()
        >>> results["CL_alpha"]  # doctest: +SKIP
    """

    fidelity = FidelityLevel.LEVEL_1

    def __init__(self, name: str = "avl_wing_analysis") -> None:
        super().__init__(name)
        self._config: UAVConfig | None = None
        self._mach = 0.0
        self._alpha_deg = 0.0

    def setup(
        self,
        vehicle_config: UAVConfig,
        mach: float = 0.3,
        alpha_deg: float = 2.0,
    ) -> None:
        """Bind the analysis to a vehicle and flight condition.

        Args:
            vehicle_config: Validated UAV configuration with a wing.
            mach: Freestream Mach number (must be < 0.6).
            alpha_deg: Angle of attack in degrees (must be < 15).

        Raises:
            ValueError: If the flight condition violates AVL applicability
                limits (Mach >= 0.6 or alpha >= 15 deg), or the config has
                no wing definition.
        """
        if mach >= MAX_MACH:
            raise ValueError(
                f"Mach {mach} outside AVL applicability (Mach < {MAX_MACH}); "
                "use empirical supersonic correlations instead"
            )
        if abs(alpha_deg) >= MAX_ALPHA_DEG:
            raise ValueError(
                f"alpha {alpha_deg} deg outside AVL applicability "
                f"(|alpha| < {MAX_ALPHA_DEG} deg)"
            )
        if getattr(vehicle_config, "wing", None) is None:
            raise ValueError("vehicle_config must define a wing")
        self._config = vehicle_config
        self._mach = mach
        self._alpha_deg = alpha_deg
        self._is_setup = True

    def execute(self) -> AnalysisResults:
        """Run the analysis and return aerodynamic coefficients.

        Uses AVL when available; otherwise analytical correlations
        (Helmbold slope + parabolic drag polar), flagged in metadata.

        Returns:
            AnalysisResults with ``CL``, ``CD``, ``CL_alpha`` (1/rad)
            and ``CM``.

        Raises:
            RuntimeError: If called before :meth:`setup`, or if the
                results fail the analytical cross-check.
        """
        if not self._is_setup or self._config is None:
            raise RuntimeError("AVLAnalysis.execute() called before setup()")

        if avl_is_available():
            method = "avl_subprocess"
            try:
                results = self._execute_avl()
            except Exception as exc:
                # AVL run failed; fall back to analytical.
                method = f"analytical_helmbold (AVL failed: {exc})"
                results = self._execute_analytical(method)
        else:
            method = "analytical_helmbold"
            results = self._execute_analytical(method)

        if not self.validate_results(results):
            raise RuntimeError(
                f"CL_alpha={results['CL_alpha']:.3f} failed analytical "
                "cross-check (2*pi/(1 + 2/AR) +/- 20%)"
            )
        return results

    def _execute_avl(self) -> AnalysisResults:
        """Drive AVL via subprocess and parse stability output."""
        assert self._config is not None
        wing = self._config.wing

        # Build AVL geometry deck for the wing.
        deck_text = self._build_avl_wing_deck()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            avl_file = tmppath / "wing.avl"
            st_file = tmppath / "wing.st"

            avl_file.write_text(deck_text, encoding="utf-8")

            # AVL command script: load geometry, set alpha, run ST analysis.
            commands = "\n".join(
                [
                    f"LOAD {avl_file}",
                    "OPER",
                    f"A A {self._alpha_deg}",  # set alpha
                    "X",  # eXecute run
                    "ST",  # stability derivatives
                    f"{st_file}",
                    "",  # confirm
                    "",  # exit OPER
                    "QUIT",
                ]
            )

            proc = subprocess.run(
                ["avl"],
                input=commands,
                text=True,
                capture_output=True,
                cwd=tmppath,
                timeout=30,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"AVL failed: {proc.stderr}")

            if not st_file.exists():
                raise RuntimeError("AVL did not produce ST output file")

            # Parse ST output for CL, CD, CM, CL_alpha.
            st_text = st_file.read_text(encoding="utf-8")
            cl_match = re.search(r"CLtot\s*=\s*([-+]?\d+\.\d+)", st_text)
            cd_match = re.search(r"CDtot\s*=\s*([-+]?\d+\.\d+)", st_text)
            cm_match = re.search(r"Cmtot\s*=\s*([-+]?\d+\.\d+)", st_text)
            cl_alpha_match = re.search(r"CLa\s*=\s*([-+]?\d+\.\d+)", st_text)

            if not (cl_match and cl_alpha_match):
                raise RuntimeError("Could not parse CL/CL_alpha from AVL ST output")

            cl = float(cl_match.group(1))
            cd = float(cd_match.group(1)) if cd_match else _CD0
            cm = float(cm_match.group(1)) if cm_match else _CM0
            cl_alpha = float(cl_alpha_match.group(1))

            return AnalysisResults(
                name=self.name,
                fidelity=self.fidelity,
                data={"CL": cl, "CD": cd, "CL_alpha": cl_alpha, "CM": cm},
                metadata={
                    "method": "avl_subprocess",
                    "mach": self._mach,
                    "alpha_deg": self._alpha_deg,
                    "aspect_ratio": wing.aspect_ratio,
                },
            )

    def _build_avl_wing_deck(self) -> str:
        """Build AVL geometry deck for the GTM-140 wing."""
        assert self._config is not None
        wing = self._config.wing

        # Reference area and dimensions.
        s_ref = wing.span_m**2 / wing.aspect_ratio
        c_ref = s_ref / wing.span_m  # mean aerodynamic chord
        b_ref = wing.span_m

        # Wing planform geometry (simplified: single trapezoidal panel).
        c_root = c_ref * 2.0 / (1.0 + wing.taper_ratio)
        c_tip = c_root * wing.taper_ratio
        sweep_rad = math.radians(wing.sweep_deg)
        x_le_tip = c_root * 0.25 + (wing.span_m / 2.0) * math.tan(sweep_rad) - c_tip * 0.25

        deck = "\n".join(
            [
                self._config.name,
                "#Mach",
                f"{self._mach:.3f}",
                "#IYsym IZsym Zsym",
                "0 0 0.0",
                "#Sref Cref Bref",
                f"{s_ref:.5f} {c_ref:.4f} {b_ref:.4f}",
                "#Xref Yref Zref",
                "0.0 0.0 0.0",
                "#",
                "SURFACE",
                "Wing",
                "#Nchord Cspace Nspan Sspace",
                "10 1.0 20 1.0",
                "YDUPLICATE",
                "0.0",
                "ANGLE",
                "0.0",
                "SECTION",
                "#Xle Yle Zle Chord Ainc Nspan Sspace",
                f"0.0 0.0 0.0 {c_root:.4f} 0.0",
                f"AIRFOIL {wing.airfoil_root}",
                "SECTION",
                f"{x_le_tip:.4f} {wing.span_m / 2.0:.4f} 0.0 {c_tip:.4f} 0.0",
                f"AIRFOIL {wing.airfoil_tip}",
            ]
        )
        return deck

    def _execute_analytical(self, method: str) -> AnalysisResults:
        """Compute coefficients from Helmbold slope + parabolic polar."""
        assert self._config is not None
        wing = self._config.wing
        ar = wing.aspect_ratio

        # Prandtl-Glauert compressibility correction on the section slope.
        beta = math.sqrt(1.0 - self._mach**2)
        cl_alpha = helmbold_cl_alpha(ar, wing.sweep_deg) / beta

        alpha_rad = math.radians(self._alpha_deg)
        cl = cl_alpha * alpha_rad
        cd = _CD0 + cl**2 / (math.pi * ar * _OSWALD_E)
        cm = _CM0

        return AnalysisResults(
            name=self.name,
            fidelity=self.fidelity,
            data={"CL": cl, "CD": cd, "CL_alpha": cl_alpha, "CM": cm},
            metadata={
                "method": method,
                "mach": self._mach,
                "alpha_deg": self._alpha_deg,
                "aspect_ratio": ar,
            },
        )

    def validate_results(self, results: AnalysisResults) -> bool:
        """Check CL_alpha against the reference slope ``2*pi/(1 + 2/AR)``.

        Args:
            results: Results to validate; must contain ``CL_alpha``.

        Returns:
            True if CL_alpha lies within ± 20 % of the reference value.
        """
        if self._config is None or "CL_alpha" not in results:
            return False
        ar = self._config.wing.aspect_ratio
        reference = 2.0 * math.pi / (1.0 + 2.0 / ar)
        return 0.8 * reference <= results["CL_alpha"] <= 1.2 * reference
