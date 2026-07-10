# Preliminary Analysis Report — 2026-07-10

Ran every self-executable analysis script in the repo end-to-end against
the current vehicle configs, in the newly-separated `knnmelprop/iade`
repo. 16/16 scripts ran cleanly (exit 0). Found and fixed one real bug in
the process (below). This report covers: what's runnable now, what
result values came out, what input data is still missing, and
recommended next work — it does not introduce new physics or change any
model.

**pytest: 208 passed, 0 failed**, unchanged before/after this run.

## Bug found and fixed while running this

`workflows/ramp_staged_mission.py` hardcoded its cruise-summary output
path as `doc/ramP/cruise_summary_night3.md` — a leftover from before
Phase 1's `doc/`→`docs/` consolidation. It's constructed as
`this_dir.parent / "doc" / "ramP" / ...` in code, not a literal string, so
it didn't show up in the grep-based `trunk`/`doc/` audits done in earlier
phases (those only catch static text, not runtime path construction).
Running the script recreated a stray `doc/` directory. Fixed to
`docs/ramP/...`, verified the corrected script writes to the right place,
and removed the stray untracked directory. This is exactly the kind of
gap a "grep for stale paths" pass can miss — only running the code
surfaces it.

## What's possible to run now

### Project B (ramP rocket) — fully covered at L0/L1/L2 fidelity, 16/16 scripts run clean

| Analysis | Script | Key result |
|---|---|---|
| Static stability (basic Barrowman) | `analyses/stability/barrowman_stability.py` | CP 4.128 m, CG 1.608 m, **SM = 10.08 cal, PASS** (margin +8.33 cal over the 1.75 cal requirement) |
| Static stability (extended, body-lift corrected) | `analyses/aero/barrowman_extended.py` | SM_extended still **+7.344 cal above Teltik CFD** even after correction — `review_needed = True` |
| Boost trajectory | `analyses/trajectory/booster_burnout.py` | Nominal (near-vertical) run: burnout Mach 1.233, altitude 1289 m, q_max 92.4 kPa @ 6 s. Separate launch-angle sweep: **5° recommended** (avoids premature ground impact, burnout alt ≈45 m) |
| Inlet performance (fixed single-cone) | `analyses/propulsion/inlet_performance.py` | η=0.6606 vs MIL-E-5007 0.8703 — **FAILS** by −0.21 margin at design point (expected; single-cone is known-inadequate) |
| Inlet actuation (4-cone variable geometry) | `analyses/propulsion/inlet_actuation.py` | η=0.8741 @ Ma2.5, η=0.7444 @ Ma3.5 — **PASSES** MIL-E-5007 contiguously on Mach [2.4, 3.5] |
| Ramjet cycle (ideal, 1-D) | `analyses/propulsion/ramjet_cycle.py` | Isp 1846 s, thrust 12,307 N (matched-nozzle) vs **9,854 N (cylindrical CAD reality)** |
| Combustor+nozzle cycle (Grzywka model) | `analyses/propulsion/combustor_nozzle_cycle.py` | Th1=12,108 N, Th2=12,009 N (hierarchy holds); **V3 = 1474 m/s vs Teltik CFD 1047 m/s (+40.8%)** |
| V3 discrepancy root-cause sensitivity | `analyses/propulsion/validation/_v3_analysis_helper.py` | Confirms nozzle area-ratio assumption (2.44 model vs 1.0 CAD) is the **primary** driver, not T04 or gamma (gamma fix to 1.28 only moves V3 by −4.5%) |
| Drag polar (wave+friction+base buildup) | `analyses/aero/drag_polar.py` | **CD0@Ma2.5 = 0.920 buildup vs 0.242 Teltik-implied (+280%)** — fin wave drag dominates |
| Fin polar (Ackeret vs Diederich surrogate) | `analyses/aero/fin_polar_comparison.py` | Ratio 2.37 @ Ma2.5/α=5°; **24/30 grid cells flagged RATIO_HIGH** |
| Operational envelope (Ma×altitude grid) | `analyses/mission/operational_envelope.py` | All 30 cells marked SUSTAINED — but still using **CD0=0.35 placeholder**, not the 0.920 buildup above |
| 0-D mission (SUAVE-fallback) | `analyses/suave/ramp_suave_baseline.py` | Total range 47,631.5 m (boost 167.5 m + 60 s cruise placeholder → 47,464 m) |
| Staged mission workflow | `workflows/ramp_staged_mission.py` | Net thrust margin at cruise: +10,121 N (vs 0-order drag) / +9,656 N (vs Teltik CFD drag) |
| XFOIL/Ackeret fin polar (single point) | `analyses/aero/xfoil_runner.py` | Correctly falls back to Ackeret (Mach range is supersonic; XFOIL not valid, not installed) |
| SU2 Euler config generator | `analyses/cfd/su2_config_template.py` | Wrote 5 configs, Mach 0.8–3.0 sweep, to `runs/su2/` — **configs only, SU2 itself not invoked** |
| OpenVSP export stub | `analyses/geometry/openvsp_export.py` | Wrote a `.vspscript` to `runs/openvsp/` — **stub only, OpenVSP binary not invoked** |

### Project A (GTM-140 drone) — nothing runnable yet

