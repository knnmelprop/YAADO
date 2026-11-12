"""Supersonic airfoil and fin polars (Ackeret fallback).

Lifting surfaces are resolved from the vehicle via ``AERO_COMPONENTS``. At
supersonic Mach 1.5-3.5 a sharp double-wedge (diamond) section is assumed to
minimise wave drag.

**Why this is not an XFOIL wrapper in practice.** XFOIL is a panel +
integral boundary-layer method valid only for incompressible/weakly
compressible, subsonic-to-transonic flow (roughly Mach < 0.7-0.8). The
fin cruise regime (Mach 1.5-3.5) is *outside XFOIL's domain of validity
by construction* -- running XFOIL there would silently produce garbage,
not merely "unavailable" results. Outside its subsonic validity window we replace it with
the physically appropriate closed-form theory, **linearised supersonic
thin-airfoil (Ackeret) theory**, rather than attempting to force XFOIL
to run out of range.

:class:`XFOILAnalysis` therefore:

1. Checks :mod:`YAADO_Core.Foundation.solver_registry` for a registered ``xfoil`` binary.
   If present *and* the requested Mach were subsonic, it would delegate
   to XFOIL (left as a documented TODO -- no analysis currently
   asks XFOIL to run in its valid subsonic window, so no subprocess
   driver has been implemented yet; see ``TODO`` below).
2. For the supersonic fin regime targeted by this module (Mach 1.5-3.5),
   XFOIL is *never* invoked (it would be invalid), and the analysis
   always uses the Ackeret analytical fallback, emitting a
   ``warnings.warn`` that documents the fallback and its validity
   limits.

Ackeret linearized supersonic thin-airfoil theory (double-wedge section)
--------------------------------------------------------------------------
For a symmetric double-wedge (diamond) airfoil with maximum thickness at
mid-chord, each half-chord surface is a flat panel inclined at the wedge
half-angle ``tau = atan(t/c)`` (small-angle convention: ``t/c`` is the
tangent of the half-angle measured from the chord line, which is exact
for a symmetric diamond with the ridge at 50% chord). For a thin
symmetric section at angle of attack ``alpha`` in inviscid linearised
supersonic flow (Anderson, *Fundamentals of Aerodynamics*, chapter on
linearized supersonic flow):

    CL = 4 * alpha / sqrt(M^2 - 1)
    CD = 4 * (alpha^2 + tau^2) / sqrt(M^2 - 1)

with ``alpha`` and ``tau`` in radians. The ``alpha^2`` term is
wave drag due to lift, and the ``tau^2`` term is wave drag due to
thickness (form/wave drag of the symmetric double wedge at zero lift).
Both expressions require Ma > 1 (the ``sqrt(M^2 - 1)`` singularity means
the theory blows up approaching Mach 1 and is invalid below it); this
module additionally rejects Ma <= 1.05 as too close to the singularity
to trust the linearisation.

Theory reference:
    Anderson, J. D., *Fundamentals of Aerodynamics*, chapter "Linearized
    Supersonic Flow" (Ackeret's rule for thin-airfoil supersonic lift
    and wave drag). Ames Research Staff, "Equations, Tables, and Charts
    for Compressible Flow", NACA Report 1135 (1953).

TODO:
    * If a future analysis needs XFOIL in its valid subsonic
      window (e.g. fin section at low boost speeds), implement
      the subprocess driver here: emit an XFOIL command deck for the
      double-wedge coordinates, drive ``xfoil`` via subprocess with a
      batch command file, and parse the polar (CL, CD, CM vs alpha).
      A missing binary must then raise a clear error.
"""

from __future__ import annotations

import math
import re
import warnings
from collections.abc import Sequence
from typing import Any

from YAADO_Core.ComponentStore import AERO_COMPONENTS
from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.solver_registry import DEFAULT_REGISTRY
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.wind_tunnel.containers import (
    AirfoilPolarResults,
    PolarCurve,
    XfoilPolarResults,
)

#: Estimated t/c for surfaces whose schema carries no thickness or NACA 4-digit airfoil.
DEFAULT_THICKNESS_TO_CHORD = 0.06

DEFAULT_MACH_LIST: tuple[float, ...] = (1.5, 2.0, 2.5, 3.0, 3.5)
DEFAULT_ALPHA_DEG_LIST: tuple[float, ...] = (-10.0, -5.0, 0.0, 5.0, 10.0)

#: Ackeret validity window enforced in :meth:`XFOILAnalysis._setup`.
MIN_MACH = 1.5
MAX_MACH = 3.5
#: Reject Mach numbers at/below this value: sqrt(M^2-1) is singular at
#: M=1 and the linearisation is untrustworthy near/below it.
MIN_MACH_ABSOLUTE = 1.05
MIN_ALPHA_DEG = -10.0
MAX_ALPHA_DEG = 10.0

