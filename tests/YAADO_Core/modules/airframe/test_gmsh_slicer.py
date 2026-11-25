"""Tests for the STEP cross-section slicer."""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.airframe.containers import GmshSliceResults, StationSection
from YAADO_Core.modules.airframe.gmsh_process import GmshError, gmsh_problem
from YAADO_Core.modules.airframe.slicer_methods.gmsh import (
    GmshSliceAnalysis,
    SlicedModel,
    check_envelope,
    classify_face_loops,
    equivalent_diameter,
    expected_max_radius,
    format_sections_csv,
    plot_sections,
    station_positions,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
HARPOON_PATH = REPO_ROOT / "Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml"

needs_gmsh = pytest.mark.skipif(gmsh_problem() is not None, reason="Gmsh does not load here")

#: A 10 deg-like nose: 0.5 m cone on a 1.5 m tube of 0.2 m diameter.
BODY = {"type": "axisymmetric_body", "length": 2.0, "diameter": 0.2, "nose_type": "conical",
        "nose_length": 0.5}


def _vehicle(**body: object) -> BaseVehicleConfig:
    return BaseVehicleConfig.model_validate({"name": "Test", "bodies": {"tube": {**BODY, **body}}})


def _write_step(path: Path, build: Callable[[object], None]) -> Path:
    """Write a STEP file. Gmsh labels STEP coordinates as millimeters, so build in mm."""
    import gmsh

    gmsh.initialize(readConfigFiles=False, interruptible=False)
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("fixture")
        build(gmsh.model.occ)
        gmsh.model.occ.synchronize()
        gmsh.write(str(path))
    finally:
        gmsh.finalize()
    return path


def _rocket(occ: object) -> None:
    """Cone and tube with four 10 mm thick fins of 0.2 m span, in mm."""
    cone = occ.addCone(0, 0, 0, 500, 0, 0, 0, 100)  # type: ignore[attr-defined]
    tube = occ.addCylinder(500, 0, 0, 1500, 0, 0, 100)  # type: ignore[attr-defined]
    fins = []
    for k in range(4):
        fin = occ.addBox(1800, 0, -5, 200, 300, 10)  # type: ignore[attr-defined]
        occ.rotate([(3, fin)], 0, 0, 0, 1, 0, 0, k * math.pi / 2)  # type: ignore[attr-defined]
        fins.append((3, fin))
    occ.fuse([(3, cone)], [(3, tube), *fins])  # type: ignore[attr-defined]


def _run(step: Path, vehicle: BaseVehicleConfig | None = None, **settings: object) -> GmshSliceResults:
    analysis = GmshSliceAnalysis()
    analysis.setup(vehicle or _vehicle(), enable_logging=False, step_file=str(step), **settings)
    return analysis.execute()


def test_equivalent_diameter_of_a_circle() -> None:
    assert equivalent_diameter(math.pi * 0.15**2) == pytest.approx(0.3)
    assert equivalent_diameter(0.0) == 0.0


def test_stations_are_slice_centers() -> None:
    assert station_positions(2.0, 4) == pytest.approx((0.25, 0.75, 1.25, 1.75))


def test_the_largest_loop_is_the_outline_and_the_others_are_holes() -> None:
    def circle(radius: float, center: float = 0.0) -> np.ndarray:
        angle = np.linspace(0.0, 2.0 * np.pi, 33)
        return np.column_stack((center + radius * np.cos(angle), radius * np.sin(angle)))

    assert classify_face_loops([circle(0.1)]) == (0, [])
    assert classify_face_loops([circle(0.02), circle(0.1), circle(0.03, 0.05)]) == (1, [0, 2])
    with pytest.raises(ValueError, match="at least one"):
        classify_face_loops([])


def test_expected_radius_reaches_the_fin_tips() -> None:
    harpoon = BaseVehicleConfig.from_toml(HARPOON_PATH)
    # Body radius 0.1715 m plus the 0.285 m mid-body wing, against a 0.457 m half span
    assert expected_max_radius(harpoon) == pytest.approx(max(0.1715 + 0.285, 0.914 / 2.0))
    assert expected_max_radius(BaseVehicleConfig(name="Empty")) is None


def _model(length: float, radius: float) -> SlicedModel:
    """A constant cylinder sliced at ten stations."""
    area = math.pi * radius**2
    stations = tuple(
        StationSection(x, area, area, 2.0 * radius, radius, ()) for x in station_positions(length, 10)
    )
    return SlicedModel(1, length, area * length, 0.0, stations)


def test_envelope_checks_flag_only_the_dimension_that_differs() -> None:
    checks = {c.metric: c for c in check_envelope(_model(2.0, 0.1), _vehicle(), 0.05)}
    assert set(checks) == {"length", "max radius", "body diameter"}
    assert all(check.matches for check in checks.values())

    checks = {c.metric: c for c in check_envelope(_model(2.3, 0.1), _vehicle(), 0.05)}
    assert not checks["length"].matches
    assert checks["length"].difference == pytest.approx(0.15)
    assert checks["body diameter"].matches


def test_there_is_nothing_to_check_without_a_body() -> None:
    assert check_envelope(_model(2.0, 0.1), BaseVehicleConfig(name="Empty"), 0.05) == ()


@needs_gmsh
def test_a_hollow_tube_with_a_loose_part_inside(tmp_path: Path) -> None:
    """A 200/120 mm tube with a separate 100 mm grain: exact areas, and no double counting."""

    def build(occ: object) -> None:
        tube = occ.addCylinder(0, 0, 0, 2000, 0, 0, 100)  # type: ignore[attr-defined]
        bore = occ.addCylinder(-10, 0, 0, 2020, 0, 0, 60)  # type: ignore[attr-defined]
        occ.cut([(3, tube)], [(3, bore)])  # type: ignore[attr-defined]
        occ.addCylinder(300, 0, 0, 900, 0, 0, 50)  # type: ignore[attr-defined]

    results = _run(_write_step(tmp_path / "tube.step", build), n_stations=20)

    tube_area, grain_area = math.pi * (0.1**2 - 0.06**2), math.pi * 0.05**2
    assert results.n_solids == 2
    assert results.length == pytest.approx(2.0, abs=1e-5)
    assert results.volume == pytest.approx(2.0 * tube_area + 0.9 * grain_area, rel=1e-6)
    assert results.sliced_volume == pytest.approx(results.volume, rel=1e-5)
    assert results.max_outline_area == pytest.approx(math.pi * 0.1**2, rel=1e-6)
    assert results.outline_volume == pytest.approx(2.0 * math.pi * 0.1**2, rel=1e-5)
    assert results.has_holes
    middle = results.stations[8]
    assert [s.n_holes for s in middle.solids] == [1, 0]
    assert middle.solids[0].hole_area == pytest.approx(math.pi * 0.06**2, rel=1e-6)
    assert middle.area == pytest.approx(tube_area + grain_area, rel=1e-6)


@needs_gmsh
def test_a_finned_rocket_matches_its_vehicle(tmp_path: Path) -> None:
    fins = {"type": "fins", "count": 4, "span": 0.2, "sweep": 0.0, "chord_root": 0.2, "chord_tip": 0.2}
    vehicle = BaseVehicleConfig.model_validate(
        {"name": "Test", "bodies": {"tube": BODY}, "aero_surfaces": {"fins": fins}}
    )
    results = _run(_write_step(tmp_path / "rocket.step", _rocket), vehicle)

    first = results.stations[0]
    assert first.max_radius == pytest.approx(0.2 * first.x, rel=1e-3)
    # A 10 mm fin reaches 0.3 m, its corners slightly further
    assert results.max_radius == pytest.approx(math.hypot(0.3, 0.005), rel=1e-4)
    assert results.sliced_volume == pytest.approx(results.volume, rel=1e-3)
    assert [check.matches for check in results.checks] == [True, True, True]
    assert results.assumptions == ()
    assert results.units()["max_outline_area"] == "m^2"


@needs_gmsh
def test_axis_and_direction_do_not_change_the_sections(tmp_path: Path) -> None:
    straight = _run(_write_step(tmp_path / "x.step", _rocket), n_stations=8)

    def upright(occ: object) -> None:
        _rocket(occ)
        solids = occ.getEntities(3)  # type: ignore[attr-defined]
        occ.rotate(solids, 0, 0, 0, 0, 1, 0, math.pi / 2)  # type: ignore[attr-defined]
        occ.translate(solids, 0, 0, 700)  # type: ignore[attr-defined]

    # A +90 deg turn about y takes +x to -z: the nose is at the positive end of z
    turned = _run(
        _write_step(tmp_path / "z.step", upright), axis="z", reverse=True, n_stations=8
    )
    assert turned.length == pytest.approx(straight.length, rel=1e-5)
    for a, b in zip(straight.stations, turned.stations, strict=True):
        assert b.area == pytest.approx(a.area, rel=1e-4)
        assert b.max_radius == pytest.approx(a.max_radius, rel=1e-4)


@needs_gmsh
def test_mismatch_offset_and_coarse_stations_are_reported(tmp_path: Path) -> None:
    def build(occ: object) -> None:
        occ.addCone(0, 30, 0, 1000, 0, 0, 0, 100)  # type: ignore[attr-defined]

    results = _run(_write_step(tmp_path / "cone.step", build), n_stations=2)
    text = " ".join(results.assumptions)
    assert "use more stations" in text
    assert "0.03 m off the x axis" in text
    assert "length is 1 m, but the vehicle has 2 m (-50.0%)" in text


@needs_gmsh
def test_a_file_without_solids_is_refused(tmp_path: Path) -> None:
    def build(occ: object) -> None:
        occ.addRectangle(0, 0, 0, 100, 100)  # type: ignore[attr-defined]

    with pytest.raises(GmshError, match="holds no solid"):
        _run(_write_step(tmp_path / "surface.step", build))

    junk = tmp_path / "junk.step"
    junk.write_text("not a STEP file", encoding="utf-8")
    with pytest.raises(GmshError, match="cannot read"):
        _run(junk)


@needs_gmsh
def test_csv_and_figure(tmp_path: Path) -> None:
    results = _run(_write_step(tmp_path / "rocket.step", _rocket), n_stations=5)
    rows = list(csv.DictReader(io.StringIO(format_sections_csv(results))))
    assert len(rows) == 5
    assert float(rows[-1]["outline_area_m2"]) == pytest.approx(results.stations[-1].outline_area, rel=1e-4)

    import matplotlib.pyplot as plt

    figure = plot_sections(results)
    assert len(figure.axes) == 2
    plt.close(figure)


@needs_gmsh
@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"step_file": None}, "No STEP file"),
        ({"step_file": "missing.step"}, "does not exist"),
        ({"axis": "w"}, "axis must be"),
        ({"n_stations": 1}, "n_stations"),
        ({"tolerance": 0.0}, "tolerance"),
    ],
)
def test_bad_settings_are_refused(tmp_path: Path, settings: dict, message: str) -> None:
    step = tmp_path / "empty.step"
    step.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        GmshSliceAnalysis().setup(
            _vehicle(), enable_logging=False, **{"step_file": str(step), **settings}
        )


def test_unknown_settings_are_refused() -> None:
    with pytest.raises(TypeError, match="pitch"):
        GmshSliceAnalysis().setup(_vehicle(), enable_logging=False, pitch=0.1)
