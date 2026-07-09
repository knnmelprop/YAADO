# MELprop-IADE | analyses.cfd.su2_config_template | v0.2.0
"""SU2 external-aerodynamics configuration generator for the ramjet rocket.

Generates SU2 ``.cfg`` files for an inviscid (Euler) Mach sweep of the
ramjet rocket, to extract CL/CD/Cm across the transonic-supersonic
envelope. This is the escalation path beyond AVL for Project B: AVL
(vortex-lattice) is only valid for Mach < 0.6 and |alpha| < 15 deg
(project rule #7 / ``analyses/aerodynamics/avl_wrapper.py``), so the
whole :data:`MACH_SWEEP` here (0.8-3.0) sits outside AVL's envelope and
is instead handled with SU2's compressible Euler solver, complementing
the Barrowman/DATCOM-style empirical drag estimates used elsewhere.

IMPORTANT -- this module only *writes* SU2 configuration text files. It
never invokes ``su2_CFD``, ``gmsh``, or any other external binary: none
of those are installed in this environment (see ``doc/AGENT_CONTEXT.md``
Section 3). Every generated file carries a ``# TO RUN: su2_CFD
<file>.cfg`` comment so a human (or a future CI job with SU2 installed)
knows how to actually execute it, plus the ``MESH_FILENAME`` a
corresponding gmsh run must produce first.

Geometry (body length/diameter, fin span/chord) is read from the
committed vehicle config (``vehicles/ramjet_rocket/vehicle_config.yaml``)
via :class:`~src.schemas.vehicle_schema.RocketConfig` -- it is never
hard-coded here, so the generated decks stay in sync with the vehicle
definition. Freestream conditions use the same ICAO troposphere formula
as ``analyses/trajectory/booster_burnout.py`` (:func:`isa_atmosphere`
below), evaluated at the ramjet design altitude
(``analyses.propulsion.inlet_performance.DESIGN_ALTITUDE_M``, 10,000 m).
The formula is re-implemented locally (instead of importing
``booster_burnout``) to avoid pulling that module's ``matplotlib``
plotting dependency into a plain ``.cfg``-file generator.

Workflow (to be completed once SU2/gmsh are available in a container):
    1. Mesh generation with gmsh from the axisymmetric body + fins
       (``MESH_FILENAME`` in each generated config is the expected
       gmsh output; not produced by this module).
    2. ``su2_CFD <file>.cfg`` per Mach number (Euler first, then
       RANS/SA if viscous drag corroboration is needed).
    3. Force-coefficient extraction (CL, CD, Cm) from the SU2 history
       file for a drag-polar table consumed by the trajectory workflow.

Theory / tooling reference:
    Economon, T. D. et al., "SU2: An Open-Source Suite for Multiphysics
    Simulation and Design", AIAA Journal 54(3), 2016.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analyses.propulsion.inlet_performance import DESIGN_ALTITUDE_M
from core.component_base import AnalysisResults, BaseAnalysis, FidelityLevel
from src.schemas.vehicle_schema import BaseVehicleConfig, RocketConfig

#: Mach numbers swept for the external-aero study (transonic -> Mach 3,
#: i.e. entirely above the AVL applicability ceiling of Mach 0.6).
MACH_SWEEP: tuple[float, ...] = (0.8, 1.5, 2.0, 2.5, 3.0)

#: ISA sea-level standard temperature [K] (ICAO Doc 7488).
_T0_ISA_K: float = 288.15
#: ISA sea-level standard pressure [Pa] (ICAO Doc 7488).
_P0_ISA_PA: float = 101325.0
#: ISA troposphere lapse rate [K/m] (0 <= h < 11000 m).
_LAPSE_RATE_K_PER_M: float = 0.0065
#: Specific gas constant for dry air [J/(kg*K)].
_R_AIR_J_PER_KGK: float = 287.05
#: Gravitational acceleration [m/s^2].
_G0_MS2: float = 9.80665
#: ISA troposphere pressure-altitude exponent, g0 / (lapse_rate * R_air).
_ISA_PRESSURE_EXPONENT: float = _G0_MS2 / (_LAPSE_RATE_K_PER_M * _R_AIR_J_PER_KGK)


def isa_atmosphere(altitude_m: float) -> tuple[float, float, float]:
    """Evaluate the ICAO standard atmosphere in the troposphere layer.

    Re-implements the same troposphere formula used by
    ``analyses/trajectory/booster_burnout.py::isa_atmosphere`` (kept
    local here to avoid importing that module's ``matplotlib``
    plotting dependency for a plain ``.cfg``-file generator).

    Args:
        altitude_m: Geometric altitude [m]. Clamped to ``>= 0``.

    Returns:
        Tuple ``(temperature_K, pressure_Pa, density_kg_m3)``.
    """
    h = max(altitude_m, 0.0)
    temperature_K = _T0_ISA_K - _LAPSE_RATE_K_PER_M * h
    pressure_Pa = _P0_ISA_PA * (temperature_K / _T0_ISA_K) ** _ISA_PRESSURE_EXPONENT
    density_kg_m3 = pressure_Pa / (_R_AIR_J_PER_KGK * temperature_K)
    return temperature_K, pressure_Pa, density_kg_m3

#: Repository root, resolved from this file's location.
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

#: Default vehicle config this generator reads geometry from.
VEHICLE_CONFIG_PATH: Path = (
    REPO_ROOT / "vehicles" / "ramjet_rocket" / "vehicle_config.yaml"
)

#: Directory the generated ``.cfg`` files are written into (next to this
#: module, mirroring the output-path convention used by the other
#: ``analyses/`` modules, e.g. ``analyses/stability/*.json``).
OUTPUT_DIR: Path = Path(__file__).resolve().parent / "su2_configs"

#: SU2 config keys common to every Mach case (Euler, no viscous terms).
_BASE_CONFIG: dict[str, str] = {
    "SOLVER": "EULER",
    "MATH_PROBLEM": "DIRECT",
    "REF_DIMENSIONALIZATION": "DIMENSIONAL",
    "MARKER_EULER": "( airframe )",
    "MARKER_FAR": "( farfield )",
    "CONV_NUM_METHOD_FLOW": "JST",
    "NUM_METHOD_GRAD": "WEIGHTED_LEAST_SQUARES",
    "CFL_NUMBER": "5.0",
    "CONV_CRITERIA": "RESIDUAL",
    "CONV_RESIDUAL_MINVAL": "-8",
    "ITER": "5000",
    "OUTPUT_FILES": "(RESTART, PARAVIEW, SURFACE_CSV)",
    "HISTORY_OUTPUT": "(ITER, RMS_RES, AERO_COEFF)",
}


def load_rocket_config(path: Path | str = VEHICLE_CONFIG_PATH) -> RocketConfig:
    """Load and validate the ramjet-rocket vehicle configuration.

    Args:
        path: Path to a ``vehicle_config.yaml`` for Project B.

    Returns:
        Validated :class:`RocketConfig`.

    Raises:
        TypeError: If the YAML at ``path`` is not a rocket config
            (e.g. the GTM-140 drone config was passed by mistake).
    """
    config = BaseVehicleConfig.from_yaml(path)
    if not isinstance(config, RocketConfig):
        raise TypeError(
            f"{path} did not load as a RocketConfig (got {type(config).__name__}); "
            "this generator is for Project B (ramjet_rocket) only"
        )
    return config


def su2_config_filename(mach: float) -> str:
    """Return the conventional filename for a Mach case's SU2 config.

    Args:
        mach: Freestream Mach number.

    Returns:
        Filename of the form ``su2_ramjet_mach{M}.cfg``, e.g.
        ``su2_ramjet_mach2p50.cfg`` for Mach 2.5.
    """
    mach_tag = f"{mach:.2f}".replace(".", "p")
    return f"su2_ramjet_mach{mach_tag}.cfg"


def build_su2_config(
    config: RocketConfig,
    mach: float,
    aoa_deg: float = 0.0,
    altitude_m: float = DESIGN_ALTITUDE_M,
) -> str:
    """Render an SU2 Euler ``.cfg`` text for one Mach/AoA case.

    Geometry (reference area/length, body length, fin span/chord) is
    pulled from ``config`` so the deck stays in sync with the committed
    vehicle YAML; only the solver numerics in :data:`_BASE_CONFIG` and
    the freestream state (ISA at ``altitude_m``) are template constants.

    Args:
        config: Validated two-stage rocket configuration (Project B).
        mach: Freestream Mach number. Intended for the transonic/
            supersonic regime (Mach >= 0.6) where AVL is invalid;
            no upper/lower bound is enforced here so the sweep can be
            extended, but values are expected to be >= 0.6 in practice.
        aoa_deg: Angle of attack in degrees.
        altitude_m: ISA altitude [m] used for freestream pressure and
            temperature (defaults to the ramjet design altitude used
            elsewhere in the project, 10,000 m).

    Returns:
        SU2 configuration file contents as a string, ready to write to
        disk (not executed by this function).

    Raises:
        ValueError: If required geometry fields are missing or
            non-physical (mirrors the guard in ``analyses/aero/
            avl_builder.py::build_avl_deck``).
    """
    if config.body.diameter_m <= 0.0:
        raise ValueError("body.diameter_m must be > 0")
    if config.fins.span_m <= 0.0:
        raise ValueError("fins.span_m must be > 0")

    d_ref_m = config.body.diameter_m
    a_ref_m2 = math.pi / 4.0 * d_ref_m**2
    body_length_m = config.body.total_length_m or config.body.length_m
    fin_span_m = config.fins.span_m
    fin_chord_root_m = config.fins.chord_root_m or fin_span_m
    fin_chord_tip_m = config.fins.chord_tip_m or fin_chord_root_m
    fin_count = config.fins.count

    temperature_K, pressure_Pa, _density_kg_m3 = isa_atmosphere(altitude_m)

    filename = su2_config_filename(mach)
    restart_stem = filename.rsplit(".", 1)[0]

    lines: list[str] = [
        f"% MELprop-IADE ramP -- SU2 Euler case, vehicle={config.name!r}",
        f"% Mach={mach}  AoA={aoa_deg} deg  altitude={altitude_m:.0f} m ISA",
        "# TO RUN: su2_CFD " + filename,
        "%",
        "% --- Geometry (from vehicles/ramjet_rocket/vehicle_config.yaml) ---",
        f"% body_length_m= {body_length_m:.4f}",
        f"% body_diameter_m= {d_ref_m:.4f}",
        f"% fin_count= {fin_count}",
        f"% fin_span_m= {fin_span_m:.4f}",
        f"% fin_chord_root_m= {fin_chord_root_m:.4f}",
        f"% fin_chord_tip_m= {fin_chord_tip_m:.4f}",
        "%",
    ]
    lines += [f"{k}= {v}" for k, v in _BASE_CONFIG.items()]
    lines += [
        "%",
        "% --- Flight condition ---",
        f"MACH_NUMBER= {mach}",
        f"AOA= {aoa_deg}",
        f"FREESTREAM_TEMPERATURE= {temperature_K:.2f}  % ISA @ {altitude_m:.0f} m [K]",
        f"FREESTREAM_PRESSURE= {pressure_Pa:.1f}  % ISA @ {altitude_m:.0f} m [Pa]",
        "%",
        "% --- Reference quantities (body-diameter based) ---",
        "REF_ORIGIN_MOMENT_X= "
        f"{config.mass_properties.cg_from_nose_m if config.mass_properties else 0.0:.4f}",
        "REF_ORIGIN_MOMENT_Y= 0.0",
        "REF_ORIGIN_MOMENT_Z= 0.0",
        f"REF_AREA= {a_ref_m2:.6f}  % pi/4 * d_ref^2 [m^2]",
        f"REF_LENGTH= {d_ref_m:.4f}  % body diameter d_ref [m]",
        "%",
        "% --- Mesh (gmsh output; not produced by this module) ---",
        "MESH_FILENAME= ramp_airframe.su2  % TODO: gmsh axisymmetric body+fins mesh",
        "MESH_FORMAT= SU2",
        f"SOLUTION_FILENAME= restart_{restart_stem}.dat",
        f"RESTART_FILENAME= restart_{restart_stem}.dat",
        f"CONV_FILENAME= history_{restart_stem}",
    ]
    return "\n".join(lines) + "\n"


def build_mach_sweep(
    config: RocketConfig | None = None,
    mach_sweep: tuple[float, ...] = MACH_SWEEP,
    aoa_deg: float = 0.0,
    altitude_m: float = DESIGN_ALTITUDE_M,
) -> dict[float, str]:
    """Build SU2 configs for every Mach in ``mach_sweep``.

    Args:
        config: Rocket configuration; loaded from
            :data:`VEHICLE_CONFIG_PATH` if omitted.
        mach_sweep: Mach numbers to generate a case for.
        aoa_deg: Angle of attack in degrees, shared by all cases.
        altitude_m: ISA altitude [m] for the freestream state.

    Returns:
        Mapping of Mach number to its SU2 ``.cfg`` text.
    """
    if config is None:
        config = load_rocket_config()
    return {
        mach: build_su2_config(config, mach, aoa_deg=aoa_deg, altitude_m=altitude_m)
        for mach in mach_sweep
    }


def write_mach_sweep_configs(
    config: RocketConfig | None = None,
    output_dir: Path | str = OUTPUT_DIR,
    mach_sweep: tuple[float, ...] = MACH_SWEEP,
    aoa_deg: float = 0.0,
    altitude_m: float = DESIGN_ALTITUDE_M,
) -> list[Path]:
    """Generate and write one SU2 ``.cfg`` file per Mach number to disk.

    This performs file generation ONLY -- it never invokes ``su2_CFD``,
    ``gmsh``, or any other external binary.

    Args:
        config: Rocket configuration; loaded from
            :data:`VEHICLE_CONFIG_PATH` if omitted.
        output_dir: Directory to write the ``.cfg`` files into (created
            if missing).
        mach_sweep: Mach numbers to generate a case for.
        aoa_deg: Angle of attack in degrees, shared by all cases.
        altitude_m: ISA altitude [m] for the freestream state.

    Returns:
        List of paths written, one per entry in ``mach_sweep``, in the
        same order.
    """
    if config is None:
        config = load_rocket_config()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for mach in mach_sweep:
        text = build_su2_config(config, mach, aoa_deg=aoa_deg, altitude_m=altitude_m)
        path = output_dir / su2_config_filename(mach)
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


class SU2ConfigGeneration(BaseAnalysis):
    """Generates SU2 Euler ``.cfg`` files for the ramjet Mach sweep.

    This is a Level-2 (Euler CFD) *preprocessing* analysis: it writes
    solver-ready configuration text but never runs SU2 itself (not
    installed in this environment). ``execute()`` returns the count and
    paths of the configs written so downstream workflows can locate them
    once a container with SU2 is used to actually run the cases.

    Example:
        >>> analysis = SU2ConfigGeneration()
        >>> analysis.setup(rocket_config)
        >>> results = analysis.execute()
        >>> results["n_configs"]  # doctest: +SKIP
    """

    fidelity = FidelityLevel.LEVEL_2

    def __init__(self, name: str = "su2_euler_mach_sweep") -> None:
        super().__init__(name)
        self._config: RocketConfig | None = None
        self._mach_sweep: tuple[float, ...] = MACH_SWEEP
        self._aoa_deg = 0.0
        self._altitude_m = DESIGN_ALTITUDE_M
        self._output_dir = OUTPUT_DIR

    def setup(
        self,
        vehicle_config: RocketConfig,
        mach_sweep: tuple[float, ...] = MACH_SWEEP,
        aoa_deg: float = 0.0,
        altitude_m: float = DESIGN_ALTITUDE_M,
        output_dir: Path | str = OUTPUT_DIR,
    ) -> None:
        """Bind the analysis to a rocket config and Mach sweep.

        Args:
            vehicle_config: Validated rocket configuration with body/fins.
            mach_sweep: Mach numbers to generate a case for.
            aoa_deg: Angle of attack in degrees, shared by all cases.
            altitude_m: ISA altitude [m] for the freestream state.
            output_dir: Directory the ``.cfg`` files are written into.

        Raises:
            ValueError: If the config has no body/fins definition.
        """
        if getattr(vehicle_config, "body", None) is None:
            raise ValueError("vehicle_config must define body")
        if getattr(vehicle_config, "fins", None) is None:
            raise ValueError("vehicle_config must define fins")
        self._config = vehicle_config
        self._mach_sweep = mach_sweep
        self._aoa_deg = aoa_deg
        self._altitude_m = altitude_m
        self._output_dir = Path(output_dir)
        self._is_setup = True

    def execute(self) -> AnalysisResults:
        """Write one SU2 config per Mach number and report the paths.

        Returns:
            AnalysisResults with ``n_configs`` (float count) in ``data``
            and the written file paths / Mach sweep in ``metadata``.

        Raises:
            RuntimeError: If called before :meth:`setup`.
        """
        if not self._is_setup or self._config is None:
            raise RuntimeError("SU2ConfigGeneration.execute() called before setup()")

        paths = write_mach_sweep_configs(
            self._config,
            output_dir=self._output_dir,
            mach_sweep=self._mach_sweep,
            aoa_deg=self._aoa_deg,
            altitude_m=self._altitude_m,
        )

        return AnalysisResults(
            name=self.name,
            fidelity=self.fidelity,
            data={"n_configs": float(len(paths))},
            metadata={
                "method": "su2_config_file_generation_only",
                "mach_sweep": self._mach_sweep,
                "aoa_deg": self._aoa_deg,
                "altitude_m": self._altitude_m,
                "config_paths": [str(p) for p in paths],
                "note": (
                    "SU2 binary was NOT invoked (not installed in this "
                    "environment); run manually with the `# TO RUN:` "
                    "comment in each generated file once available"
                ),
            },
        )

    def validate_results(self, results: AnalysisResults) -> bool:
        """Check one config file was written per Mach in the sweep."""
        return results["n_configs"] == float(len(self._mach_sweep))


def run(config_path: Path | str = VEHICLE_CONFIG_PATH) -> list[Path]:
    """Generate the full Mach-sweep SU2 config set and print a summary.

    Args:
        config_path: Path to the ramjet-rocket ``vehicle_config.yaml``.

    Returns:
        List of written ``.cfg`` file paths.
    """
    config = load_rocket_config(config_path)
    analysis = SU2ConfigGeneration()
    analysis.setup(config)
    results = analysis.execute()
    return [Path(p) for p in results.metadata["config_paths"]]


if __name__ == "__main__":
    paths = run()
    print(f"Wrote {len(paths)} SU2 Euler configs to {OUTPUT_DIR}:")
    for p in paths:
        print(f"  {p}")