_NACA_4_DIGIT = re.compile(r"^NACA\s*(\d{4})$", re.IGNORECASE)


def ackeret_polar(mach: float, alpha_deg: float, t_c: float) -> tuple[float, float]:
    """Compute CL, CD for a symmetric double-wedge section (Ackeret theory).

    Args:
        mach: Freestream Mach number. Must satisfy ``mach > 1`` (checked
            by the caller; this function does not re-validate the full
            envelope so it can be reused for quick hand checks).
        alpha_deg: Angle of attack in degrees.
        t_c: Thickness-to-chord ratio of the double wedge. The wedge
            half-angle is ``tau = atan(t_c)`` (max thickness at
            mid-chord, symmetric diamond convention).

    Returns:
        Tuple ``(CL, CD)``, dimensionless.

    Raises:
        ValueError: If ``mach <= 1.0`` (Ackeret theory is undefined at
            and below Mach 1).
    """
    if mach <= 1.0:
        raise ValueError(f"Ackeret theory requires Mach > 1, got {mach}")

    alpha_rad = math.radians(alpha_deg)
    tau_rad = math.atan(t_c)
    beta = math.sqrt(mach**2 - 1.0)

    cl = 4.0 * alpha_rad / beta
    cd = 4.0 * (alpha_rad**2 + tau_rad**2) / beta
    return cl, cd


def naca_4_digit_thickness(designation: str | None) -> float | None:
    """Return the thickness-to-chord ratio encoded in a NACA 4-digit designation.

    Args:
        designation: Airfoil designation such as ``"NACA0006"`` or ``None``.

    Returns:
        ``t/c`` (e.g. 0.06 for ``NACA0006``), or None if the designation is
        missing or not a NACA 4-digit series.
    """
    if designation is None:
        return None
    match = _NACA_4_DIGIT.match(designation.strip())
    if match is None:
        return None
    return int(match.group(1)[2:]) / 100.0


