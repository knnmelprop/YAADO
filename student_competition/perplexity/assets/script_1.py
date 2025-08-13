# Create comprehensive SUAVE-optimizable parameter set for Droniada competition
print("=== SUAVE OPTIMIZATION PARAMETER SET FOR DRONIADA SZTAFETA ===\n")

# Create structured parameter sets for different configuration options
configurations = {
    'Configuration A - Fixed Wing': {
        'type': 'Fixed Wing with GTM-140',
        'description': 'Conventional fixed-wing with jet propulsion for high efficiency',
        'parameters': {
            # Geometry Parameters (Primary Variables for SUAVE Optimization)
            'wing_area': {'value': 0.79, 'min': 0.6, 'max': 1.2, 'unit': 'm²'},
            'wing_span': {'value': 2.51, 'min': 2.0, 'max': 3.5, 'unit': 'm'},
            'aspect_ratio': {'value': 8.0, 'min': 6.0, 'max': 12.0, 'unit': '-'},
            'wing_sweep': {'value': 0, 'min': -5, 'max': 15, 'unit': 'deg'},
            'wing_taper_ratio': {'value': 0.7, 'min': 0.4, 'max': 1.0, 'unit': '-'},
            'wing_twist': {'value': -2, 'min': -5, 'max': 2, 'unit': 'deg'},
            'wing_dihedral': {'value': 3, 'min': 0, 'max': 8, 'unit': 'deg'},
            
            # Fuselage Parameters
            'fuselage_length': {'value': 1.8, 'min': 1.5, 'max': 2.5, 'unit': 'm'},
            'fuselage_diameter': {'value': 0.25, 'min': 0.20, 'max': 0.35, 'unit': 'm'},
            'fuselage_fineness_ratio': {'value': 7.2, 'min': 5.0, 'max': 10.0, 'unit': '-'},
            
            # Empennage Parameters
            'horizontal_tail_area': {'value': 0.15, 'min': 0.10, 'max': 0.25, 'unit': 'm²'},
            'vertical_tail_area': {'value': 0.12, 'min': 0.08, 'max': 0.20, 'unit': 'm²'},
            'horizontal_tail_arm': {'value': 1.2, 'min': 1.0, 'max': 1.6, 'unit': 'm'},
            'vertical_tail_arm': {'value': 1.2, 'min': 1.0, 'max': 1.6, 'unit': 'm'},
            
            # Propulsion Parameters
            'engine_thrust_max': {'value': 140, 'min': 100, 'max': 140, 'unit': 'N'},
            'engine_weight': {'value': 1.75, 'min': 1.75, 'max': 1.75, 'unit': 'kg'},
            'engine_length': {'value': 0.315, 'min': 0.315, 'max': 0.315, 'unit': 'm'},
            'engine_diameter': {'value': 0.115, 'min': 0.115, 'max': 0.115, 'unit': 'm'},
            'inlet_area_ratio': {'value': 1.0, 'min': 0.8, 'max': 1.3, 'unit': '-'},
            'nozzle_area_ratio': {'value': 1.0, 'min': 0.8, 'max': 1.2, 'unit': '-'},
        }
    },
    
    'Configuration B - VTOL Hybrid': {
        'type': 'Fixed Wing + Multirotor VTOL',
        'description': 'Hybrid configuration with electric vertical lift + GTM-140 forward propulsion',
        'parameters': {
            # Wing Parameters (smaller for VTOL capability)
            'wing_area': {'value': 0.65, 'min': 0.5, 'max': 1.0, 'unit': 'm²'},
            'wing_span': {'value': 2.2, 'min': 1.8, 'max': 2.8, 'unit': 'm'},
            'aspect_ratio': {'value': 7.5, 'min': 6.0, 'max': 9.0, 'unit': '-'},
            'wing_sweep': {'value': 5, 'min': 0, 'max': 20, 'unit': 'deg'},
            
            # VTOL Parameters
            'vtol_rotor_count': {'value': 4, 'min': 4, 'max': 8, 'unit': '-'},
            'vtol_rotor_diameter': {'value': 0.4, 'min': 0.3, 'max': 0.6, 'unit': 'm'},
            'vtol_rotor_disk_loading': {'value': 150, 'min': 100, 'max': 250, 'unit': 'N/m²'},
            'vtol_motor_power': {'value': 2000, 'min': 1500, 'max': 3000, 'unit': 'W'},
            'vtol_battery_capacity': {'value': 5000, 'min': 3000, 'max': 8000, 'unit': 'mAh'},
            
            # Fuselage (larger for dual propulsion)
            'fuselage_length': {'value': 1.9, 'min': 1.6, 'max': 2.4, 'unit': 'm'},
            'fuselage_diameter': {'value': 0.28, 'min': 0.22, 'max': 0.38, 'unit': 'm'},
        }
    },
    
    'Configuration C - Pure Electric': {
        'type': 'Electric Fixed Wing',
        'description': 'All-electric configuration for maximum precision and reliability',
        'parameters': {
            # Optimized for electric propulsion
            'wing_area': {'value': 1.0, 'min': 0.8, 'max': 1.4, 'unit': 'm²'},
            'wing_span': {'value': 3.2, 'min': 2.5, 'max': 4.0, 'unit': 'm'},
            'aspect_ratio': {'value': 10.0, 'min': 8.0, 'max': 14.0, 'unit': '-'},
            
            # Electric Propulsion
            'motor_power': {'value': 3000, 'min': 2000, 'max': 5000, 'unit': 'W'},
            'propeller_diameter': {'value': 0.5, 'min': 0.4, 'max': 0.7, 'unit': 'm'},
            'battery_capacity': {'value': 8000, 'min': 6000, 'max': 12000, 'unit': 'mAh'},
            'battery_voltage': {'value': 22.2, 'min': 14.8, 'max': 44.4, 'unit': 'V'},
        }
    }
}

# Mission-specific parameters for optimization
mission_parameters = {
    'Mission Profile': {
        # Flight segments for SUAVE mission analysis
        'takeoff_segment': {
            'altitude_start': 0,
            'altitude_end': 55,
            'climb_rate': 3.0,
            'airspeed': 18,
            'unit': 'm, m, m/s, m/s'
        },
        'cruise_segment_1': {
            'distance': 600,
            'altitude': 55,
            'airspeed': 15,
            'unit': 'm, m, m/s'
        },
        'drop_segment_1': {
            'drop_points': 2,
            'loiter_radius': 50,
            'drop_altitude': 55,
            'drop_speed': 12,
            'unit': '-, m, m, m/s'
        },
        'cruise_segment_2': {
            'distance': 600,
            'altitude': 55,
            'airspeed': 15,
            'unit': 'm, m, m/s'
        },
        'drop_segment_2': {
            'drop_points': 2,
            'loiter_radius': 50,
            'drop_altitude': 55,
            'drop_speed': 12,
            'unit': '-, m, m, m/s'
        },
        'landing_segment': {
            'altitude_start': 55,
            'altitude_end': 0,
            'descent_rate': -2.5,
            'airspeed': 16,
            'unit': 'm, m, m/s, m/s'
        }
    },
    
    'Environmental Conditions': {
        'wind_speed_max': 8,  # m/s
        'temperature': 15,    # °C
        'pressure': 101325,   # Pa
        'humidity': 60,       # %
        'night_operation': True,
        'rain_resistance': True,  # 15 min light rain
    },
    
    'Performance Requirements': {
        'cruise_speed_target': 15,     # m/s
        'stall_speed_max': 12,         # m/s
        'climb_rate_min': 3,           # m/s
        'endurance_min': 30,           # minutes
        'payload_capacity': 1.0,       # kg
        'drop_accuracy_target': 2,     # meters from target
        'autonomous_operation': True,
        'rtl_capability': True,
    }
}

