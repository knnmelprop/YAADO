# Web vehicle viewer

A static page that draws one vehicle in 3D with [Three.js](https://threejs.org/). No backend and no build step.

## Use

1. Export a vehicle to JSON (one line, run from the repository root):

   ```bash
   uv run python -c "from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig as C; print(C.from_toml('Hangar/examples/ALVRJ/ALVRJ.toml').model_dump_json(indent=2))" > vehicle.json
   ```

2. Open `Terminal/web_viewer/index.html` in a browser (double-click is enough, it works from disk).
3. Pick `vehicle.json` with the file picker or drop it on the page. `sample_vehicle.json` (ALVRJ) is included.

Three.js 0.160.0 is loaded from the jsDelivr CDN, so the first load needs internet access.

## What is drawn (all lengths in meters)

- `AxisymmetricBody`: a cylinder with a nose of `nose_length` and `nose_type` (ogive, conical, hemispherical).
- `Fins`: `count` trapezoidal plates around the body from `span`, `chord_root`, `chord_tip`, `sweep` (leading edge).
- `Wings`: two trapezoidal half-wings from `span`, `aspect_ratio`, `taper_ratio`, `sweep` (quarter chord), `dihedral`. Area is `S = b^2/AR`, root chord is `2S / (b (1 + taper))`.
- `SolidMotor`: a translucent cylinder when `casing_length` and `casing_diameter` are set. Ramjet and turbojet engines are listed but not drawn.
- The vehicle CG (`mass_properties.cg_from_nose`) is shown as a red marker.

## Assumptions

The schemas have no component positions yet (issue #43), so:

- fins sit at `root_le_from_nose`, or flush with the aft end of the body when it is not set;
- the root quarter chord of a wing sits at the vehicle CG, else at the wing's own CG, else at mid-body;
- the motor casing is flush with the aft end of the body;
- missing `nose_length` is 3 body diameters (0.5 for a hemisphere), missing `chord_root` is the fin span and missing `chord_tip` is 0.4 of the root chord.

The page lists the assumptions it used. Out of scope: editing the vehicle, running solvers, any server.

## Tests

`tests/Terminal/test_web_viewer.py` checks that `sample_vehicle.json` validates with `BaseVehicleConfig.model_validate_json()`, so the sample stays in sync with the schemas.