class XFOILAnalysis(BaseAnalysis[XfoilPolarResults]):
    """Supersonic airfoil and fin polars via Ackeret linearised thin-airfoil theory.

    Despite the module name, this analysis does **not** drive the XFOIL
    binary in the supersonic regime: XFOIL is invalid at Mach 1.5-3.5 by
    construction (see module docstring). Linear analytical method ->
    ``FidelityLevel.LEVEL_1``.

    Example:
        analysis = XFOILAnalysis()
        analysis.setup(vehicle, mach_list=[2.0, 3.0])
        results = analysis.execute()
        best_l_over_d = results.max_lift_to_drag
    """

    fidelity = FidelityLevel.LEVEL_1

    def __init__(self, name: str = "xfoil_supersonic_polar") -> None:
        super().__init__(name)
        self._surfaces: dict[str, tuple[str | None, float]] = {}
        self._mach_list: tuple[float, ...] = DEFAULT_MACH_LIST
        self._alpha_deg_list: tuple[float, ...] = DEFAULT_ALPHA_DEG_LIST

    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        mach_list: Sequence[float] = DEFAULT_MACH_LIST,
        alpha_deg_list: Sequence[float] = DEFAULT_ALPHA_DEG_LIST,
        thickness_to_chord: float | None = None,
        component_names: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Resolve aerodynamic surfaces from the vehicle and validate the sweep.

        The double-wedge ``t/c`` of each surface is taken from
        ``thickness_to_chord`` if given, else from a NACA 4-digit
        ``airfoil_root``, else :data:`DEFAULT_THICKNESS_TO_CHORD` (estimate).

        Args:
            vehicle: Validated, vehicle-agnostic configuration.
            mach_list: Freestream Mach numbers [-], each in ``[MIN_MACH, MAX_MACH]``.
            alpha_deg_list: Angles of attack [deg], each in ``[MIN_ALPHA_DEG, MAX_ALPHA_DEG]``.
            thickness_to_chord: Optional ``t/c`` override [-] applied to all surfaces.
            component_names: Optional names of ``AERO_COMPONENTS`` to analyse.
                Defaults to every aerodynamic surface on the vehicle.
            **kwargs: Unused solver-specific settings.

        Raises:
            ValueError: If the vehicle has no aerodynamic surface, a Mach number or
                angle is outside its supported range, or ``thickness_to_chord <= 0``.
            ComponentNotFoundError: If a name in ``component_names`` is unknown.
            TypeError: If a named component is not an aerodynamic surface.
        """
        if component_names is None:
            components = vehicle.get_components_by_type(AERO_COMPONENTS)
        else:
            components = {
                name: vehicle.get_component(name, expected_type=AERO_COMPONENTS)
                for name in component_names
            }
        if not components:
            raise ValueError(
                f"Vehicle '{vehicle.name}' has no aerodynamic surfaces "
                "(fins or wings) to compute polars for"
            )

        if thickness_to_chord is not None and thickness_to_chord <= 0.0:
            raise ValueError(f"thickness_to_chord must be positive, got {thickness_to_chord}")

        for mach in mach_list:
            if mach <= MIN_MACH_ABSOLUTE:
                raise ValueError(
                    f"Mach {mach} too close to/below 1.0 (limit "
                    f"{MIN_MACH_ABSOLUTE}); Ackeret theory is singular at "
                    "Mach 1 and invalid in the transonic band"
                )
            if not (MIN_MACH <= mach <= MAX_MACH):
                raise ValueError(
                    f"Mach {mach} outside supported supersonic envelope "
                    f"[{MIN_MACH}, {MAX_MACH}]"
                )
        for alpha_deg in alpha_deg_list:
            if not (MIN_ALPHA_DEG <= alpha_deg <= MAX_ALPHA_DEG):
                raise ValueError(
                    f"alpha {alpha_deg} deg outside supported range "
                    f"[{MIN_ALPHA_DEG}, {MAX_ALPHA_DEG}] deg"
                )

        surfaces: dict[str, tuple[str | None, float]] = {}
        for name, component in components.items():
            airfoil: str | None = getattr(component, "airfoil_root", None)
            t_c = thickness_to_chord
            if t_c is None:
                t_c = naca_4_digit_thickness(airfoil) or DEFAULT_THICKNESS_TO_CHORD
            surfaces[name] = (airfoil, t_c)

        self._surfaces = surfaces
        self._mach_list = tuple(mach_list)
        self._alpha_deg_list = tuple(alpha_deg_list)

    def _compute(self) -> XfoilPolarResults:
        """Compute the Ackeret polar grid for every resolved surface.

        The ``xfoil`` binary is looked up for bookkeeping only: every accepted
        Mach number is supersonic, so XFOIL is never invoked and a missing
        binary is not an error.

        Returns:
            Typed polar results for all surfaces.
        """
        xfoil_available = (
            DEFAULT_REGISTRY.is_registered("xfoil") and DEFAULT_REGISTRY.get("xfoil").is_available()
        )
        warnings.warn(
            "XFOILAnalysis: Mach range is supersonic; XFOIL (a subsonic/transonic "
            "panel + boundary-layer code) is not valid here and is not invoked "
            f"(xfoil binary available={xfoil_available}). Using Ackeret linearised "
            "supersonic thin-airfoil theory (attached, inviscid, small-disturbance flow).",
            stacklevel=2,
        )

        airfoils: list[AirfoilPolarResults] = []
        for name, (airfoil, t_c) in self._surfaces.items():
            curves = []
            for mach in self._mach_list:
                coefficients = [ackeret_polar(mach, a, t_c) for a in self._alpha_deg_list]
                curves.append(
                    PolarCurve(
                        mach=mach,
                        alpha=self._alpha_deg_list,
                        cl=tuple(cl for cl, _ in coefficients),
                        cd=tuple(cd for _, cd in coefficients),
                    )
                )
            airfoils.append(AirfoilPolarResults(name, airfoil, t_c, tuple(curves)))

        all_curves = [curve for item in airfoils for curve in item.curves]
        ratios = [r for curve in all_curves for r in curve.cl_over_cd if not math.isnan(r)]
        return XfoilPolarResults(
            name=self.name,
            fidelity=self.fidelity,
            airfoils=tuple(airfoils),
            method="ackeret_linearized_supersonic",
            xfoil_binary_available=xfoil_available,
            max_lift_to_drag=max(ratios, default=0.0),
            min_drag_coefficient=min(cd for curve in all_curves for cd in curve.cd),
        )

    def validate_results(self, results: XfoilPolarResults) -> bool:
        """Recompute every polar point from the Ackeret formulas and compare."""
        if not results.airfoils:
            return False
        for item in results.airfoils:
            for curve in item.curves:
                for alpha, cl, cd in zip(curve.alpha, curve.cl, curve.cd):
                    expected_cl, expected_cd = ackeret_polar(
                        curve.mach, alpha, item.thickness_to_chord
                    )
                    if not (
                        math.isclose(cl, expected_cl, rel_tol=1e-9, abs_tol=1e-12)
                        and math.isclose(cd, expected_cd, rel_tol=1e-9, abs_tol=1e-12)
                    ):
                        return False
        return True
