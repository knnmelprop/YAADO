"""Outer shape of a vehicle in body axes, resolved from its components.

x runs aft from the nose tip, z up and y to starboard. Fins and wing halves become
panels: a root and a tip section joined by straight lines, at an angle around x measured
from up (0 deg) toward starboard (90 deg).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from YAADO_Core.ComponentStore import (
    AERO_COMPONENTS,
    BODY_COMPONENTS,
    FIN_COMPONENTS,
    AnyAeroComponent,
    AnyBodyComponent,
)
from YAADO_Core.Foundation.units import Degrees, Meters
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.airframe.airfoil_sections import (
    Section,
    double_wedge,
    section_from_airfoil,
)

NoseType = Literal["ogive", "conical", "hemispherical"]

#: Smallest tip chord over root chord; a pointed tip is cut off there.
MIN_TIP_CHORD_RATIO = 0.02
_ANGLE_TOLERANCE = 1e-6


@dataclass(frozen=True)
class BodyShape:
    """Axisymmetric body with a flat base.

    Attributes:
        name: Component name.
        length: Length from the nose tip to the base.
        radius: Radius behind the nose.
        nose_type: Nose shape.
        nose_length: Length of the nose.
        nose_radius: Radius at the base of the nose.
    """

    name: str
    length: Meters
    radius: Meters
    nose_type: NoseType
    nose_length: Meters
    nose_radius: Meters

    @property
    def ogive_radius(self) -> float:
        """Radius of the arc of a tangent ogive nose [m]."""
        return (self.nose_radius**2 + self.nose_length**2) / (2.0 * self.nose_radius)

    def radius_at(self, x: float) -> float:
        """Body radius at a station [m]; zero ahead of the nose and behind the base."""
        if not 0.0 <= x <= self.length:
            return 0.0
        if x >= self.nose_length:
            return self.radius
        if self.nose_type == "conical":
            return self.nose_radius * x / self.nose_length
        if self.nose_type == "ogive":
            rho = self.ogive_radius
            return math.sqrt(rho**2 - (self.nose_length - x) ** 2) + self.nose_radius - rho
        aft = 1.0 - x / self.nose_length
        return self.nose_radius * math.sqrt(1.0 - aft**2)

    @property
    def volume(self) -> float:
        """Enclosed volume [m^3]."""
        n, r, length = self.nose_radius, self.radius, self.nose_length
        cylinder = math.pi * r**2 * (self.length - length)
        if self.nose_type == "conical":
            return cylinder + math.pi * n**2 * length / 3.0
        if self.nose_type == "hemispherical":
            return cylinder + 2.0 * math.pi * n**2 * length / 3.0
        rho = self.ogive_radius
        offset = rho - n
        # Integral of pi (sqrt(rho^2 - u^2) - offset)^2 for u from 0 to the nose length
        integral = (
            (rho**2 + offset**2) * length
            - length**3 / 3.0
            - offset * (length * math.sqrt(rho**2 - length**2) + rho**2 * math.asin(length / rho))
        )
        return cylinder + math.pi * integral


@dataclass(frozen=True)
class Panel:
    """One fin or one wing half.

    Attributes:
        surface: Component name.
        is_wing: Whether the root is on the centerline instead of on the body surface.
        angle: Direction from root to tip around x, from up toward starboard.
        root_le: Axial position of the root leading edge.
        root_offset: Distance of the root section from the axis.
        root_chord: Root chord.
        tip_le: Axial position of the tip leading edge.
        tip_offset: Distance of the tip section from the axis.
        tip_chord: Tip chord.
        root_section: Section at the root.
        tip_section: Section at the tip.
    """

    surface: str
    is_wing: bool
    angle: Degrees
    root_le: Meters
    root_offset: Meters
    root_chord: Meters
    tip_le: Meters
    tip_offset: Meters
    tip_chord: Meters
    root_section: Section
    tip_section: Section

    @property
    def root_thickness(self) -> float:
        """Largest thickness of the root section [m]."""
        return self.root_section.thickness_to_chord * self.root_chord

    @property
    def mean_chord(self) -> float:
        """Mean of the root and tip chords [m]."""
        return (self.root_chord + self.tip_chord) / 2.0

    @property
    def span_direction(self) -> tuple[float, float, float]:
        """Unit vector from root to tip."""
        angle = math.radians(self.angle)
        return (0.0, math.sin(angle), math.cos(angle))

    @property
    def normal(self) -> tuple[float, float, float]:
        """Unit vector through the upper side of the section: up for a wing."""
        angle = math.radians(self.angle)
        sign = -1.0 if self.is_wing and math.sin(angle) < 0.0 else 1.0
        return (0.0, -sign * math.cos(angle), sign * math.sin(angle))


@dataclass(frozen=True)
class OuterShape:
    """Body and panels of a vehicle.

    Attributes:
        vehicle: Vehicle name.
        body: Axisymmetric body.
        panels: Fins and wing halves.
        left_out: Lifting surfaces that are not part of the shape.
        assumptions: Choices made where the vehicle leaves the shape open.
    """

    vehicle: str
    body: BodyShape
    panels: tuple[Panel, ...]
    left_out: tuple[str, ...]
    assumptions: tuple[str, ...]

    @property
    def has_symmetry_plane(self) -> bool:
        """Whether the plane y = 0 mirrors the shape onto itself."""
        return all(
            (panel.is_wing or panel.root_section.is_symmetric)
            and any(
                other.surface == panel.surface
                and math.isclose(
                    math.remainder(other.angle + panel.angle, 360.0), 0.0, abs_tol=_ANGLE_TOLERANCE
                )
                for other in self.panels
            )
            for panel in self.panels
        )

    @property
    def max_radius(self) -> float:
        """Largest distance of the shape from the axis, to mid-thickness of the tips [m]."""
        return max([self.body.radius, *(panel.tip_offset for panel in self.panels)])


def default_fin_roll(count: int) -> float:
    """Angle of the first fin from up [deg] that is symmetric about y = 0.

    An even set has no fin in the symmetry plane (a cross for four fins); an odd set has
    its first fin up.
    """
    return 180.0 / count if count % 2 == 0 else 0.0


def body_shape(name: str, body: AnyBodyComponent) -> tuple[BodyShape, list[str]]:
    """Resolve the shape of a body.

    Args:
        name: Component name.
        body: Axisymmetric body.

    Returns:
        The shape and the assumptions made.

    Raises:
        ValueError: If the nose is missing a length or does not fit the body.
    """
    assumptions: list[str] = []
    radius = body.diameter / 2.0
    nose_radius = radius if body.nose_diameter is None else body.nose_diameter / 2.0
    nose_length = body.nose_length
    if nose_length is None:
        if body.nose_type != "hemispherical":
            raise ValueError(f"Set nose_length on body '{name}': an {body.nose_type} nose needs it.")
        nose_length = nose_radius
    if nose_radius > radius * (1.0 + 1e-9):
        raise ValueError(
            f"Body '{name}': nose_diameter {2.0 * nose_radius:g} m is wider than the body "
            f"({body.diameter:g} m); a flare is not modeled."
        )
    if nose_length >= body.length:
        raise ValueError(f"Body '{name}': the nose ({nose_length:g} m) is as long as the body.")
    if body.nose_type == "ogive" and nose_length < nose_radius:
        raise ValueError(
            f"Body '{name}': an ogive nose cannot be shorter than its base radius; use hemispherical."
        )
    if nose_radius < radius * (1.0 - 1e-9):
        assumptions.append(
            f"The nose base is {2.0 * nose_radius:g} m wide and the body {body.diameter:g} m: "
            "the step between them is a flat ring."
        )
    if body.nose_type == "hemispherical" and not math.isclose(nose_length, nose_radius, rel_tol=0.01):
        assumptions.append(f"The hemispherical nose is a half ellipsoid {nose_length:g} m long.")
    if body.max_diameter is not None and body.max_diameter > body.diameter * 1.01:
        assumptions.append(
            f"max_diameter {body.max_diameter:g} m has no position: the body keeps {body.diameter:g} m."
        )
    if body.total_length is not None and body.total_length > body.length * 1.01:
        assumptions.append(
            f"Protrusions up to total_length {body.total_length:g} m are left out: "
            f"the body ends at {body.length:g} m."
        )
    shape = BodyShape(name, body.length, radius, body.nose_type, nose_length, nose_radius)
    return shape, assumptions


def _tip_chord(name: str, root_chord: float, tip_chord: float, assumptions: list[str]) -> float:
    """Tip chord, cut off to a meshable length where it is pointed."""
    smallest = MIN_TIP_CHORD_RATIO * root_chord
    if tip_chord >= smallest:
        return tip_chord
    assumptions.append(f"The pointed tip of '{name}' is cut off to a {smallest:.3g} m chord.")
    return smallest


def _fin_panels(
    name: str,
    fins: AnyAeroComponent,
    body: BodyShape,
    fin_roll: float | None,
    thickness_ratio: float,
    assumptions: list[str],
) -> list[Panel]:
    """Panels of one fin set."""
    assert isinstance(fins, FIN_COMPONENTS)
    if fins.chord_root is None or fins.chord_tip is None:
        raise ValueError(f"Set chord_root and chord_tip on fin set '{name}'.")
    root_le = fins.root_le_from_nose
    if root_le is None:
        root_le = body.length - fins.chord_root
        assumptions.append(
            f"Fin set '{name}' has no root_le_from_nose: placed flush with the aft end."
        )
    if not 0.0 <= root_le < body.length:
        raise ValueError(
            f"Fin set '{name}': root leading edge at {root_le:g} m is outside the body "
            f"(0 to {body.length:g} m)."
        )
    if root_le < body.nose_length:
        assumptions.append(
            f"Fin set '{name}' starts on the nose: its root is extended straight to the nose surface."
        )
    overhang = root_le + fins.chord_root - body.length
    if overhang > 1e-6:
        assumptions.append(f"The roots of '{name}' reach {overhang:.3g} m behind the base.")
    if fins.airfoil is not None:
        section = section_from_airfoil(fins.airfoil)
    else:
        ratio = fins.thickness_ratio
        if ratio is None:
            ratio = thickness_ratio
            assumptions.append(
                f"Fin set '{name}' has no airfoil or thickness_ratio: a {ratio:.1%} thick double "
                "wedge is assumed."
            )
        section = double_wedge(ratio)
    roll = default_fin_roll(fins.count) if fin_roll is None else fin_roll
    tip_chord = _tip_chord(name, fins.chord_root, fins.chord_tip, assumptions)
    return [
        Panel(
            surface=name,
            is_wing=False,
            angle=(roll + k * 360.0 / fins.count) % 360.0,
            root_le=root_le,
            root_offset=body.radius,
            root_chord=fins.chord_root,
            tip_le=root_le + fins.span * math.tan(math.radians(fins.sweep)),
            tip_offset=body.radius + fins.span,
            tip_chord=tip_chord,
            root_section=section,
            tip_section=section,
        )
        for k in range(fins.count)
    ]


def _wing_panels(
    name: str, wing: AnyAeroComponent, assumptions: list[str]
) -> list[Panel]:
    """Panels of the two halves of a wing at mid-height of the body."""
    assert not isinstance(wing, FIN_COMPONENTS)
    assert wing.root_le_from_nose is not None
    half_span = wing.span / 2.0
    area = wing.span**2 / wing.aspect_ratio
    root_chord = 2.0 * area / (wing.span * (1.0 + wing.taper_ratio))
    tip_chord = _tip_chord(name, root_chord, root_chord * wing.taper_ratio, assumptions)
    # Sweep is given at the quarter chord
    tip_le = (
        wing.root_le_from_nose
        + half_span * math.tan(math.radians(wing.sweep))
        + 0.25 * (root_chord - tip_chord)
    )
    assumptions.append(f"Wing '{name}' is mounted at mid-height without twist or incidence.")
    root_section = section_from_airfoil(wing.airfoil_root)
    tip_section = section_from_airfoil(wing.airfoil_tip or wing.airfoil_root)
    return [
        Panel(
            surface=name,
            is_wing=True,
            angle=side * (90.0 - wing.dihedral),
            root_le=wing.root_le_from_nose,
            root_offset=0.0,
            root_chord=root_chord,
            tip_le=tip_le,
            tip_offset=half_span / math.cos(math.radians(wing.dihedral)),
            tip_chord=tip_chord,
            root_section=root_section,
            tip_section=tip_section,
        )
        for side in (1.0, -1.0)
    ]


def outer_shape_from_vehicle(
    vehicle: BaseVehicleConfig,
    *,
    body_name: str | None = None,
    surfaces: tuple[str, ...] | None = None,
    fin_roll: float | None = None,
    fin_thickness_ratio: float = 0.04,
) -> OuterShape:
    """Resolve the outer shape of a vehicle.

    Every fin set takes part; at most one may lack ``root_le_from_nose``, which places it
    flush with the aft end. A wing without ``root_le_from_nose`` is left out.

    Args:
        vehicle: Vehicle with one axisymmetric body.
        body_name: Body to use if the vehicle has more than one.
        surfaces: Lifting surfaces to include. Defaults to every one that is placed.
        fin_roll: Angle of the first fin of every set from up [deg]. Defaults to
            :func:`default_fin_roll`.
        fin_thickness_ratio: Thickness over chord of fins with neither an airfoil nor a
            ``thickness_ratio``.

    Returns:
        The shape.

    Raises:
        KeyError: If ``surfaces`` names an unknown component.
        TypeError: If ``surfaces`` names a component that is not a lifting surface.
        ValueError: If a component lacks data the shape needs.
    """
    body = vehicle.find_single_component(BODY_COMPONENTS, body_name)
    name = next(key for key, component in vehicle.bodies.items() if component is body)
    shape, assumptions = body_shape(name, body)

    available = vehicle.get_components_by_type(AERO_COMPONENTS)
    chosen = {
        key: vehicle.get_component(key, expected_type=AERO_COMPONENTS)
        for key in (available if surfaces is None else surfaces)
    }
    unplaced_fins = sorted(
        key
        for key, component in chosen.items()
        if isinstance(component, FIN_COMPONENTS) and component.root_le_from_nose is None
    )
    if len(unplaced_fins) > 1:
        raise ValueError(
            f"Set root_le_from_nose on fin sets {', '.join(unplaced_fins)}: only one fin set can "
            "default to the aft end of the body."
        )

    panels: list[Panel] = []
    left_out = [key for key in available if key not in chosen]
    for key, component in chosen.items():
        if isinstance(component, FIN_COMPONENTS):
            panels += _fin_panels(key, component, shape, fin_roll, fin_thickness_ratio, assumptions)
        elif component.root_le_from_nose is None:
            if surfaces is not None:
                raise ValueError(f"Set root_le_from_nose on wing '{key}' to place it on the body.")
            left_out.append(key)
            assumptions.append(f"Wing '{key}' has no root_le_from_nose: it is left out.")
        else:
            panels += _wing_panels(key, component, assumptions)
    return OuterShape(vehicle.name, shape, tuple(panels), tuple(sorted(left_out)), tuple(assumptions))
