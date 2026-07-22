# Mesh-quality checklist — supersonic external RANS (ramP stability)

Gate the mesh on this **before** any long solve. GO/NO-GO at the bottom.

## Topology / watertightness
- [ ] Geometry is watertight (no gaps/overlaps) after CAD cleanup from STEP.
- [ ] Every solid surface carries exactly one marker (see `cfg/markers.md`).
- [ ] `farfield` fully encloses the body; no wall touches the outer boundary.
- [ ] Interstage present and meshed as first-class geometry (not defeatured).
- [ ] Ramjet inlet **capped** (`inlet_cap` wall) — no internal duct volume.

## Domain sizing (supersonic)
- [ ] Farfield ≥ ~15 body-diameters lateral.
- [ ] Extra upstream margin for the bow shock; extra downstream for the wake /
      base recirculation (do not clip the trailing shock system).

## Near-wall / turbulence resolution
- [ ] Target **wall-resolved** y⁺ ≈ 1 (SA/SST), first-cell height sized from a
      flat-plate estimate at Mach 2.5, design altitude, REF_LENGTH.
- [ ] Do **not** land in the y⁺ 5–30 buffer-layer dead zone.
- [ ] ≥ 15–20 prism/hex layers in the boundary layer, growth ratio ≤ 1.2.

## Local refinement (where CP/CM is decided)
- [ ] Nose / tip (bow-shock capture).
- [ ] Interstage step and any shoulder (shock–BL interaction).
- [ ] Fin leading edges (if fins present).
- [ ] Base region (separation / recirculation).

## Quality metrics
- [ ] Max skewness within solver-acceptable bound; no negative volumes.
- [ ] Smooth size transitions (no >1.5 jump) across shock-refinement zones.
- [ ] Two grid levels prepared (coarse + fine) for a GCI grid-convergence pair.

## Sanity solve
- [ ] Coarse-mesh short run reaches a monotone residual drop (≥2–3 orders) with
      no NaNs before committing to the full 8000-iter solve.

---
### GO / NO-GO
Reviewer: _______   Date: _______   Verdict: **GO / NO-GO**
Notes / open ASSUMPTIONS:
