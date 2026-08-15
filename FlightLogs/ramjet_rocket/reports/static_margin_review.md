# ramP — Static Margin Review (Barrowman sanity check)

**Date:** 2026-07-08
**Author:** aero-analyst subagent (MELprop-IADE)
**Data sources:**
- `analyses/stability/barrowman_stability.py` (Barrowman + Rogers-extension implementation, re-run read-only for this review)
- `vehicles/ramjet_rocket/vehicle_config.yaml` (reconciled engineering config, v0.2.0)
- `vehicles/ramjet_rocket/fusion_extraction_v6.yaml` (raw Fusion Assembly v6 export, "CORRECTED VERSION", 2026-07-08)
- Re-run output: `analyses/stability/barrowman_results.json`, `analyses/stability/cp_vs_mach.png`

Scope note: this review is analysis-only. No code, YAML, or geometry files were modified. Any fin-geometry change implied below is a **recommendation for the vehicle-builder / mechanical team to evaluate**, not an action taken here.

---

## 1. Baseline result (confirmed by re-run)

Re-running `barrowman_stability.py` against the current `vehicle_config.yaml` reproduces the reported numbers:

| Quantity | Value |
|---|---|
| CP (subsonic, M=0) | 4.128 m from nose |
| CG | 1.6084 m from nose (Fusion Assembly v6) |
| Body diameter (d_ref) | 0.250 m |
| Static margin (subsonic) | **10.078 calibers** |
| Static margin (M=1.0, transonic peak) | 10.187 cal |
| Static margin (M=2.5 cruise) | 8.986 cal |
| Verdict from `validate_results()` | PASS (analytical cross-checks only; does not check "is 10 cal reasonable") |

The 1–2 caliber "typical safe range" quoted in the task is the standard amateur/professional rocketry design target (enough margin for wind-cocking recovery without excessive weathercocking). At **~9–10 cal**, this vehicle is roughly **5x** past the upper end of that band at every Mach number in the flight envelope, including at the M=2.5 cruise condition.

## 2. Per-component CN_alpha breakdown (Barrowman)

At M=0 (subsonic anchor):

| Component | CN_alpha [1/rad] | x_cp [m from nose] | Share of total CN_alpha |
|---|---|---|---|
| Nose (cone) | 0.72 | 0.137 | 1.1% |
| Nose-body transition (shoulder) | 1.28 | 0.347 | 1.9% |
| **Fins (4x)** | **66.21** | **4.244** | **97.1%** |
| **Total** | **68.21** | **4.128** (weighted) | 100% |

The fins alone contribute 97% of the vehicle's total normal-force-curve slope and, because their CP (4.244 m) sits almost at the tail while the body-alone CP (nose+transition combined, ~0.9 CN_alpha at x≈0.27 m) sits near the nose, the fins single-handedly drag the combined CP from ~0.27 m (body-only) out to 4.128 m — i.e. essentially all of the 10 cal of margin above what the bare body-of-revolution would give is attributable to the fin set. This is the classic signature of a fin set sized far beyond what is needed for the mission: the nose+transition (the parts of the geometry least likely to contain an export error, since they come from well-defined conical dimensions) contribute almost nothing, while the fins (span 0.6685 m — 2.674x the 0.250 m body diameter) dominate completely.

## 3. Fin-span sensitivity (everything else held fixed)

Re-running `compute_stability_at_mach()` with only `fin_span_m` varied (body, nose, CG, chords, sweep all unchanged) gives:

| Fin span [m] | span / d_ref | CN_alpha (fins) | Static margin [cal] |
|---|---|---|---|
| 0.6685 (current) | 2.674 | 66.21 | **10.078** |
| 0.500 | 2.000 | 38.40 | 9.757 |
| 0.300 | 1.200 | 14.91 | 8.664 |
| 0.150 | 0.600 | 4.19 | 5.408 |
| 0.100 | 0.400 | 1.99 | 2.580 |
| **0.090** | **0.360** | **1.64** | **1.811** |
| **0.085** (interp.) | 0.340 | ~1.5 | ~1.6 |
| 0.080 | 0.320 | 1.32 | 0.967 |
| 0.070 | 0.280 | 1.03 | 0.051 (neutral) |
| 0.060 | 0.240 | 0.77 | -0.922 (unstable) |

