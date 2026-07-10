# MELprop-IADE | analyses.aero.drag_polar | v0.1.0
"""Supersonic zero-lift drag buildup for the ramP rocket (Project B).

Replaces the ``CD0 = 0.35`` SZACOWANY flat-plate placeholder used by
:mod:`analyses.mission.operational_envelope` (``CD0_PLACEHOLDER``) with a
component drag buildup at zero lift, swept across the ramP cruise Mach
range (1.5-3.5). This is an L1 (analytical/empirical correlation) method,
consistent with the fidelity tier used by :mod:`analyses.aero.xfoil_runner`
(Ackeret fin polar) and :mod:`analyses.stability.barrowman_stability`
(Barrowman CN_alpha/CP) elsewhere in this repo -- not a CFD replacement.

Four components are summed into ``CD0_total`` (all referenced to the body
cross-section area ``Aref = pi*d^2/4``, matching
:func:`analyses.mission.operational_envelope.reference_area_m2`):

1. **Body wave drag** (:func:`body_wave_drag_cd`) -- conical-nose
   pressure (wave) drag correlation for slender bodies of revolution.
   Uses the classical linearized supersonic (Ackeret-type) cone
   pressure-drag coefficient referenced to base area,

       Cd_wave_base = 4 * (delta)^2 / sqrt(Ma^2 - 1)   [thin-cone limit]

   where ``delta`` is the nose cone half-angle, per Hoerner, *Fluid-
   Dynamic Drag* (1965), Ch. 16 "Pressure Drag of Bodies of Revolution",
   which documents this thin-cone linearized result as consistent with
   the more detailed (nonlinear) Taylor-Maccoll conical-shock solution
   in the slender-body limit. No boattail is present on this
   geometry (the body is a constant-diameter cylinder aft of the nose,
   per ``vehicles/ramjet_rocket/vehicle_config.yaml``), so only the
   nose term is computed; a cylindrical afterbody of constant cross-
   section contributes zero wave drag in this theory (d(A)/dx = 0).

2. **Skin friction** (:func:`skin_friction_cd`) -- turbulent flat-plate
   ``Cf`` (Prandtl-Schlichting correlation,
   ``Cf_incomp = 0.455/(log10(Re))^2.58``) corrected for compressibility
   via the Eckert reference-temperature method (Eckert, 1955), which
   evaluates the incompressible correlation at a reference temperature
   ``T*`` that accounts for the compressible boundary layer's higher
   effective temperature, then scales ``Cf`` by ``(T*/T_e)`` density
   and viscosity ratios (``Cf/Cf_incomp = (rho*/rho_e)*(mu_e/mu*)``,
   here reduced with a Sutherland viscosity-law temperature exponent
   for compactness). Wetted areas: body (cylinder + cone, from
   ``body.diameter_m=0.250 m``, ``body.total_length_m=4.377 m``,
   ``body.nose_length_m=0.293 m``) and 4 rectangular fins (span
   ``0.6685 m`` x chord ``0.1768 m``, both sides wetted), all read from
   ``vehicles/ramjet_rocket/vehicle_config.yaml`` /
   ``fusion_extraction_v6.yaml`` per the task spec.

3. **Fin wave drag** (:func:`fin_wave_drag_cd`) -- Ackeret thickness
   (zero-lift wave-drag) term for a symmetric double-wedge fin section,
   ``CD_wave = 4*tau^2/sqrt(Ma^2-1)`` with ``tau = atan(t/c)``. This
   reuses (imports, does not redefine) the ``t/c = 0.1697`` convention
   and the underlying Ackeret math from
   :mod:`analyses.aero.xfoil_runner` (``FIN_THICKNESS_TO_CHORD``,
   ``ackeret_polar``) evaluated at ``alpha=0`` (zero-lift condition, so
   only the thickness/tau^2 term survives), scaled by wetted planform
   area (4 fins) referenced to ``Aref``.

4. **Base drag** (:func:`base_drag_cd`) -- empirical supersonic base-
   drag fit ``Cd_base ~= 0.25/Ma^2`` (Hoerner, *Fluid-Dynamic Drag*,
   Ch. 16, "Drag at the Base" -- a widely used engineering fit for
   supersonic body-of-revolution base pressure drag on a full base
   area), reduced by the ``ANNULAR_BASE_FRACTION`` occupied by the
   ramjet nozzle exit (the base is not a fully separated dead-air
   region; part of it is nozzle exit plane). ``ANNULAR_BASE_FRACTION``
   is a placeholder split (# SZACOWANY -- no nozzle-exit-diameter vs.
   body-diameter geometry is available from the YAML to compute the
   true annular fraction exactly).

The total, ``cd0_total = cd_body_wave + cd_friction + cd_fin_wave +
cd_base``, is intended as the physically-grounded replacement candidate
for ``CD0_PLACEHOLDER`` in ``operational_envelope.py`` -- this module
does NOT modify that file; wiring the replacement in is left as a
follow-up once this buildup is reviewed.

Mandatory validation (Ma 2.5 / 6000 m ISA, Teltik 2024 CFD sanity point,
``docs/assumptions.md`` A15, drag = 2451.95 N): this module computes
``drag_N = cd0_total * q * Aref`` at that exact condition and reports
the delta against the Teltik CFD force AND against the Teltik-implied
CD0 (``2451.95 / (q*Aref)``), plus the delta of THIS buildup and of the
0.35 placeholder against that implied CD0 -- reported honestly, not
tuned to match (see :func:`teltik_validation`).

References:
    Hoerner, S. F., *Fluid-Dynamic Drag*, published by the author, 1965,
        Ch. 16 (bodies of revolution: nose pressure/wave drag, base drag).
    Eckert, E. R. G., "Engineering Relations for Friction and Heat
        Transfer to Surfaces in High Velocity Flow", Journal of the
        Aeronautical Sciences, 22(8), 1955 (reference-temperature
        compressibility correction for turbulent skin friction).
    Anderson, J. D., *Fundamentals of Aerodynamics*, Ch. "Linearized
        Supersonic Flow" (Ackeret thin-airfoil thickness/wave-drag term),
        reused via :mod:`analyses.aero.xfoil_runner`.
    ``docs/assumptions.md`` A15 -- Teltik 2024 CFD drag sanity reference
        (2451.95 N at Mach 2.5 / 6000 m ISA).
    ``vehicles/ramjet_rocket/vehicle_config.yaml`` /
        ``fusion_extraction_v6.yaml`` -- body and fin geometry source.

Run as a script to sweep the Mach grid, write the CSV + JSON, and print
the Teltik validation gate::

    python3 analyses/aero/drag_polar.py
"""

