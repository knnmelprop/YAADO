"""Tests for resolving a vehicle's outer shape."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.airframe.outer_shape import (
    OuterShape,
    default_fin_roll,
    outer_shape_from_vehicle,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
HARPOON = REPO_ROOT / "Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml"
ALVRJ = REPO_ROOT / "Hangar/examples/ALVRJ/ALVRJ.toml"

BODY = {"type": "axisymmetric_body", "length": 2.0, "diameter": 0.2, "nose_type": "conical",
        "nose_length": 0.5}
FINS = {"type": "fins", "count": 4, "span": 0.1, "sweep": 45.0, "chord_root": 0.2, "chord_tip": 0.1}
WING = {"type": "wing", "aspect_ratio": 8.0, "sweep": 0.0, "taper_ratio": 0.5, "span": 2.4,
        "dihedral": 5.0, "airfoil_root": "NACA2412", "root_le_from_nose": 0.6}


def _vehicle(body: dict | None = None, **surfaces: dict) -> BaseVehicleConfig:
    return BaseVehicleConfig.model_validate(
        {"name": "Test", "bodies": {"tube": {**BODY, **(body or {})}}, "aero_surfaces": surfaces}
    )


def _shape(body: dict | None = None, **surfaces: dict) -> OuterShape:
    return outer_shape_from_vehicle(_vehicle(body, **surfaces))


def test_harpoon_leaves_out_only_the_unplaced_wing() -> None:
    shape = outer_shape_from_vehicle(BaseVehicleConfig.from_toml(HARPOON))
    assert {panel.surface for panel in shape.panels} == {"mid_body_wings", "aft_control_fins"}
    assert len(shape.panels) == 8
    assert shape.left_out == ("planar_equivalent",)
    tail = next(panel for panel in shape.panels if panel.surface == "aft_control_fins")
    assert tail.root_le == pytest.approx(3.84 - 0.4)
    assert tail.tip_le == pytest.approx(3.44 + 0.245)
    assert shape.has_symmetry_plane
    assert any("4.0% thick double wedge" in note for note in shape.assumptions)
    assert any("planar_equivalent" in note and "left out" in note for note in shape.assumptions)


def test_alvrj_resolves() -> None:
    shape = outer_shape_from_vehicle(BaseVehicleConfig.from_toml(ALVRJ))
    assert shape.left_out == ("intake_strakes",)
    assert shape.max_radius == pytest.approx(0.381 / 2.0 + 0.28)


@pytest.mark.parametrize(
    ("nose", "volume"),
    [
        ("conical", math.pi * 0.1**2 * 0.5 / 3.0),
        ("hemispherical", 2.0 * math.pi * 0.1**2 * 0.5 / 3.0),
        ("ogive", None),
    ],
)
def test_nose_volume_matches_its_profile(nose: str, volume: float | None) -> None:
    body = _shape({"nose_type": nose}).body
    x = np.linspace(0.0, 0.5, 20001)
    radii = np.array([body.radius_at(float(v)) for v in x])
    integral = float(np.trapezoid(math.pi * radii**2, x))
    cylinder = math.pi * 0.1**2 * 1.5
    assert body.volume - cylinder == pytest.approx(integral, rel=1e-4)
    if volume is not None:
        assert integral == pytest.approx(volume, rel=1e-4)
    assert body.radius_at(0.5) == pytest.approx(0.1)
    assert body.radius_at(-0.1) == body.radius_at(2.1) == 0.0


def test_an_ogive_meets_the_body_tangentially() -> None:
    body = _shape({"nose_type": "ogive"}).body
    assert body.radius_at(0.5 - 1e-4) == pytest.approx(0.1, abs=1e-7)


@pytest.mark.parametrize(
    ("count", "angles"),
    [(3, (0.0, 120.0, 240.0)), (4, (45.0, 135.0, 225.0, 315.0)), (6, (30.0, 90.0, 150.0, 210.0, 270.0, 330.0))],
)
def test_the_default_roll_is_symmetric(count: int, angles: tuple[float, ...]) -> None:
    shape = _shape(fins={**FINS, "count": count})
    assert default_fin_roll(count) == angles[0]
    assert tuple(panel.angle for panel in shape.panels) == pytest.approx(angles)
    assert shape.has_symmetry_plane


def test_a_rolled_or_cambered_fin_set_has_no_symmetry_plane() -> None:
    vehicle = _vehicle(fins=FINS)
    assert not outer_shape_from_vehicle(vehicle, fin_roll=20.0).has_symmetry_plane
    assert outer_shape_from_vehicle(vehicle, fin_roll=0.0).has_symmetry_plane
    assert not _shape(fins={**FINS, "airfoil": "NACA2412"}).has_symmetry_plane
    assert _shape(fins={**FINS, "airfoil": "NACA0010"}).has_symmetry_plane


def test_wing_halves_mirror_each_other_and_keep_the_upper_side_up() -> None:
    shape = _shape(wing=WING)
    starboard, port = shape.panels
    assert shape.has_symmetry_plane
    assert starboard.span_direction == pytest.approx(
        (0.0, math.cos(math.radians(5.0)), math.sin(math.radians(5.0)))
    )
    assert port.span_direction[1] == pytest.approx(-starboard.span_direction[1])
    assert starboard.normal[2] > 0.0 and port.normal[2] > 0.0
    # S = b^2/AR = 0.72 m^2; root chord 2 S / (b (1 + taper)) = 0.4 m
    assert (starboard.root_chord, starboard.tip_chord) == pytest.approx((0.4, 0.2))
    assert starboard.tip_le + 0.25 * 0.2 == pytest.approx(0.6 + 0.25 * 0.4)
    assert starboard.tip_offset * starboard.span_direction[1] == pytest.approx(1.2)


def test_fin_thickness_comes_from_the_component_before_the_setting() -> None:
    assert _shape(fins=FINS).panels[0].root_thickness == pytest.approx(0.04 * 0.2)
    assert _shape(fins={**FINS, "thickness_ratio": 0.08}).panels[0].root_thickness == pytest.approx(0.016)
    assert _shape(fins={**FINS, "airfoil": "NACA0010"}).panels[0].root_section.name == "NACA 0010"


def test_shape_choices_are_reported() -> None:
    text = " ".join(
        _shape(
            {"nose_diameter": 0.16, "max_diameter": 0.25, "total_length": 2.4},
            fins={**FINS, "chord_tip": 0.0, "root_le_from_nose": 1.9},
            canards={**FINS, "root_le_from_nose": 0.4},
        ).assumptions
    )
    for part in ("flat ring", "max_diameter 0.25", "total_length 2.4", "cut off", "behind the base", "on the nose"):
        assert part in text


@pytest.mark.parametrize(
    ("body", "surfaces", "message"),
    [
        ({"nose_length": None, "nose_type": "ogive"}, {}, "nose_length"),
        ({"nose_diameter": 0.3}, {}, "flare"),
        ({"nose_length": 2.0}, {}, "as long as the body"),
        ({"nose_length": 0.05, "nose_type": "ogive"}, {}, "shorter than its base radius"),
        ({}, {"a": FINS, "b": FINS}, "only one fin set"),
        ({}, {"a": {**FINS, "chord_tip": None}}, "chord_root and chord_tip"),
        ({}, {"a": {**FINS, "root_le_from_nose": 2.5}}, "outside the body"),
    ],
)
def test_incomplete_shapes_are_refused(body: dict, surfaces: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _shape(body, **surfaces)


def test_only_the_named_surfaces_take_part() -> None:
    vehicle = _vehicle(fins=FINS, wing=WING)
    shape = outer_shape_from_vehicle(vehicle, surfaces=("wing",))
    assert {panel.surface for panel in shape.panels} == {"wing"}
    assert shape.left_out == ("fins",)
    assert outer_shape_from_vehicle(vehicle, surfaces=()).panels == ()

    unplaced = _vehicle(wing={**WING, "root_le_from_nose": None})
    with pytest.raises(ValueError, match="root_le_from_nose"):
        outer_shape_from_vehicle(unplaced, surfaces=("wing",))
    with pytest.raises(KeyError):
        outer_shape_from_vehicle(unplaced, surfaces=("missing",))
