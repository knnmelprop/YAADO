# ramP — Stability Discrepancy Reconciliation (Geometry Audit + Sensitivity)

**Date:** 2026-07-09 (Night-3, Phase 5)
**Author:** aero-analyst subagent (MELprop-IADE)
**Scope:** Analysis and documentation only. No vehicle config/geometry YAML and
no code under `analyses/stability/` were modified — this file is the only
write. All numbers below were produced by calling the existing
`analyses/stability/barrowman_stability.py` functions (`load_geometry`,
`compute_stability_at_mach`) directly, read-only, from a throwaway script;
none of the Barrowman math was reimplemented.

**Prerequisite reading (not reproduced here):**
- `docs/ramP/stability_margin_report.md` — Phase 0b writeup establishing the
  sign-flip discrepancy (Barrowman +8.99 cal vs Teltik 2024 CFD −2.75 cal at
  Ma 2.5).
- `docs/assumptions.md`, row **A15** — numeric register entry for the same
  discrepancy.
- `docs/ramP/static_margin_review.md` (Night 1) — origin of the "~7-8x
  fin-span reduction would restore 1.5-2 cal" hypothesis, computed at the
  M=0 anchor condition.

---

## 1. Geometry-field audit — what feeds the Barrowman CP

`load_geometry()` in `analyses/stability/barrowman_stability.py` (lines
189–223) reads the following exact YAML keys from
`vehicles/ramjet_rocket/vehicle_config.yaml` into the `RocketGeometry`
dataclass used by every downstream CP/CN_alpha formula:

| YAML key (in `vehicle_config.yaml`) | `RocketGeometry` field | Role in CP computation |
|---|---|---|
| `body.diameter_m` | `d_ref_m` | Reference diameter for all `CN_alpha` normalization and the caliber (`SM_cal`) denominator. |
| `body.nose_length_m` | `nose_length_m` | Nose `CN_alpha`/CP (`nose_cn_alpha_and_cp`), scaled by `NOSE_CP_FACTOR = 0.466`. |
| `body.nose_diameter_m` | `nose_base_diameter_m` | Nose area-ratio `CN_alpha`; also the small-end radius of the nose→body transition (shoulder) term. |
| `body.total_length_m` | `total_length_m` | Overall length; also fixes the fin-root leading-edge axial position via `fin_root_le_x_m = total_length_m − fin_root_chord_m` (fins assumed flush with the aft end — a coded assumption, not a YAML field). |
| `fins.count` | `fin_count` | Linear multiplier `N` on fin `CN_alpha` (`fin_cn_alpha_base_and_cp`). |
| `fins.span_m` | `fin_span_m` | Enters fin `CN_alpha` as `(s/d)^2` (squared) and the body-fin interference factor `Kfb = 1 + R/(s+R)` — the single most sensitive geometry input to CP, since fins alone already carry 97.1% of total `CN_alpha` per the Night-1 breakdown. |
| `fins.chord_root_m` | `fin_root_chord_m` | Fin `CN_alpha` denominator term and fin-CP `x_from_root_le` offset. |
| `fins.chord_tip_m` | `fin_tip_chord_m` | Same as above (taper terms). |
| `fins.sweep_deg` | `fin_sweep_deg` | Leading-edge sweep distance `l_m = s·tan(sweep)`, feeds both `CN_alpha` and fin-CP location. |
| `mass_properties.cg_from_nose_m` | `cg_from_nose_m` | Not a CP input, but is the other half of `static_margin_cal = (x_cp − cg)/d_ref`. |

**Not sourced from either YAML file at all:** `TRANSITION_LENGTH_M = 0.10`
(module-level constant, line 88) — the nose→body shoulder length used by
`transition_cn_alpha_and_cp` is a hardcoded engineering assumption ("short"),
explicitly flagged in the module's own `_assumptions()` output, because no
transition length is present in the Fusion export. Nose fineness itself
(`nose_length_m / nose_base_diameter_m = 0.293/0.150 = 1.953`) and overall
fineness (`total_length_m / d_ref_m = 4.377/0.250 = 17.51`) are both derived
from the audited keys above, not separate YAML fields.

