# Optimal Aircraft Parameters for Droniada Sztafeta Competition - SUAVE Optimization Framework

## Executive Summary

Based on comprehensive analysis of Droniada Sztafeta competition requirements, GTM-140 engine specifications, and SUAVE optimization capabilities, this document presents optimal aircraft parameters designed to maximize competition success while enabling full optimization in the SUAVE framework.

## Competition Requirements Analysis

### Droniada Sztafeta Mission Profile
- **Objective**: Create buffer zone between contaminated and safe areas using light beacons
- **Mission**: Drop 4 light beacons (racers) every 10 meters over two 600m circuits
- **Flight Conditions**: Night operation, 50-60m AGL, autonomous mode
- **Environmental**: Wind up to 8 m/s, 15-minute rain resistance required
- **Time Limit**: 30 minutes maximum mission duration
- **Weight Limit**: 25kg MTOW maximum
- **Payload**: 4 beacons × 250g = 1.0kg total

### GTM-140 Engine Integration
- **Type**: Miniature turbojet engine
- **Thrust Range**: 8-140N variable
- **Weight**: 1.75kg (complete system)
- **Dimensions**: 315mm × 115mm diameter
- **Fuel Consumption**: 420-500g/min at maximum power
- **Operating Range**: 33,000-120,000 RPM

## Recommended Configuration: Fixed-Wing with GTM-140

### Primary SUAVE Optimization Variables

#### Wing Geometry Parameters
| Parameter | Initial Value | Min | Max | Unit | Priority |
|-----------|---------------|-----|-----|------|----------|
| Wing Area | 0.79 | 0.6 | 1.2 | m² | High |
| Wing Span | 2.51 | 2.0 | 3.5 | m | High |
| Aspect Ratio | 8.0 | 6.0 | 12.0 | - | High |
| Wing Sweep | 0 | -5 | 15 | deg | Medium |
| Taper Ratio | 0.7 | 0.4 | 1.0 | - | Medium |
| Wing Twist | -2 | -5 | 2 | deg | Medium |
| Dihedral | 3 | 0 | 8 | deg | Low |

#### Fuselage Parameters
| Parameter | Initial Value | Min | Max | Unit | Priority |
|-----------|---------------|-----|-----|------|----------|
| Length | 1.8 | 1.5 | 2.5 | m | High |
| Diameter | 0.25 | 0.20 | 0.35 | m | High |
| Fineness Ratio | 7.2 | 5.0 | 10.0 | - | Medium |

#### Empennage Parameters
| Parameter | Initial Value | Min | Max | Unit | Priority |
|-----------|---------------|-----|-----|------|----------|
| H-Tail Area | 0.15 | 0.10 | 0.25 | m² | High |
| V-Tail Area | 0.12 | 0.08 | 0.20 | m² | High |
| Tail Moment Arm | 1.2 | 1.0 | 1.6 | m | Medium |

#### Propulsion Integration
| Parameter | Value | Range | Unit | Notes |
|-----------|-------|-------|------|-------|
| Engine Thrust | 140 | 8-140 | N | GTM-140 specifications |
| Cruise Thrust Setting | 55.7 | 40-80 | N | 40% of maximum |
| Inlet Area Ratio | 1.0 | 0.8-1.3 | - | Optimize for efficiency |
| Engine Position | Centerline | - | - | Minimize intake losses |

## Mission-Specific Optimization Parameters

### Flight Profile Segments
```
1. Takeoff Segment
   - Altitude: 0 → 55m AGL
   - Climb Rate: 3.0 m/s
   - Airspeed: 18 m/s
   
2. Cruise Segment 1
   - Distance: 600m
   - Altitude: 55m AGL
   - Airspeed: 15 m/s
   
3. Drop Segment 1
   - Drop Points: 2 beacons
   - Loiter Radius: 50m
   - Drop Speed: 12 m/s
   
4. Cruise Segment 2
   - Distance: 600m (return)
   - Altitude: 55m AGL
   - Airspeed: 15 m/s
   
5. Drop Segment 2
   - Drop Points: 2 beacons
   - Loiter Radius: 50m
   - Drop Speed: 12 m/s
   
6. Landing Segment
   - Altitude: 55m → 0 AGL
   - Descent Rate: -2.5 m/s
   - Approach Speed: 16 m/s
```

### Performance Requirements
| Requirement | Target Value | Constraint | Unit |
|-------------|--------------|------------|------|
| Cruise Speed | 15 | 12-20 | m/s |
| Stall Speed | <12 | <12 | m/s |
| Climb Rate | 3.0 | >2.5 | m/s |
| Wing Loading | 15 | 10-25 | kg/m² |
| Thrust-to-Weight | 0.4 | >0.35 | - |
| Drop Accuracy | <2 | <5 | m |

## Weight and Balance Optimization

### Fixed Components
| Component | Weight | Notes |
|-----------|--------|-------|
| GTM-140 Engine | 1.75 kg | Including accessories |
| Avionics & Flight Control | 1.0 kg | Autopilot, GPS, sensors |
| Beacon Drop System | 0.7 kg | Servo actuators, release mechanism |
| Fuel System | 0.3 kg | Tank, lines, pumps |
| Electrical System | 0.4 kg | Wiring, switches, lighting |
| **Fixed Total** | **4.15 kg** | |

