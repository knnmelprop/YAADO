import pytest
from pydantic import ValidationError
from YAADO_Core.ComponentStore.propulsion import SolidMotor, RamjetEngine

def test_solid_motor_valid():
    """Test parsing a perfectly valid SolidMotor."""
    motor = SolidMotor.model_validate({
        "type": "solid_motor",
        "isp_vacuum_s": 250.0,
        "isp_sl_s": 220.0,
        "propellant_mass_kg": 10.0,
        "burn_time_s": 2.0,
        "thrust_mean_N": 10500.0,  # Ideal: 220 * (10/2) * 9.81 = ~10787 N (Very close!)
        "thrust_peak_N": 12000.0,
        "propellant_density_kg_m3": 1700.0
    })
    assert motor.thrust_peak_N == 12000.0
    assert motor.mdot_kg_per_s == 5.0

def test_solid_motor_peak_below_mean_fails():
    """Test that the physics validator blocks peak thrust < mean thrust."""
    with pytest.raises(ValidationError, match="cannot be below the mean|thrust_peak_N=10000 < thrust_mean_N=15000 N"):
        SolidMotor.model_validate({
            "type": "solid_motor",
            "isp_vacuum_s": 250.0,
            "isp_sl_s": 220.0,
            "propellant_mass_kg": 10.0,
            "burn_time_s": 2.0,
            "thrust_mean_N": 15000.0,
            "thrust_peak_N": 10000.0,  # Physically impossible
            "propellant_density_kg_m3": 1700.0
        })

def test_solid_motor_thrust_inconsistent_with_isp_fails():
    """Test that the physics validator blocks impossible thrust/mass ratios."""
    with pytest.raises(ValidationError, match="inconsistent with Isp_sl\\*mdot\\*g0"):
        SolidMotor.model_validate({
            "type": "solid_motor",
            "isp_vacuum_s": 250.0,
            "isp_sl_s": 220.0,
            "propellant_mass_kg": 1.0,    # Very little propellant
            "burn_time_s": 10.0,          # Very slow burn
            "thrust_mean_N": 500000.0,    # Insanely high thrust (Impossible)
            "thrust_peak_N": 600000.0,
            "propellant_density_kg_m3": 1700.0
        })

def test_ramjet_valid():
    """Test parsing a valid RamjetEngine with dimensions."""
    ramjet = RamjetEngine.model_validate({
        "type": "ramjet_engine",
        "design_mach": 2.5,
        "combustor_temp_K": 2000.0,
        "nozzle_area_ratio": 4.0,
        "nozzle_throat_diameter_m": 0.1,
        "nozzle_exit_diameter_m": 0.2  # 0.2 / 0.1 = 2, squared = 4 (Perfect!)
    })
    assert ramjet.design_mach == 2.5

def test_ramjet_inconsistent_area_ratio_fails():
    """Test that the nozzle validator catches bad geometry inputs."""
    with pytest.raises(ValidationError, match="inconsistent with diameters"):
        RamjetEngine.model_validate({
            "type": "ramjet_engine",
            "design_mach": 2.5,
            "combustor_temp_K": 2000.0,
            "nozzle_area_ratio": 9.0,         # User claims area ratio is 9
            "nozzle_throat_diameter_m": 0.1,
            "nozzle_exit_diameter_m": 0.2     # But diameters only imply area ratio of 4!
        })
