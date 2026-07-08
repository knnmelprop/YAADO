# SUAVE Student Competition Framework

This directory contains aircraft design and analysis frameworks for various student competitions, with modular structures supporting different aircraft types and competition requirements.

## Directory Structure

```
student_competition/
├── README.md                     # This file
├── PROPOSAL_DRONIADA_INTEGRATION.md  # Integration proposal document
├── droniada_sztafeta/            # Droniada Sztafeta competition framework
│   ├── main.py                   # GTM-140 turbojet aircraft analysis
│   ├── README.md                 # Competition-specific documentation
│   ├── vehicle/                  # Aircraft configurations
│   ├── mission/                  # Competition mission profiles
│   ├── engines/                  # GTM-140 and engine models
│   ├── analysis/                 # Competition-specific analysis
│   ├── plots/                    # Visualization tools
│   └── results/                  # Generated results
├── turbo_aircraft/               # Large turbofan aircraft framework
│   ├── main.py                   # Traditional turbofan analysis
│   ├── README.md                 # Documentation
│   ├── vehicle/                  # Large aircraft configurations
│   ├── mission/                  # Long-range mission profiles
│   └── analysis/                 # Standard performance analysis
├── aircraft_concepts/            # Aircraft concept studies
│   ├── conventional/             # Conventional configurations
│   ├── electric/                 # Electric propulsion concepts
│   ├── hybrid/                   # Hybrid propulsion concepts
│   └── vtol/                     # VTOL configurations
├── analysis/                     # Shared analysis tools
│   ├── optimization/             # Optimization frameworks
│   ├── performance/              # Performance analysis tools
│   └── stability/                # Stability analysis tools
├── documentation/                # Reports and presentations
├── reference_data/               # Competition rules and reference data
├── results/                      # Shared results directory
└── perplexity/                   # Research and concept development
    ├── exported-assets-2/        # Droniada analysis and parameters
    └── concepts/                 # Prepared competition concepts
```

## Competition Frameworks

### 1. Droniada Sztafeta (Poland)
**Focus**: Small UAV turbojet aircraft for autonomous beacon dropping

**Key Features**:
- GTM-140 turbojet integration (140N, 1.75kg)
- 25kg maximum weight limit
- 50-60m AGL autonomous operation
- Precision beacon dropping mission
- Night operations capability

**Quick Start**:
```bash
cd droniada_sztafeta
python main.py
```

**Results**: Competition-optimized aircraft (~12kg, 20min mission, <2m drop accuracy)

### 2. General Turbofan Aircraft
**Focus**: Traditional turbofan aircraft for educational analysis

**Key Features**:
- Twin turbofan engines (24,000N total)
- 1,500kg aircraft weight
- High-altitude cruise missions
- Educational framework for large aircraft

**Quick Start**:
```bash
cd turbo_aircraft
python main.py
```

## Key Capabilities

### Aircraft Design
- **Small UAV**: GTM-140 turbojet, competition optimized
- **Large Aircraft**: Traditional turbofan, educational focus
- **Alternative Propulsion**: Electric, hybrid, VTOL concepts
- **Modular Framework**: Easy addition of new configurations

### Mission Analysis
- **Competition Missions**: Specific requirement validation
- **Performance Optimization**: Multi-objective frameworks
- **Constraint Validation**: Automatic rule compliance checking
- **Safety Analysis**: Margins and fail-safe evaluation

### Analysis Tools
- **SUAVE Integration**: Full aerospace analysis framework
- **Competition Metrics**: Specialized performance indicators
- **Visualization**: Custom plots for competition needs
- **Optimization**: Design variable studies and Pareto analysis

## Competition Integration

### Validated Competitions
- ✅ **Droniada Sztafeta**: Complete framework implemented
- 🔄 **SAE Aero Design**: Framework adaptable
- 🔄 **AIAA Design Build Fly**: Framework adaptable
- 🔄 **UAS Challenge**: Framework adaptable

### Framework Benefits
- **Rapid Prototyping**: Quick aircraft concept evaluation
- **Rule Validation**: Automatic constraint checking
- **Performance Prediction**: Detailed mission analysis
- **Design Optimization**: Systematic parameter studies
- **Educational Value**: SUAVE integration for learning

## Usage Examples

### Basic Analysis
```python
# Droniada Sztafeta analysis
cd droniada_sztafeta
python main.py

# Results automatically saved to results/ and plots/
```

### Interactive Analysis
```python
import sys
sys.path.append('droniada_sztafeta')
from main import main

vehicle, mission, results = main()

# Access competition metrics
metrics = results.competition_metrics
print(f"Mission time: {metrics['total_mission_time']:.1f} min")
print(f"Weight margin: {metrics['weight_margin']:.1f} kg")
print(f"Drop accuracy: {metrics['estimated_drop_accuracy']:.1f} m")
```

### Optimization Studies
```python
# Future implementation
from droniada_sztafeta.analysis.optimization import run_optimization
optimized_vehicle = run_optimization(design_variables, constraints)
```

## Development Guidelines

### Adding New Competitions
1. Create new competition directory: `competition_name/`
2. Copy structure from `droniada_sztafeta/` or `turbo_aircraft/`
3. Modify vehicle, mission, and analysis modules
4. Update main README with new competition details

### Extending Existing Frameworks
1. Add new aircraft configurations in `vehicle/`
2. Create specialized mission profiles in `mission/`
3. Develop competition-specific analysis in `analysis/`
4. Add custom visualization in `plots/`

### Integration Requirements
- SUAVE framework compatibility
- Standard directory structure
- Competition constraint validation
- Results export capability
- Documentation and examples

## Research Foundation

The frameworks are built on detailed research including:
- **Perplexity Analysis**: Comprehensive competition and technology research
- **SUAVE Integration**: Proven aerospace analysis methods
- **Competition Rules**: Official regulations and constraints
- **Industry Data**: Manufacturer specifications (GTM-140, etc.)
- **Optimization Theory**: Multi-objective design principles

## Future Development

### Planned Enhancements
1. **Multi-Fidelity Analysis**: CFD and higher-order methods integration
2. **Real-Time Optimization**: Interactive design parameter studies
3. **Competition Database**: Historical data and performance benchmarks
4. **Simulation Integration**: Flight simulator export capability
5. **Automated Reporting**: Competition documentation generation

### Integration Opportunities
- **CAD Integration**: 3D model generation from parameters
- **Manufacturing Analysis**: Buildability and cost estimation
- **Flight Test Correlation**: Real aircraft validation
- **Control System Design**: Autopilot integration
- **Certification Support**: Regulatory compliance tools

## Technical Support

For technical questions and development support:
- Review competition-specific README files
- Check SUAVE documentation for analysis methods
- Refer to perplexity research for design rationale
- Follow SUAVE coding standards and conventions

**Goal**: Provide comprehensive, validated frameworks for student competition success through systematic aircraft design and analysis.