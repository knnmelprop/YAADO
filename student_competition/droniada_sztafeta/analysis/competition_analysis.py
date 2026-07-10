# competition_analysis.py
# 
# Created:  August 2025
# Modified: 

"""
Droniada Sztafeta Competition Analysis Module
Performance evaluation specific to competition requirements
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
    Evaluates the Droniada Sztafeta mission performance
    Includes competition-specific metrics and constraints
    """
    
    print("   Setting up analysis framework...")
    
    # ------------------------------------------------------------------
    #   Setup Analyses
    # ------------------------------------------------------------------
    
    analyses = setup_competition_analyses(vehicle)
    
    # Attach analyses to each mission segment
    for segment in mission.segments.values():
        segment.analyses.extend(analyses)
    
    # finalize the mission analyses
    mission.finalize()
    
    print("   Running mission analysis...")
    
    # ------------------------------------------------------------------
    #   Evaluate Mission
    # ------------------------------------------------------------------
    
    results = mission.evaluate()
    
    # ------------------------------------------------------------------
    #   Post-process Competition Metrics
    # ------------------------------------------------------------------
    
    competition_metrics = calculate_competition_metrics(vehicle, mission, results)
    
    # Add competition metrics to results
    results.competition_metrics = competition_metrics
    
    print_competition_results(competition_metrics)
    
    return results


