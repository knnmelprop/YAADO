import pytest
from pydantic import ValidationError
from YAADO_Core.ComponentStore.body import AxisymmetricBody

def test_axisymmetric_body_valid():
    """Test parsing a standard airframe."""
    body = AxisymmetricBody.model_validate({
        "type": "axisymmetric_body",
        "length": 5.0,
        "diameter": 0.3,
        "nose_type": "conical",
        "nose_length": 0.5
    })
    assert body.length == 5.0
    assert body.diameter == 0.3
    assert body.nose_type == "conical"
    assert body.mass is None
    assert AxisymmetricBody.UNITS["length"] == "m"
    assert AxisymmetricBody.UNITS["diameter"] == "m"
    assert AxisymmetricBody.UNITS["nose_length"] == "m"

def test_axisymmetric_body_with_distributed_mass():
    """Test that the new distributed mass logic works perfectly."""
    body = AxisymmetricBody.model_validate({
        "type": "axisymmetric_body",
        "length": 5.0,
        "diameter": 0.3,
        "mass": {
            "type": "mass",
            "total_mass": 25.0,
            "cg_from_nose": 2.5
        }
    })
    assert body.mass is not None
    assert body.mass.total_mass == 25.0
    assert body.mass.cg_from_nose == 2.5

def test_axisymmetric_body_negative_dimension_fails():
    """Test that the geometry bounds block negative values."""
    with pytest.raises(ValidationError, match="Input should be greater than 0"):
        AxisymmetricBody.model_validate({
            "type": "axisymmetric_body",
            "length": -5.0,  # Impossible length
            "diameter": 0.3
        })

