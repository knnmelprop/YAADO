# MELprop-IADE — Active Assumptions Register

Every active working assumption, including all [TBD] items from the nightly-run
prompt, with confirmation status. Update whenever an assumption is confirmed,
refuted, or superseded. Companion files: `docs/decision-log.md` (decisions),
`agents/memory.md` (lessons/failure modes).

Status legend: **ACTIVE** (in use, unconfirmed) · **CONFIRMED** · **REFUTED**
· **TBD-HUMAN** (needs a human decision/data — agent must not guess).

| # | Assumption | Status | Notes / evidence |
|---|------------|--------|------------------|
| A1 | Python 3.9 + one pinned SUAVE version for the team environment | TBD-HUMAN | Container runs Python 3.11.15; `.devcontainer/` pins 3.9. Exact SUAVE tag not found in repo env files (2026-07-08). Confirm tag with the team. |
| A2 | WSL2/Ubuntu preferred team environment; Docker/Codespaces deferred | TBD-HUMAN | No evidence in repo either way; needs human confirmation. |
| A3 | Grzywka MATLAB 2D model is the DEFAULT thrust baseline; CFD studies (Dałek, Teltik) show exit velocity/Mach 20–30% higher — open unresolved discrepancy | ACTIVE | Never quote a single thrust/exit number without both values (MATLAB baseline + CFD delta). |
| A4 | Combustor risk baseline: liquid fuel does not vaporize sufficiently before the flame holders; flame-holder cavity temperature ~2400 K exceeds the melting point of the currently specified aluminium | ACTIVE | Every combustor task is blocked-by-design until a redesign (flame-holder relocation and/or injector atomization change) is logged in the decision log. Phase 4 note: Tt4=2000 K placeholder is BELOW the ~2400 K risk figure; also Fusion v6 lists flame_holder material as Steel, contradicting the aluminium risk note — needs human review. |
| A5 | CAD + signed reports live in OneDrive; code/configs/parametric CSV/decision logs live in Git | TBD-HUMAN | Exact boundary to be confirmed with the team. |
| A6 | No defined Project Lead/reviewer exists; "assign reviewer"/"approve gate" are always human actions | CONFIRMED | Nothing in the repo defines such a role; agent never invents one. |
| A7 | Nightly-run prompt WIP (+528/+159 lines multi-cone inlet) exists in working tree | REFUTED | 2026-07-08: working tree clean (fresh container). Phase 1 executed from scratch. See decision-log entry. |
| A8 | Phase-3 dangling commits b2cc871d/65631dad need rebasing onto origin/develop | REFUTED | 2026-07-08: objects absent; equivalent work already merged via PR #11. Adapted Phase 3 = push designated branch + new draft PR. |
| A9 | 2 and 3 cones cannot meet MIL-E-5007 at Mach 2.5; 4 cones give a thin margin (~0.872–0.874), 5 cones comfortable (~0.888–0.897) | CONFIRMED | 2026-07-08: verified numerically in Phase 1 (2 cones 0.799 FAIL, 3 cones 0.849 FAIL, 4 cones 0.8741 PASS, 5 cones 0.8883 PASS vs 0.8703). |
| A10 | `nozzle_area_ratio: 4.0` in YAML matches Fusion CAD geometry | REFUTED | 2026-07-08 Phase 4: Fusion v6 nozzle is cylindrical_exit_nozzle expansion_ratio 1.0 ('full ramjet engine NOT modeled'); YAML 4.0 is a design-intent placeholder, both variants quantified in ramjet_cycle.py. |
| A11 | Design cruise: Mach 2.5 @ 10 km ISA, diffuser eta 0.92 (placeholder) | ACTIVE | eta_diffuser=0.92 is an assumed placeholder pending duct-loss/CFD data. |
| A12 | Stage-1 motor data (Isp, propellant mass, burn time), GTM-140 mass/sfc, wing.aspect_ratio, Ixx/Iyy/Izz | TBD-HUMAN | TODO_PHYSICAL_PARAM — never guessed or approximated by agents; require datasheets / Fusion GUI / team decision. |
| A13 | Grzywka 2022 loss coefficients pi_CC=0.8924 (1→2), pi_nozzle=0.97 (2→3); D21 nozzle throat is DYNAMIC (f(V,H), Ma_throat=1 always) — never a constant | ACTIVE | Night-2 prompt input; to be implemented in Phase 2b (blocked_by_budget). |
| A14 | Three thrust models Thi/Th1/Th2 diverge (Grzywka §6.2.2); all three must always be reported, never a single thrust number | ACTIVE | |
| A15 | Teltik 2024 CFD: CP 1.85 m @ Ma1.5 / 0.92 m @ Ma2.5; V3 ~1047 m/s @ Ma2.5/6000 m; drag 2451.95 N | ACTIVE | 2026-07-09 Phase 0b: CP values imply SM +0.97 cal @ Ma1.5 and −2.75 cal @ Ma2.5 — SIGN FLIP vs Barrowman (+8.99 cal); two-methods stability gate FAILS pending fin-geometry verification (see docs/ramP/stability_margin_report.md). |
| A16 | Night-2 STEP 0 (2026-07-09): tree clean & synced, 80/80 tests green, PR #12 open/draft/mergeable-clean at start; Night-1 report present | CONFIRMED | |
| A18 | V3 discrepancy analysis (Night-4 P1-B): T04 = 2000 K assumed (YAML combustor_temp_K), source Grzywka MATLAB T_fuel(Ma) [TBD_FROM_SOURCE], confidence SZACOWANY; root cause of +40.8% V3 delta identified as fully-expanded nozzle assumption, NOT T04 (T04_teltik_equivalent 1008.6 K unphysical) | ACTIVE | HUMAN_REVIEW for T04 confirmation; see docs/ramP/human_review_night4.md HR-7. Nozzle area_ratio 4.0 vs CAD 1.0 is PRIMARY factor; Laval design decision required (HR-3). |
| A19 | Gamma treatment: code uses gamma_cold=1.4 / gamma_hot=1.33 (NOT 1.4 throughout as previously believed); gamma_products at T21~2000–2500 K is ~1.25–1.30; composition-consistent 1.28 moves V3 by <5% (small lever) | ACTIVE | Review after T04 confirmation; combustion-products composition (stoichiometric kerosene+air assumed) to be confirmed per HR-8. |
| A20 | ISA model: standard troposphere formula (T=288.15−0.0065H, p-power law), valid to H=11000 m, no wind/turbulence; implemented in analyses/mission/operational_envelope.py isa_atmosphere() | ACTIVE | Baseline for all cruise-point analysis; mission-planner to flag if operational envelope extends beyond 11 km. |

