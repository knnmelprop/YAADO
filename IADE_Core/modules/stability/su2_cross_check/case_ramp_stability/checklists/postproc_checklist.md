# Post-processing checklist — CP / CN / CM & static-margin sign check

Goal of this whole case: an **independent** confirmation of the stability
sign (statically stable vs unstable) that does NOT rely on Barrowman
(retired > Ma 0.7) — a CFD cross-check of DATCOM-class + Ackeret.

## Convergence sanity (do first)
- [ ] `RMS_DENSITY` reached `CONV_RESIDUAL_MINVAL` (-8) OR plateaued cleanly.
- [ ] Force/moment monitors (LIFT, DRAG, MOMENT_Z) flat over last ~500 iters.
- [ ] No unphysical oscillation from the entropy fix / limiter.

## Coefficients (from `forces_breakdown.dat` + `history.csv`)
- [ ] Extract CL, CD, CMz per AoA (post/postprocess_coeffs.py).
- [ ] Convert to body axes: CN (normal), CA (axial) from CL/CD & AoA.
- [ ] CN_alpha from the {0,4,8}° sweep (linear fit through small AoA).
- [ ] CMz_alpha about the REF_ORIGIN_MOMENT (the CG used).

## CP & static margin
- [ ] X_cp = REF_ORIGIN_MOMENT_X − CMz / CN  (consistent length convention).
- [ ] Static margin (calibers) = (X_cp − X_cg) / body_diameter.
- [ ] **Sign check:** SM > 0 ⇒ statically stable. Report the sign explicitly.
- [ ] If CG is swept (unknown CG), report SM as a **band** vs CG, and the
      CG at which the sign flips (neutral point).

## Cross-checks & V&V
- [ ] Compare CN_alpha / X_cp against DATCOM-class (`datcom_class_sweep.py`)
      and Ackeret (`ackeret_fin_check.py`) at the same Mach.
- [ ] SA vs SST agreement — if the sign is near-neutral, both models must
      agree before the result is anything but PROVISIONAL.
- [ ] GCI on coarse/fine pair; a result is CONFIRMED only with an acceptable
      grid-convergence index (Roache/Celik).
- [ ] CP distribution plotted on nose / interstage / base (surface_flow.csv).

## Reporting
- [ ] Record Mach, altitude, AoA sweep, CG (or CG band), mesh levels, y⁺.
- [ ] Mark result PROVISIONAL until GCI + model cross-check both pass.
- [ ] Append one decision line to `docs/decision-log.md`.
