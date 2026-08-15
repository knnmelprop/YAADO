# MELprop-IADE | tests.unit.test_geometry_station_sweep | v0.1.0
"""Unit tests for analyses.geometry.cad_station_sweep.

Pure-Python helpers are tested with hand-built synthetic data (no gmsh
needed). One integration test builds synthetic gmsh solids (a solid
cylinder and a hollow tube via cut) to validate the loop/hole detection
against a real gmsh OCC session end-to-end, without any dependency on the
proprietary ``ramPcfdSimplified.step`` file; it is skipped cleanly if
``gmsh`` is not installed in the running environment.
"""

from __future__ import annotations

import math

import pytest

from IADE_Core.modules.geometry.cad_station_sweep import (
    CrossCheckResult,
    LoopTopology,
    classify_face_loops,
    cross_check_against_vehicle_config,
    equivalent_diameter_from_area,
    group_curves_into_loops,
)

try:
    import gmsh

    HAS_GMSH = True
except ImportError:
    HAS_GMSH = False


# ---------------------------------------------------------------------------
# equivalent_diameter_from_area
# ---------------------------------------------------------------------------


def test_equivalent_diameter_from_area_known_circle():
    """A circle of radius 10mm has area pi*100mm^2 and diameter 20mm."""
    area_mm2 = math.pi * 10.0**2
    assert equivalent_diameter_from_area(area_mm2) == pytest.approx(20.0)


def test_equivalent_diameter_from_area_zero_and_negative():
    """Non-positive area returns 0.0 rather than raising."""
    assert equivalent_diameter_from_area(0.0) == 0.0
    assert equivalent_diameter_from_area(-5.0) == 0.0


# ---------------------------------------------------------------------------
# group_curves_into_loops
# ---------------------------------------------------------------------------


def test_group_curves_single_triangle_loop():
    """Three curves sharing endpoints pairwise form one closed loop."""
    edges = [(1, (10, 11)), (2, (11, 12)), (3, (12, 10))]
    loops = group_curves_into_loops(edges)
    assert len(loops) == 1
    assert sorted(loops[0]) == [1, 2, 3]


def test_group_curves_two_disjoint_loops():
    """Two independent closed curves (e.g. two circles) form two loops."""
    edges = [(1, (10, 10)), (2, (20, 20))]
    loops = group_curves_into_loops(edges)
    assert len(loops) == 2
    loop_sets = {tuple(sorted(loop)) for loop in loops}
    assert loop_sets == {(1,), (2,)}


def test_group_curves_square_with_separate_hole_loop():
    """A square outer boundary plus a disjoint circular hole = 2 loops."""
    edges = [
        (1, (1, 2)),
        (2, (2, 3)),
        (3, (3, 4)),
        (4, (4, 1)),
        (5, (100, 100)),  # inner circle, degenerate self-loop point
    ]
    loops = group_curves_into_loops(edges)
    assert len(loops) == 2
    sizes = sorted(len(loop) for loop in loops)
    assert sizes == [1, 4]


def test_group_curves_empty_input():
    assert group_curves_into_loops([]) == []


# ---------------------------------------------------------------------------
# classify_face_loops
# ---------------------------------------------------------------------------


def test_classify_face_loops_no_hole():
    """A single closed loop classifies as outer-only, no inner loop."""
    edges = [(1, (10, 10))]
    point_coords = {10: (20.0, 0.0)}
    topology = classify_face_loops(edges, point_coords)
    assert topology.n_loops == 1
    assert not topology.has_inner_loop
    assert topology.outer_bbox_r_mm == pytest.approx(20.0)
    assert topology.inner_bbox_r_mm == 0.0
    assert topology.inner_loops == []


def test_classify_face_loops_with_hole_picks_larger_extent_as_outer():
    """Outer loop = larger radial extent; inner (hole) = smaller extent."""
    edges = [(1, (10, 10)), (2, (20, 20))]
    point_coords = {10: (50.0, 0.0), 20: (10.0, 0.0)}
    topology = classify_face_loops(edges, point_coords)
    assert topology.n_loops == 2
    assert topology.has_inner_loop
    assert topology.outer_curves == [1]
    assert topology.inner_loops == [[2]]
    assert topology.outer_bbox_r_mm == pytest.approx(50.0)
    assert topology.inner_bbox_r_mm == pytest.approx(10.0)


def test_classify_face_loops_star_shape_single_loop_no_false_hole():
    """A star/fin cross-section (one loop, irregular extent) is not a hole."""
    edges = [(1, (1, 2)), (2, (2, 3)), (3, (3, 1))]
    point_coords = {1: (5.0, 0.0), 2: (0.0, 30.0), 3: (-5.0, 0.0)}
    topology = classify_face_loops(edges, point_coords)
    assert topology.n_loops == 1
    assert not topology.has_inner_loop


def test_classify_face_loops_empty_input():
    topology = classify_face_loops([], {})
    assert topology.n_loops == 0
    assert not topology.has_inner_loop


# ---------------------------------------------------------------------------
# cross_check_against_vehicle_config
# ---------------------------------------------------------------------------

REPO_ROOT_VEHICLE_CONFIG = (
    __import__("pathlib").Path(__file__).resolve().parents[4]
    / "Hangar"
    / "ramjet_rocket"
    / "vehicle_config.yaml"
)


