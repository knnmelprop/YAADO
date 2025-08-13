# competition_plots.py
# 
# Created:  August 2025
# Modified: 

"""
Droniada Sztafeta Competition Plotting and Visualization
Specialized plots for competition analysis and results
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
    Post-processes and creates competition-specific plots and reports
    """
    
    # create results and plots directories if they don't exist
    results_dir = os.path.join(os.getcwd(), "results")
    plots_dir = os.path.join(os.getcwd(), "plots")
    
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    if not os.path.exists(plots_dir):
        os.makedirs(plots_dir)
    
    # ------------------------------------------------------------------
    #   Competition Summary Report
    # ------------------------------------------------------------------
    
    print_detailed_mission_summary(results)
    
    # ------------------------------------------------------------------
    #   Create Competition-Specific Plots
    # ------------------------------------------------------------------
    
    plot_mission_profile(results, plots_dir)
    plot_competition_metrics(results, plots_dir)
    plot_aircraft_performance(results, plots_dir)
    plot_fuel_analysis(results, plots_dir)
    plot_drop_zones_analysis(results, plots_dir)
    
    # ------------------------------------------------------------------
    #   Save Detailed Results
    # ------------------------------------------------------------------
    
    save_competition_results(vehicle, mission, results, results_dir)
    
    print(f"\n   Post-processing complete!")
    print(f"   Results saved to: {results_dir}")
    print(f"   Plots saved to: {plots_dir}")
    
    return


def print_detailed_mission_summary(results):
    """
    Prints detailed mission performance summary
    """
    
    print(f"\n" + "="*60)
    print("DRONIADA SZTAFETA - DETAILED MISSION ANALYSIS")
    print("="*60)
    
    # Mission segment breakdown
    print(f"\nMISSION SEGMENT BREAKDOWN:")
    print(f"-" * 40)
    
    total_time = 0
    total_distance = 0
    total_fuel = 0
    
    for i, segment in enumerate(results.segments):
        print(f"\nSegment {i+1}: {segment.tag}")
        
        if hasattr(segment.conditions.frames.inertial, 'time'):
            duration = segment.conditions.frames.inertial.time[-1, 0]
            total_time += duration
            print(f"  Duration: {duration/60:.2f} minutes")
        
        if hasattr(segment.conditions.freestream, 'altitude'):
            start_alt = segment.conditions.freestream.altitude[0, 0]
            end_alt = segment.conditions.freestream.altitude[-1, 0]
            print(f"  Altitude: {start_alt:.1f} → {end_alt:.1f} m")
        
        if hasattr(segment.conditions.freestream, 'velocity'):
            avg_speed = np.mean(segment.conditions.freestream.velocity[:, 0])
            print(f"  Average Speed: {avg_speed:.1f} m/s")
        
        if hasattr(segment.conditions.weights, 'total_mass'):
            fuel_start = segment.conditions.weights.total_mass[0, 0]
            fuel_end = segment.conditions.weights.total_mass[-1, 0]
            fuel_burned = fuel_start - fuel_end
            total_fuel += fuel_burned
            print(f"  Fuel Burned: {fuel_burned:.3f} kg")
    
    # Overall mission summary
    print(f"\nOVERALL MISSION PERFORMANCE:")
    print(f"-" * 40)
    print(f"Total Mission Time:    {total_time/60:.1f} minutes")
    print(f"Total Distance:        {total_distance:.0f} m")
    print(f"Total Fuel Consumed:   {total_fuel:.2f} kg")
    
    # Competition metrics if available
    if hasattr(results, 'competition_metrics'):
        metrics = results.competition_metrics
        print(f"\nCOMPETITION VALIDATION:")
        print(f"-" * 40)
        print(f"Time Constraint:       {'PASS' if metrics['time_constraint_met'] else 'FAIL'}")
        print(f"Weight Constraint:     {'PASS' if metrics['weight_constraint_met'] else 'FAIL'}")
        print(f"Altitude Constraint:   {'PASS' if metrics['altitude_constraint_met'] else 'FAIL'}")
        print(f"Stall Speed:          {metrics['stall_speed']:.1f} m/s")
        print(f"Drop Accuracy Est.:   {metrics['estimated_drop_accuracy']:.1f} m")


