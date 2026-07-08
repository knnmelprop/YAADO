# MELprop-IADE | analyses.aero.avl_builder | v0.1.0
"""AVL geometry-deck generation stub for the ramjet rocket fin set.

Generates an Athena Vortex Lattice (AVL) input deck from a validated
:class:`~src.schemas.vehicle_schema.RocketConfig` and (once implemented)
runs AVL to extract stability derivatives (CL_alpha, Cm_alpha, CN_beta,
neutral point).

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

TODO:
    * Map RocketConfig fins/body geometry into the SURFACE/SECTION blocks.
    * Write the .avl deck and a .run mass/case file.
    * Invoke AVL via subprocess; parse the ST (stability) output.
    * Return CL_alpha, Cm_alpha, neutral point in AnalysisResults.
"""

from __future__ import annotations

import math

from src.schemas.vehicle_schema import RocketConfig


def build_avl_deck(config: RocketConfig) -> str:
    """Assemble an AVL geometry deck string from a rocket config.

    Args:
        config: Validated two-stage rocket configuration.

    Returns:
        The AVL input-deck text (header + fin SURFACE block).

    Note:
        This is a stub that lays out the deck skeleton; the SECTION
        coordinates use first-order estimates and MUST be verified before
        any AVL run (see module ``TODO``).
    """
    d_ref = config.body.diameter_m
    a_ref = math.pi / 4.0 * d_ref**2
    r_body = d_ref / 2.0
    total_len = config.body.total_length_m or config.body.length_m
    x_cg = config.mass_properties.cg_from_nose_m if config.mass_properties else 0.0
    c_root = config.fins.chord_root_m or config.fins.span_m
    c_tip = config.fins.chord_tip_m or c_root
    x_fin = total_len - c_root  # fins at aft end (first-order)

    return "\n".join(
        [
            config.name,
            "#Mach",
            "0.0",
            "#IYsym IZsym Zsym",
            "0 0 0.0",
            "#Sref Cref Bref",
            f"{a_ref:.5f} {c_root:.4f} {2 * config.fins.span_m:.4f}",
            "#Xref Yref Zref",
            f"{x_cg:.4f} 0.0 0.0",
            "#",
            "SURFACE",
            "Fins",
            "8 1.0 12 1.0",
            "ANGLE",
            "0.0",
            "SECTION",
            f"{x_fin:.4f} {r_body:.4f} 0.0 {c_root:.4f} 0.0",
            "SECTION",
            f"{x_fin:.4f} {r_body + config.fins.span_m:.4f} 0.0 {c_tip:.4f} 0.0",
            "# TODO: verify station coordinates, add body/nose, run AVL",
        ]
    )
