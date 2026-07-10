# ramP — Stability Margin Report (Barrowman vs CFD Teltik 2024)

**Date:** 2026-07-10
**Author:** aero-analyst subagent (MELprop-IADE)
**Scope:** Analysis only. No code, YAML, or geometry files were modified. This report re-uses and extends `docs/ramP/static_margin_review.md` (2026-07-08, Night 1) — that review is not reproduced in full here; read it first for the fin-CN_alpha breakdown, the fin-span sensitivity table, and the burnout-CG analysis. This report adds an independent data point (CFD) that the Night 1 review did not have, and re-frames the conclusion in light of it.

**Data sources:**
- `analyses/stability/barrowman_stability.py` (Barrowman + Rogers-extension implementation; re-run read-only for this report)
- `docs/ramP/static_margin_review.md` (Night 1 review — cited throughout, not duplicated)
- Teltik, 2024 — CFD thesis data for the ramjet_rocket outer mold line, cited as given: CP = 1.85 m from nose at Ma 1.5, CP = 0.92 m from nose at Ma 2.5
- `analyses/cfd/su2_config_template.py` (stub only — no run performed for this report)

---

## 1. Recap of the Night 1 finding (for context only)

`static_margin_review.md` established, from the Barrowman/Rogers model alone: CP = 4.128 m (M=0), CG = 1.6084 m, SM = 10.08 cal at liftoff, growing to ~12-13 cal at estimated booster burnout; fins alone contribute 97.1% of CN_alpha and are responsible for essentially all of the CP-CG separation; a ~7-8x fin-span reduction would restore the standard 1.5-2 cal band; verdict was "prawdopodobny artefakt geometrii — wymaga przeglądu zespołu." That review used **only** the Barrowman method. This report's job is to check that conclusion against an independent method: CFD.

## 2. Barrowman CP, Mach-matched to the CFD data points (re-run)

Re-running `compute_stability_at_mach()` at the specific Mach numbers reported by Teltik 2024 (rather than only the M=0 anchor value quoted in Night 1) gives:

| Mach | Barrowman CP [m from nose] | Barrowman CN_alpha_total [1/rad] | Barrowman SM [cal] |
|---|---|---|---|
| 0.0 (Night-1 anchor) | 4.128 | 68.21 | 10.078 |
| 1.0 | 4.155 | 88.95 | 10.187 |
| **1.5** | **4.044** | 39.70 | **9.743** |
| **2.5** | **3.855** | 20.40 | **8.986** |

(CG = 1.6084 m from nose, d_ref = 0.250 m, throughout.) These Mach-matched Barrowman values are used below for a fair, same-Mach comparison against the CFD points, rather than comparing CFD at Ma 1.5/2.5 against the single M=0 headline number.

## 3. CFD (Teltik 2024) vs Barrowman — the comparison

| Mach | Barrowman CP [m] | CFD CP [m] (Teltik 2024) | ΔCP [m] | ΔCP [calibers, Δ/0.25 m] | Barrowman SM [cal] | CFD-implied SM [cal] |
|---|---|---|---|---|---|---|
| 1.5 | 4.044 | 1.85 | **2.194** | **8.78** | 9.743 | **+0.966** |
| 2.5 | 3.855 | 0.92 | **2.935** | **11.74** | 8.986 | **−2.754** |

Derivation, worked explicitly:

- Ma 1.5: ΔCP = 4.0443 − 1.85 = 2.1943 m → 2.1943 / 0.250 = **8.777 cal**. CFD-implied SM = (CP_CFD − CG) / d_ref = (1.85 − 1.6084) / 0.250 = 0.2416 / 0.250 = **+0.966 cal**.
- Ma 2.5: ΔCP = 3.8548 − 0.92 = 2.9348 m → 2.9348 / 0.250 = **11.739 cal**. CFD-implied SM = (0.92 − 1.6084) / 0.250 = −0.6884 / 0.250 = **−2.754 cal**.