def plot_mission_profile(results, plots_dir):
    """
    Plots detailed mission profile with competition phases highlighted
    """
    
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    
    # Collect data from all segments
    time_vec = []
    altitude_vec = []
    speed_vec = []
    throttle_vec = []
    segment_labels = []
    segment_times = []
    
    cumulative_time = 0
    
    for segment in results.segments:
        time = segment.conditions.frames.inertial.time[:, 0] + cumulative_time
        altitude = segment.conditions.freestream.altitude[:, 0]
        speed = segment.conditions.freestream.velocity[:, 0]
        
        # Try to get throttle setting
        if hasattr(segment.conditions.propulsion, 'throttle'):
            throttle = segment.conditions.propulsion.throttle[:, 0]
        else:
            throttle = np.ones_like(time) * 0.5  # Default assumption
        
        time_vec.extend(time)
        altitude_vec.extend(altitude)
        speed_vec.extend(speed)
        throttle_vec.extend(throttle)
        
        # Store segment information for annotations
        segment_labels.append(segment.tag)
        segment_times.append(cumulative_time/60)  # in minutes
        
        cumulative_time = time[-1]
    
    # Convert to numpy arrays
    time_vec = np.array(time_vec) / 60  # Convert to minutes
    altitude_vec = np.array(altitude_vec)
    speed_vec = np.array(speed_vec)
    throttle_vec = np.array(throttle_vec)
    
    # Plot altitude profile
    axes[0].plot(time_vec, altitude_vec, 'b-', linewidth=2)
    axes[0].axhline(y=50, color='g', linestyle='--', alpha=0.7, label='Min Altitude (50m)')
    axes[0].axhline(y=60, color='r', linestyle='--', alpha=0.7, label='Max Altitude (60m)')
    axes[0].fill_between(time_vec, 50, 60, alpha=0.2, color='green', label='Competition Zone')
    axes[0].set_ylabel('Altitude (m)')
    axes[0].set_title('Droniada Sztafeta Mission Profile')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    
    # Plot speed profile
    axes[1].plot(time_vec, speed_vec, 'r-', linewidth=2)
    axes[1].axhline(y=12, color='orange', linestyle='--', alpha=0.7, label='Drop Speed')
    axes[1].axhline(y=15, color='purple', linestyle='--', alpha=0.7, label='Cruise Speed')
    axes[1].set_ylabel('Airspeed (m/s)')
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()
    
    # Plot throttle setting
    axes[2].plot(time_vec, throttle_vec * 100, 'g-', linewidth=2)
    axes[2].set_xlabel('Time (minutes)')
    axes[2].set_ylabel('Throttle (%)')
    axes[2].grid(True, alpha=0.3)
    
    # Add vertical lines for mission phases
    for i, (label, start_time) in enumerate(zip(segment_labels, segment_times)):
        if 'drop' in label.lower():
            for ax in axes:
                ax.axvline(x=start_time, color='red', linestyle=':', alpha=0.8)
        elif 'circuit' in label.lower():
            for ax in axes:
                ax.axvline(x=start_time, color='blue', linestyle=':', alpha=0.6)
    
    # Add time limit indicator
    for ax in axes:
        ax.axvline(x=30, color='red', linestyle='-', alpha=0.8, linewidth=3, label='30 min limit')
    
    plt.tight_layout()
    plt.savefig(f"{plots_dir}/mission_profile.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_competition_metrics(results, plots_dir):
    """
    Creates a dashboard of competition-specific metrics
    """
    
    if not hasattr(results, 'competition_metrics'):
        print("   Warning: Competition metrics not available for plotting")
        return
    
    metrics = results.competition_metrics
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Droniada Sztafeta Competition Metrics Dashboard', fontsize=16, fontweight='bold')
    
    # 1. Constraint Compliance Chart
    constraints = ['Time\\n(30 min)', 'Weight\\n(25 kg)', 'Altitude\\n(50-60m)', 'Stall Speed\\n(<12 m/s)']
    compliance = [
        metrics['time_constraint_met'],
        metrics['weight_constraint_met'], 
        metrics['altitude_constraint_met'],
        metrics['stall_constraint_met']
    ]
    colors = ['green' if c else 'red' for c in compliance]
    
    axes[0,0].bar(constraints, [1 if c else 0 for c in compliance], color=colors, alpha=0.7)
    axes[0,0].set_ylabel('Compliance')
    axes[0,0].set_title('Competition Constraints')
    axes[0,0].set_ylim(0, 1.2)
    
    # Add text annotations
    values = [
        f"{metrics['total_mission_time']:.1f} min",
        f"{25 - metrics['weight_margin']:.1f} kg",
        "Check altitude",
        f"{metrics['stall_speed']:.1f} m/s"
    ]
    for i, (constraint, value, compliant) in enumerate(zip(constraints, values, compliance)):
        axes[0,0].text(i, 0.5, value, ha='center', va='center', fontweight='bold',
                      color='white' if compliant else 'white')
    
    # 2. Performance Efficiency
    categories = ['Fuel Eff.\\n(kg/km)', 'Avg Speed\\n(m/s)', 'Drop Acc.\\n(m)', 'Range\\n(km)']
    values = [
        metrics['fuel_efficiency'] * 1000,  # Scale for visibility
        metrics['average_speed'],
        metrics['estimated_drop_accuracy'],
        metrics['theoretical_range']
    ]
    
    bars = axes[0,1].bar(categories, values, color=['blue', 'orange', 'red', 'green'], alpha=0.7)
    axes[0,1].set_title('Performance Metrics')
    axes[0,1].set_ylabel('Value')
    
    # Add value labels on bars
    for bar, value, category in zip(bars, values, categories):
        height = bar.get_height()
        if 'Fuel Eff.' in category:
            label = f"{metrics['fuel_efficiency']:.3f}"
        else:
            label = f"{value:.1f}"
        axes[0,1].text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                      label, ha='center', va='bottom', fontweight='bold')
    
    # 3. Mission Timeline Breakdown
    segment_names = []
    segment_durations = []
    
    for segment in results.segments:
        if hasattr(segment.conditions.frames.inertial, 'time'):
            duration = segment.conditions.frames.inertial.time[-1, 0] / 60  # minutes
            segment_durations.append(duration)
            # Simplify segment names
            name = segment.tag.replace('_', ' ').title()
            if len(name) > 12:
                name = name[:12] + '...'
            segment_names.append(name)
    
    if segment_durations:
        axes[1,0].pie(segment_durations, labels=segment_names, autopct='%1.1f min',
                     startangle=90, textprops={'fontsize': 8})
        axes[1,0].set_title('Mission Time Breakdown')
    
    # 4. Safety Margins
    margin_categories = ['Time Margin', 'Weight Margin', 'Stall Margin']
    margin_values = [
        metrics['time_margin'],
        metrics['weight_margin'], 
        metrics['stall_margin']
    ]
    margin_colors = ['green' if v > 0 else 'red' for v in margin_values]
    
    bars = axes[1,1].bar(margin_categories, margin_values, color=margin_colors, alpha=0.7)
    axes[1,1].set_title('Safety Margins')
    axes[1,1].set_ylabel('Margin')
    axes[1,1].axhline(y=0, color='black', linestyle='-', linewidth=1)
    
    # Add value labels
    for bar, value in zip(bars, margin_values):
        height = bar.get_height()
        axes[1,1].text(bar.get_x() + bar.get_width()/2., height + (0.1 if height > 0 else -0.3),
                      f"{value:.1f}", ha='center', va='bottom' if height > 0 else 'top',
                      fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(f"{plots_dir}/competition_metrics.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_aircraft_performance(results, plots_dir):
    """
    Plots aircraft performance characteristics during mission
    """
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Aircraft Performance Analysis', fontsize=16, fontweight='bold')
    
    # Collect performance data
    time_vec = []
    lift_vec = []
    drag_vec = []
    thrust_vec = []
    cl_vec = []
    cd_vec = []
    
    cumulative_time = 0
    
    for segment in results.segments:
        time = segment.conditions.frames.inertial.time[:, 0] + cumulative_time
        
        # Aerodynamic coefficients
        if hasattr(segment.conditions.aerodynamics, 'lift_coefficient'):
            cl = segment.conditions.aerodynamics.lift_coefficient[:, 0]
            cd = segment.conditions.aerodynamics.drag_coefficient[:, 0]
            
            # Calculate forces
            q = segment.conditions.freestream.dynamic_pressure[:, 0]
            S = 0.79  # Wing area from vehicle definition
            
            lift = cl * q * S
            drag = cd * q * S
        else:
            lift = np.zeros_like(time)
            drag = np.zeros_like(time)
            cl = np.zeros_like(time)
            cd = np.zeros_like(time)
        
        if hasattr(segment.conditions.propulsion, 'thrust'):
            thrust = segment.conditions.propulsion.thrust[:, 0]
        else:
            thrust = np.zeros_like(time)
        
        time_vec.extend(time)
        lift_vec.extend(lift)
        drag_vec.extend(drag)
        thrust_vec.extend(thrust)
        cl_vec.extend(cl)
        cd_vec.extend(cd)
        
        cumulative_time = time[-1]
    
    # Convert to numpy arrays
    time_vec = np.array(time_vec) / 60  # minutes
    lift_vec = np.array(lift_vec)
    drag_vec = np.array(drag_vec)
    thrust_vec = np.array(thrust_vec)
    cl_vec = np.array(cl_vec)
    cd_vec = np.array(cd_vec)
    
    # Plot forces
    axes[0,0].plot(time_vec, lift_vec, 'g-', linewidth=2, label='Lift')
    axes[0,0].plot(time_vec, drag_vec, 'r-', linewidth=2, label='Drag')
    axes[0,0].plot(time_vec, thrust_vec, 'b-', linewidth=2, label='Thrust')
    axes[0,0].set_xlabel('Time (minutes)')
    axes[0,0].set_ylabel('Force (N)')
    axes[0,0].set_title('Aerodynamic Forces')
    axes[0,0].legend()
    axes[0,0].grid(True, alpha=0.3)
    
    # Plot coefficients
    axes[0,1].plot(time_vec, cl_vec, 'g-', linewidth=2, label='CL')
    axes[0,1].plot(time_vec, cd_vec, 'r-', linewidth=2, label='CD')
    axes[0,1].set_xlabel('Time (minutes)')
    axes[0,1].set_ylabel('Coefficient')
    axes[0,1].set_title('Aerodynamic Coefficients')
    axes[0,1].legend()
    axes[0,1].grid(True, alpha=0.3)
    
    # Drag polar (CL vs CD)
    if len(cl_vec) > 0 and len(cd_vec) > 0:
        axes[1,0].scatter(cd_vec, cl_vec, c=time_vec, cmap='viridis', alpha=0.6)
        axes[1,0].set_xlabel('CD')
        axes[1,0].set_ylabel('CL')
        axes[1,0].set_title('Drag Polar')
        axes[1,0].grid(True, alpha=0.3)
        
        # Add colorbar for time
        cbar = fig.colorbar(axes[1,0].collections[0], ax=axes[1,0])
        cbar.set_label('Time (minutes)')
    
    # L/D ratio
    ld_ratio = np.divide(cl_vec, cd_vec, out=np.zeros_like(cl_vec), where=cd_vec!=0)
    axes[1,1].plot(time_vec, ld_ratio, 'purple', linewidth=2)
    axes[1,1].set_xlabel('Time (minutes)')
    axes[1,1].set_ylabel('L/D Ratio')
    axes[1,1].set_title('Lift-to-Drag Ratio')
    axes[1,1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f"{plots_dir}/aircraft_performance.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_fuel_analysis(results, plots_dir):
    """
    Detailed fuel consumption analysis
    """
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('GTM-140 Fuel Analysis', fontsize=16, fontweight='bold')
    
    # Collect fuel data
    time_vec = []
    fuel_remaining_vec = []
    fuel_flow_vec = []
    
    cumulative_time = 0
    
    for segment in results.segments:
        time = segment.conditions.frames.inertial.time[:, 0] + cumulative_time
        
        if hasattr(segment.conditions.weights, 'total_mass'):
            fuel_mass = segment.conditions.weights.total_mass[:, 0]
            
            # Calculate fuel flow rate
            if len(time) > 1:
                fuel_flow = -np.gradient(fuel_mass, time) * 3600  # kg/hour
            else:
                fuel_flow = np.zeros_like(time)
        else:
            fuel_mass = np.zeros_like(time)
            fuel_flow = np.zeros_like(time)
        
        time_vec.extend(time)
        fuel_remaining_vec.extend(fuel_mass)
        fuel_flow_vec.extend(fuel_flow)
        
        cumulative_time = time[-1]
    
    # Convert to arrays
    time_vec = np.array(time_vec) / 60  # minutes
    fuel_remaining_vec = np.array(fuel_remaining_vec)
    fuel_flow_vec = np.array(fuel_flow_vec)
    
    # Calculate fuel consumed
    if len(fuel_remaining_vec) > 0:
        initial_fuel = fuel_remaining_vec[0]
        fuel_consumed_vec = initial_fuel - fuel_remaining_vec
        
        # Plot fuel consumption
        ax1.plot(time_vec, fuel_consumed_vec, 'r-', linewidth=2, label='Fuel Consumed')
        ax1.plot(time_vec, fuel_remaining_vec, 'b-', linewidth=2, label='Fuel Remaining')
        ax1.axhline(y=2.6, color='g', linestyle='--', alpha=0.7, label='Design Fuel (2.6 kg)')
        ax1.set_xlabel('Time (minutes)')
        ax1.set_ylabel('Fuel (kg)')
        ax1.set_title('Fuel Consumption')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot fuel flow rate
        # Smooth the fuel flow data to remove noise
        if len(fuel_flow_vec) > 5:
            window_size = min(5, len(fuel_flow_vec))
            fuel_flow_smooth = np.convolve(fuel_flow_vec, np.ones(window_size)/window_size, mode='same')
        else:
            fuel_flow_smooth = fuel_flow_vec
        
        ax2.plot(time_vec, fuel_flow_smooth, 'g-', linewidth=2)
        ax2.axhline(y=0.42*60, color='r', linestyle='--', alpha=0.7, label='GTM-140 Max (25.2 kg/h)')
        ax2.axhline(y=0.36*60, color='orange', linestyle='--', alpha=0.7, label='85% Power (21.6 kg/h)')
        ax2.set_xlabel('Time (minutes)')
        ax2.set_ylabel('Fuel Flow (kg/hour)')
        ax2.set_title('Fuel Flow Rate')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f"{plots_dir}/fuel_analysis.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_drop_zones_analysis(results, plots_dir):
    """
    Analysis of drop zones and accuracy estimation
    """
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('Beacon Drop Zone Analysis', fontsize=16, fontweight='bold')
    
    # Simulate drop zones based on mission segments
    drop_segments = []
    for segment in results.segments:
        if 'drop' in segment.tag.lower():
            drop_segments.append(segment)
    
    if drop_segments:
        # Extract conditions during drop sequences
        for i, segment in enumerate(drop_segments):
            if hasattr(segment.conditions.freestream, 'velocity'):
                speeds = segment.conditions.freestream.velocity[:, 0]
                altitudes = segment.conditions.freestream.altitude[:, 0]
                times = segment.conditions.frames.inertial.time[:, 0]
                
                # Estimate drop accuracy for different wind conditions
                wind_speeds = np.array([0, 2, 4, 6, 8])  # m/s
                drop_errors = []
                
                for wind in wind_speeds:
                    # Simple ballistic calculation
                    avg_altitude = np.mean(altitudes)
                    avg_speed = np.mean(speeds)
                    
                    drop_time = np.sqrt(2 * avg_altitude / 9.81)
                    wind_drift = wind * drop_time
                    speed_drift = avg_speed * drop_time / 10  # simplified
                    
                    total_error = np.sqrt(wind_drift**2 + speed_drift**2)
                    drop_errors.append(total_error)
                
                # Plot drop accuracy vs wind speed
                ax1.plot(wind_speeds, drop_errors, 'o-', linewidth=2, 
                        label=f'Drop Zone {i+1}', markersize=6)
        
        ax1.axhline(y=5, color='r', linestyle='--', alpha=0.7, label='5m Target')
        ax1.axhline(y=2, color='g', linestyle='--', alpha=0.7, label='2m Goal')
        ax1.set_xlabel('Wind Speed (m/s)')
        ax1.set_ylabel('Estimated Drop Error (m)')
        ax1.set_title('Drop Accuracy vs Wind Speed')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Create a visual representation of drop pattern
        # Simulate 4 beacon drops in a pattern
        target_positions = np.array([[0, 0], [10, 0], [20, 0], [30, 0]])  # 10m spacing
        
        # Add wind effects (8 m/s worst case)
        wind_effect = 2.0  # meters drift
        actual_positions = target_positions + np.random.normal(0, wind_effect, target_positions.shape)
        
        # Plot drop pattern
        ax2.scatter(target_positions[:, 0], target_positions[:, 1], 
                   c='green', s=100, marker='s', label='Target Positions', alpha=0.8)
        ax2.scatter(actual_positions[:, 0], actual_positions[:, 1], 
                   c='red', s=100, marker='o', label='Estimated Drops', alpha=0.8)
        
        # Draw error circles
        for i, (target, actual) in enumerate(zip(target_positions, actual_positions)):
            circle = plt.Circle(target, 5, fill=False, color='orange', linestyle='--', alpha=0.5)
            ax2.add_patch(circle)
            circle = plt.Circle(target, 2, fill=False, color='green', linestyle='--', alpha=0.5)
            ax2.add_patch(circle)
            
            # Connect target to actual
            ax2.plot([target[0], actual[0]], [target[1], actual[1]], 
                    'k--', alpha=0.5, linewidth=1)
        
        ax2.set_xlabel('Distance (m)')
        ax2.set_ylabel('Cross-track (m)')
        ax2.set_title('Beacon Drop Pattern (8 m/s wind)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        ax2.set_aspect('equal')
    
    else:
        # No drop segments found
        ax1.text(0.5, 0.5, 'No drop segments found\\nin mission', 
                ha='center', va='center', transform=ax1.transAxes, fontsize=12)
        ax2.text(0.5, 0.5, 'No drop analysis\\navailable', 
                ha='center', va='center', transform=ax2.transAxes, fontsize=12)
    
    plt.tight_layout()
    plt.savefig(f"{plots_dir}/drop_zones_analysis.png", dpi=300, bbox_inches='tight')
    plt.close()


def save_competition_results(vehicle, mission, results, results_dir):
    """
    Saves detailed competition results to files
    """
    
    # Main results file
    with open(f"{results_dir}/droniada_results.txt", 'w') as f:
        f.write("DRONIADA SZTAFETA COMPETITION ANALYSIS RESULTS\\n")
        f.write("="*60 + "\\n\\n")
        
        # Vehicle configuration
        f.write("VEHICLE CONFIGURATION:\\n")
        f.write("-"*30 + "\\n")
        f.write(f"Aircraft: {vehicle.tag}\\n")
        f.write(f"MTOW: {vehicle.mass_properties.max_takeoff:.1f} kg\\n")
        f.write(f"Empty Weight: {vehicle.mass_properties.operating_empty:.1f} kg\\n")
        f.write(f"Wing Area: {vehicle.reference_area:.2f} m²\\n")
        f.write(f"Wing Span: {vehicle.wings.main_wing.spans.projected:.2f} m\\n")
        f.write(f"Aspect Ratio: {vehicle.wings.main_wing.aspect_ratio:.1f}\\n")
        f.write(f"Engine: GTM-140 Turbojet\\n\\n")
        
        # Mission summary
        f.write("MISSION SUMMARY:\\n")
        f.write("-"*30 + "\\n")
        f.write(f"Mission: {mission.tag}\\n")
        f.write(f"Segments: {len(mission.segments)}\\n")
        
        # Competition metrics
        if hasattr(results, 'competition_metrics'):
            metrics = results.competition_metrics
            f.write("\\nCOMPETITION METRICS:\\n")
            f.write("-"*30 + "\\n")
            f.write(f"Mission Time: {metrics['total_mission_time']:.1f} minutes\\n")
            f.write(f"Total Distance: {metrics['total_distance']:.0f} m\\n")
            f.write(f"Fuel Consumed: {metrics['total_fuel_consumed']:.2f} kg\\n")
            f.write(f"Average Speed: {metrics['average_speed']:.1f} m/s\\n")
            f.write(f"Stall Speed: {metrics['stall_speed']:.1f} m/s\\n")
            f.write(f"Drop Accuracy: {metrics['estimated_drop_accuracy']:.1f} m\\n")
            f.write(f"\\nCONSTRAINT VALIDATION:\\n")
            f.write(f"Time (30 min): {'PASS' if metrics['time_constraint_met'] else 'FAIL'}\\n")
            f.write(f"Weight (25 kg): {'PASS' if metrics['weight_constraint_met'] else 'FAIL'}\\n")
            f.write(f"Altitude (50-60m): {'PASS' if metrics['altitude_constraint_met'] else 'FAIL'}\\n")
            f.write(f"Stall Speed (<12 m/s): {'PASS' if metrics['stall_constraint_met'] else 'FAIL'}\\n")
    
    print(f"   Competition results saved to: {results_dir}/droniada_results.txt")


#: def post_process()
