# MELprop-IADE | RamP full-analysis rerun — session checkpoint | 2026-07-11

Cloud/remote session. Orchestrator: Opus 4.8. Branch:
`claude/ramp-full-analysis-rerun-nkqwp1` (draft PR
[#3](https://github.com/knnmelprop/iade/pull/3)). Session stopped cleanly at a
user-imposed 95% usage cap **after Stage 1**; Stages 2–5 not started. This file
is the resume spec so the next session does **not** re-derive Stage 0.

## Environment findings (verified this session, this container)

| Item | Status |
|---|---|
| git push | **OK** (branch pushed, PR #3 draft open, base `main`) |
| Runtime | system Python 3.11.15 + pip (devcontainer pins 3.9 for SUAVE; NOT used). Installed fresh: pydantic 2.13, numpy 2.4, scipy 1.17, matplotlib, pytest |
| pytest baseline | 211 passed at session start → **220 passed** after Stage 1. Scope to `tests/` (root pytest crashes on `external/su2` fixtures) |
| SU2 RANS | **BLOCKED_BY_ENVIRONMENT** — submodule not checked out; building the SU2 C++ CFD suite in-sandbox is infeasible in budget. Run Stage 1's SU2 cross-check locally. |
| NASA CEA | **AVAILABLE** ✅ — `apt-get install gfortran` then `pip install rocketcea` (1.2.3) builds and runs. Real equilibrium γ obtained (table below). |
| Research artifact | `docs/references/ramp_analysis_plan_2026-07-11.md` is NOT in the repo (can't fetch in sandbox). Proceeded from the condensed findings in the run prompt. |

### rocketcea recipe (reuse verbatim in Stage 2 — custom cards, since Air/Jet-A are not built-in)

```python
from rocketcea.cea_obj import add_new_fuel, add_new_oxidizer, CEA_Obj
add_new_oxidizer('Air_MEL', '''
oxid Air N 1.56168 O 0.41959 AR 0.00937 C 0.00032
h,cal=-29.0 t(k)=298.15 wt%=100.
''')
add_new_fuel('JetA_MEL', '''
fuel Jet-A(g)  C 12 H 23    wt%=100.00
h,cal=-49710.0   t(k)=298.15
''')
c = CEA_Obj(oxName='Air_MEL', fuelName='JetA_MEL')
# MR = air/fuel mass ratio; stoich AFR for C12H23 ~ 14.7 -> phi = 14.7/MR
# c.get_Tcomb(Pc=psia, MR=MR) returns RANKINE; c.get_Chamber_MolWt_gamma(Pc,MR,eps) -> (MW, gamma)
```

## Real CEA station-γ table (Pc≈45 psia chamber, area ratio eps=1.317)

Cold compressed inlet air (proxy, very-lean MR=1000): **γ ≈ 1.398** (≈1.40 as expected).

Post-combustion kerosene–air (equilibrium, eps=1.317):

| φ (equiv. ratio) | MR (air/fuel) | Tc [K] | γ | MW |
|---|---|---|---|---|
| 0.40 | 36.7 | 1310 | 1.297 | 28.97 |
| 0.50 | 29.4 | 1519 | 1.282 | 28.97 |
| 0.60 | 24.5 | 1715 | 1.268 | 28.97 |
| **0.70 (PROVISIONAL design pt)** | 21.0 | 1898 | **1.254** | 28.96 |
| 0.80 | 18.4 | 2068 | 1.237 | 28.95 |
| 1.00 | 14.7 | 2314 | 1.186 | 28.74 |

These confirm the research target (post-combustion γ ≈ 1.25–1.30). **PROVISIONAL
inputs:** φ (equivalence ratio) unconfirmed — used 0.70 as the lean cruise design
point (Heiser & Pratt ramjet practice); Jet-A(g) C12H23 surrogate for kerosene;
Pc≈45 psia. All must be replaced when the team confirms fuel + equivalence ratio.

## Stage status

- **Stage 1 (stability): COMPLETE** — committed + pushed. Barrowman supersonic
  gate retired; `datcom_class_sweep.py` + `ackeret_fin_check.py` added. SM at
  Mach 2.5 = +8.92…+12.92 cal across CG sweep 1.40–2.20 m; DATCOM +11.92 vs
  Ackeret +12.29 cal agree in sign AND magnitude at CG=1.6084. Orchestrator
  fixed a crossflow-linearization defect (secant vs tangent slope) the subagent
  missed. See `docs/decision-log.md` 2026-07-11 entry. **SU2 sign-vs-CFD
  tie-break still owed (blocked here).**
- **Stage 2 (ramjet cycle / V3): NOT STARTED.** Resume spec: build a Heiser &
  Pratt stream-thrust station model in `analyses/propulsion/cycle_v2/` (do NOT
  modify the Grzywka model in place), station-wise γ from the CEA table above
  (cold ~1.40, hot ~1.254 at φ=0.7). Run the γ sweep [1.20,1.25,1.30,1.35,1.40]
  on the corrected AR=1.317 geometry. Report V3/thrust vs old 1474 m/s and
  Teltik CFD 1047 m/s. **KEY COUPLED-PHYSICS NOTE:** the prior in-repo root-cause
  (`analyses/propulsion/validation/v3_discrepancy_analysis.md`) found γ is a
  <5% lever and the *fully-expanded p3=p0 nozzle assumption* dominated the gap —
  but that was pre-AR-correction. With AR now 1.317 (real partial-expansion C-D
  nozzle, not the old 2.44 full-expansion or 1.0 stub), the exit Mach from the
  area–Mach relation is modest, so V3 should land much closer to CFD; γ then
  modulates it secondarily. Do the nozzle expansion (Stage 3) with the SAME
  corrected γ — do not run nozzle at γ=1.4 while cycle uses new γ. Gates:
  V3>0 ∀γ, V3 monotonic with γ, T3>T2. Existing constants to reuse:
  `analyses/propulsion/ramjet_cycle.py` GAMMA_COLD=1.4/CP_COLD=1004.5,
  GAMMA_HOT=1.33/CP_HOT=1156/R_HOT, NOZZLE_AREA_RATIO_DESIGN=1.317;
  `analyses/mission/operational_envelope.py::isa_atmosphere(h)` →
  (rho, T, p, a).
- **Stage 3 (inlet Taylor–Maccoll + nozzle): NOT STARTED.** Inlet cone 42°/60°,
  centerbody 85×62 mm (from `vehicles/ramjet_rocket/cad_reference/
  drawing_dimensions_raw.yaml`). MIL-E-5007D reference pt2/pt0 = 1−0.075(M−1)^1.35
  (~0.866 @ Ma2.5). Nozzle over/under-expansion vs ISA altitude band using
  Stage 2 γ.
- **Stage 4 (cold-flow plan): NOT STARTED.**
- **Stage 5 (integration): NOT STARTED.**

## Concrete next human/agent actions

1. **Next agent session:** resume at Stage 2 using the CEA recipe + table above
   (do not reinstall/re-derive — gfortran+rocketcea already proven to work; just
   `apt-get install gfortran && pip install rocketcea` in the fresh container).
2. **Human:** run Stage 1's SU2 RANS cross-check locally (submodule buildable
   there) to settle the DATCOM/Ackeret-vs-Teltik-CFD sign question at Mach 2.5.
3. **Human:** re-verify `fins.span_m` (0.550 MODERATE confidence vs possible
   0.127) — the entire overstable stability result is conditional on it.
4. **Human:** CG/MOI still `TBD_PHYSICAL_PARAM` (Fusion GUI extraction);
   Stage 1 swept CG 1.40–2.20 m to bound this — no fabricated CG committed.
