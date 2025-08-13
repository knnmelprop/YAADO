# sztafeta_mission.py
# 
# Created:  August 2025
# Modified: 

"""
Droniada Sztafeta Competition Mission Definition
Based on competition requirements and perplexity analysis
"""

# ----------------------------------------------------------------------
#   Imports
# ----------------------------------------------------------------------

import SUAVE
import numpy as np
from SUAVE.Core import Units

# ----------------------------------------------------------------------
#   Define Mission
# ----------------------------------------------------------------------

def define_mission(vehicle):
    """
    Defines the Droniada Sztafeta competition mission profile
    
    Mission Requirements:
    - Drop 4 light beacons over two 600m circuits
    - Flight altitude: 50-60m AGL
    - Night operation, autonomous mode
    - Maximum mission time: 30 minutes
    - Environmental: wind up to 8 m/s
    """

    # ------------------------------------------------------------------
    #   Initialize the Mission
    # ------------------------------------------------------------------

    mission = SUAVE.Analyses.Mission.Sequential_Segments()
    mission.tag = 'Droniada_Sztafeta_Mission'

    # airport (competition site)
    airport = SUAVE.Attributes.Airports.Airport()
    airport.altitude   = 0.0 * Units.ft         # Ground level
    airport.delta_isa  = 0.0                    # Standard atmosphere
    airport.atmosphere = SUAVE.Attributes.Atmospheres.Earth.US_Standard_1976()

    mission.airport = airport    

    # unpack Segments module
    Segments = SUAVE.Analyses.Mission.Segments

    # base segment
    base_segment = Segments.Segment()
    base_segment.process.iterate.conditions.stability    = SUAVE.Methods.skip
    base_segment.process.finalize.post_process.stability = SUAVE.Methods.skip        

    # ------------------------------------------------------------------
    #   Takeoff and Initial Climb
    # ------------------------------------------------------------------

    segment = Segments.Ground.Takeoff(base_segment)
    segment.tag = "takeoff"
    
    segment.analyses.extend(base_segment.analyses)
    
    # Takeoff parameters for small UAV
    segment.velocity_start           = 0.0 * Units['m/s']
    segment.velocity_end             = 12.0 * Units['m/s']  # Liftoff speed
    segment.friction_coefficient     = 0.04                 # Paved runway
    segment.throttle                 = 0.8                  # 80% power for takeoff
    
    # add to mission
    mission.append_segment(segment)

    # ------------------------------------------------------------------
    #   Climb to Operating Altitude
    # ------------------------------------------------------------------

    segment = Segments.Climb.Constant_Speed_Constant_Rate(base_segment)
    segment.tag = "climb_to_altitude"

    segment.analyses.extend(base_segment.analyses)

    # Climb parameters (from perplexity analysis)
    segment.altitude_start = 0.0 * Units.meter
    segment.altitude_end   = 55.0 * Units.meter     # 55m AGL (middle of 50-60m range)
    segment.air_speed      = 18.0 * Units['m/s']    # Conservative climb speed
    segment.climb_rate     = 3.0 * Units['m/s']     # Good climb performance

    # add to mission
    mission.append_segment(segment)

    # ------------------------------------------------------------------
    #   First Circuit: Outbound Leg
    # ------------------------------------------------------------------

    segment = Segments.Cruise.Constant_Speed_Constant_Altitude(base_segment)
    segment.tag = "circuit_1_outbound"

    segment.analyses.extend(base_segment.analyses)

    # First 600m circuit leg
    segment.altitude  = 55.0 * Units.meter
    segment.air_speed = 15.0 * Units['m/s']      # Optimal cruise speed from analysis
    segment.distance  = 600.0 * Units.meter     # Competition requirement

    # add to mission
    mission.append_segment(segment)

    # ------------------------------------------------------------------
    #   First Drop Sequence (2 beacons)
    # ------------------------------------------------------------------

    segment = Segments.Cruise.Constant_Speed_Constant_Altitude_Loiter(base_segment)
    segment.tag = "drop_sequence_1"

    segment.analyses.extend(base_segment.analyses)

    # Loiter for precision dropping
    segment.altitude  = 55.0 * Units.meter
    segment.air_speed = 12.0 * Units['m/s']      # Reduced speed for accuracy
    segment.time      = 3.0 * Units.minute      # Time for 2 beacon drops

    # add to mission
    mission.append_segment(segment)

    # ------------------------------------------------------------------
    #   First Circuit: Return Leg
    # ------------------------------------------------------------------

    segment = Segments.Cruise.Constant_Speed_Constant_Altitude(base_segment)
    segment.tag = "circuit_1_return"

    segment.analyses.extend(base_segment.analyses)

    # Return to start point
    segment.altitude  = 55.0 * Units.meter
    segment.air_speed = 15.0 * Units['m/s']
    segment.distance  = 600.0 * Units.meter

    # add to mission
    mission.append_segment(segment)

    # ------------------------------------------------------------------
    #   Second Circuit: Outbound Leg
    # ------------------------------------------------------------------

    segment = Segments.Cruise.Constant_Speed_Constant_Altitude(base_segment)
    segment.tag = "circuit_2_outbound"

    segment.analyses.extend(base_segment.analyses)

    # Second 600m circuit leg
    segment.altitude  = 55.0 * Units.meter
    segment.air_speed = 15.0 * Units['m/s']
    segment.distance  = 600.0 * Units.meter

    # add to mission
    mission.append_segment(segment)

    # ------------------------------------------------------------------
    #   Second Drop Sequence (2 beacons)
    # ------------------------------------------------------------------

    segment = Segments.Cruise.Constant_Speed_Constant_Altitude_Loiter(base_segment)
    segment.tag = "drop_sequence_2"

    segment.analyses.extend(base_segment.analyses)

    # Final beacon drops
    segment.altitude  = 55.0 * Units.meter
    segment.air_speed = 12.0 * Units['m/s']
    segment.time      = 3.0 * Units.minute      # Time for final 2 beacon drops

    # add to mission
    mission.append_segment(segment)

    # ------------------------------------------------------------------
    #   Second Circuit: Return Leg
    # ------------------------------------------------------------------

    segment = Segments.Cruise.Constant_Speed_Constant_Altitude(base_segment)
    segment.tag = "circuit_2_return"

    segment.analyses.extend(base_segment.analyses)

    # Return to landing pattern
    segment.altitude  = 55.0 * Units.meter
    segment.air_speed = 15.0 * Units['m/s']
    segment.distance  = 600.0 * Units.meter

    # add to mission
    mission.append_segment(segment)

    # ------------------------------------------------------------------
    #   Descent for Landing
    # ------------------------------------------------------------------

    segment = Segments.Descent.Constant_Speed_Constant_Rate(base_segment)
    segment.tag = "descent_to_landing"

    segment.analyses.extend(base_segment.analyses)

    # Descent parameters
    segment.altitude_start = 55.0 * Units.meter
    segment.altitude_end   = 0.0 * Units.meter
    segment.air_speed      = 16.0 * Units['m/s']    # Approach speed
    segment.descent_rate   = 2.5 * Units['m/s']     # Conservative descent

    # add to mission
    mission.append_segment(segment)

    # ------------------------------------------------------------------
    #   Landing
    # ------------------------------------------------------------------

    segment = Segments.Ground.Landing(base_segment)
    segment.tag = "landing"
    
    segment.analyses.extend(base_segment.analyses)
    
    # Landing parameters
    segment.velocity_start           = 16.0 * Units['m/s']
    segment.velocity_end             = 0.0 * Units['m/s']
    segment.friction_coefficient     = 0.04
    segment.throttle                 = 0.0                  # Idle power
    
    # add to mission
    mission.append_segment(segment)

    # ------------------------------------------------------------------    
    #   Mission definition complete    
    # ------------------------------------------------------------------

    # Print mission summary
    print_mission_summary(mission)

    return mission


