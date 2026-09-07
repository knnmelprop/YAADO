"""Unit tests for the OpenVSP AngelScript exporter's ``setup`` contract.

Covers only :meth:`OpenVSPExporter.setup` and, where it does not require
the (unavailable) ``vsp`` binary, :meth:`OpenVSPExporter.execute`. Never
runs OpenVSP itself -- this exporter is an export-stub that only writes
text files.
"""

from __future__ import annotations

import pytest

from YAADO_Core.ComponentStore import AxisymmetricBody, Fins, Wings
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.airframe.generator_methods.openvsp import OpenVSPExporter


def _make_vehicle(**overrides: object) -> BaseVehicleConfig:
    """Build a minimal, validating generic vehicle with a body and fins.

    Args:
        **overrides: Extra keyword args forwarded to
            :class:`BaseVehicleConfig` (e.g. to add/omit aero surfaces).

    Returns:
        A validated :class:`BaseVehicleConfig`.
    """
    kwargs: dict[str, object] = {
        "name": "test_vehicle",
        "bodies": {
            "main_body": AxisymmetricBody(
                length_m=4.0,
                diameter_m=0.2,
                nose_type="conical",
                nose_length_m=0.3,
                nose_diameter_m=0.2,
            ),
        },
        "aero_surfaces": {
            "fin_set": Fins(
                count=4,
                span_m=0.55,
                sweep_deg=29.98,
                chord_root_m=0.1768,
                chord_tip_m=0.1768,
            ),
        },
    }
    kwargs.update(overrides)
    return BaseVehicleConfig(**kwargs)


def test_setup_binds_body_and_fins_from_vehicle() -> None:
    """setup() reads body/fins geometry from the vehicle, not from disk."""
    vehicle = _make_vehicle()
    analysis = OpenVSPExporter()

    analysis.setup(vehicle)

    assert analysis._is_setup is True
    assert analysis._config is not None
    assert analysis._config.name == "test_vehicle"
    assert analysis._config.body.diameter_m == pytest.approx(0.2)
    assert analysis._config.fins.count == 4


def test_setup_accepts_operating_state_none() -> None:
    """operating_state is optional per the BaseAnalysis contract."""
    vehicle = _make_vehicle()
    analysis = OpenVSPExporter()

    analysis.setup(vehicle, operating_state=None)

    assert analysis._is_setup is True


def test_setup_output_dir_override_via_operating_state(tmp_path: object) -> None:
    """An "output_dir" key in operating_state overrides the write location."""
    vehicle = _make_vehicle()
    analysis = OpenVSPExporter()

    analysis.setup(vehicle, operating_state={"output_dir": str(tmp_path)})

    assert str(analysis._output_dir) == str(tmp_path)


def test_setup_raises_without_body() -> None:
    """A vehicle with no bodies is rejected."""
    vehicle = _make_vehicle(bodies={})
    analysis = OpenVSPExporter()

    with pytest.raises(ValueError, match="body"):
        analysis.setup(vehicle)


def test_setup_raises_without_fins() -> None:
    """A vehicle whose aero_surfaces contain no Fins is rejected."""
    vehicle = _make_vehicle(
        aero_surfaces={
            "main_wing": Wings(
                aspect_ratio=8.0,
                sweep_deg=5.0,
                taper_ratio=0.6,
                span_m=2.0,
                airfoil_root="NACA2412",
            ),
        }
    )
    analysis = OpenVSPExporter()

    with pytest.raises(ValueError, match="Fins"):
        analysis.setup(vehicle)


def test_execute_writes_vspscript_and_manifest(tmp_path: object) -> None:
    """execute() writes the export stub files after setup(), no binary run."""
    vehicle = _make_vehicle()
    analysis = OpenVSPExporter()
    analysis.setup(vehicle, operating_state={"output_dir": str(tmp_path)})

    results = analysis.execute()

    assert analysis.validate_results(results)
    assert results.data["n_files"] == 2.0
