# RamP Ramjet Inlet — Cold-Flow Test Plan

**Stage 4 of the 2026-07-11 RamP rerun.** Purpose: measure the inlet's shock
structure, total-pressure recovery, and buzz behavior **directly**, rather than
relying only on the analytical Taylor–Maccoll prediction
(`analyses/propulsion/inlet_performance_v2.md`). Companion limitation note:
`analyses/cold_flow/co2_surrogate_mismatch_note.md`.

> Scope: a **non-reacting** (cold-flow) supersonic rig test of the intake at and
> around the design Mach 2.5. What it can and cannot establish is stated up front
> in the limitation note — cold flow verifies shocks/recovery, **not** reacting
> mixing.

## Objectives (tied to the analysis findings)

1. **Total-pressure recovery pt2/pt0** at M2.5 vs the Taylor–Maccoll prediction
   (0.64 for the 42° reading) and the MIL-E-5007D reference goal (0.870).
2. **Shock structure**: external conical shock angle (predicted β≈58.5° for 42°),
   shock-on-lip position (analytically UNVERIFIED — the rig resolves it), and the
   internal shock train / terminal-shock location.
3. **Starting and buzz limits**: confirm the predicted **detachment / non-start
   below M≈2.1** and characterise subcritical buzz onset and frequency.
4. **Cone-interpretation resolution**: distinguish the 42°-half vs 21°-half
   (included-angle) drawing readings by the measured shock angle.

## Instrumentation

### AIP total-pressure rake (recovery)
- Rake at the aerodynamic interface plane (engine face / diffuser exit).
- Pitot/total-pressure probes on an **area-weighted pattern** — concentric rings
  at the equal-area radii (e.g. 5 rings × 8 rakes = 40 probes) to resolve profile
  distortion (DC60-style), not just a mean.
- Reference freestream total pressure from a settling-chamber pitot + the tunnel
  nozzle calibration; recovery = area-averaged pt_AIP / pt0.

### Static-pressure taps (compression path + throat)
- **Centerbody (spike)** static taps along the 42°/60° cone generators to map the
  conical-shock and isentropic-compression pressure rise.
- **Cowl internal** static taps through the throat and subsonic diffuser to
  locate the terminal shock and quantify diffuser recovery.
- Taps at ≥ 2 azimuths to check axisymmetry / flow asymmetry.

### High-speed Schlieren / shadowgraph (shock structure + buzz)
- Z-type schlieren, twin f/8 parabolic mirrors, spark or continuous LED source.
- **High-speed camera ≥ 20 kHz** to resolve buzz cycles (expel/swallow of the
  terminal shock) and measure buzz frequency; horizontal knife-edge for the
  streamwise density gradients of the conical shock.
- Optical access windows spanning the spike tip through the cowl lip.

### Dynamic pressure (buzz)
- Fast-response (Kulite-class) transducers on the cowl and centerbody near the
  throat to time-resolve buzz pressure oscillations and correlate with Schlieren.

## Test matrix

| Run group | Mach | What it establishes |
|---|---|---|
| Design point | 2.5 | recovery, shock-on-lip, β vs 42°/21° prediction |
| Start/buzz sweep | 2.5 → 1.8 (descending) | detachment / non-start (predicted ~2.1), buzz onset |
| Off-design high | 3.0 | recovery trend (predicted worse) |
| Backpressure sweep | 2.5, vary exit throttle | critical→subcritical transition, buzz margin |

## Explicit limitations (see the mismatch note)

- **Cold-flow CO2 / tracer mixing data is qualitative/screening only** for the
  reacting kerosene flight: the surrogate–reacting **density ratio and
  momentum-flux ratio differ by ~11×** (`co2_surrogate_mismatch.py`). Do not use
  cold-flow mixing to predict combustion efficiency.
- **No boundary-layer bleed** in either the analysis or (unless added to the rig)
  the model → recovery numbers are optimistic; a bleed configuration should be a
  planned rig variable.
- Reynolds-number / wall-temperature matching between the cold rig and flight is
  imperfect — boundary-layer state (and thus shock–BL interaction and recovery)
  will differ; note it when comparing rig recovery to flight.

## Next human action

Confirm rig Mach capability and optical-access geometry; fix the AIP rake radii
to the actual diffuser-exit diameter; and set the backpressure/throttle hardware
so the critical→subcritical (buzz) boundary predicted near M2.1 can be traversed
safely.