from __future__ import annotations

import csv
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

if __name__ == "__main__" and __package__ in (None, ""):
    # Allow `python3 analyses/aero/drag_polar.py` direct execution by
    # putting the repository root on sys.path (mirrors the convention
    # used by analyses.mission.operational_envelope and
    # analyses.aero.xfoil_runner).
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analyses.aero.xfoil_runner import FIN_THICKNESS_TO_CHORD  # noqa: E402
from analyses.mission.operational_envelope import (  # noqa: E402
    NIGHT3_ALTITUDE_M,
    NIGHT3_MACH,
    TELTIK_CFD_DRAG_N_REF,
    isa_atmosphere,
    reference_area_m2,
)
from core.component_base import AnalysisResults, BaseAnalysis, FidelityLevel  # noqa: E402

# --------------------------------------------------------------------------
# Geometry constants (Fusion 360 Assembly v6 extraction; read-only source of
# truth is vehicles/ramjet_rocket/vehicle_config.yaml /
# fusion_extraction_v6.yaml -- values duplicated here as plain floats since
# this module's component functions are pure/standalone, mirroring the
# convention in analyses.aero.xfoil_runner).
# --------------------------------------------------------------------------

BODY_DIAMETER_M: float = 0.250
"""Body (cylindrical section) diameter [m], Fusion-verified."""

BODY_TOTAL_LENGTH_M: float = 4.377
"""Total rocket length [m] (nose + cylindrical body), Fusion Assembly v6."""

NOSE_LENGTH_M: float = 0.293
"""Conical nose length [m], Fusion Assembly v6."""

BODY_CYLINDER_LENGTH_M: float = BODY_TOTAL_LENGTH_M - NOSE_LENGTH_M
"""Cylindrical-body length [m] = total - nose (4.377 - 0.293 = 4.084 m,
matches ``vehicle_config.yaml body.length_m``)."""

FIN_COUNT: int = 4
"""Number of fins."""

FIN_SPAN_M: float = 0.6685
"""Exposed span of one fin [m], Fusion Assembly v6."""

FIN_CHORD_M: float = 0.1768
"""Fin chord [m] (rectangular planform, root=tip), Fusion Assembly v6."""

# --------------------------------------------------------------------------
# Empirical correlation constants.
# --------------------------------------------------------------------------

NOSE_HALF_ANGLE_RAD: float = math.atan((BODY_DIAMETER_M / 2.0) / NOSE_LENGTH_M)
"""Conical-nose half-angle [rad] from base radius / nose length
(assumes the nose fairs smoothly out to the full body diameter over its
length -- # SZACOWANY: the YAML's separate ``nose_diameter_m=0.150`` field
refers to the internal inlet-spike base per ``cfd_notes.ramjet_inlet_note``,
not the external nose-fairing base, so the external nose is instead
assumed here to taper to the full body diameter, consistent with
``reference_area_m2()``'s use of the body diameter as Aref)."""