Both hand-worked values match the figures given in the task brief (~0.97 cal and ~−2.75 cal) to within rounding — sanity check passed. Also sanity-checked: CP moving forward with increasing Mach is qualitatively consistent between the two methods (Barrowman CP drifts from 4.155 m at M=1 down to 3.855 m at M=2.5, i.e. -0.3 m over that range; CFD CP drifts from 1.85 m to 0.92 m over the same range, i.e. -0.93 m) — so both methods agree on the *direction* of CP travel with Mach (forward migration is the classic supersonic behavior as the body's own lift contribution grows relative to the fins'), they simply disagree enormously on the *absolute* location and, critically, on which side of the CG that location falls.

**The CFD CP at Ma 2.5 (0.92 m) is forward of the CG (1.6084 m) by 0.688 m.** That places the aerodynamic center of pressure ahead of the center of gravity at the design cruise condition — the textbook definition of **static instability** (a positive-alpha disturbance produces a nose-up, alpha-increasing pitching moment rather than a restoring one). At Ma 1.5 the CFD CP (1.85 m) is still aft of the CG, giving a thin margin of +0.97 cal — positive but far below the healthy 1.5-2 cal band, and rapidly heading toward zero and negative as Mach increases toward the 2.5 cruise condition.

## 4. Why Barrowman and CFD can diverge this hard

Several independent, non-exclusive mechanisms plausibly contribute, and they should not be collapsed into a single explanation:

1. **Barrowman's linear/slender-body assumptions break down exactly where the divergence is largest.** The method assumes small angle of attack, slender-body potential flow for the body, and a fin normal-force slope built from incompressible thin-airfoil theory with a Prandtl-Glauert/Ackeret (Rogers-extension) Mach correction. At Ma 2.5 this correction is a single scalar multiplier (`fin_mach_correction_factor` ≈ 0.278 at Ma 2.5, per `barrowman_stability.py`) applied uniformly to the M=0 fin slope — it does not capture supersonic effects such as fin leading-edge shock detachment/attachment, three-dimensional tip relief, shock-expansion interaction between the four cruciform panels, or the redistribution of body normal force along a body of revolution with real (non-slender) local slope discontinuities at the nose-shoulder and body-fin junctions. CFD (Navier-Stokes or even Euler) captures these directly.
2. **Body lift distribution differs qualitatively at Ma 2.5.** Slender-body theory puts essentially all of the body's own CN_alpha near the nose (from the nose+transition terms), which is why the Barrowman body-only CP sits near x ≈ 0.27 m in the Night-1 breakdown. At supersonic Mach numbers the actual pressure-lift distribution over a body of revolution is markedly different (shifted by shock-induced pressure loading over the cylindrical afterbody and boat-tail/fin-root region), which is exactly the kind of effect that would move a CFD-derived CP forward relative to what the fin-dominated Barrowman sum predicts.
3. **The suspected fin-geometry export error (Night 1, Section 3) inflates the Barrowman fin term directly.** If the current `fin_span_m = 0.6685 m` is in fact a ~7-8x oversized value from a Fusion cm/mm export bug (as flagged in `static_margin_review.md`), then the Barrowman CN_alpha and CP calculated here are **both** built on a fin that is far larger, and far more aft-CP-dominant, than the real vehicle. **This is the critical point: resolving the fin-span question changes both models' conclusions, not just Barrowman's.** A smaller, corrected fin reduces the Barrowman CP (bringing it toward, not necessarily to, the CFD figure) and simultaneously changes the CFD baseline's validity, because if Teltik 2024 was run against a different (older or corrected) fin geometry than the current Fusion Assembly v6, the CFD CP of 1.85 m / 0.92 m may not even correspond to the same physical vehicle being evaluated by Barrowman here. Until the fin span is confirmed, neither number can be fully trusted in isolation, and the size of the disagreement itself cannot yet be assigned to "Barrowman is wrong" or "CFD used different geometry" without checking which one (or both) used the (possibly erroneous) 0.6685 m span.
4. **Geometry/version mismatch is a live possibility, not just a caveat.** No confirmation exists in this repo that Teltik 2024's CFD geometry is the same "Fusion Assembly v6 (corrected)" that `vehicle_config.yaml` and `fusion_extraction_v6.yaml` describe (see Night-1 review, dated 2026-07-08, "CORRECTED VERSION"). A thesis from 2024 predates that correction pass by roughly two years; it is plausible the CFD was run on an earlier CAD iteration with different fin sizing, nose shape, or overall length, none of which is verifiable from information available here.

