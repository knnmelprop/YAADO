# competition_mission.py
# 
# Created:  August 2025
# Modified: 

"""
Student Competition Mission Definition
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
    Defines a typical student competition mission profile
    """

    # ------------------------------------------------------------------
    #   Initialize the Mission
    # ------------------------------------------------------------------

    mission = SUAVE.Analyses.Mission.Sequential_Segments()
    mission.tag = 'Student_Competition_Mission'

    # airport
    airport = SUAVE.Attributes.Airports.Airport()
    airport.altitude   =  0.0  * Units.ft
    airport.delta_isa  =  0.0
    airport.atmosphere = SUAVE.Attributes.Atmospheres.Earth.US_Standard_1976()

    mission.airport = airport    

    # unpack Segments module
    Segments = SUAVE.Analyses.Mission.Segments

    # base segment
    base_segment = Segments.Segment()
    base_segment.process.iterate.conditions.stability    = SUAVE.Methods.skip
    base_segment.process.finalize.post_process.stability = SUAVE.Methods.skip        

    # ------------------------------------------------------------------
    #   First Climb Segment: Constant Speed, Constant Rate
    # ------------------------------------------------------------------

    segment = Segments.Climb.Constant_Speed_Constant_Rate(base_segment)
    segment.tag = "climb_1"

    segment.analyses.extend( base_segment.analyses )

    segment.altitude_start = 0.0   * Units.km
    segment.altitude_end   = 3.0   * Units.km
    segment.air_speed      = 125.0 * Units['m/s']
    segment.climb_rate     = 6.0   * Units['m/s']

    # add to misison
    mission.append_segment(segment)

    # ------------------------------------------------------------------
    #   Second Climb Segment: Constant Speed, Constant Rate
    # ------------------------------------------------------------------    

    segment = Segments.Climb.Constant_Speed_Constant_Rate(base_segment)
    segment.tag = "climb_2"

    segment.analyses.extend( base_segment.analyses )

    segment.altitude_start = 3.0   * Units.km
    segment.altitude_end   = 8.0   * Units.km
    segment.air_speed      = 190.0 * Units['m/s']
    segment.climb_rate     = 6.0   * Units['m/s']

    # add to mission
    mission.append_segment(segment)

    # ------------------------------------------------------------------
    #   Third Climb Segment: Constant Speed, Constant Rate
    # ------------------------------------------------------------------    

    segment = Segments.Climb.Constant_Speed_Constant_Rate(base_segment)
    segment.tag = "climb_3"

    segment.analyses.extend( base_segment.analyses )

    segment.altitude_start = 8.0   * Units.km
    segment.altitude_end   = 10.5  * Units.km
    segment.air_speed      = 226.0 * Units['m/s']
    segment.climb_rate     = 3.0   * Units['m/s']

    # add to mission
    mission.append_segment(segment)

    # ------------------------------------------------------------------    
    #   Cruise Segment: Constant Speed, Constant Altitude
    # ------------------------------------------------------------------    

    segment = Segments.Cruise.Constant_Speed_Constant_Altitude(base_segment)
    segment.tag = "cruise"

    segment.analyses.extend( base_segment.analyses )

    segment.altitude  = 10.5  * Units.km
    segment.air_speed = 230.0 * Units['m/s']
    segment.distance  = 2000. * Units.km

    # add to mission
    mission.append_segment(segment)

    # ------------------------------------------------------------------    
    #   First Descent Segment: Constant Speed, Constant Rate
    # ------------------------------------------------------------------    

    segment = Segments.Descent.Constant_Speed_Constant_Rate(base_segment)
    segment.tag = "descent_1"

    segment.analyses.extend( base_segment.analyses )

    segment.altitude_start = 10.5 * Units.km
    segment.altitude_end   = 5.0  * Units.km
    segment.air_speed      = 220.0 * Units['m/s']
    segment.descent_rate   = 5.0   * Units['m/s']

    # add to mission
    mission.append_segment(segment)

    # ------------------------------------------------------------------    
    #   Second Descent Segment: Constant Speed, Constant Rate
    # ------------------------------------------------------------------    

    segment = Segments.Descent.Constant_Speed_Constant_Rate(base_segment)
    segment.tag = "descent_2"

    segment.analyses.extend( base_segment.analyses )

    segment.altitude_start = 5.0  * Units.km
    segment.altitude_end   = 0.0  * Units.km
    segment.air_speed      = 145.0 * Units['m/s']
    segment.descent_rate   = 5.0   * Units['m/s']

    # add to mission
    mission.append_segment(segment)

    # ------------------------------------------------------------------    
    #   Mission definition complete    
    # ------------------------------------------------------------------

    return mission

#: def define_mission()
