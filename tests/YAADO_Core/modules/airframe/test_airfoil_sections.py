"""Tests for fin and wing sections."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from YAADO_Core.modules.airframe.airfoil_sections import (
    double_wedge,
    naca_section,
    section_from_airfoil,
    section_from_coordinates,
)


def test_double_wedge_is_a_symmetric_diamond() -> None:
    section = double_wedge(0.06)
    assert section.straight and section.is_symmetric
    assert section.upper == ((0.0, 0.0), (0.5, 0.03), (1.0, 0.0))
    assert section.thickness_to_chord == pytest.approx(0.06)
    with pytest.raises(ValueError, match="thickness ratio"):
        double_wedge(0.6)


def test_naca_0012_matches_the_published_ordinates() -> None:
    """Abbott & von Doenhoff, appendix III: y/c = 0.06002 at 30% and 0.04563 at 60% chord."""
    section = naca_section("0012")
    x, z = np.array(section.upper).T
    assert np.interp(0.30, x, z) == pytest.approx(0.06002, abs=2e-4)
    assert np.interp(0.60, x, z) == pytest.approx(0.04563, abs=2e-4)
    assert section.is_symmetric
    assert section.leading_edge_radius == pytest.approx(0.0158, abs=1e-4)
    assert section.upper[0] == section.lower[0] and section.upper[-1] == section.lower[-1]


@pytest.mark.parametrize(
    ("digits", "camber", "position"),
    [("2412", 0.02, 0.4), ("4415", 0.04, 0.4), ("23012", 0.0184, 0.15)],
)
def test_camber_peaks_where_the_designation_says(digits: str, camber: float, position: float) -> None:
    section = naca_section(digits)
    upper, lower = np.array(section.upper), np.array(section.lower)
    grid = np.linspace(0.02, 0.98, 400)
    line = (np.interp(grid, *upper.T) + np.interp(grid, *lower.T)) / 2.0
    assert line.max() == pytest.approx(camber, rel=0.02)
    assert grid[line.argmax()] == pytest.approx(position, abs=0.03)
    assert not section.is_symmetric
    assert section.thickness_to_chord == pytest.approx(int(digits[-2:]) / 100.0, rel=0.02)


@pytest.mark.parametrize("digits", ["23112", "6409x", "0000"])
def test_unknown_naca_sections_are_refused(digits: str) -> None:
    with pytest.raises(ValueError, match="NACA"):
        naca_section(digits)


def test_coordinates_are_scaled_and_a_blunt_trailing_edge_is_closed(tmp_path: Path) -> None:
    x, half = np.array(naca_section("0010").upper).T
    blunt = half + 0.003 * x
    points = [*zip(2.0 * x[::-1] + 1.0, 2.0 * blunt[::-1], strict=True),
              *zip(2.0 * x[1:] + 1.0, -2.0 * blunt[1:], strict=True)]
    path = tmp_path / "fin.dat"
    path.write_text("Fin\n" + "\n".join(f"{a:.6f} {b:.6f}" for a, b in points), encoding="utf-8")

    section = section_from_airfoil(str(path))
    assert section.name == "Fin"
    assert section.upper[0] == (0.0, 0.0)
    assert section.upper[-1] == pytest.approx((1.0, 0.0), abs=1e-6)
    assert section.lower[-1] == pytest.approx((1.0, 0.0), abs=1e-6)
    assert section.thickness_to_chord == pytest.approx(0.10, rel=0.01)
    assert section.leading_edge_radius == pytest.approx(1.1019 * 0.1**2, rel=0.5)


def test_coordinates_need_a_leading_edge() -> None:
    with pytest.raises(ValueError, match="leading edge"):
        section_from_coordinates("flat", [(0.1 * i, 0.0) for i in range(12)])