# ----------------------------------------------------------------------
#   Helper Functions
# ----------------------------------------------------------------------

def print_mission_summary(mission):
    """
    Prints a summary of the mission profile
    """
    
    print(f"\n   Mission Profile Summary:")
    print(f"   - Mission: {mission.tag}")
    print(f"   - Segments: {len(mission.segments)}")
    
    # Calculate total mission parameters
    total_distance = 0.0
    total_time_estimate = 0.0
    
    for segment in mission.segments:
        if hasattr(segment, 'distance'):
            total_distance += segment.distance
        
        # Estimate time for each segment
        if hasattr(segment, 'distance') and hasattr(segment, 'air_speed'):
            if segment.distance > 0 and segment.air_speed > 0:
                total_time_estimate += segment.distance / segment.air_speed
        elif hasattr(segment, 'time'):
            total_time_estimate += segment.time
        elif hasattr(segment, 'altitude_start') and hasattr(segment, 'altitude_end'):
            if hasattr(segment, 'climb_rate') and segment.climb_rate > 0:
                altitude_change = abs(segment.altitude_end - segment.altitude_start)
                total_time_estimate += altitude_change / segment.climb_rate
            elif hasattr(segment, 'descent_rate') and segment.descent_rate > 0:
                altitude_change = abs(segment.altitude_end - segment.altitude_start)
                total_time_estimate += altitude_change / segment.descent_rate
    
    print(f"   - Total Distance: {total_distance:.0f} m")
    print(f"   - Estimated Time: {total_time_estimate/60:.1f} minutes")
    print(f"   - Operating Altitude: 55 m AGL")
    print(f"   - Beacon Drops: 4 (2 per circuit)")


def validate_mission_constraints(mission):
    """
    Validates mission against Droniada Sztafeta competition constraints
    """
    
    constraints = {
        'max_mission_time': 30.0,      # minutes
        'min_altitude': 50.0,          # meters AGL
        'max_altitude': 60.0,          # meters AGL
        'required_beacons': 4,         # number
        'circuit_distance': 600.0,     # meters per circuit
        'max_wind_speed': 8.0,         # m/s capability required
    }
    
    print(f"\n   Competition Constraint Validation:")
    print(f"   - Max mission time: {constraints['max_mission_time']} min")
    print(f"   - Altitude range: {constraints['min_altitude']}-{constraints['max_altitude']} m AGL")
    print(f"   - Circuit distance: {constraints['circuit_distance']} m")
    print(f"   - Required beacons: {constraints['required_beacons']}")
    print(f"   - Wind capability: up to {constraints['max_wind_speed']} m/s")
    
    return constraints


#: def define_mission()
