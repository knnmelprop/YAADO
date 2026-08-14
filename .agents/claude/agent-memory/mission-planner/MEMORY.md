# Mission Planner Memory Log

This file tracks validated segment definitions, staging event state continuities, Mach×altitude constraints, ISA corrections, and MDO convergence histories.

## 2026-07-09 — SUAVE baseline mission wiring (analyses/suave/ramp_suave_baseline.py)

**Task**: Wire Night-3 propulsion data (P1-C operational envelope) into a SUAVE
baseline mission with a 0D fallback. New files only, no core/YAML/trunk edits.

**Critical environment finding — `import SUAVE` is NOT a reliable availability
probe in this container**: the repo root has an empty stub directory
`/home/user/droneEnv/SUAVE/` containing only `version.py` (no `__init__.py`),
which Python treats as an implicit **namespace package**. A bare `import SUAVE`
therefore **succeeds silently** (`SUAVE.__file__ is None`,
`SUAVE.__path__ == _NamespacePath(['/home/user/droneEnv/SUAVE'])`), shadowing
the real reference fork in `trunk/SUAVE/` (which has a real `__init__.py` and
`Analyses/Mission/Segments/` etc., but is never added to `sys.path`). Any
guarded-import check MUST attempt the specific deep submodule the workflow
needs (e.g. `from SUAVE.Analyses.Mission.Segments.Cruise import
Constant_Mach_Constant_Altitude`) — this correctly raises
`ModuleNotFoundError` (an `ImportError` subclass), which a plain
`except ImportError` catches fine. A bare `try: import SUAVE / except
ImportError` alone WILL NOT trigger the fallback — it will false-positive as
"available" and then crash later on `AttributeError` when real SUAVE API
calls are attempted. Pattern used:
```python
def _probe_suave_available() -> bool:
    try:
        import SUAVE
        from SUAVE.Analyses.Mission.Segments.Cruise import Constant_Mach_Constant_Altitude
        from SUAVE.Analyses.Mission.Segments.Climb import Constant_Mach_Linear_Altitude
        return True
    except ImportError:
        return False
```
Confirmed via `python3 -c "import SUAVE; from SUAVE.Analyses... "` — raises
`ModuleNotFoundError: No module named 'SUAVE.Analyses'`. Re-check this probe
each session; if a real SUAVE install is ever added to sys.path ahead of the
stub, `SUAVE_AVAILABLE` will flip to True and `build_mission_suave()` (real
`SUAVE.Analyses.Mission.Sequential_Segments` construction, written but never
exercised) becomes reachable — smoke-test it before trusting it.

**Fallback 0D mission pattern (this is what actually runs)**: two-segment
baseline (`boost_stage_1` + `cruise_stage_2_ramjet`), NOT the 3-segment
`workflows.ramp_staged_mission` staging profile (no `staging_event` segment —
out of this baseline's scope, noted explicitly in output JSON `notes`).
Reused rather than duplicated:
- `analyses.mission.operational_envelope.{isa_atmosphere, compute_th2_thrust_N,
  compute_drag_N, reference_area_m2, CD0_PLACEHOLDER, NIGHT3_MACH,
  NIGHT3_ALTITUDE_M}` for the cruise segment — reproduces the committed P1-C
  operational-envelope grid point at Mach 2.5/6000 m ISA EXACTLY (not just
  within tolerance): `Th2_N=19107.352487726544`, `drag_N=3546.3356928511203`.
- `analyses.propulsion.combustor_nozzle_cycle.GrzywkaCombustorNozzleAnalysis`
  run a second time (with the same `eta_inlet=mil_e_5007_eta_std(mach)`
  override as `operational_envelope`) ONLY to pull `mdot_fuel_kg_s`, since
  `compute_th2_thrust_N` doesn't expose it.
- `analyses.trajectory.booster_burnout.{load_booster_params,
  drag_coefficient}` for the boost segment's drag (evaluated at the
  `burnout_state.json` handoff state); thrust taken directly from that JSON's
  `metadata.thrust_used_N` (impulse-consistent `Isp_sl*mdot*g0`).

**Placeholders introduced (both `# SZACOWANY`)**:
- `CRUISE_DURATION_FALLBACK_S = 60.0` — `vehicles/ramjet_rocket/
  vehicle_config.yaml` `stage_2` has NO `fuel_mass_kg` field (only
  `combustor_temp_K`, `nozzle_area_ratio`, `design_mach`, `fuel_type`), so
  cruise duration can't be derived from a real fuel budget; matches the same
  order-of-magnitude stub already used in
  `workflows.ramp_staged_mission._STUB_CRUISE_DESIGN_POINT` for repo-wide
  consistency of the "no real fuel budget" flag (NOT independently derived —
  do not treat as validated).
- `BOOST_INITIAL_ALTITUDE_M = 100.0` mirrors `booster_burnout.H0_M`.

**Result of this run**: fallback path executed (as expected — SUAVE
unavailable). `total_range_m = 47631.5 m` (boost 167.5 m + cruise 47464.0 m
at fixed 60 s placeholder duration — this range number is only as good as the
60 s SZACOWANY cruise duration, treat as illustrative, not a validated mission
range). Cruise thrust margin at this design point:
`Th2/drag = 19107.4/3546.3 ≈ 5.39` (well above the 1.1 margin rule; note this
is a single design point, not a full envelope sweep — see
`analyses/mission/operational_envelope.py`/CSV for the full 30-point grid,
all SUSTAINED as of P1-C).

**Tests**: `tests/unit/test_suave_baseline.py`, 11 tests, all green
(`python -m pytest tests/unit/test_suave_baseline.py -v` and full suite
`python -m pytest tests/ -q` — 157 passed, no regressions vs prior 139/146
baseline). Notable test: `test_probe_suave_available_is_false_in_this_container`
pins the namespace-package-shadow finding above as a regression guard —
if this ever starts failing (SUAVE_AVAILABLE flips True), the SUAVE path
(`build_mission_suave`, currently `# pragma: no cover`) needs a real smoke
test before being trusted.

