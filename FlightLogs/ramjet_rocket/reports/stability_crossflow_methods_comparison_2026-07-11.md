# MELprop-IADE | ramP Stage-1 stability — two independent DATCOM-class implementations compared | 2026-07-11

Two parallel cloud sessions independently implemented the Stage-1 DATCOM-class
supersonic component buildup (`analyses/stability/datcom_class_sweep.py`,
`ackeret_fin_check.py`) on the same day, from the same research plan. The
version that landed on `main` (session `up6lcz`, see the
`2026-07-11 — Stage 1 — Barrowman supersonic retired as CDR stability gate`
decision-log entry) is the one in the codebase. This note documents the
**other** session's (`nkqwp1`) independent implementation as an alternate
cross-check, per the team's "keep all ideas documented" policy — it was not
merged as code (it would have silently replaced the reviewed `main` module),
but its numbers and modeling choice are worth recording since they bear on
how much confidence to place in the Stage-1 result.

## The one real modeling disagreement: the body viscous-crossflow term

Both implementations build the same three components (nose, shoulder
transition, supersonic fins) but differ on the Allen–Perkins body
viscous-crossflow term, which is proportional to `sin^2(alpha)`:

- **`main` (up6lcz):** notes that the crossflow term's contribution to the
  *linear* (`alpha -> 0`) `CN_alpha` slope is exactly zero (the derivative of
  `sin^2(alpha)` at `alpha=0` is zero), and excludes it from the static-margin
  buildup entirely. This is the more conservative, textbook-defensible choice
  for a linear static-margin calculation.
- **`nkqwp1` (this note):** linearized the term at a finite trim angle
  (`alpha_ref = 4 deg`, a DATCOM/RASAero convention for getting an "effective"
  slope usable at a representative trim condition) using the **secant** slope
  `delta_CN(alpha_ref) / alpha_ref` — the term's value at the picked angle
  divided by that angle, so the combined CP is evaluated at `alpha_ref` rather
  than at the mathematical zero. This adds a small destabilizing (CP-forward)
  body contribution that `main`'s zero-crossflow choice omits.

Both are legitimate, defensible engineering choices — the disagreement is
about **which angle the static margin is meant to represent** (the strict
linear limit vs. a representative small-trim condition), not a bug in either
implementation.

## Numbers, side by side (Mach 2.5, CG = 1.6084 m, current `main` geometry)

Run directly against `main`'s current modules for the numbers in the first two
rows (verified this session):

| Quantity | `main` (zero-crossflow) | `nkqwp1` (secant crossflow @ 4°) |
|---|---|---|
| Body `CN_alpha` [1/rad] | 2.00 (nose 1.125 + transition 0.875) | 3.56 (2.00 potential + 1.56 crossflow) |
| Fin `CN_alpha` [1/rad] | 11.59 (Puckett tip-loss) | 23.19 (different finite-span/interference model) |
| Combined `x_cp` [m from nose] | 3.813 | 3.984 |
| **DATCOM static margin** | **+11.02 cal** | **+11.92 cal** |
| **Ackeret static margin** (independent hand-check) | +9.71 cal | +12.29 cal |

**Both implementations agree in sign (large positive / stable) and are within
~2 cal of each other** — a useful independent cross-check that the DATCOM-class
methodology itself is not wildly implementation-sensitive, even though the two
sessions made different choices for the fin finite-span correction and the
crossflow linearization.

## This does NOT change the Stage-1 gate status

Per the existing `main` decision-log addendum ("Stage 1 gate is NOT green"):
both linear analytical methods place the (very large, semi-span/body-dia=2.75)
fins' CP far aft and conflict in sign with the Teltik 2024 CFD result
(−2.75 cal, unstable at Ma 2.5). This note's alternate numbers **reproduce the
same structural disagreement** — a second independent implementation landing
in the same +9…+12 cal band as the first is *more* evidence that the
disagreement with CFD is a fidelity-class limitation of linear supersonic
theory on oversized fins, not an implementation bug in either version. The
CDR gate remains **NOT SATISFIED pending SU2** (BLOCKED_BY_ENVIRONMENT in every
cloud session so far — next human action: run the SU2 RANS-SST cross-check
locally).

## Provenance

- `nkqwp1` branch: `claude/ramp-full-analysis-rerun-nkqwp1`, commit history
  through `0d55435` (implementation) and `427ea59` (this session's own
  crossflow-formula correction, catching a distinct secant-vs-tangent slope
  error in an earlier draft of the same implementation — see that branch's
  `docs/decision-log.md` for the fix detail).
- `main`'s current modules: session `up6lcz`, PR #4.
- CG sweep ranges differ by convention: `nkqwp1` swept absolute CG
  1.40–2.20 m; `main` sweeps CG as a fraction of total length,
  [0.37, 0.45, 0.55, 0.64] -> 1.61–2.79 m. The overlap band (1.61–2.20 m)
  is where both results are directly comparable.
