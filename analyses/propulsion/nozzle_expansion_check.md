# Nozzle Over/Under-Expansion Check (corrected geometry + Stage 2 gamma)

**Stage 3 (nozzle) of the 2026-07-11 RamP rerun.** Module:
`analyses/propulsion/nozzle_expansion_check.py`. Data:
`nozzle_expansion_check.csv`.

**Coupled to Stage 2:** this check uses the **same station γ** as the Heiser &
Pratt cycle rebuild (`cycle_v2`, nominal γ_hot = 1.28), **not** the legacy
γ = 1.4 — per the research finding (Section 4) the nozzle and cycle analyses must
not disagree on γ.

## Setup

Convergent–divergent nozzle, real drawing area ratio **A_exit/A_throat = 1.317**
(throat 0.210 m / exit 0.241 m). Design M0 = 2.5. PROVISIONAL altitude band
4–10 km ISA (Teltik reference 6 km + config M2.5 @ 10 km; standard troposphere,
assumptions A20) — mark PROVISIONAL until the mission profile is confirmed.

## Result

| altitude [m] | M_exit | p0 [Pa] | p_exit [Pa] | p_exit/p0 | state | matched AR needed |
|---:|---:|---:|---:|---:|:---|---:|
| 4000 | 1.643 | 61 640 | 183 989 | 2.98 | **under-expanded** | 2.48 |
| 6000 | 1.643 | 47 181 | 140 829 | 2.98 | **under-expanded** | 2.48 |
| 8000 | 1.643 | 35 599 | 106 261 | 2.98 | **under-expanded** | 2.48 |
| 10000 | 1.643 | 26 436 | 78 908 | 2.98 | **under-expanded** | 2.48 |

## Reading

- **Under-expanded across the entire band**, by a nearly constant factor
  (p_exit/p0 ≈ 3.0). At a fixed flight Mach the nozzle total pressure scales with
  the ambient pressure (pt0 ∝ p0), so p_exit and p0 fall together with altitude
  and their ratio barely moves — **there is no altitude in the band at which the
  AR=1.317 nozzle is matched.**
- **Matched expansion would need AR ≈ 2.48**, not 1.317. Note this is essentially
  the legacy model's *implied* AR ≈ 2.44 — i.e. the old cycle silently assumed
  the fully-expanded (matched) nozzle, which is exactly why the legacy V3 (1474
  m/s) was inflated. The real, shorter AR=1.317 nozzle leaves the flow
  under-expanded, so part of the available thrust appears as the pressure term
  `(p_exit − p0)·A_exit` (≈ 3.6 kN at 10 km, Stage 2) rather than as exit
  momentum.
- **Design consequence:** the current nozzle is under-sized for full expansion at
  M2.5. Lengthening it toward AR≈2.5 would raise exit velocity and momentum
  thrust and cut the under-expansion loss — a genuine performance lever, to be
  traded against mass/length and off-design (lower-Mach) over-expansion once the
  mission profile is fixed.

## Provisional inputs

| Parameter | Value | Source | Resolves when |
|---|---|---|---|
| γ_hot | 1.28 (Stage 2 nominal) | CEA-class (A19) | real CEA run |
| altitude band | 4–10 km ISA | Teltik 6 km + config 10 km | mission profile |
| nozzle loss π_nozzle | 0.97 | Grzywka (A13) | — |
