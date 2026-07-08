# Proposal: Droniada Sztafeta Integration into Student Competition Structure

## Executive Summary

This proposal outlines adjustments to the existing `student_competition` directory structure to accommodate the Droniada Sztafeta competition concept with GTM-140 turbojet integration, while maintaining compatibility with existing frameworks.

## Current Structure Analysis

The existing structure provides:
- ✅ Modular vehicle definition system
- ✅ Mission profiling framework
- ✅ Performance analysis pipeline
- ✅ Visualization and reporting tools
- ❌ Large aircraft focus (1500kg, high altitude, long range)
- ❌ No small UAV or competition-specific configurations
- ❌ Missing precision operations (beacon dropping)
- ❌ No GTM-140 or small turbojet support

## Proposed Structural Changes

### 1. New Directory: `droniada_sztafeta/`
Create dedicated directory structure for the competition:

```
student_competition/
├── droniada_sztafeta/           # NEW: Dedicated Droniada folder
│   ├── main.py                  # Main execution script
│   ├── README.md                # Competition-specific documentation
│   ├── vehicle/                 # Vehicle definitions
│   │   ├── __init__.py
│   │   ├── gtm140_aircraft.py   # NEW: GTM-140 powered aircraft
│   │   ├── electric_aircraft.py # NEW: Electric alternative
│   │   └── hybrid_aircraft.py   # NEW: Hybrid configuration
│   ├── mission/                 # Mission profiles
│   │   ├── __init__.py
│   │   ├── sztafeta_mission.py  # NEW: Droniada competition mission
│   │   └── optimization_mission.py # NEW: Parameter optimization mission
│   ├── analysis/                # Analysis modules
│   │   ├── __init__.py
│   │   ├── competition_analysis.py # NEW: Competition-specific analysis
│   │   ├── drop_accuracy.py     # NEW: Beacon drop analysis
│   │   └── optimization.py      # NEW: Multi-objective optimization
│   ├── engines/                 # NEW: Engine models
│   │   ├── __init__.py
│   │   ├── gtm140_model.py      # NEW: GTM-140 engine deck
│   │   └── engine_database.py   # NEW: Engine parameter database
│   ├── payloads/                # NEW: Payload systems
│   │   ├── __init__.py
│   │   ├── beacon_dropper.py    # NEW: Drop system modeling
│   │   └── payload_effects.py   # NEW: CG/weight effects
│   ├── plots/                   # Visualization
│   │   ├── __init__.py
│   │   ├── competition_plots.py # NEW: Competition-specific plots
│   │   └── optimization_plots.py # NEW: Optimization visualizations
│   ├── data/                    # Input data
│   │   ├── airfoils/            # Airfoil coordinates
│   │   ├── engines/             # Engine performance data
│   │   └── competition_rules/   # Rules and constraints
│   └── results/                 # Output results
│       ├── baseline/            # Baseline configurations
│       ├── optimized/           # Optimization results
│       └── reports/             # Generated reports
```

### 2. Enhanced Aircraft Concepts Structure
Reorganize `aircraft_concepts/` to include Droniada configurations:

```
aircraft_concepts/
├── conventional/
│   └── droniada_gtm140/         # NEW: GTM-140 configuration
├── electric/
│   └── droniada_electric/       # NEW: Electric configuration
├── hybrid/
│   └── droniada_hybrid/         # NEW: Hybrid configuration
└── vtol/
    └── droniada_vtol/           # NEW: VTOL configuration
```

### 3. Analysis Framework Extensions
Extend `analysis/` structure for competition-specific needs:

```
analysis/
├── optimization/
│   ├── droniada_optimizer.py    # NEW: Competition-specific optimizer
│   └── multi_objective.py       # NEW: Multi-objective framework
├── performance/
│   ├── drop_accuracy.py         # NEW: Drop precision analysis
│   ├── wind_effects.py          # NEW: Wind disturbance modeling
│   └── night_operations.py      # NEW: Night flight considerations
└── stability/
    └── small_uav_stability.py   # NEW: Small UAV stability analysis
```

### 4. Reference Data Enhancements
Expand `reference_data/` with competition-specific data:

```
reference_data/
├── airfoils/
│   ├── gtm140_optimized/        # NEW: GTM-140 optimized airfoils
│   └── small_uav/               # NEW: Small UAV airfoil database
├── competition_rules/
│   ├── droniada_2025_rules.pdf  # NEW: Official rules
│   ├── constraints.yaml         # NEW: Programmatic constraints
│   └── scoring_criteria.yaml    # NEW: Scoring methodology
└── engines/
    ├── gtm140_data/             # NEW: GTM-140 performance data
    └── small_turbojets/         # NEW: Small turbojet database
```

## Implementation Plan

### Phase 1: Core Framework (Week 1-2)
1. Create `droniada_sztafeta/` directory structure
2. Implement GTM-140 engine model based on perplexity data
3. Create baseline aircraft configuration
4. Implement basic mission profile

### Phase 2: Competition Integration (Week 3-4)
1. Implement beacon drop system modeling
2. Add competition constraints and validation
3. Create wind effects and disturbance modeling
4. Implement night operations considerations

### Phase 3: Optimization Framework (Week 5-6)
1. Implement multi-objective optimization
2. Add design variable definition system
3. Create Pareto front analysis
4. Implement sensitivity studies

### Phase 4: Validation and Testing (Week 7-8)
1. Validate against competition requirements
2. Compare with perplexity baseline calculations
3. Create comprehensive test suite
4. Generate documentation and examples

## Key Implementation Files

### 1. GTM-140 Aircraft Configuration
Based on perplexity analysis with SUAVE integration:

```python
# droniada_sztafeta/vehicle/gtm140_aircraft.py
- Wing area: 0.79 m² (optimizable 0.6-1.2 m²)
- Wing span: 2.51 m (AR = 8.0)
- Total weight: ~11.8 kg (< 25 kg limit)
- GTM-140 engine: 140N max thrust, 1.75 kg
- Fuel capacity: 2.6 kg with reserves
```

### 2. Competition Mission Profile
Based on Droniada Sztafeta requirements:

```python
# droniada_sztafeta/mission/sztafeta_mission.py
- Takeoff and climb to 55m AGL
- Two 600m circuit segments
- 4 precision beacon drops
- Autonomous operation
- 30-minute time limit
- Wind up to 8 m/s
```

### 3. Optimization Framework
Multi-objective optimization for competition success:

```python
# droniada_sztafeta/analysis/optimization.py
- Minimize: mission time, fuel consumption
- Maximize: drop accuracy, stability margins
- Constraints: weight < 25kg, stall speed < 12 m/s
- Variables: wing geometry, fuel loading, cruise speeds
```

## Migration Strategy

### Preserving Existing Work
1. Keep existing `turbo_aircraft/` unchanged as reference
2. Create new directories alongside existing structure
3. Reuse existing plotting and analysis frameworks where applicable
4. Maintain backward compatibility

### Integration Benefits
1. Leverages existing SUAVE integration patterns
2. Provides comparison baseline with larger aircraft
3. Maintains educational value for different aircraft scales
4. Enables future competition concept additions

## Expected Outcomes

### Technical Deliverables
1. Complete SUAVE model of GTM-140 powered aircraft
2. Validated mission profile for Droniada Sztafeta
3. Multi-objective optimization framework
4. Competition constraint validation system
5. Comprehensive analysis and visualization tools

### Performance Targets
1. Aircraft weight: < 25 kg (target ~12 kg)
2. Mission time: < 30 minutes (target ~20 minutes)
3. Drop accuracy: < 5 meters (target < 2 meters)
4. Fuel consumption: optimized for mission requirements
5. Stall speed: < 12 m/s for safe autonomous operation

### Educational Value
1. Demonstrates small UAV design principles
2. Shows competition-specific optimization
3. Illustrates turbojet integration challenges
4. Provides practical SUAVE application example
5. Creates reusable framework for future competitions

## Conclusion

This proposal provides a comprehensive integration of the Droniada Sztafeta concept into the existing student competition structure while preserving existing work and maintaining educational value. The modular approach allows for future extensions and provides a solid foundation for competition success.

The implementation leverages the detailed analysis from the perplexity folder while structuring it within SUAVE's established patterns and the existing directory organization.
