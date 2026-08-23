import pytest
from pydantic import ValidationError
from IADE_Core.ComponentStore.mass import MassProperties

def test_mass_properties_valid():
    """Test standard mass properties parsing."""
    mass = MassProperties.model_validate({
        "type": "mass",
        "total_mass_kg": 150.0,
        "cg_from_nose_m": 1.2,
        "cg_source": "CAD estimate"
    })
    assert mass.total_mass_kg == 150.0
    assert mass.cg_source == "CAD estimate"

def test_mass_properties_negative_cg_fails():
    """Test that CG must be strictly positive (behind the nose tip)."""
    with pytest.raises(ValidationError, match="Input should be greater than 0"):
        MassProperties.model_validate({
            "type": "mass",
            "total_mass_kg": 150.0,
            "cg_from_nose_m": -0.5  # CG cannot be in front of the nose
        })
