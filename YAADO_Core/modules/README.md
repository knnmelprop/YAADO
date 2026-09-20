# Physics Modules

This directory contains the swappable physics solvers for the YAADO framework. Solvers derive from `BaseAnalysis` and return standard `AnalysisResults` containers.

## Repaired and Verified Methods:

| Submodule | Method / Tool | File | Fidelity | Description |
| :--- | :--- | :--- | :---: | :--- |
| **Flight Dynamics** | `PointMass3DOFBoostAnalysis` | [`flight_dynamics/methods/point_mass_3dof.py`](flight_dynamics/methods/point_mass_3dof.py) | L0 | 3-DOF point-mass rocket boost trajectory simulation |

## Not Yet Repaired and/or Verified Methods:

| Submodule | Method / Tool | File | Fidelity | Description |
| :--- | :--- | :--- | :---: | :--- |
| **Airframe** | `OpenVSPExporter` | [`airframe/generator_methods/openvsp.py`](airframe/generator_methods/openvsp.py) | L1 | OpenVSP geometry generation |
| **Airframe** | Gmsh Slicer | [`airframe/slicer_methods/gmsh.py`](airframe/slicer_methods/gmsh.py) | - | STEP cross-section slicing utility |
| **Powerplant** | `InletPerformanceAnalysis` | [`powerplant/inlet_methods/wedge.py`](powerplant/inlet_methods/wedge.py) | L0 | Supersonic spike/wedge inlet total pressure recovery |
| **Powerplant** | `MultiConeInletPerformanceAnalysis` | [`powerplant/inlet_methods/wedge.py`](powerplant/inlet_methods/wedge.py) | L0 | Multi-cone supersonic inlet compression |
| **Powerplant** | Taylor-Maccoll Solver | [`powerplant/inlet_methods/taylor_maccoll.py`](powerplant/inlet_methods/taylor_maccoll.py) | L0 | Conical shock ODE integration |
| **Powerplant** | `RamjetCycleAnalysis` | [`powerplant/cycle_methods/mattingly.py`](powerplant/cycle_methods/mattingly.py) | L2 | 1-D thermodynamic station ramjet cycle |
| **Powerplant** | `GrzywkaCombustorNozzleAnalysis` | [`powerplant/cycle_methods/grzywka.py`](powerplant/cycle_methods/grzywka.py) | L2 | 1-D ramjet combustor and nozzle expansion |
| **Powerplant** | Heiser & Pratt Cycle | [`powerplant/cycle_methods/heiser_pratt.py`](powerplant/cycle_methods/heiser_pratt.py) | L2 | Stream-thrust ramjet cycle routines |
| **Stability & Control** | `BarrowmanStabilityAnalysis` | [`stability_control/methods/barrowman/barrowman_stability.py`](stability_control/methods/barrowman/barrowman_stability.py) | L0 | Slender-body rocket static margin and CP |
| **Stability & Control** | `BarrowmanExtendedAnalysis` | [`stability_control/methods/barrowman/barrowman_extended.py`](stability_control/methods/barrowman/barrowman_extended.py) | L0 | Extended Barrowman with transonic corrections |
| **Stability & Control** | DATCOM Runner | [`stability_control/methods/datcom/datcom_class_sweep.py`](stability_control/methods/datcom/datcom_class_sweep.py) | L1 | USAF Digital DATCOM deck generator and wrapper |
| **Stability & Control** | Ackeret Fin Check | [`stability_control/methods/ackeret/ackeret_fin_check.py`](stability_control/methods/ackeret/ackeret_fin_check.py) | L0 | Supersonic fin lift-curve slope calculation |
| **Wind Tunnel** | `XFOILAnalysis` | [`wind_tunnel/methods/xfoil/xfoil_runner.py`](wind_tunnel/methods/xfoil/xfoil_runner.py) | L0 / L1 | Airfoil polar analysis with Ackeret supersonic fallback |
| **Wind Tunnel** | `AVLFinAnalysis` | [`wind_tunnel/methods/avl/avl_builder.py`](wind_tunnel/methods/avl/avl_builder.py) | L1 | Subsonic fin vortex lattice analysis (AVL) |
| **Wind Tunnel** | `AVLAnalysis` | [`wind_tunnel/methods/avl/avl_wrapper.py`](wind_tunnel/methods/avl/avl_wrapper.py) | L1 | Subsonic wing vortex lattice analysis (AVL) |
| **Wind Tunnel** | `SU2ConfigGeneration` | [`wind_tunnel/methods/su2/su2_config_template.py`](wind_tunnel/methods/su2/su2_config_template.py) | L2 / L3 | SU2 CFD configuration template generator |

