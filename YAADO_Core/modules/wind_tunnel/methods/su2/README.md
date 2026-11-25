# SU2 Euler Configuration Decks

* **Method class**: `SU2ConfigGeneration` in [`su2_config_template.py`](su2_config_template.py)
* **Fidelity**: Level 2 (compressible Euler CFD)
* **Status**: Repaired and verified as a deck generator. The [Gmsh mesher](../../../airframe/mesher_methods/README.md) makes the mesh. Running SU2 is tracked in #44.

This module writes one [SU2](https://su2code.github.io/) configuration deck per pair of Mach number and angle of attack: every Mach number gets every angle. The decks set up SU2's compressible Euler solver (JST scheme, converged on the density residual) for the freestream of the ISA atmosphere at `altitude_m`.

* **References:** the force coefficients use the body's frontal area $`\pi d^2/4`$, and the moment coefficients the body diameter $`d`$, about the vehicle CG from `mass_properties`. For an aircraft, set `ref_area` and `ref_length` to the wing area and mean chord. Without a CG the moments are taken about the nose tip, and the run says so.
* **Mesh:** every deck reads `airframe.su2`, with the wall markers `airframe` and `base` and the far-field marker `farfield`, as the Gmsh mesher writes them. `half_model` adds the marker `symmetry` and halves `REF_AREA`, so that the coefficients stay those of the whole vehicle. A half model has no meaningful side force, rolling or yawing moment.
* **Option names** follow SU2 v8 (the `external/su2` submodule). A test checks every option of a deck against the SU2 source, because SU2_CFD stops on an unknown option.

| Input | Setting | From the TOML | Default |
| :--- | :--- | :--- | :--- |
| Mach numbers | `mach_list` | - | 0.8, 1.5, 2.0, 2.5, 3.0 |
| Angles of attack [deg] | `alpha_list_deg` | - | 0 |
| Altitude [m] | `altitude_m` | - | 0 |
| Force reference area [m²] | `ref_area` | Body `diameter` | Body frontal area |
| Moment reference length [m] | `ref_length` | Body `diameter` | Body diameter |
| Moment reference point [m] | `cg_from_nose` | `mass_properties.cg_from_nose` | Nose tip |
| Whether the mesh is half a vehicle | `half_model` | - | `true` |

A logged run saves the decks (for example `su2_mach2p50_aoam2p00.cfg` for Mach 2.5 at -2°) and `run_manifest.json`, which lists every case, in the run's `artifacts/` folder. Run a case with `SU2_CFD su2_mach2p50_aoa0p00.cfg` in a folder that also holds the mesh.

**Limits:**
* Inviscid: no skin friction, and base drag is unreliable. The history lists `CD(airframe)` and `CD(base)` separately; add a friction and a base drag estimate for total drag.
* Euler is meant for transonic and supersonic flow. Below about Mach 0.3 use a low-speed method such as XFOIL for sections.

**Reference:** Economon, T. D. et al., "SU2: An Open-Source Suite for Multiphysics Simulation and Design", *AIAA Journal* 54(3), 2016.