No `__main__`-executable script exists beyond `analyses/aerodynamics/avl_wrapper.py` (a library class, not a runnable analysis). The vehicle config (`vehicles/gtm140_drone/vehicle_config.yaml`) has three blocking `# TBD` values: `aspect_ratio` (8.0, placeholder), `sfc_kg_per_Ns` (0.000028, placeholder), `mass_kg` (1.2, placeholder) — none sourced from real data. There is nothing meaningful to run for Project A until at least the engine datasheet lands.

### Newly-available but not yet exercised

`external/su2` and `external/openvsp` were added as submodules this session but neither has been built or run — the SU2 config generator produces valid input files for a solver that hasn't been compiled here, and the OpenVSP export is a stub for the same reason (no binary). This is genuinely new capacity: the repo can now generate real SU2 input decks, but actually running them (build SU2, execute a case, parse `.dat`/`.vtu` output) hasn't been attempted.

## What input data is still needed

These are pre-existing gaps in the repo's own docs (`docs/assumptions.md`, `docs/ramP/human_review_night4.md`), not new findings — consolidated here because they directly gate the next round of analysis:

| # | Item | Blocks |
|---|---|---|
| HR-1 | Fin span (0.6685 m) suspected wrong by 3–8× vs Fusion CAD — drag polar (+280% CD0) and stability sign-flip (SM +8.99 cal Barrowman vs −2.75 cal Teltik CFD @ Ma2.5) both point at this | Trustworthy stability margin, drag polar, operational envelope |
| HR-2 | Teltik CFD mesh/geometry version not confirmed against current YAML geometry | Any comparison against Teltik as ground truth |
| HR-3 | Nozzle design decision: Laval (area_ratio ≈4.0, design intent) vs cylindrical (CAD as-built, ratio 1.0) | Real thrust/Isp/V3 number — currently reporting two divergent values every run |
| HR-4 | Stage-1 solid motor real datasheet (Isp, thrust curve, propellant mass) — currently internally-reconciled `SZACOWANY` values | Trustworthy boost trajectory, staging, launch-angle recommendation |
| HR-5 | Ixx/Iyy/Izz moments of inertia (Fusion GUI extraction, not available via API) | Any dynamic-stability or 6-DOF work beyond the current static-margin analysis |
| HR-6 | `max_rpm` units convention (unresolved naming ambiguity) | Turbomachinery-adjacent config fields, if used later |
| HR-7 | T04 combustor temperature source confirmation (currently 2000 K assumed, below the 2400 K flame-holder risk figure) | Combustor design confidence, flame-holder material decision |
| HR-8 | Combustion-products composition / gamma (currently 1.28 assumed) | Small lever on V3 (~5%) but still unconfirmed |
| HR-9 | Which CD0 to treat as authoritative for cruise design (0.35 placeholder / 0.242 Teltik-implied / 0.920 buildup) — explicitly *not* resolved by design in the last session that touched this | Operational envelope, cruise fuel/range trade |
| — | Jetpol GTM-140 datasheet (mass, SFC) + MELprop's own wing aspect-ratio/CAD data | All of Project A — currently zero runnable analyses |
| — | `design_mach: 2.5` in `vehicles/ramjet_rocket/vehicle_config.yaml` is still marked `# TBD — decyzja projektowa` despite being used as 2.5 throughout every analysis above | Formal design sign-off; currently a de facto default, not a confirmed decision |
| — | Fuel type/mass budget and recovery-system approach for stage 2 — not modeled anywhere in the repo | Full mission closure (currently a 60 s cruise-duration placeholder stands in for a real fuel/range trade) |

## Recommendations for next work

Ranked by leverage — highest-impact / most-blocking first:

1. **Resolve HR-1 (fin span) first.** It's implicated in two independent discrepancies simultaneously (stability sign-flip *and* the 280%-high drag polar). A single CAD verification against Fusion likely resolves both at once — this is the highest-leverage open item in the repo.
2. **HR-3 (nozzle decision)** next — it's the confirmed root cause of the V3/thrust discrepancy (independently verified via the sensitivity helper, ruling out T04/gamma). Every propulsion number downstream (thrust, Isp, cruise margin) currently reports two divergent values because this isn't decided.
3. **Get the stage-1 motor datasheet (HR-4).** The trajectory/staging results are internally consistent but built on `SZACOWANY` inputs — real numbers would either confirm or invalidate the current 5° launch-angle recommendation.
4. **Re-run the operational envelope with the real drag polar** once HR-1 is resolved, replacing the CD0=0.35 placeholder — this was already flagged as the next step by a prior session and still hasn't been done; the buildup CD0 (0.920) is sitting right there unused.
5. **Get the GTM-140/Jetpol datasheet** to unblock Project A entirely — right now it's the only one of the two projects with literally nothing runnable.
6. **Actually exercise the new SU2 submodule.** The config generator already produces 5 valid Mach-sweep Euler decks; building SU2 and running even one case would give independent CP/drag data directly relevant to resolving HR-1/HR-2 — this is new capacity this session unlocked but hasn't used yet.
7. **Formalize `design_mach: 2.5`** as a real decision rather than a `# TBD` that everything already treats as final.

None of the above requires code changes to get started — items 1–3 and 5 are data-acquisition (CAD, datasheets), item 4 is a config change once HR-1 lands, item 6 is infrastructure (build SU2) rather than new modeling.