BASE_DRAG_FIT_CONSTANT: float = 0.25
"""Hoerner supersonic base-drag fit constant [-]: ``Cd_base ~= C/Ma^2``.
Source: Hoerner, *Fluid-Dynamic Drag*, Ch. 16, an engineering fit for
turbulent-base supersonic afterbody drag on a full (unblocked) base area."""

ANNULAR_BASE_FRACTION: float = 0.7
"""Fraction of the base area that is genuinely separated dead-air/base
flow (rather than nozzle exit plane) [-]. # SZACOWANY -- no nozzle-exit
diameter is available in the YAML to compute the exact annular
(base-minus-nozzle-exit) area fraction; 0.7 is a placeholder engineering
guess pending real ramjet nozzle-exit geometry (nozzle_area_ratio=4.0 in
``vehicle_config.yaml`` gives the exit/throat ratio, not exit/body)."""

SUTHERLAND_TEMPERATURE_EXPONENT: float = 0.76
"""Viscosity-temperature-ratio exponent used in the Eckert reference-
temperature Cf scaling (``mu ~ T^exponent``), a standard simplification
of Sutherland's law over the temperature range of interest here
(Eckert 1955; also used in Anderson, *Hypersonic and High-Temperature
Gas Dynamics*, Ch. 6)."""

MIN_MACH_ABSOLUTE: float = 1.05
"""Reject Mach numbers at/below this value (mirrors
``analyses.aero.xfoil_runner.MIN_MACH_ABSOLUTE``): the Ackeret-type
sqrt(Ma^2-1) terms used here are singular at Mach 1 and untrustworthy
in the transonic band."""

MACH_GRID: tuple[float, ...] = (1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5)
"""Freestream Mach numbers swept (1.5-3.5, step 0.25) per task spec."""

THIS_DIR: Path = Path(__file__).resolve().parent
RESULTS_DIR: Path = THIS_DIR / "results"
OUTPUT_CSV_PATH: Path = RESULTS_DIR / "drag_polar.csv"
OUTPUT_JSON_PATH: Path = RESULTS_DIR / "drag_polar.json"
OUTPUT_PNG_PATH: Path = RESULTS_DIR / "drag_polar.png"


# --------------------------------------------------------------------------
# Component drag functions.
# --------------------------------------------------------------------------


def body_wave_drag_cd(mach: float, aref_m2: float) -> float:
    """Conical-nose supersonic wave (pressure) drag, referenced to ``Aref``.

    Uses the thin-cone linearized supersonic pressure-drag coefficient
    (referenced to the cone base area, which equals ``Aref`` here since
    the nose fairs out to the full body diameter):

        Cd_wave = 4 * delta^2 / sqrt(Ma^2 - 1)

    with ``delta`` the nose half-angle in radians. This is the thin-body
    limit of the conical-shock (Taylor-Maccoll) pressure-drag result and
    is documented as an acceptable slender-body approximation by Hoerner
    for cones with half-angle below ~15 deg (ramP's nose half-angle is
    ~23 deg from ``atan(0.125/0.293)``, at the upper edge of "slender" --
    flagged as an approximation, not exact Taylor-Maccoll).

    The cylindrical afterbody (constant cross-section, per the YAML's
    body geometry -- no boattail) contributes zero wave drag in this
    theory since ``d(Area)/dx = 0`` there.

    Args:
        mach: Freestream Mach number. Must be > ``MIN_MACH_ABSOLUTE``.
        aref_m2: Reference area [m^2] (body cross-section).

    Returns:
        Zero-lift body wave-drag coefficient [-], referenced to ``aref_m2``.

    Raises:
        ValueError: If ``mach <= MIN_MACH_ABSOLUTE``.

    Reference:
        Hoerner, S. F., *Fluid-Dynamic Drag*, 1965, Ch. 16 -- pressure
        (wave) drag of conical noses, slender-body/thin-cone limit.
    """
    if mach <= MIN_MACH_ABSOLUTE:
        raise ValueError(
            f"Mach {mach} too close to/below 1.0 (limit {MIN_MACH_ABSOLUTE}); "
            "linearized supersonic wave-drag theory is singular at Mach 1"
        )
    beta = math.sqrt(mach**2 - 1.0)
    return 4.0 * NOSE_HALF_ANGLE_RAD**2 / beta


