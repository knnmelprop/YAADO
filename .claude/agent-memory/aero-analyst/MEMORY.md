# Aero Analyst Memory Log

This file tracks Barrowman coefficients, fin interference multipliers, Ackeret correlations, static margin validations, and reference envelopes tested.

## 2026-07-09 — Fin polar comparison: Ackeret vs. Diederich AVL-style surrogate (Project B, ramP fins)

- New module: `analyses/aero/fin_polar_comparison.py`. `analyses/aero/xfoil_runner.py`
  (Night-3) was confirmed to be a stub only — its `execute()` always raises
  `NotImplementedError` and it contains no Ackeret math, only geometry constants
  (`FIN_CHORD_M`, `FIN_THICKNESS_MAX_M=0.030`, `FIN_DESIGN_MACH=2.5`). Ackeret theory
  was implemented fresh in the new module rather than "reused" from a nonexistent
  implementation.
- **Ackeret 2D thin-airfoil relations** (symmetric double-wedge/diamond section,
  no camber): `CL = 4*alpha_rad/beta`; `CD_wave = 4/beta * (alpha_rad^2 + (t/c)^2)`,
  `beta = sqrt(Ma^2-1)`. Derivation note: for a symmetric double-wedge with max
  thickness at mid-chord, the half-thickness slope magnitude is constant over the
  whole chord = t/c, so the mean-square-slope wave-drag term reduces exactly to
  `(t/c)^2` (no numerical integration needed). Source: Ackeret NACA TM 317 (1925);
  Anderson *Fundamentals of Aerodynamics* Ch.12.
- **t/c = 0.05 (SZACOWANY)** used for the supersonic wave-drag-optimised double-wedge
  fin section — YAML `fins:` block has no airfoil/thickness data (planform only:
  span/chord/sweep). This is a *different* assumption from `xfoil_runner.py`'s
  `t/c ~ 0.17` (30mm/176.8mm), which is a structural (solid steel plate) estimate for
  the unrelated low-speed XFOIL stub — the two t/c values are for different purposes
  and intentionally do not need to agree. A real fin section drawing is a
  TODO_PHYSICAL_PARAM for future work.
- **Diederich (NACA TN 2751, 1952) analytic surrogate** used as an AVL/VLM stand-in
  (AVL itself never invoked — out of its Mach<0.6 envelope here and binary
  unavailable anyway): `CL_alpha = AR_eff / (1 + AR_eff/(4*beta))`,
  `AR_eff = 2*s/c_mean` with `s` = exposed fin semi-span (ramP YAML `fins.span_m`
  is documented in `barrowman_stability.RocketGeometry` as *already* the exposed
  semi-span, so it plugs directly into Diederich's `s` with no further halving).
  For ramP fins (span 0.6685 m, chord_root=chord_tip=0.1768 m, rectangular,
  sweep 0 deg): `AR_eff = 7.5622`.
- **Ratio (Diederich slope / Ackeret slope) is alpha-independent** — both models are
  exactly linear through the origin in alpha, so compute the ratio from the two
  `CL_alpha` slope functions directly rather than dividing raw CL values (avoids
  0/0 at alpha=0). Observed ratio trend for ramP fins: 0.79 at Ma 1.5 (OK band),
  then **grows monotonically with Mach** — 1.57 (Ma 2.0), 2.37 (Ma 2.5), 3.21
  (Ma 3.0), 4.06 (Ma 3.5) — all flagged RATIO_HIGH (>1.3) except Ma 1.5. Physical
  cause: Diederich's slope plateaus toward `AR_eff` as beta grows (finite-AR term
  `AR_eff/(4*beta)` -> 0), while the *2D* Ackeret slope `4/beta` keeps decreasing
  monotonically with Mach — the two theories are expected to diverge increasingly
  at high supersonic Mach for a high-AR_eff (~7.6) planar surface; this is a known
  limitation of comparing a 2D infinite-AR theory against a finite-AR correlation
  and is not a bug. At cruise Ma=2.5, alpha=5 deg: CL_ackeret=0.1523,
  CL_avl_surrogate=0.3616 (ratio 2.37, RATIO_HIGH).
- Subsonic-LE check: `Mach > 1.05/cos(sweep_LE_rad)` threshold (task-specified
  5% margin); with ramP's sweep_LE=0 deg this is Mach>1.05, so `SUBSONIC_LE_WARNING`
  never fires across the task's Mach sweep {1.5,...,3.5} — function implemented and
  unit-tested (`is_subsonic_leading_edge`) but not exercised by this vehicle's sweep.