**A fin span of roughly 0.085–0.093 m (span/d_ref ≈ 0.34–0.37, i.e. exposed span ≈ one-third of the body diameter) would place the static margin in the requested 1.5–2.0 cal band, with every other dimension in this analysis unchanged.** That is a reduction of roughly **7.2x–7.9x** from the current 0.6685 m fin span.

This ratio is numerically striking: **0.6685 m / 10 = 0.06685 m**, which falls right at the computed neutral-to-marginally-stable point (span 0.065–0.070 m gives SM ≈ -0.4 to +0.05 cal), and a span of ~0.085–0.09 m (i.e. current span divided by ~7.5–8, close to but not exactly a factor of 10) lands in the 1.5–2 cal target band. The raw Fusion export file (`fusion_extraction_v6.yaml`) documents, in its own `corrections` section, that this exact assembly had a **known, already-encountered cm-vs-mm unit bug** ("Fusion API returns dimensions in CENTIMETERS, not millimeters... all conversions now verified: cm -> m") that was caught and fixed for the body/mass properties on this same 2026-07-08 extraction pass. The fin span value (`span_m: 0.6685`, `span_mm: 668.5`) is internally self-consistent (668.5 mm = 0.6685 m, no arithmetic error within the file), so this is **not proof** of a repeated unit error — but the fact that dividing the current span by approximately one order of magnitude produces a textbook-normal static margin, on a component from an assembly that is independently documented to have suffered exactly this class of unit-conversion bug elsewhere, is a strong circumstantial flag rather than a coincidence that should be dismissed.

## 4. CG travel at booster burnout (SZACOWANY)

Per `vehicle_config.yaml`, `stage_1.propulsion.propellant_mass_kg: 75.0` is explicitly marked **SZACOWANY** (estimated, R-13 motor is a Fusion mockup pending datasheet), out of `total_mass_kg: 355.02`. The booster section occupies the aft ~2.089 m of the 4.377 m rocket (`fusion_extraction_v6.yaml`, `dimensional_summary`: ramjet section ≈ 2.288 m from nose, booster section 2.089 m aft of that, i.e. spanning roughly x = 2.288 m to x = 4.377 m).

No propellant-grain centroid location is given anywhere in the repo, so two bounding **SZACOWANY** assumptions are used (mass model, not geometry, not code):

| Assumption | Propellant centroid x [m] | CG at burnout [m] | SM at burnout (subsonic CP) |
|---|---|---|---|
| Centroid at booster mid-length | 3.332 | 1.147 | **11.93 cal** |
| Centroid biased aft (near nozzle/aft dome, x = tail - 0.3 m) | 4.077 | 0.947 | **12.72 cal** |

Both bounding cases **increase** the static margin at burnout relative to the already-excessive 10.08 cal at liftoff, because the burned propellant mass is aft of the CG and removing it pulls the CG forward (away from the aft-mounted CP), increasing CP-CG separation. This is the opposite of the more common rocket failure mode (CG creeping aft and eating the margin); here the vehicle only gets *more* over-stable as the booster burns, reaching an estimated **~12–13 cal by burnout**. This reinforces that the margin problem is dominated by fin sizing, not by CG travel, and that CG travel is not a mitigating factor.

## 5. Consequences of ~9–13 cal static margin at Mach 2.5 cruise

Even setting aside whether the 10 cal figure is a geometry artifact, a static margin this large has real physical consequences for the ramjet cruise stage (M=2.5, `stage_2.design_mach`):