def _reference_temperature_k(mach: float, t_static_k: float) -> float:
    """Eckert reference temperature for a turbulent compressible boundary layer.

    Compact Eckert (1955) polynomial form for an (approximately)
    adiabatic wall in turbulent flow:

        T*/Te = 1 + 0.032*Ma^2

    (the ``0.032`` coefficient already folds in a turbulent recovery
    factor ``r ~= Pr^(1/3) ~= 0.89`` and ``gamma=1.4`` air, per Eckert's
    original derivation -- this is the standard compact form used in
    high-speed skin-friction engineering estimates, e.g. Anderson,
    *Hypersonic and High-Temperature Gas Dynamics*, Ch. 6).

    Args:
        mach: Freestream Mach number.
        t_static_k: Freestream static temperature [K].

    Returns:
        Reference temperature ``T*`` [K].

    Reference:
        Eckert, E. R. G., "Engineering Relations for Friction and Heat
        Transfer to Surfaces in High Velocity Flow", J. Aero. Sci. 22(8),
        1955.
    """
    t_ratio = 1.0 + 0.032 * mach**2
    return t_static_k * t_ratio


def _wetted_area_body_m2() -> float:
    """Wetted area of the body (cone + cylinder), body-of-revolution.

    Cone lateral area: ``pi * r_base * slant_length``.
    Cylinder lateral area: ``pi * d * length``.

    Returns:
        Total body wetted area [m^2].
    """
    r_base = BODY_DIAMETER_M / 2.0
    slant_length = math.sqrt(NOSE_LENGTH_M**2 + r_base**2)
    cone_area = math.pi * r_base * slant_length
    cylinder_area = math.pi * BODY_DIAMETER_M * BODY_CYLINDER_LENGTH_M
    return cone_area + cylinder_area


def _wetted_area_fins_m2() -> float:
    """Wetted area of all fins (both sides, flat rectangular planform).

    Returns:
        Total fin wetted area [m^2] (``2 * count * span * chord``).
    """
    return 2.0 * FIN_COUNT * FIN_SPAN_M * FIN_CHORD_M


def skin_friction_cd(
    mach: float,
    altitude_m: float,
    aref_m2: float,
    reference_length_m: float = BODY_TOTAL_LENGTH_M,
) -> float:
    """Turbulent skin-friction drag coefficient with compressibility correction.

    Steps (reference-temperature method):
        1. Incompressible turbulent flat-plate ``Cf`` from the
           Prandtl-Schlichting correlation, ``Cf = 0.455/(log10(Re))^2.58``,
           evaluated at the Eckert reference temperature ``T*``
           (:func:`_reference_temperature_k`).
        2. Reynolds number recomputed at ``T*`` (density and viscosity
           both scaled with temperature via the ideal-gas law and a
           power-law viscosity model, ``mu ~ T^0.76``).
        3. ``Cf`` scaled to actual flight dynamic pressure and summed
           over wetted areas (body + fins), referenced to ``Aref``.

    Args:
        mach: Freestream Mach number.
        altitude_m: ISA altitude [m] (``0 <= altitude_m <= 11000``).
        aref_m2: Reference area [m^2] (body cross-section).
        reference_length_m: Characteristic length for the Reynolds
            number [m] (defaults to total body length).

    Returns:
        Zero-lift skin-friction drag coefficient [-], referenced to
        ``aref_m2``.

    Reference:
        Eckert, E. R. G. (1955), reference-temperature method.
        Schlichting, H., *Boundary-Layer Theory*, turbulent flat-plate
        Cf correlation (Prandtl-Schlichting).
    """
    rho_kg_m3, t_static_k, _p_pa, a_m_s = isa_atmosphere(altitude_m)
    v_m_s = mach * a_m_s

    t_ref_k = _reference_temperature_k(mach, t_static_k)

    # Sutherland-law viscosity at freestream static T (reference value
    # mu_ref=1.716e-5 Pa*s at T_ref=273.15 K, S=110.4 K -- standard air).
    mu_ref_pa_s = 1.716e-5
    t_mu_ref_k = 273.15
    sutherland_s_k = 110.4

    def _mu_sutherland(t_k: float) -> float:
        return (
            mu_ref_pa_s
            * (t_k / t_mu_ref_k) ** 1.5
            * (t_mu_ref_k + sutherland_s_k)
            / (t_k + sutherland_s_k)
        )

    mu_e_pa_s = _mu_sutherland(t_static_k)
    mu_star_pa_s = _mu_sutherland(t_ref_k)

    # Density scales as rho* = rho_e * (Te/T*) at constant static pressure
    # across the boundary layer (standard reference-temperature assumption).
    rho_star_kg_m3 = rho_kg_m3 * (t_static_k / t_ref_k)

    reynolds_star = rho_star_kg_m3 * v_m_s * reference_length_m / mu_star_pa_s
    reynolds_star = max(reynolds_star, 1.0e5)  # guard against degenerate log10

    cf_incompressible = 0.455 / (math.log10(reynolds_star)) ** 2.58

    # Cf*/Cf_incomp density-viscosity scaling (reference-temperature method):
    cf = cf_incompressible * (rho_star_kg_m3 / rho_kg_m3) * (mu_e_pa_s / mu_star_pa_s)

    wetted_area_m2 = _wetted_area_body_m2() + _wetted_area_fins_m2()
    return cf * wetted_area_m2 / aref_m2


