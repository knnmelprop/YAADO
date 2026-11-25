"""SU2 Euler configuration decks for a Mach number and angle-of-attack grid.

Writes one SU2 ``.cfg`` deck per (Mach, angle of attack) pair for SU2's compressible
Euler solver. The freestream state comes from the ISA atmosphere at the chosen altitude,
and the force and moment references from the vehicle: the body's frontal area and
diameter, about the vehicle CG, unless overridden (for example with a wing area and
mean chord). The decks name the mesh and the markers that the Gmsh mesher writes. This
module does not run SU2; that is tracked in issue #44.

Reference:
    Economon, T. D. et al., "SU2: An Open-Source Suite for Multiphysics Simulation and
    Design", AIAA Journal 54(3), 2016.
"""

from __future__ import annotations

import math
from typing import Any, ClassVar

from YAADO_Core.ComponentStore import AERO_COMPONENTS, BODY_COMPONENTS
from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.atmosphere import AtmosphereState, isa_atmosphere
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.airframe.mesher_methods.gmsh_euler import (
    AIRFRAME,
    BASE,
    FARFIELD,
    MESH_FILENAME,
    SYMMETRY,
)
from YAADO_Core.modules.wind_tunnel.containers import SU2Case, SU2ConfigResults

MANIFEST_FILENAME = "run_manifest.json"

#: Solver numerics shared by every deck (Euler, JST scheme, residual convergence).
#: Option names follow SU2 v8 (``external/su2``).
SOLVER_SETTINGS: tuple[tuple[str, str], ...] = (
    ("SOLVER", "EULER"),
    ("MATH_PROBLEM", "DIRECT"),
    ("REF_DIMENSIONALIZATION", "DIMENSIONAL"),
    ("MARKER_EULER", f"( {AIRFRAME}, {BASE} )"),
    ("MARKER_FAR", f"( {FARFIELD} )"),
    ("MARKER_MONITORING", f"( {AIRFRAME}, {BASE} )"),
    ("MARKER_PLOTTING", f"( {AIRFRAME}, {BASE} )"),
    ("CONV_NUM_METHOD_FLOW", "JST"),
    ("NUM_METHOD_GRAD", "WEIGHTED_LEAST_SQUARES"),
    ("CFL_NUMBER", "5.0"),
    ("CONV_FIELD", "RMS_DENSITY"),
    ("CONV_RESIDUAL_MINVAL", "-8"),
    ("ITER", "5000"),
    ("OUTPUT_FILES", "(RESTART, PARAVIEW, SURFACE_CSV)"),
    ("HISTORY_OUTPUT", "(ITER, RMS_RES, AERO_COEFF, AERO_COEFF_SURF)"),
)


def su2_config_filename(mach: float, alpha_deg: float) -> str:
    """Deck name of one case, e.g. ``su2_mach2p50_aoam2p00.cfg`` for Mach 2.5 at -2 deg."""
    mach_tag = f"{mach:.2f}".replace(".", "p")
    sign = "m" if alpha_deg < 0 else ""
    alpha_tag = f"{abs(alpha_deg):.2f}".replace(".", "p")
    return f"su2_mach{mach_tag}_aoa{sign}{alpha_tag}.cfg"


