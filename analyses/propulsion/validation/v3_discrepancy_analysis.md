# MELprop-IADE | ramP V3 discrepancy root-cause | v0.1.0

Root-cause analysis of the nozzle-exit velocity (V3) discrepancy in the Grzywka
combustor/nozzle cycle (`analyses/propulsion/combustor_nozzle_cycle.py`) versus
the Teltik 2024 CFD reference. Condition: **Mach 2.5 / 6000 m ISA**, Teltik CFD
V3 ~ **1047 m/s** (assumptions A15). Night-3 model V3 = **1474 m/s** (Th2, real
losses) -> delta **+40.8 %**, exceeding the accepted 20-30 % band (A3).

Analysis only — no production code or YAML was modified; all numbers come from
importing and calling the existing module (`_v3_analysis_helper.py`).

## Summary

- **Primary root cause = the fully-expanded (p3 = p0) 1-D nozzle assumption**,
  not a coefficient error. The model forces isentropic expansion to ambient
  (A3/A21 = **2.44**, Ma3 = 2.32, V3 = 1474 m/s). The real CAD nozzle is a
  cylindrical stub (`expansion_ratio` = 1.0, A10 refuted) whose choked
  constant-area duct exits near-sonic (u21 = **809 m/s**). CFD 1047 m/s sits
  ~36 % of the way from sonic to full-expansion — the full-expansion idealization
  over-shoots the entire gap.
- **T04 (combustor-exit total temperature Tt2) is the second lever and is a
  team decision (HUMAN_REVIEW).** V3 ∝ √T04; the 2000 K placeholder is a genuine
  TBD (A4 flame-holder risk at ~2400 K, Fusion steel-vs-aluminium contradiction).
  Matching CFD via T04 *alone* needs **1009 K** — physically implausible (only
  ~450 K heat addition) — so T04 cannot be the sole cause, but it is uncertain.
- **Gamma and inlet recovery are non-causes.** The code already uses
  gamma_hot = **1.33** (not 1.4 — the task premise was wrong) and cp_hot = 1156;
  moving the expansion exponent to 1.28 shifts V3 by only −4.5 %. Inlet recovery
  eta_inlet = 0.8741 is on-standard vs MIL-E-5007D 0.8703 (+0.43 %).

## Task 1 — Station-by-station reproduction (baseline T04 = 2000 K)

Reproduced by calling `GrzywkaCombustorNozzleAnalysis._run_condition(2.5, 6000)`
(the factored path `execute()` uses for the Teltik cross-check). V3 is
altitude-independent in this model (it depends on the pressure *ratio* p0/pt_noz,
a function of Mach only), so the 6000 m value equals the 10 000 m design-point
JSON value (1474.33 m/s) exactly.

| Station | Plane | T [K] | p [Pa] | V [m/s] | Ma | A [m²] |
|---|---|---|---|---|---|---|
| 1  | combustor inlet (post-diffuser) | Tt1 = 560.59 | pt1 = 704 607 | — | — | — |
| 2  | combustor exit (Tt2 = T04)      | Tt2 = 2000.00 | pt2 = 628 791 | — | — | — |
| 21 | throat (choked, Ma = 1)         | T21 = 1716.74 | p21 = 339 776 | u21 = **809.26** | 1.000 | 0.04785 |
| 3  | nozzle exit (Th2, p3 = p0)       | T3 = 1059.84  | p3 = 47 181  | **V3 = 1474.33** | 2.319 | 0.11678 |

- eta_inlet = 0.8741 (4-cone chain), pi_CC = 0.8924, pi_nozzle = 0.97.
- Implied full-expansion area ratio **A3/A21 = 2.440** vs CAD cylindrical stub
  **1.0** and YAML design intent **4.0**.

**Which transition drives the departure vs CFD?** All of the velocity is
generated in the **21 → 3 nozzle expansion**. Stations 1 and 2 are total-condition
planes (no velocity target). The model expands to Ma3 = 2.32; the real geometry
(expansion_ratio 1.0) can only reach ~Ma 1.3 (CFD). The departure is therefore
localized entirely at the **nozzle-exit expansion**, and its magnitude is set by
the assumed exit area ratio, not by any station-1/station-2 quantity.

**Bracket (quantitative):** at fixed T04 = 2000 K the exit velocity is bounded by

```
sonic exit  (A3/A21 = 1.0, cylindrical stub)   V3 ≈ u21 = 809 m/s   (undershoot −238)
Teltik CFD  (real geometry + real gas)          V3     = 1047 m/s
full expand (A3/A21 = 2.44, model Th2)          V3     = 1474 m/s   (overshoot +427)
```

