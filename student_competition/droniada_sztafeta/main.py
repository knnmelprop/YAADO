#!/usr/bin/env python3
# main.py
# 
# Created:  August 2025
# Modified: 

"""
Droniada Sztafeta Competition Aircraft Analysis
Main execution script for SUAVE-based optimization
"""

# ----------------------------------------------------------------------
#   Imports
# ----------------------------------------------------------------------

import SUAVE
import numpy as np
import matplotlib.pyplot as plt
import sys
import os

# Add current directory to path for local imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vehicle.gtm140_aircraft import define_vehicle
from mission.sztafeta_mission import define_mission
from analysis.competition_analysis import evaluate_mission
from plots.competition_plots import post_process

# ----------------------------------------------------------------------
#   Main
# ----------------------------------------------------------------------
def main():
    """
    Main function for Droniada Sztafeta aircraft analysis
    """
    
    print("="*60)
    print("DRONIADA SZTAFETA COMPETITION AIRCRAFT ANALYSIS")
    print("GTM-140 Turbojet Powered UAV for Beacon Drop Mission")
    print("="*60)
    
    # build the GTM-140 aircraft
    print("\n1. Building aircraft configuration...")
    vehicle = define_vehicle()
    print(f"   ✓ Aircraft: {vehicle.tag}")
    print(f"   ✓ MTOW: {vehicle.mass_properties.max_takeoff:.1f} kg")
    print(f"   ✓ Wing Area: {vehicle.reference_area:.2f} m²")
    print(f"   ✓ Engine: GTM-140 Turbojet")
    
    # define the competition mission
    print("\n2. Defining competition mission...")
    mission = define_mission(vehicle)
    print(f"   ✓ Mission: {mission.tag}")
    print(f"   ✓ Segments: {len(mission.segments)}")
    print(f"   ✓ Competition: Droniada Sztafeta")
    
    # evaluate the mission
    print("\n3. Evaluating mission performance...")
    results = evaluate_mission(vehicle, mission)
    print("   ✓ Mission analysis complete")
    
    # plot results and save data
    print("\n4. Generating results and plots...")
    post_process(vehicle, mission, results)
    print("   ✓ Results saved to ./results/")
    print("   ✓ Plots saved to ./plots/")
    
    print("\n" + "="*60)
    print("ANALYSIS COMPLETE!")
    print("="*60)
    
    return vehicle, mission, results


def run_baseline_analysis():
    """
    Runs the baseline aircraft analysis
    """
    return main()


def run_optimization_study():
    """
    Runs optimization study (placeholder for future implementation)
    """
    print("Optimization study not yet implemented")
    print("Run baseline analysis first: python main.py")
    return None


# ----------------------------------------------------------------------
#   Call Main
# ----------------------------------------------------------------------
if __name__ == '__main__':
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == 'optimize':
            run_optimization_study()
        elif sys.argv[1] == 'baseline':
            run_baseline_analysis()
        else:
            print("Usage: python main.py [baseline|optimize]")
            print("Default: baseline analysis")
            run_baseline_analysis()
    else:
        # Default to baseline analysis
        vehicle, mission, results = run_baseline_analysis()
