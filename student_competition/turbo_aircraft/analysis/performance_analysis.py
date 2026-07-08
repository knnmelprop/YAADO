# performance_analysis.py
# 
# Created:  August 2025
# Modified: 

"""
Student Competition Aircraft Performance Analysis
"""

# ----------------------------------------------------------------------
#   Imports
# ----------------------------------------------------------------------

import SUAVE
import numpy as np
from SUAVE.Core import Units

# ----------------------------------------------------------------------
#   Evaluate Mission
# ----------------------------------------------------------------------

def evaluate_mission(vehicle, mission):
    """
    Evaluates the mission performance
    """
    
    # ------------------------------------------------------------------
    #   Setup Analyses
    # ------------------------------------------------------------------
    
    analyses = setup_analyses(vehicle)
    
    # finalize the mission analyses
    mission.finalize()
    
    # ------------------------------------------------------------------
    #   Evaluate Mission
    # ------------------------------------------------------------------
    
    results = mission.evaluate(analyses)
    
    return results


def setup_analyses(vehicle):
    """
    Sets up the analysis for the student competition aircraft
    """
    
    # ------------------------------------------------------------------
    #   Initialize the Analyses
    # ------------------------------------------------------------------
    
    analyses = SUAVE.Analyses.Vehicle()
    
    # ------------------------------------------------------------------
    #   Basic Geometry Relations
    # ------------------------------------------------------------------
    sizing = SUAVE.Analyses.Sizing.Sizing()
    sizing.features.vehicle = vehicle
    analyses.append(sizing)
    
    # ------------------------------------------------------------------
    #   Weights
    # ------------------------------------------------------------------
    weights = SUAVE.Analyses.Weights.Weights_Transport()
    weights.vehicle = vehicle
    analyses.append(weights)
    
    # ------------------------------------------------------------------
    #   Aerodynamics Analysis
    # ------------------------------------------------------------------
    
    aerodynamics = SUAVE.Analyses.Aerodynamics.Fidelity_Zero()
    aerodynamics.geometry = vehicle
    aerodynamics.settings.drag_coefficient_increment = 0.0000
    analyses.append(aerodynamics)
    
    # ------------------------------------------------------------------
    #   Stability Analysis
    # ------------------------------------------------------------------
    stability = SUAVE.Analyses.Stability.Fidelity_Zero()
    stability.geometry = vehicle
    analyses.append(stability)
    
    # ------------------------------------------------------------------
    #   Energy
    # ------------------------------------------------------------------
    energy= SUAVE.Analyses.Energy.Energy()
    energy.network = vehicle.networks #what is called throughout the mission (at every time step))
    analyses.append(energy)
    
    # ------------------------------------------------------------------
    #   Planet Analysis
    # ------------------------------------------------------------------
    planet = SUAVE.Analyses.Planets.Planet()
    analyses.append(planet)
    
    # ------------------------------------------------------------------
    #   Atmosphere Analysis
    # ------------------------------------------------------------------
    atmosphere = SUAVE.Analyses.Atmospheric.US_Standard_1976()
    atmosphere.features.planet = planet.features
    analyses.append(atmosphere)   
    
    # done!
    return analyses

#: def setup_analyses()
