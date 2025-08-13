# gtm140_aircraft.py
# 
# Created:  August 2025
# Modified: 

"""
Droniada Sztafeta GTM-140 Turbojet Aircraft Vehicle Definition
Based on perplexity analysis and competition requirements
"""

# ----------------------------------------------------------------------
#   Imports
# ----------------------------------------------------------------------

import SUAVE
import numpy as np
from SUAVE.Core import Units

# Add engines module to path
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from engines.gtm140_model import create_gtm140_network

# ----------------------------------------------------------------------
#   Define Vehicle
# ----------------------------------------------------------------------

def define_vehicle():
    """
    Defines a Droniada Sztafeta competition aircraft with GTM-140 turbojet
    Based on optimization analysis from perplexity folder
    """
    
    # ------------------------------------------------------------------
    #   Initialize the Vehicle
    # ------------------------------------------------------------------    
    
    vehicle = SUAVE.Vehicle()
    vehicle.tag = 'Droniada_Sztafeta_GTM140_Aircraft'
    
    # ------------------------------------------------------------------
    #   Vehicle-level Properties
    # ------------------------------------------------------------------    
    
    # mass properties (from perplexity analysis: target ~11.8 kg)
    vehicle.mass_properties.max_takeoff               = 25.0 * Units.kg    # Competition limit
    vehicle.mass_properties.takeoff                   = 11.8 * Units.kg    # Target weight
    vehicle.mass_properties.operating_empty           = 8.2 * Units.kg     # Empty weight
    vehicle.mass_properties.max_zero_fuel             = 10.2 * Units.kg    # Without fuel
    vehicle.mass_properties.cargo                     = 1.0 * Units.kg     # 4 beacons payload
    
    # envelope properties
    vehicle.envelope.ultimate_load = 6.0
    vehicle.envelope.limit_load    = 4.0
    
    # basic parameters (from perplexity: 0.79 m² wing area)
    vehicle.reference_area         = 0.79 * Units.meter**2  
    vehicle.passengers             = 0
    vehicle.systems.control        = "fly_by_wire"
    vehicle.systems.accessories    = "short_range"
    
    # ------------------------------------------------------------------        
    #   Main Wing (Optimized for GTM-140 and competition)
    # ------------------------------------------------------------------        
    
    wing = SUAVE.Components.Wings.Main_Wing()
    wing.tag = 'main_wing'
    
    # Geometry from perplexity optimization (AR=8.0, area=0.79 m²)
    wing.aspect_ratio            = 8.0
    wing.sweeps.quarter_chord    = 0.0 * Units.deg      # Straight wing for stability
    wing.thickness_to_chord      = 0.12                 # 12% thickness for structure
    wing.taper                   = 0.7                  # Slight taper for efficiency
    wing.span_efficiency         = 0.85                 # Conservative estimate
    
    # Calculated dimensions
    wing.spans.projected         = 2.51 * Units.meter   # From perplexity: sqrt(0.79 * 8)
    wing.chords.root             = 0.37 * Units.meter   # Calculated from area/span
    wing.chords.tip              = 0.26 * Units.meter   # With taper ratio
    wing.chords.mean_aerodynamic = 0.315 * Units.meter  # MAC
    wing.areas.reference         = 0.79 * Units.meter**2
    wing.areas.wetted            = 1.8 * wing.areas.reference  # Both surfaces + interference
    wing.areas.exposed           = 0.9 * wing.areas.wetted     # Reduced exposure
    wing.areas.affected          = 0.7 * wing.areas.wetted     # Control surface area
    
    # Airfoil and twist optimization for small UAV
    wing.twists.root             = 2.0 * Units.degrees  # Root twist for efficiency
    wing.twists.tip              = 0.0 * Units.degrees  # No tip twist
    
    # Position relative to vehicle centerline
    wing.origin                  = [0.7, 0, 0] * Units.meter  # CG consideration
    wing.aerodynamic_center      = [0.25, 0, 0] * Units.meter # 25% MAC
    
    wing.vertical                = False
    wing.symmetric               = True
    wing.high_lift               = False  # Simple wing for reliability
    
    wing.dynamic_pressure_ratio  = 1.0
    
    # add to vehicle
    vehicle.append_component(wing)
    
    # ------------------------------------------------------------------        
    #   Horizontal Stabilizer (Sized for 10% static margin)
    # ------------------------------------------------------------------        
    
    wing = SUAVE.Components.Wings.Wing()
    wing.tag = 'horizontal_stabilizer'
    
    wing.aspect_ratio            = 4.0                  # Lower AR for control
    wing.sweeps.quarter_chord    = 0.0 * Units.deg
    wing.thickness_to_chord      = 0.10                 # Thinner for weight
    wing.taper                   = 0.8
    wing.span_efficiency         = 0.8                  # Lower efficiency
    
    # Sized for stability (approximately 15% of wing area)
    wing.spans.projected         = 0.71 * Units.meter   # Calculated for AR=4
    wing.chords.root             = 0.20 * Units.meter
    wing.chords.tip              = 0.16 * Units.meter
    wing.chords.mean_aerodynamic = 0.18 * Units.meter
    wing.areas.reference         = 0.12 * Units.meter**2
    wing.areas.wetted            = 2.0 * wing.areas.reference
    wing.areas.exposed           = 0.9 * wing.areas.wetted
    wing.areas.affected          = 0.6 * wing.areas.wetted
    
    wing.twists.root             = 0.0 * Units.degrees
    wing.twists.tip              = 0.0 * Units.degrees
    
    # Position for stability margin
    wing.origin                  = [1.4, 0, 0] * Units.meter  # Tail moment arm
    wing.aerodynamic_center      = [0.25, 0, 0] * Units.meter
    
    wing.vertical                = False
    wing.symmetric               = True
    wing.high_lift               = False
    
    wing.dynamic_pressure_ratio  = 0.95  # Reduced efficiency in wing wake
    
    # add to vehicle
    vehicle.append_component(wing)
    
    # ------------------------------------------------------------------
    #   Vertical Stabilizer (Sized for directional stability)
    # ------------------------------------------------------------------
    
    wing = SUAVE.Components.Wings.Wing()
    wing.tag = 'vertical_stabilizer'    
    
    wing.aspect_ratio            = 2.0                  # Typical for vertical tail
    wing.sweeps.quarter_chord    = 15.0 * Units.deg    # Slight sweep for stability
    wing.thickness_to_chord      = 0.10
    wing.taper                   = 0.6                  # Tapered for efficiency
    wing.span_efficiency         = 0.8
    
    # Sized for directional stability
    wing.spans.projected         = 0.49 * Units.meter   # Height of vertical tail
    wing.chords.root             = 0.25 * Units.meter
    wing.chords.tip              = 0.15 * Units.meter
    wing.chords.mean_aerodynamic = 0.20 * Units.meter
    wing.areas.reference         = 0.10 * Units.meter**2
    wing.areas.wetted            = 2.0 * wing.areas.reference
    wing.areas.exposed           = 0.9 * wing.areas.wetted
    wing.areas.affected          = 0.5 * wing.areas.wetted
    
    wing.twists.root             = 0.0 * Units.degrees
    wing.twists.tip              = 0.0 * Units.degrees
    
    wing.origin                  = [1.4, 0, 0] * Units.meter
    wing.aerodynamic_center      = [0.25, 0, 0] * Units.meter
    
    wing.vertical                = True 
    wing.symmetric               = False
    wing.t_tail                  = False
    
    wing.dynamic_pressure_ratio  = 0.95
    
    # add to vehicle
    vehicle.append_component(wing)
    
    # ------------------------------------------------------------------
    #  Fuselage (Optimized for GTM-140 integration)
    # ------------------------------------------------------------------
    
    fuselage = SUAVE.Components.Fuselages.Fuselage()
    fuselage.tag = 'fuselage'
    
    fuselage.number_coach_seats    = 0
    fuselage.seats_abreast         = 0
    fuselage.seat_pitch            = 0
    
    # Fineness ratios for small UAV
    fuselage.fineness.nose         = 1.8                # Shorter nose
    fuselage.fineness.tail         = 2.5                # Tapered tail
    
    # Length optimized for GTM-140 (315mm) and payload bay
    fuselage.lengths.nose          = 0.3 * Units.meter
    fuselage.lengths.tail          = 0.4 * Units.meter
    fuselage.lengths.cabin         = 1.1 * Units.meter  # Engine + payload bay
    fuselage.lengths.total         = 1.8 * Units.meter  # From perplexity analysis
    fuselage.lengths.fore_space    = 0.2 * Units.meter  # Avionics
    fuselage.lengths.aft_space     = 0.2 * Units.meter  # Engine exhaust
    
    # Cross-section sized for GTM-140 (115mm diameter)
    fuselage.width                 = 0.25 * Units.meter # From perplexity analysis
    fuselage.heights.maximum       = 0.25 * Units.meter
    fuselage.heights.at_quarter_length          = 0.22 * Units.meter
    fuselage.heights.at_three_quarters_length   = 0.20 * Units.meter
    fuselage.heights.at_wing_root_quarter_chord = 0.25 * Units.meter
    
    # Surface areas for drag calculation
    fuselage.areas.side_projected  = 0.25 * 1.8 * Units.meter**2
    fuselage.areas.wetted          = np.pi * 0.25 * 1.8 * Units.meter**2
    fuselage.areas.front_projected = np.pi * (0.25/2)**2 * Units.meter**2
    
    fuselage.effective_diameter    = 0.25 * Units.meter
    
    fuselage.differential_pressure = 0.0 * Units.pascal  # Unpressurized
    
    # add to vehicle
    vehicle.append_component(fuselage)
    
    # ------------------------------------------------------------------
    #   GTM-140 Turbojet Engine Network
    # ------------------------------------------------------------------
    
    # Create GTM-140 engine network using dedicated module
    turbojet_engine = create_gtm140_network()
    
    # Add to vehicle
    vehicle.append_component(turbojet_engine)
    
    # ------------------------------------------------------------------
    #   Landing Gear (Simple fixed gear)
    # ------------------------------------------------------------------
    
    landing_gear = SUAVE.Components.Landing_Gear.Landing_Gear()
    landing_gear.tag = "main_landing_gear"
    
    # Small UAV landing gear
    landing_gear.main_tire_diameter = 0.15 * Units.m
    landing_gear.nose_tire_diameter = 0.10 * Units.m
    landing_gear.main_strut_length  = 0.20 * Units.m
    landing_gear.nose_strut_length  = 0.15 * Units.m
    landing_gear.main_units  = 2    # Two main gear
    landing_gear.nose_units  = 1    # One nose gear
    landing_gear.main_wheels = 1    # Single wheels
    landing_gear.nose_wheels = 1    # Single nose wheel
    vehicle.landing_gear = landing_gear
    
    # ------------------------------------------------------------------
    #   Fuel System
    # ------------------------------------------------------------------
    
    # Fuel tank sized for mission requirements (2.6 kg from perplexity)
    fuel = SUAVE.Components.Energy.Storages.Fuel_Tanks.Fuel_Tank()
    fuel.origin             = [0.9, 0, 0] * Units.meter  # Behind wing
    fuel.mass_properties.center_of_gravity = [0.9, 0, 0] * Units.meter
    fuel.mass_properties.fuel_mass_when_full = 2.6 * Units.kg
    fuel.fuel_selector_ratio = 1.0
    fuel.fuel               = SUAVE.Attributes.Propellants.Jet_A()
    
    # add fuel tank to vehicle
    vehicle.fuel = fuel
    
    # ------------------------------------------------------------------
    #   Payload Bay (Beacon Drop System)
    # ------------------------------------------------------------------
    
    payload_bay = SUAVE.Components.Payloads.Payload()
    payload_bay.tag = 'beacon_drop_system'
    payload_bay.origin = [0.5, 0, -0.1] * Units.meter  # Below wing
    payload_bay.mass_properties.mass = 1.0 * Units.kg  # 4 beacons + mechanism
    payload_bay.mass_properties.center_of_gravity = [0.5, 0, -0.1] * Units.meter
    
    # add to vehicle
    vehicle.append_component(payload_bay)
    
    # ------------------------------------------------------------------
    #   Vehicle Definition Complete
    # ------------------------------------------------------------------
    
    # Print configuration summary
    print_vehicle_summary(vehicle)
    
    return vehicle


# ----------------------------------------------------------------------
#   Helper Functions
# ----------------------------------------------------------------------

def print_vehicle_summary(vehicle):
    """
    Prints a summary of the vehicle configuration
    """
    print(f"\n   Vehicle Configuration Summary:")
    print(f"   - MTOW: {vehicle.mass_properties.max_takeoff:.1f} kg")
    print(f"   - Empty Weight: {vehicle.mass_properties.operating_empty:.1f} kg")
    print(f"   - Wing Area: {vehicle.reference_area:.2f} m²")
    print(f"   - Wing Span: {vehicle.wings.main_wing.spans.projected:.2f} m")
    print(f"   - Aspect Ratio: {vehicle.wings.main_wing.aspect_ratio:.1f}")
    print(f"   - Fuselage Length: {vehicle.fuselages.fuselage.lengths.total:.1f} m")


#: def define_vehicle()
