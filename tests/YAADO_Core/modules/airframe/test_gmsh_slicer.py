"""Tests for the Gmsh station sweep: pure helpers and the typed analysis."""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import pytest

from YAADO_Core.ComponentStore.body import AxisymmetricBody
from YAADO_Core.Foundation.analysis_base import BaseAnalysis
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.airframe.containers import GmshSliceResults, StationSlice
from YAADO_Core.modules.airframe.slicer_methods.gmsh import (
    GmshStationSweepAnalysis,
    LoopTopology,
    build_station_slice,
    classify_face_loops,
    cross_check_against_body,
    equivalent_diameter_from_area,
    group_curves_into_loops,
)

OUTER_R_MM = 100.0
INNER_R_MM = 60.0
LENGTH_MM = 1000.0


def _vehicle(length: float = 1.0, diameter: float = 0.2) -> BaseVehicleConfig:
    body = AxisymmetricBody(length=length, diameter=diameter)
    return BaseVehicleConfig(name="tube", bodies={"body": body})


def _slice(x: float, radius: float) -> StationSlice:
    return StationSlice(
        x=x,
        volume_tag=1,
        area=math.pi * radius**2,
        n_loops=1,
        outer_equivalent_radius=radius,
        outer_bbox_radius=radius,
        has_inner_loop=False,
        inner_area=0.0,
        inner_equivalent_radius=0.0,
    )


@pytest.fixture
def tube_step(tmp_path: Path) -> Path:
    """Write a hollow tube (axis = X, mm) to STEP, or skip if gmsh/OCC is unusable."""
    gmsh = pytest.importorskip("gmsh")
    path = tmp_path / "tube.step"
    try:
        gmsh.initialize()
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("tube")
        outer = gmsh.model.occ.addCylinder(0, 0, 0, LENGTH_MM, 0, 0, OUTER_R_MM)
        inner = gmsh.model.occ.addCylinder(0, 0, 0, LENGTH_MM, 0, 0, INNER_R_MM)
        gmsh.model.occ.cut([(3, outer)], [(3, inner)])
        gmsh.model.occ.synchronize()
        gmsh.write(str(path))
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - depends on local gmsh build
        pytest.skip(f"gmsh OpenCASCADE unavailable: {exc}")
    finally:
        gmsh.finalize()
    return path


# -- pure helpers ------------------------------------------------------------


def test_equivalent_diameter() -> None:
    assert equivalent_diameter_from_area(math.pi * 25.0) == pytest.approx(10.0)
    assert equivalent_diameter_from_area(0.0) == 0.0
    assert equivalent_diameter_from_area(-1.0) == 0.0


def test_group_curves_into_loops() -> None:
    # Self-closed circle (points 1-1) plus a 3-curve triangle (points 2,3,4).
    edges = [(10, (1, 1)), (20, (2, 3)), (21, (3, 4)), (22, (4, 2))]
    loops = group_curves_into_loops(edges)
    assert sorted(sorted(loop) for loop in loops) == [[10], [20, 21, 22]]
    assert group_curves_into_loops([]) == []


def test_classify_face_loops_outer_and_inner() -> None:
    edges = [(1, (1, 1)), (2, (2, 2))]
    coords = {1: (100.0, 0.0), 2: (0.0, 60.0)}
    topo = classify_face_loops(edges, coords)
    assert topo.n_loops == 2 and topo.has_inner_loop
    assert topo.outer_curves == [1] and topo.inner_loops == [[2]]
    assert topo.outer_bbox_r_mm == pytest.approx(100.0)
    assert topo.inner_bbox_r_mm == pytest.approx(60.0)
    assert classify_face_loops([], {}).n_loops == 0


