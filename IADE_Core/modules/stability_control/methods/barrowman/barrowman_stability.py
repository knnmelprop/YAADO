"""Low-order static-stability analysis for the ramjet rocket (Generic Vehicle).

Implements the classical Barrowman method for the subsonic center of
pressure (CP) of a slender body-of-revolution + fin rocket, extended
through the transonic band and into the supersonic regime with a
Prandtl-Glauert / linearized-supersonic-theory correction on the fin
normal-force-curve slope (informally known in the amateur/professional
rocketry community as the "Rogers extension" to Barrowman, used e.g. by
RASAero and OpenRocket to keep CP well-behaved through Mach 1).

Theory references
------------------
- Barrowman, J. S. and Barrowman, J. A., *The Theoretical Prediction of
  the Center of Pressure*, NARAM-8, 1966; and Barrowman, J. S., *The
  Practical Calculation of the Aerodynamic Characteristics of Slender
  Finned Vehicles*, MS Thesis, The Catholic University of America, 1967.
  (Source of the nose/transition/fin ``CN_alpha`` and CP formulas used
  below.)
- Galejs, R., *Where is the Center of Pressure?*, describes the same
  formulas as implemented in RockSim/OpenRocket.
- Prandtl-Glauert subsonic compressibility correction and Ackeret
  (linearized supersonic thin-airfoil) theory ``CN_alpha = 4/sqrt(M^2-1)``
  for the transonic/supersonic fin-slope extension.
- Hoerner, S. F. and Borst, H. V., *Fluid-Dynamic Lift*, for the
  fin-body interference factor ``Kfb = 1 + R/(s+R)``.

Applicability and limits
-------------------------
This is a **low-order engineering estimate**, not CFD: it uses linear
(small-disturbance) potential theory for the body and fins, a simple
area-ratio nose/transition model, and a hand-blended transonic bridge
(0.8 <= Mach <= 1.2) where no closed-form linear theory is valid. It
does **not** capture nonlinear vortex lift, base drag effects on CP,
boundary-layer/viscous effects, or fin-fin interference between the
four panels. Per project rules, AVL (a subsonic VLM solver) is never
used for this vehicle's supersonic flight regime; empirical DATCOM-style
correlations are used throughout instead.

**SUPERSONIC REGIME: HISTORICAL / OUT-OF-REGIME (2026-07-11 decision)**
------------------------------------------------------------------------
The supersonic output of this module (Mach > 1.2) is **RETIRED as the CDR
stability gate** and marked HISTORICAL / OUT-OF-REGIME per the following
reasoning:

1. **Barrowman slender-body theory is validated only to ~Mach 0.7**. The
   vehicle cruise condition (Mach 2.5) is well outside this validated envelope.

2. **The vehicle fins violate the small-fin assumption**:
   - Fin semi-span: 0.550 m
   - Body diameter: 0.200 m
   - Ratio: 0.550 / 0.200 = **2.75** (fin extends ~2.67× a body diameter
     from the centerline).
   - Classical Barrowman assumes fins are "small perturbations" on the body
     (fin span comparable to or smaller than body radius).

For these reasons, the supersonic static-margin results produced by this
module (+8.99 cal basic / +4.594 cal extended at Ma 2.5) are **NOT
reconciled** with the Teltik CFD (-2.75 cal @ Ma 2.5) or other supersonic
methods. Instead, the supersonic stability analysis is replaced by:

- **datcom_class_sweep.py**: DATCOM/RASAero-class supersonic component
  buildup (intermediate fidelity, Mach 1.2–3.0).
- **ackeret_fin_check.py**: Independent Ackeret / slender-body fin CP
  hand-check.
- **SU2 RANS-SST** (authoritative cross-check, deferred where SU2 is not
  buildable).

See ``docs/decision-log.md`` (2026-07-11 entry) for the full rationale and
``docs/references/vehicle_analysis_plan_2026-07-11.md`` for the research
findings that motivate this retirement.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if __name__ == "__main__" and __package__ in (None, ""):
    # Allow `python3 analyses/stability/barrowman_stability.py` direct
    # execution by putting the repository root on sys.path, mirroring
    # what `python -m` / pytest's rootdir-based conftest.py already do.
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (backend must be set first)
import numpy as np  # noqa: E402
import yaml  # noqa: E402

from IADE_Core.modules.wind_tunnel.methods.avl.avl_wrapper import helmbold_cl_alpha  # noqa: E402
from IADE_Core.Foundation.component_base import (  # noqa: E402
    AnalysisResults,
    BaseAnalysis,
    FidelityLevel,
)

# --------------------------------------------------------------------------
# Named constants (Barrowman / Rogers-extension correlation parameters).
# --------------------------------------------------------------------------

#: CP location factor (fraction of nose length, measured from the nose
#: tip) applied to the nose in this analysis, per explicit task
#: specification. NOTE: the classical Barrowman value for a *true*
#: conical nose is 2/3 = 0.666 (apex-to-CP), while 0.466 is the classical
#: value for a tangent-ogive nose. This module uses 0.466 as instructed
#: (documented as an ``assumption`` in the output); it is a conservative
#: (more-forward, i.e. destabilizing) choice relative to the 0.666 cone
#: value, so static-margin results here are slightly conservative for a
#: geometrically perfect cone.
NOSE_CP_FACTOR = 0.466

#: Assumed axial length of the 0.150 m -> 0.250 m conical shoulder
#: (transition) aft of the nose. Not present in the Fusion export;
#: assumed short per task instruction and documented in ``assumptions``.
TRANSITION_LENGTH_M = 0.10

#: Upper Mach bound of the "purely subsonic" Prandtl-Glauert branch.
MACH_SUBSONIC_LIMIT = 0.8

#: Lower Mach bound of the "purely supersonic" linearized-theory branch.
#: 0.8 < Mach < 1.2 is bridged by linear interpolation (no closed-form
#: linear theory is valid transonically).
MACH_SUPERSONIC_LIMIT = 1.2

#: 2D incompressible thin-airfoil lift-curve slope [1/rad], used to
#: normalize the supersonic Ackeret slope onto the same M=0 anchor as
#: the incompressible Barrowman fin formula.
THIN_AIRFOIL_SLOPE_2D = 2.0 * math.pi

#: Static-margin design rule: required margin scales with fineness ratio,
#: SM_required [calibers] = (L / d_ref) / STATIC_MARGIN_RULE_DIVISOR.
STATIC_MARGIN_RULE_DIVISOR = 10.0

#: Default Mach sweep for the CP-vs-Mach plot.
MACH_SWEEP_MIN = 0.3
MACH_SWEEP_MAX = 3.5

#: Default path to the Project-B vehicle configuration.
DEFAULT_VEHICLE_CONFIG = (
    Path(__file__).resolve().parents[5]
    / "Hangar"
    / "generic_vehicle"
    / "vehicle_config.yaml"
)

#: Output artifact paths.
RESULTS_JSON_PATH = Path(__file__).resolve().parent / "barrowman_results.json"
CP_PLOT_PATH = Path(__file__).resolve().parent / "cp_vs_mach.png"


@dataclass
class RocketGeometry:
    """Slender-body + fin geometry needed by the Barrowman method.

    All lengths and diameters are in meters, measured along the body
    centerline from the nose tip (``x = 0``) unless noted otherwise.

    Attributes:
        d_ref_m: Reference (body) diameter used for all CN_alpha
            coefficients and the static-margin caliber normalization.
        nose_length_m: Axial length of the conical nose.
        nose_base_diameter_m: Diameter at the base of the nose (may be
            smaller than ``d_ref_m``, in which case a conical transition
            follows).
        total_length_m: Total rocket length (nose tip to aft end).
        transition_length_m: Axial length of the nose-to-body conical
            transition (shoulder).
        fin_count: Number of fins (typically 3 or 4).
        fin_span_m: Exposed fin semi-span (from the body surface to the
            fin tip), i.e. does not include the body radius.
        fin_root_chord_m: Fin root chord.
        fin_tip_chord_m: Fin tip chord.
        fin_sweep_deg: Fin leading-edge sweep angle in degrees.
        cg_from_nose_m: Center of gravity location from the nose tip.
    """

    d_ref_m: float
    nose_length_m: float
    nose_base_diameter_m: float
    total_length_m: float
    transition_length_m: float
    fin_count: int
    fin_span_m: float
    fin_root_chord_m: float
    fin_tip_chord_m: float
    fin_sweep_deg: float
    cg_from_nose_m: float

    @property
    def body_radius_m(self) -> float:
        """Reference body radius [m]."""
        return self.d_ref_m / 2.0

    @property
    def transition_start_m(self) -> float:
        """Axial start of the nose-to-body transition [m from nose]."""
        return self.nose_length_m

    @property
    def fin_root_le_x_m(self) -> float:
        """Axial position of the fin root leading edge [m from nose].

        Assumption: the fins are mounted flush with the aft end of the
        rocket, so the root *trailing* edge coincides with the total
        rocket length (``x_fin = L - chord_root``), per task
        specification.
        """
        return self.total_length_m - self.fin_root_chord_m

    @property
    def fineness_ratio(self) -> float:
        """Overall fineness ratio ``L / d_ref`` [-]."""
        return self.total_length_m / self.d_ref_m


def load_geometry(config_path: Path | str = DEFAULT_VEHICLE_CONFIG) -> RocketGeometry:
    """Load rocket geometry from the Project-B vehicle YAML configuration.

    Args:
        config_path: Path to ``vehicle_config.yaml`` for the ramjet
            rocket (Fusion Assembly v6 reconciled geometry).

    Returns:
        Populated :class:`RocketGeometry`.

    Raises:
        FileNotFoundError: If ``config_path`` does not exist.
        KeyError: If a required geometry field is missing from the YAML.
    """
    config_path = Path(config_path)
    with config_path.open("r", encoding="utf-8") as fh:
        config: dict[str, Any] = yaml.safe_load(fh)

    body = config["body"]
    fins = config["fins"]
    mass = config["mass_properties"]

    return RocketGeometry(
        d_ref_m=float(body["diameter_m"]),
        nose_length_m=float(body["nose_length_m"]),
        nose_base_diameter_m=float(body["nose_diameter_m"]),
        total_length_m=float(body["total_length_m"]),
        transition_length_m=TRANSITION_LENGTH_M,
        fin_count=int(fins["count"]),
        fin_span_m=float(fins["span_m"]),
        fin_root_chord_m=float(fins["chord_root_m"]),
        fin_tip_chord_m=float(fins["chord_tip_m"]),
        fin_sweep_deg=float(fins["sweep_deg"]),
        cg_from_nose_m=float(mass["cg_from_nose_m"]),
    )


# --------------------------------------------------------------------------
# Barrowman component formulas (each returns (CN_alpha [1/rad, referenced
# to A_ref = pi/4 * d_ref^2], x_cp [m from nose tip]).
# --------------------------------------------------------------------------


def nose_cn_alpha_and_cp(geometry: RocketGeometry) -> tuple[float, float]:
    """Conical-nose CN_alpha and CP location (Barrowman).

    ``CN_alpha = 2`` referenced to the nose's own base area, converted
    to the common reference area via the diameter-squared ratio. CP is
    located at ``NOSE_CP_FACTOR * L_nose`` from the nose tip (see the
    module-level note on the 0.466 vs 0.666 coefficient).

    Args:
        geometry: Rocket geometry.

    Returns:
        Tuple of (CN_alpha [1/rad, ref. A_ref], x_cp [m from nose]).
    """
    area_ratio = (geometry.nose_base_diameter_m / geometry.d_ref_m) ** 2
    cn_alpha = 2.0 * area_ratio
    x_cp = NOSE_CP_FACTOR * geometry.nose_length_m
    return cn_alpha, x_cp


def transition_cn_alpha_and_cp(geometry: RocketGeometry) -> tuple[float, float]:
    """Conical-transition (shoulder) CN_alpha and CP location (Barrowman).

    ``CN_alpha = 2 * (A_rear - A_front) / A_ref``. CP measured from the
    front of the transition:
    ``X = (L_t/3) * [1 + (1 - r1/r2) / (1 - (r1/r2)^2)]``.

    Args:
        geometry: Rocket geometry.

    Returns:
        Tuple of (CN_alpha [1/rad, ref. A_ref], x_cp [m from nose]).
    """
    r1 = geometry.nose_base_diameter_m / 2.0
    r2 = geometry.body_radius_m
    length = geometry.transition_length_m

    area_ratio = (r1 / r2) ** 2
    cn_alpha = 2.0 * (1.0 - area_ratio)

    ratio = r1 / r2
    x_from_front = (length / 3.0) * (1.0 + (1.0 - ratio) / (1.0 - ratio**2))
    x_cp = geometry.transition_start_m + x_from_front
    return cn_alpha, x_cp


def fin_cn_alpha_base_and_cp(geometry: RocketGeometry) -> tuple[float, float]:
    """Fin-set CN_alpha (M=0 anchor) and CP location (Barrowman).

    ``CN_alpha = Kfb * 4*N*(s/d)^2 / (1 + sqrt(1 + (2*l_m/(Cr+Ct))^2))``
    with body-interference factor ``Kfb = 1 + R/(s+R)``. CP is measured
    from the fin root leading edge:
    ``X = l_m*(Cr+2*Ct)/(3*(Cr+Ct)) + (Cr+Ct - Cr*Ct/(Cr+Ct))/6``.

    Args:
        geometry: Rocket geometry.

    Returns:
        Tuple of (CN_alpha [1/rad, ref. A_ref, M=0 anchor],
        x_cp [m from nose]).
    """
    s = geometry.fin_span_m
    cr = geometry.fin_root_chord_m
    ct = geometry.fin_tip_chord_m
    n = geometry.fin_count
    r = geometry.body_radius_m
    d = geometry.d_ref_m

    # Leading-edge sweep distance (root LE to tip LE, parallel to axis).
    l_m = s * math.tan(math.radians(geometry.fin_sweep_deg))

    k_fb = 1.0 + r / (s + r)
    denom = 1.0 + math.sqrt(1.0 + (2.0 * l_m / (cr + ct)) ** 2)
    cn_alpha = k_fb * 4.0 * n * (s / d) ** 2 / denom

    x_from_root_le = l_m * (cr + 2.0 * ct) / (3.0 * (cr + ct)) + (
        cr + ct - cr * ct / (cr + ct)
    ) / 6.0
    x_cp = geometry.fin_root_le_x_m + x_from_root_le
    return cn_alpha, x_cp


def fin_mach_correction_factor(mach: float) -> float:
    """Rogers-extended compressibility correction on fin CN_alpha.

    **NOTE (2026-07-11): The supersonic branch (mach > MACH_SUPERSONIC_LIMIT)
    of this function is HISTORICAL / OUT-OF-REGIME for the vehicle vehicle
    (see module-level docstring "SUPERSONIC REGIME" section). Barrowman
    is valid only to ~Mach 0.7; the vehicle fins violate the small-fin
    assumption (fin span / body diameter = 2.75). Supersonic stability
    analysis is now performed by datcom_class_sweep.py (DATCOM-class
    component buildup) and ackeret_fin_check.py (independent Ackeret
    hand-check). This function's numerics are UNCHANGED (for historical
    reproducibility), but its supersonic output is not used as a CDR gate.**

    Anchored at 1.0 for ``mach -> 0`` (matching the incompressible
    Barrowman fin formula):

    - Subsonic (``mach < MACH_SUBSONIC_LIMIT``): Prandtl-Glauert,
      ``1 / sqrt(1 - mach^2)``.
    - Transonic (``MACH_SUBSONIC_LIMIT <= mach <= MACH_SUPERSONIC_LIMIT``):
      linear interpolation between the subsonic-branch value at
      ``MACH_SUBSONIC_LIMIT`` and the supersonic-branch value at
      ``MACH_SUPERSONIC_LIMIT``. No closed-form linear theory is valid
      in this band; this is the low-order "Rogers" bridge.
    - Supersonic (``mach > MACH_SUPERSONIC_LIMIT``): linearized
      (Ackeret) thin-airfoil slope ``4 / sqrt(mach^2 - 1)``, normalized
      by the 2D incompressible slope ``2*pi`` so it is dimensionally
      consistent with the M=0 anchor of 1.0.

    Args:
        mach: Freestream Mach number (>= 0).

    Returns:
        Dimensionless multiplier on the M=0 fin CN_alpha.

    Raises:
        ValueError: If ``mach`` is negative.
    """
    if mach < 0.0:
        raise ValueError(f"mach must be >= 0, got {mach}")

    def _subsonic(m: float) -> float:
        return 1.0 / math.sqrt(1.0 - m**2)

    def _supersonic(m: float) -> float:
        return (4.0 / math.sqrt(m**2 - 1.0)) / THIN_AIRFOIL_SLOPE_2D

    if mach < MACH_SUBSONIC_LIMIT:
        return _subsonic(mach)
    if mach > MACH_SUPERSONIC_LIMIT:
        return _supersonic(mach)

    f_sub = _subsonic(MACH_SUBSONIC_LIMIT)
    f_sup = _supersonic(MACH_SUPERSONIC_LIMIT)
    frac = (mach - MACH_SUBSONIC_LIMIT) / (MACH_SUPERSONIC_LIMIT - MACH_SUBSONIC_LIMIT)
    return f_sub + frac * (f_sup - f_sub)


@dataclass
class ComponentContribution:
    """CN_alpha and CP contribution of a single Barrowman component.

    Attributes:
        name: Component name (``"nose"``, ``"transition"``, ``"fins"``).
        cn_alpha: Normal-force-curve slope [1/rad], referenced to
            ``A_ref = pi/4 * d_ref^2``, at the evaluated Mach number.
        x_cp_m: Center-of-pressure location [m from the nose tip].
    """

    name: str
    cn_alpha: float
    x_cp_m: float


@dataclass
class StabilityResult:
    """Aggregate stability result at a single Mach number.

    Attributes:
        mach: Freestream Mach number.
        components: Per-component contributions.
        cn_alpha_total: Total vehicle CN_alpha [1/rad].
        x_cp_m: Combined center-of-pressure location [m from nose].
    """

    mach: float
    components: list[ComponentContribution] = field(default_factory=list)
    cn_alpha_total: float = 0.0
    x_cp_m: float = 0.0


def compute_stability_at_mach(geometry: RocketGeometry, mach: float) -> StabilityResult:
    """Compute total CN_alpha and CP location at a given Mach number.

    Nose and transition CN_alpha are held constant with Mach (slender-
    body theory is Mach-invariant to first order for pointed
    axisymmetric bodies); only the fin CN_alpha receives the
    Prandtl-Glauert / Rogers / Ackeret compressibility correction via
    :func:`fin_mach_correction_factor`.

    Args:
        geometry: Rocket geometry.
        mach: Freestream Mach number (>= 0).

    Returns:
        :class:`StabilityResult` with the component breakdown, total
        CN_alpha, and combined CP location.
    """
    cn_nose, x_nose = nose_cn_alpha_and_cp(geometry)
    cn_trans, x_trans = transition_cn_alpha_and_cp(geometry)
    cn_fin_base, x_fin = fin_cn_alpha_base_and_cp(geometry)
    cn_fin = cn_fin_base * fin_mach_correction_factor(mach)

    components = [
        ComponentContribution("nose", cn_nose, x_nose),
        ComponentContribution("transition", cn_trans, x_trans),
        ComponentContribution("fins", cn_fin, x_fin),
    ]
    cn_alpha_total = sum(c.cn_alpha for c in components)
    x_cp_m = sum(c.cn_alpha * c.x_cp_m for c in components) / cn_alpha_total

    return StabilityResult(
        mach=mach,
        components=components,
        cn_alpha_total=cn_alpha_total,
        x_cp_m=x_cp_m,
    )


class BarrowmanStabilityAnalysis(BaseAnalysis):
    """Low-order (Barrowman + Rogers extension) static-stability analysis.

    Computes the subsonic Barrowman center of pressure and its
    transonic/supersonic Mach-dependent shift for a slender body +
    cruciform-fin rocket (Generic Vehicle, generic_vehicle), and evaluates the
    static margin against a fineness-ratio-scaled design rule.

    Example:
        >>> analysis = BarrowmanStabilityAnalysis()
        >>> analysis.setup()
        >>> results = analysis.execute()
        >>> results["static_margin_cal"] > 0  # doctest: +SKIP
    """

    fidelity = FidelityLevel.LEVEL_0

    def __init__(self, name: str = "barrowman_stability") -> None:
        super().__init__(name)
        self._geometry: RocketGeometry | None = None

    @property
    def geometry(self) -> RocketGeometry | None:
        """Rocket geometry bound by :meth:`setup`, or None before setup."""
        return self._geometry

    def setup(self, config_path: Path | str = DEFAULT_VEHICLE_CONFIG) -> None:
        """Load geometry from the vehicle YAML and validate it.

        Args:
            config_path: Path to the ramjet-rocket ``vehicle_config.yaml``.

        Raises:
            ValueError: If any geometry field is non-physical (<= 0).
        """
        geometry = load_geometry(config_path)
        for field_name in (
            "d_ref_m",
            "nose_length_m",
            "nose_base_diameter_m",
            "total_length_m",
            "fin_span_m",
            "fin_root_chord_m",
            "fin_tip_chord_m",
        ):
            if getattr(geometry, field_name) <= 0.0:
                raise ValueError(f"Geometry field {field_name!r} must be > 0")
        if geometry.nose_base_diameter_m > geometry.d_ref_m:
            raise ValueError(
                "nose_base_diameter_m must not exceed d_ref_m "
                "(expansion transitions are not modeled)"
            )
        self._geometry = geometry
        self._is_setup = True

    def execute(self) -> AnalysisResults:
        """Run the Barrowman + Rogers-extension analysis.

        Returns:
            AnalysisResults with ``cp_subsonic_m``, ``cp_transonic_m``
            (Mach 1.0), ``cg_m``, ``static_margin_cal``,
            ``sm_required_cal``, ``margin_cal``, ``fineness_ratio``, and
            ``cn_alpha_subsonic`` / ``cn_alpha_transonic`` [1/rad].
            ``metadata`` carries the geometry, per-component breakdown,
            assumptions, and PASS/FAIL verdict.

        Raises:
            RuntimeError: If called before :meth:`setup`, or if results
                fail the analytical sanity check.
        """
        if not self._is_setup or self._geometry is None:
            raise RuntimeError("BarrowmanStabilityAnalysis.execute() called before setup()")

        geometry = self._geometry
        subsonic = compute_stability_at_mach(geometry, mach=0.0)
        transonic = compute_stability_at_mach(geometry, mach=1.0)

        cg_m = geometry.cg_from_nose_m
        fineness_ratio = geometry.fineness_ratio
        sm_required_cal = fineness_ratio / STATIC_MARGIN_RULE_DIVISOR

        sm_subsonic_cal = (subsonic.x_cp_m - cg_m) / geometry.d_ref_m
        sm_transonic_cal = (transonic.x_cp_m - cg_m) / geometry.d_ref_m

        margin_cal = sm_subsonic_cal - sm_required_cal
        verdict = "PASS" if margin_cal >= 0.0 else "FAIL"

        results = AnalysisResults(
            name=self.name,
            fidelity=self.fidelity,
            data={
                "cp_subsonic_m": subsonic.x_cp_m,
                "cp_transonic_m": transonic.x_cp_m,
                "cg_m": cg_m,
                "static_margin_cal": sm_subsonic_cal,
                "static_margin_transonic_cal": sm_transonic_cal,
                "fineness_ratio": fineness_ratio,
                "sm_required_cal": sm_required_cal,
                "margin_cal": margin_cal,
                "cn_alpha_subsonic_per_rad": subsonic.cn_alpha_total,
                "cn_alpha_transonic_per_rad": transonic.cn_alpha_total,
            },
            metadata={
                "verdict": verdict,
                "method": "barrowman_subsonic + rogers_transonic_extension",
                "geometry": _geometry_to_dict(geometry),
                "component_breakdown_subsonic": _components_to_dict(subsonic.components),
                "component_breakdown_transonic_m1": _components_to_dict(transonic.components),
                "assumptions": _assumptions(geometry),
            },
        )
        if not self.validate_results(results):
            raise RuntimeError(
                "BarrowmanStabilityAnalysis results failed analytical "
                "cross-check; see validate_results()"
            )
        return results

    def validate_results(self, results: AnalysisResults) -> bool:
        """Sanity-check CP bounds and an independent fin-slope estimate.

        Checks:

        1. Both CP locations lie within the rocket length (physical
           bound: CP cannot be ahead of the nose tip or aft of the tail).
        2. Every component CN_alpha is positive (each element adds
           normal-force capability; a negative value would indicate a
           sign error in the area-ratio or sweep terms).
        3. The M=0 fin CN_alpha is within a factor of 2 of an
           independent low-aspect-ratio-wing estimate (Helmbold
           equation applied to the fin pair treated as an isolated
           planar wing of span ``2*s`` and area ``2*s*c``). A factor of
           2 (not +/-20%) is used because the two methods rest on
           different theoretical bases (cruciform, body-interference
           Barrowman fins vs. an isolated planar wing) and are only
           expected to agree in order of magnitude.

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        if self._geometry is None or "cp_subsonic_m" not in results:
            return False
        geometry = self._geometry

        for key in ("cp_subsonic_m", "cp_transonic_m"):
            if not (0.0 <= results[key] <= geometry.total_length_m):
                return False

        cn_fin_base, _ = fin_cn_alpha_base_and_cp(geometry)
        if cn_fin_base <= 0.0:
            return False

        span_pair = 2.0 * geometry.fin_span_m
        area_pair = 2.0 * geometry.fin_span_m * geometry.fin_root_chord_m
        aspect_ratio_pair = span_pair**2 / area_pair
        cl_alpha_pair = helmbold_cl_alpha(aspect_ratio_pair, geometry.fin_sweep_deg)
        a_ref = math.pi / 4.0 * geometry.d_ref_m**2
        cn_alpha_pair_ref = cl_alpha_pair * (area_pair / a_ref)
        # Two fin pairs (4 fins) contribute comparable order of magnitude.
        cn_fin_independent_estimate = 2.0 * cn_alpha_pair_ref

        ratio = cn_fin_base / cn_fin_independent_estimate
        if not (0.5 <= ratio <= 2.0):
            return False

        return True


