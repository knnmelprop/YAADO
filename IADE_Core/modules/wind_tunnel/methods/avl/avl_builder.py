# MELprop-IADE | analyses.aero.avl_builder | v0.1.0
"""AVL geometry-deck generation for the ramjet rocket fin set.

Generates an Athena Vortex Lattice (AVL) input deck from a validated
:class:`~src.schemas.vehicle_schema.RocketConfig` and runs AVL to extract
stability derivatives (CL_alpha, Cm_alpha, CN_beta, neutral point).

APPLICABILITY: AVL is a subsonic vortex-lattice method — valid only for
Mach < 0.6 and small angles (|alpha| < ~15 deg). It must NOT be used for
the supersonic cruise fins (Mach 2.5); use linearised supersonic theory
or SU2 CFD there. This deck is therefore intended for the low-speed boost
initiation / recovery envelope only.

AVL geometry-deck format (surface block template)::

    Ramjet-Missile
    #Mach
    0.0
    #IYsym IZsym Zsym
    0     0     0.0
    #Sref  Cref  Bref
    <A_ref> <c_ref> <b_ref>
    #Xref Yref Zref   (moment reference = CG)
    <Xcg> 0.0 0.0
    #
    SURFACE
    Fins
    #Nchord Cspace Nspan Sspace
    8 1.0 12 1.0
    ANGLE
    0.0
    SECTION
    #Xle Yle Zle Chord Ainc
    <x_fin> <r_body> 0.0 <c_root> 0.0
    SECTION
    <x_fin> <r_body+span> 0.0 <c_tip> 0.0

Theory reference:
    Drela, M. & Youngren, H., "AVL 3.xx User Primer", MIT (vortex-lattice
    method); Bertin & Cummings, "Aerodynamics for Engineers" (VLM theory).
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from IADE_Core.modules.wind_tunnel.methods.avl.avl_wrapper import helmbold_cl_alpha
from IADE_Core.Foundation.component_base import AnalysisResults, BaseAnalysis, FidelityLevel
from Hangar.ramjet_rocket.rocket_schema import RocketConfig

#: AVL applicability limits (same as avl_wrapper.py).
MAX_MACH = 0.6
MAX_ALPHA_DEG = 15.0


def avl_is_available() -> bool:
    """Return True if the ``avl`` executable is on ``PATH``."""
    return shutil.which("avl") is not None


def build_avl_deck(config: RocketConfig, mach: float = 0.0) -> str:
    """Assemble an AVL geometry deck string from a rocket config.

    Args:
        config: Validated two-stage rocket configuration.
        mach: Freestream Mach number for AVL compressibility (default 0.0).

    Returns:
        The AVL input-deck text (header + fin SURFACE block).

    Raises:
        ValueError: If required geometry fields are missing or non-physical.
    """
    if config.body.diameter_m <= 0.0:
        raise ValueError("body.diameter_m must be > 0")
    if config.fins.span_m <= 0.0:
        raise ValueError("fins.span_m must be > 0")

    d_ref = config.body.diameter_m
    a_ref = math.pi / 4.0 * d_ref**2
    r_body = d_ref / 2.0
    total_len = config.body.total_length_m or config.body.length_m
    x_cg = config.mass_properties.cg_from_nose_m if config.mass_properties else 0.0
    c_root = config.fins.chord_root_m or config.fins.span_m
    c_tip = config.fins.chord_tip_m or c_root
    x_fin = total_len - c_root  # fins at aft end (first-order)

    # Reference span: for cruciform fins, treat as a pair (2 fins).
    b_ref = 2.0 * config.fins.span_m

    deck = "\n".join(
        [
            config.name,
            "#Mach",
            f"{mach:.3f}",
            "#IYsym IZsym Zsym",
            "0 0 0.0",
            "#Sref Cref Bref",
            f"{a_ref:.5f} {c_root:.4f} {b_ref:.4f}",
            "#Xref Yref Zref",
            f"{x_cg:.4f} 0.0 0.0",
            "#",
            "SURFACE",
            "Fins",
            "8 1.0 12 1.0",
            "ANGLE",
            "0.0",
            "SECTION",
            f"#Xle Yle Zle Chord Ainc",
            f"{x_fin:.4f} {r_body:.4f} 0.0 {c_root:.4f} 0.0",
            "SECTION",
            f"{x_fin:.4f} {r_body + config.fins.span_m:.4f} 0.0 {c_tip:.4f} 0.0",
        ]
    )
    return deck


class AVLFinAnalysis(BaseAnalysis):
    """AVL stability analysis for the ramjet rocket fins (low-speed only).

    Valid only for Mach < 0.6 and |alpha| < 15 deg. Produces CL_alpha,
    Cm_alpha, and neutral point when AVL is available; otherwise falls
    back to an analytical VLM estimate (Helmbold) for the fin planform.

    Example:
        >>> analysis = AVLFinAnalysis()
        >>> analysis.setup(rocket_config, mach=0.3)
        >>> results = analysis.execute()
        >>> results["CL_alpha"]  # doctest: +SKIP
    """

    fidelity = FidelityLevel.LEVEL_1

    def __init__(self, name: str = "avl_fin_stability") -> None:
        super().__init__(name)
        self._config: RocketConfig | None = None
        self._mach = 0.0

    def setup(self, vehicle_config: RocketConfig, mach: float = 0.3) -> None:
        """Bind the analysis to a rocket config and flight condition.

        Args:
            vehicle_config: Validated rocket configuration with fins.
            mach: Freestream Mach number (must be < 0.6).

        Raises:
            ValueError: If Mach >= 0.6 (AVL applicability violated), or if
                the config has no fin definition.
        """
        if mach >= MAX_MACH:
            raise ValueError(
                f"Mach {mach} outside AVL applicability (Mach < {MAX_MACH}); "
                "use empirical supersonic correlations instead"
            )
        if getattr(vehicle_config, "fins", None) is None:
            raise ValueError("vehicle_config must define fins")
        self._config = vehicle_config
        self._mach = mach
        self._is_setup = True

    def execute(self) -> AnalysisResults:
        """Run AVL (if available) or analytical fallback, and return derivatives.

        Returns:
            AnalysisResults with ``CL_alpha`` [1/rad], ``Cm_alpha`` [1/rad],
            ``neutral_point_m`` [m from nose].

        Raises:
            RuntimeError: If called before :meth:`setup`.
        """
        if not self._is_setup or self._config is None:
            raise RuntimeError("AVLFinAnalysis.execute() called before setup()")

        if avl_is_available():
            method = "avl_subprocess"
            try:
                return self._execute_avl()
            except Exception as exc:
                # AVL run failed; fall back to analytical.
                method = f"analytical_helmbold (AVL failed: {exc})"
        else:
            method = "analytical_helmbold"

        return self._execute_analytical(method)

    def _execute_avl(self) -> AnalysisResults:
        """Drive AVL via subprocess and parse stability output."""
        assert self._config is not None
        deck_text = build_avl_deck(self._config, self._mach)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            avl_file = tmppath / "fins.avl"
            st_file = tmppath / "fins.st"

            avl_file.write_text(deck_text, encoding="utf-8")

            # AVL command script: load geometry, run ST (stability) analysis.
            commands = "\n".join(
                [
                    f"LOAD {avl_file}",
                    "OPER",
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

            # Parse ST output for CL_alpha, Cm_alpha, neutral point.
            st_text = st_file.read_text(encoding="utf-8")
            cl_alpha_match = re.search(r"CLa\s*=\s*([-+]?\d+\.\d+)", st_text)
            cm_alpha_match = re.search(r"Cma\s*=\s*([-+]?\d+\.\d+)", st_text)
            xnp_match = re.search(r"Xnp\s*=\s*([-+]?\d+\.\d+)", st_text)

            if not (cl_alpha_match and cm_alpha_match):
                raise RuntimeError("Could not parse CL_alpha/Cm_alpha from AVL ST output")

            cl_alpha = float(cl_alpha_match.group(1))
            cm_alpha = float(cm_alpha_match.group(1))
            neutral_point_m = float(xnp_match.group(1)) if xnp_match else 0.0

            return AnalysisResults(
                name=self.name,
                fidelity=self.fidelity,
                data={
                    "CL_alpha": cl_alpha,
                    "Cm_alpha": cm_alpha,
                    "neutral_point_m": neutral_point_m,
                },
                metadata={
                    "method": "avl_subprocess",
                    "mach": self._mach,
                    "avl_deck": deck_text,
                },
            )

    def _execute_analytical(self, method: str) -> AnalysisResults:
        """Analytical VLM estimate (Helmbold) for the fin planform."""
        assert self._config is not None
        fins = self._config.fins

        # Treat the fin pair as an isolated planar wing.
        span_pair = 2.0 * fins.span_m
        chord_avg = (fins.chord_root_m + fins.chord_tip_m) / 2.0 if fins.chord_tip_m else fins.chord_root_m
        area_pair = span_pair * chord_avg
        aspect_ratio = span_pair**2 / area_pair

        # Helmbold lift-curve slope (reuse from avl_wrapper).
        cl_alpha = helmbold_cl_alpha(aspect_ratio, fins.sweep_deg)

        # Apply Prandtl-Glauert for compressibility.
        if self._mach < 1.0:
            beta = math.sqrt(1.0 - self._mach**2)
            cl_alpha /= beta

        # Cm_alpha estimate: assume fins aft of CG, destabilizing.
        # x_ac ~ x_fin + 0.25 * chord (quarter-chord of fin).
        x_cg = self._config.mass_properties.cg_from_nose_m if self._config.mass_properties else 0.0
        total_len = self._config.body.total_length_m or self._config.body.length_m
        x_fin = total_len - (fins.chord_root_m or fins.span_m)
        x_ac_fin = x_fin + 0.25 * (fins.chord_root_m or fins.span_m)
        moment_arm_m = x_ac_fin - x_cg

        # Cm_alpha = CL_alpha * (x_ac - x_cg) / c_ref, c_ref = chord_root.
        c_ref = fins.chord_root_m or fins.span_m
        cm_alpha = cl_alpha * moment_arm_m / c_ref

        # Neutral point: x_NP ~ x_ac_fin (first-order).
        neutral_point_m = x_ac_fin

        return AnalysisResults(
            name=self.name,
            fidelity=self.fidelity,
            data={
                "CL_alpha": cl_alpha,
                "Cm_alpha": cm_alpha,
                "neutral_point_m": neutral_point_m,
            },
            metadata={
                "method": method,
                "mach": self._mach,
                "aspect_ratio": aspect_ratio,
                "moment_arm_m": moment_arm_m,
            },
        )
