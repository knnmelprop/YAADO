# plotting.py
# 
# Created:  August 2025
# Modified: 

"""
Student Competition Aircraft Plotting and Post-Processing
"""

# ----------------------------------------------------------------------
#   Imports
# ----------------------------------------------------------------------

import SUAVE
import numpy as np
import matplotlib.pyplot as plt
from SUAVE.Core import Units
import os

# ----------------------------------------------------------------------
#   Post Process Results
# ----------------------------------------------------------------------

def post_process(vehicle, mission, results):
    """
    Post-processes and plots the mission results
    """
    
    # create results directory if it doesn't exist
    results_dir = "../results"
    plots_dir = "../plots"
    
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    if not os.path.exists(plots_dir):
        os.makedirs(plots_dir)
    
    # ------------------------------------------------------------------
    #   Print Results Summary
    # ------------------------------------------------------------------
    
    print_mission_summary(results)
    
    # ------------------------------------------------------------------
    #   Plot Results
    # ------------------------------------------------------------------
    
    plot_mission_profile(results, plots_dir)
    plot_aerodynamic_forces(results, plots_dir)
    plot_engine_performance(results, plots_dir)
    plot_fuel_consumption(results, plots_dir)
    
    # ------------------------------------------------------------------
    #   Save Results
    # ------------------------------------------------------------------
    
    save_results_to_file(vehicle, mission, results, results_dir)
    
    print("\\nPost-processing complete!")
    print(f"Results saved to: {results_dir}")
    print(f"Plots saved to: {plots_dir}")
    
    return


def print_mission_summary(results):
    """
    Prints a summary of the mission results
    """
    
    print("\\n" + "="*60)
    print("STUDENT COMPETITION TURBO AIRCRAFT - MISSION SUMMARY")
    print("="*60)
    
    # Extract key performance metrics
    segments = results.segments
    
    total_time = 0
    total_distance = 0
    total_fuel = 0
    
    for segment in segments:
        segment_time = segment.conditions.frames.inertial.time[-1, 0]
        segment_distance = np.sum(segment.conditions.frames.inertial.position_vector[:, 0])
        
        total_time += segment_time
        total_distance += segment_distance
        
        if hasattr(segment.conditions.weights, 'total_mass'):
            fuel_burned = segment.conditions.weights.total_mass[0, 0] - segment.conditions.weights.total_mass[-1, 0]
            total_fuel += fuel_burned
    
    print(f"Total Mission Time:     {total_time/60:.1f} minutes")
    print(f"Total Distance:         {total_distance/1000:.1f} km")
    print(f"Total Fuel Consumed:    {total_fuel:.1f} kg")
    
    # Find maximum values
    max_altitude = 0
    max_speed = 0
    
    for segment in segments:
        seg_max_alt = np.max(segment.conditions.freestream.altitude)
        seg_max_speed = np.max(segment.conditions.freestream.velocity)
        
        if seg_max_alt > max_altitude:
            max_altitude = seg_max_alt
        if seg_max_speed > max_speed:
            max_speed = seg_max_speed
    
    print(f"Maximum Altitude:       {max_altitude/1000:.1f} km")
    print(f"Maximum Speed:          {max_speed:.1f} m/s")
    print("="*60)