---

## 2026-07-11 rerun — PROVISIONAL inputs used this session (one table)

Every PROVISIONAL default used in the Stage 1–4 reruns. Safety-critical unknowns
(CG, MOI, booster thrust) are NOT in this table — they were swept/bounded, not
defaulted (see the sweep note below).

| Parameter | Value used | Source / justification | What resolves it |
|---|---|---|---|
| Post-combustion γ_hot | 1.28 (sweep 1.20–1.40) | CEA-class kerosene-air equilibrium ~2000–2400 K (A19) | real NASA-CEA run (BLOCKED this session) |
| Cold inlet γ | 1.40 | ideal air, T<600 K | — |
| Fuel LHV | 43.0 MJ/kg | standard kerosene/Jet-A | team confirms fuel |
| Tt4 (combustor exit) | 2000 K | config `combustor_temp_K` (below ~2400 K flame-holder risk, A4) | combustor test data |
| η_inlet (cycle input) | 0.8741 | 4-cone chain (A9) | Stage 3 inlet_v2 / rig test |
| π_CC / π_nozzle | 0.8924 / 0.97 | Grzywka (A13) | — |
| ṁ_air | 15.167 kg/s | rho0·u0·A_capture, full capture | inlet capture confirmed |
| Nozzle altitude band | 4–10 km ISA | Teltik 6 km + config M2.5@10 km (A20) | mission profile confirmed |
| Subsonic-diffuser π | 0.97 | typical short annular diffuser | internal duct (60° cowl) modeled |
| Cone-angle interpretation | 42° AND 21° both evaluated | drawing ambiguity (raw yaml) | human reads the PDF callout |
| Puckett fin tip-loss | rectangular-tip correction | DATCOM/Puckett supersonic | higher-fidelity fin model / SU2 |
| K_fb fin-body carryover | 1+R/(s+R) (subsonic form) | Barrowman; supersonic carryover lower | SU2 |
| CO2-rig combustor p/T, u_jet | 350 kPa / 560 K, 150 m/s | cycle station-2 estimate; equal-velocity to isolate density | injector schedule / combustor test |

### Safety-critical unknowns — SWEPT, not defaulted

| Parameter | Treatment | Range / note |
|---|---|---|
| CG (cg_from_nose_m) | **SWEPT** | 0.37–0.64 L (config anchor 0.37; aft bounds booster-attached). SM +5.13…+11.01 cal over the range — all stable analytically, but conflicts with CFD (see below). `TBD_PHYSICAL_PARAM`. |
| Moments of inertia Ixx/Iyy/Izz | **NOT used** | Not needed for static margin (CG-only); still `TBD_PHYSICAL_PARAM`, Fusion GUI extraction (A12). |
| Booster thrust / Isp | **NOT used** this session | Stage 1–4 are cruise-point; still SZACOWANY (A12). |

### New assumptions this session

| # | Assumption | Status | Notes |
|---|------------|--------|-------|
| A21 | cycle_v2 (Heiser & Pratt) V3=1200 m/s at γ=1.28 on AR=1.317; gamma is a WEAK lever (~0.5% across sweep); geometry correction closed the legacy gap, residual +14.6% vs Teltik CFD | ACTIVE | HR-7 RECALCULATED_WITH_CORRECTED_GAMMA_AND_GEOMETRY; needs CEA/SU2 |
| A22 | Stability: DATCOM-class + Ackeret both give +5…+11 cal at Ma2.5 but CONFLICT with Teltik CFD (−2.75 cal); CDR gate NOT satisfied (2-vs-1), SU2 arbiter BLOCKED | ACTIVE | Do NOT gate CDR on analytical +margin; run SU2 locally |
| A23 | Inlet: 42° external cone is ATTACHED at M2.5 (Taylor–Maccoll, not the wedge model) but recovery 0.639 < MIL 0.870; DETACHES at M2.0 → min starting Mach ≈2.1 | ACTIVE | Constrains staging Mach; needs internal-duct schema + rig test |
| A24 | Nozzle AR=1.317 under-expanded (p_e/p0≈3) across 4–10 km; matched AR≈2.48 | ACTIVE | Legacy implied AR≈2.44 ≈ matched → why old V3 inflated |
| A25 | Cold-flow CO2 verifies shocks/recovery but NOT reacting mixing (density & momentum-flux ratio ~11× off) | CONFIRMED (limitation) | Screening only; never feed cold-flow mixing to the cycle model |