def setup_competition_analyses(vehicle):
    """
    Sets up analysis framework optimized for small UAV competition aircraft
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
    #   Weights (Modified for small UAV)
    # ------------------------------------------------------------------
    weights = SUAVE.Analyses.Weights.Weights_UAV()  # Use UAV weight methods if available
    weights.vehicle = vehicle
    analyses.append(weights)
    
    # ------------------------------------------------------------------
    #   Aerodynamics Analysis (Low Reynolds Number)
    # ------------------------------------------------------------------
    
    aerodynamics = SUAVE.Analyses.Aerodynamics.Fidelity_Zero()
    aerodynamics.geometry = vehicle
    
    # Adjust for small UAV characteristics
    aerodynamics.settings.drag_coefficient_increment = 0.0020  # Small UAV drag penalty
    aerodynamics.settings.oswald_efficiency_factor = 0.85     # Conservative for small AR
    
    analyses.append(aerodynamics)
    
    # ------------------------------------------------------------------
    #   Stability Analysis (Small UAV specific)
    # ------------------------------------------------------------------
    stability = SUAVE.Analyses.Stability.Fidelity_Zero()
    stability.geometry = vehicle
    analyses.append(stability)
    
    # ------------------------------------------------------------------
    #   Energy Analysis (GTM-140 specific)
    # ------------------------------------------------------------------
    energy = SUAVE.Analyses.Energy.Energy()
    energy.network = vehicle.networks  # GTM-140 network
    analyses.append(energy)
    
    # ------------------------------------------------------------------
    #   Planet Analysis
    # ------------------------------------------------------------------
    planet = SUAVE.Analyses.Planets.Planet()
    analyses.append(planet)
    
    # ------------------------------------------------------------------
    #   Atmosphere Analysis (Low altitude focus)
    # ------------------------------------------------------------------
    atmosphere = SUAVE.Analyses.Atmospheric.US_Standard_1976()
    atmosphere.features.planet = planet.features
    analyses.append(atmosphere)   
    
    return analyses


def calculate_competition_metrics(vehicle, mission, results):
    """
    Calculates competition-specific performance metrics
    """
    
    print("   Calculating competition metrics...")
    
    metrics = {}
    
    # ------------------------------------------------------------------
    #   Mission Performance Metrics
    # ------------------------------------------------------------------
    
    # Calculate total mission time
    total_time = 0.0
    total_distance = 0.0
    total_fuel_consumed = 0.0
    
    for segment in results.segments.values():
        if hasattr(segment.conditions.frames.inertial, 'time'):
            segment_time = segment.conditions.frames.inertial.time[-1, 0]
            total_time += segment_time
            
        if hasattr(segment.conditions.frames.inertial, 'position_vector'):
            # Calculate distance from position changes
            positions = segment.conditions.frames.inertial.position_vector
            if len(positions) > 1:
                distances = np.sqrt(np.sum(np.diff(positions, axis=0)**2, axis=1))
                segment_distance = np.sum(distances)
                total_distance += segment_distance
        
        # Fuel consumption calculation
        if hasattr(segment.conditions.weights, 'total_mass'):
            fuel_start = segment.conditions.weights.total_mass[0, 0]
            fuel_end = segment.conditions.weights.total_mass[-1, 0]
            fuel_burned = fuel_start - fuel_end
            total_fuel_consumed += fuel_burned
    
    metrics['total_mission_time'] = total_time / 60.0  # minutes
    metrics['total_distance'] = total_distance         # meters
    metrics['total_fuel_consumed'] = total_fuel_consumed  # kg
    
    # ------------------------------------------------------------------
    #   Competition Constraint Validation
    # ------------------------------------------------------------------
    
    # Time constraint (30 minutes maximum)
    metrics['time_margin'] = 30.0 - metrics['total_mission_time']  # minutes
    metrics['time_constraint_met'] = metrics['time_margin'] > 0
    
    # Weight constraint (25 kg maximum)
    current_weight = vehicle.mass_properties.takeoff
    metrics['weight_margin'] = 25.0 - current_weight  # kg
    metrics['weight_constraint_met'] = metrics['weight_margin'] > 0
    
    # Altitude validation (50-60m AGL)
    altitude_violations = 0
    for segment in results.segments.values():
        if hasattr(segment.conditions.freestream, 'altitude'):
            altitudes = segment.conditions.freestream.altitude[:, 0]
            cruise_altitudes = altitudes[(altitudes > 10) & (altitudes < 100)]  # Filter cruise altitudes
            if len(cruise_altitudes) > 0:
                violations = np.sum((cruise_altitudes < 50) | (cruise_altitudes > 60))
                altitude_violations += violations
    
    metrics['altitude_constraint_met'] = altitude_violations == 0
    
    # ------------------------------------------------------------------
    #   Performance Efficiency Metrics
    # ------------------------------------------------------------------
    
    # Fuel efficiency
    if total_distance > 0:
        metrics['fuel_efficiency'] = total_fuel_consumed / (total_distance / 1000.0)  # kg/km
    else:
        metrics['fuel_efficiency'] = 0.0
    
    # Speed efficiency
    if total_time > 0:
        metrics['average_speed'] = total_distance / total_time  # m/s
    else:
        metrics['average_speed'] = 0.0
    
    # Range capability (with current fuel)
    if metrics['fuel_efficiency'] > 0:
        fuel_capacity = vehicle.fuel.mass_properties.fuel_mass_when_full
        metrics['theoretical_range'] = fuel_capacity / metrics['fuel_efficiency']  # km
    else:
        metrics['theoretical_range'] = 0.0
    
    # ------------------------------------------------------------------
    #   Drop Accuracy Estimation (Simplified)
    # ------------------------------------------------------------------
    
    # Estimate drop accuracy based on cruise speed and altitude
    drop_altitude = 55.0  # meters
    drop_speed = 12.0     # m/s
    wind_speed = 8.0      # m/s (maximum expected)
    
    # Simple ballistic calculation
    drop_time = np.sqrt(2 * drop_altitude / 9.81)  # seconds
    wind_drift = wind_speed * drop_time              # meters
    speed_drift = drop_speed * drop_time / 10        # simplified forward drift
    
    estimated_cep = np.sqrt(wind_drift**2 + speed_drift**2)  # Circular Error Probable
    metrics['estimated_drop_accuracy'] = estimated_cep       # meters
    metrics['drop_accuracy_target_met'] = estimated_cep < 5.0  # 5m target
    
    # ------------------------------------------------------------------
    #   Stall Speed and Safety Margins
    # ------------------------------------------------------------------
    
    # Calculate stall speed (simplified)
    wing_area = vehicle.reference_area
    max_cl = 1.4  # Typical maximum CL for UAV airfoil
    air_density = 1.225  # kg/m³ at sea level
    landing_weight = current_weight - total_fuel_consumed * 0.7  # Assume 70% fuel used
    
    stall_speed = np.sqrt((2 * landing_weight * 9.81) / (air_density * wing_area * max_cl))
    metrics['stall_speed'] = stall_speed  # m/s
    metrics['stall_margin'] = 12.0 - stall_speed  # 12 m/s target maximum
    metrics['stall_constraint_met'] = stall_speed < 12.0
    
    return metrics


def print_competition_results(metrics):
    """
    Prints competition-specific results summary
    """
    
    print(f"\n   Competition Performance Summary:")
    print(f"   ================================")
    
    # Mission performance
    print(f"   Mission Time:        {metrics['total_mission_time']:.1f} min")
    print(f"   Total Distance:      {metrics['total_distance']:.0f} m")
    print(f"   Fuel Consumed:       {metrics['total_fuel_consumed']:.2f} kg")
    print(f"   Average Speed:       {metrics['average_speed']:.1f} m/s")
    
    # Constraint validation
    print(f"\n   Constraint Validation:")
    time_status = "✓ PASS" if metrics['time_constraint_met'] else "✗ FAIL"
    print(f"   Time Limit (30 min): {time_status} (margin: {metrics['time_margin']:.1f} min)")
    
    weight_status = "✓ PASS" if metrics['weight_constraint_met'] else "✗ FAIL"
    print(f"   Weight Limit (25 kg): {weight_status} (margin: {metrics['weight_margin']:.1f} kg)")
    
    altitude_status = "✓ PASS" if metrics['altitude_constraint_met'] else "✗ FAIL"
    print(f"   Altitude (50-60m):   {altitude_status}")
    
    stall_status = "✓ PASS" if metrics['stall_constraint_met'] else "✗ FAIL"
    print(f"   Stall Speed (<12 m/s): {stall_status} ({metrics['stall_speed']:.1f} m/s)")
    
    # Performance metrics
    print(f"\n   Performance Metrics:")
    print(f"   Fuel Efficiency:     {metrics['fuel_efficiency']:.3f} kg/km")
    print(f"   Theoretical Range:   {metrics['theoretical_range']:.1f} km")
    
    accuracy_status = "✓ GOOD" if metrics['drop_accuracy_target_met'] else "⚠ REVIEW"
    print(f"   Est. Drop Accuracy:  {metrics['estimated_drop_accuracy']:.1f} m {accuracy_status}")


def validate_gtm140_integration(vehicle):
    """
    Validates GTM-140 engine integration and performance
    """
    
    validation_results = {}
    
    # Check if GTM-140 network exists
    if hasattr(vehicle, 'networks'):
        gtm140_found = False
        for network_tag in vehicle.networks:
            if 'gtm140' in network_tag.lower() or 'turbojet' in network_tag.lower():
                gtm140_found = True
                network = vehicle.networks[network_tag]
                
                # Validate engine specifications
                validation_results['engine_found'] = True
                validation_results['engine_length'] = network.engine_length
                validation_results['nacelle_diameter'] = network.nacelle_diameter
                
                break
        
        if not gtm140_found:
            validation_results['engine_found'] = False
            validation_results['error'] = "GTM-140 engine network not found"
    
    else:
        validation_results['engine_found'] = False
        validation_results['error'] = "No engine networks defined"
    
    return validation_results


#: def evaluate_mission()
