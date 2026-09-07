# ComponentStore

This directory contains the Pydantic v2 schemas used to validate incoming declarative YAML configurations before they are passed to the physics solvers.

## Why We Use ComponentStore
ComponentStore provides "front-door" validation for the `YAADO_Core` framework. 
If a user accidentally types a string (`"five"`) instead of a float (`5.0`), or specifies a negative mass (`-10 kg`) in their configuration, these Pydantic schemas catch the error instantly. Without this layer, bad data might flow deep into the core framework and cause a mystical failure somewhere down the road.

---

## 🧱 The Lego Brick Architecture

Instead of rigid vehicle templates, YAADO uses a pure **Composition** architecture. This folder provides generic physical building blocks that can be snapped together in their YAML files to build any vehicle imaginable (Rockets, UAVs, Airships, etc.).

### Current Component Categories:

**1. `propulsion.py`**
* `SolidMotor`
* `RamjetEngine`
* `TurbojetEngine`

**2. `aero_surfaces.py`**
* `Fins` (radial rocket fins)
* `Wings` (fixed-wing aircraft wings)
* `ControlSurface` (nested inside fins/wings)

**3. `body.py`**
* `AxisymmetricBody` (fuselages, rocket casings)

**4. `mass.py`**
* `MassProperties` (used for distributed mass inside components, or as a global vehicle point-mass)

### Adding New Components
When adding a new component (e.g. `Rotors`):
1. **Create the Schema:** Define a new Pydantic `BaseModel` in the appropriate category file.
2. **Discriminator:** Assign a unique type discriminator (e.g. `type: Literal["rotor"] = Field(default="rotor", frozen=True)`).
3. **Mandatory Baseline Examples:** Every parameter field (except `type`) **MUST** define realistic baseline examples via `Field(..., examples=[...])`. YAADO's template generation (`Terminal/Assembly`), CLI prompt fallbacks, and test suites enforce that all component fields define examples.
4. **Registry & Unions:** Add the model to the appropriate subsystem registry tuple (e.g. `AERO_COMPONENTS`) and union (e.g. `AnyAeroComponent`) in `YAADO_Core/ComponentStore/__init__.py`.
5. **Unit Tests:** Add validation tests in `tests/YAADO_Core/ComponentStore/`. Schema example validity and typing will automatically be tested by `tests/YAADO_Core/ComponentStore/test_examples.py`.