# Airfoil selection for GTM-140 analysis
airfoil_options = {
    'Primary Options': {
        'GTM-140': {
            'description': 'GTM-140 specific airfoil for jet integration',
            'thickness_ratio': 0.12,
            'camber': 0.02,
            'optimization_focus': 'jet_integration',
            'cl_design': 0.4,
            'cd_design': 0.008,
        },
        'NACA_4412': {
            'description': 'Proven airfoil for small aircraft',
            'thickness_ratio': 0.12,
            'camber': 0.02,
            'optimization_focus': 'low_speed_performance',
            'cl_design': 0.6,
            'cd_design': 0.012,
        },
        'Eppler_423': {
            'description': 'Low Reynolds number optimized',
            'thickness_ratio': 0.125,
            'camber': 0.025,
            'optimization_focus': 'low_reynolds',
            'cl_design': 0.8,
            'cd_design': 0.010,
        }
    }
}

# Weight breakdown for optimization
weight_components = {
    'Fixed_Components': {
        'GTM_140_engine': 1.75,      # kg
        'avionics_flight_control': 1.0,  # kg
        'beacon_drop_system': 0.7,   # kg
        'fuel_system': 0.3,          # kg
        'electrical_system': 0.4,    # kg
    },
    
    'Variable_Components': {
        # These will be optimized by SUAVE
        'wing_structure': {'base': 1.2, 'factor': 2.5, 'unit': 'kg per m² wing area'},
        'fuselage_structure': {'base': 1.8, 'factor': 3.2, 'unit': 'kg per m fuselage length'},
        'empennage_structure': {'base': 0.3, 'factor': 1.8, 'unit': 'kg per m² tail area'},
        'landing_gear': {'base': 0.8, 'factor': 0.05, 'unit': 'kg + factor*MTOW'},
        'fuel_weight': {'base': 2.6, 'factor': 1.3, 'unit': 'kg with reserve factor'},
        'payload': {'base': 1.0, 'factor': 1.0, 'unit': 'kg fixed payload'},
    }
}

# Print comprehensive parameter sets
print("RECOMMENDED CONFIGURATION: Configuration A - Fixed Wing with GTM-140")
print("\nPrimary Optimization Variables for SUAVE:")
print("-" * 50)

config_a = configurations['Configuration A - Fixed Wing']
for category, params in [('Geometry', ['wing_area', 'wing_span', 'aspect_ratio', 'wing_sweep']),
                        ('Airfoil', ['wing_taper_ratio', 'wing_twist', 'wing_dihedral']),
                        ('Fuselage', ['fuselage_length', 'fuselage_diameter']),
                        ('Empennage', ['horizontal_tail_area', 'vertical_tail_area'])]:
    print(f"\n{category} Parameters:")
    for param in params:
        if param in config_a['parameters']:
            p = config_a['parameters'][param]
            print(f"  {param}: {p['value']} {p['unit']} (range: {p['min']}-{p['max']})")

print(f"\nMission Profile Optimization:")
print("-" * 30)
for segment, data in mission_parameters['Mission Profile'].items():
    print(f"{segment}:")
    for key, value in data.items():
        if key != 'unit':
            print(f"  {key}: {value}")

print(f"\nWeight Budget Analysis:")
print("-" * 25)
fixed_weight = sum(weight_components['Fixed_Components'].values())
print(f"Fixed components total: {fixed_weight:.1f}kg")
print(f"Variable components: optimized by SUAVE")
print(f"Target total weight: <12kg (margin: 13kg under 25kg limit)")

print(f"\nSUAVE Integration Strategy:")
print("-" * 30)
print("1. Use SUAVE's multi-objective optimization:")
print("   - Minimize: Total mission time + fuel consumption")
print("   - Maximize: Drop accuracy + flight stability")
print("   - Constraints: Weight < 25kg, Stall speed < 12 m/s")

print("\n2. GTM-140 specific modeling:")
print("   - Custom engine deck with thrust/fuel consumption curves")
print("   - Inlet design optimization for jet integration")
print("   - Thermal management considerations")

print("\n3. Mission-specific optimization:")
print("   - Precision trajectory optimization for drop accuracy")
print("   - Wind disturbance rejection analysis")
print("   - Night flight stability margins")

print("\n4. Configuration trade studies:")
print("   - Wing aspect ratio vs. gust response")
print("   - Fuel capacity vs. structure weight")
print("   - Control authority vs. efficiency")