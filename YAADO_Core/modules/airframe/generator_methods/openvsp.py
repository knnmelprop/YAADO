"""OpenVSP AngelScript (``.vspscript``) export stub.

**EXPORT STUB -- this module never invokes the ``vsp`` / ``vspscript``
binary.** OpenVSP is not installed in this environment (see project rule
"NIE uruchamiaj AVL/XFOIL/SU2 binariow" -- the same constraint applies
here to OpenVSP). :class:`OpenVSPExporter` only *writes* an AngelScript
text file that encodes the OpenVSP scripting API calls
(``AddGeom("FUSELAGE")`` / ``AddGeom("WING")`` plus the associated
``SetParmValUpdate`` calls) needed to reconstruct the current YAML
geometry inside OpenVSP; a human (or a future CI job with OpenVSP
installed) must actually run it with ``vsp -script <file>``.

Geometry source
----------------
All dimensions are read from the committed vehicle configuration
(``Hangar/generic_vehicle/vehicle_config.yaml``) via
:class:`~src.schemas.vehicle_schema.Any`
(:meth:`~src.schemas.vehicle_schema.BaseVehicleConfig.from_yaml`), never
hard-coded, so the generated script stays in sync with the vehicle
definition:

- ``body.total_length_m`` (4.35501 m) -- total rocket length used for the
  fuselage geom.
- ``body.diameter_m`` (0.200 m) -- cylindrical body diameter (drawing-verified
  as of 2026-07-10; was 0.250 m, Fusion).
- ``body.nose_length_m`` (0.293 m) and ``body.nose_diameter_m`` -- conical
  nose section (a ``BodyConfig.nose_type == "conical"`` is required; other
  nose types are rejected in :meth:`OpenVSPExporter.setup`, see
  ``TODO_PHYSICAL_PARAM`` note below for ogive/hemispherical support).
- ``fins.count`` (4), ``fins.span_m`` (0.550 m), ``fins.chord_root_m`` /
  ``fins.chord_tip_m`` (0.1768 m, rectangular planform) and
  ``fins.sweep_deg`` (29.98 deg) -- the 4-fin WING geom set.

HUMAN_REVIEW (HR-1) -- fin span layout-inferred, not a labeled callout
------------------------------------------------------------------------
``fins.span_m = 0.550`` m is flagged for human CAD/drawing verification: it
is this project's best-effort reading of the "CFD Simplified Single Rocket
Model" drawing (Aleks Czernicki, DWG 10/07/2026)'s tail-area "550"
dimension, inferred from layout position (near the tail fin, alongside a
"127" value and the "29.98deg" sweep callout) rather than a clearly labeled
dimension line -- see ``Hangar/generic_vehicle/vehicle_config.yaml``
provenance comments and ``docs/decision-log.md``. A 2026-07-11 independent
DATCOM/Ackeret stability rerun flagged the resulting semi-span/diameter
ratio (2.75) as physically extreme, corroborating the concern. **This
script encodes the current YAML value as-is and must be regenerated once
the drawing dimension is confirmed against the source PDF.**

AngelScript API reference (OpenVSP scripting):
    OpenVSP API documentation, ``AddGeom``, ``SetParmValUpdate``,
    ``SetParmVal`` (http://openvsp.org/api_docs/, "Custom Scripts"
    section); Fuselage/Wing geom parameter naming per the OpenVSP
    "Geometry -> Fuselage" and "Geometry -> Wing" GUI parameter groups.
"""

from __future__ import annotations

import datetime
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if __name__ in ("__main__",) and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from YAADO_Core.ComponentStore import AxisymmetricBody, Fins  # noqa: E402
from YAADO_Core.Foundation.analysis_base import AnalysisResults, BaseAnalysis, FidelityLevel  # noqa: E402

if TYPE_CHECKING:
    from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig

#: Repository root, resolved from this file's location.
REPO_ROOT: Path = Path(__file__).resolve().parents[4]

#: Default vehicle config this generator reads geometry from.
VEHICLE_CONFIG_PATH: Path = (
    REPO_ROOT / "Hangar" / "generic_vehicle" / "vehicle_config.yaml"
)

