# Let's calculate optimal aircraft parameters for Droniada Sztafeta competition
import numpy as np
import pandas as pd

# Competition requirements analysis
print("=== DRONIADA SZTAFETA COMPETITION ANALYSIS ===\n")

# Mission requirements
mission_time_max = 30 * 60  # 30 minutes in seconds
route_distance = 600  # meters per round
total_rounds = 2
total_distance = route_distance * total_rounds
beacon_count = 4
beacon_weight = 0.25  # kg each, max allowed
total_payload = beacon_count * beacon_weight

print(f"Mission Requirements:")
print(f"- Total distance: {total_distance}m ({route_distance}m x {total_rounds} rounds)")
print(f"- Mission time limit: {mission_time_max/60} minutes")
print(f"- Total payload (beacons): {total_payload}kg")
print(f"- Flight altitude: 50-60m AGL")
print(f"- Wind conditions: up to 8 m/s")
print(f"- Night operation with autonomous precision dropping")

# GTM-140 engine analysis
gtm140_thrust_min = 8  # N
gtm140_thrust_max = 140  # N
gtm140_weight = 1.75  # kg
gtm140_fuel_consumption_max = 500  # g/min
gtm140_length = 0.315  # m
gtm140_diameter = 0.115  # m

print(f"\nGTM-140 Engine Specifications:")
print(f"- Thrust range: {gtm140_thrust_min}-{gtm140_thrust_max}N")
print(f"- Engine weight: {gtm140_weight}kg")
print(f"- Max fuel consumption: {gtm140_fuel_consumption_max}g/min")
print(f"- Dimensions: {gtm140_length}m x {gtm140_diameter}m")

# Calculate optimal aircraft parameters
print(f"\n=== OPTIMAL AIRCRAFT PARAMETER CALCULATIONS ===\n")

# Mission profile analysis
cruise_speed_target = 15  # m/s (conservative for precision and stability)
climb_rate_target = 3  # m/s
cruise_altitude = 55  # m AGL (middle of 50-60m range)
loiter_time = 5 * 60  # 5 minutes for mission setup and beacon drops

# Calculate mission timeline
climb_time = cruise_altitude / climb_rate_target
cruise_time = total_distance / cruise_speed_target
total_flight_time = climb_time + cruise_time + loiter_time

print(f"Mission Timeline Analysis:")
print(f"- Climb time to {cruise_altitude}m: {climb_time:.1f}s")
print(f"- Cruise time for {total_distance}m at {cruise_speed_target}m/s: {cruise_time:.1f}s")
print(f"- Loiter time for drops and maneuvering: {loiter_time}s")
print(f"- Total estimated flight time: {total_flight_time:.1f}s ({total_flight_time/60:.1f} minutes)")
print(f"- Safety margin: {(mission_time_max - total_flight_time)/60:.1f} minutes")

# Fuel requirements calculation
flight_time_minutes = total_flight_time / 60
# Use conservative 60% power setting for most of flight
avg_fuel_consumption = gtm140_fuel_consumption_max * 0.6  # g/min
fuel_required = flight_time_minutes * avg_fuel_consumption / 1000  # kg
fuel_with_reserve = fuel_required * 1.3  # 30% reserve

print(f"\nFuel Analysis:")
print(f"- Flight time: {flight_time_minutes:.1f} minutes")
print(f"- Average fuel consumption (60% power): {avg_fuel_consumption:.1f}g/min")
print(f"- Fuel required: {fuel_required:.2f}kg")
print(f"- Fuel with 30% reserve: {fuel_with_reserve:.2f}kg")

# Weight and balance calculation
empty_weight_components = {
    'GTM-140 Engine': gtm140_weight,
    'Airframe Structure': 3.5,  # kg - carbon fiber/aluminum construction
    'Avionics & Flight Control': 1.0,  # kg - autopilot, GPS, sensors
    'Landing Gear': 0.8,  # kg - retractable gear
    'Wiring & Misc': 0.5,  # kg
    'Beacon Drop System': 0.7,  # kg - servo actuators and release mechanism
}

empty_weight = sum(empty_weight_components.values())
fuel_weight = fuel_with_reserve
payload_weight = total_payload
total_weight = empty_weight + fuel_weight + payload_weight

print(f"\nWeight Breakdown:")
for component, weight in empty_weight_components.items():
    print(f"- {component}: {weight:.1f}kg")
print(f"- Empty Weight: {empty_weight:.1f}kg")
print(f"- Fuel Weight: {fuel_weight:.2f}kg")
print(f"- Payload Weight: {payload_weight:.1f}kg")
print(f"- Total Weight: {total_weight:.1f}kg")
print(f"- Weight margin under 25kg limit: {25 - total_weight:.1f}kg")

# Performance requirements
wing_loading_target = 15  # kg/m² (low for good low-speed handling)
thrust_to_weight_min = 0.4  # minimum for adequate performance
stall_speed_max = 12  # m/s (for safe autonomous operation)

wing_area = total_weight / wing_loading_target
thrust_required = total_weight * 9.81 * thrust_to_weight_min  # N

print(f"\nPerformance Analysis:")
print(f"- Target wing loading: {wing_loading_target}kg/m²")
print(f"- Required wing area: {wing_area:.2f}m²")
print(f"- Minimum thrust required: {thrust_required:.1f}N")
print(f"- GTM-140 max thrust: {gtm140_thrust_max}N")
print(f"- Thrust margin: {gtm140_thrust_max - thrust_required:.1f}N")

# Optimal wing configuration
aspect_ratio = 8  # High AR for efficiency but not too high for stability
wing_span = np.sqrt(wing_area * aspect_ratio)
wing_chord = wing_area / wing_span

print(f"\nWing Configuration:")
print(f"- Wing area: {wing_area:.2f}m²")
print(f"- Aspect ratio: {aspect_ratio}")
print(f"- Wing span: {wing_span:.2f}m")
print(f"- Mean chord: {wing_chord:.2f}m")

# GTM-140 specific calculations
# Calculate optimal airfoil for GTM-140 integration
gtm140_inlet_area = np.pi * (gtm140_diameter/2)**2
gtm140_thrust_cruise = thrust_required * 1.2  # 20% margin for cruise

print(f"\nGTM-140 Integration:")
print(f"- Engine inlet area: {gtm140_inlet_area*10000:.1f}cm²")
print(f"- Cruise thrust setting: {gtm140_thrust_cruise:.1f}N ({gtm140_thrust_cruise/gtm140_thrust_max*100:.1f}% of max)")
print(f"- Engine placement: Centerline fuselage, minimal intake losses")