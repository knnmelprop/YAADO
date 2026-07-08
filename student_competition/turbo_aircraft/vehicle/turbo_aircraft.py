# turbo_aircraft.py
# 
# Created:  August 2025
# Modified: 

"""
Student Competition Turbo Engine Aircraft Vehicle Definition
"""

# ----------------------------------------------------------------------
#   Imports
# ----------------------------------------------------------------------

import SUAVE
import numpy as np
from SUAVE.Core import Units

# ----------------------------------------------------------------------
#   Define Vehicle
# ----------------------------------------------------------------------

def define_vehicle():
    """
    Defines a student competition aircraft with turbo engine
    """
    
    # ------------------------------------------------------------------
    #   Initialize the Vehicle
    # ------------------------------------------------------------------    
    
    vehicle = SUAVE.Vehicle()
    vehicle.tag = 'Student_Competition_Turbo_Aircraft'
    
    # ------------------------------------------------------------------
    #   Vehicle-level Properties
    # ------------------------------------------------------------------    
    
    # mass properties
    vehicle.mass_properties.max_takeoff               = 1500. * Units.kg
    vehicle.mass_properties.takeoff                   = 1500. * Units.kg
    vehicle.mass_properties.operating_empty           = 1000. * Units.kg
    vehicle.mass_properties.takeoff                   = 1500. * Units.kg
    vehicle.mass_properties.max_zero_fuel             = 1500. * Units.kg
    vehicle.mass_properties.cargo                     = 0.  * Units.kg
    
    # envelope properties
    vehicle.envelope.ultimate_load = 5.7
    vehicle.envelope.limit_load    = 3.8
    
    # basic parameters
    vehicle.reference_area         = 124.862 * Units.meter**2  
    vehicle.passengers             = 0
    vehicle.systems.control        = "fully powered" 
    vehicle.systems.accessories    = "medium range"
    
    # ------------------------------------------------------------------        
    #   Main Wing
    # ------------------------------------------------------------------        
    
    wing = SUAVE.Components.Wings.Main_Wing()
    wing.tag = 'main_wing'
    
    wing.aspect_ratio            = 10.
    wing.sweeps.quarter_chord    = 0.0 * Units.deg
    wing.thickness_to_chord      = 0.12
    wing.taper                   = 1.0
    wing.span_efficiency         = 0.9
    
    wing.spans.projected         = 35.66 * Units.meter
    wing.chords.root             = 3.5 * Units.meter
    wing.chords.tip              = 3.5 * Units.meter
    wing.chords.mean_aerodynamic = 3.5 * Units.meter
    wing.areas.reference         = 124.862 * Units.meter**2
    wing.areas.wetted            = 2.0 * wing.areas.reference
    wing.areas.exposed           = 0.8 * wing.areas.wetted
    wing.areas.affected          = 0.6 * wing.areas.wetted
    
    wing.twists.root             = 3.0 * Units.degrees
    wing.twists.tip              = 3.0 * Units.degrees
    
    wing.origin                  = [20,0,0] * Units.meter
    wing.aerodynamic_center      = [3,0,0] * Units.meter
    
    wing.vertical                = False
    wing.symmetric               = True
    wing.high_lift               = True
    
    wing.dynamic_pressure_ratio  = 1.0
    
    # add to vehicle
    vehicle.append_component(wing)
    
    # ------------------------------------------------------------------        
    #   Horizontal Stabilizer
    # ------------------------------------------------------------------        
    
    wing = SUAVE.Components.Wings.Wing()
    wing.tag = 'horizontal_stabilizer'
    
    wing.aspect_ratio            = 3.0
    wing.sweeps.quarter_chord    = 0.0 * Units.deg
    wing.thickness_to_chord      = 0.12
    wing.taper                   = 1.0
    wing.span_efficiency         = 0.9
    
    wing.spans.projected         = 7.5 * Units.meter
    wing.chords.root             = 2.5 * Units.meter
    wing.chords.tip              = 2.5 * Units.meter
    wing.chords.mean_aerodynamic = 2.5 * Units.meter
    wing.areas.reference         = 18.75 * Units.meter**2
    wing.areas.wetted            = 2.0 * wing.areas.reference
    wing.areas.exposed           = 0.8 * wing.areas.wetted
    wing.areas.affected          = 0.6 * wing.areas.wetted
    
    wing.twists.root             = 0.0 * Units.degrees
    wing.twists.tip              = 0.0 * Units.degrees
    
    wing.origin                  = [50,0,0] * Units.meter
    wing.aerodynamic_center      = [2,0,0] * Units.meter
    
    wing.vertical                = False
    wing.symmetric               = True
    wing.high_lift               = False
    
    wing.dynamic_pressure_ratio  = 0.9
    
    # add to vehicle
    vehicle.append_component(wing)
    
    # ------------------------------------------------------------------
    #   Vertical Stabilizer
    # ------------------------------------------------------------------
    
    wing = SUAVE.Components.Wings.Wing()
    wing.tag = 'vertical_stabilizer'    
    
    wing.aspect_ratio            = 1.5
    wing.sweeps.quarter_chord    = 25. * Units.deg
    wing.thickness_to_chord      = 0.12
    wing.taper                   = 0.5
    wing.span_efficiency         = 0.9
    
    wing.spans.projected         = 6.0 * Units.meter
    wing.chords.root             = 4.0 * Units.meter
    wing.chords.tip              = 2.0 * Units.meter
    wing.chords.mean_aerodynamic = 3.0 * Units.meter
    wing.areas.reference         = 18.0 * Units.meter**2
    wing.areas.wetted            = 2.0 * wing.areas.reference
    wing.areas.exposed           = 0.8 * wing.areas.wetted
    wing.areas.affected          = 0.6 * wing.areas.wetted
    
    wing.twists.root             = 0.0 * Units.degrees
    wing.twists.tip              = 0.0 * Units.degrees
    
    wing.origin                  = [50,0,0] * Units.meter
    wing.aerodynamic_center      = [2,0,0] * Units.meter
    
    wing.vertical                = True 
    wing.symmetric               = False
    wing.t_tail                  = False
    
    wing.dynamic_pressure_ratio  = 1.0
    
    # add to vehicle
    vehicle.append_component(wing)
    
    # ------------------------------------------------------------------
    #  Fuselage
    # ------------------------------------------------------------------
    
    fuselage = SUAVE.Components.Fuselages.Fuselage()
    fuselage.tag = 'fuselage'
    
    fuselage.number_coach_seats    = 0
    fuselage.seats_abreast         = 0
    fuselage.seat_pitch            = 1  * Units.meter
    
    fuselage.fineness.nose         = 1.6
    fuselage.fineness.tail         = 2.
    
    fuselage.lengths.nose          = 6.  * Units.meter
    fuselage.lengths.tail          = 8.  * Units.meter
    fuselage.lengths.cabin         = 28. * Units.meter
    fuselage.lengths.total         = 42. * Units.meter
    fuselage.lengths.fore_space    = 6.  * Units.meter
    fuselage.lengths.aft_space     = 5.  * Units.meter
    
    fuselage.width                 = 4.  * Units.meter
    fuselage.heights.maximum       = 4.  * Units.meter
    fuselage.heights.at_quarter_length          = 4. * Units.meter
    fuselage.heights.at_three_quarters_length   = 4. * Units.meter
    fuselage.heights.at_wing_root_quarter_chord = 4. * Units.meter
    
    fuselage.areas.side_projected  = 4. * 42. * Units.meter**2
    fuselage.areas.wetted          = 4. * np.pi * 4. * 42. * Units.meter**2
    fuselage.areas.front_projected = np.pi * 4. * Units.meter**2
    
    fuselage.effective_diameter    = 4. * Units.meter
    
    fuselage.differential_pressure = 0. * Units.pascal # Maximum differential pressure
    
    # add to vehicle
    vehicle.append_component(fuselage)
    
    # ------------------------------------------------------------------
    #   Turbo Engine Network
    # ------------------------------------------------------------------
    
    # create turbo engine network
    turbo_engine = SUAVE.Components.Energy.Networks.Turbofan()
    turbo_engine.tag = 'turbo_engine'
    
    # setup
    turbo_engine.number_of_engines = 2.0
    turbo_engine.bypass_ratio      = 5.4
    turbo_engine.engine_length     = 2.71 * Units.meter
    turbo_engine.nacelle_diameter  = 2.05 * Units.meter
    turbo_engine.origin           = [[36.5, 5.2, 1.9], [36.5, -5.2, 1.9]] * Units.meter
    
    # working fluid
    turbo_engine.working_fluid = SUAVE.Attributes.Gases.Air()
    
    # ------------------------------------------------------------------
    #   Component 1 - Ram
    
    # to convert freestream static to stagnation quantities
    
    ram = SUAVE.Components.Energy.Converters.Ram()
    ram.tag = 'ram'
    
    # add to the network
    turbo_engine.append(ram)
    
    # ------------------------------------------------------------------
    #  Component 2 - Inlet Nozzle
    
    inlet_nozzle = SUAVE.Components.Energy.Converters.Compression_Nozzle()
    inlet_nozzle.tag = 'inlet_nozzle'
    
    inlet_nozzle.polytropic_efficiency = 0.98
    inlet_nozzle.pressure_ratio        = 1.0
    
    # add to network
    turbo_engine.append(inlet_nozzle)
    
    # ------------------------------------------------------------------
    #  Component 3 - Low Pressure Compressor
    
    low_pressure_compressor = SUAVE.Components.Energy.Converters.Compressor()    
    low_pressure_compressor.tag = 'low_pressure_compressor'
    
    low_pressure_compressor.polytropic_efficiency = 0.91
    low_pressure_compressor.pressure_ratio        = 1.14
    
    # add to network
    turbo_engine.append(low_pressure_compressor)
    
    # ------------------------------------------------------------------
    #  Component 4 - High Pressure Compressor
    
    high_pressure_compressor = SUAVE.Components.Energy.Converters.Compressor()    
    high_pressure_compressor.tag = 'high_pressure_compressor'
    
    high_pressure_compressor.polytropic_efficiency = 0.91
    high_pressure_compressor.pressure_ratio        = 13.415
    
    # add to network  
    turbo_engine.append(high_pressure_compressor)
    
    # ------------------------------------------------------------------
    #  Component 5 - Low Pressure Turbine
    
    low_pressure_turbine = SUAVE.Components.Energy.Converters.Turbine()   
    low_pressure_turbine.tag='low_pressure_turbine'
    
    low_pressure_turbine.mechanical_efficiency = 0.99
    low_pressure_turbine.polytropic_efficiency = 0.93
    
    # add to network
    turbo_engine.append(low_pressure_turbine)
    
    # ------------------------------------------------------------------
    #  Component 6 - High Pressure Turbine
    
    high_pressure_turbine = SUAVE.Components.Energy.Converters.Turbine()   
    high_pressure_turbine.tag='high_pressure_turbine'
    
    high_pressure_turbine.mechanical_efficiency = 0.99
    high_pressure_turbine.polytropic_efficiency = 0.93
    
    # add to network
    turbo_engine.append(high_pressure_turbine)
    
    # ------------------------------------------------------------------
    #  Component 7 - Combustor
    
    combustor = SUAVE.Components.Energy.Converters.Combustor()   
    combustor.tag = 'combustor'
    
    combustor.efficiency                = 0.99
    combustor.alphac                    = 1.0     
    combustor.turbine_inlet_temperature = 1500 * Units.kelvin
    combustor.pressure_ratio            = 0.95
    combustor.fuel_data                 = SUAVE.Attributes.Propellants.Jet_A()
    
    # add to network
    turbo_engine.append(combustor)
    
    # ------------------------------------------------------------------
    #  Component 8 - Core Nozzle
    
    core_nozzle = SUAVE.Components.Energy.Converters.Expansion_Nozzle()   
    core_nozzle.tag = 'core_nozzle'
    
    core_nozzle.polytropic_efficiency = 0.95
    core_nozzle.pressure_ratio        = 0.99    
    
    # add to network
    turbo_engine.append(core_nozzle)
    
    # ------------------------------------------------------------------
    #  Component 9 - Fan Nozzle
    
    fan_nozzle = SUAVE.Components.Energy.Converters.Expansion_Nozzle()   
    fan_nozzle.tag = 'fan_nozzle'
    
    fan_nozzle.polytropic_efficiency = 0.95
    fan_nozzle.pressure_ratio        = 0.99
    
    # add to network
    turbo_engine.append(fan_nozzle)
    
    # ------------------------------------------------------------------
    #  Component 10 - Fan
    
    fan = SUAVE.Components.Energy.Converters.Fan()   
    fan.tag = 'fan'
    
    fan.polytropic_efficiency = 0.93
    fan.pressure_ratio        = 1.7
    
    # add to network
    turbo_engine.append(fan)
    
    # ------------------------------------------------------------------
    #   Component 11 - Thrust
    
    thrust = SUAVE.Components.Energy.Processes.Thrust()       
    thrust.tag ='compute_thrust'
    
    # total design thrust (includes all the engines)
    thrust.total_design             = 24000. * Units.N #Newtons
    
    # design sizing conditions
    thrust.design_altitude          = 35000.0*Units.ft
    thrust.design_mach_number       = 0.78   
    thrust.design_thrust            = 24000.0*Units.N
    
    # add to network
    turbo_engine.thrust = thrust
    
    # size the turbofan
    turbofan_sizing(turbo_engine)
    
    # add  gas turbine network gt_engine to the vehicle
    vehicle.append_component(turbo_engine)
    
    # ------------------------------------------------------------------
    #   Landing Gear
    # ------------------------------------------------------------------
    
    landing_gear = SUAVE.Components.Landing_Gear.Landing_Gear()
    landing_gear.tag = "main_landing_gear"
    
    landing_gear.main_tire_diameter = 1.12 * Units.m
    landing_gear.nose_tire_diameter = 0.6 * Units.m
    landing_gear.main_strut_length  = 1.8 * Units.m
    landing_gear.nose_strut_length  = 1.3 * Units.m
    landing_gear.main_units  = 2    #number of main landing gear units
    landing_gear.nose_units  = 1    #number of nose landing gear
    landing_gear.main_wheels = 2    #number of wheels on the main landing gear
    landing_gear.nose_wheels = 2    #number of wheels on the nose landing gear
    vehicle.landing_gear = landing_gear
    
    # ------------------------------------------------------------------
    #   Vehicle Definition Complete
    # ------------------------------------------------------------------
    
    return vehicle


