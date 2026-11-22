"""Tests for the XFOIL section polar: input deck, parsing, metrics and the analysis.

Unit tests replace the XFOIL process with a stand-in that writes the files XFOIL would.
Tests marked ``real_xfoil`` run the executable and skip when none works on this machine.
"""

from __future__ import annotations

import math
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from YAADO_Core.ComponentStore import Fins, Wings
from YAADO_Core.Foundation.cancellation import CancelToken, RunCancelledError
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.wind_tunnel.containers import SectionPolar
from YAADO_Core.modules.wind_tunnel.methods.xfoil import xfoil_runner
from YAADO_Core.modules.wind_tunnel.methods.xfoil.xfoil_runner import (
    AirfoilSource,
    XFOILAnalysis,
    XfoilConvergenceError,
    alpha_schedule,
    build_command_deck,
    parse_polar,
    polar_metrics,
    read_airfoil_file,
    resolve_airfoil,
    run_xfoil,
    thickness_to_chord,
)

HARPOON_PATH = Path("Hangar/examples/AGM-84_HARPOON/AGM-84_HARPOON.toml")

_POLAR_HEADER = """
       XFOIL         Version 6.99

 Calculated polar for: NACA 0012

 1 1 Reynolds number fixed          Mach number fixed

 xtrf =   1.000 (top)        1.000 (bottom)
 Mach =   0.000     Re =     3.000 e 6     Ncrit =   9.000  9.000

   alpha    CL        CD       CDp       CM     Top_Xtr  Bot_Xtr  Top_Itr  Bot_Itr
  ------ -------- --------- --------- -------- -------- -------- -------- --------
"""


def _naca00_coordinates(thickness: float, n: int = 81) -> list[tuple[float, float]]:
    """Symmetric NACA 4-digit section in Selig order (closed trailing edge)."""
    beta = np.linspace(0.0, math.pi, n)
    x = 0.5 * (1.0 - np.cos(beta))
    yt = 5.0 * thickness * (
        0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4
    )
    upper = list(zip(x[::-1], yt[::-1], strict=True))
    lower = list(zip(x[1:], -yt[1:], strict=True))
    return [(float(a), float(b)) for a, b in upper + lower]


def _row(alpha: float) -> str:
    """A polar row with CL = 0.11 alpha, CD = 0.006 + 1e-4 alpha^2 and CM = 0.001 alpha."""
    cl, cd, cm = 0.11 * alpha, 0.006 + 1e-4 * alpha**2, 0.001 * alpha
    return f"{alpha:8.3f} {cl:8.4f} {cd:9.5f} {0.001:9.5f} {cm:8.4f} {0.5:8.4f} {0.6:8.4f}"


