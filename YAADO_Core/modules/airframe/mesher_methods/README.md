# Gmsh Euler Mesher

* **Method class**: `GmshMeshAnalysis` in [`gmsh_euler.py`](gmsh_euler.py)
* **Fidelity**: Level 2 (meshes for compressible Euler CFD)
* **Status**: Repaired and verified as a mesher. Running SU2 on the mesh is tracked in #44.

Builds the vehicle from its components as one solid, cuts it out of a sphere, and fills the rest with tetrahedra for inviscid flow. The shape comes from [`outer_shape.py`](../outer_shape.py):

* **Body**: a tangent ogive, cone, or half ellipsoid nose on a cylinder with a flat base. Axes: $`x`$ aft from the nose tip, $`z`$ up, $`y`$ to starboard.
* **Fins**: every fin set at its `root_le_from_nose`; one set without it sits flush with the aft end. The section is the fin's `airfoil`, or a double wedge of its `thickness_ratio`. A fin with neither gets `fin_thickness_ratio`, and the run says so.
* **Wings**: placed by `root_le_from_nose` (root leading edge at the centerline), at mid-height. A wing without it is left out, and the run says so.

A vehicle that is symmetric about $`y = 0`$ is meshed as half a model. Fins roll to a symmetric position unless `fin_roll_deg` is set: four fins form a cross, three have one fin up. A rolled or cambered fin set needs the full model, which `domain=auto` picks by itself.

| Input | Setting | Default |
| :--- | :--- | :--- |
| Cells across the body diameter; sets the whole mesh | `cells_per_diameter` | 16 |
| Lifting surfaces: names separated by commas, or `none` | `surfaces` | Every placed one |
| Half or full vehicle | `domain` (`auto`, `half`, `full`) | `auto` |
| First fin from straight up [deg] | `fin_roll_deg` | Symmetric |
| Thickness of fins that give none | `fin_thickness_ratio` | 0.04 |
| Far-field radius in body lengths | `farfield_lengths` | 8 |

**Cell sizes:** cells are smallest at the nose tip and the edges of fins and wings (about a third of the cells around them), and grow linearly toward the far field. The number of cells grows with about the cube of `cells_per_diameter`, everywhere at once, so meshes at 12, 16 and 24 are a fair refinement study. The Harpoon example has about 270 000 tetrahedra at 16.

**Checks on every mesh:** the boundary is watertight (every free face is on exactly one marker), the meshed airframe and base areas are within 5% of the CAD areas, and cells of poor quality are counted and reported.

**Files:** a logged run saves `airframe.su2` with the markers `airframe`, `base`, `farfield` and, for half a model, `symmetry`; `airframe.step` with the vehicle as one solid; a figure of the mesh; and Gmsh's output. The [SU2 decks](../../wind_tunnel/methods/su2/README.md) use these names, and the [STEP slicer](../slicer_methods/README.md) lists the STEP file.

**Limits:**
* Inviscid meshes only: there are no boundary-layer cells.
* Closed bodies only: inlets, nozzles and control-surface deflections are not modeled.
* One body. Transitions (`max_diameter`) and protrusions (`total_length`) have no position in the schema and are left out, and the run says so.

**Gmsh:** see [Installing Gmsh](../slicer_methods/README.md#installing-gmsh).

**Reference:** Geuzaine, C. and Remacle, J.-F., "Gmsh: a three-dimensional finite element mesh generator with built-in pre- and post-processing facilities", *International Journal for Numerical Methods in Engineering* 79(11), 2009.