### Variable Components (SUAVE Optimized)
| Component | Formula | Range | Notes |
|-----------|---------|-------|-------|
| Wing Structure | 2.5 × Wing_Area | 1.5-3.0 kg | Carbon fiber construction |
| Fuselage Structure | 3.2 × Fuselage_Length | 4.8-8.0 kg | Monocoque design |
| Empennage | 1.8 × Tail_Area | 0.5-0.8 kg | Lightweight construction |
| Landing Gear | 0.8 + 0.05 × MTOW | 1.4-2.0 kg | Retractable gear |
| Fuel Weight | 2.6 × Reserve_Factor | 2.6-3.4 kg | Including 30% reserve |
| Payload | 1.0 | 1.0 kg | 4 beacons fixed |

### Target Weight Budget
- **Empty Weight**: ~8.2 kg
- **Fuel Weight**: ~2.6 kg
- **Payload**: 1.0 kg
- **Total Weight**: ~11.8 kg
- **Safety Margin**: 13.2 kg under 25kg limit

## Airfoil Selection for GTM-140 Integration

### Primary Options for SUAVE Analysis
1. **GTM-140 Specific Profile**
   - Thickness: 12%
   - Camber: 2%
   - Design CL: 0.4
   - Focus: Jet integration optimization

2. **NACA 4412** (Baseline)
   - Thickness: 12%
   - Camber: 2%
   - Design CL: 0.6
   - Focus: Proven low-speed performance

3. **Eppler 423** (Alternative)
   - Thickness: 12.5%
   - Camber: 2.5%
   - Design CL: 0.8
   - Focus: Low Reynolds number optimization

## SUAVE Optimization Framework Implementation

### Multi-Objective Optimization Setup
```python
# Primary Objectives (Minimize)
objectives = {
    'mission_time': weight_factor_0.3,
    'fuel_consumption': weight_factor_0.3,
    'structural_weight': weight_factor_0.2,
    'drop_deviation': weight_factor_0.2
}

# Constraints
constraints = {
    'MTOW': {'max': 25.0, 'unit': 'kg'},
    'stall_speed': {'max': 12.0, 'unit': 'm/s'},
    'climb_rate': {'min': 2.5, 'unit': 'm/s'},
    'static_margin': {'min': 0.05, 'max': 0.15, 'unit': '-'},
    'wing_loading': {'min': 10.0, 'max': 25.0, 'unit': 'kg/m²'}
}
```

### Design Variables Priority Matrix
| Variable Group | Variables | Impact on Success | Optimization Priority |
|----------------|-----------|-------------------|----------------------|
| **Critical** | Wing area, span, aspect ratio | Very High | 1 |
| **Important** | Fuselage length, tail areas | High | 2 |
| **Moderate** | Wing sweep, taper, twist | Medium | 3 |
| **Fine-tuning** | Dihedral, detailed geometry | Low | 4 |

### Competition-Specific Optimization Goals

#### Primary Success Factors
1. **Drop Accuracy** (35% weight)
   - Minimize flight path deviation in wind
   - Optimize control authority for precision
   - Minimize gust sensitivity

2. **Mission Reliability** (30% weight)
   - Maximize stall margin
   - Optimize fuel consumption
   - Minimize structural loads

3. **Autonomous Performance** (25% weight)
   - Optimize flight stability
   - Minimize control effort
   - Maximize sensor effectiveness

4. **Regulatory Compliance** (10% weight)
   - Stay within weight limits
   - Meet night flight requirements
   - Ensure fail-safe operation

## Implementation Recommendations

### Phase 1: Baseline Optimization
- Optimize wing geometry for cruise efficiency
- Size empennage for stability margins
- Balance weight distribution for CG limits

### Phase 2: Mission-Specific Tuning
- Optimize trajectory for drop accuracy
- Minimize wind disturbance effects
- Tune control system for precision

### Phase 3: Competition Preparation
- Validate performance in competition conditions
- Test beacon drop system integration
- Verify autonomous operation reliability

### Phase 4: Final Optimization
- Fine-tune based on test results
- Optimize for specific weather conditions
- Implement competition-day contingencies

## Risk Mitigation Strategies

### Technical Risks
- **Engine Integration**: Custom inlet design, thermal management
- **Drop Accuracy**: Precision guidance system, wind compensation
- **Night Operations**: Enhanced lighting, sensor redundancy
- **Weight Management**: Lightweight materials, system integration

### Operational Risks
- **Weather Sensitivity**: Design margins for wind gusts
- **Autonomous Reliability**: Redundant flight control systems
- **Fuel Management**: Conservative consumption estimates
- **Maintenance**: Simplified systems, field serviceability

## Conclusion

This parameter set provides a comprehensive foundation for SUAVE optimization targeting maximum Droniada Sztafeta competition success. The configuration prioritizes:

1. **Mission-specific performance** over general aviation metrics
2. **Precision and reliability** over maximum performance
3. **Optimization flexibility** while maintaining practical constraints
4. **GTM-140 integration** with proven aircraft design principles

The recommended approach balances competition requirements with SUAVE's optimization capabilities, providing clear pathways for achieving competition success through systematic design optimization.