#: Directory generated ``.vspscript`` + manifest artifacts are written into
#: (repo-root ``runs/<tool>/`` convention, gitignored -- see
#: ``analyses/aero/su2_config_template.py::RUNS_OUTPUT_DIR`` for the
#: sibling convention this mirrors).
RUNS_OUTPUT_DIR: Path = REPO_ROOT / "runs" / "openvsp"

#: Filename of the generated AngelScript file.
SCRIPT_FILENAME: str = "vehicle.vspscript"

#: Filename of the companion JSON manifest.
MANIFEST_FILENAME: str = "vehicle_manifest.json"

#: HUMAN_REVIEW tag propagated into the manifest for the layout-inferred
#: fin-span reading (HR-1).
HR1_FIN_SPAN_NOTE: str = (
    "HUMAN_REVIEW (HR-1): fins.span_m=0.550 is a layout-inferred drawing "
    "reading, not a labeled dimension callout; regenerate this script "
    "after the drawing dimension is confirmed."
)


@dataclass
class _VehicleGeometryAdapter:
    """Adapts a generic ``BaseVehicleConfig`` to this exporter's body/fins pair.

    :func:`build_vspscript` and :func:`build_manifest` were written against
    a bespoke rocket schema exposing single ``body``/``fins`` attributes;
    this adapter lets :meth:`OpenVSPExporter.setup` bind the generic,
    dict-based :class:`~YAADO_Core.Foundation.vehicle_base.BaseVehicleConfig`
    (``vehicle.bodies`` / ``vehicle.aero_surfaces``) without touching that
    downstream rendering logic.

    Attributes:
        name: Vehicle name, forwarded from the source ``BaseVehicleConfig``.
        body: The vehicle's axisymmetric body geometry.
        fins: The vehicle's fin-set geometry.
    """

    name: str
    body: AxisymmetricBody
    fins: Fins


def load_rocket_config(path: Path | str = VEHICLE_CONFIG_PATH) -> Any:
    """Load and validate the ramjet-rocket vehicle configuration.

    Args:
        path: Path to a ``vehicle_config.yaml`` for Generic Vehicle.

    Returns:
        Validated :class:`Any`.

    Raises:
        TypeError: If the YAML at ``path`` is not a rocket config (e.g.
            the generic_uav drone config was passed by mistake).
    """
    config = Any.from_yaml(path)
    if not isinstance(config, Any):
        raise TypeError(
            f"{path} did not load as a Any (got {type(config).__name__}); "
            "this generator is for Generic Vehicle (generic_vehicle) only"
        )
    return config