Cross-check against `fusion_extraction_v6.yaml` (the raw, "do not hand-edit"
source of truth): `fins.fin_properties.span_m = 0.6685`,
`chord_root_m = chord_tip_m = 0.1768`, `sweep_le_degrees = sweep_te_degrees =
0.0`; `body.nose_cone.length_m = 0.293`, `base_diameter_m = 0.150`;
`structure.total_length_m = 4.377`; `center_of_gravity.y_m = 1.6084`. All
values in `vehicle_config.yaml` match the raw extraction 1:1 — the
reconciled YAML has not introduced a transcription error relative to the raw
export; if an error exists, it is upstream, in the Fusion extraction itself
or in what CAD feature was measured.

## 2. Confirmed vs. suspect fields

| Field | YAML value | Flag status | Evidence |
|---|---|---|---|
| `body.diameter_m` | 0.250 m | Confirmed-good | Comment: "Fusion-verified body diameter"; `fusion_extraction_v6.yaml` `extraction.confidence.dimensions: "VERY HIGH"`. |
| `body.nose_length_m` / `nose_diameter_m` | 0.293 m / 0.150 m | Confirmed (self-declared) | Same "VERY HIGH" dimensions confidence block; internally consistent with nose fineness ratio ~1.95 (physically plausible cone). |
| `body.total_length_m` | 4.377 m | Confirmed (self-declared) | Cross-checked in the extraction's own "CORRECTIONS LOG" (`axis_correction`: "Booster 2.089m now fits in total 4.377m"). |
| `mass_properties.cg_from_nose_m` | 1.6084 m | Confirmed (self-declared) | `extraction.confidence.center_of_gravity: "VERY HIGH (verified by component breakdown)"`. |
| `fins.count`, `sweep_deg`, `chord_root_m`/`chord_tip_m` | 4, 0.0°, 0.1768 m | Confirmed (self-declared), **not independently flagged as suspect anywhere** | No `SZACOWANY` tag; not mentioned in Night-1/A15 discussion. |
| **`fins.span_m`** | **0.6685 m** | **Suspect** — but *not* via any explicit `SZACOWANY`/estimated tag in either YAML file | Flagged only in `docs/ramP/static_margin_review.md` and `docs/ramP/analysis_status.md` ("Fin span suspect... likely Fusion export artifact"), inferred *indirectly* from the physically implausible resulting static margin (10+ cal at M=0, +8.99 cal at Ma 2.5) and from this exact extraction pipeline's own history of one already-caught cm/mm unit bug (`fusion_extraction_v6.yaml` → `corrections.unit_system_fix`). |
| `body.max_diameter_m` | 0.639 m | **Internally inconsistent, not currently used by Barrowman** | Not read by `load_geometry()` at all. See Section 3 note below — it is numerically hard to reconcile with `fins.span_m = 0.6685 m` if both describe the same physical vehicle. |

Note the asymmetry: propulsion fields in `vehicle_config.yaml`
(`stage_1.propulsion.isp_*`, `thrust_*`, `burn_time_s`, etc.) carry explicit
`# SZACOWANY` comments. **No geometry field carries an equivalent explicit
flag** — every CP-feeding geometry field is labeled by the extraction as
"Fusion" / "VERY HIGH confidence". The fin-span suspicion is therefore an
*inferred*, not a *declared*, data-quality flag, which is precisely why it
needs a human CAD check rather than a code fix: the file offers no signal by
itself.

## 3. Sensitivity sweep — `fin_span_m` at Ma 2.5

Sweeping `fins.span_m` ±20% around the current 0.6685 m value (5 points),
holding every other geometry field fixed, and calling
`compute_stability_at_mach(geometry, mach=2.5)` directly:

| Δspan | `fin_span_m` [m] | CP [m from nose] | Static margin [cal] |
|---|---|---|---|
| −20% | 0.5348 | 3.6808 | **8.290** |
| −10% | 0.6017 | 3.7794 | **8.684** |
| 0% (current) | 0.6685 | 3.8548 | **8.986** |
| +10% | 0.7354 | 3.9137 | **9.221** |
| +20% | 0.8022 | 3.9603 | **9.408** |

(CG = 1.6084 m, d_ref = 0.250 m throughout; the 0% row reproduces the
+8.986 ≈ +8.99 cal figure from `stability_margin_report.md` exactly, which
is a useful internal cross-check that the sweep script is calling the real
code path correctly.)

**Reading:** over the full ±20% band the static margin stays positive and
moves only from 8.29 to 9.41 cal — a swing of ~1.1 cal. **±20% alone comes
nowhere close to flipping the sign**, let alone reaching the CFD-implied
−2.75 cal. The local slope is roughly **+4.18 cal per meter of span** at
this Mach, i.e. the margin is fin-span-sensitive but not steep enough for a
plausible small measurement error to explain a 9-12 caliber CP gap.

Extending the same bisection (still calling `compute_stability_at_mach`
directly, no reimplementation) to find what span *would* close the gap at
Ma 2.5, holding everything else fixed:

| Target | Span needed [m] | Reduction factor vs. current 0.6685 m |
|---|---|---|
| SM = 0 (sign flip) | 0.1391 m | **4.80x** |
| SM = +1.5 cal (healthy band, low end) | 0.1732 m | **3.86x** |
| SM = +2.0 cal (healthy band, high end) | 0.1857 m | **3.60x** |

This is smaller than the Night-1 "~7-8x" figure — but that figure was
derived at the **M=0** anchor condition in `static_margin_review.md`, not at
Ma 2.5. The two are not directly comparable: `fin_mach_correction_factor()`
scales the fin `CN_alpha` differently at each Mach (Prandtl-Glauert at M=0
vs. the Ackeret supersonic branch at M=2.5), so the span reduction needed to
reach a given caliber target is itself Mach-dependent. **This is a
discrepancy the team should be aware of, not one this analysis resolves**:
the correct question is not "what single span value fixes the margin" but
"does a single corrected span produce an acceptable margin across the whole
flight Mach range," which requires a full Mach sweep at the corrected span,
not addressed here.

**A concrete numeric lead worth flagging (hypothesis, not fact):**
`body.max_diameter_m = 0.639 m` (Fusion bbox, currently unused by
`load_geometry()`) is not read into Barrowman at all, but if it is meant to
represent the fin-tip-to-fin-tip envelope diameter of the finned section,
back-solving `d_ref + 2·span = 0.639` gives an implied span of
`(0.639 − 0.250)/2 = 0.1945 m` — a **3.44x reduction** from the current
0.6685 m. That factor falls almost exactly inside the 3.60x–4.80x band this
sweep found necessary to reach a sane margin at Ma 2.5. This is a
coincidence worth checking, not a confirmed root cause — Section 4, item 1,
asks the team to check it directly against the CAD.

## 4. Verification questions for the team (HUMAN_REVIEW — not resolved here)

None of the following were acted on; no YAML value was changed. These are
CAD-verification tasks against **Fusion Assembly v6**.

1. **Fin-span vs. body bounding box.** Open Assembly v6 and directly measure
   the fin-tip-to-fin-tip diameter of the aft stabilizer section. Compare
   against `fins.span_m = 0.6685 m` (implying a tip-to-tip diameter of
   `0.250 + 2×0.6685 = 1.6035 m`) versus `body.max_diameter_m = 0.639 m`
   (Fusion bbox, currently unused by the stability code). These two numbers
   describing the same vehicle differ by a factor of ~2.5x; determine which
   one (if either) is the correct fin span, and specifically test the
   `(0.639 − 0.250)/2 = 0.1945 m` hypothesis in Section 3.
