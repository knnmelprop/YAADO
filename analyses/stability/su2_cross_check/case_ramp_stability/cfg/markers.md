# Canonical marker list — ramP stability case

SU2 reads boundary-condition tags from the mesh by **marker name**. Name them
consistently in the mesher (Gmsh Physical Surfaces / CGNS boundary names) so
the `.cfg` BC blocks resolve. Do **not** rename after meshing — the `.cfg`
references these strings verbatim.

| Marker            | Physical meaning                              | SU2 BC (this case)      |
|-------------------|-----------------------------------------------|-------------------------|
| `farfield`        | Outer domain boundary (≥15 body-dia away)     | `MARKER_FAR`            |
| `body_wall`       | Ramjet (stage-2) external body-of-revolution  | `MARKER_HEATFLUX` (adiab.) |
| `interstage_wall` | Interstage section — **mandatory geometry**   | `MARKER_HEATFLUX` (adiab.) |
| `booster_wall`    | Stage-1 booster external surface              | `MARKER_HEATFLUX` (adiab.) |
| `base_region`     | Blunt base(s) — booster aft, any step         | `MARKER_HEATFLUX` (adiab.) |
| `inlet_cap`       | **Capped** ramjet inlet face (solid, no flow) | `MARKER_HEATFLUX` (adiab.) |
| `symmetry`        | Optional — only if running a half-model       | `MARKER_SYM`            |

## Rules
- **Capped inlet:** for a first stability case there is NO internal duct flow.
  The inlet is closed by `inlet_cap` (a wall). This matches the historical
  air-breathing-missile stability practice (external geometry only; DTIC
  ADA111786) cited in the plan.
- **Interstage is not optional.** It carries real normal force and shifts CP;
  include it as first-class geometry, not a detail to defeature.
- **Force integration** (`MARKER_MONITORING`) must cover every solid wall so
  the integrated CN / CA / CM are complete. Missing a wall silently biases CP.
- Fins, if present, get their own `fin_wall` marker and must be added to both
  `MARKER_HEATFLUX` and `MARKER_MONITORING`.
