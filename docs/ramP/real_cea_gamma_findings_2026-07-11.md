# MELprop-IADE | Real NASA CEA station-gamma run for ramP (resolves the Stage-2 "replace with a real CEA run" TODO) | 2026-07-11

`analyses/propulsion/cycle_v2/hp_stream_thrust_cycle.py` (Stage 2, the
Heiser & Pratt ramjet cycle rebuild) currently uses a **PROVISIONAL literature
default** `GAMMA_HOT_DEFAULT = 1.28`, with an explicit code comment: *"replace
with a real NASA-CEA run once the team confirms equivalence ratio / fuel"*
(assumptions.md A19). This note supplies that real run, executed in a cloud
sandbox session (`claude/ramp-full-analysis-rerun-nkqwp1`) that discovered
NASA CEA is buildable in this environment.

## Environment finding: NASA CEA is buildable in-sandbox

Contrary to the research plan's assumption that CEA would be
`BLOCKED_BY_ENVIRONMENT` in a cloud sandbox:

```bash
apt-get install -y gfortran   # only missing prerequisite; gcc is preinstalled
pip install rocketcea         # 1.2.3, builds cleanly against gfortran
```

`rocketcea` wraps the real NASA CEA Fortran source (Gordon & McBride,
NASA RP-1311), not a lookup table. Air and Jet-A are not in its built-in card
library, so custom cards are needed:

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
cea = CEA_Obj(oxName='Air_MEL', fuelName='JetA_MEL')

# MR = air/fuel mass ratio; stoichiometric AFR for C12H23 ~= 14.7,
# so equivalence ratio phi = 14.7 / MR.
mr = 14.7 / phi
tc_rankine = cea.get_Tcomb(Pc=45.0, MR=mr)                  # combustor Pc in psia
mw, gamma = cea.get_Chamber_MolWt_gamma(Pc=45.0, MR=mr, eps=1.317)
```

## Real CEA results (Pc ~= 45 psia, nozzle area ratio eps = 1.317)

Cold compressed inlet air (proxy, very-lean MR=1000): **gamma ~= 1.398**
(confirms the cold-side `GAMMA_COLD = 1.4` already used everywhere in the
codebase — no change needed there).

Post-combustion kerosene-air equilibrium products, swept over equivalence
ratio phi (fuel/air relative to stoichiometric):

| phi | MR (air/fuel) | Tc [K] | gamma | MW [g/mol] |
|---|---|---|---|---|
| 0.40 | 36.7 | 1310 | 1.297 | 28.97 |
| 0.50 | 29.4 | 1519 | 1.282 | 28.97 |
| 0.60 | 24.5 | 1715 | 1.268 | 28.97 |
| **0.70** | 21.0 | 1898 | **1.254** | 28.96 |
| 0.80 | 18.4 | 2068 | 1.237 | 28.95 |
| 1.00 | 14.7 | 2314 | 1.186 | 28.74 |

All values were re-validated live against a fresh `rocketcea` run this
session (not just computed once and copied).

## How this compares to the current PROVISIONAL default

`GAMMA_HOT_DEFAULT = 1.28` sits almost exactly at the CEA phi=0.5 point
(1.282) and is close to the phi=0.6 point (1.268) — i.e. the literature
placeholder happens to already be in a physically reasonable part of the
real CEA curve. The nearest "design intent" point, phi=0.7 (a typical lean
ramjet-cruise equivalence ratio per Heiser & Pratt Ch. 4), gives **gamma =
1.254**, about 2% lower than the current placeholder.

**Practical impact is small.** A companion analysis in the `nkqwp1` session
(Stage 2 rebuild, run independently against the same AR=1.317 geometry) found
that on the real (fixed-area) nozzle, V3 varies **less than 1%** across the
entire gamma range [1.20, 1.40] — gamma is a minor lever once the nozzle area
ratio is fixed. Swapping 1.28 -> 1.254 would move V3 by a fraction of a
percent, well inside the model's other uncertainties (Tt4 placeholder,
real-gas effects, nozzle boundary-layer losses). It is **not** worth
rewiring the reviewed Stage-2 module for this alone, but the real numbers
and working recipe are recorded here so the next session that DOES want a
verified (not literature-approximated) gamma has zero setup cost.

## Suggested next step (not done here, to avoid touching the reviewed Stage-2 module without a fresh test pass)

If/when the team confirms a design equivalence ratio, replace
`GAMMA_HOT_DEFAULT = 1.28` with `post_combustion_gamma(phi)` interpolated from
the table above (or call `rocketcea` live, per the recipe) and re-run
`gamma_sensitivity.py` to confirm the conclusion is unchanged.