def test_build_station_slice_converts_to_si() -> None:
    topo = LoopTopology(2, True, [1], [[2]], 100.0, 60.0)
    s = build_station_slice(500.0, 3, 20000.0, topo)
    assert dataclasses.is_dataclass(s)
    assert s.x == pytest.approx(0.5)
    assert s.area == pytest.approx(0.02)
    assert s.outer_bbox_radius == pytest.approx(0.1)
    assert s.inner_equivalent_radius == pytest.approx(0.06)
    assert s.inner_area == pytest.approx(math.pi * 0.06**2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.x = 1.0  # type: ignore[misc]


def test_cross_check_against_body() -> None:
    body = AxisymmetricBody(length=1.0, diameter=0.2)
    stations = [_slice(0.0, 0.1), _slice(0.5, 0.1), _slice(1.0, 0.1)]
    checks = {c.metric: c for c in cross_check_against_body(stations, body)}
    assert checks["axial_extent"].verdict == "MATCH"
    assert checks["cylindrical_body_radius"].verdict == "MATCH"
    assert "max_radius" not in checks  # max_diameter unset

    bad = cross_check_against_body([_slice(0.0, 0.3), _slice(0.5, 0.3)], body)
    assert any(c.verdict == "MISMATCH" for c in bad)
    assert cross_check_against_body([], body) == ()


# -- analysis ----------------------------------------------------------------


def test_analysis_is_base_analysis_and_validates_setup(tmp_path: Path) -> None:
    analysis = GmshStationSweepAnalysis()
    assert isinstance(analysis, BaseAnalysis)
    with pytest.raises(RuntimeError):
        analysis.execute()
    with pytest.raises(ValueError, match="required"):
        analysis.setup(_vehicle(), enable_logging=False)
    with pytest.raises(ValueError, match="pitch"):
        analysis.setup(
            _vehicle(), enable_logging=False, step_path="a.step", x_end=1.0, pitch=0.0
        )
    with pytest.raises(ValueError, match="x_end"):
        analysis.setup(
            _vehicle(),
            enable_logging=False,
            step_path="a.step",
            x_start=1.0,
            x_end=0.5,
            pitch=0.1,
        )


def test_missing_step_file_raises(tmp_path: Path) -> None:
    analysis = GmshStationSweepAnalysis()
    analysis.setup(
        _vehicle(), enable_logging=False, step_path=tmp_path / "no.step", x_end=1.0, pitch=0.5
    )
    with pytest.raises(FileNotFoundError):
        analysis.execute()


def test_validate_results_rejects_empty() -> None:
    results = GmshSliceResults(
        name="x",
        fidelity=GmshStationSweepAnalysis.fidelity,
        max_outer_radius=0.0,
        max_area=0.0,
        axial_extent=0.0,
        station_count=0,
        has_inner_loops=False,
        stations=(),
        envelope_checks=(),
    )
    assert not GmshStationSweepAnalysis().validate_results(results)


def test_station_sweep_on_hollow_tube(tube_step: Path) -> None:
    analysis = GmshStationSweepAnalysis()
    analysis.setup(
        _vehicle(),
        enable_logging=False,
        step_path=tube_step,
        x_start=0.1,
        x_end=0.9,
        pitch=0.4,
    )
    results = analysis.execute()

    assert isinstance(results, GmshSliceResults)
    assert results.station_count == 3
    assert results.axial_extent == pytest.approx(0.8)
    assert results.has_inner_loops
    ring_area = math.pi * (0.1**2 - 0.06**2)
    for s in results.stations:
        assert s.area == pytest.approx(ring_area, rel=1e-3)
        assert s.n_loops == 2
        assert s.outer_bbox_radius == pytest.approx(0.1, rel=1e-3)
        assert s.inner_equivalent_radius == pytest.approx(0.06, rel=1e-3)
    assert results.max_outer_radius == pytest.approx(0.1, rel=1e-3)
    assert {c.metric for c in results.envelope_checks} >= {"cylindrical_body_radius"}
    assert results.scalars()["max_area"] == pytest.approx(ring_area, rel=1e-3)
