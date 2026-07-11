# CO2 Surrogate vs Reacting Kerosene — Known Limitation (NOT a validated capability)

**Stage 4 of the 2026-07-11 RamP rerun (research finding Section 5).** Calc:
`analyses/cold_flow/co2_surrogate_mismatch.py`.

## What cold-flow CO2 + optics DOES verify (well)

- **Shock structure** — external conical shock angle, shock-on-lip position,
  internal shock train, terminal-shock location (Schlieren / shadowgraph).
- **Gross total-pressure recovery** — AIP rake + wall static taps give the
  actual pt2/pt0 to compare against the Taylor–Maccoll prediction
  (`inlet_performance_v2.md`) and the MIL-E-5007D reference goal.
- **Started/unstarted and buzz** — onset of the subcritical bow-shock / buzz
  the analysis flags for M ≲ 2.1 can be observed directly.

## What it does NOT verify (the limitation)

Cold CO2 injection does **not** reproduce the mixing of the reacting kerosene-air
flow. The jet-in-crossflow similarity parameters — **density ratio** and
**momentum-flux ratio** `J = ρ_jet·u_jet² / ρ_cross·u_cross²` — are far apart
between a cold surrogate and hot reacting products.

Screening estimate (PROVISIONAL conditions: combustor static ~350 kPa, 560 K
crossflow, equal 150 m/s injection velocity — see the module docstring):

| quantity | value |
|---|---:|
| ρ crossflow air | 2.18 kg/m³ |
| ρ cold CO2 surrogate | 6.18 kg/m³ |
| ρ hot reacting products | 0.55 kg/m³ |
| **density ratio (surrogate / reacting)** | **≈ 11×** |
| J surrogate | 4.43 |
| J reacting | 0.40 |
| **momentum-flux-ratio mismatch** | **≈ 11×** |

At equal injection velocity the cold CO2 jet is ~11× denser and carries ~11× the
momentum flux of the hot products, so its **penetration depth and large-scale
mixing are not representative**. Matching J (by lowering the surrogate injection
velocity/pressure) forces a large density-ratio mismatch instead — you cannot
match both with a cold gas. Heat-release effects (dilatation, volume production,
flame-anchoring recirculation) are absent entirely.

## Consequence / how to use cold-flow mixing data

- Treat cold-flow CO2 mixing/penetration data as **qualitative / screening only**
  for the later kerosene flight — good for "does the injectant reach the core"
  yes/no screening and PIV/PLIF rig commissioning, **not** for quantitative
  mixing-efficiency or combustion-efficiency prediction.
- Do **not** carry a cold-flow mixing result into the cycle model
  (`cycle_v2`) as a validated combustor input.
- Quantitative reacting-mixing confidence needs a reacting test (or reacting
  CFD / CEA-backed combustor model), not the cold rig.

## Provisional inputs

| Parameter | Value | Source | Resolves when |
|---|---|---|---|
| combustor static p / T | 350 kPa / 560 K | RamP cycle station 2 estimate | combustor CFD/test |
| injection velocity | 150 m/s (equal both jets) | assumed to isolate density | injector schedule |
| products temperature | 2200 K | near-flame estimate | combustor test |
