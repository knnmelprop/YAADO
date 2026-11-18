"""Typed result containers for wind tunnel analyses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from YAADO_Core.Foundation.analysis_base import BaseAnalysisResults
from YAADO_Core.Foundation.units import (
    Degrees,
    Dimensionless,
    Meters,
    MetersPerSecond,
    PerRadian,
)


@dataclass(frozen=True)
class AirfoilGeometry:
    """Section coordinates as XFOIL paneled them.

    Attributes:
        name: Airfoil name.
        x: Chordwise coordinates, trailing edge over the upper surface to the
            trailing edge over the lower surface (XFOIL order).
        y: Normal coordinates at each ``x``.
        thickness_to_chord: Maximum thickness over chord.
    """

    name: str
    x: tuple[Dimensionless, ...]
    y: tuple[Dimensionless, ...]
    thickness_to_chord: Dimensionless


@dataclass(frozen=True)
class SectionPolar:
    """Converged XFOIL points of one section at one Reynolds and Mach number.

    Attributes:
        reynolds: Chord Reynolds number.
        mach: Freestream Mach number of the Karman-Tsien correction.
        alpha: Angles of attack, ascending.
        cl: Lift coefficient.
        cd: Total (friction and pressure) drag coefficient.
        cdp: Pressure drag coefficient.
        cm: Quarter-chord pitching moment coefficient.
        xtr_top: Transition location on the upper surface, x/c.
        xtr_bottom: Transition location on the lower surface, x/c.
    """

    reynolds: Dimensionless
    mach: Dimensionless
    alpha: tuple[Degrees, ...]
    cl: tuple[Dimensionless, ...]
    cd: tuple[Dimensionless, ...]
    cdp: tuple[Dimensionless, ...]
    cm: tuple[Dimensionless, ...]
    xtr_top: tuple[Dimensionless, ...]
    xtr_bottom: tuple[Dimensionless, ...]

    @property
    def cl_over_cd(self) -> tuple[Dimensionless, ...]:
        """Lift-to-drag ratio at each angle of attack."""
        return tuple(cl / cd for cl, cd in zip(self.cl, self.cd, strict=True))


@dataclass(frozen=True)
class PolarMetrics:
    """Design numbers read off one section polar.

    Attributes:
        cl_max: Largest converged lift coefficient.
        alpha_cl_max: Angle of attack at ``cl_max``.
        stall_reached: Whether the lift falls after ``cl_max`` within the sweep.
        max_lift_to_drag: Largest lift-to-drag ratio.
        alpha_max_lift_to_drag: Angle of attack at ``max_lift_to_drag``.
        cd_min: Smallest drag coefficient.
        cl_at_cd_min: Lift coefficient at ``cd_min``.
        cl_alpha: Lift slope fitted near zero lift, or None without enough points.
        alpha_zero_lift: Zero-lift angle, or None if the lift does not change sign.
        cm_zero_lift: Pitching moment at zero lift, or None if the lift does not
            change sign.
    """

    cl_max: Dimensionless
    alpha_cl_max: Degrees
    stall_reached: bool
    max_lift_to_drag: Dimensionless
    alpha_max_lift_to_drag: Degrees
    cd_min: Dimensionless
    cl_at_cd_min: Dimensionless
    cl_alpha: PerRadian | None
    alpha_zero_lift: Degrees | None
    cm_zero_lift: Dimensionless | None


@dataclass(frozen=True)
class ReynoldsSweepPoint:
    """Polar of the same section at another Reynolds number.

    Attributes:
        polar: Converged XFOIL points.
        metrics: Design numbers of ``polar``.
    """

    polar: SectionPolar
    metrics: PolarMetrics


@dataclass(frozen=True)
class XfoilPolarResults(BaseAnalysisResults):
    """XFOIL polar of the section of one lifting surface at one flight condition.

    Attributes:
        surface: Name of the analysed component in ``vehicle.aero_surfaces``.
        airfoil: Airfoil as given: a NACA designation or a coordinate file.
        geometry: Section coordinates XFOIL analysed.
        thickness_to_chord: Maximum thickness over chord of ``geometry``.
        chord: Chord of the Reynolds number, the surface's mean aerodynamic chord
            unless overridden.
        altitude: ISA altitude of the flight condition.
        mach: Flight Mach number.
        velocity: Flight speed.
        reynolds: Chord Reynolds number.
        n_crit: e^n transition amplification exponent.
        alpha_requested: Angles of attack XFOIL was asked to solve.
        polar: Converged points.
        n_converged: Number of converged angles.
        cl_max: Largest converged lift coefficient.
        alpha_cl_max: Angle of attack at ``cl_max``.
        stall_reached: Whether the lift falls after ``cl_max`` within the sweep.
        max_lift_to_drag: Largest lift-to-drag ratio.
        alpha_max_lift_to_drag: Angle of attack at ``max_lift_to_drag``.
        cd_min: Smallest drag coefficient.
        cl_at_cd_min: Lift coefficient at ``cd_min``.
        cl_alpha: Lift slope fitted near zero lift.
        alpha_zero_lift: Zero-lift angle.
        cm_zero_lift: Quarter-chord pitching moment at zero lift.
        assumptions: Conditions that limit how far the results can be trusted.
    """

    HEADLINE_METRICS: ClassVar[tuple[str, ...]] = ("cl_max", "max_lift_to_drag", "cd_min")

    surface: str
    airfoil: str
    geometry: AirfoilGeometry
    thickness_to_chord: Dimensionless
    chord: Meters
    altitude: Meters
    mach: Dimensionless
    velocity: MetersPerSecond
    reynolds: Dimensionless
    n_crit: Dimensionless
    alpha_requested: tuple[Degrees, ...]
    polar: SectionPolar
    n_converged: int
    cl_max: Dimensionless
    alpha_cl_max: Degrees
    stall_reached: bool
    max_lift_to_drag: Dimensionless
    alpha_max_lift_to_drag: Degrees
    cd_min: Dimensionless
    cl_at_cd_min: Dimensionless
    cl_alpha: PerRadian | None
    alpha_zero_lift: Degrees | None
    cm_zero_lift: Dimensionless | None
    assumptions: tuple[str, ...]