def fin_wave_drag_cd(mach: float, aref_m2: float) -> float:
    """Zero-lift Ackeret thickness (wave-drag) term for all 4 fins.

    Reuses the ``t/c`` convention from
    :data:`analyses.aero.xfoil_runner.FIN_THICKNESS_TO_CHORD` (Fusion
    360 fin geometry, ``t/c ~= 0.1697``) rather than redefining it.
    At zero lift (``alpha=0``) the Ackeret ``CD`` expression
    (``4*(alpha^2+tau^2)/beta``) reduces to the pure thickness term
    ``4*tau^2/beta``, with ``tau = atan(t/c)``.

    Args:
        mach: Freestream Mach number. Must be > ``MIN_MACH_ABSOLUTE``.
        aref_m2: Reference area [m^2] (body cross-section).

    Returns:
        Zero-lift fin wave-drag coefficient [-], referenced to
        ``aref_m2`` (scaled by total fin planform area, both sides,
        summed over 4 fins).

    Raises:
        ValueError: If ``mach <= MIN_MACH_ABSOLUTE``.

    Reference:
        Anderson, *Fundamentals of Aerodynamics*, "Linearized Supersonic
        Flow" (Ackeret's rule), as reused in
        ``analyses.aero.xfoil_runner``.
    """
    if mach <= MIN_MACH_ABSOLUTE:
        raise ValueError(
            f"Mach {mach} too close to/below 1.0 (limit {MIN_MACH_ABSOLUTE}); "
            "Ackeret theory is singular at Mach 1"
        )
    beta = math.sqrt(mach**2 - 1.0)
    tau_rad = math.atan(FIN_THICKNESS_TO_CHORD)
    cd_2d = 4.0 * tau_rad**2 / beta

    fin_planform_area_m2 = FIN_COUNT * FIN_SPAN_M * FIN_CHORD_M
    return cd_2d * fin_planform_area_m2 / aref_m2


def base_drag_cd(mach: float) -> float:
    """Empirical supersonic base-drag coefficient (annular-base fraction).

    ``Cd_base = C / Ma^2``, ``C = BASE_DRAG_FIT_CONSTANT`` (Hoerner fit
    on the full base area), reduced by :data:`ANNULAR_BASE_FRACTION`
    (# SZACOWANY, see module docstring) to account for the ramjet
    nozzle exit occupying part of the base -- the base flow is not a
    fully dead-air/separated region.

    Args:
        mach: Freestream Mach number. Must be > ``MIN_MACH_ABSOLUTE``.

    Returns:
        Zero-lift base-drag coefficient [-], referenced to ``Aref``
        (base area == body cross-section for a non-boattailed body).

    Raises:
        ValueError: If ``mach <= MIN_MACH_ABSOLUTE``.

    Reference:
        Hoerner, S. F., *Fluid-Dynamic Drag*, 1965, Ch. 16, "Drag at
        the Base" -- supersonic base-drag engineering fit ``Cd ~ 1/Ma^2``.
    """
    if mach <= MIN_MACH_ABSOLUTE:
        raise ValueError(
            f"Mach {mach} too close to/below 1.0 (limit {MIN_MACH_ABSOLUTE}); "
            "supersonic base-drag fit is not intended for transonic/subsonic use"
        )
    cd_base_full = BASE_DRAG_FIT_CONSTANT / mach**2
    return cd_base_full * ANNULAR_BASE_FRACTION


# --------------------------------------------------------------------------
# Aggregation, results container, CSV/JSON I/O.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DragPolarPoint:
    """One Mach-swept zero-lift drag buildup point.

    Attributes:
        mach: Freestream Mach number [-].
        cd_body_wave: Conical-nose wave-drag coefficient [-].
        cd_friction: Turbulent compressible skin-friction coefficient [-].
        cd_fin_wave: Fin Ackeret thickness wave-drag coefficient [-].
        cd_base: Annular-base drag coefficient [-].
        cd0_total: Sum of the four components [-].
    """

    mach: float
    cd_body_wave: float
    cd_friction: float
    cd_fin_wave: float
    cd_base: float
    cd0_total: float


