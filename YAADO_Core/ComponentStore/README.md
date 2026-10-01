# ComponentStore

This directory contains the Pydantic v2 schemas used to validate incoming declarative TOML configurations before they are passed to the physics solvers.

## Why We Use ComponentStore
ComponentStore provides "front-door" validation for the `YAADO_Core` framework. 
If a user accidentally types a string (`"five"`) instead of a float (`5.0`), or specifies a negative mass (`-10 kg`) in their configuration, these Pydantic schemas catch the error instantly. Without this layer, bad data might flow deep into the core framework and cause a mystical failure somewhere down the road.

---

## 🧱 The Lego Brick Architecture

Instead of rigid vehicle templates, YAADO uses a pure **Composition** architecture. This folder provides generic physical building blocks that can be snapped together in their TOML files to build any vehicle imaginable (Rockets, UAVs, Airships, etc.).

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
1. **Create the Schema:** Define a new Pydantic `BaseModel` in the appropriate category file with `model_config = ConfigDict(extra="forbid")`.
2. **Discriminator:** Assign a unique type discriminator (e.g. `type: Literal["rotor"] = Field(default="rotor", frozen=True)`).
3. **Canonical SI Units (`UNITS`):** Declare `UNITS: ClassVar[dict[str, str]]` mapping every dimensional numeric field to its canonical SI unit symbol (e.g. `{"diameter": "m", "thrust": "N"}`). Field names must NEVER contain unit suffixes (`thrust` not `thrust_n`, `span` not `span_m`).
4. **Curated Headline Fields (`HEADLINE_FIELDS`):** Declare `HEADLINE_FIELDS: ClassVar[tuple[str, ...]] = ("diameter", "thrust")` listing the 2–3 most defining parameters. The Terminal UI (cockpit inspector) and CLI summaries use this to render prominent top-level summaries before reflecting remaining fields.
5. **Mandatory Baseline Examples:** Every parameter field (except `type`) **MUST** define realistic baseline examples via `Field(..., examples=[...])`. YAADO's template generation (`Terminal/Assembly`), CLI prompt fallbacks, and test suites enforce that all component fields define examples.
6. **Distributed Mass Property:** If the component has physical mass, include an optional `mass: MassProperties | None = Field(default=None, ...)` with a realistic prefilled example.
7. **Registry & Unions:** Add the model to the appropriate subsystem registry tuple (e.g. `AERO_COMPONENTS`) and union (e.g. `AnyAeroComponent`) in `YAADO_Core/ComponentStore/__init__.py`.
8. **Unit Tests:** Add validation tests in `tests/YAADO_Core/ComponentStore/`. Schema example validity, typing, units, and headline fields are automatically enforced by `tests/YAADO_Core/ComponentStore/test_examples.py`.