## Rules for Repair

* **Kill untyped dictionaries; use typed containers**:
  * Do not use untyped dictionaries for internal state or multi-variable returns. Use typed, frozen dataclasses (e.g. `TrajectorySamples`, `TrajectoryMetrics`).
  * Remove dictionary emulation methods (`to_dict`, `from_dict`, `__getitem__`, `get`, `__contains__`) and "backwards compatibility" shims. The framework does not need them; `FlightLogger` / `YaadoJSONEncoder` serializes dataclasses natively via `asdict()`.
  * Do not churn metadata dictionaries in loops. Sweeps and ODE routines should only extract and return the raw numbers or dataclasses needed, avoiding repeated 40-key documentation dict allocations.
  * Strip out filler comments, self-evident docstrings, and essays in comments.

* **Single source of truth & centralized constants**:
  * Import universal physics constants (`G0`, `R_AIR`, `P0_ISA`, etc.) from `YAADO_Core.Foundation.constants`. Do not define loose duplicates at the top of solver files.
  * Use centralized atmosphere models from `YAADO_Core.Foundation.atmosphere` (`isa_atmosphere` for scalar, `isa_atmosphere_array` for vectorized) rather than ad-hoc ISA calculations.
  * Solver-specific default parameters, tolerances, and thresholds belong as class attributes on the analysis class inheriting `BaseAnalysis`.

* **Component resolving (no hardcoded schemas)**:
  * Solvers must operate on generic registry tuples and union types in `ComponentStore` (e.g. `BOOSTER_COMPONENTS` / `AnyBoosterComponent`, `BODY_COMPONENTS` / `AnyBodyComponent`, `AERO_COMPONENTS` / `AnyAeroComponent`).
  * Never hardcode specific leaf classes (like `SolidMotor` or `Fuselage`) in solver resolution logic or type annotations. Subsystem discovery must use `isinstance(comp, SUBSYSTEM_COMPONENTS)`.
  * Never import vehicle schemas from `Hangar/` into `YAADO_Core/`.

* **Strict data contracts & Mypy compliance**:
  * Remove dual-path typing: never accept `T | Mapping[str, Any]` or write `if isinstance(x, dict): ... else: ...` to accommodate loose mock tests. Fix the tests to supply the typed dataclass/model.
  * Remove redundant runtime type casting (e.g. unnecessary `float(...)` or `int(...)` calls in hot ODE loops). If Mypy complains about types, fix the upstream return signatures (e.g. separating scalar vs. vectorized functions).
  * When external libraries require function attributes (like SciPy's `solve_ivp` event callables `terminal` and `direction`), attach them via `setattr()` to satisfy static checkers cleanly.
  * The module must pass `uv run mypy <file>` with zero errors.

* **Logger integration & plotting rules**:
  * Connect `FlightLogger` (`self.logger` from `BaseAnalysis`). Solvers should save artifacts (results JSON, figures, CSVs) via logger methods (`save_json`, `save_figure`, `save_text`).
  * Plotting routines must be headless-safe: create figures with `plt.subplots()`, return the `Figure` object, and never call `plt.show()` unconditionally. Interactive windows must be strictly opt-in (`show_figures: bool = False`).
  * Plot axes must reflect physical constraints (e.g. speed and dynamic pressure clipped at 0.0, altitude lower-bounded at `ground_altitude_m`).
  * Support diskless runs: respect `enable_logging=False` for zero disk I/O in automated sweeps and unit tests.

* **Single entry-point**:
  * No standalone `argparse` blocks, CLI scripts, or runnable `if __name__ == "__main__":` blocks inside solver modules. All execution goes through the analysis class's `execute()` method or the main YAADO CLI (`Terminal/`).

* **Verification on real TOML configurations**:
  * Make sure the method can actually run by testing it on an actual TOML file from `Hangar/examples/` (or via vehicle factory), not just synthetic unit mocks.
  * Ensure the full test suite passes: `uv run pytest --tb=short`.