# gtm140_model.py
# 
# Created:  August 2025
# Modified: 

"""
GTM-140 Miniature Turbojet Engine Model
Based on JETPOL specifications and performance data
"""

# ----------------------------------------------------------------------
#   Imports
# ----------------------------------------------------------------------

import SUAVE
import numpy as np
from SUAVE.Core import Units
from SUAVE.Methods.Propulsion.turbofan_sizing import turbofan_sizing

# ----------------------------------------------------------------------
#   GTM-140 Engine Network Creation
# ----------------------------------------------------------------------

def create_gtm140_network():
    """
    Creates a SUAVE network representing the GTM-140 turbojet engine
    Based on specifications from perplexity research:
    - Thrust: 8-140N variable
    - Weight: 1.75kg
    - Fuel consumption: 420-500 g/min at max power
    - RPM: 33,000-120,000
    """
    
    # ------------------------------------------------------------------
    #   Initialize Network
    # ------------------------------------------------------------------
    
    # Create a turbofan network and configure it as a turbojet (bypass_ratio = 0)
    turbojet = SUAVE.Components.Energy.Networks.Turbofan()
    turbojet.tag = 'gtm140_turbojet'
    
    # ------------------------------------------------------------------
    #   Engine Setup (Configure as simple turbojet)
    # ------------------------------------------------------------------
    
    turbojet.number_of_engines = 1.0               # Single engine
    turbojet.bypass_ratio      = 0.0               # No bypass for turbojet
    turbojet.engine_length     = 0.315 * Units.meter  # 315mm from specs
    turbojet.nacelle_diameter  = 0.115 * Units.meter  # 115mm from specs
    turbojet.origin           = [[0.9, 0.0, 0.0]]  # Centerline, behind wing
    
    # working fluid
    turbojet.working_fluid = SUAVE.Attributes.Gases.Air()
    
    # ------------------------------------------------------------------
    #   Component 1 - Ram
    # ------------------------------------------------------------------
    
    ram = SUAVE.Components.Energy.Converters.Ram()
    ram.tag = 'ram'
    turbojet.append(ram)
    
    # ------------------------------------------------------------------
    #   Component 2 - Inlet Nozzle
    # ------------------------------------------------------------------
    
    inlet_nozzle = SUAVE.Components.Energy.Converters.Compression_Nozzle()
    inlet_nozzle.tag = 'inlet_nozzle'
    inlet_nozzle.polytropic_efficiency = 0.95
    inlet_nozzle.pressure_ratio        = 0.98
    turbojet.append(inlet_nozzle)
    
    # ------------------------------------------------------------------
    #   Component 3 - Compressor (Single-stage centrifugal for GTM-140)
    # ------------------------------------------------------------------
    
    low_pressure_compressor = SUAVE.Components.Energy.Converters.Compressor()    
    low_pressure_compressor.tag = 'low_pressure_compressor'
    low_pressure_compressor.polytropic_efficiency = 0.78        # Small centrifugal compressor
    low_pressure_compressor.pressure_ratio        = 2.8         # From GTM-140 specs
    turbojet.append(low_pressure_compressor)
    
    # ------------------------------------------------------------------
    #   Component 4 - High Pressure Compressor (Dummy for turbofan structure)
    # ------------------------------------------------------------------
    
    high_pressure_compressor = SUAVE.Components.Energy.Converters.Compressor()    
    high_pressure_compressor.tag = 'high_pressure_compressor'
    high_pressure_compressor.polytropic_efficiency = 0.95
    high_pressure_compressor.pressure_ratio        = 1.0        # No additional compression
    turbojet.append(high_pressure_compressor)
    
    # ------------------------------------------------------------------
    #   Component 5 - Fan (Dummy for turbofan structure, no bypass)
    # ------------------------------------------------------------------
    
    fan = SUAVE.Components.Energy.Converters.Fan()   
    fan.tag = 'fan'
    fan.polytropic_efficiency = 0.95
    fan.pressure_ratio        = 1.0                # No fan compression
    turbojet.append(fan)
    
    # ------------------------------------------------------------------
    #   Component 6 - Combustor
    # ------------------------------------------------------------------
    
    combustor = SUAVE.Components.Energy.Converters.Combustor()   
    combustor.tag = 'combustor'
    combustor.efficiency                = 0.92
    combustor.alphac                    = 1.0
    combustor.turbine_inlet_temperature = 1023.0 * Units.kelvin  # Max EGT from specs
    combustor.pressure_ratio            = 0.94
    combustor.fuel_data                 = SUAVE.Attributes.Propellants.Jet_A()
    turbojet.append(combustor)
    
    # ------------------------------------------------------------------
    #   Component 7 - High Pressure Turbine
    # ------------------------------------------------------------------
    
    high_pressure_turbine = SUAVE.Components.Energy.Converters.Turbine()   
    high_pressure_turbine.tag = 'high_pressure_turbine'
    high_pressure_turbine.mechanical_efficiency = 0.95
    high_pressure_turbine.polytropic_efficiency = 0.85          # Single stage axial turbine
    turbojet.append(high_pressure_turbine)
    
    # ------------------------------------------------------------------
    #   Component 8 - Low Pressure Turbine (Dummy for turbofan structure)
    # ------------------------------------------------------------------
    
    low_pressure_turbine = SUAVE.Components.Energy.Converters.Turbine()   
    low_pressure_turbine.tag = 'low_pressure_turbine'
    low_pressure_turbine.mechanical_efficiency = 0.95
    low_pressure_turbine.polytropic_efficiency = 0.95
    turbojet.append(low_pressure_turbine)
    
    # ------------------------------------------------------------------
    #   Component 9 - Core Nozzle
    # ------------------------------------------------------------------
    
    core_nozzle = SUAVE.Components.Energy.Converters.Expansion_Nozzle()   
    core_nozzle.tag = 'core_nozzle'
    core_nozzle.polytropic_efficiency = 0.92
    core_nozzle.pressure_ratio        = 0.98
    turbojet.append(core_nozzle)
    
    # ------------------------------------------------------------------
    #   Component 10 - Fan Nozzle (Dummy for turbofan structure)
    # ------------------------------------------------------------------
    
    fan_nozzle = SUAVE.Components.Energy.Converters.Expansion_Nozzle()   
    fan_nozzle.tag = 'fan_nozzle'
    fan_nozzle.polytropic_efficiency = 0.95
    fan_nozzle.pressure_ratio        = 0.99
    turbojet.append(fan_nozzle)
    
    # ------------------------------------------------------------------
    #   Component 11 - Thrust
    # ------------------------------------------------------------------
    
    thrust = SUAVE.Components.Energy.Processes.Thrust()       
    thrust.tag = 'compute_thrust'
    thrust.total_design             = 140.0 * Units.N       # Maximum thrust from specs
    thrust.design_altitude          = 1000.0 * Units.ft     # Low altitude operation
    thrust.design_mach_number       = 0.06                  # ~20 m/s design speed
    thrust.design_thrust            = 55.0 * Units.N        # ~40% power for cruise
    turbojet.thrust = thrust
    
    # ------------------------------------------------------------------
    #   Size the Engine (Use SUAVE's built-in sizing)
    # ------------------------------------------------------------------
    
    # Use SUAVE's turbofan sizing function
    altitude = 1000.0 * Units.feet  # Design altitude
    mach_number = 0.06              # Design Mach number
    
    # Simple sizing without custom functions
    turbofan_sizing(turbojet, mach_number, altitude)
    
    return turbojet


# ----------------------------------------------------------------------
#   GTM-140 Specific Functions
# ----------------------------------------------------------------------

def get_gtm140_performance_map():
    """
    Returns performance characteristics of the GTM-140 based on specifications
    """
    
    performance_data = {
        'thrust_min': 8.0,      # N
        'thrust_max': 140.0,    # N
        'rpm_min': 33000,       # rpm
        'rpm_max': 120000,      # rpm
        'fuel_flow_min': 100,   # g/min (estimated idle)
        'fuel_flow_max': 500,   # g/min at max power
        'weight': 1.75,         # kg (complete system)
        'length': 0.315,        # m
        'diameter': 0.115,      # m
        'pressure_ratio': 2.8,  # -
        'mass_flow_max': 0.35,  # kg/s
        'egt_max': 1023,        # K (750°C)
    }
    
    return performance_data


def calculate_fuel_consumption(throttle_setting):
    """
    Calculates fuel consumption based on throttle setting
    Interpolates between idle and maximum fuel flow
    """
    
    perf_data = get_gtm140_performance_map()
    
    # Linear interpolation between min and max fuel flow
    fuel_flow = perf_data['fuel_flow_min'] + (
        (perf_data['fuel_flow_max'] - perf_data['fuel_flow_min']) * throttle_setting
    )
    
    return fuel_flow  # g/min


def calculate_thrust(throttle_setting):
    """
    Calculates thrust based on throttle setting
    """
    
    perf_data = get_gtm140_performance_map()
    
    # Non-linear thrust relationship (more realistic for turbojets)
    thrust = perf_data['thrust_min'] + (
        (perf_data['thrust_max'] - perf_data['thrust_min']) * throttle_setting**1.5
    )
    
    return thrust  # N


#: def create_gtm140_network()
