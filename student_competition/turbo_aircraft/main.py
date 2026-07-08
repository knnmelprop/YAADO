# main.py
# 
# Created:  August 2025
# Modified: 

"""
Student Competition Turbo Engine Aircraft Analysis
Main execution script for SUAVE analysis
"""

# ----------------------------------------------------------------------
#   Imports
# ----------------------------------------------------------------------

import SUAVE
import numpy as np
import matplotlib.pyplot as plt

from vehicle.turbo_aircraft import define_vehicle
from mission.competition_mission import define_mission
from analysis.performance_analysis import evaluate_mission
from plots.plotting import post_process

# ----------------------------------------------------------------------
#   Main
# ----------------------------------------------------------------------
def main():
    
    # build the turbo engine aircraft
    vehicle = define_vehicle()
    
    # define the competition mission
    mission = define_mission(vehicle)
    
    # evaluate the mission
    results = evaluate_mission(vehicle, mission)
    
    # plot results and save data
    post_process(vehicle, mission, results)
    
    return vehicle, mission, results


# ----------------------------------------------------------------------
#   Call Main
# ----------------------------------------------------------------------
if __name__ == '__main__':
    vehicle, mission, results = main()
    print("Student Competition Turbo Aircraft Analysis Complete!")