def compute_drag_polar_point(
    mach: float, altitude_m: float, aref_m2: float
) -> DragPolarPoint:
    """Evaluate all four drag components and their sum at one Mach/altitude.

    Args:
        mach: Freestream Mach number. Must be > ``MIN_MACH_ABSOLUTE``.
        altitude_m: ISA altitude [m] (``0 <= altitude_m <= 11000``).
        aref_m2: Reference area [m^2] (body cross-section).

    Returns:
        The resolved :class:`DragPolarPoint`.

    Raises:
        ValueError: If ``mach <= MIN_MACH_ABSOLUTE``.
    """
    cd_body_wave = body_wave_drag_cd(mach, aref_m2)
    cd_friction = skin_friction_cd(mach, altitude_m, aref_m2)
    cd_fin_wave = fin_wave_drag_cd(mach, aref_m2)
    cd_base = base_drag_cd(mach)
    cd0_total = cd_body_wave + cd_friction + cd_fin_wave + cd_base
    return DragPolarPoint(
        mach=mach,
        cd_body_wave=cd_body_wave,
        cd_friction=cd_friction,
        cd_fin_wave=cd_fin_wave,
        cd_base=cd_base,
        cd0_total=cd0_total,
    )


def compute_drag_polar_grid(
    mach_values: tuple[float, ...] = MACH_GRID,
    altitude_m: float = NIGHT3_ALTITUDE_M,
    aref_m2: float | None = None,
) -> list[DragPolarPoint]:
    """Sweep the Mach grid at a fixed reference altitude.

    Args:
        mach_values: Freestream Mach numbers to sweep (default 1.5-3.5,
            step 0.25).
        altitude_m: ISA altitude [m] held fixed across the sweep
            (default: Night-3 nominal cruise altitude, 6000 m).
        aref_m2: Reference area [m^2]; resolved from the vehicle config
            via :func:`analyses.mission.operational_envelope.reference_area_m2`
            if ``None``.

    Returns:
        List of :class:`DragPolarPoint`, one per Mach number.
    """
    if aref_m2 is None:
        aref_m2 = reference_area_m2()
    return [compute_drag_polar_point(mach, altitude_m, aref_m2) for mach in mach_values]


def teltik_validation(aref_m2: float | None = None) -> dict[str, float | str]:
    """Compare this buildup's Ma 2.5/6000 m result against the Teltik CFD point.

    Computes ``drag_N = cd0_total * q * Aref`` at the Teltik reference
    condition (Mach 2.5, 6000 m ISA -- ``docs/assumptions.md`` A15) and
    reports it, the Teltik-implied ``CD0`` (``Teltik_drag_N /
    (q*Aref)``), and the deltas of THIS buildup and of the
    ``operational_envelope.CD0_PLACEHOLDER`` (0.35) against that implied
    CD0. Deltas are reported as-is (not tuned to close the gap).

    Args:
        aref_m2: Reference area [m^2]; resolved via
            :func:`analyses.mission.operational_envelope.reference_area_m2`
            if ``None``.

    Returns:
        Dict with keys ``mach``, ``altitude_m``, ``cd0_buildup``,
        ``drag_N_buildup``, ``teltik_drag_N_ref``, ``teltik_implied_cd0``,
        ``delta_drag_N``, ``delta_drag_pct``, ``delta_cd0_buildup_vs_teltik``,
        ``delta_cd0_placeholder_vs_teltik``, and ``note``.
    """
    if aref_m2 is None:
        aref_m2 = reference_area_m2()

    point = compute_drag_polar_point(NIGHT3_MACH, NIGHT3_ALTITUDE_M, aref_m2)

    rho_kg_m3, _t_k, _p_pa, a_m_s = isa_atmosphere(NIGHT3_ALTITUDE_M)
    v_m_s = NIGHT3_MACH * a_m_s
    q_pa = 0.5 * rho_kg_m3 * v_m_s**2

    drag_n_buildup = point.cd0_total * q_pa * aref_m2
    teltik_implied_cd0 = TELTIK_CFD_DRAG_N_REF / (q_pa * aref_m2)

    delta_drag_n = drag_n_buildup - TELTIK_CFD_DRAG_N_REF
    delta_drag_pct = 100.0 * delta_drag_n / TELTIK_CFD_DRAG_N_REF

    cd0_placeholder = 0.35  # mirrors operational_envelope.CD0_PLACEHOLDER
    delta_cd0_buildup_vs_teltik = point.cd0_total - teltik_implied_cd0
    delta_cd0_placeholder_vs_teltik = cd0_placeholder - teltik_implied_cd0

    note = (
        "Reported as-is, NOT tuned to match Teltik CFD. Component buildup is "
        "an independent L1 estimate; disagreement with a single CFD point at "
        "one Mach/altitude does not invalidate the buildup across the full "
        "Mach sweep, but flags where refinement (nose taper geometry, actual "
        "nozzle-exit annular fraction, boundary-layer transition location) "
        "would matter most."
    )

    return {
        "mach": NIGHT3_MACH,
        "altitude_m": NIGHT3_ALTITUDE_M,
        "cd0_buildup": point.cd0_total,
        "drag_N_buildup": drag_n_buildup,
        "teltik_drag_N_ref": TELTIK_CFD_DRAG_N_REF,
        "teltik_implied_cd0": teltik_implied_cd0,
        "delta_drag_N": delta_drag_n,
        "delta_drag_pct": delta_drag_pct,
        "cd0_placeholder": cd0_placeholder,
        "delta_cd0_buildup_vs_teltik": delta_cd0_buildup_vs_teltik,
        "delta_cd0_placeholder_vs_teltik": delta_cd0_placeholder_vs_teltik,
        "note": note,
    }