def _geometry_to_dict(geometry: RocketGeometry) -> dict[str, float | int]:
    """Serialize :class:`RocketGeometry` to a JSON-friendly dict."""
    return {
        "d_ref_m": geometry.d_ref_m,
        "nose_length_m": geometry.nose_length_m,
        "nose_base_diameter_m": geometry.nose_base_diameter_m,
        "total_length_m": geometry.total_length_m,
        "transition_length_m": geometry.transition_length_m,
        "transition_start_m": geometry.transition_start_m,
        "fin_count": geometry.fin_count,
        "fin_span_m": geometry.fin_span_m,
        "fin_root_chord_m": geometry.fin_root_chord_m,
        "fin_tip_chord_m": geometry.fin_tip_chord_m,
        "fin_sweep_deg": geometry.fin_sweep_deg,
        "fin_root_le_x_m": geometry.fin_root_le_x_m,
        "cg_from_nose_m": geometry.cg_from_nose_m,
    }


def _components_to_dict(
    components: list[ComponentContribution],
) -> dict[str, dict[str, float]]:
    """Serialize component contributions to a JSON-friendly dict."""
    return {
        c.name: {"cn_alpha_per_rad": c.cn_alpha, "x_cp_m": c.x_cp_m} for c in components
    }


def _assumptions(geometry: RocketGeometry) -> list[str]:
    """Human-readable list of modeling assumptions for the JSON report."""
    return [
        (
            f"Nose CP factor {NOSE_CP_FACTOR} x L_nose applied to a conical nose per "
            "task specification; classical Barrowman value for a true cone is "
            "2/3 x L_nose (0.466 is the tangent-ogive value). Using 0.466 places "
            "the nose CP slightly forward, i.e. is a mildly conservative "
            "(less stable) choice for this cone."
        ),
        (
            f"Nose-to-body conical transition (shoulder, {geometry.nose_base_diameter_m} m "
            f"-> {geometry.d_ref_m} m) assumed to start at x = "
            f"{geometry.transition_start_m:.3f} m (aft of the nose) and to be "
            f"{geometry.transition_length_m:.3f} m long; this length is not present "
            "in the Fusion export and is an engineering assumption ('short')."
        ),
        (
            "Fin root leading edge placed at x = L_total - chord_root "
            f"= {geometry.fin_root_le_x_m:.4f} m, i.e. fins assumed mounted flush "
            "with the aft end of the rocket body (root trailing edge at the base)."
        ),
        (
            "Nose and transition CN_alpha are treated as Mach-invariant "
            "(slender-body theory, first order); only the fin CN_alpha receives "
            "the Prandtl-Glauert / transonic-bridge / Ackeret compressibility "
            "correction (see fin_mach_correction_factor)."
        ),
        (
            "Transonic band (0.8 <= Mach <= 1.2) is bridged by linear "
            "interpolation of the fin compressibility factor between its "
            "Mach-0.8 subsonic value and its Mach-1.2 supersonic value; no "
            "closed-form linear theory exists in this band. This is a "
            "low-order engineering estimate, not CFD, and should not be used "
            "for final flight-safety sign-off without wind-tunnel or CFD "
            "corroboration near Mach 1."
        ),
        (
            "Body-fin interference uses the Hoerner factor Kfb = 1 + R/(s+R); "
            "no fin-fin (cruciform panel-to-panel) interference is modeled."
        ),
    ]


