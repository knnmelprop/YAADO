# STEP Cross-Section Slicer

* **Method class**: `GmshSliceAnalysis` in [`gmsh.py`](gmsh.py)
* **Fidelity**: Level 0 (exact geometry of the CAD model)
* **Status**: Repaired and verified

Cuts a STEP model of the vehicle with planes along its axis, using Gmsh's OpenCASCADE kernel, and measures every section:

* **Material area**: the solid material the plane cuts, holes excluded.
* **Outline area**: the area inside the outer outline with every hole filled. Parts inside each other (a grain in a casing) or touching each other (fins on a tube) count once. This is the area distribution for wave drag.
* **Equivalent diameter**: the diameter of the circle with the outline area.
* **Largest radius**: the distance from the axis to the farthest point of the outline, such as a fin tip.

The stations are the centers of equal slices, so the sum of their areas integrates the volume. The run compares that with the CAD kernel's own volume and says so if they differ by more than 2%.

The model's length, largest radius and body diameter are compared with the vehicle's body, fins and wings. A difference above `tolerance` is reported; nothing is changed. The body diameter is the median equivalent diameter behind the nose, so fins on less than half of the body do not affect it.

| Input | Setting | Default |
| :--- | :--- | :--- |
| STEP file | `step_file` | First STEP file found |
| CAD axis along the vehicle | `axis` (`x`, `y` or `z`) | `x` |
| Nose at the positive end of the axis | `reverse` | `false` |
| Number of stations | `n_stations` | 60 |
| Accepted relative difference from the vehicle | `tolerance` | 0.05 |

Put STEP files in `Hangar/geometry` (any `Hangar` folder works); the Flight Deck lists them, together with STEP files saved by the vehicle's own runs. Lengths are read in the file's own unit. Export the CAD model as solid bodies: a model of open surfaces has no volume to cut.

A logged run saves `sections.csv`, a figure of the areas and radii, and Gmsh's output.

## Installing Gmsh

The `gmsh` Python package is installed by `uv sync`. On Ubuntu and Debian it also needs `sudo apt install libglu1-mesa`. Gmsh runs in a child process ([`gmsh_process.py`](../gmsh_process.py)), so a run can be cancelled at once and a Gmsh crash does not take YAADO with it.
