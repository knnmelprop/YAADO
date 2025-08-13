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
    
    # Create a simplified turbojet network for the GTM-140
    turbojet = SUAVE.Components.Energy.Networks.Turbojet()
    turbojet.tag = 'gtm140_turbojet'
    
    # ------------------------------------------------------------------
    #   Engine Setup
    # ------------------------------------------------------------------
    
    turbojet.number_of_engines = 1.0               # Single engine
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
    
    # add to the network
    turbojet.append(ram)
    
    # ------------------------------------------------------------------
    #   Component 2 - Inlet Nozzle
    # ------------------------------------------------------------------
    
    inlet_nozzle = SUAVE.Components.Energy.Converters.Compression_Nozzle()
    inlet_nozzle.tag = 'inlet_nozzle'
    
    # GTM-140 specific inlet characteristics
    inlet_nozzle.polytropic_efficiency = 0.95      # Small engine efficiency
    inlet_nozzle.pressure_ratio        = 0.98      # Inlet losses
    
    # add to network
    turbojet.append(inlet_nozzle)
    
    # ------------------------------------------------------------------
    #   Component 3 - Compressor (Single-stage centrifugal)
    # ------------------------------------------------------------------
    
    compressor = SUAVE.Components.Energy.Converters.Compressor()    
    compressor.tag = 'compressor'
    
    # GTM-140 specifications: pressure ratio 2.8:1
    compressor.polytropic_efficiency = 0.78        # Small centrifugal compressor
    compressor.pressure_ratio        = 2.8         # From GTM-140 specs
    
    # add to network
    turbojet.append(compressor)
    
    # ------------------------------------------------------------------
    #   Component 4 - Combustor
    # ------------------------------------------------------------------
    
    combustor = SUAVE.Components.Energy.Converters.Combustor()   
    combustor.tag = 'combustor'
    
    # GTM-140 combustion characteristics
    combustor.efficiency                = 0.92     # Small engine combustion efficiency
    combustor.alphac                    = 1.0      # Stoichiometric ratio
    combustor.turbine_inlet_temperature = 1023.0 * Units.kelvin  # Max EGT from specs
    combustor.pressure_ratio            = 0.94     # Combustor pressure drop
    combustor.fuel_data                 = SUAVE.Attributes.Propellants.Jet_A()
    
    # add to network
    turbojet.append(combustor)
    
    # ------------------------------------------------------------------
    #   Component 5 - Turbine (Single-stage axial)
    # ------------------------------------------------------------------
    
    turbine = SUAVE.Components.Energy.Converters.Turbine()   
    turbine.tag = 'turbine'
    
    # GTM-140 turbine characteristics
    turbine.mechanical_efficiency = 0.95           # Small turbine efficiency
    turbine.polytropic_efficiency = 0.85           # Single stage axial turbine
    
    # add to network
    turbojet.append(turbine)
    
    # ------------------------------------------------------------------
    #   Component 6 - Nozzle
    # ------------------------------------------------------------------
    
    nozzle = SUAVE.Components.Energy.Converters.Expansion_Nozzle()   
    nozzle.tag = 'nozzle'
    
    # GTM-140 nozzle characteristics
    nozzle.polytropic_efficiency = 0.92            # Small nozzle efficiency
    nozzle.pressure_ratio        = 0.98            # Nozzle pressure ratio
    
    # add to network
    turbojet.append(nozzle)
    
    # ------------------------------------------------------------------
    #   Component 7 - Thrust
    # ------------------------------------------------------------------
    
    thrust = SUAVE.Components.Energy.Processes.Thrust()       
    thrust.tag = 'compute_thrust'
    
    # GTM-140 thrust characteristics
    thrust.total_design             = 140.0 * Units.N     # Maximum thrust from specs
    
    # design sizing conditions (low altitude, subsonic)
    thrust.design_altitude          = 1000.0 * Units.ft   # Low altitude operation
    thrust.design_mach_number       = 0.06                # ~20 m/s design speed
    thrust.design_thrust            = 55.0 * Units.N      # ~40% power for cruise
    
    # add to network
    turbojet.thrust = thrust
    
    # ------------------------------------------------------------------
    #   Size the Engine
    # ------------------------------------------------------------------
    
    gtm140_sizing(turbojet)
    
    return turbojet


# ----------------------------------------------------------------------
#   GTM-140 Specific Functions
# ----------------------------------------------------------------------

def gtm140_sizing(turbojet):
    """
    Sizes the GTM-140 turbojet based on design conditions
    """
    
    # Get components
    ram         = turbojet.ram
    inlet       = turbojet.inlet_nozzle
    compressor  = turbojet.compressor
    combustor   = turbojet.combustor
    turbine     = turbojet.turbine
    nozzle      = turbojet.nozzle
    thrust      = turbojet.thrust
    
    # Create sizing segment
    sizing_segment = SUAVE.Components.Energy.Segments.Segment()
    
    # Set design conditions (low altitude, low speed for UAV)
    sizing_segment.state.conditions.freestream.altitude       = thrust.design_altitude 
    sizing_segment.state.conditions.freestream.mach_number    = thrust.design_mach_number
    
    # Standard atmosphere at 1000 ft
    sizing_segment.state.conditions.freestream.pressure       = 97717.0 * Units.pascal
    sizing_segment.state.conditions.freestream.temperature    = 285.0 * Units.kelvin
    sizing_segment.state.conditions.freestream.density        = sizing_segment.state.conditions.freestream.pressure/(287*sizing_segment.state.conditions.freestream.temperature)
    sizing_segment.state.conditions.freestream.dynamic_viscosity = 1.79e-05 * Units.pascal * Units.second
    sizing_segment.state.conditions.freestream.gravity        = 9.80665 * Units.meter/Units.second**2
    sizing_segment.state.conditions.freestream.isentropic_expansion_factor = 1.4
    sizing_segment.state.conditions.freestream.specific_heat_at_constant_pressure = 1004.5 * Units.joule/(Units.kg * Units.kelvin)
    sizing_segment.state.conditions.freestream.speed_of_sound = np.sqrt(sizing_segment.state.conditions.freestream.isentropic_expansion_factor*287*sizing_segment.state.conditions.freestream.temperature)
    sizing_segment.state.conditions.freestream.velocity       = sizing_segment.state.conditions.freestream.speed_of_sound*thrust.design_mach_number
    sizing_segment.state.conditions.propulsion.throttle      = 0.4  # 40% throttle for cruise
    
    # Size the engine
    turbojet.engine_sizing_1d(sizing_segment.state)
    
    return


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
