import pytest
from pydantic import ValidationError
from YAADO_Core.ComponentStore.body import AxisymmetricBody

def test_axisymmetric_body_valid():
    """Test parsing a standard airframe."""
    body = AxisymmetricBody.model_validate({
        "type": "axisymmetric_body",
        "length_m": 5.0,
        "diameter_m": 0.3,
        "nose_type": "conical",
        "nose_length_m": 0.5
    })
    assert body.length_m == 5.0
    assert body.nose_type == "conical"
    assert body.mass is None

def test_axisymmetric_body_with_distributed_mass():
    """Test that the new distributed mass logic works perfectly."""
    body = AxisymmetricBody.model_validate({
        "type": "axisymmetric_body",
        "length_m": 5.0,
        "diameter_m": 0.3,
        "mass": {
            "type": "mass",
            "total_mass_kg": 25.0,
            "cg_from_nose_m": 2.5
        }
    })
    assert body.mass is not None
    assert body.mass.total_mass_kg == 25.0
    assert body.mass.cg_from_nose_m == 2.5

def test_axisymmetric_body_negative_dimension_fails():
    """Test that the geometry bounds block negative values."""
    with pytest.raises(ValidationError, match="Input should be greater than 0"):
        AxisymmetricBody.model_validate({
            "type": "axisymmetric_body",
            "length_m": -5.0,  # Impossible length
            "diameter_m": 0.3
        })
