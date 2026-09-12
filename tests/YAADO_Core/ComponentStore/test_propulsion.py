import pytest
from pydantic import ValidationError
from YAADO_Core.ComponentStore.propulsion import SolidMotor, RamjetEngine

def test_solid_motor_valid():
    """Test parsing a perfectly valid SolidMotor."""
    motor = SolidMotor.model_validate({
        "type": "solid_motor",
        "isp_vacuum": 250.0,
        "isp_sl": 220.0,
        "propellant_mass": 10.0,
        "burn_time": 2.0,
        "thrust_mean": 10500.0,  # Ideal: 220 * (10/2) * 9.81 = ~10787 N (Very close!)
        "thrust_peak": 12000.0,
        "propellant_density": 1700.0
    })
    assert motor.thrust_peak == 12000.0
    assert motor.mdot == 5.0
    assert SolidMotor.UNITS["thrust_mean"] == "N"
    assert SolidMotor.UNITS["isp_sl"] == "s"
    assert SolidMotor.UNITS["propellant_mass"] == "kg"

def test_solid_motor_peak_below_mean_fails():
    """Test that the physics validator blocks peak thrust < mean thrust."""
    with pytest.raises(ValidationError, match="cannot be below the mean|thrust_peak=10000 < thrust_mean=15000 N"):
        SolidMotor.model_validate({
            "type": "solid_motor",
            "isp_vacuum": 250.0,
            "isp_sl": 220.0,
            "propellant_mass": 10.0,
            "burn_time": 2.0,
            "thrust_mean": 15000.0,
            "thrust_peak": 10000.0,  # Physically impossible
            "propellant_density": 1700.0
        })

def test_solid_motor_thrust_inconsistent_with_isp_fails():
    """Test that the physics validator blocks impossible thrust/mass ratios."""
    with pytest.raises(ValidationError, match="inconsistent with Isp_sl\\*mdot\\*g0"):
        SolidMotor.model_validate({
            "type": "solid_motor",
            "isp_vacuum": 250.0,
            "isp_sl": 220.0,
            "propellant_mass": 1.0,    # Very little propellant
            "burn_time": 10.0,          # Very slow burn
            "thrust_mean": 500000.0,    # Insanely high thrust (Impossible)
            "thrust_peak": 600000.0,
            "propellant_density": 1700.0
        })

def test_ramjet_valid():
    """Test parsing a valid RamjetEngine with dimensions."""
    ramjet = RamjetEngine.model_validate({
        "type": "ramjet_engine",
        "design_mach": 2.5,
        "combustor_temp": 2000.0,
        "nozzle_area_ratio": 4.0,
        "nozzle_throat_diameter": 0.1,
        "nozzle_exit_diameter": 0.2  # 0.2 / 0.1 = 2, squared = 4 (Perfect!)
    })
    assert ramjet.design_mach == 2.5
    assert RamjetEngine.UNITS["combustor_temp"] == "K"
    assert RamjetEngine.UNITS["nozzle_throat_diameter"] == "m"

def test_ramjet_inconsistent_area_ratio_fails():
    """Test that the nozzle validator catches bad geometry inputs."""
    with pytest.raises(ValidationError, match="inconsistent with diameters"):
        RamjetEngine.model_validate({
            "type": "ramjet_engine",
            "design_mach": 2.5,
            "combustor_temp": 2000.0,
            "nozzle_area_ratio": 9.0,         # User claims area ratio is 9
            "nozzle_throat_diameter": 0.1,
            "nozzle_exit_diameter": 0.2     # But diameters only imply area ratio of 4!
        })