def _fake_xfoil(
    converges: Callable[[float, str], bool],
    returncode: int = 0,
    save_geometry: bool = True,
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Stand-in for ``xfoil_runner._run_process`` that writes XFOIL's geometry and polar files.

    Args:
        converges: Whether an angle converges, given the polar file of the pass.
        returncode: Exit status to report.
        save_geometry: Whether ``SAVE`` writes the coordinate file.
    """

    def run(args: list[str], *, input: str, cwd: Path, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        lines = input.splitlines()
        workdir = Path(cwd)
        if save_geometry and any(line.startswith("SAVE ") for line in lines):
            body = "\n".join(f"{x:.6f} {y:.6f}" for x, y in _naca00_coordinates(0.12))
            (workdir / "section.dat").write_text(f"NACA 0012\n{body}\n", encoding="utf-8")
        polar_file = lines[lines.index("PACC") + 1]
        alphas = [float(line.split()[1]) for line in lines if line.startswith("ALFA ")]
        rows = [_row(alpha) for alpha in alphas if converges(alpha, polar_file)]
        (workdir / polar_file).write_text(_POLAR_HEADER + "\n".join(rows) + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(args, returncode, stdout="fake xfoil\n", stderr="")

    return run


@pytest.fixture
def harpoon() -> BaseVehicleConfig:
    return BaseVehicleConfig.from_toml(HARPOON_PATH)


@pytest.fixture
def fake_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend an XFOIL executable is on PATH."""
    monkeypatch.setattr(xfoil_runner, "xfoil_executable", lambda: "xfoil")


# --- Geometry ---------------------------------------------------------------------------


def test_wing_mean_aerodynamic_chord_hand_checks() -> None:
    """A rectangular wing's MAC is its chord b/AR; a taper of 0.2 matches the hand value."""
    rectangle = Wings(aspect_ratio=4.0, sweep=0.0, taper_ratio=1.0, span=2.0, airfoil_root="NACA0012")
    assert rectangle.mean_aerodynamic_chord == pytest.approx(0.5, rel=1e-12)

    # Harpoon planform: S = 0.914^2 / 2.3 = 0.363216 m^2, c_r = 2 S / (b (1 + 0.2)) = 0.662319 m,
    # MAC = 2/3 c_r (1 + 0.2 + 0.04) / 1.2 = 0.456264 m.
    tapered = Wings(aspect_ratio=2.3, sweep=45.0, taper_ratio=0.2, span=0.914, airfoil_root="NACA0006")
    assert tapered.mean_aerodynamic_chord == pytest.approx(0.456264, rel=1e-5)
    assert tapered.section_airfoil == "NACA0006"


def test_fin_mean_aerodynamic_chord_hand_checks() -> None:
    """Trapezoid MAC 2/3 (c_r + c_t - c_r c_t / (c_r + c_t)); a pointed tip gives 2/3 c_r."""
    fins = Fins(count=4, span=0.245, sweep=45.0, chord_root=0.4, chord_tip=0.12)
    # 2/3 (0.52 - 0.048 / 0.52) = 0.285128 m
    assert fins.mean_aerodynamic_chord == pytest.approx(0.285128, rel=1e-5)
    pointed = Fins(count=3, span=0.1, sweep=30.0, chord_root=0.3, chord_tip=0.0)
    assert pointed.mean_aerodynamic_chord == pytest.approx(0.2, rel=1e-12)
    assert Fins(count=3, span=0.1, sweep=30.0, chord_root=0.3).mean_aerodynamic_chord is None
    assert fins.section_airfoil is None


def test_thickness_to_chord_of_a_naca_0012() -> None:
    x, y = zip(*_naca00_coordinates(0.12, n=201), strict=True)
    assert thickness_to_chord(x, y) == pytest.approx(0.12, abs=5e-4)


# --- Airfoil input ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("designation", "digits"),
    [("NACA2412", "2412"), ("naca 0012", "0012"), ("NACA-23012", "23012"), (" NACA_4415 ", "4415")],
)
def test_resolve_airfoil_reads_naca_designations(designation: str, digits: str) -> None:
    source = resolve_airfoil(designation)
    assert source.naca_digits == digits
    assert source.coordinates == ()


def test_resolve_airfoil_rejects_unknown_names() -> None:
    with pytest.raises(ValueError, match="neither a NACA"):
        resolve_airfoil("Clark Y")


def test_read_selig_and_lednicer_files_agree(tmp_path: Path) -> None:
    """Both formats come back in Selig order, trailing edge over the upper surface first."""
    points = _naca00_coordinates(0.10, n=21)
    selig = tmp_path / "foil.dat"
    selig.write_text("MY FOIL\n" + "\n".join(f"{x} {y}" for x, y in points), encoding="utf-8")

    upper = points[:21][::-1]  # leading edge to trailing edge
    lower = points[20:]
    lednicer = tmp_path / "foil_lednicer.dat"
    lednicer.write_text(
        "MY FOIL\n"
        f"{len(upper)}. {len(lower)}.\n\n"
        + "\n".join(f"{x} {y}" for x, y in upper)
        + "\n\n"
        + "\n".join(f"{x} {y}" for x, y in lower),
        encoding="utf-8",
    )

    from_selig = read_airfoil_file(selig)
    from_lednicer = resolve_airfoil(str(lednicer))
    assert from_selig.name == "MY FOIL"
    assert from_selig.naca_digits is None
    assert np.allclose(from_selig.coordinates, points)
    assert np.allclose(from_lednicer.coordinates, points)


