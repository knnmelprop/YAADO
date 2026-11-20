"""Viscous section polar of one lifting surface with XFOIL.

Runs Mark Drela's XFOIL in batch mode on the section of one wing or fin set picked from
the vehicle: a panel method coupled with an integral boundary layer and e^n transition,
with the Karman-Tsien compressibility correction. The chord Reynolds number comes from
the surface's mean aerodynamic chord and the flight condition in the ISA atmosphere.

The sweep starts at the angle nearest zero and runs up to the end angle, then restarts
from a fresh boundary layer and runs down, which converges better past stall. Angles
XFOIL does not converge are left out of the polar and reported.

Reference:
    Drela, M., "XFOIL: An Analysis and Design System for Low Reynolds Number Airfoils",
    Low Reynolds Number Aerodynamics, Lecture Notes in Engineering 54, Springer, 1989.
"""

from __future__ import annotations

import csv
import functools
import io
import math
import re
import shutil
import signal
import subprocess
import tempfile
from dataclasses import dataclass, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np

if TYPE_CHECKING:
    from matplotlib.figure import Figure

from YAADO_Core.ComponentStore import AERO_COMPONENTS
from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.atmosphere import isa_atmosphere
from YAADO_Core.Foundation.solver_registry import DEFAULT_REGISTRY, SolverInfo
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.wind_tunnel.containers import (
    AirfoilGeometry,
    PolarMetrics,
    ReynoldsSweepPoint,
    SectionPolar,
    XfoilPolarResults,
)

DEFAULT_REGISTRY.register(
    SolverInfo(name="xfoil", executable="xfoil", description="MIT XFOIL subsonic airfoil analysis")
)

_NACA_PATTERN = re.compile(r"^\s*NACA[\s_-]*(\d{4,5})\s*$", re.IGNORECASE)
_AIRFOIL_FILE = "airfoil.dat"
_GEOMETRY_FILE = "section.dat"
_POLAR_FILE = "polar.txt"
_NAME_LENGTH = 32
_MIN_COORDINATES = 10
_POLAR_COLUMNS = 7
_STAGE_NAMES = {"upward": "upward sweep", "downward": "downward sweep", "retry": "retries"}
#: A missed angle is retried from a fresh boundary layer this much nearer zero [deg].
_RETRY_OFFSET_DEG = 0.1

_INSTALL_HINT = "see 'Installing XFOIL' in YAADO_Core/modules/wind_tunnel/methods/xfoil/README.md"
FPE_MESSAGE = (
    "XFOIL stopped on a floating-point exception (SIGFPE). The Ubuntu and Debian xfoil "
    f"package stops on harmless floating-point exceptions: put a wrapper on PATH ({_INSTALL_HINT})."
)
MISSING_MESSAGE = f"XFOIL executable 'xfoil' not found on PATH ({_INSTALL_HINT})."


class XfoilConvergenceError(RuntimeError):
    """XFOIL ran but converged at none of the requested angles of attack."""


@dataclass(frozen=True)
class AirfoilSource:
    """Airfoil handed to XFOIL: a NACA designation or explicit coordinates.

    Attributes:
        name: Airfoil name written to the coordinate file.
        naca_digits: Digits of a NACA 4- or 5-digit section XFOIL generates itself.
        coordinates: (x, y) points in Selig order, used when ``naca_digits`` is None.
    """

    name: str
    naca_digits: str | None = None
    coordinates: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class XfoilRun:
    """Parsed outputs and raw text of one XFOIL batch run.

    Attributes:
        polar: Converged points.
        geometry: Paneled section coordinates.
        missed: Requested angles of attack that did not converge [deg].
        stopped: XFOIL calls ("upward", "downward", "retry") stopped at the time limit.
        commands: Command decks sent to XFOIL.
        output: XFOIL console output.
        polar_text: Raw XFOIL polar file.
    """

    polar: SectionPolar
    geometry: AirfoilGeometry
    missed: tuple[float, ...]
    stopped: tuple[str, ...]
    commands: str
    output: str
    polar_text: str


def xfoil_executable() -> str | None:
    """Path of the registered XFOIL executable, or None if it is not on PATH."""
    return shutil.which(DEFAULT_REGISTRY.get("xfoil").executable)