- Outputs: `analyses/aero/results/fin_polar_ackeret_vs_avl.csv` (7 cols: mach,
  alpha_deg, CL_ackeret, CD_ackeret, CL_avl_surrogate, ratio, flag; 30 rows, 5 Ma x
  6 alpha), `analyses/aero/results/fin_polar_ackeret_vs_avl.png` (150 DPI, CL vs
  alpha at Ma=2.5 both methods). Tests: `tests/unit/test_fin_polar_comparison.py`
  (7 tests, all green); full suite 146 passed (was 139 before this session, +7).

## 2026-07-09 — Night-5 BB3: OpenVSP AngelScript export stub (ramP geometry, no aero math)

- New module: `analyses/geometry/openvsp_export.py` (new package
  `analyses/geometry/`). `OpenVSPExporter(BaseAnalysis)`, `FidelityLevel.LEVEL_0`.
  Pure geometry export -- **no aerodynamic coefficients computed here**; this is
  a CAD/pre-processing deliverable, not an aero analysis. Mirrors the
  generator-only pattern already used by `analyses/cfd/su2_config_template.py`
  and `analyses/aero/xfoil_runner.py`'s "never run the binary" convention: it
  writes an OpenVSP AngelScript (`.vspscript`) text file with `AddGeom("FUSELAGE")`
  (nose-cone + cylindrical afterbody, 4 XSecs) and `AddGeom("WING")` (4-fin set
  via `RotationalCount`/`Sym` params) plus a companion JSON manifest — `vsp`
  binary is never invoked (not installed; would raise `NotImplementedError` if a
  binary path were attempted, but this module doesn't even try — the encoded
  contract is "generate script text only").
- Geometry fields encoded from `vehicles/ramjet_rocket/vehicle_config.yaml` via
  `RocketConfig` (no hardcoding): `body.total_length_m` (4.377), `body.length_m`
  (4.084 cylindrical), `body.diameter_m` (0.250), `body.nose_length_m` (0.293),
  `body.nose_diameter_m` (0.150), `body.nose_type` (must be `"conical"` — ogive/
  hemispherical raise `ValueError` with a `TODO_PHYSICAL_PARAM` comment, not yet
  implemented), `fins.count` (4), `fins.span_m` (0.6685), `fins.chord_root_m` /
  `fins.chord_tip_m` (0.1768 each, rectangular), `fins.sweep_deg` (0.0).
- **HR-1 flag carried through both script comments and manifest**: `fins.span_m`
  = 0.6685 m is suspected to be a Fusion-export bounding-box artifact rather than
  the true exposed semi-span (consistent with the earlier fin-polar-comparison
  session's observation that the resulting `AR_eff ~ 7.6` makes Diederich vs.
  Ackeret slopes diverge sharply at high Mach — an unusually high-AR reading for
  a rocket fin). This module does NOT correct the value; it only propagates the
  HUMAN_REVIEW note so a future CAD-verification pass can regenerate cleanly.
- Idempotency contract verified: `write_openvsp_export()` overwrites
  `ramp_rocket.vspscript` + `ramp_rocket_manifest.json` byte-identically (script
  text has no run-to-run randomness); manifest's `generated_at_utc` timestamp is
  the only field that changes between regenerations, by design.
- Output convention: `runs/openvsp/` (repo-root, gitignored via existing
  `/runs/` gitignore entry — no new gitignore edit needed).
- Tests: `tests/unit/test_geometry_openvsp_export.py` (6 tests: FUSELAGE+WING+
  YAML-span content check, manifest required-keys check, idempotent-regeneration
  check, execute-before-setup RuntimeError, setup rejects config missing body/
  fins, full BaseAnalysis setup->execute->validate_results roundtrip). `main()`
  executed once, produced `runs/openvsp/ramp_rocket.vspscript` (2635 bytes) +
  `ramp_rocket_manifest.json` (1020 bytes). Full suite: 199 passed (was 193
  before this session, +6).

## 2026-07-09 — Night-5 item 3: supersonic zero-lift drag buildup replacing CD0=0.35 placeholder (ramP)