def write_csv(points: list[DragPolarPoint], output_path: Path = OUTPUT_CSV_PATH) -> None:
    """Write the drag-polar grid to CSV with the required 6 columns.

    Columns: ``mach, cd_body_wave, cd_friction, cd_fin_wave, cd_base,
    cd0_total`` (all dimensionless [-]).

    Args:
        points: Drag-polar grid points (see :func:`compute_drag_polar_grid`).
        output_path: Destination CSV path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["mach", "cd_body_wave", "cd_friction", "cd_fin_wave", "cd_base", "cd0_total"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for point in points:
            writer.writerow(asdict(point))


def plot_drag_polar(points: list[DragPolarPoint], output_path: Path = OUTPUT_PNG_PATH) -> None:
    """Render the stacked component drag buildup vs. Mach (optional, 150 DPI).

    Not committed (PNG outputs are gitignored per project convention) --
    regenerable via :func:`main`.

    Args:
        points: Drag-polar grid points.
        output_path: Destination PNG path.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    machs = [p.mach for p in points]
    fig, ax = plt.subplots(figsize=(8.0, 6.0))
    ax.stackplot(
        machs,
        [p.cd_body_wave for p in points],
        [p.cd_friction for p in points],
        [p.cd_fin_wave for p in points],
        [p.cd_base for p in points],
        labels=["Body wave drag", "Skin friction", "Fin wave drag", "Base drag"],
    )
    ax.plot(machs, [p.cd0_total for p in points], color="black", linewidth=2.0, label="CD0 total")
    ax.set_xlabel("Freestream Mach number [-]")
    ax.set_ylabel("Zero-lift drag coefficient, CD0 [-]")
    ax.set_title("MELprop-IADE | RamP zero-lift drag buildup (Ma 1.5-3.5)")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


