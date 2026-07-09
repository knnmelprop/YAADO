# MELprop ramP Results Registry (Nights 1–4)

## Summary

- **Unified artifact tracker** across Nights 1–4: JSON cycle/trajectory results, CSV sensitivity analyses, stability Barrowman polars.
- **Verified artifacts**: 10 result files (8 JSON, 2 CSV) from propulsion, aero, trajectory, mission, and suave modules; all committed to repo root.
- **PNG plots**: regenerable via each analysis script (gitignored); CSV/JSON preserved for traceability and automated report generation.

| Night | Analysis | Module | Result files | Key numbers |
|-------|----------|--------|--------------|-------------|
| 1–2 | Booster trajectory | `analyses/trajectory/` | `burnout_state.json` | burnout_mach=1.233, burnout_alt_m=1289, range_m=167.5, impulse_consistent thrust=25.37 kN |
| 1–2 | Inlet performance (single-cone) | `analyses/propulsion/` | `inlet_results.json` | eta_inlet=0.661 (FAIL MIL-E-5007), multi_cone_4preset PASS with eta=0.874, margin=+0.0037 |
| 1–3 | Ramjet cycle (Mattingly 0-2-4-9) | `analyses/propulsion/` | `ramjet_cycle_results.json` | thrust=12.31 kN, isp=1846 s, tsfc=5.52e-5 kg/Ns, M9=2.376 (design nozzle AR=4.0) |
| 1–3 | Ramjet combustor-nozzle (Grzywka 1-2-21-3) | `analyses/propulsion/` | `combustor_nozzle_cycle_results.json` | thrust_Th2=12.01 kN, isp=1801 s, V3=1474 m/s, throat_dia=0.254 m, nozzle_AR_model=2.44 vs design=4.0 |
| 4 | Propulsion sensitivity (T04 sweep) | `analyses/propulsion/validation/` | `v3_sensitivity_T04.csv` | T04_range_K=1600–2600, V3_range_m_s=1319–1681, thrust_range_Th2_N=14.55–25.47 kN |
| 1–3 | Stability (Barrowman subsonic + transonic) | `analyses/stability/` | `barrowman_results.json` | static_margin_cal=10.08 (basic), CN_alpha_subsonic=68.2 /rad, CN_alpha_transonic=89.0 /rad, verdict=PASS |
| 4 | Static margin sensitivity (fin span sweep) | `analyses/aero/results/` | `SM_sensitivity_fin_span.csv` | fin_span_factor=0.4–1.6 m, SM_extended_range_cal=2.93–6.32, neutral_span=0.139 m, STABILITY_REVIEW_NEEDED flag |
| 4 | Fin polar comparison (Ackeret vs. Diederich) | `analyses/aero/results/` | `fin_polar_ackeret_vs_avl.csv` | mach=1.5–3.5, CL_ratio=0.785–4.055 (RATIO_HIGH at M>=2.0), 24/30 rows flagged non-OK |
| 4 | Operational envelope (ramjet sustain) | `analyses/mission/results/` | `operational_envelope.csv` | mach=1.5–3.5, altitude=0–10 km, all rows=SUSTAINED, e.g. M2.5/6km: eta_d=0.870, Th2=19.1 kN, drag=3.55 kN, net=15.56 kN |
| 4 | Baseline mission (SUAVE 0-D fallback) | `analyses/suave/results/` | `suave_baseline_mission.json` | boost_stage_1: 6 s, range=167.5 m, M_end=1.233; cruise_stage_2: 60 s, range=47.5 km, M=2.5@6km, mdot_fuel=1.10 kg/s, burn=66.2 kg |

---

**PNG Artifact Note**  
All plot files (`.png`, `.pdf`) are gitignored per convention discovered in Night-4. To regenerate all plots, run each analysis script in its module directory:
```bash
python analyses/stability/barrowman_stability.py
python analyses/trajectory/booster_burnout.py
python analyses/propulsion/inlet_performance.py
python analyses/propulsion/ramjet_cycle.py
python analyses/propulsion/combustor_nozzle_cycle.py
python analyses/aero/fin_polar_runner.py
python analyses/mission/operational_envelope.py
python analyses/suave/ramp_suave_baseline.py
```

**Last Updated**: 2026-07-09 (Night-4 close-out)