def test_read_airfoil_file_rejects_a_short_file(tmp_path: Path) -> None:
    path = tmp_path / "short.dat"
    path.write_text("1.0 0.0\n0.0 0.0\n1.0 0.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="too few"):
        read_airfoil_file(path)


# --- Command deck and polar parsing -----------------------------------------------------


def test_alpha_schedule_includes_both_ends() -> None:
    alphas = alpha_schedule(-5.0, 15.0, 0.5)
    assert len(alphas) == 41
    assert alphas[0] == -5.0 and alphas[-1] == 15.0
    assert alpha_schedule(-1.0, 1.0, 0.3) == (-1.0, -0.7, -0.4, -0.1, 0.2, 0.5, 0.8)


def test_command_deck_disables_plotting_and_sweeps_out_from_zero() -> None:
    deck = build_command_deck(
        AirfoilSource(name="NACA 2412", naca_digits="2412"),
        reynolds=1.5e6,
        mach=0.1,
        n_crit=9.0,
        runs=[[0.0, 1.0, 2.0], [-1.0, -2.0]],
        max_iter=100,
    ).splitlines()
    assert deck[:3] == ["PLOP", "G F", ""]
    assert deck[3] == "NACA 2412"
    assert "SAVE section.dat" in deck
    assert "VISC 1500000" in deck and "MACH 0.1" in deck and "N 9" in deck
    alfa = [line for line in deck if line.startswith(("ALFA", "INIT"))]
    assert alfa == ["ALFA 0", "ALFA 1", "ALFA 2", "INIT", "ALFA -1", "ALFA -2"]
    assert deck[-3:] == ["PACC", "", "QUIT"]


def test_parse_polar_sorts_and_drops_repeated_angles() -> None:
    text = _POLAR_HEADER + "\n".join([_row(2.0), _row(0.0), _row(-1.0), _row(2.0)]) + "\n"
    polar = parse_polar(text, reynolds=3e6, mach=0.0)
    assert polar.alpha == (-1.0, 0.0, 2.0)
    assert polar.cl == pytest.approx((-0.11, 0.0, 0.22))
    assert polar.xtr_bottom == (0.6, 0.6, 0.6)
    assert polar.reynolds == 3e6


def test_parse_polar_reads_two_concatenated_files() -> None:
    """The retry pass appends a second header; its text lines are skipped."""
    text = _POLAR_HEADER + _row(1.0) + "\n" + _POLAR_HEADER + _row(0.5) + "\n"
    assert parse_polar(text, reynolds=1e6, mach=0.0).alpha == (0.5, 1.0)


# --- Polar metrics ----------------------------------------------------------------------


def _polar(alpha: list[float], cl: list[float], cd: list[float], cm: list[float]) -> SectionPolar:
    n = len(alpha)
    return SectionPolar(
        reynolds=1e6, mach=0.0, alpha=tuple(alpha), cl=tuple(cl), cd=tuple(cd),
        cdp=(0.0,) * n, cm=tuple(cm), xtr_top=(1.0,) * n, xtr_bottom=(1.0,) * n,
    )


def test_polar_metrics_of_a_thin_cambered_section() -> None:
    """Linear lift 2 pi (alpha - alpha0) with alpha0 = -2 deg, then a drop past 10 deg."""
    alpha = [float(a) for a in range(-6, 15)]
    cl = [2 * math.pi * math.radians(a + 2.0) for a in alpha]
    cl[-3:] = [1.0, 0.9, 0.85]  # 12, 13, 14 deg: past stall
    cd = [0.006 + 0.0002 * (a - 1.0) ** 2 for a in alpha]
    cm = [-0.05 - 0.001 * a for a in alpha]

    metrics = polar_metrics(_polar(alpha, cl, cd, cm), (-2.0, 6.0))
    assert metrics.alpha_zero_lift == pytest.approx(-2.0, abs=1e-9)
    assert metrics.cl_alpha == pytest.approx(2 * math.pi, rel=1e-9)
    # CM interpolated at alpha0 = -2 deg: -0.05 + 0.002
    assert metrics.cm_zero_lift == pytest.approx(-0.048, abs=1e-12)
    assert metrics.cl_max == pytest.approx(2 * math.pi * math.radians(13.0))
    assert metrics.alpha_cl_max == 11.0
    assert metrics.stall_reached
    assert metrics.cd_min == pytest.approx(0.006)
    assert metrics.cl_at_cd_min == pytest.approx(2 * math.pi * math.radians(3.0))
    ratios = [c / d for c, d in zip(cl, cd, strict=True)]
    assert metrics.max_lift_to_drag == pytest.approx(max(ratios))


def test_polar_metrics_without_a_zero_crossing_leave_the_slope_unknown() -> None:
    alpha = [2.0, 3.0, 4.0]
    metrics = polar_metrics(_polar(alpha, [0.3, 0.4, 0.5], [0.01] * 3, [0.0] * 3), (-2.0, 6.0))
    assert metrics.alpha_zero_lift is None
    assert metrics.cl_alpha is None
    assert metrics.cm_zero_lift is None
    assert not metrics.stall_reached


# --- XFOIL process handling -------------------------------------------------------------


def test_run_xfoil_retries_angles_that_fail_the_first_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    def converges(alpha: float, polar_file: str) -> bool:
        return alpha != 4.0 or polar_file == "polar_retry.txt"

    monkeypatch.setattr(xfoil_runner, "_run_process", _fake_xfoil(converges))
    run = run_xfoil("xfoil", resolve_airfoil("NACA0012"), 1e6, 0.0, 9.0,
                    alpha_schedule(-2.0, 6.0, 1.0), 100, 10.0)
    assert run.polar.alpha == tuple(float(a) for a in range(-2, 7))
    assert run.missed == ()
    assert run.stopped == ()
    upward, downward, retry = run.commands.split("QUIT")[:3]
    assert "SAVE section.dat" in upward and "SAVE" not in downward + retry
    assert next(line for line in upward.splitlines() if line.startswith("ALFA")) == "ALFA 0"
    assert [line for line in downward.splitlines() if line.startswith("ALFA")] == ["ALFA -1", "ALFA -2"]
    assert "polar_retry.txt" in retry
    assert retry.splitlines()[-4:-2] == ["ALFA 3.9", "ALFA 4"]
    assert run.geometry.thickness_to_chord == pytest.approx(0.12, abs=2e-3)


def test_run_xfoil_keeps_the_points_of_a_sweep_stopped_at_the_time_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A diverged upward sweep is stopped; its converged points and the other sweeps remain."""
    finish = _fake_xfoil(lambda a, _: a <= 3.0)

    def run(args: list[str], *, input: str, cwd: Path, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        finish(args, input=input, cwd=cwd, **kwargs)
        if "polar_upward.txt" in input:
            raise subprocess.TimeoutExpired(args, kwargs["timeout"], output=b"partial")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(xfoil_runner, "_run_process", run)
    result = run_xfoil("xfoil", resolve_airfoil("NACA0012"), 1e6, 0.0, 9.0,
                       alpha_schedule(-2.0, 6.0, 1.0), 100, 10.0)
    assert result.stopped == ("upward",)
    assert result.polar.alpha == (-2.0, -1.0, 0.0, 1.0, 2.0, 3.0)
    assert result.missed == (4.0, 5.0, 6.0)
    assert "partial" in result.output


def test_run_xfoil_reports_angles_that_never_converge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(xfoil_runner, "_run_process", _fake_xfoil(lambda a, _: a not in (-1.0, 4.0)))
    run = run_xfoil("xfoil", resolve_airfoil("NACA0012"), 1e6, 0.0, 9.0,
                    alpha_schedule(-2.0, 6.0, 1.0), 100, 10.0)
    assert run.missed == (-1.0, 4.0)
    assert -1.0 not in run.polar.alpha and 4.0 not in run.polar.alpha


def test_run_xfoil_explains_the_debian_floating_point_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        xfoil_runner, "_run_process", _fake_xfoil(lambda a, _: True, returncode=-signal.SIGFPE)
    )
    with pytest.raises(RuntimeError, match="SIGFPE.*wrapper on PATH"):
        run_xfoil("xfoil", resolve_airfoil("NACA0012"), 1e6, 0.0, 9.0, (0.0,), 100, 10.0)


def test_run_xfoil_fails_when_the_airfoil_cannot_be_built(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        xfoil_runner, "_run_process", _fake_xfoil(lambda a, _: True, save_geometry=False)
    )
    with pytest.raises(RuntimeError, match="could not build"):
        run_xfoil("xfoil", resolve_airfoil("NACA99999"), 1e6, 0.0, 9.0, (0.0,), 100, 10.0)


def test_run_xfoil_fails_when_nothing_converges(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(xfoil_runner, "_run_process", _fake_xfoil(lambda a, _: False))
    with pytest.raises(XfoilConvergenceError, match="none of the 3 angles"):
        run_xfoil("xfoil", resolve_airfoil("NACA0012"), 1e6, 0.0, 9.0, (0.0, 1.0, 2.0), 100, 10.0)


# A child process that holds the output pipe open, as XFOIL started by a wrapper script does.
_SLEEPING_CHILD = (
    "import subprocess, sys\n"
    "subprocess.run([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
)


@pytest.mark.skipif(sys.platform == "win32", reason="process groups are POSIX only")
def test_run_deck_kills_the_process_group_when_cancelled(tmp_path: Path) -> None:
    """A cancel kills the running process and its children within a second."""
    token = CancelToken()
    timer = threading.Timer(0.3, token.cancel)
    start = time.monotonic()
    timer.start()
    with pytest.raises(RunCancelledError):
        xfoil_runner._run_deck(sys.executable, _SLEEPING_CHILD, tmp_path, 60.0, token)
    assert time.monotonic() - start < 3.0

    # An already cancelled run starts no process.
    with pytest.raises(RunCancelledError):
        xfoil_runner._run_deck("no-such-executable", "", tmp_path, 60.0, token)


def test_run_deck_keeps_the_output_of_a_process_stopped_at_the_time_limit(
    tmp_path: Path,
) -> None:
    script = "print('first point', flush=True)\nimport time\ntime.sleep(60)\n"
    start = time.monotonic()
    output, stopped = xfoil_runner._run_deck(sys.executable, script, tmp_path, 0.5)
    assert stopped
    assert "first point" in output
    assert time.monotonic() - start < 3.0


# --- Analysis setup ---------------------------------------------------------------------


@pytest.mark.usefixtures("fake_executable")
def test_setup_needs_a_surface_when_the_vehicle_has_several(harpoon: BaseVehicleConfig) -> None:
    with pytest.raises(ValueError, match="3 aerodynamic surfaces.*surface=NAME"):
        XFOILAnalysis().setup(harpoon, enable_logging=False)


@pytest.mark.usefixtures("fake_executable")
def test_setup_needs_an_airfoil_for_fins_without_one(harpoon: BaseVehicleConfig) -> None:
    with pytest.raises(ValueError, match="'aft_control_fins' has no airfoil"):
        XFOILAnalysis().setup(harpoon, enable_logging=False, surface="aft_control_fins")


@pytest.mark.usefixtures("fake_executable")
def test_setup_rejects_an_unknown_surface(harpoon: BaseVehicleConfig) -> None:
    with pytest.raises(KeyError, match="main_wing"):
        XFOILAnalysis().setup(harpoon, enable_logging=False, surface="main_wing")


@pytest.mark.usefixtures("fake_executable")
@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"mach": 0.8}, "Mach number"),
        ({"alpha_start_deg": 5.0, "alpha_end_deg": 0.0}, "alpha_start_deg"),
        ({"alpha_end_deg": 40.0}, "within"),
        ({"alpha_step_deg": 0.05, "alpha_start_deg": -20.0, "alpha_end_deg": 20.0}, "increase"),
        ({"mach": 0.0}, "Reynolds number"),
        ({"n_crit": 0.0}, "n_crit"),
        ({"chord": -0.1}, "chord"),
        ({"bogus": 1.0}, "Unknown settings"),
    ],
)
def test_setup_rejects_settings_out_of_range(
    harpoon: BaseVehicleConfig, settings: dict[str, Any], message: str
) -> None:
    with pytest.raises((ValueError, TypeError), match=message):
        XFOILAnalysis().setup(harpoon, enable_logging=False, surface="planar_equivalent", **settings)


def test_setup_reports_a_missing_executable(
    harpoon: BaseVehicleConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(xfoil_runner, "xfoil_executable", lambda: None)
    with pytest.raises(RuntimeError, match="not found on PATH"):
        XFOILAnalysis().setup(harpoon, enable_logging=False, surface="planar_equivalent")


@pytest.mark.usefixtures("fake_executable")
def test_analysis_on_the_harpoon_wing(
    harpoon: BaseVehicleConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reynolds number by hand at sea level: rho 1.225, a 340.294 m/s, mu 1.7894e-5 Pa s."""
    monkeypatch.setattr(xfoil_runner, "_run_process", _fake_xfoil(lambda a, _: True))
    analysis = XFOILAnalysis()
    analysis.setup(harpoon, enable_logging=False, surface="planar_equivalent",
                   alpha_start_deg=-2.0, alpha_end_deg=6.0, alpha_step_deg=1.0)
    results = analysis.execute()

    velocity = 0.15 * 340.294
    assert results.surface == "planar_equivalent"
    assert results.airfoil == "NACA0006"
    assert results.chord == pytest.approx(0.456264, rel=1e-5)
    assert results.velocity == pytest.approx(velocity, rel=1e-4)
    assert results.reynolds == pytest.approx(1.225 * velocity * 0.456264 / 1.7894e-5, rel=1e-3)
    assert results.n_converged == 9
    # The stand-in polar: CL = 0.11 alpha[deg], CM = 0.001 alpha[deg]
    assert results.cl_alpha == pytest.approx(0.11 * 180.0 / math.pi, rel=1e-3)
    assert results.alpha_zero_lift == pytest.approx(0.0, abs=1e-6)
    assert results.cm_zero_lift == pytest.approx(0.0, abs=1e-6)
    assert not results.stall_reached
    assert any("beyond the sweep" in note for note in results.assumptions)
    assert results.units()["cl_alpha"] == "1/rad"
    assert results.units()["alpha_cl_max"] == "deg"


@pytest.mark.usefixtures("fake_executable")
def test_overrides_replace_the_surface_values(
    harpoon: BaseVehicleConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(xfoil_runner, "_run_process", _fake_xfoil(lambda a, _: True))
    analysis = XFOILAnalysis()
    analysis.setup(harpoon, enable_logging=False, surface="aft_control_fins",
                   airfoil="NACA0010", chord=0.3, reynolds=2.0e5, mach=0.0,
                   alpha_start_deg=0.0, alpha_end_deg=2.0)
    results = analysis.execute()
    assert results.airfoil == "NACA0010"
    assert results.chord == 0.3
    assert results.reynolds == 2.0e5
    assert results.velocity == 0.0


# --- Real XFOIL -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_xfoil() -> str:
    """Path of a working XFOIL; skips when it is missing or crashes."""
    executable = xfoil_runner.xfoil_executable()
    if executable is None:
        pytest.skip("xfoil is not on PATH")
    try:
        run_xfoil(executable, resolve_airfoil("NACA0012"), 1e6, 0.0, 9.0, (0.0,), 100, 30.0)
    except RuntimeError as exc:
        pytest.skip(f"xfoil does not run: {exc}")
    return executable


@pytest.mark.usefixtures("real_xfoil")
def test_real_naca_0012_matches_abbott_and_von_doenhoff() -> None:
    """NACA 0012 at Re 3e6: lift slope about 0.105/deg (6.0/rad), CDmin near 0.0055,
    CLmax near 1.6 (Abbott & von Doenhoff, Theory of Wing Sections, App. IV)."""
    run = run_xfoil(xfoil_runner.xfoil_executable() or "", resolve_airfoil("NACA0012"),
                    3.0e6, 0.0, 9.0, alpha_schedule(-4.0, 18.0, 1.0), 100, 60.0)
    metrics = polar_metrics(run.polar, XFOILAnalysis.SLOPE_WINDOW_DEG)
    assert run.geometry.thickness_to_chord == pytest.approx(0.12, abs=2e-3)
    assert metrics.alpha_zero_lift == pytest.approx(0.0, abs=0.05)
    assert metrics.cm_zero_lift == pytest.approx(0.0, abs=0.005)
    assert 5.8 < (metrics.cl_alpha or 0.0) < 6.8
    assert 0.0045 < metrics.cd_min < 0.0065
    assert 1.4 < metrics.cl_max < 1.8


@pytest.mark.usefixtures("real_xfoil")
def test_real_naca_4412_zero_lift_angle_and_moment() -> None:
    """NACA 4412: zero-lift angle about -4 deg and c/4 moment about -0.1 (thin-airfoil
    theory: -4.15 deg and -0.106)."""
    run = run_xfoil(xfoil_runner.xfoil_executable() or "", resolve_airfoil("NACA4412"),
                    3.0e6, 0.0, 9.0, alpha_schedule(-8.0, 8.0, 0.5), 100, 60.0)
    metrics = polar_metrics(run.polar, XFOILAnalysis.SLOPE_WINDOW_DEG)
    assert -4.8 < (metrics.alpha_zero_lift or 0.0) < -3.6
    assert -0.12 < (metrics.cm_zero_lift or 0.0) < -0.08


@pytest.mark.usefixtures("real_xfoil")
def test_real_analysis_on_every_harpoon_surface(harpoon: BaseVehicleConfig) -> None:
    for surface, airfoil in (("planar_equivalent", None), ("aft_control_fins", "NACA0010")):
        analysis = XFOILAnalysis()
        analysis.setup(harpoon, enable_logging=False, surface=surface, airfoil=airfoil)
        results = analysis.execute()
        assert results.surface == surface
        assert results.n_converged >= 30
        assert 0.5 < results.cl_max < 2.0


@pytest.mark.usefixtures("real_xfoil")
def test_real_diverging_run_stops_when_cancelled(harpoon: BaseVehicleConfig) -> None:
    """The Harpoon wing at Mach 0.3 diverges for about 30 s; a cancel stops it at once."""
    analysis = XFOILAnalysis()
    token = CancelToken()
    analysis.setup(
        harpoon, enable_logging=False, cancel_token=token, surface="planar_equivalent", mach=0.3
    )
    timer = threading.Timer(1.0, token.cancel)
    start = time.monotonic()
    timer.start()
    with pytest.raises(RunCancelledError):
        analysis.execute()
    assert time.monotonic() - start < 3.0