CFD lands at (1047−809)/(1474−809) = **36 %** of the sonic→full-expansion span —
i.e. the physical nozzle does partial expansion, and the 1-D full-expansion
assumption is the dominant source of the +40.8 % overshoot.

## Task 2 — T04 sensitivity sweep

`v3_sensitivity_T04.csv` (6 rows). V3 ∝ √T04 at fixed pressure ratio (confirmed:
bisection and the closed-form √-law agree to 0.1 K). Thrusts rise with T04
(more heat addition → more mass flow enthalpy) and obey Thi ≥ Th1 ≥ Th2 in
every row.

| T04 [K] | V3 [m/s] | Thi [N] | Th1 [N] | Th2 [N] |
|---|---|---|---|---|
| 1600 | 1318.68 | 15 238 | 14 702 | 14 555 |
| 1800 | 1398.67 | 17 616 | 17 044 | 16 887 |
| 2000 | 1474.33 | 19 904 | 19 298 | 19 131 |
| 2200 | 1546.29 | 22 119 | 21 479 | 21 303 |
| 2400 | 1615.05 | 24 271 | 23 599 | 23 414 |
| 2600 | 1680.99 | 26 372 | 25 668 | 25 475 |

**`T04_teltik_equivalent_K = 1008.6 K`** (model bisection to V3 = 1047 m/s;
logged in the CSV header). This is *below* any credible ramjet flame temperature
(only ~450 K above Tt1 = 560 K, fuel-air ratio ~0.02), which is the quantitative
proof that **T04 overestimation alone cannot explain the discrepancy** — the
nozzle-model difference must carry most of it.

> Thrust magnitudes here (~19 kN at 6 km) exceed the 12 kN design-point JSON
> value only because of the higher air density at 6 km (larger mdot); this is
> expected and not part of the V3 question.

## Task 3 — Gamma check (the task premise was incorrect)

The task assumed "gamma = 1.4 throughout." **The code does not do this** — it
imports `GAMMA_HOT = 1.33` and `CP_HOT = 1156 J/kgK` from `ramjet_cycle` and
uses them in both the throat and the exit expansion. So the hot-gas correction
is *already applied*. Isolating the gamma effect in the expansion exponent
`(γ−1)/γ` with p0/pt_noz = 0.07735 (Th2), T04 = 2000 K:

| gamma | cp [J/kgK] | V3 [m/s] | Δ vs code (1.33) |
|---|---|---|---|
| 1.33 (code baseline) | 1156 | 1474.33 | — |
| **1.28**, cp fixed 1156 | 1156 | **1407.96** | **−4.50 %** |
| 1.28, R fixed (cp = 1311) | 1311 | 1499.51 | +1.71 % |
| 1.40, cp fixed 1156 | 1156 | 1548.68 | +5.04 % (the wrong premise) |

The gamma = 1.28 correction moves V3 by only **−4.5 %** (−66 m/s) with cp held;
with a composition-consistent gas (R fixed, cp rises) it slightly *increases*.
Either way gamma is a sub-5 % lever — **not a root cause**, and the direction is
ambiguous. The already-applied 1.33 (vs a naive 1.4) has itself removed ~5 % of
over-prediction.

## Task 4 — Inlet recovery vs MIL-E-5007D

eta_d_MIL at Ma 2.5 = 1 − 0.075·(2.5−1)^1.35 = **0.8703**.
Model eta_inlet (4-cone chain) = **0.8741**. Delta = **+0.0037 (+0.43 %)** — the
inlet is on-standard, marginally better. Because V3 enters via
(p0/pt_noz)^0.248, even a 5 % recovery error moves V3 by ~1 %; inlet recovery is
**not** a contributor to the 40.8 % gap.

**Naming clarification (checked in code, flagging the confusion in the task):**
`PI_CC = 0.8924` in `combustor_nozzle_cycle.py` is the **combustor** total-pressure
loss pt2/pt1 (station 1→2), *not* the inlet recovery. The inlet recovery is the
separate quantity `eta_inlet ≈ 0.8741`, computed from
`MultiConeInletPerformanceAnalysis`. The two numbers are coincidentally close
(0.8924 vs the MIL 0.8703), which invites confusion, but they are physically
distinct planes. There is **no naming bug in the code** — the risk is only in
prose that compares "pi_CC" to a MIL-E-5007 recovery target; that comparison
should use `eta_inlet`.

## Hypothesis ranking

