# Inlet Performance v2 — Taylor–Maccoll Conical Analysis

**Stage 3 (inlet) of the 2026-07-11 RamP rerun.** Module:
`analyses/propulsion/inlet_performance_v2.py`. Data:
`inlet_performance_v2.csv`.

> **Supersedes, does not overwrite,** the earlier
> `analyses/propulsion/inlet_performance.py`, which used a 2-D wedge
> theta-beta-Mach stand-in for the axisymmetric conical shock. That earlier FAIL
> result is kept and referenced (see `inlet_results.json`, the 4-cone chain
> recovery 0.874); this v2 redoes the external cone with proper Taylor–Maccoll
> conical flow.

## Why the wedge model was wrong for this geometry

A 2-D wedge detaches at ~29.8° flow deflection at Mach 2.5. The as-drawn spike
half-angle is **42°**, so a wedge model would (wrongly) predict a **detached**
shock. The true axisymmetric **Taylor–Maccoll** solution keeps the shock
attached up to a **~46.1° cone half-angle** at Mach 2.5 — so the 42° cone is
**attached** at design. Getting this right is the whole reason for the redo.
(Solver validated: M1=2.0, 20° cone → β=37.80°, matching Anderson's tables.)

## Geometry interpretation (drawing ambiguity)

`drawing_dimensions_raw.yaml` gives external cone 42°, internal 60°, centerbody
85×62 mm, but flags the physical mapping as unsettled. Two readings of "42°" are
evaluated: **42° as the half-angle** (as dimensioned) and **21° half-angle**
(42° read as the *included* angle). The internal 60° surface is treated as the
cowl / subsonic-diffuser contour — after the strong 42° external shock the flow
is only weakly supersonic (M≈1.12), so a second *attached* 60° compression cone
is not physical.

## Results (recovery chain vs MIL-E-5007D reference GOAL)

MIL-E-5007D reference: `pt2/pt0 = 1 − 0.075(M−1)^1.35` (≈ **0.870** at M2.5).
Reported as a **reference goal**, not a hard pass/fail limit.

| M0 | cone | attached | β [°] | M behind cone | pt_conical | **overall recovery** | MIL ref | meets goal |
|---:|-----:|:--------:|------:|--------------:|-----------:|---------------------:|--------:|:----------:|
| 2.5 | 42° | yes | 58.5 | 1.122 | 0.660 | **0.639** | 0.870 | no |
| 2.0 | 42° | **NO (detached)** | – | – | – | 0.699 (bound) | 0.925 | no |
| 3.0 | 42° | yes | 54.5 | 1.313 | 0.522 | 0.495 | 0.809 | no |
| 2.5 | 21° | yes | 33.5 | 2.015 | 0.963 | 0.667 | 0.870 | no |
| 2.0 | 21° | yes | 38.7 | 1.662 | 0.987 | 0.834 | 0.925 | no |
| 3.0 | 21° | yes | 30.6 | 2.339 | 0.922 | 0.506 | 0.809 | no |

## Which failure modes most plausibly explain the shortfall

1. **A single external cone + one terminal normal shock cannot stage the
   compression enough.** Both interpretations fall below MIL at every Mach. This
   is the same physics that earlier drove the design to a **4-cone chain**
   (recovery 0.874, on-spec — assumptions A9). The as-drawn 42°/60° two-surface
   intake sits between "single cone" and that staged chain; its true recovery
   needs the **internal duct area schedule** (60° cowl contraction), which the
   drawing does not give → **PROVISIONAL**, flagged for the inlet-schema work.
2. **42° reading → strong, near-detachment conical shock.** β=58.5° at M2.5 is
   nearly normal (only ~4° of margin to the 46° detachment limit), so most of
   the loss is in that one strong shock (pt_conical=0.66). **Buzz-sensitive.**
3. **21° reading → weak cone but strong terminal shock.** The cone barely
   compresses (M still 2.0 behind it), so the terminal normal shock is strong
   (pt≈0.71). Loss just moves downstream.

## Off-design / starting and buzz (research finding Section 3)

- **The 42° cone DETACHES at M2.0.** The attached-shock limit falls below 42° for
  M ≲ 2.1, so below ~M2.1 the intake runs with a **bow shock → subcritical
  spillage → buzz risk** (Ferri–Nucci). **Implication for staging:** the
  booster→ramjet transition Mach must stay **above ~2.1–2.2** for the intake to
  start on the 42° reading. This is a hard constraint the earlier wedge model
  could not have surfaced (it declared 42° detached even at M2.5).
- **Shock-on-lip: UNVERIFIED / PROVISIONAL.** The cowl-lip radial position is
  not in the drawing data, so whether the conical shock lands on the lip at
  design cannot be confirmed here.
- **No boundary-layer bleed modeled** → every recovery above is **optimistic**;
  the real inlet with a turbulent boundary layer on the long spike will do worse.

## Provisional inputs

| Parameter | Value | Source | Resolves when |
|---|---|---|---|
| cone half-angle interpretation | 42° and 21° both evaluated | drawing ambiguity | human reads the PDF callout |
| subsonic-diffuser pt ratio | 0.97 | typical short annular diffuser | internal duct modeled |
| internal 60° contraction loss | not modeled | needs duct area schedule | inlet-geometry schema |
| gas | air, γ=1.40 | cold inlet | — |

## Next human action

Confirm the 42° vs 21° drawing reading; design the InletGeometry schema so the
60° internal contraction can be modeled (moving beyond single-cone + normal
shock toward the staged recovery the 4-cone chain already achieves); and treat
**M≈2.1 as the minimum starting Mach** for the intake pending that work.