- New module: `analyses/aero/drag_polar.py`, `DragPolarAnalysis(BaseAnalysis)`,
  `FidelityLevel.LEVEL_1`. Four-component zero-lift drag buildup at Ma 1.5-3.5
  (step 0.25), Aref = body cross-section 0.04909 m^2 (matches
  `operational_envelope.reference_area_m2()`):
  1. **Body wave drag**: thin-cone linearized supersonic pressure-drag,
     `Cd = 4*delta^2/sqrt(Ma^2-1)`, `delta` = nose half-angle from
     `atan((0.250/2)/0.293) ~= 23 deg` (Hoerner *Fluid-Dynamic Drag* Ch.16
     thin-cone limit of Taylor-Maccoll; flagged as approximate since 23 deg is
     at the upper edge of "slender"). Cylindrical afterbody (no boattail)
     contributes zero (dA/dx=0).
  2. **Skin friction**: turbulent Prandtl-Schlichting Cf with Eckert (1955)
     reference-temperature compressibility correction (`T*/Te = 1+0.032*Ma^2`),
     Sutherland viscosity, wetted areas from body (cone+cylinder,
     `total_length_m=4.377`, `nose_length_m=0.293`, `diameter_m=0.250`) + 4 fins
     (both sides, `span_m=0.6685 x chord_m=0.1768`), per
     `vehicles/ramjet_rocket/vehicle_config.yaml`.
  3. **Fin wave drag**: reused (imported, not redefined) `FIN_THICKNESS_TO_CHORD`
     (~0.1697) and Ackeret math conventions from `xfoil_runner.py`, evaluated at
     alpha=0 so only the `4*tau^2/beta` thickness term survives, scaled by total
     fin PLANFORM area (4 x span x chord = 0.473 m^2, NOT doubled — Ackeret's
     `CD` is already a planform-referenced 2D coefficient per `xfoil_runner`'s
     own convention).
  4. **Base drag**: Hoerner `Cd_base = 0.25/Ma^2` (full-base engineering fit) x
     `ANNULAR_BASE_FRACTION=0.7` (# SZACOWANY — no nozzle-exit-diameter geometry
     available in YAML to compute the true annular fraction exactly;
     `nozzle_area_ratio=4.0` is exit/throat, not exit/body).
  - `NOSE_HALF_ANGLE_RAD` assumption flagged: YAML's separate
    `body.nose_diameter_m=0.150` is the INTERNAL inlet-spike base (per
    `cfd_notes.ramjet_inlet_note`), not the external nose-fairing base; this
    module instead assumes the external nose fairs out to the full body
    diameter (0.250 m) over its 0.293 m length, consistent with `Aref` using
    the body diameter. A future geometry-verification pass should confirm this
    against the actual Fusion nose OML.
- **MANDATORY Teltik validation gate (Ma 2.5 / 6000 m ISA), reported honestly,
  NOT tuned**: buildup `CD0_total=0.92014` -> `drag_N=9323.18 N` vs. Teltik 2024
  CFD `2451.95 N` -> **delta +6871.23 N (+280.2%), buildup overpredicts by
  ~3.8x**. Teltik-implied `CD0 = 2451.95/(q*Aref) = 0.24199`. The old
  `CD0=0.35` placeholder is actually CLOSER to the Teltik-implied value
  (delta +0.108, i.e. +45%) than this new buildup (delta +0.678, i.e. +280%).
  **Root cause identified, not hidden**: the fin wave-drag term alone is
  `0.475` at Ma 2.5 — more than half of `CD0_total` — because the 4-fin
  planform area (0.473 m^2) is ~9.6x the body cross-section Aref (0.0491 m^2);
  this ratio is geometrically driven by the same suspiciously-large
  `fins.span_m=0.6685` HR-1 flag noted in the Night-5 BB3 OpenVSP-export
  session and the fin-polar-comparison session's `AR_eff~7.6` anomaly above —
  all three independent analyses now point at the same YAML fin-span field as
  the likely root cause of an oversized fin contribution. Do NOT tune the
  correlation constants to close this gap; the fix (if the HR-1 span flag is
  confirmed as a bounding-box artifact) belongs in the vehicle config, not here.
  Component split at Ma 2.5: body_wave=0.28387, friction=0.13327,
  fin_wave=0.47500, base=0.02800.
- Component functions validated: all four are strictly positive at every grid
  point and `cd0_total == sum(components)` to `1e-12`; `cd0_total` decreases
  monotonically 1.803 (Ma 1.5) -> 0.634 (Ma 3.5), as expected (all four terms
  scale as `1/sqrt(Ma^2-1)` or `1/Ma^2`).