| Rank | Hypothesis | Quantified effect | Verdict |
|---|---|---|---|
| 1 | **Fully-expanded (p3=p0) nozzle assumption vs cylindrical CAD geometry** | Spans the whole 809→1474 m/s range; CFD 1047 lies inside it. Explains the +427 m/s (+40.8 %) overshoot. | **PRIMARY** (model/geometry mismatch, A10) |
| 2 | **T04 = Tt2 combustor-exit temperature** | V3 ∝ √T04; ±200 K ≈ ±75 m/s. Sole-cause value 1009 K is unphysical. | **SECONDARY — HUMAN_REVIEW** (tie to A4) |
| 3 | Gamma of combustion products | 1.33→1.28 = −4.5 % (cp fixed); already 1.33 not 1.4 | Minor, already handled |
| 4 | Inlet total-pressure recovery | +0.43 % vs MIL-E-5007D; ~1 % V3 leverage | Non-cause (on-spec) |
| 5 | Generic "CFD vs MATLAB model differences" (A3) | A3 expects CFD *higher* by 20-30 %; here the 1-D model is *higher* than CFD by 40.8 % — **opposite sign** | See caveat below |

### Most probable root cause (with support)

The **fully-expanded 1-D nozzle assumption**. The model imposes p3 = p0 (exit
area ratio 2.44, Ma3 = 2.32) on a nozzle that physically cannot fully expand: the
Fusion v6 nozzle is a cylindrical exit stub (`expansion_ratio` = 1.0, A10
refuted; design intent 4.0). A choked constant-area duct exits near-sonic
(u21 = 809 m/s); the CFD 1047 m/s reflects partial expansion (36 % of the way to
full). The 1-D value overshoots by +427 m/s — the entire discrepancy — while T04
(√-law, needs an impossible 1009 K), gamma (−4.5 %) and inlet recovery (+0.4 %)
are all too small or wrong-signed to be primary.

**A3 sign caveat (flag for the team):** A3 records "CFD 20-30 % *higher* than the
Grzywka MATLAB 2D baseline." Our reproduction is the *opposite* — the 1-D model
is 40.8 % *higher* than CFD. This means the Night-3 fully-expanded 1-D result is
**not** equivalent to Grzywka's 2D MATLAB baseline (which evidently modelled the
real, non-fully-expanded nozzle). The +40.8 % is therefore **not directly
comparable to the A3 band** and should not be reported against it without
qualification.

## Recommended assumption updates

1. **Report V3 as a bracket, not a single number** — mirror the existing
   Thi/Th1/Th2 convention: quote V3(sonic, A3/A21=1.0) ≈ 809 m/s and
   V3(full-expansion, 2.44) = 1474 m/s as bounds around the CFD 1047 m/s, until a
   nozzle model matched to the real expansion ratio exists. (Update the
   `teltik_v3_cross_check` note accordingly — analysis-side only.)
2. **A3 (register):** annotate that the 1-D Grzywka reproduction runs *higher*
   than CFD (opposite sign to the A3 note), so the +40.8 % is a full-expansion
   artifact and is not the A3 MATLAB-vs-CFD discrepancy. Needs reconciliation
   against the actual Grzywka 2D MATLAB baseline. **HUMAN_REVIEW.**
3. **T04 / Tt2 = 2000 K (A4):** do **not** lower unilaterally to chase CFD. The
   sole-cause value (1009 K) is unphysical; a defensible flame temperature is a
   team decision tied to the A4 flame-holder relocation / injector redesign and
   the Fusion steel-vs-aluminium contradiction. **HUMAN_REVIEW — do not decide
   T04 in-agent.**
4. **Gamma:** no change required; 1.33/1156 are already in use. Optionally note
   that a variable-cp / equilibrium-products gas model is a future L3 refinement
   (< 5 % effect).

## One-line for AGENT_CONTEXT.md §Known Issues

> Grzywka 1-D V3 = 1474 m/s runs +40.8 % hot vs Teltik CFD 1047 m/s (Ma2.5/6 km):
> dominated by the fully-expanded p3=p0 nozzle assumption (A3/A21 = 2.44, Ma3 =
> 2.32) applied to the CAD cylindrical stub (ratio 1.0, sonic ~809 m/s, A10); T04 =
> 2000 K placeholder is the 2nd lever (√-law; sole-cause 1009 K is unphysical —
> HUMAN_REVIEW, tie to A4); gamma already 1.33 not 1.4 (−4.5 % to 1.28), inlet
> recovery on-spec (0.874 vs MIL 0.870). Report V3 as a sonic↔full-expansion
> bracket, not a single number.
