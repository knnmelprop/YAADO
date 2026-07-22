# ramP stability CFD case — `ramP + interstage + booster`

Independent CFD cross-check of the ramjet-rocket **static-stability sign**,
replacing Barrowman above Ma 0.7. Steady, compressible, **supersonic RANS**,
**external-only, capped inlet**, Mach 2.5, small-AoA sweep {0, 4, 8}°, two grid
levels, SA + SST.

## Status

| Item | State |
|---|---|
| SU2 v8.5.0 local build (`~/.local/su2-8.5.0/bin`) | ✅ works (validated on NACA0012 inviscid) |
| Case scaffolding (this dir) | ✅ ready |
| Vehicle geometry (STEP) | ⛔ **does not exist yet** |
| Mesh | ⛔ **blocked on geometry** |
| Production solve | ⛔ blocked on mesh |

**The one blocker:** there is no vehicle CAD/mesh. Everything here is ready to
consume a STEP export the moment one lands.

## Directory layout

```
cad/    STEP masters from Fusion 360 (gitignored data)
        - ramp_interstage_booster_master.step          (full B-rep)
        - ramp_interstage_booster_external_capped.step (watertight, capped inlet)
geom/   cleaned/defeatured intermediate geometry (gitignored)
mesh/   .su2 / .cgns meshes (gitignored; DVC if versioned)
cfg/    ramp_stability_supersonic_RANS.cfg.template  ← tracked template
        markers.md                                    ← canonical marker names
run/    per-AoA solve dirs (gitignored outputs)
post/   postprocess_coeffs.py — CN/CA/CM, CP, static-margin sign
checklists/ mesh_quality_checklist.md, postproc_checklist.md
```

## Pipeline (Fusion → SU2)

1. **Fusion 360 → STEP** (not STL): export `..._master.step` and a simplified
   watertight `..._external_capped.step`. Split into logical components first so
   Fusion doesn't fuse bodies. → `cad/`
2. **Cleanup** to a single watertight external solid, inlet capped. → `geom/`
3. **Mesh** (Gmsh → `.su2`/CGNS): name markers per `cfg/markers.md`; wall-resolved
   y⁺≈1; refine nose/interstage/base/fin-LE; farfield ≥15 dia. Two levels. → `mesh/`
4. **Config:** fill `{{...}}` tokens in the cfg template (mesh name, REF_LENGTH,
   REF_AREA, CG). **Never fabricate CG** — sweep if unknown. Run SA and SST.
5. **Solve** per AoA (see run env below). → `run/aoaXX/`
6. **Post:** `post/postprocess_coeffs.py` → static-margin sign; complete
   `checklists/postproc_checklist.md`; GCI on the grid pair; cross-check vs
   DATCOM-class + Ackeret; append one line to `docs/decision-log.md`.

## Run environment (local, MPI-disabled build)

```bash
export SU2_RUN="$HOME/.local/su2-8.5.0/bin"
export SU2_HOME="/Users/aleksczernicki/Desktop/dev/iade/external/su2"
export PATH="$PATH:$SU2_RUN"
export PYTHONPATH="$PYTHONPATH:$SU2_RUN"
"$SU2_RUN/SU2_CFD" ramp_stability_supersonic_RANS.cfg   # filled template
```

The local build was configured `-Dwith-mpi=disabled` (Homebrew-OpenMPI/meson
linker mismatch on `SU2_GEO`); it is single-core. Fine for a first case — add a
proper MPI build before large fine-grid solves.
