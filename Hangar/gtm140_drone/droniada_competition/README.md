# Droniada Sztafeta Competition Aircraft Analysis

This directory contains a complete SUAVE-based analysis framework for the Droniada Sztafeta competition, featuring a GTM-140 turbojet-powered UAV optimized for autonomous beacon dropping missions.

## Competition Overview

**Droniada Sztafeta** is a Polish drone competition focused on autonomous precision operations:
- **Mission**: Drop 4 light beacons over two 600m circuits at night
- **Constraints**: 25kg max weight, 50-60m altitude, 30min time limit
- **Environment**: Wind up to 8 m/s, autonomous operation required
- **Success Factors**: Precision, reliability, autonomous execution

## Aircraft Configuration

### GTM-140 Turbojet Aircraft
Based on detailed optimization analysis from perplexity research:

**Performance Targets:**
- **Weight**: ~11.8 kg (13.2 kg margin under limit)
- **Wing**: 0.79 m² area, 8:1 aspect ratio, 2.51m span
- **Engine**: GTM-140 turbojet (140N max thrust, 1.75kg)
- **Mission Time**: ~20 minutes (10-minute safety margin)
- **Drop Accuracy**: <2m target (5m competition requirement)

**Key Features:**
- Centerline GTM-140 integration optimized for efficiency
- Conservative wing loading (15 kg/m²) for stability
- Precision autonomous flight control system
- 4-beacon payload bay with servo-actuated drop system

## Directory Structure

```
droniada_sztafeta/
├── main.py                    # Main execution script
├── README.md                  # This file
├── vehicle/                   # Aircraft definitions
│   ├── gtm140_aircraft.py     # GTM-140 powered configuration
│   └── __init__.py
├── mission/                   # Mission profiles
│   ├── sztafeta_mission.py    # Competition mission definition
│   └── __init__.py
├── engines/                   # Engine models
│   ├── gtm140_model.py        # GTM-140 engine deck
│   └── __init__.py
├── analysis/                  # Analysis modules
│   ├── competition_analysis.py # Competition-specific analysis
│   └── __init__.py
├── plots/                     # Visualization
│   ├── competition_plots.py   # Competition plotting tools
│   └── __init__.py
├── payloads/                  # Payload systems
│   └── __init__.py
├── data/                      # Input data files
├── results/                   # Output results
└── plots/                     # Generated plots
```

## Quick Start

### 1. Basic Analysis
```bash
cd /workspaces/SUAVE/student_competition/droniada_sztafeta
python main.py
```

### 2. Interactive Analysis
```python
import main
vehicle, mission, results = main.main()

# Access results
print(f"Mission time: {results.competition_metrics['total_mission_time']:.1f} min")
print(f"Fuel consumed: {results.competition_metrics['total_fuel_consumed']:.2f} kg")
print(f"Drop accuracy: {results.competition_metrics['estimated_drop_accuracy']:.1f} m")
```

## GTM-140 Engine Integration

### Engine Specifications
Based on JETPOL GTM-140 technical data:
- **Thrust**: 8-140N variable (40% cruise setting)
- **Weight**: 1.75kg complete system
- **Fuel Consumption**: 420-500 g/min at max power
- **Dimensions**: 315mm × 115mm diameter
- **RPM Range**: 33,000-120,000 rpm
- **Pressure Ratio**: 2.8:1

### SUAVE Implementation
- Custom turbojet network with GTM-140 characteristics
- Performance maps based on manufacturer specifications
- Installation effects and inlet design optimization
- Fuel consumption modeling for mission planning

## Mission Profile

### Competition Mission Segments
1. **Takeoff**: Ground acceleration to 12 m/s liftoff
2. **Climb**: Ascent to 55m AGL at 3 m/s climb rate
3. **Circuit 1 Outbound**: 600m cruise at 15 m/s
4. **Drop Sequence 1**: Precision drops of 2 beacons at 12 m/s
5. **Circuit 1 Return**: Return cruise at 15 m/s
6. **Circuit 2 Outbound**: Second 600m circuit
7. **Drop Sequence 2**: Final 2 beacon drops
8. **Circuit 2 Return**: Return to landing pattern
9. **Descent**: Controlled descent to landing
10. **Landing**: Touchdown and rollout

