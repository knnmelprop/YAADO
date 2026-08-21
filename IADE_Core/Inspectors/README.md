# Inspectors

This directory contains the Pydantic v2 schemas used to validate incoming declarative YAML configurations before they are passed to the physics solvers.

## Why We Use Inspectors
Inspectors provide "front-door" validation for the `IADE_Core` framework. 
If a user accidentally types a string (`"five"`) instead of a float (`5.0`), or specifies a negative mass (`-10 kg`) in their YAML configuration, these Pydantic schemas catch the error instantly. Without this layer, bad data might flow deep into the core framework and cause a mythical failure somewhere down the road.

---

> WARNING: This is just my ([Arseni's](https://github.com/Arseni10Lk)) vision, we might agree to implement smth else
> ## 🚧 ARCHITECTURAL REFACTOR NEEDED (TODO)
> 
> **The current implementation in `vehicle_schema.py` actively violates the framework's "vehicle-agnostic" rule.**
> 
> Currently, the base configuration schema hardcodes the discriminator `vehicle_type: Literal["UAV", "Rocket"]`, and `IADE_Core` physics modules are hardcoding imports to specific project schemas (e.g., `from Hangar.ramjet_rocket.rocket_schema import RocketConfig`).
> 
> This is a major architectural flaw. A core framework should never know about specific user projects. If a user wants to model a Helicopter, they should not have to edit the core open-source framework.
> 
> ### The Required Refactor:
> To achieve a true vehicle-agnostic architecture, this directory must be refactored from **Vehicle-Based Schemas** to **Component-Based Schemas**:
> 
> 1. **Generic Base:** `BaseVehicleConfig` must be made completely generic (e.g., `vehicle_type: str`, and `extra="allow"` so users can prototype without the inspector crashing).
> 2. **Component Lego Bricks:** Instead of validating a "Rocket", this directory should provide generic physical building blocks:
>    * `WingSchema` (demands `span_m > 0`, `chord_m > 0`)
>    * `EngineSchema` (demands `thrust_N > 0`)
>    * `MassPropertiesSchema` (demands `total_mass_kg > 0`)
> 3. **Move Specifics to Hangar:** The rigid, specific vehicle assemblies (like `RocketConfig` and `UAVConfig`) must be moved entirely into the user's `Hangar/` workspace. `IADE_Core` solvers should only ever ask a vehicle for its generic components (e.g., *"give me a list of all objects passing `WingSchema`"*), rather than expecting a specific vehicle class.