def plot_cp_vs_mach(
    geometry: RocketGeometry,
    mach_min: float = MACH_SWEEP_MIN,
    mach_max: float = MACH_SWEEP_MAX,
    output_path: Path | str = CP_PLOT_PATH,
) -> Path:
    """Plot CP location, CG, and static margin vs. Mach number.

    Args:
        geometry: Rocket geometry.
        mach_min: Lower bound of the Mach sweep.
        mach_max: Upper bound of the Mach sweep.
        output_path: PNG output path (>= 150 DPI).

    Returns:
        Path to the saved PNG file.
    """
    mach_sub = np.linspace(mach_min, MACH_SUBSONIC_LIMIT, 40, endpoint=False)
    mach_trans = np.linspace(MACH_SUBSONIC_LIMIT, MACH_SUPERSONIC_LIMIT, 20)
    mach_sup = np.linspace(MACH_SUPERSONIC_LIMIT, mach_max, 60, endpoint=True)[1:]
    mach_values = np.concatenate([mach_sub, mach_trans, mach_sup])

    cp_values = np.array(
        [compute_stability_at_mach(geometry, float(m)).x_cp_m for m in mach_values]
    )
    sm_values = (cp_values - geometry.cg_from_nose_m) / geometry.d_ref_m

    fig, ax1 = plt.subplots(figsize=(8.0, 5.0), dpi=150)

    ax1.plot(mach_values, cp_values, color="#1f77b4", lw=2.0, label="CP location")
    ax1.axhline(
        geometry.cg_from_nose_m,
        color="#d62728",
        lw=1.5,
        ls="--",
        label=f"CG = {geometry.cg_from_nose_m:.3f} m",
    )
    ax1.axvspan(
        MACH_SUBSONIC_LIMIT,
        MACH_SUPERSONIC_LIMIT,
        color="grey",
        alpha=0.15,
        label="Transonic bridge (0.8-1.2)",
    )
    ax1.set_xlabel("Mach number [-]")
    ax1.set_ylabel("Axial position from nose tip [m]")
    ax1.set_xlim(mach_min, mach_max)
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(
        mach_values,
        sm_values,
        color="#2ca02c",
        lw=1.5,
        ls=":",
        label="Static margin [cal]",
    )
    ax2.set_ylabel("Static margin [calibers, (CP-CG)/d_ref]")

    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="best", fontsize=8)

    ax1.set_title("MELprop ramjet rocket -- CP vs. Mach (Barrowman + Rogers extension)")
    fig.tight_layout()

    output_path = Path(output_path)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def run(config_path: Path | str = DEFAULT_VEHICLE_CONFIG) -> dict[str, Any]:
    """Run the full analysis: compute results, write JSON, save the plot.

    Args:
        config_path: Path to the ramjet-rocket ``vehicle_config.yaml``.

    Returns:
        The JSON-serializable results dict (also written to
        ``barrowman_results.json``).
    """
    analysis = BarrowmanStabilityAnalysis()
    analysis.setup(config_path)
    results = analysis.execute()

    output = dict(results.data)
    output["verdict"] = results.metadata["verdict"]
    output["geometry"] = results.metadata["geometry"]
    output["component_breakdown_subsonic"] = results.metadata["component_breakdown_subsonic"]
    output["component_breakdown_transonic_m1"] = results.metadata[
        "component_breakdown_transonic_m1"
    ]
    output["assumptions"] = results.metadata["assumptions"]
    output["method"] = results.metadata["method"]

    RESULTS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_JSON_PATH.open("w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)

    plot_cp_vs_mach(analysis.geometry, output_path=CP_PLOT_PATH)

    return output


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
    print(f"\nVerdict: {result['verdict']} (margin = {result['margin_cal']:.3f} cal)")
    print(f"Results written to: {RESULTS_JSON_PATH}")
    print(f"Plot written to: {CP_PLOT_PATH}")