## 5. Conclusion

The two methods do not merely disagree in magnitude — **they disagree in the sign of stability at the cruise Mach number.** Barrowman predicts a large positive static margin (+8.99 cal) at Ma 2.5; CFD (Teltik 2024) predicts a **negative** margin (−2.75 cal) at the same condition, i.e. an aerodynamically unstable vehicle at its design cruise point. Even at Ma 1.5, where both methods agree on the sign (positive), CFD gives a margin an order of magnitude below Barrowman's (0.97 cal vs 9.74 cal) and trending toward instability as Mach increases toward cruise — consistent with the sign flip already seen at Ma 2.5.

This is not a case of "one number is a bit more conservative than the other." A ~9-12 caliber absolute CP discrepancy, and a flip from stable to unstable at the exact flight condition (Ma 2.5 cruise) that matters most for the mission, **fails the MELprop project's two-independent-methods corroboration gate.** Per project rules, AVL cannot be used to adjudicate (Ma 2.5 is far outside AVL's Ma < 0.6 validity range), so a third, independent supersonic method is required. **No CDR-level stability claim can be made on this vehicle until (a) the fin geometry is verified against the CAD source of truth, and (b) at least one of the two existing methods is corroborated by a third tool** — the stub at `analyses/cfd/su2_config_template.py` (SU2 Euler sweep) is the natural next step, since an inviscid Euler solve would already resolve whether the CFD-vs-Barrowman gap is dominated by shock/compressibility effects the linear theory misses, versus a geometry input error common to both.

**Weryfikacja (Polish verdict, per Night-1 format):**

**Prawdopodobny artefakt geometrii — wymaga przeglądu zespołu.**

Uzasadnienie: rozbieżność CP między Barrowmanem a CFD (Teltik 2024) sięga ~9-12 kalibrów i — co ważniejsze — zmienia znak zapasu stateczności przy Ma 2.5 (przelot), z czego Barrowman daje +8,99 kal, a CFD −2,75 kal (niestateczność). Podejrzenie błędu eksportu rozpiętości usterzenia z Nocy 1 pozostaje najbardziej prawdopodobnym wspólnym mianownikiem, ponieważ wpływa na OBIE metody jednocześnie (Barrowman wprost przez CN_alpha usterzenia; CFD pośrednio, jeśli geometria Teltik 2024 nie odpowiada aktualnej wersji Assembly v6).

**Co zespół musi sprawdzić (numbered checklist):**

1. **Rozpiętość usterzenia vs. Fusion** — potwierdzić `fin_span_m = 0.6685 m` bezpośrednio w modelu CAD (Fusion Assembly v6), pod kątem tego samego błędu cm/mm już wykrytego i częściowo poprawionego w tym samym eksporcie (`fusion_extraction_v6.yaml`, sekcja `corrections`).
2. **Wersja geometrii Teltik 2024 vs. aktualny Assembly v6** — ustalić, na jakiej wersji CAD/OML wykonano CFD w pracy Teltik (2024); jeśli to inna geometria (inny rozmiar usterzenia, nos, długość), rozbieżność 9-12 kal nie jest w pełni porównywalna 1:1 i musi być odnotowana jako ograniczenie porównania.
3. **Korroboracja SU2** — uruchomić zamiatanie Euler/RANS na `analyses/cfd/su2_config_template.py` przy Ma 1.5 i 2.5 na AKTUALNEJ (nie historycznej) geometrii, aby uzyskać trzecią, niezależną wartość CP i rozstrzygnąć, która z dwóch istniejących metod (lub żadna) jest bliższa prawdy przed jakimkolwiek zapisem stateczności na poziomie CDR.
