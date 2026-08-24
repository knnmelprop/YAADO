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
If you want to add a new component (e.g. `Rotors`), simply create a new Pydantic `BaseModel` in the appropriate file, give it a unique type (e. g. `type: Literal["rotor"]`), and inject it into the appropriate union (e. g. `AnyAeroComponent`) at the bottom of the file!