def build_vspscript(config: Any) -> str:
    """Render the OpenVSP AngelScript (``.vspscript``) text.

    Emits ``AddGeom("FUSELAGE", ...)`` calls for a nose-cone + cylinder
    body of revolution, and a single ``AddGeom("WING", ...)`` call
    parameterised as a 4-panel symmetric fin set (rectangular planform),
    with ``SetParmValUpdate`` calls carrying every geometric dimension
    read from ``config``.

    Reference: OpenVSP scripting API (AngelScript), ``AddGeom`` /
    ``SetParmValUpdate`` (http://openvsp.org/api_docs/); Barrowman 1967
    (nose-cone + cylindrical body-of-revolution idealisation used
    elsewhere in this project for the same geometry, e.g.
    ``analyses/aero/barrowman_extended.py``).

    Args:
        config: Validated two-stage rocket configuration (Generic Vehicle).

    Returns:
        AngelScript source text, ready to write to a ``.vspscript`` file
        (never executed by this function).

    Raises:
        ValueError: If required geometry fields are missing/non-physical,
            or ``body.nose_type`` is not ``"conical"`` (only the conical
            nose case is implemented; see ``TODO_PHYSICAL_PARAM`` note
            below for other nose shapes).
    """
    body = config.body
    fins = config.fins

    if body.diameter_m <= 0.0:
        raise ValueError("body.diameter_m must be > 0")
    if fins.span_m <= 0.0:
        raise ValueError("fins.span_m must be > 0")
    if body.nose_type != "conical":
        # TODO_PHYSICAL_PARAM [geometry_data]: ogive/hemispherical nose
        # cross-section profiles are not yet encoded as AngelScript
        # XSec calls; only the conical case (straight-line profile,
        # nose_diameter_m at the base) is implemented.
        raise ValueError(
            f"nose_type={body.nose_type!r} not yet supported by the OpenVSP "
            "exporter (only 'conical' is implemented)"
        )

    total_length_m = body.total_length_m or body.length_m
    nose_length_m = body.nose_length_m or 0.0
    nose_diameter_m = body.nose_diameter_m or body.diameter_m
    body_diameter_m = body.diameter_m
    cylinder_length_m = body.length_m

    fin_count = fins.count
    fin_span_m = fins.span_m
    fin_chord_root_m = fins.chord_root_m or fin_span_m
    fin_chord_tip_m = fins.chord_tip_m or fin_chord_root_m
    fin_sweep_deg = fins.sweep_deg

    lines: list[str] = [
        f"// YAADO vehicle -- OpenVSP AngelScript export (vehicle={config.name!r})",
        "// TO RUN: vsp -script " + SCRIPT_FILENAME,
        "// EXPORT STUB: never executed by this repo's Python code.",
        f"// {HR1_FIN_SPAN_NOTE}",
        "//",
        "// --- Geometry source: Hangar/generic_vehicle/vehicle_config.yaml ---",
        f"//   body.total_length_m   = {total_length_m:.4f}",
        f"//   body.length_m (cyl.)  = {cylinder_length_m:.4f}",
        f"//   body.diameter_m       = {body_diameter_m:.4f}",
        f"//   body.nose_length_m    = {nose_length_m:.4f}",
        f"//   body.nose_diameter_m  = {nose_diameter_m:.4f}",
        f"//   fins.count            = {fin_count}",
        f"//   fins.span_m           = {fin_span_m:.4f}  <-- HR-1",
        f"//   fins.chord_root_m     = {fin_chord_root_m:.4f}",
        f"//   fins.chord_tip_m      = {fin_chord_tip_m:.4f}",
        f"//   fins.sweep_deg        = {fin_sweep_deg:.2f}",
        "",
        "void main()",
        "{",
        "    // --- Body of revolution: nose cone + cylindrical afterbody ---",
        '    string fuse_id = AddGeom( "FUSELAGE", "" );',
        '    SetGeomName( fuse_id, "vehicle_body" );',
        f'    SetParmValUpdate( fuse_id, "Length", "Design", {total_length_m:.6f} );',
        "    // XSec 0: nose tip (zero diameter)",
        f'    SetParmValUpdate( fuse_id, "Diameter", "XSecCurve_0", 0.0 );',
        "    // XSec 1: nose-cylinder junction (conical nose base diameter)",
        f'    SetParmValUpdate( fuse_id, "XLocPercent", "XSec_1", '
        f"{(nose_length_m / total_length_m):.6f} );",
        f'    SetParmValUpdate( fuse_id, "Diameter", "XSecCurve_1", {nose_diameter_m:.6f} );',
        "    // XSec 2: max body diameter (start of cylindrical afterbody)",
        f'    SetParmValUpdate( fuse_id, "Diameter", "XSecCurve_2", {body_diameter_m:.6f} );',
        "    // XSec 3: tail (cylindrical afterbody end, constant diameter)",
        f'    SetParmValUpdate( fuse_id, "XLocPercent", "XSec_3", 1.0 );',
        f'    SetParmValUpdate( fuse_id, "Diameter", "XSecCurve_3", {body_diameter_m:.6f} );',
        "",
        "    // --- 4-fin set: rectangular planform, symmetric about body axis ---",
        '    string fin_id = AddGeom( "WING", fuse_id );',
        '    SetGeomName( fin_id, "vehicle_fins" );',
        f'    SetParmValUpdate( fin_id, "Sym_Planar_Flag", "Sym", 1.0 );',
        f'    SetParmValUpdate( fin_id, "Sym_Attach_Flag", "Sym", 1.0 );',
        f'    SetParmValUpdate( fin_id, "TotalSpan", "WingGeom", {fin_span_m:.6f} );',
        f'    SetParmValUpdate( fin_id, "Root_Chord", "XSec_1", {fin_chord_root_m:.6f} );',
        f'    SetParmValUpdate( fin_id, "Tip_Chord", "XSec_1", {fin_chord_tip_m:.6f} );',
        f'    SetParmValUpdate( fin_id, "Sweep", "XSec_1", {fin_sweep_deg:.4f} );',
        f'    // fins.count = {fin_count}: OpenVSP WING geom is bilaterally symmetric '
        "(2 panels); the remaining panels are duplicated via 4x rotational",
        '    // symmetry about the body axis (RotationalAboutAxis) below.',
        f'    SetParmValUpdate( fin_id, "RotationalCount", "Sym", {float(fin_count)} );',
        f'    SetParmValUpdate( fin_id, "RotationalAboutAxis", "Sym", 0.0 );  // X-axis (body axis)',
        "",
        "    Update();",
        f'    WriteVSPFile( "vehicle.vsp3", SET_ALL );',
        "}",
        "",
    ]
    return "\n".join(lines)