2. **Fin span vs. booster wing halfspan.** `fins.span_m = 0.6685 m`
   (stabilizer, aft section) is suspiciously close in order of magnitude to
   `stage_1.geometry.wings_halfspan_est_m = 0.780 m` (the *booster's*
   PRD-240 control-fin halfspan, an already-flagged estimate). Confirm the
   0.6685 m value in `fusion_extraction_v6.yaml` under
   `fins.fin_properties.span_m` genuinely traces back to the
   `stabilizer v11:1..4` bodies (aft ramjet section) in Assembly v6, and was
   not accidentally sourced from the booster's own wing geometry during
   extraction.
3. **Units re-check, independent of the API script.** This extraction
   pipeline already caught one cm/mm unit-conversion bug
   (`fusion_extraction_v6.yaml` → `corrections.unit_system_fix`). Given that
   history, manually read `fin_span_m` off the Assembly v6 sketch/parameter
   panel in the Fusion GUI directly (not via the same API script that
   produced the original bug) to independently confirm 0.6685 m rather than,
   e.g., 66.85 mm or 6.685 cm misplaced by a decade.
4. **Fin mounting position.** `barrowman_stability.py` assumes the fin root
   trailing edge sits flush with the aft end of the rocket
   (`fin_root_le_x_m = total_length_m − chord_root`). Confirm this against
   the actual axial mounting position of the `stabilizer v11:*` bodies in
   Assembly v6 — if the fins are mounted forward of the very aft tip, the
   fin CP (and hence the whole-vehicle CP) shifts, independent of the span
   question.
5. **Nose→body transition length.** `TRANSITION_LENGTH_M = 0.10 m` is a
   hardcoded code assumption, not present in either YAML file. Measure the
   actual axial length of the 0.150 m → 0.250 m conical shoulder in Assembly
   v6 and report it so it can be added as a real geometry field instead of
   a guess.
6. **Nose bluntness.** `fusion_extraction_v6.yaml` lists
   `bluntness_radius_m: 0.0` for the nose cone (perfectly sharp tip).
   Confirm this against the physical/CAD nose — a non-zero tip radius would
   change the nose `CN_alpha`/CP formula, which currently assumes a pure
   cone.
7. **Teltik 2024 CFD geometry vintage.** Confirm what CAD revision Teltik
   2024's CFD mesh was built from, and specifically whether its fin
   geometry (span, chord, mounting) matches the *current* Assembly v6 or an
   earlier iteration. If the fin span used in the CFD differs from 0.6685 m,
   the Barrowman-vs-CFD comparison in `stability_margin_report.md` is not a
   like-for-like comparison of the same vehicle, regardless of which
   span value turns out to be correct.
8. **Cross-Mach consistency of any corrected span.** Once a corrected
   `fin_span_m` is confirmed, re-run the full Mach sweep (not just Ma 2.5)
   to confirm the corrected value gives an acceptable static margin across
   the whole flight envelope (boost, transonic, Ma 1.5, Ma 2.5 cruise) —
   Section 3 showed the "reduction factor needed" is itself Mach-dependent,
   so a value that fixes Ma 2.5 is not guaranteed to fix Ma 1.5 or M=0.
9. **Moments of inertia, while the CAD is open.** Unrelated to CP but noted
   here since it requires the same manual Assembly v6 GUI session:
   `Ixx/Iyy/Izz` are still `"TBD"` in `fusion_extraction_v6.yaml` and
   flagged in `docs/ramP/analysis_status.md` — worth extracting in the same
   CAD pass as the fin-span check to avoid a second manual session.

---

**Verdict (unchanged from `stability_margin_report.md`):
Prawdopodobny artefakt geometrii — wymaga przeglądu zespołu.** This
reconciliation narrows the search: a ±20% span perturbation cannot explain
the Barrowman-vs-CFD gap, but a ~3.6x–4.8x span reduction (Ma 2.5) can flip
the sign back to positive and reach a healthy margin — and the
`body.max_diameter_m = 0.639 m` bbox field, not currently used by the
stability code at all, independently hints at a similar-order correction
(~3.44x). None of this is confirmed; it is a set of concrete, numbered
CAD-verification tasks for the team (Section 4), not a resolution.
