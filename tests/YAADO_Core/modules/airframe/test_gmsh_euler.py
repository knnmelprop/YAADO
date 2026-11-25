"""Tests for the Gmsh Euler mesher."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.airframe.containers import GmshMeshResults
from YAADO_Core.modules.airframe.gmsh_process import gmsh_problem, run_gmsh
from YAADO_Core.modules.airframe.mesher_methods.gmsh_euler import (
    GmshMeshAnalysis,
    MeshJob,
    boundary_is_closed,
    mesh_vehicle,
    parse_surfaces,
    plot_mesh,
    root_section,
)
from YAADO_Core.modules.airframe.outer_shape import outer_shape_from_vehicle
from YAADO_Core.modules.airframe.slicer_methods.gmsh import GmshSliceAnalysis

REPO_ROOT = Path(__file__).resolve().parents[4]
HARPOON = REPO_ROOT / "Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml"

needs_gmsh = pytest.mark.skipif(gmsh_problem() is not None, reason="Gmsh does not load here")

BODY = {"type": "axisymmetric_body", "length": 1.0, "diameter": 0.2, "nose_type": "conical",
        "nose_length": 0.4}
FINS = {"type": "fins", "count": 4, "span": 0.1, "sweep": 30.0, "chord_root": 0.2, "chord_tip": 0.1,
        "thickness_ratio": 0.06}
CONE_VOLUME = math.pi * 0.1**2 * (0.4 / 3.0 + 0.6)
CONE_AREA = math.pi * 0.1 * math.hypot(0.4, 0.1) + 2.0 * math.pi * 0.1 * 0.6


def _vehicle(body: dict | None = None, **surfaces: dict) -> BaseVehicleConfig:
    return BaseVehicleConfig.model_validate(
        {"name": "Test", "bodies": {"tube": {**BODY, **(body or {})}}, "aero_surfaces": surfaces}
    )


def _run(vehicle: BaseVehicleConfig, **settings: object) -> GmshMeshResults:
    analysis = GmshMeshAnalysis()
    analysis.setup(
        vehicle, enable_logging=False, **{"cells_per_diameter": 8, "farfield_lengths": 4.0, **settings}
    )
    return analysis.execute()


def test_surface_lists() -> None:
    assert parse_surfaces(None) is None
    assert parse_surfaces("  ") is None
    assert parse_surfaces("none") == ()
    assert parse_surfaces("fins, wing") == ("fins", "wing")


def test_watertightness_check_finds_a_missing_and_an_extra_face() -> None:
    """Two tetrahedra sharing the face (1, 2, 3)."""
    cells = np.array([[0, 1, 2, 3], [1, 2, 3, 4]])
    faces = np.array([[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 4], [1, 3, 4], [2, 3, 4]])
    assert boundary_is_closed(cells, faces)
    assert boundary_is_closed(cells, faces[:, ::-1])
    assert not boundary_is_closed(cells, faces[:-1])
    assert not boundary_is_closed(cells, np.vstack([faces, [[1, 2, 3]]]))


def test_a_fin_root_lies_under_the_surface_and_stays_inside_the_base() -> None:
    body_radius = 0.1
    for chord_tip, flush in ((0.05, True), (0.19, False)):
        shape = outer_shape_from_vehicle(_vehicle(fins={**FINS, "chord_tip": chord_tip}))
        root = root_section(shape.panels[0], shape.body)
        assert root.inner_offset < root.offset < math.sqrt(body_radius**2 - 0.006**2)
        # A trailing edge that sweeps forward keeps the base plane; one that sweeps aft recedes
        assert (root.le + root.chord == pytest.approx(1.0)) is flush
        assert root.le + root.chord <= 1.0 + 1e-12


@needs_gmsh
def test_body_alone_matches_the_cone_cylinder() -> None:
    results = _run(_vehicle())
    assert results.is_half
    assert results.volume == pytest.approx(CONE_VOLUME, rel=1e-6)
    assert results.wetted_area == pytest.approx(CONE_AREA, rel=1e-6)
    assert results.base_area == pytest.approx(math.pi * 0.1**2, rel=1e-6)
    areas = {marker.name: marker.area for marker in results.markers}
    assert set(areas) == {"airframe", "base", "farfield", "symmetry"}
    assert areas["airframe"] == pytest.approx(CONE_AREA / 2.0, rel=0.02)
    assert areas["base"] == pytest.approx(math.pi * 0.1**2 / 2.0, rel=0.02)
    assert results.min_quality > GmshMeshAnalysis.POOR_QUALITY


@needs_gmsh
def test_fins_add_their_volume_in_half_and_full_domains() -> None:
    vehicle = _vehicle(fins=FINS)
    half = _run(vehicle)
    full = _run(vehicle, domain="full")
    # Double wedge area t/c c^2 / 2, integrated over the span of four fins
    mean_square_chord = (0.2**2 + 0.2 * 0.1 + 0.1**2) / 3.0
    expected = CONE_VOLUME + 4.0 * 0.03 * mean_square_chord * 0.1
    assert half.volume == pytest.approx(expected, rel=2e-3)
    assert full.volume == pytest.approx(half.volume, rel=1e-9)
    assert full.wetted_area == pytest.approx(half.wetted_area, rel=1e-6)
    assert not full.is_half and "symmetry" not in {marker.name for marker in full.markers}
    assert 1.5 < full.n_tetrahedra / half.n_tetrahedra < 2.5
    assert half.surfaces == ("fins",)


@needs_gmsh
def test_more_cells_per_diameter_refine_the_whole_mesh() -> None:
    coarse, fine = (_run(_vehicle(), cells_per_diameter=n) for n in (11, 16))
    ratio = 16.0 / 11.0
    assert fine.n_wall_triangles == pytest.approx(ratio**2 * coarse.n_wall_triangles, rel=0.2)
    assert fine.n_tetrahedra == pytest.approx(ratio**3 * coarse.n_tetrahedra, rel=0.2)


@needs_gmsh
@pytest.mark.parametrize(
    ("body", "surfaces", "settings"),
    [
        ({"nose_type": "hemispherical", "nose_length": 0.1}, {"fins": {**FINS, "count": 3}}, {}),
        ({"nose_type": "ogive"}, {"fins": {**FINS, "airfoil": "NACA0010"}}, {"fin_roll_deg": 0.0}),
        ({"nose_type": "ogive"}, {"fins": FINS}, {"fin_roll_deg": 20.0}),
        ({}, {"fins": {**FINS, "chord_root": 0.15, "chord_tip": 0.12}}, {}),
        (
            {},
            {"wing": {"type": "wing", "aspect_ratio": 6.0, "sweep": 20.0, "taper_ratio": 0.5, "span": 1.2,
                      "airfoil_root": "NACA2412", "root_le_from_nose": 0.4, "dihedral": 3.0}},
            {},
        ),
    ],
    ids=["hemisphere-3-fins", "ogive-naca-plus", "rolled-full", "flush-aft-swept", "wing"],
)
def test_a_range_of_vehicles_meshes(body: dict, surfaces: dict, settings: dict) -> None:
    results = _run(_vehicle(body, **surfaces), **settings)
    assert results.n_tetrahedra > 10_000
    assert results.n_poor <= 0.001 * results.n_tetrahedra
    assert results.is_half is not (settings.get("fin_roll_deg") == 20.0)


@needs_gmsh
def test_the_files_hold_the_vehicle(tmp_path: Path) -> None:
    """The SU2 file counts match, and the STEP file slices back to the same volume."""
    vehicle = _vehicle(fins=FINS)
    shape = outer_shape_from_vehicle(vehicle)
    job = MeshJob(shape, True, 8, 4.0, str(tmp_path / "airframe.su2"), str(tmp_path / "airframe.step"))
    mesh = run_gmsh(mesh_vehicle, job).value

    lines = (tmp_path / "airframe.su2").read_text(encoding="utf-8").splitlines()
    values = [line.split("=") for line in lines if "=" in line]
    assert ["NDIME", " 3"] in values
    assert ["NELEM", f" {mesh.n_tetrahedra}"] in values
    assert int(next(v for k, v in values if k == "NPOIN")) == mesh.n_nodes
    assert [v.strip() for k, v in values if k == "MARKER_TAG"] == ["airframe", "base", "farfield", "symmetry"]
    assert mesh.wall[:, :, 1].min() > -1e-6

    analysis = GmshSliceAnalysis()
    analysis.setup(vehicle, enable_logging=False, step_file=job.step_path, n_stations=40)
    sliced = analysis.execute()
    assert sliced.volume == pytest.approx(mesh.volume, rel=1e-5)
    assert sliced.length == pytest.approx(1.0, abs=1e-4)
    assert all(check.matches for check in sliced.checks)

    import matplotlib.pyplot as plt

    figure = plot_mesh(mesh, shape)
    assert len(figure.axes) == 4
    plt.close(figure)
    plt.close(plot_mesh(replace(mesh, symmetry=np.empty((0, 3, 3))), shape))


@needs_gmsh
def test_harpoon_meshes_from_its_toml() -> None:
    results = _run(BaseVehicleConfig.from_toml(HARPOON), cells_per_diameter=6)
    assert results.is_half
    assert results.surfaces == ("mid_body_wings", "aft_control_fins")
    assert results.left_out == ("planar_equivalent",)
    assert results.base_area == pytest.approx(math.pi * 0.1715**2, rel=1e-4)
    assert results.units()["wetted_area"] == "m^2"


@needs_gmsh
@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"cells_per_diameter": 3}, "cells_per_diameter"),
        ({"farfield_lengths": 1.0}, "farfield_lengths"),
        ({"domain": "quarter"}, "domain"),
        ({"domain": "half", "fin_roll_deg": 20.0}, "domain=full"),
    ],
)
def test_bad_settings_are_refused(settings: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        GmshMeshAnalysis().setup(_vehicle(fins=FINS), enable_logging=False, **settings)


def test_unknown_settings_are_refused() -> None:
    with pytest.raises(TypeError, match="pitch"):
        GmshMeshAnalysis().setup(_vehicle(), enable_logging=False, pitch=0.1)