- **Weathercocking:** static margin scales the restoring-moment stiffness (∝ CN_alpha_total x (x_cp - x_cg)); at ~9-10x the target margin, any local flow angularity (wind shear during boost, gust, or an inlet-induced asymmetric flow disturbance) produces a much larger corrective yaw/pitch moment than needed, causing the vehicle to over-rotate into the disturbance ("weathercock") rather than smoothly damping back to zero AoA. This increases trajectory dispersion, not decreases it, despite the vehicle being "very stable" in the linear sense.
- **Trim drag:** the CN_alpha_total at M=2.5 is still ~20.4 /rad (fin_mach_correction_factor = 0.278 at M=2.5, from the re-run above) — any residual trim AoA required to null thrust misalignment, inlet asymmetry, or CG offset is multiplied by this large CN_alpha and by the long CP-CG moment arm, producing more induced (trim) drag at cruise than a fin set sized for ~1.5-2 cal would. At Mach 2.5 this drag penalty is compounded by wave drag on the oversized fins themselves (4 fins, each spanning 2.674x body diameter, exposed to the full cruise dynamic pressure).
- **Gust/disturbance response:** high static margin raises the aerodynamic pitch/yaw stiffness, which raises the natural weathercock frequency; combined with the large fin area (and its own added mass/damping), the short-period response, while stable and well-damped, responds to disturbances with much larger corrective moments and hence larger transient AoA excursions and structural fin loading than a moderately-margined design — an unfavorable trade against a design that already carries known TBD items on motor thrust/mass.
- **Mass and drag budget:** independent of dynamics, 4 fins each 0.6685 m span x 0.1768 m chord (`total_fin_area_m2: 0.449` per `fusion_extraction_v6.yaml`) carry mass (0.224 kg, minor) and, more importantly, wetted/wave drag area that is almost certainly unnecessary once the margin is brought into the 1.5-2 cal band — this is a drag-reduction opportunity independent of the stability question.

## 6. Repeated caveat: transonic band is not CFD

As already documented in `barrowman_stability.py` (`_assumptions()` and the module docstring): the 0.8 ≤ Mach ≤ 1.2 band is bridged by **linear interpolation** of the fin compressibility factor between its Mach-0.8 (Prandtl-Glauert) and Mach-1.2 (Ackeret/linearized-supersonic) values. No closed-form linear theory is valid in this band; this is a low-order engineering bridge, not a CFD or wind-tunnel result, and the transonic CP/SM values reported here and in `barrowman_results.json` (including the M=1.0 point at 10.19 cal used above) **should not be used for flight-safety sign-off** without CFD or wind-tunnel corroboration near Mach 1. This caveat applies equally to the sensitivity and burnout numbers in this review, which build on the same subsonic/transonic model.

## 7. Summary of numeric findings

- Static margin is ~9-10 cal across the entire flight envelope (M=0 to M=2.5), roughly 5x the top of the typical 1-2 cal design band.
- Fins contribute 97.1% of total CN_alpha and are entirely responsible for pulling the CP from ~0.27 m (body-only) to 4.13 m (with fins).
- A fin span of ~0.085-0.093 m (currently 0.6685 m, a ~7.2-7.9x reduction) would bring SM into the 1.5-2.0 cal band with all other geometry fixed.
- Booster burnout (SZACOWANY: 75 kg of 355 kg total, aft-located) moves CG forward and *increases* SM further, to an estimated ~11.9-12.7 cal — CG travel is not masking or explaining the excess margin; if anything it makes it worse.
- The magnitude and direction of the needed fin-span correction (divide by a factor close to but not exactly 10) closely mirrors a unit-conversion bug class (cm vs mm) that the same Fusion Assembly v6 export is independently documented to have already exhibited and partially corrected elsewhere in this same extraction pass.

## Verdict

**Prawdopodobny artefakt geometrii — wymaga przeglądu zespołu.**

Justification: the fin set alone accounts for 97% of CN_alpha and 100% of the excess CP-CG separation; a span reduction of ~7-8x (numerically adjacent to a factor-of-10 unit error) restores the static margin to the standard 1.5-2 cal design band; the same Fusion export is independently documented to have suffered a cm/mm unit bug on other components in this very extraction pass; and CG travel from booster burnout only increases the margin further rather than explaining or mitigating it. This pattern is far more consistent with an un-caught unit or geometry-export error on the fin span than with a deliberate 5x-oversized fin design, but the fin geometry itself should be re-verified against the Fusion model by the vehicle-builder/mechanical team before any change is made — this review only recommends investigation, it does not alter the geometry.