def test_cross_check_reports_match_for_consistent_synthetic_rows():
    """Rows whose envelope matches the real config's body dims -> MATCH.

    ``body.diameter_m = 0.200m`` -> r=100mm (cylindrical section);
    ``body.total_length_m = 4.35501m``. Note ``max_radius_mm`` is *not*
    asserted MATCH here: the real config's ``body.max_diameter_m``
    (0.639m) includes the booster's PRD-240 wing bbox, which these
    body-only synthetic rows deliberately don't represent -- exercising
    that the helper correctly flags a genuine mismatch, not a test bug.
    """
    rows = [
        {"x_mm": 500.0, "outer_bbox_r_mm": 100.0},
        {"x_mm": 4355.0, "outer_bbox_r_mm": 100.0},
    ]
    results = cross_check_against_vehicle_config(
        rows, REPO_ROOT_VEHICLE_CONFIG, tolerance_pct=15.0
    )
    assert results
    by_metric = {r.metric: r for r in results}
    assert isinstance(by_metric["axial_extent_mm"], CrossCheckResult)
    assert by_metric["axial_extent_mm"].verdict == "MATCH"
    assert by_metric["cylindrical_body_radius_mm"].verdict == "MATCH"


def test_cross_check_reports_mismatch_for_inconsistent_rows():
    """Wildly-off envelope numbers must be flagged MISMATCH, not silently accepted."""
    rows = [
        {"x_mm": 0.0, "outer_bbox_r_mm": 9999.0},
        {"x_mm": 1.0, "outer_bbox_r_mm": 9999.0},
    ]
    results = cross_check_against_vehicle_config(
        rows, REPO_ROOT_VEHICLE_CONFIG, tolerance_pct=10.0
    )
    assert results
    assert all(r.verdict == "MISMATCH" for r in results if r.metric == "max_radius_mm")


def test_cross_check_empty_rows_returns_empty():
    assert cross_check_against_vehicle_config([], REPO_ROOT_VEHICLE_CONFIG) == []


def test_cross_check_rejects_non_rocket_config(tmp_path):
    """A non-RocketConfig YAML (e.g. GTM-140 drone) must raise TypeError."""
    drone_config = (
        __import__("pathlib").Path(__file__).resolve().parents[4]
        / "Hangar"
        / "gtm140_drone"
        / "vehicle_config.yaml"
    )
    if not drone_config.is_file():
        pytest.skip("gtm140_drone vehicle_config.yaml not present in this checkout")
    rows = [{"x_mm": 0.0, "outer_bbox_r_mm": 10.0}]
    with pytest.raises(TypeError):
        cross_check_against_vehicle_config(rows, drone_config)


# ---------------------------------------------------------------------------
# Integration test: synthetic gmsh solids, no real STEP file required.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_GMSH, reason="gmsh not installed in this environment")
def test_synthetic_solid_and_hollow_cylinder_loop_detection():
    """End-to-end gmsh validation using synthetic solids, per
    docs/geometry/status.md's instruction to validate the loop/hole logic
    without the real (gitignored, local-only) STEP file.

    Builds a solid cylinder (radius 20mm) and a hollow tube (outer 20mm,
    inner 10mm, via addCylinder + cut) and confirms the station-slice +
    loop-detection code reports 1 loop (no hole) for the solid and 2 loops
    (hole detected, with the correct known inner radius) for the hollow
    one -- exercising the exact same gmsh API path
    (addRectangle+rotate+translate, intersect, face->curve->point
    adjacency) the real STEP file will use later.
    """
    from IADE_Core.modules.geometry.cad_station_sweep import slice_volume_at_station

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("test_synthetic_station_sweep")

        outer_r_mm, inner_r_mm, length_mm = 20.0, 10.0, 100.0

        solid_vol = gmsh.model.occ.addCylinder(0, 0, 0, length_mm, 0, 0, outer_r_mm)
        gmsh.model.occ.synchronize()

        outer_cyl = gmsh.model.occ.addCylinder(0, 0, 0, length_mm, 0, 0, outer_r_mm)
        inner_cyl = gmsh.model.occ.addCylinder(0, 0, 0, length_mm, 0, 0, inner_r_mm)
        hollow_out, _ = gmsh.model.occ.cut([(3, outer_cyl)], [(3, inner_cyl)])
        gmsh.model.occ.synchronize()
        hollow_vol = hollow_out[0][1]

        solid_results = slice_volume_at_station(solid_vol, length_mm / 2.0)
        assert len(solid_results) == 1
        solid_topology: LoopTopology = solid_results[0]["topology"]
        assert solid_topology.n_loops == 1
        assert not solid_topology.has_inner_loop
        assert solid_results[0]["area_mm2"] == pytest.approx(
            math.pi * outer_r_mm**2, rel=1e-3
        )

        hollow_results = slice_volume_at_station(hollow_vol, length_mm / 2.0)
        assert len(hollow_results) == 1
        hollow_topology: LoopTopology = hollow_results[0]["topology"]
        assert hollow_topology.n_loops == 2
        assert hollow_topology.has_inner_loop
        assert hollow_topology.inner_bbox_r_mm == pytest.approx(inner_r_mm, rel=1e-3)
        assert hollow_topology.outer_bbox_r_mm == pytest.approx(outer_r_mm, rel=1e-3)
        expected_hollow_area = math.pi * (outer_r_mm**2 - inner_r_mm**2)
        assert hollow_results[0]["area_mm2"] == pytest.approx(
            expected_hollow_area, rel=1e-3
        )
    finally:
        gmsh.finalize()
