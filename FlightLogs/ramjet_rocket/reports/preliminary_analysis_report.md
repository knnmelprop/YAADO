# MELprop ramP — Preliminary Analysis Report

**Date:** 2026-07-08
**Vehicle:** MELprop-Ramjet-Missile — two-stage supersonic rocket (solid booster + ramjet cruise)
**Geometry source:** Fusion 360 Assembly v6 (CORRECTED: cm→m, Y-axis longitudinal)
**Fidelity:** low-order engineering estimates (L0–L1) — **not** flight-safety sign-off.

---

## 1. Vehicle Dimensions (from Fusion)

| Parameter | Value | Source |
|---|---|---|
| Total length | 4.377 m | Fusion Y-bbox |
| Max transverse dimension | 0.639 m | Fusion X/Z-bbox |
| Body diameter (aero ref) | 0.250 m | body |
| Nose (conical spike) | L 0.293 m, base Ø 0.150 m | inlet_cone |
| Total mass | 355.02 kg | Fusion physics |
| CG from nose | 1.6084 m (36.7 % L) | Fusion |
| Booster assembly | L 2.089 m, bbox Ø 1.809 m (incl. PRD-240 wings) | booster |
| Fins | 4× rectangular, span 0.6685 m, chord 0.1768 m, sweep 0° | stabilizers |
| Ramjet capture area | 0.04909 m² (= π/4·0.250²) | inlet_Mk1 |

> **Booster bbox note.** The 1.809 m booster "diameter" is a bounding-box artifact of the
> protruding PRD-240 reference wings; the aerodynamic reference diameter is the 0.250 m body.

---

## 2. Stability Assessment

Method: subsonic Barrowman (nose + 0.150→0.250 shoulder transition + cruciform fins with
Hoerner body-interference) plus a Rogers-style transonic/supersonic fin-slope correction.
Full data: [`analyses/stability/barrowman_results.json`](../../analyses/stability/barrowman_results.json).

| Quantity | Value |
|---|---|
| CP (subsonic, M→0) | **4.128 m** from nose |
| CP (transonic, M=1.0) | 4.155 m from nose |
| CG | 1.6084 m from nose |
| Static margin (subsonic) | **10.08 cal** |
| Fineness ratio L/d | 17.51 |
| Required SM = L/(10·d) | 1.75 cal |
| Margin over requirement | +8.33 cal |
| **Verdict** | ✅ **PASS** |

The huge exposed fin span (2.67× body diameter) makes the fins dominate CN_α, driving CP far
aft and yielding a very large — arguably *over*-stable — margin. Physically this fin set reads
more like a booster-glide surface than a dart fin.

![CP vs Mach](../../analyses/stability/cp_vs_mach.png)

---

## 3. Boost Phase Trajectory

Method: 3-DOF point mass (vertical plane), `scipy.solve_ivp` RK45, manual ISA atmosphere,
DATCOM-style CD, mass depletion. Full data:
[`analyses/trajectory/burnout_state.json`](../../analyses/trajectory/burnout_state.json).

| Quantity | Value |
|---|---|
| Thrust used | **25.4 kN** (impulse-consistent, Isp·ṁ·g₀) |
| Burn cutoff | **t = 4.53 s** (⚠️ ground impact, before 6 s burnout) |
| Velocity at cutoff | 350 m/s (**Mach 1.03**) |
| Altitude at cutoff | ≈ 0 m (from h₀ = 100 m) |
| Max dynamic pressure | **75.0 kPa** |
| Range at cutoff | 771 m |

> ⚠️ **0° horizontal launch is not viable as modeled.** With gravity, no lift, and h₀ = 100 m,
> the rocket sinks to the ground at t ≈ 4.5 s — *before* the nominal 6 s burnout. A real launch
> needs a positive launch angle and/or lift. The along-track state is reported honestly at impact.
>
> ⚠️ **Thrust inconsistency.** `vehicle_config.yaml` lists `thrust_peak_N = 12000`, but 75 kg of
> propellant over 6 s at Isp 207–230 s implies a **mean** thrust of ~25.4 kN — a peak below the
> mean is impossible. The sim used the impulse-consistent 25.4 kN and ignored the 12 kN figure.

![Boost phase](../../analyses/trajectory/boost_phase.png) <!-- TODO: dead link, target missing as of 2026-07-09 -->

---

## 4. Inlet Performance

Method: axisymmetric conical-spike inlet at design Mach 2.5 — oblique shock (θ-β-M weak
solution) + terminating normal shock + diffuser efficiency, vs the MIL-E-5007 standard.
Full data: [`analyses/propulsion/inlet_results.json`](../../analyses/propulsion/inlet_results.json).

| Quantity | Value |
|---|---|
| Spike half-angle | 14.36° |
| Oblique shock angle β | 36.25° |
| Mach after oblique / normal shock | 1.90 → 0.60 |
| Pressure recovery (oblique·normal·η_diff) | 0.937 · 0.767 · 0.92 = **η_inlet 0.661** |
| MIL-E-5007 standard | η_std 0.870 |
| Mass flow at design (10 km ISA) | 15.17 kg/s |
| **Verdict** | ❌ **FAIL** (margin −0.210) |

A single-cone (one oblique + one normal shock) spike is minimum-part-count and predictably falls
short of MIL-E-5007 at M 2.5. This motivates a **multi-shock (2–3 cone) or isentropic spike** for
a production inlet. The θ-β-M wedge stand-in for the true Taylor–Maccoll conical shock makes the
reported recovery slightly *conservative*.

![Inlet recovery](../../analyses/propulsion/inlet_recovery.png)