def build_su2_config(
    vehicle_name: str,
    mach: float,
    alpha_deg: float,
    altitude_m: float,
    freestream: AtmosphereState,
    ref_area: float,
    ref_length: float,
    moment_origin_x: float,
    filename: str,
    geometry_notes: tuple[str, ...] = (),
    half_model: bool = False,
) -> str:
    """Render the SU2 deck of one Euler case.

    Args:
        vehicle_name: Vehicle the deck belongs to, for the header.
        mach: Freestream Mach number.
        alpha_deg: Angle of attack [deg].
        altitude_m: ISA altitude of ``freestream`` [m].
        freestream: Atmospheric state at ``altitude_m``.
        ref_area: Reference area of the force coefficients [m^2].
        ref_length: Reference length of the moment coefficients [m].
        moment_origin_x: Moment reference point, from the nose tip [m].
        filename: Name the deck is saved under; sets the restart and history names.
        geometry_notes: Lines describing the vehicle, written as comments.
        half_model: Whether the mesh holds half of the vehicle. SU2 then integrates half of
            the forces, so half of the reference area keeps the coefficients of the whole
            vehicle.

    Returns:
        The deck text.
    """
    stem = filename.rsplit(".", 1)[0]
    lines = [
        f"% YAADO SU2 Euler case for vehicle {vehicle_name!r}",
        f"% Mach {mach:g}, angle of attack {alpha_deg:g} deg, ISA {altitude_m:g} m",
        f"% To run: SU2_CFD {filename} (needs the mesh {MESH_FILENAME})",
        *(f"% {note}" for note in geometry_notes),
        "%",
        *(f"{key}= {value}" for key, value in SOLVER_SETTINGS),
        *([f"MARKER_SYM= ( {SYMMETRY} )"] if half_model else []),
        "%",
        f"MACH_NUMBER= {mach:g}",
        f"AOA= {alpha_deg:g}",
        f"FREESTREAM_TEMPERATURE= {freestream.temperature:.3f}",
        f"FREESTREAM_PRESSURE= {freestream.pressure:.2f}",
        "%",
        f"REF_ORIGIN_MOMENT_X= {moment_origin_x:.4f}",
        "REF_ORIGIN_MOMENT_Y= 0.0",
        "REF_ORIGIN_MOMENT_Z= 0.0",
        f"REF_AREA= {ref_area / 2.0 if half_model else ref_area:.6g}",
        f"REF_LENGTH= {ref_length:.6g}",
        "%",
        f"MESH_FILENAME= {MESH_FILENAME}",
        "MESH_FORMAT= SU2",
        f"SOLUTION_FILENAME= restart_{stem}.dat",
        f"RESTART_FILENAME= restart_{stem}.dat",
        f"CONV_FILENAME= history_{stem}",
    ]
    return "\n".join(lines) + "\n"


