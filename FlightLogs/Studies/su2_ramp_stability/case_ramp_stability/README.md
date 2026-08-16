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
| Vehicle geometry (STEP) | ✅ `cad/ramPcfdSimplified.step` (2026-07-22) |
| Marker identity (which solid = which stage) | ⛔ **needs human confirmation** — see `gmsh/marker_zones.yaml.template` |
| Mesh | ⛔ blocked on marker confirmation |
| Production solve | ⛔ blocked on mesh |

**The blocker moved, it didn't disappear.** A real STEP landed
(`ramPcfdSimplified.step`, "CFD SIMPLIFIED SINGLE ROCKET MODEL v2" per its own
STEP header, 2 solids, units mm). Its overall length (4355.0 mm) matches
`vehicles/ramjet_rocket/vehicle_config.yaml`'s `stage_2.total_length_m =
4.35501` to within 0.01 mm — confirms it's the same geometry that config
already references. But **which of the two solids is the ramjet stage and
which is the booster is not determinable from geometry alone**, and getting
it wrong would silently corrupt the stability-sign result this whole case
exists to compute. That identification is now the one open human step — see
`gmsh/marker_zones.yaml.template`.

## Directory layout

```
cad/    STEP masters (gitignored data)
        - ramPcfdSimplified.step   ← the real geometry, landed 2026-07-22
geom/   cleaned/defeatured intermediate geometry (gitignored)
mesh/   .su2 meshes + mesh/inventory/*.csv (gitignored; DVC if versioned)
cfg/    ramp_stability_supersonic_RANS.cfg.template  ← tracked template
        markers.md                                    ← canonical marker names
gmsh/   00_inventory_step.py       — dumps volume/surface bboxes to CSV
        01_classify_and_mesh.py   — classify-only + full mesh generation
        marker_zones.yaml.template — X-zone -> marker map, NEEDS CONFIRMATION
        isa_yplus.py              — ISA + first-cell-height (y+) sizing
        requirements-gmsh.txt     — gmsh==4.15.1 (Python module, not the
                                    Homebrew CLI package — see below)
run/    per-AoA solve dirs (gitignored outputs)
post/   postprocess_coeffs.py — CN/CA/CM, CP, static-margin sign
checklists/ mesh_quality_checklist.md, postproc_checklist.md
```

## Pipeline (STEP → SU2)

1. **Inventory** the STEP (read-only, already run — see below):
   ```bash
   python3 -m venv .venv-gmsh && .venv-gmsh/bin/pip install -r gmsh/requirements-gmsh.txt pyyaml
   .venv-gmsh/bin/python3 gmsh/00_inventory_step.py cad/ramPcfdSimplified.step
   ```
   Writes `mesh/inventory/volumes.csv` + `surfaces.csv`.
2. **Confirm marker identity** — open the STEP in Fusion or the Gmsh GUI
   (`gmsh cad/ramPcfdSimplified.step`), visually identify which solid is the
   ramjet (stage 2), which is the booster (stage 1), and where the interstage
   boundary sits. Copy `gmsh/marker_zones.yaml.template` →
   `gmsh/marker_zones.yaml` and fill in the `candidate_identity` and
   `markers` fields (X ranges, mm, STEP frame). **Do not guess** — the
   template already carries every real observed number; only the
   human-visual identification is missing.
3. **Classify-only dry run** (works without step 2, sanity-checks the read):
   ```bash
   .venv-gmsh/bin/python3 gmsh/01_classify_and_mesh.py --classify-only cad/ramPcfdSimplified.step
   ```
4. **Mesh** (requires step 2 done — the script refuses to run with any null
   marker):
   ```bash
   .venv-gmsh/bin/python3 gmsh/01_classify_and_mesh.py --level coarse --mach 2.5 --altitude-m 10000 cad/ramPcfdSimplified.step
   .venv-gmsh/bin/python3 gmsh/01_classify_and_mesh.py --level fine   --mach 2.5 --altitude-m 10000 cad/ramPcfdSimplified.step
   ```
   Builds a >=15-body-diameter farfield sphere, boolean-subtracts the vehicle,
   tags physical groups per marker, sizes the near-wall first cell for y+≈1
   via `isa_yplus.py` (ISA @ altitude + turbulent flat-plate Cf), refines
   nose/interstage/base by distance field, exports `mesh/ramp_stability_{coarse,fine}.su2`.
   Run `checklists/mesh_quality_checklist.md` against the result before solving.
5. **Config:** fill `{{...}}` tokens in the cfg template (mesh filename,
   REF_LENGTH, REF_AREA, CG). **Never fabricate CG** — sweep if unknown. Run
   both SA and SST.
6. **Solve** per AoA (see run env below). → `run/aoaXX/`
7. **Post:** `post/postprocess_coeffs.py` → static-margin sign; complete
   `checklists/postproc_checklist.md`; GCI on the coarse/fine pair;
   cross-check vs DATCOM-class + Ackeret; append one line to
   `docs/decision-log.md`.

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

## gmsh Python module note

Homebrew's `gmsh` CLI package (`brew install gmsh`, confirmed v4.15.1 present)
does **not** ship the Python bindings. The scripts in `gmsh/` need the PyPI
`gmsh` module of the *same* version, installed in a separate venv (see step 1
above) — mixing CLI and Python-module major versions has been a source of
mesh-format drift upstream, so keep them pinned together.