def build_manifest(config: Any, script_path: Path) -> dict[str, Any]:
    """Build the JSON-serialisable manifest for a generated ``.vspscript``.

    Args:
        config: Validated two-stage rocket configuration (Generic Vehicle).
        script_path: Path the AngelScript file was (or will be) written
            to; recorded verbatim in the manifest.

    Returns:
        Manifest dict with keys ``script_path``, ``vehicle_name``,
        ``generated_at_utc``, ``geometry_m`` (dimensions used),
        ``human_review`` (HR-1 note) and ``to_run`` (execution hint).
    """
    body = config.body
    fins = config.fins
    return {
        "script_path": str(script_path),
        "vehicle_name": config.name,
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "geometry_m": {
            "body_total_length_m": body.total_length_m or body.length_m,
            "body_length_m": body.length_m,
            "body_diameter_m": body.diameter_m,
            "body_nose_length_m": body.nose_length_m,
            "body_nose_diameter_m": body.nose_diameter_m,
            "body_nose_type": body.nose_type,
            "fin_count": fins.count,
            "fin_span_m": fins.span_m,
            "fin_chord_root_m": fins.chord_root_m,
            "fin_chord_tip_m": fins.chord_tip_m,
            "fin_sweep_deg": fins.sweep_deg,
        },
        "human_review": {
            "HR-1": HR1_FIN_SPAN_NOTE,
            "field": "fins.span_m",
            "value_m": fins.span_m,
        },
        "to_run": f"vsp -script {script_path.name}",
        "note": (
            "EXPORT STUB: OpenVSP binary was NOT invoked (not installed in "
            "this environment). Run manually with the `to_run` command "
            "once available; regenerate after CAD verification of HR-1."
        ),
    }


def write_openvsp_export(
    config: Any | None = None,
    output_dir: Path | str = RUNS_OUTPUT_DIR,
) -> tuple[Path, Path]:
    """Write the ``.vspscript`` and its JSON manifest, overwriting cleanly.

    Idempotent: calling this twice with the same ``config``/``output_dir``
    overwrites both files with byte-identical script content (the
    manifest's ``generated_at_utc`` timestamp will differ between calls,
    by design).

    Args:
        config: Rocket configuration; loaded from
            :data:`VEHICLE_CONFIG_PATH` if omitted.
        output_dir: Directory the ``.vspscript`` and manifest are written
            into (created if missing).

    Returns:
        Tuple ``(script_path, manifest_path)``.
    """
    if config is None:
        config = load_rocket_config()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    script_path = output_dir / SCRIPT_FILENAME
    manifest_path = output_dir / MANIFEST_FILENAME

    script_text = build_vspscript(config)
    script_path.write_text(script_text, encoding="utf-8")

    manifest = build_manifest(config, script_path)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return script_path, manifest_path