---

## 5. Open Issues & Next Steps

- [ ] Replace **R-13 mockup** with a real motor datasheet (resolves the 12 kN vs 25 kN thrust conflict).
- [ ] Re-run the trajectory with a **positive launch angle** and/or a lift model (0° horizontal is non-viable).
- [ ] Redesign the **ramjet inlet** (multi-shock/isentropic spike) to meet MIL-E-5007 at M 2.5.
- [ ] Redesign the **cylindrical nozzle** (area ratio 1.0) into a Laval nozzle for the cruise stage.
- [ ] Run **XFOIL** fin polar at M 2.5 (double-wedge) — `analyses/aero/xfoil_runner.py` (STUB).
- [ ] Generate the **AVL** subsonic deck, compute Cmα / CLα — `analyses/aero/avl_builder.py` (STUB).
- [ ] Run **SU2** external-aero Mach sweep [0.8–3.0] — `analyses/cfd/su2_config_template.py` (STUB).
- [ ] Extract **moments of inertia** Ixx/Iyy/Izz from the Fusion GUI (not available via API).
- [ ] Model the full **ramjet cycle** (combustor + nozzle), currently inlet-only.
- [ ] Wind-tunnel / water-tunnel (WUT) validation of the transonic CP estimate.

## 6. TBD Parameters (from `vehicle_config.yaml`)

- Stage-1 motor datasheet: Isp, thrust curve, propellant mass — currently `SZACOWANY` (estimated).
- Stage-2 ramjet `design_mach` — final decision pending (2.5 assumed).
- Moments of inertia Ixx/Iyy/Izz — from Fusion GUI.
- Combustor exit temperature — pending pyCycle cycle analysis (2000 K assumed).

---

## Night-3 Results (2026-07-09)

**Combustor + nozzle cycle (Grzywka model):** Merged PR #13 introduces `analyses/propulsion/combustor_nozzle_cycle.py`, implementing Grzywka 2022 stations (CC → NT → NE) with loss coefficients π_CC = 0.8924, π_nozzle = 0.97. At Ma 2.5 cruise design point: thrust hierarchy Thi = 12467.6 N, Th1 = 12107.9 N, Th2 = 12009.0 N all consistent; Brayton-cycle Tt2 estimate 2250.7 K; exit velocity V3 = 1474.3 m/s vs Teltik 2024 CFD reference ~1047 m/s yields delta **+40.8%**, exceeding the known 20–30% MATLAB-vs-CFD scatter band. ⚠️ **HUMAN_REVIEW** flagged — recommend corroboration with full-fidelity CFD (SU2) before accepting cruise thrust numbers.

**Cruise-stage wiring:** Module `workflows/ramp_staged_mission.py` now routes nominal cruise design point through Th1 (intermediate thrust model). Net thrust margin at Ma 2.5 cruise = **+10120.9 N** against 0-order drag estimate (CD0 = 0.35 SZACOWANY, FD = 1987.1 N) and **+9656.0 N** against Teltik CFD drag estimate (FD = 2451.95 N). Full per-altitude / per-Mach tables and sensitivity summary at `docs/ramP/cruise_summary_night3.md`.

**Inlet actuation schedule:** Module `analyses/propulsion/inlet_actuation.py` implements 4-cone variable-geometry spike (throat-area modulation Δθ per cone) spanning Mach 1.0–3.5. MIL-E-5007 η ≥ 0.870 is met **contiguously** only on Mach [2.4, 3.5] (example: Ma 2.5, η_achieved = 0.8741 vs η_std = 0.8703, margin +0.0038). Below ~Ma 2.4, current geometry cannot achieve standard even with full cone deflection. Actuation range per cone: cone 1 Δθ = 3.5°, cone 2 Δθ = 8.3°, cone 3 Δθ = 15.2°, cone 4 Δθ = 24.3°.

**Solid motor database:** Module `vehicles/ramjet_rocket/motor_database.yaml` populated with 3 reference-class HTPB candidates (mean thrust 20–30 kN, burn duration 5–8 s, Isp 205–230 s). All entries marked **SZACOWANY** (estimated from literature correlations). Real R-13 (or equivalent booster-class) datasheet remains outstanding — TODO_PHYSICAL_PARAM in the config.

**Fin airfoil polar (supersonic):** Module `analyses/aero/xfoil_runner.py` implements Ackeret supersonic-wedge fallback (pending XFOIL binary availability). Example result at Ma 2.5, α = 5°: CL = 0.1523 (verified vs hand calculation), CD includes compressibility + thickness term with τ = 0.1697 (Fusion v6 fin t/c). XFOIL delegation pathway awaits external binary; Ackeret results serve as L0 placeholder.

**Launch-angle sensitivity sweep:** Module `analyses/trajectory/booster_burnout.py::run_launch_angle_sweep` executed sweep over launch angles 5–30° (step 5°); all swept angles avoid premature ground impact. Recommended angle = **5.0°** (smallest viable, burnout state: Mach 1.367, altitude 45.3 m, downrange 1363.6 m, max dynamic pressure 131.75 kPa). Horizontal launch (0°) confirmed non-viable: rocket hits ground at t ≈ 4.51 s. Module nominal run retains near-vertical 83° rail-launch angle for mission-test backward compatibility; override via `launch_angle_deg` config parameter.

---

*Generated by the MELprop-IADE analysis pipeline (Grzywka ramjet cycle, 4-cone variable inlet, fin airfoil Ackeret, launch-angle sweep).
All results are low-order preliminary estimates pending CFD / wind-tunnel corroboration and real motor data.*
