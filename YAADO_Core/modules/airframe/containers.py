"""Typed containers for airframe geometry generation analyses."""

from __future__ import annotations

from dataclasses import dataclass

from YAADO_Core.Foundation.analysis_base import BaseAnalysisResults
from YAADO_Core.Foundation.units import Degrees, Dimensionless, Meters


@dataclass(frozen=True)
class OpenVSPGeometry:
    """Body and fin dimensions resolved from a vehicle for the OpenVSP export.

    Attributes:
        body_length: Cylindrical body length.
        body_total_length: Total vehicle length (falls back to ``body_length``).
        body_diameter: Body diameter.
        nose_length: Nose section length (0 if unmeasured).
        nose_diameter: Nose base diameter (falls back to ``body_diameter``).
        nose_type: Nose shape name.
        fin_count: Number of fins in the radial set.
        fin_span: Semi-span of one fin.
        fin_chord_root: Root chord (falls back to ``fin_span``).
        fin_chord_tip: Tip chord (falls back to ``fin_chord_root``).
        fin_sweep: Leading-edge sweep.
    """

    body_length: Meters
    body_total_length: Meters
    body_diameter: Meters
    nose_length: Meters
    nose_diameter: Meters
    nose_type: str
    fin_count: int
    fin_span: Meters
    fin_chord_root: Meters
    fin_chord_tip: Meters
    fin_sweep: Degrees


@dataclass(frozen=True)
class OpenVSPHumanReview:
    """Human-review flag attached to an exported script.

    Attributes:
        tag: Review identifier.
        field: Geometry field needing human verification.
        value: Value of that field as exported [m].
        note: Reason for the review.
    """

    tag: str
    field: str
    value: Meters
    note: str


@dataclass(frozen=True)
class OpenVSPManifest:
    """Manifest describing a generated ``.vspscript``.

    Attributes:
        script_path: Path the script was written to, or None when logging is disabled.
        vehicle_name: Name of the source vehicle.
        generated_at_utc: ISO-8601 generation timestamp.
        geometry: Dimensions encoded in the script.
        human_review: Human-review flag for the fin span.
        to_run: Command that executes the script in OpenVSP.
        note: Statement that the OpenVSP binary was not invoked.
    """

    script_path: str | None
    vehicle_name: str
    generated_at_utc: str
    geometry: OpenVSPGeometry
    human_review: OpenVSPHumanReview
    to_run: str
    note: str


@dataclass(frozen=True)
class OpenVSPExportResults(BaseAnalysisResults):
    """Outputs of the OpenVSP AngelScript export.

    Attributes:
        body_total_length: Total vehicle length encoded in the script.
        body_diameter: Body diameter encoded in the script.
        fin_span: Fin semi-span encoded in the script.
        fin_count: Number of fins encoded in the script.
        script: Generated AngelScript source text.
        manifest: Manifest of the generated script.
        script_path: Saved script path, or None when logging is disabled.
        manifest_path: Saved manifest path, or None when logging is disabled.
    """

    body_total_length: Meters
    body_diameter: Meters
    fin_span: Meters
    fin_count: Dimensionless
    script: str
    manifest: OpenVSPManifest
    script_path: str | None = None
    manifest_path: str | None = None
