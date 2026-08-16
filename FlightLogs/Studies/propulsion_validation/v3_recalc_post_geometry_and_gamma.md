# V3 Recalculation — Post-Geometry (AR=1.317) + Station-Gamma Rebuild

**Stage 2 of the 2026-07-11 RamP full-analysis rerun.**
Model: `analyses/propulsion/cycle_v2/hp_stream_thrust_cycle.py` (Heiser & Pratt
stream-thrust station cycle, station-wise gamma). Sweep driver:
`analyses/propulsion/validation/gamma_sensitivity.py`. Data:
`v3_recalc_post_geometry_and_gamma.csv`, `gamma_sensitivity.csv`.

> **HR-7 status: `RECALCULATED_WITH_CORRECTED_GAMMA_AND_GEOMETRY`,** still
> pending independent verification (a real NASA-CEA run and/or SU2). This is
> NOT "problem solved" — a residual delta vs CFD remains (below).

## What changed vs the legacy model

| | Legacy (Grzywka / combustor_nozzle_cycle) | cycle_v2 (this rebuild) |
|---|---|---|
| Ratio of specific heats | ~constant (cold 1.4 / hot 1.33) | **station-wise**: cold 1.40, hot swept 1.20–1.40 (nominal 1.28) |
| Nozzle expansion | fully expanded to p0 (**implied** A3/A21 ≈ 2.44) | **real finite** area ratio A_e/A_t = **1.317** (drawing) |
| Exit state | p3 = p0 by construction | p_exit solved from AR → **under-expanded**, p_e/p0 ≈ 3.0 |
| Pressure thrust | implicitly zero | **explicit** `(p_e − p0)·A_e` term retained |

## Headline result (nominal γ_hot = 1.28)

- **V3 = 1200 m/s** (was 1474 m/s legacy → **−18.6 %**).
- **vs Teltik CFD 1047 m/s: +14.6 %** — down from the legacy **+40.8 %**.
- Exit Mach 1.643; **under-expanded** (p_e/p0 ≈ 2.99).
- Thrust hierarchy (holds by construction) Thi ≥ Th1 ≥ Th2 =
  11 801 / 11 606 / **11 439 N** (nominal Th2). Of Th2, momentum ≈ 7 854 N and
  **pressure thrust ≈ 3 585 N** — a contribution the legacy fully-expanded
  model structurally omitted.

## Gamma sensitivity sweep (AR fixed at 1.317, Tt4 = 2000 K)

| γ_hot | V3 [m/s] | M_exit | p_e/p0 | Th2 [N] | ΔV3 vs MATLAB | ΔV3 vs Teltik |
|------:|---------:|-------:|-------:|--------:|--------------:|--------------:|
| 1.20 | 1196.9 | 1.620 | 3.19 | 12365.7 | −18.8 % | +14.3 % |
| 1.25 | 1198.9 | 1.635 | 3.06 | 11739.0 | −18.7 % | +14.5 % |
| 1.30 | 1200.6 | 1.649 | 2.94 | 11261.6 | −18.5 % | +14.7 % |
| 1.35 | 1202.0 | 1.663 | 2.82 | 10873.0 | −18.5 % | +14.8 % |
| 1.40 | 1203.1 | 1.678 | 2.71 | 10543.2 | −18.4 % | +14.9 % |

V3 is **monotonic (weakly increasing) in γ** and positive for all γ.

## The important, non-obvious finding

The 2026-07-11 research finding named the legacy **constant γ = 1.4 as the
primary suspect** for the +40.8 % V3 gap. This rebuild does not support that as
the dominant lever:

- **V3 moves only ~0.5 % across the entire γ ∈ [1.20, 1.40] sweep** at fixed
  geometry. Gamma is a *weak* lever on exit velocity here.
- **The nozzle area-ratio correction is what closed the gap.** Replacing the
  legacy fully-expanded (implied AR ≈ 2.44) assumption with the real AR = 1.317
  drops the 1-D exit velocity from 1474 to ≈ 1200 m/s (−18.6 %), i.e. ~26 of the
  ~41 gap-points. Gamma contributes < 1 point.
- A **residual +14.6 % vs Teltik CFD remains** at every γ. Because cycle_v2 is a
  1-D calorically-perfect model, this residual is the expected home of effects
  it cannot capture: nozzle boundary-layer / divergence losses, real-gas /
  variable-cp and dissociation, spillage, and CFD's own modeling. It should be
  closed by a real CEA run (variable-cp, dissociation) and/or SU2, **not** by
  tuning γ.

## Provisional inputs used (see docs/assumptions.md)

| Parameter | Value | Source / justification | Resolves when |
|---|---|---|---|
| γ_hot (nominal) | 1.28 (sweep 1.20–1.40) | CEA-class kerosene-air products ~2000–2400 K (A19) | real NASA-CEA run |
| Fuel LHV | 43.0 MJ/kg | standard kerosene/Jet-A | fuel confirmed |
| Tt4 | 2000 K | config `combustor_temp_K` (below ~2400 K flame-holder risk) | combustor test data |
| η_inlet | 0.8741 | 4-cone inlet chain (A9) | Stage 3 inlet_v2 supersedes |
| π_CC / π_nozzle | 0.8924 / 0.97 | Grzywka (A13) | — |
| ṁ_air | 15.167 kg/s | rho0·u0·A_capture (full capture) | inlet capture confirmed |

**Derived (not assumed):** f_fuel_air ≈ 0.055 (energy balance) ⇒ equivalence
ratio φ ≈ 0.8 relative to stoichiometric kerosene-air (f_st ≈ 0.068) — consistent
with a lean-to-moderate ramjet burner reaching Tt4 = 2000 K.

## Coupling to Stage 3 (nozzle)

The nozzle is **under-expanded (p_e/p0 ≈ 3)** at 10 km on the corrected geometry.
The Stage 3 nozzle over/under-expansion check MUST use this same station γ (not
1.4) and the same AR = 1.317, and should expect under-expansion across the whole
plausible altitude band (it only worsens with altitude as p0 falls).
