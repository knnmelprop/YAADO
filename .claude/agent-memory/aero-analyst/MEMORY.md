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