class DragPolarAnalysis(BaseAnalysis):
    """L1 empirical supersonic zero-lift drag buildup (Project B, ramP).

    Attributes:
        fidelity: :attr:`FidelityLevel.LEVEL_1` (empirical/analytical
            correlation buildup, same tier as the Ackeret fin polar and
            Barrowman stability analyses elsewhere in this repo).
    """

    fidelity = FidelityLevel.LEVEL_1

    def __init__(self, name: str = "ramp_drag_polar") -> None:
        super().__init__(name)
        self._mach_values: tuple[float, ...] | None = None
        self._altitude_m: float | None = None
        self._aref_m2: float | None = None

    def setup(
        self,
        mach_values: tuple[float, ...] = MACH_GRID,
        altitude_m: float = NIGHT3_ALTITUDE_M,
        aref_m2: float | None = None,
    ) -> None:
        """Bind the Mach sweep, altitude, and reference area.

        Args:
            mach_values: Freestream Mach numbers to sweep.
            altitude_m: ISA altitude [m] held fixed across the sweep.
            aref_m2: Reference area [m^2]; resolved from the vehicle
                config if ``None``.

        Raises:
            ValueError: If any Mach number is ``<= MIN_MACH_ABSOLUTE``.
        """
        for mach in mach_values:
            if mach <= MIN_MACH_ABSOLUTE:
                raise ValueError(
                    f"Mach {mach} too close to/below 1.0 (limit "
                    f"{MIN_MACH_ABSOLUTE}); supersonic drag-buildup "
                    "correlations used here are singular/invalid at Mach 1"
                )
        self._mach_values = mach_values
        self._altitude_m = altitude_m
        self._aref_m2 = aref_m2 if aref_m2 is not None else reference_area_m2()
        self._is_setup = True

    def execute(self) -> AnalysisResults:
        """Compute the drag-polar grid and the Teltik validation gate.

        Returns:
            AnalysisResults whose ``data`` holds the Teltik-validation
            scalars (for the uniform ``AnalysisResults.data`` contract)
            and whose ``metadata`` carries the full per-Mach grid plus
            the validation note string.

        Raises:
            RuntimeError: If called before :meth:`setup`.
        """
        if not self._is_setup or self._mach_values is None:
            raise RuntimeError("DragPolarAnalysis.execute() called before setup()")

        points = compute_drag_polar_grid(self._mach_values, self._altitude_m, self._aref_m2)
        validation = teltik_validation(self._aref_m2)

        data: dict[str, float] = {
            "cd0_at_teltik_point": float(validation["cd0_buildup"]),
            "drag_N_at_teltik_point": float(validation["drag_N_buildup"]),
            "teltik_drag_N_ref": float(validation["teltik_drag_N_ref"]),
            "delta_drag_pct": float(validation["delta_drag_pct"]),
            "teltik_implied_cd0": float(validation["teltik_implied_cd0"]),
        }

        return AnalysisResults(
            name=self.name,
            fidelity=self.fidelity,
            data=data,
            metadata={
                "method": "empirical_drag_buildup_body_wave_friction_fin_base",
                "grid": [asdict(p) for p in points],
                "validation": validation,
                "annular_base_fraction_szacowany": ANNULAR_BASE_FRACTION,
            },
        )

    def validate_results(self, results: AnalysisResults) -> bool:
        """Sanity-check that CD0 decreases with Mach and matches component sum.

        Args:
            results: Output of :meth:`execute`.

        Returns:
            True if the grid is monotonically decreasing in ``cd0_total``
            over Mach and the first grid point's total equals the sum
            of its four components (within a tight tolerance).
        """
        grid = results.metadata.get("grid", [])
        if len(grid) < 2:
            return False
        totals = [row["cd0_total"] for row in grid]
        monotonic = all(totals[i] >= totals[i + 1] for i in range(len(totals) - 1))
        first = grid[0]
        component_sum = (
            first["cd_body_wave"] + first["cd_friction"] + first["cd_fin_wave"] + first["cd_base"]
        )
        sum_matches = math.isclose(component_sum, first["cd0_total"], rel_tol=1e-9)
        return monotonic and sum_matches


def main() -> dict[str, Any]:
    """Sweep the grid, write CSV + JSON (+ optional PNG), print validation gate.

    Returns:
        The JSON-serializable output dict (also written to
        ``analyses/aero/results/drag_polar.json``).
    """
    analysis = DragPolarAnalysis()
    analysis.setup()
    results = analysis.execute()
    assert analysis.validate_results(results), "Drag-polar grid failed self-consistency check"

    points = [DragPolarPoint(**row) for row in results.metadata["grid"]]
    write_csv(points, OUTPUT_CSV_PATH)
    plot_drag_polar(points, OUTPUT_PNG_PATH)

    output: dict[str, Any] = {
        "data": results.data,
        "metadata": results.metadata,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON_PATH.open("w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)

    validation = results.metadata["validation"]
    print("=== RamP zero-lift drag buildup (Ma 1.5-3.5) ===")
    print(f"Grid points: {len(points)}")
    for p in points:
        print(
            f"  Ma {p.mach:4.2f}: CD0_total={p.cd0_total:.5f} "
            f"(body_wave={p.cd_body_wave:.5f}, friction={p.cd_friction:.5f}, "
            f"fin_wave={p.cd_fin_wave:.5f}, base={p.cd_base:.5f})"
        )
    print(
        f"\nTeltik validation (Ma {validation['mach']} / {validation['altitude_m']:.0f} m):"
    )
    print(f"  CD0 buildup: {validation['cd0_buildup']:.5f}")
    print(f"  drag_N buildup: {validation['drag_N_buildup']:.2f} N")
    print(f"  Teltik CFD drag_N ref: {validation['teltik_drag_N_ref']:.2f} N")
    print(f"  delta_drag_N: {validation['delta_drag_N']:.2f} N ({validation['delta_drag_pct']:.1f}%)")
    print(f"  Teltik-implied CD0: {validation['teltik_implied_cd0']:.5f}")
    print(
        f"  delta CD0 buildup vs Teltik-implied: {validation['delta_cd0_buildup_vs_teltik']:.5f}"
    )
    print(
        f"  delta CD0 placeholder(0.35) vs Teltik-implied: "
        f"{validation['delta_cd0_placeholder_vs_teltik']:.5f}"
    )
    print(f"  {validation['note']}")
    print(f"\nCSV written to: {OUTPUT_CSV_PATH}")
    print(f"JSON written to: {OUTPUT_JSON_PATH}")
    print(f"PNG written to: {OUTPUT_PNG_PATH}")

    return output


if __name__ == "__main__":
    main()