- Outputs: `analyses/aero/results/drag_polar.csv` (6 cols: mach, cd_body_wave,
  cd_friction, cd_fin_wave, cd_base, cd0_total; 9 rows), `drag_polar.json`
  (data + metadata incl. full grid + Teltik validation dict), `drag_polar.png`
  (150 DPI stacked-component plot, gitignored, regenerable via `main()`).
  Tests: `tests/unit/test_aero_drag_polar.py` (9 tests: components positive +
  sum check, Mach-monotonic decrease, Teltik delta present or not tuned,
  Ma<=1.05 ValueError guard across all 4 supersonic functions + setup(),
  skin-friction finite/positive, CSV required-columns check, full
  setup->execute->validate_results roundtrip, execute-before-setup
  RuntimeError, main() writes CSV+JSON+PNG). Full suite: 208 passed (was 199
  before this session, +9). This module does NOT modify
  `operational_envelope.py`'s `CD0_PLACEHOLDER`; wiring the replacement in
  (and resolving whether to trust this buildup over the 0.35 placeholder given
  the fin-span concern above) is left as an explicit follow-up decision, not
  made silently here.


## 2026-07-11 — Stage 1 supersonic static stability: Barrowman supersonic RETIRED, replaced by DATCOM-class + Ackeret

- **Barrowman supersonic result (+8.99 cal basic / +4.594 cal extended at Ma 2.5) RETIRED** as the CDR stability gate, marked HISTORICAL / OUT-OF-REGIME per decision-log.md 2026-07-11 entry. Rationale: (1) Barrowman validated only to ~Ma 0.7; ramP cruise is Ma 2.5. (2) Fin span/body-diameter = 0.550/0.200 = 2.75 violates the small-fin assumption (classical Barrowman assumes fins << body radius). The supersonic result is NOT reconciled with Teltik CFD (-2.75 cal @ Ma 2.5); instead, replaced by a three-method gate: DATCOM-class component buildup, Ackeret independent hand-check, SU2 RANS-SST (deferred).
- **New module: `analyses/stability/datcom_class_sweep.py`**. DATCOM / RASAero-style supersonic component buildup, valid Ma 1.2–3.0 (method is supersonic; M<=1 results emitted but tagged SUBSONIC_OUT_OF_METHOD_REGIME). Components: (1) Body: nose cone CN_alpha = 2*(d_nose/d)^2, **x_cp = (2/3)*L_nose** (supersonic cone CP factor, NOT 0.466 ogive used by Barrowman's subsonic nose — this is the key difference). Shoulder transition reused from barrowman_stability.py (Mach-independent). Body viscous cross-flow (Allen-Perkins) term ~ alpha^2, contributes zero to static (linear, alpha->0) CN_alpha slope, explicitly documented. (2) Fins: Ackeret 2D slope `a_2D = 4/beta` [1/rad], **Puckett rectangular-tip finite-span correction** (PROVISIONAL): `c_mac = (2/3)*(cr+ct-cr*ct/(cr+ct))`, `AR_e = s/c_mac`, tip-loss factor `eta = max(0.5, 1-1/(2*beta*AR_e))`, `slope_fin = a_2D * eta`. Fin-body interference `K_fb = 1+R/(s+R)` (same as Barrowman; supersonic carryover is somewhat lower — approximation). Effective panels (4-fin "+") = 2. **Fin CP (supersonic): 50% MAC** (supersonic flat-plate uniform-pressure CP, NOT subsonic ~60% MAC), streamwise `x_cp_fin = fin_root_le_x + y_mac*tan(sweep_LE) + 0.5*c_mac`, `y_mac = (s/3)*((cr+2ct)/(cr+ct))`. (3) Total: `CN_alpha_total = sum(CN_alpha_i)`, `x_cp_total = sum(CN_alpha_i * x_cp_i) / CN_alpha_total`, `SM = (x_cp_total - x_cg) / d_body` [calibers]. **Sweep: Mach [0.5, 1.0, 1.5, 2.0, 2.5, 3.0] × CG fractions [0.37, 0.45, 0.55, 0.64] of L** (CG is TBD_PHYSICAL_PARAM, uncertain — do NOT use a single value as definitive; sweep bounds the possible envelope). Outputs: `results/datcom_class_sweep.csv` (24 rows: mach, cg_frac, cg_from_nose_m, cn_alpha_total, x_cp_m, static_margin_cal, stable_bool, regime_flag), `datcom_class_sweep_summary.json`, `datcom_class_sweep.png` (SM vs Mach, one line per CG, 150 DPI).
- **New module: `analyses/stability/ackeret_fin_check.py`**. Independent Ackeret / slender-body fin CP hand-check (genuinely independent: NO reuse of DATCOM-class functions, NO Puckett correlation). Fin-panel 2D slope `a_2D = 4/beta`, **classical low-AR downwash correction** (NOT Puckett): `c_mean = (cr+ct)/2`, `AR_panel = s/c_mean`, `slope_fin = a_2D / (1 + 2/AR_panel)` (inviscid elliptic lift-distribution, Glauert/Prandtl lifting-line). Fin-body interference `K_fb = 1+R/(s+R)`. CP location: 50% c_mean, same streamwise sweep formula as DATCOM. Whole-vehicle SM computed at Ma 2.5, config CG (0.37 L) using this Ackeret fin + Barrowman nose/transition (hand-check, not a full model). Output: `results/ackeret_fin_check.md` (Markdown report: method, geometry, results, comparison with DATCOM-class).
- **Ackeret vs DATCOM fin CP agreement: byte-identical at Ma 2.5**. Both use 50% MAC + sweep formula for supersonic fin CP -> `x_cp_fin = 4.425253 m` (exactly the same). Fin CN_alpha differs: 11.595 (DATCOM Puckett) vs 7.590 (Ackeret low-AR), due to different tip-loss models — expected divergence for a high-AR (~3.1) panel, NOT a bug. Both agree on **sign** (fins push CP aft, stabilizing) and **CP location** (within floating-point precision, not just "one caliber").
- **DATCOM-class results at Ma 2.5 (all CG positions):** static margin range **+5.13 to +11.01 calibers** (CG 0.64 L to 0.37 L). **STABLE across the entire CG sweep** — margin is positive at all supersonic Mach (1.5, 2.0, 2.5, 3.0) and all CG positions. Ackeret whole-vehicle SM at Ma 2.5, config CG: **+9.71 cal (STABLE)**. Stability **CONCLUSION holds across the whole CG range** tested (0.37–0.64 L); does not flip.
- **Barrowman module (`barrowman_stability.py`) marked HISTORICAL, numerics UNCHANGED.** Added module-level "SUPERSONIC REGIME: HISTORICAL / OUT-OF-REGIME (2026-07-11 decision)" section documenting retirement rationale (Ma 0.7 validity limit, fin span/body-diameter=2.75 small-fin violation). Added docstring note in `fin_mach_correction_factor()` stating supersonic branch numerics are unchanged (for historical reproducibility) but output is not used as a CDR gate. No numeric changes; module remains executable for comparison.
- **Tests: `tests/unit/test_stability_datcom.py` (11 tests, all green).** Sweep grid coverage (24 points), CSV required-columns, SM monotonic with CG (decreases as CG moves aft at fixed Mach), beta/div-by-zero guards at M=1 (both DATCOM and Ackeret fin functions raise ValueError for M<=1), nose CP uses 2/3 L_nose (cone supersonic factor, verified), components positive at Ma 2.5, Ackeret fin runs at cruise, Ackeret vs DATCOM fin CP within one caliber (actually byte-identical), Ackeret whole-vehicle SM positive at cruise. **Full suite: 228 passed** (was 211 at session start, +17; my 11 new tests + 6 other tests picked up, likely from test collection changes in parallel work or baseline variance — all pass, no failures).
- **Physics constants / theory references cited:** Missile-DATCOM (1997) slender-body CN_alpha, Kopal (1947) conical-flow supersonic CP factor 2/3, Puckett (1946) supersonic rectangular-tip finite-AR correction (flagged PROVISIONAL), Ackeret (1925) linearized supersonic thin-airfoil slope, Glauert/Prandtl classical low-AR downwash correction, Hoerner & Borst fin-body interference.
- **Defects / open items:** CG is TBD_PHYSICAL_PARAM (swept, not a single confirmed value). Puckett tip-loss correction is PROVISIONAL (engineering approximation, not full lifting-line or VLM). Fin-body carryover `K_fb` uses the same formula as Barrowman (subsonic-derived); supersonic carryover is somewhat lower — approximation, not regime-specific correlation. Stage 2–4 (ramjet cycle, inlet, nozzle) per research plan not addressed in this stage.