@functools.lru_cache(maxsize=8)
def _smoke_test(executable: str, modified: float) -> str | None:
    """Solve one inviscid point; the Debian build already stops there with SIGFPE."""
    deck = "PLOP\nG F\n\nNACA 0012\nOPER\nALFA 0\n\nQUIT\n"
    try:
        completed = subprocess.run(
            [executable], input=deck, capture_output=True, text=True, timeout=10.0, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"XFOIL at {executable} does not run: {exc}"
    if completed.returncode == -signal.SIGFPE:
        return FPE_MESSAGE
    return None


def xfoil_problem() -> str | None:
    """Why the XFOIL on PATH cannot run, or None if it works.

    The check runs XFOIL once per executable and file version, then reuses the answer.
    """
    executable = xfoil_executable()
    if executable is None:
        return MISSING_MESSAGE
    try:
        modified = Path(executable).stat().st_mtime
    except OSError as exc:
        return f"XFOIL at {executable} does not run: {exc}"
    return _smoke_test(executable, modified)


def read_airfoil_file(path: Path) -> AirfoilSource:
    """Read a Selig or Lednicer airfoil coordinate file.

    Args:
        path: Coordinate file. A first line that is not two numbers is the name.

    Returns:
        The airfoil with its coordinates in Selig order (trailing edge, upper surface,
        leading edge, lower surface, trailing edge).

    Raises:
        ValueError: If the file holds fewer than ten coordinate pairs.
    """
    name = path.stem
    pairs: list[tuple[float, float]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        parts = line.replace(",", " ").split()
        try:
            x, y = float(parts[0]), float(parts[1])
        except (IndexError, ValueError):
            if index == 0 and line.strip():
                name = line.strip()
            continue
        pairs.append((x, y))

    if pairs and pairs[0][0] > 1.5 and pairs[0][1] > 1.5:
        # Lednicer: point counts, then the upper and the lower surface from the leading edge.
        n_upper, n_lower = int(pairs[0][0]), int(pairs[0][1])
        upper = pairs[1 : 1 + n_upper]
        lower = pairs[1 + n_upper : 1 + n_upper + n_lower]
        if lower and upper and lower[0] == upper[0]:
            lower = lower[1:]
        pairs = [*reversed(upper), *lower]

    if len(pairs) < _MIN_COORDINATES:
        raise ValueError(f"Airfoil file {path} holds {len(pairs)} coordinate pairs, too few")
    return AirfoilSource(name=name[:_NAME_LENGTH], coordinates=tuple(pairs))


def resolve_airfoil(airfoil: str) -> AirfoilSource:
    """Turn an airfoil setting into what XFOIL loads.

    Args:
        airfoil: A NACA 4- or 5-digit designation (``"NACA2412"``) or the path of a
            coordinate file, relative to the working directory.

    Returns:
        The airfoil source.

    Raises:
        ValueError: If ``airfoil`` is neither a NACA designation nor an existing file.
    """
    match = _NACA_PATTERN.match(airfoil)
    if match is not None:
        return AirfoilSource(name=f"NACA {match.group(1)}", naca_digits=match.group(1))
    path = Path(airfoil).expanduser()
    if not path.is_file():
        raise ValueError(
            f"Airfoil '{airfoil}' is neither a NACA 4- or 5-digit designation nor an "
            "existing coordinate file"
        )
    return read_airfoil_file(path)


def alpha_schedule(start: float, end: float, step: float) -> tuple[float, ...]:
    """Angles of attack from ``start`` to ``end`` inclusive [deg]."""
    count = math.floor((end - start) / step + 1e-9) + 1
    return tuple(round(start + i * step, 6) for i in range(count))


def _sweep_order(alphas: tuple[float, ...]) -> list[list[float]]:
    """Split ascending angles into an upward run from the one nearest zero and a downward run."""
    pivot = min(range(len(alphas)), key=lambda i: abs(alphas[i]))
    downward = list(reversed(alphas[:pivot]))
    return [list(alphas[pivot:]), downward] if downward else [list(alphas[pivot:])]


def _retry_order(missed: list[float]) -> list[list[float]]:
    """Approach each missed angle from a fresh boundary layer slightly nearer zero."""
    return [[alpha - math.copysign(_RETRY_OFFSET_DEG, alpha or 1.0), alpha] for alpha in missed]


def build_command_deck(
    source: AirfoilSource,
    reynolds: float,
    mach: float,
    n_crit: float,
    runs: list[list[float]],
    max_iter: int,
    polar_file: str = _POLAR_FILE,
    save_geometry: bool = True,
) -> str:
    """XFOIL keyboard input for one polar with plotting switched off.

    Args:
        source: Airfoil to analyse.
        reynolds: Chord Reynolds number.
        mach: Freestream Mach number.
        n_crit: e^n transition amplification exponent.
        runs: Angle sequences [deg]; each after the first starts from a fresh boundary layer.
        max_iter: Viscous Newton iterations allowed per angle.
        polar_file: Polar file XFOIL appends converged points to.
        save_geometry: Whether to save the paneled coordinates.

    Returns:
        The command text, one command per line.
    """
    lines = ["PLOP", "G F", ""]
    lines.append(f"NACA {source.naca_digits}" if source.naca_digits else f"LOAD {_AIRFOIL_FILE}")
    lines.append("PANE")
    if save_geometry:
        lines.append(f"SAVE {_GEOMETRY_FILE}")
    lines += [
        "OPER",
        "VPAR",
        f"N {n_crit:g}",
        "",
        f"VISC {reynolds:.0f}",
        f"MACH {mach:.6g}",
        f"ITER {max_iter}",
        "PACC",
        polar_file,
        "",
    ]
    for index, run in enumerate(runs):
        if index:
            lines.append("INIT")
        lines += [f"ALFA {alpha:g}" for alpha in run]
    lines += ["PACC", "", "QUIT"]
    return "\n".join(lines) + "\n"


def _alpha_key(alpha: float) -> float:
    """Angle of attack rounded as XFOIL prints it."""
    return round(alpha, 3)


def _polar_rows(text: str) -> dict[float, list[float]]:
    """Polar file rows keyed by angle of attack; the first row of a repeated angle wins."""
    rows: dict[float, list[float]] = {}
    lines = text.splitlines()
    start = next((i + 1 for i, line in enumerate(lines) if line.strip().startswith("-----")), len(lines))
    for line in lines[start:]:
        try:
            values = [float(p) for p in line.split()[:_POLAR_COLUMNS]]
        except ValueError:
            continue
        if len(values) == _POLAR_COLUMNS:
            rows.setdefault(_alpha_key(values[0]), values)
    return rows


def _polar_from_rows(rows: list[list[float]], reynolds: float, mach: float) -> SectionPolar:
    """Build a polar from rows sorted by angle of attack."""
    columns = list(zip(*rows, strict=True)) if rows else [()] * _POLAR_COLUMNS
    return SectionPolar(
        reynolds=reynolds,
        mach=mach,
        alpha=tuple(columns[0]),
        cl=tuple(columns[1]),
        cd=tuple(columns[2]),
        cdp=tuple(columns[3]),
        cm=tuple(columns[4]),
        xtr_top=tuple(columns[5]),
        xtr_bottom=tuple(columns[6]),
    )


def parse_polar(text: str, reynolds: float, mach: float) -> SectionPolar:
    """Parse an XFOIL polar file into ascending, de-duplicated points.

    Args:
        text: Polar file written by XFOIL's ``PACC``.
        reynolds: Chord Reynolds number of the run.
        mach: Mach number of the run.

    Returns:
        The converged points.
    """
    rows = _polar_rows(text)
    return _polar_from_rows([rows[key] for key in sorted(rows)], reynolds, mach)


def thickness_to_chord(x: tuple[float, ...], y: tuple[float, ...]) -> float:
    """Maximum thickness over chord of a section in Selig order."""
    xs, ys = np.asarray(x), np.asarray(y)
    le = int(np.argmin(xs))
    upper_order = np.argsort(xs[: le + 1])
    lower_order = np.argsort(xs[le:])
    grid = np.linspace(xs[le], xs.max(), 400)
    upper = np.interp(grid, xs[: le + 1][upper_order], ys[: le + 1][upper_order])
    lower = np.interp(grid, xs[le:][lower_order], ys[le:][lower_order])
    return float(np.max(upper - lower) / (xs.max() - xs[le]))


def parse_geometry(text: str) -> AirfoilGeometry:
    """Parse a labeled coordinate file written by XFOIL's ``SAVE``."""
    lines = text.splitlines()
    points = [tuple(float(v) for v in line.split()[:2]) for line in lines[1:] if line.split()]
    x = tuple(p[0] for p in points)
    y = tuple(p[1] for p in points)
    return AirfoilGeometry(
        name=lines[0].strip(), x=x, y=y, thickness_to_chord=thickness_to_chord(x, y)
    )


def _run_deck(executable: str, commands: str, workdir: Path, timeout_s: float) -> tuple[str, bool]:
    """Feed a command deck to XFOIL.

    Returns:
        The console output, and whether XFOIL was stopped at the time limit. XFOIL
        closes its polar file after every point, so the points before the stop remain.

    Raises:
        RuntimeError: If XFOIL crashes.
    """
    try:
        completed = subprocess.run(
            [executable],
            input=commands,
            capture_output=True,
            text=True,
            cwd=workdir,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or b""
        return (partial.decode(errors="replace") if isinstance(partial, bytes) else partial), True
    output = completed.stdout + completed.stderr
    if completed.returncode == -signal.SIGFPE:
        raise RuntimeError(FPE_MESSAGE)
    if completed.returncode != 0:
        tail = "\n".join(output.strip().splitlines()[-5:])
        raise RuntimeError(f"XFOIL exited with status {completed.returncode}:\n{tail}")
    return output, False


def run_xfoil(
    executable: str,
    source: AirfoilSource,
    reynolds: float,
    mach: float,
    n_crit: float,
    alphas: tuple[float, ...],
    max_iter: int,
    timeout_s: float,
    retry: bool = True,
) -> XfoilRun:
    """Run one XFOIL polar in a temporary directory, retrying angles that fail.

    The upward sweep, the downward sweep and the retries run as separate XFOIL calls,
    each within ``timeout_s``, so a diverged sweep cannot hold up the others.

    Args:
        executable: XFOIL executable.
        source: Airfoil to analyse.
        reynolds: Chord Reynolds number.
        mach: Freestream Mach number.
        n_crit: e^n transition amplification exponent.
        alphas: Ascending angles of attack [deg].
        max_iter: Viscous Newton iterations allowed per angle.
        timeout_s: Wall-clock limit of each XFOIL call [s].
        retry: Whether to retry the angles that fail, from a fresh boundary layer.

    Returns:
        The polar at the requested angles that converged, the paneled geometry and
        the raw input and output.

    Raises:
        RuntimeError: If XFOIL crashes or cannot build the airfoil.
        XfoilConvergenceError: If no angle converges.
    """
    calls = [(name, [run]) for name, run in zip(("upward", "downward"), _sweep_order(alphas), strict=False)]
    rows: dict[float, list[float]] = {}
    commands = output = polar_text = ""
    stopped: list[str] = []
    geometry: AirfoilGeometry | None = None
    with tempfile.TemporaryDirectory(prefix="yaado_xfoil_") as tmp:
        workdir = Path(tmp)
        if source.naca_digits is None:
            body = "\n".join(f"{x:.7f} {y:.7f}" for x, y in source.coordinates)
            (workdir / _AIRFOIL_FILE).write_text(f"{source.name}\n{body}\n", encoding="utf-8")

        for index, (name, runs) in enumerate([*calls, ("retry", [])]):
            if name == "retry":
                misses = [alpha for alpha in alphas if _alpha_key(alpha) not in rows]
                if not (retry and misses):
                    break
                runs = _retry_order(misses)
            polar_file = f"polar_{name}.txt"
            deck = build_command_deck(
                source, reynolds, mach, n_crit, runs, max_iter,
                polar_file=polar_file, save_geometry=index == 0,
            )
            call_output, timed_out = _run_deck(executable, deck, workdir, timeout_s)
            commands += deck
            output += call_output
            if timed_out:
                stopped.append(name)
            if geometry is None:
                geometry_path = workdir / _GEOMETRY_FILE
                if not geometry_path.is_file():
                    raise RuntimeError(f"XFOIL could not build the airfoil '{source.name}'")
                geometry = parse_geometry(geometry_path.read_text(encoding="utf-8"))
            polar_path = workdir / polar_file
            if polar_path.is_file():
                text = polar_path.read_text(encoding="utf-8")
                polar_text += text
                for key, row in _polar_rows(text).items():
                    rows.setdefault(key, row)

    kept = [rows[_alpha_key(alpha)] for alpha in alphas if _alpha_key(alpha) in rows]
    polar = _polar_from_rows(kept, reynolds, mach)
    if geometry is None or not polar.alpha:
        raise XfoilConvergenceError(
            f"XFOIL converged at none of the {len(alphas)} angles at Re {reynolds:.3g}"
        )
    missed = tuple(alpha for alpha in alphas if _alpha_key(alpha) not in rows)
    return XfoilRun(polar, geometry, missed, tuple(stopped), commands, output, polar_text)


def polar_metrics(polar: SectionPolar, slope_window_deg: tuple[float, float]) -> PolarMetrics:
    """Read the design numbers off a polar.

    Args:
        polar: Converged points, ascending in angle of attack.
        slope_window_deg: Angles around the zero-lift angle, below and above it, over
            which the lift slope is fitted [deg].

    Returns:
        Maximum lift, best lift-to-drag ratio, minimum drag and the zero-lift values.
    """
    alpha = np.asarray(polar.alpha)
    cl = np.asarray(polar.cl)
    cd = np.asarray(polar.cd)
    cm = np.asarray(polar.cm)
    i_max = int(np.argmax(cl))
    i_ld = int(np.argmax(cl / cd))
    i_cd = int(np.argmin(cd))

    alpha_zero_lift: float | None = None
    cm_zero_lift: float | None = None
    for i in range(len(alpha) - 1):
        if cl[i] <= 0.0 <= cl[i + 1] and cl[i + 1] > cl[i]:
            t = -cl[i] / (cl[i + 1] - cl[i])
            alpha_zero_lift = float(alpha[i] + t * (alpha[i + 1] - alpha[i]))
            cm_zero_lift = float(cm[i] + t * (cm[i + 1] - cm[i]))
            break

    cl_alpha: float | None = None
    if alpha_zero_lift is not None:
        low, high = alpha_zero_lift + slope_window_deg[0], alpha_zero_lift + slope_window_deg[1]
        mask = (alpha >= low) & (alpha <= min(high, alpha[i_max]))
        if np.count_nonzero(mask) >= 3:
            cl_alpha = float(np.polyfit(np.radians(alpha[mask]), cl[mask], 1)[0])

    return PolarMetrics(
        cl_max=float(cl[i_max]),
        alpha_cl_max=float(alpha[i_max]),
        stall_reached=i_max < len(cl) - 1,
        max_lift_to_drag=float(cl[i_ld] / cd[i_ld]),
        alpha_max_lift_to_drag=float(alpha[i_ld]),
        cd_min=float(cd[i_cd]),
        cl_at_cd_min=float(cl[i_cd]),
        cl_alpha=cl_alpha,
        alpha_zero_lift=alpha_zero_lift,
        cm_zero_lift=cm_zero_lift,
    )


class XFOILAnalysis(BaseAnalysis[XfoilPolarResults]):
    """XFOIL polar of the section of one wing or fin set at one flight condition.

    Example:
        analysis = XFOILAnalysis()
        analysis.setup(vehicle, surface="main_wing", mach=0.1)
        results = analysis.execute()
        best_l_over_d = results.max_lift_to_drag
    """

    fidelity = FidelityLevel.LEVEL_1

    DEFAULT_MACH: ClassVar[float] = 0.15
    DEFAULT_ALTITUDE_M: ClassVar[float] = 0.0
    DEFAULT_N_CRIT: ClassVar[float] = 9.0
    DEFAULT_ALPHA_START_DEG: ClassVar[float] = -5.0
    DEFAULT_ALPHA_END_DEG: ClassVar[float] = 15.0
    DEFAULT_ALPHA_STEP_DEG: ClassVar[float] = 0.5

    #: Karman-Tsien correction stays credible below about this Mach number.
    MAX_MACH: ClassVar[float] = 0.7
    MAX_ALPHA_DEG: ClassVar[float] = 30.0
    MAX_ALPHA_POINTS: ClassVar[int] = 241
    MIN_REYNOLDS: ClassVar[float] = 1.0e4
    #: Below this Reynolds number laminar separation bubbles make XFOIL less reliable.
    LOW_REYNOLDS_WARNING: ClassVar[float] = 5.0e4
    MAX_ITER: ClassVar[int] = 100
    #: Wall-clock limit of each XFOIL call: upward sweep, downward sweep and retries [s].
    TIMEOUT_S: ClassVar[float] = 20.0
    #: Shorter limit for the Reynolds number sweep, which skips retries [s].
    SWEEP_TIMEOUT_S: ClassVar[float] = 10.0
    #: Lift slope fit window around the zero-lift angle [deg].
    SLOPE_WINDOW_DEG: ClassVar[tuple[float, float]] = (-2.0, 6.0)
    SWEEP_REYNOLDS_FACTORS: ClassVar[tuple[float, ...]] = (0.25, 0.5, 2.0, 4.0)

    def __init__(self, name: str = "xfoil_polar") -> None:
        super().__init__(name)
        self._executable = ""
        self._surface = ""
        self._airfoil = ""
        self._source = AirfoilSource(name="")
        self._chord = 0.0
        self._altitude = self.DEFAULT_ALTITUDE_M
        self._mach = self.DEFAULT_MACH
        self._velocity = 0.0
        self._reynolds = 0.0
        self._n_crit = self.DEFAULT_N_CRIT
        self._alphas: tuple[float, ...] = ()

    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        surface: str | None = None,
        mach: float = DEFAULT_MACH,
        altitude_m: float = DEFAULT_ALTITUDE_M,
        alpha_start_deg: float = DEFAULT_ALPHA_START_DEG,
        alpha_end_deg: float = DEFAULT_ALPHA_END_DEG,
        alpha_step_deg: float = DEFAULT_ALPHA_STEP_DEG,
        n_crit: float = DEFAULT_N_CRIT,
        airfoil: str | None = None,
        chord: float | None = None,
        reynolds: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Pick the surface, its section and chord, and the flight condition.

        Args:
            vehicle: Vehicle with at least one wing or fin set.
            surface: Component in ``vehicle.aero_surfaces``. May be omitted if the
                vehicle has only one.
            mach: Flight Mach number, below :attr:`MAX_MACH`.
            altitude_m: ISA altitude [m].
            alpha_start_deg: First angle of attack [deg].
            alpha_end_deg: Last angle of attack [deg].
            alpha_step_deg: Angle of attack step [deg].
            n_crit: e^n transition exponent: 9 for an average wind tunnel, 11-13 for
                clean free flight, 4-8 for turbulent air.
            airfoil: NACA designation or coordinate file. Defaults to the surface's
                ``section_airfoil``.
            chord: Chord of the Reynolds number [m]. Defaults to the surface's mean
                aerodynamic chord.
            reynolds: Chord Reynolds number. Defaults to the value at the flight condition.
            **kwargs: Not accepted; present for the ``BaseAnalysis`` signature.

        Raises:
            TypeError: If an unknown setting is passed or the component is not a surface.
            RuntimeError: If no XFOIL executable is on PATH.
            ValueError: If the surface, airfoil or chord cannot be resolved, or a setting
                is out of range.
        """
        if kwargs:
            raise TypeError(f"Unknown settings for '{self.name}': {sorted(kwargs)}")
        executable = xfoil_executable()
        if executable is None:
            raise RuntimeError(MISSING_MESSAGE)

        surfaces = vehicle.get_components_by_type(AERO_COMPONENTS)
        if surface is None:
            if len(surfaces) != 1:
                raise ValueError(
                    f"Vehicle '{vehicle.name}' has {len(surfaces)} aerodynamic surfaces "
                    f"{sorted(surfaces)}: pick one with surface=NAME"
                )
            surface = next(iter(surfaces))
        component = vehicle.get_component(surface, expected_type=AERO_COMPONENTS)

        airfoil = airfoil or component.section_airfoil
        if not airfoil:
            raise ValueError(
                f"Surface '{surface}' has no airfoil: pick one under Airfoil "
                "(airfoil=NACA0010 in bare mode), or add airfoil to it in the TOML"
            )
        source = resolve_airfoil(airfoil)

        if chord is None:
            chord = component.mean_aerodynamic_chord
            if chord is None:
                raise ValueError(
                    f"Surface '{surface}' needs chord_root and chord_tip, or set chord"
                )
        if chord <= 0.0:
            raise ValueError(f"chord must be positive, got {chord}")
        if not 0.0 <= mach <= self.MAX_MACH:
            raise ValueError(f"XFOIL needs a Mach number in [0, {self.MAX_MACH}], got {mach}")
        if not 0.0 < n_crit <= 20.0:
            raise ValueError(f"n_crit must be in (0, 20], got {n_crit}")
        if alpha_step_deg <= 0.0 or alpha_end_deg < alpha_start_deg:
            raise ValueError(
                "Angles need alpha_start_deg <= alpha_end_deg and alpha_step_deg > 0"
            )
        if max(abs(alpha_start_deg), abs(alpha_end_deg)) > self.MAX_ALPHA_DEG:
            raise ValueError(f"Angles of attack must lie within +-{self.MAX_ALPHA_DEG:g} deg")
        alphas = alpha_schedule(alpha_start_deg, alpha_end_deg, alpha_step_deg)
        if len(alphas) > self.MAX_ALPHA_POINTS:
            raise ValueError(
                f"{len(alphas)} angles requested; increase alpha_step_deg to stay within "
                f"{self.MAX_ALPHA_POINTS}"
            )

        atmosphere = isa_atmosphere(altitude_m)
        velocity = mach * atmosphere.speed_of_sound
        if reynolds is None:
            reynolds = atmosphere.density * velocity * chord / atmosphere.dynamic_viscosity
        if reynolds < self.MIN_REYNOLDS:
            raise ValueError(
                f"Reynolds number {reynolds:.3g} is below {self.MIN_REYNOLDS:.0e}: raise the "
                "Mach number or set reynolds"
            )

        self._executable = executable
        self._surface = surface
        self._airfoil = airfoil
        self._source = source
        self._chord = chord
        self._altitude = altitude_m
        self._mach = mach
        self._velocity = velocity
        self._reynolds = reynolds
        self._n_crit = n_crit
        self._alphas = alphas
        self.logger.info(
            "Configured XFOIL for '%s' on vehicle '%s': %s, chord %.4f m, M=%.3f, Re=%.4g",
            surface,
            vehicle.name,
            source.name,
            chord,
            mach,
            reynolds,
        )

    def _compute(self, **kwargs: Any) -> XfoilPolarResults:
        """Run XFOIL and read the design numbers off its polar."""
        run = run_xfoil(
            self._executable,
            self._source,
            self._reynolds,
            self._mach,
            self._n_crit,
            self._alphas,
            self.MAX_ITER,
            self.TIMEOUT_S,
        )
        self.logger.save_artifact("xfoil_input.txt", run.commands)
        self.logger.save_artifact("xfoil_output.log", run.output)
        self.logger.save_artifact("xfoil_polar.txt", run.polar_text)

        polar = run.polar
        metrics = polar_metrics(polar, self.SLOPE_WINDOW_DEG)
        assumptions: list[str] = []
        if run.stopped:
            stages = " and ".join(_STAGE_NAMES[name] for name in run.stopped)
            assumptions.append(
                f"XFOIL diverged and was stopped after {self.TIMEOUT_S:g} s in the {stages}; "
                "angles it had not reached are left out."
            )
        missed = run.missed
        if missed:
            shown = ", ".join(f"{alpha:g}" for alpha in missed[:8])
            more = ", ..." if len(missed) > 8 else ""
            assumptions.append(
                f"XFOIL did not converge at {len(missed)} of {len(self._alphas)} angles "
                f"({shown}{more} deg); they are left out."
            )
        if not metrics.stall_reached:
            assumptions.append(
                f"Lift still rises at {metrics.alpha_cl_max:g} deg, the last converged angle: "
                "CLmax and stall lie beyond the sweep."
            )
        if self._reynolds < self.LOW_REYNOLDS_WARNING:
            assumptions.append(
                f"Reynolds number {self._reynolds:.3g} is low: laminar separation bubbles "
                "dominate and XFOIL is less reliable."
            )

        self.logger.info(
            "CLmax %.3f at %.1f deg, (L/D)max %.1f, CDmin %.5f, %d of %d angles converged",
            metrics.cl_max,
            metrics.alpha_cl_max,
            metrics.max_lift_to_drag,
            metrics.cd_min,
            len(polar.alpha),
            len(self._alphas),
        )
        return XfoilPolarResults(
            name=self.name,
            fidelity=self.fidelity,
            surface=self._surface,
            airfoil=self._airfoil,
            geometry=run.geometry,
            thickness_to_chord=run.geometry.thickness_to_chord,
            chord=self._chord,
            altitude=self._altitude,
            mach=self._mach,
            velocity=self._velocity,
            reynolds=self._reynolds,
            n_crit=self._n_crit,
            alpha_requested=self._alphas,
            polar=polar,
            n_converged=len(polar.alpha),
            cl_max=metrics.cl_max,
            alpha_cl_max=metrics.alpha_cl_max,
            stall_reached=metrics.stall_reached,
            max_lift_to_drag=metrics.max_lift_to_drag,
            alpha_max_lift_to_drag=metrics.alpha_max_lift_to_drag,
            cd_min=metrics.cd_min,
            cl_at_cd_min=metrics.cl_at_cd_min,
            cl_alpha=metrics.cl_alpha,
            alpha_zero_lift=metrics.alpha_zero_lift,
            cm_zero_lift=metrics.cm_zero_lift,
            assumptions=tuple(assumptions),
        )

    def validate_results(self, results: XfoilPolarResults) -> bool:
        """Check for positive drag, a real section and a positive Reynolds number.

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        return (
            results.n_converged > 0
            and all(cd > 0.0 for cd in results.polar.cd)
            and 0.0 < results.thickness_to_chord < 1.0
            and results.reynolds > 0.0
            and results.chord > 0.0
        )


def run_reynolds_sweep(
    results: XfoilPolarResults,
    factors: tuple[float, ...] = XFOILAnalysis.SWEEP_REYNOLDS_FACTORS,
) -> list[ReynoldsSweepPoint]:
    """Polars of the same section at multiples of the run's Reynolds number.

    Failed angles are not retried, and Reynolds numbers where XFOIL converges nowhere
    are skipped.

    Args:
        results: Results of the run; it is included at its own Reynolds number.
        factors: Multiples of ``results.reynolds`` to run.

    Returns:
        Points in ascending Reynolds number.

    Raises:
        RuntimeError: If no XFOIL executable is on PATH or XFOIL crashes.
    """
    executable = xfoil_executable()
    if executable is None:
        raise RuntimeError(MISSING_MESSAGE)
    geometry = results.geometry
    source = AirfoilSource(name=geometry.name, coordinates=tuple(zip(geometry.x, geometry.y, strict=True)))
    window = XFOILAnalysis.SLOPE_WINDOW_DEG
    points = [ReynoldsSweepPoint(results.polar, polar_metrics(results.polar, window))]
    for factor in factors:
        try:
            run = run_xfoil(
                executable,
                source,
                results.reynolds * factor,
                results.mach,
                results.n_crit,
                results.alpha_requested,
                XFOILAnalysis.MAX_ITER,
                XFOILAnalysis.SWEEP_TIMEOUT_S,
                retry=False,
            )
        except XfoilConvergenceError:
            continue
        points.append(ReynoldsSweepPoint(run.polar, polar_metrics(run.polar, window)))
    return sorted(points, key=lambda p: p.polar.reynolds)


def format_polar_csv(polar: SectionPolar) -> str:
    """CSV text of a polar."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["alpha_deg", "cl", "cd", "cdp", "cm", "cl_over_cd", "xtr_top", "xtr_bottom"])
    writer.writerows(
        zip(
            polar.alpha,
            polar.cl,
            polar.cd,
            polar.cdp,
            polar.cm,
            polar.cl_over_cd,
            polar.xtr_top,
            polar.xtr_bottom,
            strict=True,
        )
    )
    return buffer.getvalue()


def format_reynolds_sweep_csv(points: list[ReynoldsSweepPoint]) -> str:
    """CSV text of the design numbers at each Reynolds number."""
    names = [f.name for f in fields(PolarMetrics)]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["reynolds", *names])
    for point in points:
        writer.writerow([point.polar.reynolds, *(getattr(point.metrics, n) for n in names)])
    return buffer.getvalue()


def plot_polar(results: XfoilPolarResults) -> Figure:
    """Plot the section and its lift, drag, lift-to-drag and moment curves.

    Args:
        results: Results of the run.

    Returns:
        The matplotlib Figure instance.
    """
    import matplotlib.pyplot as plt

    polar = results.polar
    fig = plt.figure(figsize=(11.0, 9.0))
    grid = fig.add_gridspec(3, 2, height_ratios=(0.55, 2.0, 2.0))
    ax_shape = fig.add_subplot(grid[0, :])
    ax_cl = fig.add_subplot(grid[1, 0])
    ax_drag = fig.add_subplot(grid[1, 1])
    ax_ld = fig.add_subplot(grid[2, 0])
    ax_cm = fig.add_subplot(grid[2, 1])

    ax_shape.fill(results.geometry.x, results.geometry.y, color="tab:blue", alpha=0.25)
    ax_shape.plot(results.geometry.x, results.geometry.y, color="tab:blue", lw=1.0)
    ax_shape.set_aspect("equal")
    ax_shape.axis("off")
    ax_shape.set_title(
        f"{results.geometry.name} (t/c {results.thickness_to_chord:.1%}) on {results.surface}: "
        f"Re {results.reynolds:.3g}, M {results.mach:g}, Ncrit {results.n_crit:g}"
    )

    ax_cl.plot(polar.alpha, polar.cl, ".-")
    ax_cl.plot(results.alpha_cl_max, results.cl_max, "o", color="k",
               label=f"CLmax {results.cl_max:.3f}")
    ax_cl.set_xlabel("Angle of attack [deg]")
    ax_cl.set_ylabel("CL [-]")

    ax_drag.plot(polar.cd, polar.cl, ".-")
    ax_drag.set_xlim(left=0.0)
    ax_drag.set_xlabel("CD [-]")
    ax_drag.set_ylabel("CL [-]")

    ax_ld.plot(polar.alpha, polar.cl_over_cd, ".-")
    ax_ld.plot(results.alpha_max_lift_to_drag, results.max_lift_to_drag, "o", color="k",
               label=f"(L/D)max {results.max_lift_to_drag:.1f}")
    ax_ld.set_xlabel("Angle of attack [deg]")
    ax_ld.set_ylabel("CL/CD [-]")

    ax_cm.plot(polar.alpha, polar.cm, ".-")
    ax_cm.set_xlabel("Angle of attack [deg]")
    ax_cm.set_ylabel("CM c/4 [-]")

    for ax in (ax_cl, ax_drag, ax_ld, ax_cm):
        ax.grid(True, alpha=0.3)
    for ax in (ax_cl, ax_ld):
        ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def plot_reynolds_sweep(points: list[ReynoldsSweepPoint], results: XfoilPolarResults) -> Figure:
    """Plot the lift curve and the drag polar at each Reynolds number.

    Args:
        points: Output of :func:`run_reynolds_sweep`.
        results: Results of the run, drawn bold.

    Returns:
        The matplotlib Figure instance.
    """
    import matplotlib.pyplot as plt

    fig, (ax_cl, ax_drag) = plt.subplots(1, 2, figsize=(11.0, 5.0))
    for point in points:
        polar = point.polar
        is_run = polar.reynolds == results.reynolds
        style: dict[str, Any] = {"lw": 2.2 if is_run else 1.0, "label": f"Re {polar.reynolds:.3g}"}
        ax_cl.plot(polar.alpha, polar.cl, **style)
        ax_drag.plot(polar.cd, polar.cl, **style)
    ax_cl.set_xlabel("Angle of attack [deg]")
    ax_cl.set_ylabel("CL [-]")
    ax_drag.set_xlim(left=0.0)
    ax_drag.set_xlabel("CD [-]")
    ax_drag.set_ylabel("CL [-]")
    fig.suptitle(f"{results.geometry.name} on {results.surface}: Reynolds number effect")
    for ax in (ax_cl, ax_drag):
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    fig.tight_layout()
    return fig