class OpenVSPExporter(BaseAnalysis):
    """Generates an OpenVSP AngelScript export for the vehicle rocket geometry.

    Level-0 (analytical/handbook-geometry) analysis: it only *writes* a
    ``.vspscript`` text file plus a JSON manifest -- OpenVSP itself is
    never invoked (not installed in this environment). See the module
    docstring for the HR-1 (fin span) human-review flag.

    Example:
        >>> analysis = OpenVSPExporter()
        >>> analysis.setup(vehicle)
        >>> results = analysis.execute()
        >>> results.metadata["script_path"]  # doctest: +SKIP
    """

    fidelity = FidelityLevel.LEVEL_0

    def __init__(self, name: str = "openvsp_vehicle_export") -> None:
        super().__init__(name)
        self._config: _VehicleGeometryAdapter | None = None
        self._output_dir: Path = RUNS_OUTPUT_DIR

    def setup(
        self,
        vehicle: "BaseVehicleConfig",
        operating_state: dict | None = None,
    ) -> None:
        """Bind the analysis to a validated vehicle configuration.

        Geometry is read exclusively from ``vehicle``: the first entry of
        ``vehicle.bodies`` (an
        :class:`~YAADO_Core.ComponentStore.body.AxisymmetricBody`) and the
        first :class:`~YAADO_Core.ComponentStore.aero_surfaces.Fins`
        aero surface found in ``vehicle.aero_surfaces``.

        Args:
            vehicle: Validated, vehicle-agnostic configuration providing
                the body and fin-set geometry this exporter needs.
            operating_state: Optional SI-unit operating conditions. This
                geometry-only exporter has no operating-state dependence,
                except that an ``"output_dir"`` key (``str`` or
                :class:`~pathlib.Path``) overrides the directory the
                ``.vspscript`` and manifest are written into (default:
                the constructor's :data:`RUNS_OUTPUT_DIR`, injectable so
                tests can point it at ``tmp_path``).

        Raises:
            ValueError: If ``vehicle`` defines no body, or no ``Fins``
                aero surface.
        """
        body = next(iter(vehicle.bodies.values()), None)
        if body is None:
            raise ValueError("vehicle must define at least one body (vehicle.bodies)")

        fins = next(
            (
                surface
                for surface in vehicle.aero_surfaces.values()
                if isinstance(surface, Fins)
            ),
            None,
        )
        if fins is None:
            raise ValueError(
                "vehicle must define at least one Fins aero surface "
                "(vehicle.aero_surfaces)"
            )

        self._config = _VehicleGeometryAdapter(name=vehicle.name, body=body, fins=fins)

        if operating_state is not None and "output_dir" in operating_state:
            self._output_dir = Path(operating_state["output_dir"])

        self._is_setup = True

    def execute(self) -> AnalysisResults:
        """Write the ``.vspscript`` + manifest and report their paths.

        Returns:
            AnalysisResults with ``n_files`` (float, always 2.0) in
            ``data`` and ``script_path``/``manifest_path``/geometry echo
            in ``metadata``.

        Raises:
            RuntimeError: If called before :meth:`setup`.
        """
        if not self._is_setup or self._config is None:
            raise RuntimeError("OpenVSPExporter.execute() called before setup()")

        script_path, manifest_path = write_openvsp_export(
            self._config, output_dir=self._output_dir
        )

        return AnalysisResults(
            name=self.name,
            fidelity=self.fidelity,
            data={"n_files": 2.0},
            metadata={
                "method": "openvsp_angelscript_export_stub",
                "script_path": str(script_path),
                "manifest_path": str(manifest_path),
                "human_review": "HR-1: fins.span_m=0.550 is a layout-inferred drawing reading",
                "note": (
                    "OpenVSP binary was NOT invoked (not installed in this "
                    "environment); run manually with `vsp -script "
                    f"{script_path.name}` once available"
                ),
            },
        )

    def validate_results(self, results: AnalysisResults) -> bool:
        """Check both the script and manifest files were written."""
        script_path = Path(results.metadata.get("script_path", ""))
        manifest_path = Path(results.metadata.get("manifest_path", ""))
        return script_path.is_file() and manifest_path.is_file()


def main(
    config_path: Path | str = VEHICLE_CONFIG_PATH,
    output_dir: Path | str = RUNS_OUTPUT_DIR,
) -> dict[str, Any]:
    """Generate the OpenVSP export for the default vehicle config.

    Args:
        config_path: Path to the ramjet-rocket ``vehicle_config.yaml``.
        output_dir: Directory the ``.vspscript`` and manifest are
            written into.

    Returns:
        The manifest dict (also written to ``<output_dir>/{}``).
    """.format(MANIFEST_FILENAME)
    config = load_rocket_config(config_path)
    analysis = OpenVSPExporter()
    analysis.setup(config, output_dir=output_dir)
    results = analysis.execute()
    assert analysis.validate_results(results), "OpenVSP export files were not written"

    manifest_path = Path(results.metadata["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return manifest


if __name__ == "__main__":
    manifest = main()
    print(json.dumps(manifest, indent=2))
    print(f"\nScript written to: {manifest['script_path']}")
