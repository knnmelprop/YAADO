# Terminal Assembly

The `Terminal/Assembly` module provides vehicle assembly and template generation logic for YAADO. It bridges interactive CLI workflows with the declarative TOML configuration files stored in `Hangar/`.

## Purpose & Design Philosophy

YAADO vehicles are built via **Composition** using modular Lego-like components defined in `YAADO_Core/ComponentStore/`. The Assembly module coordinates these components into a unified `BaseVehicleConfig` and handles serialization to TOML.

### The "Physics-Owned Fallback" Pattern
To keep the CLI completely decoupled from specific aerospace configurations, the Assembly module never hardcodes physical dimensions or component parameters:

- **Dynamic Context:** Field descriptions and constraints are read dynamically from Pydantic schema metadata (`field_info.description`).
- **Baseline Values via Examples:** Default values are sourced directly from the schema definitions via `Field(..., examples=[...])`. The physics developers own and maintain realistic baseline numbers right in the schemas.
- **Strict Validation Intact:** Required fields remain strictly required during normal simulation validation; examples serve as templates without weakening schema validation.

## Interactive CLI Workflow Specification

During interactive CLI operation (under development), component configuration follows these 3 prompt scenarios:

1. **Component Selection:** The user chooses a component type from `ComponentStore` to add to the vehicle.
2. **Prompting & Fallback Choice:** The CLI asks whether the user wants to provide custom values or use baseline examples (with a disclaimer):
   - **Scenario 2.1 — Production (Full Customization):** The CLI prompts for each field sequentially, displaying contextual help, units, and mathematical bounds dynamically from `field_info.description`.
   - **Scenario 2.2 — Quick-Start / Demo (Skip All):** If the user opts to skip all prompts, a fully functional baseline component is generated immediately from `field_info.examples`.
   - **Scenario 2.3 — Granular Skip (Per-Field Fallback):** On any individual prompt, the user can press Enter to accept the embedded schema example for that specific parameter (useful when a parameter is not critical for their intended analysis).

## Key Class: `VehicleTemplateGenerator`

Located in [`template_generator.py`](template_generator.py), the `VehicleTemplateGenerator` exposes class methods for vehicle creation:

### 1. `generate_template(name, component_classes, pre_filled=False)`
Constructs and serializes a vehicle TOML file to `Hangar/<name>/<name>.toml`.

- **Pre-filled Mode (`pre_filled=True`):** Populates all required fields using schema examples. Produces an instantly valid, ready-to-fly baseline configuration (e.g. for quick interactive studies and demos).
- **Production Skeleton Mode (`pre_filled=False`):** Creates an unvalidated template blueprint using Pydantic's `model_construct()`, leaving fields unpopulated for users to manually define.

### 2. `assemble_vehicle(name, components)`
Routes instantiated Pydantic models into their appropriate vehicle subsystems (`aero_surfaces`, `bodies`, `propulsion`, or `mass_properties`) on a `BaseVehicleConfig`.

### 3. `prefill_component_values(component_class)`
Reflects on a Pydantic model class and instantiates it using values extracted from `field_info.examples`.

### 4. `get_field_example(component_class, field_name)`
Retrieves the mandatory baseline example value for an individual field, facilitating granular per-field prompt fallback (Scenario 2.3). Raises `ValueError` if the field lacks schema examples.

## Usage

```python
from Terminal.Assembly import VehicleTemplateGenerator
from YAADO_Core.ComponentStore import (
    AxisymmetricBody,
    Wings,
    Fins,
    TurbojetEngine,
    SolidMotor,
    MassProperties,
)

# Generate a pre-filled, simulation-ready vehicle template in Hangar/
VehicleTemplateGenerator.generate_template(
    name="my_harpoon",
    component_classes=[
        AxisymmetricBody,
        Wings,
        Fins,
        TurbojetEngine,
        SolidMotor,
        MassProperties,
    ],
    pre_filled=True,
)
```