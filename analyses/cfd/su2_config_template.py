# MELprop-IADE | analyses.cfd.su2_config_template | v0.1.0
"""SU2 external-aerodynamics configuration-template stub.

Generates SU2 ``.cfg`` files for an inviscid/RANS Mach sweep of the
ramjet rocket to extract CL/CD across the transonic–supersonic envelope,
complementing the low-order Barrowman (stability) and DATCOM-style drag
estimates used elsewhere in the project.

Workflow (to be implemented):
    1. Mesh generation with gmsh from the axisymmetric body + fins.
    2. SU2_CFD run per Mach number (Euler first, then RANS/SA).
    3. Force-coefficient extraction (CL, CD, Cm) from the SU2 history.

Theory / tooling reference:
    Economon, T. D. et al., "SU2: An Open-Source Suite for Multiphysics
    Simulation and Design", AIAA Journal 54(3), 2016.

TODO:
    * gmsh geometry + boundary-layer mesh generation.
    * Per-Mach farfield boundary conditions (ISA at design altitude).
    * Launch SU2_CFD, monitor convergence, parse forces.
    * Aggregate CL(M), CD(M) into a drag-polar table for trajectory use.
"""

from __future__ import annotations

#: Mach numbers swept for the external-aero study.
MACH_SWEEP: tuple[float, ...] = (0.8, 1.2, 1.5, 2.0, 2.5, 3.0)

#: SU2 config keys common to every Mach case (template defaults).
_BASE_CONFIG: dict[str, str] = {
    "SOLVER": "EULER",
    "MATH_PROBLEM": "DIRECT",
    "REF_DIMENSIONALIZATION": "DIMENSIONAL",
    "MARKER_EULER": "( airframe )",
    "MARKER_FAR": "( farfield )",
    "CONV_NUM_METHOD_FLOW": "JST",
    "ITER": "5000",
}


def build_su2_config(mach: float, aoa_deg: float = 0.0) -> str:
    """Render an SU2 ``.cfg`` text for one Mach/AoA case.

    Args:
        mach: Freestream Mach number.
        aoa_deg: Angle of attack in degrees.

    Returns:
        SU2 configuration file contents as a string.

    Note:
        Stub: farfield pressure/temperature and reference area/length are
        placeholders and MUST be set from the vehicle config and ISA
        conditions before use (see module ``TODO``).
    """
    lines = [f"% SU2 case  Mach={mach}  AoA={aoa_deg} deg  (MELprop ramP)"]
    lines += [f"{k}= {v}" for k, v in _BASE_CONFIG.items()]
    lines += [
        f"MACH_NUMBER= {mach}",
        f"AOA= {aoa_deg}",
        "FREESTREAM_PRESSURE= 26500   % TODO: ISA at design altitude [Pa]",
        "FREESTREAM_TEMPERATURE= 223.3 % TODO: ISA at design altitude [K]",
        "REF_AREA= 0.04909            % pi/4 * 0.250^2 [m^2]",
        "REF_LENGTH= 0.250            % d_ref [m]",
        "MESH_FILENAME= ramp_airframe.su2  % TODO: gmsh output",
    ]
    return "\n".join(lines)


def build_mach_sweep() -> dict[float, str]:
    """Build SU2 configs for every Mach in :data:`MACH_SWEEP`.

    Returns:
        Mapping of Mach number to its SU2 ``.cfg`` text.
    """
    return {mach: build_su2_config(mach) for mach in MACH_SWEEP}