# ----------------------------------------------------------------------
#   Helper Functions
# ----------------------------------------------------------------------

def turbofan_sizing(turbofan):
    """
    Sizes the turbofan
    """
    
    # Make a copy of the turbofan before sizing, in case something goes wrong
    turbofan_copy = turbofan.deep_copy()
    
    # Creating the network by manually linking the different components
    
    # set the working fluid to determine the fluid properties
    ram                       = turbofan.ram
    inlet_nozzle              = turbofan.inlet_nozzle
    low_pressure_compressor   = turbofan.low_pressure_compressor
    high_pressure_compressor  = turbofan.high_pressure_compressor
    fan                       = turbofan.fan
    combustor                 = turbofan.combustor
    high_pressure_turbine     = turbofan.high_pressure_turbine
    low_pressure_turbine      = turbofan.low_pressure_turbine
    core_nozzle               = turbofan.core_nozzle
    fan_nozzle                = turbofan.fan_nozzle
    thrust                    = turbofan.thrust
    
    # Component linking list
    turbofan.append_operating_conditions(turbofan)
    
    # populate the sizing conditions
    sizing_segment                                             = SUAVE.Components.Energy.Segments.Segment()
    
    sizing_segment.state.conditions.freestream.altitude       = thrust.design_altitude 
    sizing_segment.state.conditions.freestream.mach_number    = thrust.design_mach_number
    sizing_segment.state.conditions.freestream.pressure       = 23.84 * Units.kPascal 
    sizing_segment.state.conditions.freestream.temperature    = 218.0 * Units.kelvin
    sizing_segment.state.conditions.freestream.density        = sizing_segment.state.conditions.freestream.pressure/(287*sizing_segment.state.conditions.freestream.temperature)
    sizing_segment.state.conditions.freestream.dynamic_viscosity = 1.43e-05 * Units.pascal * Units.second
    sizing_segment.state.conditions.freestream.gravity        = 9.80665 * Units.meter/Units.second**2
    sizing_segment.state.conditions.freestream.isentropic_expansion_factor = 1.4
    sizing_segment.state.conditions.freestream.specific_heat_at_constant_pressure = 1004.5 * Units.joule/(Units.kg * Units.kelvin) 
    sizing_segment.state.conditions.freestream.speed_of_sound = np.sqrt(sizing_segment.state.conditions.freestream.isentropic_expansion_factor*287*sizing_segment.state.conditions.freestream.temperature)
    sizing_segment.state.conditions.freestream.velocity       = sizing_segment.state.conditions.freestream.speed_of_sound*thrust.design_mach_number
    sizing_segment.state.conditions.propulsion.throttle      = 1.0
    
    # Size the turbofan
    turbofan.engine_sizing_1d(sizing_segment.state)
    
    return


#: def define_vehicle()
