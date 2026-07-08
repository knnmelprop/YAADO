# Student Competition Turbo Aircraft

This directory contains a complete SUAVE analysis setup for a student competition aircraft with turbo engine propulsion.

## Directory Structure

```
turbo_aircraft/
├── main.py                    # Main execution script
├── vehicle/                   # Vehicle definition
│   ├── __init__.py
│   └── turbo_aircraft.py     # Aircraft configuration with turbofan engine
├── mission/                   # Mission profiles
│   ├── __init__.py
│   └── competition_mission.py # Competition mission definition
├── analysis/                  # Analysis modules
│   ├── __init__.py
│   └── performance_analysis.py # Performance evaluation
├── optimization/              # Optimization studies
│   └── __init__.py
├── plots/                     # Plotting and visualization
│   ├── __init__.py
│   └── plotting.py           # Post-processing and plotting
├── data/                      # Input data files
├── results/                   # Output results
└── README.md                  # This file
```

## Usage

1. **Basic Analysis:**
   ```bash
   cd /workspaces/SUAVE/student_competition/turbo_aircraft
   python main.py
   ```

2. **Interactive Mode:**
   ```bash
   python
   >>> import main
   >>> vehicle, mission, results = main.main()
   ```

## Aircraft Configuration

The aircraft is configured as a turbofan-powered aircraft suitable for student competitions with:

- **Wing:** High aspect ratio (10.0) main wing with 35.66m span
- **Engines:** Twin turbofan engines with 5.4 bypass ratio
- **Thrust:** 24,000 N total design thrust
- **Weight:** 1,500 kg maximum takeoff weight
- **Mission:** Multi-segment mission including climb, cruise, and descent

## Mission Profile

The default mission includes:
1. Three-stage climb to 10.5 km altitude
2. Cruise at 10.5 km for 2000 km
3. Two-stage descent to ground level

## Outputs

Results are automatically saved to:
- `results/mission_results.txt` - Detailed numerical results
- `plots/mission_profile.png` - Altitude and speed profiles
- `plots/aerodynamic_forces.png` - Lift, drag, and thrust forces
- `plots/engine_performance.png` - Engine parameters
- `plots/fuel_consumption.png` - Fuel usage over time

## Customization

To modify the aircraft or mission:

1. **Aircraft Configuration:** Edit `vehicle/turbo_aircraft.py`
2. **Mission Profile:** Edit `mission/competition_mission.py`
3. **Analysis Setup:** Edit `analysis/performance_analysis.py`
4. **Plotting:** Edit `plots/plotting.py`

## Requirements

- SUAVE aerospace analysis package
- NumPy
- Matplotlib
- Python 3.x

## Notes

This template provides a starting point for student competition aircraft analysis. Modify the aircraft parameters, mission profile, and analysis methods according to your specific competition requirements.
