# Template Generation

TOML generation follows this workflow:
1. The user picks a component to add to the model
2. The CLI asks the user whether the user wants to fill in the values or use dummy values (with a clear warning)
2.1 If the user wants to fill in the values (production), then the CLI asks for each value and provides context
2.2 If the user simply wants to skip everything, a dummy (but actually working) config is created.
2.3 It should also be possible to skip individual values (if they wouldn't be important to the user given their specific analysis they want to run)

## Implementation Strategy: The Physics-Owned Fallback (Pydantic Native)

To keep the CLI infinitely scalable and avoid hardcoding dummy values, the CLI utilizes Pydantic's native reflection capabilities:

* **Dynamic Context (2.1):** The CLI does not hardcode help text. It dynamically reads `field_info.description` directly from the Pydantic schema to display contextual help (e.g. *"Wing aspect ratio b^2/S. (> 0)"*).
* **Safe Fallbacks (2.2 & 2.3):** The physics developers define safe, working dummy values directly inside the `ComponentStore` schemas using Pydantic's metadata (e.g., `Field(..., json_schema_extra={"demo_default": 2.0})`). 
* **The Logic:** When a user skips a prompt or asks for a dummy config, the CLI automatically injects the embedded `demo_default` for that specific field. This ensures the generated TOML is always mathematically valid without the CLI needing to know anything about aerospace engineering.
