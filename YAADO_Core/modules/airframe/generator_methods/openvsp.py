"""OpenVSP AngelScript (``.vspscript``) export stub.

**EXPORT STUB -- this module never invokes the ``vsp`` / ``vspscript``
binary.** :class:`OpenVSPExporter` only *writes* an AngelScript text file
(``AddGeom("FUSELAGE")`` / ``AddGeom("WING")`` plus ``SetParmValUpdate``
calls) that reconstructs the vehicle geometry inside OpenVSP; run it
manually with ``vsp -script <file>``.

Geometry is resolved from the vehicle via the ``BODY_COMPONENTS`` and
``AERO_COMPONENTS`` registries of the ComponentStore, never hard-coded.
Only a conical nose is supported; other nose shapes are rejected.

HUMAN_REVIEW (HR-1): the fin span is flagged for human CAD/drawing
verification because it may be a layout-inferred reading rather than a
labeled dimension. Regenerate the script once it is confirmed.

AngelScript API reference: OpenVSP scripting API, ``AddGeom`` /
``SetParmValUpdate`` (http://openvsp.org/api_docs/).
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from YAADO_Core.ComponentStore import AERO_COMPONENTS, BODY_COMPONENTS
from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.airframe.containers import (
    OpenVSPExportResults,
    OpenVSPGeometry,
    OpenVSPHumanReview,
    OpenVSPManifest,
)

#: Filename of the generated AngelScript file.
SCRIPT_FILENAME: str = "vehicle.vspscript"

#: Filename of the companion JSON manifest.
MANIFEST_FILENAME: str = "vehicle_manifest.json"

#: HUMAN_REVIEW tag for the fin-span reading.
HR1_TAG: str = "HR-1"

#: Reason for the fin-span human review.
HR1_FIN_SPAN_NOTE: str = (
    "HUMAN_REVIEW (HR-1): the fin span may be a layout-inferred drawing "
    "reading, not a labeled dimension callout; regenerate this script "
    "after the dimension is confirmed."
)

_EXPORT_NOTE: str = (
    "EXPORT STUB: OpenVSP binary was NOT invoked. Run manually with the "
    "`to_run` command once available; regenerate after CAD verification of HR-1."
)


def resolve_geometry(
    vehicle: BaseVehicleConfig,
    *,
    body_name: str | None = None,
    fins_name: str | None = None,
) -> OpenVSPGeometry:
    """Resolve body and fin dimensions from a vehicle config.

    Components are found through :data:`~YAADO_Core.ComponentStore.BODY_COMPONENTS`
    and :data:`~YAADO_Core.ComponentStore.AERO_COMPONENTS`.

    Args:
        vehicle: Validated vehicle configuration.
        body_name: Explicit body name; required if several bodies exist.
        fins_name: Explicit fin-set name; required if several aero surfaces exist.

    Returns:
        Resolved :class:`OpenVSPGeometry` in SI units.

    Raises:
        ValueError: If a component is missing or ambiguous, the aero surface
            is not a fin set (lacks ``count``), or a dimension is non-physical.
        TypeError: If a named component has the wrong type.
    """
    body = vehicle.find_single_component(BODY_COMPONENTS, name=body_name)
    fins: Any = vehicle.find_single_component(AERO_COMPONENTS, name=fins_name)

    fin_count = getattr(fins, "count", None)
    if fin_count is None:
        raise ValueError(
            f"Aero surface '{type(fins).__name__}' has no 'count'; the OpenVSP "
            "exporter needs a radial fin set"
        )

    body_length: float = body.length
    body_diameter: float = body.diameter
    fin_span: float = fins.span
    fin_chord_root: float = getattr(fins, "chord_root", None) or fin_span
    fin_chord_tip: float = getattr(fins, "chord_tip", None) or fin_chord_root

    if body_diameter <= 0.0:
        raise ValueError("body.diameter must be > 0")
    if fin_span <= 0.0:
        raise ValueError("fins.span must be > 0")
    if body.nose_type != "conical":
        # TODO_PHYSICAL_PARAM [geometry_data]: ogive/hemispherical nose
        # profiles are not yet encoded as AngelScript XSec calls.
        raise ValueError(
            f"nose_type={body.nose_type!r} not yet supported by the OpenVSP "
            "exporter (only 'conical' is implemented)"
        )

    return OpenVSPGeometry(
        body_length=body_length,
        body_total_length=body.total_length or body_length,
        body_diameter=body_diameter,
        nose_length=body.nose_length or 0.0,
        nose_diameter=body.nose_diameter or body_diameter,
        nose_type=body.nose_type,
        fin_count=fin_count,
        fin_span=fin_span,
        fin_chord_root=fin_chord_root,
        fin_chord_tip=fin_chord_tip,
        fin_sweep=fins.sweep,
    )


def build_vspscript(geometry: OpenVSPGeometry, vehicle_name: str) -> str:
    """Render the OpenVSP AngelScript (``.vspscript``) text.

    Emits a nose-cone + cylinder ``FUSELAGE`` and a symmetric ``WING`` geom
    parameterised as the radial fin set.

    Args:
        geometry: Resolved body and fin dimensions [m, deg].
        vehicle_name: Vehicle name written into the script header.

    Returns:
        AngelScript source text (never executed by this function).
    """
    g = geometry
    nose_frac = g.nose_length / g.body_total_length
    lines: list[str] = [
        f"// YAADO vehicle -- OpenVSP AngelScript export (vehicle={vehicle_name!r})",
        f"// TO RUN: vsp -script {SCRIPT_FILENAME}",
        "// EXPORT STUB: never executed by this repo's Python code.",
        f"// {HR1_FIN_SPAN_NOTE}",
        "//",
        "// --- Geometry source: vehicle configuration ---",
        f"//   body.total_length_m   = {g.body_total_length:.4f}",
        f"//   body.length_m (cyl.)  = {g.body_length:.4f}",
        f"//   body.diameter_m       = {g.body_diameter:.4f}",
        f"//   body.nose_length_m    = {g.nose_length:.4f}",
        f"//   body.nose_diameter_m  = {g.nose_diameter:.4f}",
        f"//   fins.count            = {g.fin_count}",
        f"//   fins.span_m           = {g.fin_span:.4f}  <-- HR-1",
        f"//   fins.chord_root_m     = {g.fin_chord_root:.4f}",
        f"//   fins.chord_tip_m      = {g.fin_chord_tip:.4f}",
        f"//   fins.sweep_deg        = {g.fin_sweep:.2f}",
        "",
        "void main()",
        "{",
        "    // --- Body of revolution: nose cone + cylindrical afterbody ---",
        '    string fuse_id = AddGeom( "FUSELAGE", "" );',
        '    SetGeomName( fuse_id, "vehicle_body" );',
        f'    SetParmValUpdate( fuse_id, "Length", "Design", {g.body_total_length:.6f} );',
        "    // XSec 0: nose tip (zero diameter)",
        '    SetParmValUpdate( fuse_id, "Diameter", "XSecCurve_0", 0.0 );',
        "    // XSec 1: nose-cylinder junction (conical nose base diameter)",
        f'    SetParmValUpdate( fuse_id, "XLocPercent", "XSec_1", {nose_frac:.6f} );',
        f'    SetParmValUpdate( fuse_id, "Diameter", "XSecCurve_1", {g.nose_diameter:.6f} );',
        "    // XSec 2: max body diameter (start of cylindrical afterbody)",
        f'    SetParmValUpdate( fuse_id, "Diameter", "XSecCurve_2", {g.body_diameter:.6f} );',
        "    // XSec 3: tail (cylindrical afterbody end, constant diameter)",
        '    SetParmValUpdate( fuse_id, "XLocPercent", "XSec_3", 1.0 );',
        f'    SetParmValUpdate( fuse_id, "Diameter", "XSecCurve_3", {g.body_diameter:.6f} );',
        "",
        "    // --- Fin set: rectangular planform, symmetric about body axis ---",
        '    string fin_id = AddGeom( "WING", fuse_id );',
        '    SetGeomName( fin_id, "vehicle_fins" );',
        '    SetParmValUpdate( fin_id, "Sym_Planar_Flag", "Sym", 1.0 );',
        '    SetParmValUpdate( fin_id, "Sym_Attach_Flag", "Sym", 1.0 );',
        f'    SetParmValUpdate( fin_id, "TotalSpan", "WingGeom", {g.fin_span:.6f} );',
        f'    SetParmValUpdate( fin_id, "Root_Chord", "XSec_1", {g.fin_chord_root:.6f} );',
        f'    SetParmValUpdate( fin_id, "Tip_Chord", "XSec_1", {g.fin_chord_tip:.6f} );',
        f'    SetParmValUpdate( fin_id, "Sweep", "XSec_1", {g.fin_sweep:.4f} );',
        f"    // fins.count = {g.fin_count}: extra panels via rotational symmetry",
        f'    SetParmValUpdate( fin_id, "RotationalCount", "Sym", {float(g.fin_count)} );',
        '    SetParmValUpdate( fin_id, "RotationalAboutAxis", "Sym", 0.0 );  // X-axis (body axis)',
        "",
        "    Update();",
        '    WriteVSPFile( "vehicle.vsp3", SET_ALL );',
        "}",
        "",
    ]
    return "\n".join(lines)


def build_manifest(
    geometry: OpenVSPGeometry,
    vehicle_name: str,
    script_path: str | None,
) -> OpenVSPManifest:
    """Build the manifest for a generated ``.vspscript``.

    Args:
        geometry: Resolved body and fin dimensions.
        vehicle_name: Name of the source vehicle.
        script_path: Path the script was written to, or None if not saved.

    Returns:
        Frozen :class:`OpenVSPManifest`.
    """
    return OpenVSPManifest(
        script_path=script_path,
        vehicle_name=vehicle_name,
        generated_at_utc=datetime.datetime.now(datetime.UTC).isoformat(),
        geometry=geometry,
        human_review=OpenVSPHumanReview(
            tag=HR1_TAG,
            field="fins.span",
            value=geometry.fin_span,
            note=HR1_FIN_SPAN_NOTE,
        ),
        to_run=f"vsp -script {SCRIPT_FILENAME}",
        note=_EXPORT_NOTE,
    )


class OpenVSPExporter(BaseAnalysis[OpenVSPExportResults]):
    """Generates an OpenVSP AngelScript export of the vehicle body and fins.

    Writes a ``.vspscript`` and a JSON manifest through the
    :class:`~YAADO_Core.Foundation.flight_logger.FlightLogger` artifacts
    directory; OpenVSP itself is never invoked.

    Example:
        analysis = OpenVSPExporter()
        analysis.setup(vehicle)
        results = analysis.execute()
        script_text = results.script
    """

    fidelity = FidelityLevel.LEVEL_1

    def __init__(self, name: str = "openvsp_vehicle_export") -> None:
        super().__init__(name)
        self._vehicle_name: str = ""
        self._geometry: OpenVSPGeometry | None = None

    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        body_name: str | None = None,
        fins_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Resolve body and fin geometry from the vehicle.

        Args:
            vehicle: Validated vehicle configuration.
            body_name: Explicit body name if the vehicle has several bodies.
            fins_name: Explicit fin-set name if the vehicle has several aero surfaces.
            **kwargs: Unused solver settings.
        """
        self._vehicle_name = vehicle.name
        self._geometry = resolve_geometry(
            vehicle, body_name=body_name, fins_name=fins_name
        )
        self.logger.info(
            "Configured OpenVSPExporter for vehicle '%s' (L=%.3f m, D=%.3f m, %d fins)",
            vehicle.name,
            self._geometry.body_total_length,
            self._geometry.body_diameter,
            self._geometry.fin_count,
        )

    def _compute(self) -> OpenVSPExportResults:
        """Render the script, save script and manifest, and return typed results."""
        if self._geometry is None:
            raise RuntimeError(
                f"Analysis '{self.name}' must be setup before computation. Call setup() first."
            )
        geometry = self._geometry

        script = build_vspscript(geometry, self._vehicle_name)
        script_path = self.logger.save_text(script, SCRIPT_FILENAME)
        script_path_str = str(script_path) if script_path is not None else None

        manifest = build_manifest(geometry, self._vehicle_name, script_path_str)
        manifest_path = self.logger.save_json(manifest, MANIFEST_FILENAME)
        manifest_path_str = str(manifest_path) if manifest_path is not None else None

        self.logger.info("Generated OpenVSP script (%d bytes)", len(script))

        return OpenVSPExportResults(
            name=self.name,
            fidelity=self.fidelity,
            body_total_length=geometry.body_total_length,
            body_diameter=geometry.body_diameter,
            fin_span=geometry.fin_span,
            fin_count=geometry.fin_count,
            script=script,
            manifest=manifest,
            script_path=script_path_str,
            manifest_path=manifest_path_str,
        )

    def validate_results(self, results: OpenVSPExportResults) -> bool:
        """Check the script is non-empty and any saved files exist on disk."""
        if not results.script.strip():
            return False
        saved = (results.script_path, results.manifest_path)
        return all(Path(p).is_file() for p in saved if p is not None)
