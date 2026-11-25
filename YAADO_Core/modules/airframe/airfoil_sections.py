"""Sections of fins and wings as closed outlines with a sharp trailing edge."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from YAADO_Core.modules.wind_tunnel.methods.xfoil.xfoil_runner import resolve_airfoil

#: Points on each side of a curved section.
POINTS_PER_SIDE = 41
#: NACA 5-digit mean line: max camber position digits -> (m, k1) for a design lift of 0.3.
_FIVE_DIGIT_MEAN_LINES: dict[str, tuple[float, float]] = {
    "10": (0.0580, 361.4),
    "20": (0.1260, 51.64),
    "30": (0.2025, 15.957),
    "40": (0.2900, 6.643),
    "50": (0.3910, 3.230),
}
_MIN_SPACING = 1e-4

Point = tuple[float, float]


@dataclass(frozen=True)
class Section:
    """Outline of a section, scaled to unit chord.

    Attributes:
        name: Section name.
        upper: (x, z) points of the upper side from the leading to the trailing edge.
        lower: (x, z) points of the lower side, with the same end points as ``upper``.
        straight: Whether the points are joined by straight lines instead of a curve.
        leading_edge_radius: Nose radius over chord, 0 for a sharp leading edge.
    """

    name: str
    upper: tuple[Point, ...]
    lower: tuple[Point, ...]
    straight: bool
    leading_edge_radius: float

    @property
    def thickness_to_chord(self) -> float:
        """Largest thickness over chord."""
        grid = np.linspace(0.0, 1.0, 401)
        upper, lower = (np.array(sorted(side)) for side in (self.upper, self.lower))
        heights = [np.interp(grid, side[:, 0], side[:, 1]) for side in (upper, lower)]
        return float(np.max(heights[0] - heights[1]))

    @property
    def is_symmetric(self) -> bool:
        """Whether the lower side mirrors the upper side."""
        return len(self.upper) == len(self.lower) and all(
            math.isclose(xu, xl, abs_tol=1e-9) and math.isclose(zu, -zl, abs_tol=1e-9)
            for (xu, zu), (xl, zl) in zip(self.upper, self.lower, strict=True)
        )


def double_wedge(thickness_ratio: float) -> Section:
    """Diamond section with its largest thickness at mid-chord.

    Args:
        thickness_ratio: Largest thickness over chord.

    Returns:
        The section.

    Raises:
        ValueError: If ``thickness_ratio`` is not within 0 and 0.5.
    """
    if not 0.0 < thickness_ratio < 0.5:
        raise ValueError(f"The thickness ratio must be within 0 and 0.5, got {thickness_ratio}")
    half = thickness_ratio / 2.0
    return Section(
        name=f"double wedge {thickness_ratio:.1%}",
        upper=((0.0, 0.0), (0.5, half), (1.0, 0.0)),
        lower=((0.0, 0.0), (0.5, -half), (1.0, 0.0)),
        straight=True,
        leading_edge_radius=0.0,
    )


def _cosine_stations() -> np.ndarray:
    """Chord stations clustered at both edges."""
    return 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, POINTS_PER_SIDE)))


def naca_section(digits: str) -> Section:
    """NACA 4-digit or 5-digit section with a closed trailing edge.

    Args:
        digits: Digits of the designation, such as ``"2412"`` or ``"23012"``.

    Returns:
        The section.

    Raises:
        ValueError: If the digits are not a 4-digit or a standard 5-digit section.

    Reference:
        Abbott, I. H. and von Doenhoff, A. E., "Theory of Wing Sections", Dover, 1959,
        chapter 6. The last thickness coefficient is -0.1036 to close the trailing edge.
    """
    x = _cosine_stations()
    if re.fullmatch(r"\d{4}", digits):
        m, p = int(digits[0]) / 100.0, int(digits[1]) / 10.0
        if m > 0.0 and p > 0.0:
            fore = x < p
            camber = np.where(
                fore,
                m / p**2 * (2.0 * p * x - x**2),
                m / (1.0 - p) ** 2 * (1.0 - 2.0 * p + 2.0 * p * x - x**2),
            )
            slope = np.where(
                fore, 2.0 * m / p**2 * (p - x), 2.0 * m / (1.0 - p) ** 2 * (p - x)
            )
        else:
            camber = slope = np.zeros_like(x)
    elif re.fullmatch(r"\d{5}", digits) and digits[1:3] in _FIVE_DIGIT_MEAN_LINES:
        r, k1 = _FIVE_DIGIT_MEAN_LINES[digits[1:3]]
        k1 *= int(digits[0]) / 2.0
        fore = x < r
        camber = np.where(
            fore,
            k1 / 6.0 * (x**3 - 3.0 * r * x**2 + r**2 * (3.0 - r) * x),
            k1 * r**3 / 6.0 * (1.0 - x),
        )
        slope = np.where(
            fore,
            k1 / 6.0 * (3.0 * x**2 - 6.0 * r * x + r**2 * (3.0 - r)),
            -k1 * r**3 / 6.0,
        )
    else:
        raise ValueError(
            f"NACA {digits} is not a 4-digit or standard 5-digit section; use a coordinate file"
        )

    t = int(digits[-2:]) / 100.0
    if t <= 0.0:
        raise ValueError(f"NACA {digits} has no thickness")
    half = 5.0 * t * (
        0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4
    )
    half[-1] = 0.0
    theta = np.arctan(slope)
    upper = zip(x - half * np.sin(theta), camber + half * np.cos(theta), strict=True)
    lower = zip(x + half * np.sin(theta), camber - half * np.cos(theta), strict=True)
    return Section(
        name=f"NACA {digits}",
        upper=tuple((float(a), float(b)) for a, b in upper),
        lower=tuple((float(a), float(b)) for a, b in lower),
        straight=False,
        leading_edge_radius=1.1019 * t**2,
    )


def _thin_out(points: list[Point]) -> list[Point]:
    """Drop points closer than :data:`_MIN_SPACING` to the one before, keeping both ends."""
    kept = [points[0]]
    for point in points[1:-1]:
        if math.dist(point, kept[-1]) > _MIN_SPACING and math.dist(point, points[-1]) > _MIN_SPACING:
            kept.append(point)
    return [*kept, points[-1]]


def section_from_coordinates(name: str, coordinates: Sequence[Point]) -> Section:
    """Section from airfoil coordinates in Selig order, scaled to unit chord.

    A blunt trailing edge is closed by taking half of the gap off each side, growing
    linearly from the leading edge.

    Args:
        name: Section name.
        coordinates: (x, y) points from the trailing edge over the upper side to the
            leading edge, and back over the lower side.

    Returns:
        The section.

    Raises:
        ValueError: If the points do not run around a leading edge.
    """
    points = np.asarray(coordinates, dtype=float)
    le = int(np.argmin(points[:, 0]))
    chord = float(points[:, 0].max() - points[le, 0])
    if not 2 <= le <= len(points) - 3 or chord <= 0.0:
        raise ValueError(f"Airfoil '{name}' does not run around a leading edge")
    unit = (points - points[le]) / chord
    upper, lower = unit[: le + 1][::-1].copy(), unit[le:].copy()
    if upper[:, 1].mean() < lower[:, 1].mean():
        upper, lower = lower, upper
    trailing_edge = (upper[-1] + lower[-1]) / 2.0
    for side in (upper, lower):
        gap = trailing_edge - side[-1]
        side += side[:, :1] / side[-1, 0] * gap

    nose = upper[1 : max(3, len(upper) // 8)]
    radius = float(np.median((nose**2).sum(axis=1) / (2.0 * nose[:, 0])))
    sides = [_thin_out([(float(x), float(z)) for x, z in side]) for side in (upper, lower)]
    return Section(
        name=name,
        upper=tuple(sides[0]),
        lower=tuple(sides[1]),
        straight=False,
        leading_edge_radius=min(radius, 0.1),
    )


def section_from_airfoil(airfoil: str) -> Section:
    """Section of a component's airfoil setting.

    Args:
        airfoil: A NACA designation or the path of a coordinate file.

    Returns:
        The section.

    Raises:
        ValueError: If the airfoil cannot be resolved.
    """
    source = resolve_airfoil(airfoil)
    if source.naca_digits is not None:
        return naca_section(source.naca_digits)
    return section_from_coordinates(source.name, source.coordinates)