class SU2ConfigGeneration(BaseAnalysis[SU2ConfigResults]):
    """SU2 Euler decks for every (Mach, angle of attack) pair of a grid.

    Example:
        analysis = SU2ConfigGeneration()
        analysis.setup(vehicle, mach_list=(1.5, 2.5), alpha_list_deg=(0.0, 4.0))
        results = analysis.execute()
        n_decks = results.n_configs
    """

    fidelity = FidelityLevel.LEVEL_2

    DEFAULT_MACH_LIST: ClassVar[tuple[float, ...]] = (0.8, 1.5, 2.0, 2.5, 3.0)
    DEFAULT_ALPHA_LIST_DEG: ClassVar[tuple[float, ...]] = (0.0,)
    DEFAULT_ALTITUDE_M: ClassVar[float] = 0.0
    DEFAULT_HALF_MODEL: ClassVar[bool] = True
    MAX_CASES: ClassVar[int] = 400

    def __init__(self, name: str = "su2_euler_decks") -> None:
        super().__init__(name)
        self._vehicle_name = ""
        self._cases: tuple[SU2Case, ...] = ()
        self._altitude = self.DEFAULT_ALTITUDE_M
        self._freestream = isa_atmosphere(self.DEFAULT_ALTITUDE_M)
        self._ref_area = 0.0
        self._ref_length = 0.0
        self._moment_origin_x = 0.0
        self._half_model = self.DEFAULT_HALF_MODEL
        self._notes: tuple[str, ...] = ()
        self._assumptions: tuple[str, ...] = ()

    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        mach_list: tuple[float, ...] = DEFAULT_MACH_LIST,
        alpha_list_deg: tuple[float, ...] = DEFAULT_ALPHA_LIST_DEG,
        altitude_m: float = DEFAULT_ALTITUDE_M,
        ref_area: float | None = None,
        ref_length: float | None = None,
        cg_from_nose: float | None = None,
        half_model: bool = DEFAULT_HALF_MODEL,
        body_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Resolve the reference quantities and the case grid.

        Args:
            vehicle: Vehicle with one axisymmetric body, unless both references are set.
            mach_list: Freestream Mach numbers.
            alpha_list_deg: Angles of attack [deg].
            altitude_m: ISA altitude of the freestream [m].
            ref_area: Force reference area [m^2]. Defaults to the body's frontal area.
            ref_length: Moment reference length [m]. Defaults to the body diameter.
            cg_from_nose: Moment reference point [m]. Defaults to the vehicle CG.
            half_model: Whether the mesh holds the half of the vehicle at y > 0, as the
                mesher makes for a symmetric vehicle.
            body_name: Body to use if the vehicle has more than one.
            **kwargs: Not accepted; present for the ``BaseAnalysis`` signature.

        Raises:
            TypeError: If an unknown setting is passed.
            ValueError: If no reference can be found, or a setting is out of range.
        """
        if kwargs:
            raise TypeError(f"Unknown settings for '{self.name}': {sorted(kwargs)}")
        if not mach_list or not alpha_list_deg:
            raise ValueError("Give at least one Mach number and one angle of attack")
        if any(mach <= 0.0 for mach in mach_list):
            raise ValueError(f"Mach numbers must be positive, got {mach_list}")
        if len(mach_list) * len(alpha_list_deg) > self.MAX_CASES:
            raise ValueError(f"The grid has more than {self.MAX_CASES} cases")

        notes: list[str] = []
        assumptions: list[str] = []
        if ref_area is None or ref_length is None:
            body = vehicle.find_single_component(BODY_COMPONENTS, body_name)
            ref_area = math.pi / 4.0 * body.diameter**2 if ref_area is None else ref_area
            ref_length = body.diameter if ref_length is None else ref_length
            notes.append(f"body: length {body.length:g} m, diameter {body.diameter:g} m")
        if ref_area <= 0.0 or ref_length <= 0.0:
            raise ValueError("ref_area and ref_length must be positive")
        for surface_name, surface in vehicle.get_components_by_type(AERO_COMPONENTS).items():
            notes.append(f"surface {surface_name}: span {surface.span:g} m")

        if cg_from_nose is None:
            if vehicle.mass_properties is not None:
                cg_from_nose = vehicle.mass_properties.cg_from_nose
            else:
                cg_from_nose = 0.0
                assumptions.append("No vehicle CG: moments are taken about the nose tip.")

        cases = tuple(
            SU2Case(mach=mach, alpha=alpha, filename=su2_config_filename(mach, alpha))
            for mach in mach_list
            for alpha in alpha_list_deg
        )
        if len({case.filename for case in cases}) != len(cases):
            raise ValueError("Mach numbers and angles of attack must differ at two decimals")

        self._vehicle_name = vehicle.name
        self._cases = cases
        self._altitude = altitude_m
        self._freestream = isa_atmosphere(altitude_m)
        self._ref_area = ref_area
        self._ref_length = ref_length
        self._moment_origin_x = cg_from_nose
        self._half_model = half_model
        self._notes = tuple(notes)
        decks_only = (
            f"Decks only, for a {'half' if half_model else 'full'} model: make {MESH_FILENAME} "
            "with the Gmsh mesher, then run SU2_CFD on each deck next to it."
        )
        self._assumptions = (decks_only, *assumptions)
        self.logger.info(
            "Configured %d SU2 Euler decks for vehicle '%s' at %.0f m (A_ref %.4g m^2, L_ref %.4g m)",
            len(self._cases),
            vehicle.name,
            altitude_m,
            ref_area,
            ref_length,
        )

    def _compute(self, **kwargs: Any) -> SU2ConfigResults:
        """Render every deck and save the decks and their manifest through the logger."""
        for case in self._cases:
            deck = build_su2_config(
                self._vehicle_name,
                case.mach,
                case.alpha,
                self._altitude,
                self._freestream,
                self._ref_area,
                self._ref_length,
                self._moment_origin_x,
                case.filename,
                self._notes,
                self._half_model,
            )
            self.logger.save_artifact(case.filename, deck)
        self.logger.save_json(self._cases, MANIFEST_FILENAME)
        return SU2ConfigResults(
            name=self.name,
            fidelity=self.fidelity,
            cases=self._cases,
            n_configs=len(self._cases),
            altitude=self._altitude,
            freestream_temperature=self._freestream.temperature,
            freestream_pressure=self._freestream.pressure,
            freestream_density=self._freestream.density,
            ref_area=self._ref_area,
            ref_length=self._ref_length,
            moment_origin_x=self._moment_origin_x,
            mesh_filename=MESH_FILENAME,
            is_half=self._half_model,
            assumptions=self._assumptions,
        )

    def validate_results(self, results: SU2ConfigResults) -> bool:
        """Check one uniquely named deck per case and a physical freestream.

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        names = {case.filename for case in results.cases}
        return (
            results.n_configs == len(names) > 0
            and results.freestream_pressure > 0.0
            and results.freestream_temperature > 0.0
        )
