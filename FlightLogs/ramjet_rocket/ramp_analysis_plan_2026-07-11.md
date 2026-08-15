# RamP Analysis Plan — Research Findings (2026-07-11)

> **Provenance note.** The original external research artifact of this name was
> *not* present in the repository at the start of the 2026-07-11 full-analysis
> rerun session (`docs/ramP/nightly_run_report_2026-07-11.md` is a mislabeled
> Night-4 report, not this artifact). This file reconstructs the **condensed
> findings** carried in the rerun session prompt so that the Stage 1–4 analysis
> modules can cite a real in-repo reference. The literature justification for the
> method choices (DATCOM, Ackeret, Taylor–Maccoll, MIL-E-5007D, CEA γ) was done
> in the research phase and is summarized — not re-derived — here. Numeric
> coefficients used by the code are cited at their point of use in the modules.

---

## 1. Stability — retire the Barrowman supersonic gate

- Barrowman's `+8.99 cal` (basic) / `+4.594 cal` (extended) result is **out of
  regime** and must be **RETIRED as the CDR stability gate**, not reconciled
  with CFD:
  - Barrowman slender-body theory is validated only to ~**Ma 0.7**; the cruise
    condition is Ma 2.5.
  - The fins violate the **small-fin assumption**: fin semi-span 0.550 m against
    body diameter 0.200 m ⇒ span/diameter ≈ **2.75** (fin extends ~2.67× a body
    diameter from the centerline).
- Replacement three-method gate:
  1. **Missile-DATCOM / RASAero-style supersonic component buildup** —
     intermediate fidelity (CN, CP, static margin, Ma 0.5–3.0).
  2. **Ackeret / slender-body analytical fin CP hand-check** — independent
     closed-form cross-check.
  3. **SU2 RANS-SST** (y+<1, grid-convergence, α-sweep) — authoritative
     cross-check (deferred where SU2 is not buildable in the environment).
- **CDR gate = all three agree on sign and give positive margin.**

## 2. Ramjet cycle / V3 gap

- The Grzywka MATLAB model's **constant γ=1.4** is the primary suspect for the
  40.8 % V3 gap (1474 m/s model vs 1047 m/s Teltik CFD), not only the nozzle
  area ratio (already corrected to **AR=1.317** from the Czernicki drawing).
- Rebuild on a **Heiser & Pratt stream-thrust station framework** with
  **NASA-CEA-derived γ per station**: ~1.40 cold inlet air, ~1.25–1.30
  post-combustion.
- Run a **γ sensitivity sweep [1.20, 1.25, 1.30, 1.35, 1.40]**.

## 3. Inlet — Taylor–Maccoll + MIL-E-5007D

- MIL-E-5007D reference recovery: `pt2/pt0 = 1 - 0.075 (M-1)^1.35` for M>1
  (≈ **0.866 at Ma 2.5**). This is a reference **GOAL**, not a hard limit.
- Redo Taylor–Maccoll conical flow for the **42° external / 60° internal** cone,
  followed by the oblique-shock train and terminal normal shock, then diffuser
  losses.
- Explicitly check likely failure modes: **shock-on-lip mismatch**,
  **subcritical buzz** (Ferri–Nucci-style criterion), **no boundary-layer
  bleed**.

## 4. Nozzle — coupled to cycle γ

- With the corrected **AR=1.317**, check over/under-expansion against the
  altitude/ambient-pressure profile using the **SAME corrected γ** from item 2.
- The nozzle and cycle analyses are coupled: do **not** run the nozzle expansion
  check at γ=1.4 while the cycle uses the new γ.

## 5. Cold-flow instrumentation

- CO₂ + optical methods (Schlieren / tracer) verify shock structure and gross
  recovery well, but do **NOT** assume they predict reacting (kerosene) mixing
  behavior.
- Document the **momentum-flux / density-ratio mismatch** explicitly as a known
  limitation — cold-flow mixing data is qualitative/screening only for the later
  kerosene flight.

---

*Reconstructed 2026-07-11 for the RamP full-analysis rerun. See
`docs/decision-log.md` for the dated per-stage decisions that implement these
findings.*