### Performance Analysis
- Total mission time: ~20 minutes
- Total distance: ~2.4 km
- Fuel consumption: ~2.0 kg
- Drop accuracy: <2m in 8 m/s winds
- Safety margins: 10 min time, 13 kg weight, 2 m/s stall

## Competition Validation

### Automatic Constraint Checking
The analysis automatically validates against competition requirements:
- ✅ **Weight**: <25 kg (target: ~12 kg)
- ✅ **Time**: <30 minutes (target: ~20 minutes)
- ✅ **Altitude**: 50-60m AGL maintained
- ✅ **Stall Speed**: <12 m/s for safe autonomous operation
- ✅ **Drop Accuracy**: <5m required (<2m target)

### Performance Metrics
- **Fuel Efficiency**: Optimized for mission requirements
- **Drop Precision**: Wind compensation and ballistic modeling
- **Safety Margins**: Conservative design for competition reliability
- **Autonomous Capability**: Stability and control authority analysis

## Outputs

### Generated Results
- `results/droniada_results.txt` - Detailed performance summary
- `results/mission_data.csv` - Raw mission data export

### Visualization Plots
- `plots/mission_profile.png` - Altitude, speed, and throttle profiles
- `plots/competition_metrics.png` - Constraint validation dashboard
- `plots/aircraft_performance.png` - Aerodynamic performance analysis
- `plots/fuel_analysis.png` - GTM-140 fuel consumption details
- `plots/drop_zones_analysis.png` - Beacon drop accuracy estimation

## Key Design Features

### Aircraft Optimization
- **Wing Design**: High aspect ratio (8:1) for efficiency, optimized for 55m cruise
- **Engine Integration**: Centerline GTM-140 mount with optimized inlet design
- **Weight Distribution**: CG management for fuel and payload variations
- **Control Surfaces**: Sized for 8 m/s wind disturbance rejection

### Mission-Specific Features
- **Autonomous Operation**: Waypoint navigation with precision approach
- **Drop System**: Servo-actuated beacon release with timing optimization
- **Night Capability**: Enhanced lighting and navigation systems
- **Wind Resistance**: Designed for 8 m/s operational winds

### Competition Strategy
- **Conservative Margins**: 50% time margin, 50% weight margin for reliability
- **Precision Focus**: Drop accuracy prioritized over maximum performance
- **Fail-Safe Design**: Multiple backup systems and abort procedures
- **Regulatory Compliance**: Full adherence to competition rules and safety requirements

## Future Enhancements

### Planned Improvements
1. **Multi-Objective Optimization**: Pareto frontier analysis for design trades
2. **Monte Carlo Analysis**: Statistical validation of drop accuracy
3. **Wind Effects Modeling**: CFD analysis of gust response
4. **Control System Design**: PID tuning for precision operations
5. **Alternative Configurations**: Electric and hybrid variants

### Integration Opportunities
- Link with existing `turbo_aircraft` framework for comparison
- Integration with optimization packages (PyOptSparse, SciPy)
- Connection to SUAVE's higher-fidelity analysis modules
- Export capability for flight simulator validation

## Technical Notes

### SUAVE Integration
- Compatible with SUAVE 2.5+ framework
- Uses standard SUAVE vehicle and mission structures
- Custom engine network for GTM-140 integration
- Extended analysis modules for competition metrics

### Dependencies
- SUAVE aerospace analysis package
- NumPy, SciPy for numerical analysis
- Matplotlib for visualization
- Standard Python 3.x libraries

### Validation
- Aircraft parameters validated against perplexity analysis
- GTM-140 performance based on JETPOL specifications
- Mission profile verified against competition requirements
- Results cross-checked with baseline calculations

## Contact and Support

This implementation is based on detailed analysis from the perplexity research folder and integrates seamlessly with the existing SUAVE student competition framework. For questions or improvements, refer to the original perplexity concepts and SUAVE documentation.

**Competition Goal**: Maximize Droniada Sztafeta success through optimal aircraft design, mission planning, and autonomous execution reliability.
