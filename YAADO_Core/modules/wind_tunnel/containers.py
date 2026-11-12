"""Typed result containers for wind tunnel analyses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from YAADO_Core.Foundation.analysis_base import BaseAnalysisResults
from YAADO_Core.Foundation.units import Degrees, Dimensionless


@dataclass(frozen=True)
class PolarCurve:
    """Lift and drag coefficients versus angle of attack at one Mach number.

    Attributes:
        mach: Freestream Mach number.
        alpha: Angles of attack.
        cl: Lift coefficient at each angle of attack.
        cd: Drag coefficient at each angle of attack.
    """

    mach: Dimensionless
    alpha: tuple[Degrees, ...]
    cl: tuple[Dimensionless, ...]
    cd: tuple[Dimensionless, ...]

    @property
    def cl_over_cd(self) -> tuple[Dimensionless, ...]:
        """Lift-to-drag ratio at each angle of attack (NaN where ``cd`` is zero)."""
        return tuple(cl / cd if cd != 0.0 else float("nan") for cl, cd in zip(self.cl, self.cd))


@dataclass(frozen=True)
class AirfoilPolarResults:
    """Polar curves of one aerodynamic surface section.

    Attributes:
        component_name: Name of the component in ``vehicle.aero_surfaces``.
        airfoil: Airfoil designation if the component defines one, else None.
        thickness_to_chord: Double-wedge thickness-to-chord ratio used.
        curves: One polar curve per Mach number.
    """

    component_name: str
    airfoil: str | None
    thickness_to_chord: Dimensionless
    curves: tuple[PolarCurve, ...]


@dataclass(frozen=True)
class XfoilPolarResults(BaseAnalysisResults):
    """Outputs of the airfoil polar analysis.

    Attributes:
        airfoils: Polar results for every analysed aerodynamic surface.
        method: Calculation method that produced the polars.
        xfoil_binary_available: Whether an ``xfoil`` executable was found.
        max_lift_to_drag: Largest ``CL/CD`` over all surfaces, Mach numbers and angles.
        min_drag_coefficient: Smallest ``CD`` over all surfaces, Mach numbers and angles.
    """

    HEADLINE_METRICS: ClassVar[tuple[str, ...]] = ("max_lift_to_drag", "min_drag_coefficient")

    airfoils: tuple[AirfoilPolarResults, ...]
    method: str
    xfoil_binary_available: bool
    max_lift_to_drag: Dimensionless
    min_drag_coefficient: Dimensionless