def plot_mission_profile(results, plots_dir):
    """
    Plots the mission altitude and speed profile
    """
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Collect data from all segments
    time_vec = []
    altitude_vec = []
    speed_vec = []
    
    cumulative_time = 0
    
    for segment in results.segments:
        time = segment.conditions.frames.inertial.time[:, 0] + cumulative_time
        altitude = segment.conditions.freestream.altitude[:, 0]
        speed = segment.conditions.freestream.velocity[:, 0]
        
        time_vec.extend(time)
        altitude_vec.extend(altitude)
        speed_vec.extend(speed)
        
        cumulative_time = time[-1]
    
    # Convert to numpy arrays
    time_vec = np.array(time_vec)
    altitude_vec = np.array(altitude_vec)
    speed_vec = np.array(speed_vec)
    
    # Plot altitude profile
    ax1.plot(time_vec/60, altitude_vec/1000, 'b-', linewidth=2)
    ax1.set_ylabel('Altitude (km)')
    ax1.set_title('Mission Profile')
    ax1.grid(True)
    
    # Plot speed profile
    ax2.plot(time_vec/60, speed_vec, 'r-', linewidth=2)
    ax2.set_xlabel('Time (minutes)')
    ax2.set_ylabel('Speed (m/s)')
    ax2.grid(True)
    
    plt.tight_layout()
    plt.savefig(f"{plots_dir}/mission_profile.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_aerodynamic_forces(results, plots_dir):
    """
    Plots lift, drag, and thrust forces
    """
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10))
    
    # Collect data from all segments
    time_vec = []
    lift_vec = []
    drag_vec = []
    thrust_vec = []
    
    cumulative_time = 0
    
    for segment in results.segments:
        time = segment.conditions.frames.inertial.time[:, 0] + cumulative_time
        
        if hasattr(segment.conditions.aerodynamics, 'lift_coefficient'):
            dynamic_pressure = segment.conditions.freestream.dynamic_pressure[:, 0]
            reference_area = 124.862  # m^2 (from vehicle definition)
            
            lift = segment.conditions.aerodynamics.lift_coefficient[:, 0] * dynamic_pressure * reference_area
            drag = segment.conditions.aerodynamics.drag_coefficient[:, 0] * dynamic_pressure * reference_area
        else:
            lift = np.zeros_like(time)
            drag = np.zeros_like(time)
            
        if hasattr(segment.conditions.propulsion, 'thrust'):
            thrust = segment.conditions.propulsion.thrust[:, 0]
        else:
            thrust = np.zeros_like(time)
        
        time_vec.extend(time)
        lift_vec.extend(lift)
        drag_vec.extend(drag)
        thrust_vec.extend(thrust)
        
        cumulative_time = time[-1]
    
    # Convert to numpy arrays
    time_vec = np.array(time_vec)
    lift_vec = np.array(lift_vec)
    drag_vec = np.array(drag_vec)
    thrust_vec = np.array(thrust_vec)
    
    # Plot forces
    ax1.plot(time_vec/60, lift_vec/1000, 'g-', linewidth=2)
    ax1.set_ylabel('Lift (kN)')
    ax1.set_title('Aerodynamic Forces')
    ax1.grid(True)
    
    ax2.plot(time_vec/60, drag_vec/1000, 'r-', linewidth=2)
    ax2.set_ylabel('Drag (kN)')
    ax2.grid(True)
    
    ax3.plot(time_vec/60, thrust_vec/1000, 'b-', linewidth=2)
    ax3.set_xlabel('Time (minutes)')
    ax3.set_ylabel('Thrust (kN)')
    ax3.grid(True)
    
    plt.tight_layout()
    plt.savefig(f"{plots_dir}/aerodynamic_forces.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_engine_performance(results, plots_dir):
    """
    Plots engine performance parameters
    """
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Collect data from all segments
    time_vec = []
    throttle_vec = []
    sfc_vec = []
    
    cumulative_time = 0
    
    for segment in results.segments:
        time = segment.conditions.frames.inertial.time[:, 0] + cumulative_time
        
        if hasattr(segment.conditions.propulsion, 'throttle'):
            throttle = segment.conditions.propulsion.throttle[:, 0]
        else:
            throttle = np.ones_like(time)
            
        if hasattr(segment.conditions.propulsion, 'specific_fuel_consumption'):
            sfc = segment.conditions.propulsion.specific_fuel_consumption[:, 0]
        else:
            sfc = np.zeros_like(time)
        
        time_vec.extend(time)
        throttle_vec.extend(throttle)
        sfc_vec.extend(sfc)
        
        cumulative_time = time[-1]
    
    # Convert to numpy arrays
    time_vec = np.array(time_vec)
    throttle_vec = np.array(throttle_vec)
    sfc_vec = np.array(sfc_vec)
    
    # Plot engine parameters
    ax1.plot(time_vec/60, throttle_vec*100, 'b-', linewidth=2)
    ax1.set_ylabel('Throttle (%)')
    ax1.set_title('Engine Performance')
    ax1.grid(True)
    
    ax2.plot(time_vec/60, sfc_vec*3600, 'r-', linewidth=2)
    ax2.set_xlabel('Time (minutes)')
    ax2.set_ylabel('SFC (kg/h/N)')
    ax2.grid(True)
    
    plt.tight_layout()
    plt.savefig(f"{plots_dir}/engine_performance.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_fuel_consumption(results, plots_dir):
    """
    Plots fuel consumption over time
    """
    
    fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    
    # Collect data from all segments
    time_vec = []
    fuel_flow_vec = []
    fuel_remaining_vec = []
    
    cumulative_time = 0
    initial_fuel = None
    
    for segment in results.segments:
        time = segment.conditions.frames.inertial.time[:, 0] + cumulative_time
        
        if hasattr(segment.conditions.weights, 'total_mass'):
            if initial_fuel is None:
                initial_fuel = segment.conditions.weights.total_mass[0, 0]
            
            fuel_remaining = segment.conditions.weights.total_mass[:, 0]
            
            # Calculate fuel flow rate
            if len(time) > 1:
                fuel_flow = -np.gradient(fuel_remaining, time)
            else:
                fuel_flow = np.zeros_like(time)
        else:
            fuel_remaining = np.zeros_like(time)
            fuel_flow = np.zeros_like(time)
        
        time_vec.extend(time)
        fuel_flow_vec.extend(fuel_flow)
        fuel_remaining_vec.extend(fuel_remaining)
        
        cumulative_time = time[-1]
    
    # Convert to numpy arrays
    time_vec = np.array(time_vec)
    fuel_flow_vec = np.array(fuel_flow_vec)
    fuel_remaining_vec = np.array(fuel_remaining_vec)
    
    if initial_fuel is not None:
        fuel_consumed = initial_fuel - fuel_remaining_vec
        
        ax.plot(time_vec/60, fuel_consumed, 'g-', linewidth=2, label='Fuel Consumed')
        ax.plot(time_vec/60, fuel_remaining_vec, 'b-', linewidth=2, label='Fuel Remaining')
        
        ax.set_xlabel('Time (minutes)')
        ax.set_ylabel('Fuel (kg)')
        ax.set_title('Fuel Consumption')
        ax.legend()
        ax.grid(True)
    
    plt.tight_layout()
    plt.savefig(f"{plots_dir}/fuel_consumption.png", dpi=300, bbox_inches='tight')
    plt.close()


def save_results_to_file(vehicle, mission, results, results_dir):
    """
    Saves results to a text file
    """
    
    with open(f"{results_dir}/mission_results.txt", 'w') as f:
        f.write("STUDENT COMPETITION TURBO AIRCRAFT - DETAILED RESULTS\\n")
        f.write("="*60 + "\\n\\n")
        
        f.write("VEHICLE CONFIGURATION:\\n")
        f.write("-"*30 + "\\n")
        f.write(f"Aircraft Tag: {vehicle.tag}\\n")
        f.write(f"Max Takeoff Weight: {vehicle.mass_properties.max_takeoff} kg\\n")
        f.write(f"Operating Empty Weight: {vehicle.mass_properties.operating_empty} kg\\n")
        f.write(f"Reference Area: {vehicle.reference_area} m²\\n")
        f.write(f"Number of Engines: {vehicle.networks.turbo_engine.number_of_engines}\\n")
        f.write("\\n")
        
        f.write("MISSION SEGMENTS:\\n")
        f.write("-"*30 + "\\n")
        
        for i, segment in enumerate(results.segments):
            f.write(f"Segment {i+1}: {segment.tag}\\n")
            
            if hasattr(segment.conditions.frames.inertial, 'time'):
                duration = segment.conditions.frames.inertial.time[-1, 0]
                f.write(f"  Duration: {duration/60:.2f} minutes\\n")
            
            if hasattr(segment.conditions.freestream, 'altitude'):
                start_alt = segment.conditions.freestream.altitude[0, 0]
                end_alt = segment.conditions.freestream.altitude[-1, 0]
                f.write(f"  Altitude: {start_alt/1000:.2f} - {end_alt/1000:.2f} km\\n")
            
            if hasattr(segment.conditions.freestream, 'velocity'):
                avg_speed = np.mean(segment.conditions.freestream.velocity[:, 0])
                f.write(f"  Average Speed: {avg_speed:.1f} m/s\\n")
            
            f.write("\\n")

#: def post_process()
