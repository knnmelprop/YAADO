# 3-DOF Point-Mass Boost Trajectory Analysis

* **Method Class**: `PointMass3DOFBoostAnalysis` (inherits `BaseAnalysis`)
* **Orchestration Function**: `run_boost_study()`
* **Fidelity**: Level 0 (Analytical / ODE integration)
* **Status**: Repaired and Verified

This module simulates the 2D vertical-plane trajectory (range $x$, altitude $h$, and velocity components $v_x, v_h$) of a rocket booster stage from launch rail release through motor burnout or full unpowered coast to ground impact.

## Physical & Mathematical Model

### 1. Equations of Motion
Point-mass equations in the vertical launch plane:
$$\frac{dx}{dt} = v_x, \quad \frac{dh}{dt} = v_h$$
$$\frac{dv_x}{dt} = \frac{T_x - D \cdot u_x}{m(t)}, \quad \frac{dv_h}{dt} = \frac{T_h - D \cdot u_h}{m(t)} - g_0$$

where:
* $(u_x, u_h) = (v_x / V, v_h / V)$ is the velocity unit vector.
* $T(t) = \dot{m} \cdot g_0 \cdot I_{sp}(h)$ is the altitude-compensated thrust during motor burn ($t \le t_{burn}$), directed along the fixed launch rail elevation angle $\theta_{launch}$.
* $D = \frac{1}{2} \rho(h) V^2 C_D(M) A_{ref}$ is aerodynamic drag opposing the velocity vector.
* $m(t)$ decreases linearly from `launch_mass` to dry burnout mass over `burn_time`.

### 2. Environment & Atmosphere
Atmospheric conditions ($\rho, p, T, a$) are evaluated via the centralized standard atmosphere in [`YAADO_Core.Foundation.atmosphere`](../../Foundation/atmosphere.py) (`isa_atmosphere` for scalar ODE steps, `isa_atmosphere_array` for vectorized trajectory postprocessing). The model supports launch sites above sea level or in terrain depressions below sea level ($h_{ground} < 0$).

### 3. Aerodynamics Build-Up
Drag coefficient $C_D(M)$ uses a piecewise Mach build-up:
* **Subsonic** ($M < M_{transonic}$): constant body base/skin drag $C_{D,sub}$.
* **Transonic** ($M_{transonic} \le M < M_{supersonic}$): linearly interpolated drag rise to $C_{D,trans}$.
* **Supersonic** ($M \ge M_{supersonic}$): supersonic wave drag $C_{D,sup}$ plus fin wave drag per fin:
  $$C_{D,total} = C_{D,body}(M) + N_{fins} \cdot C_{D,wave/fin}$$

## Assumptions & Limitations

* **Point-mass model**: Rotational degrees of freedom, moments of inertia, and attitude dynamics are neglected.
* **Fixed thrust elevation (Gravity-turn approximation)**: Thrust is aligned with the fixed initial launch rail angle $\theta_{launch}$ without active pitch programming or TVC. The trajectory arcs over naturally under gravity.
* **Zero-lift flight**: Angle of attack is assumed near zero ($\alpha \approx 0$). Aerodynamic lift forces are neglected. Valid for high launch rail angles (e.g. 80°–85°).

## Vehicle Component Resolution

The solver extracts all physical parameters from a declarative `BaseVehicleConfig` via [`ComponentStore`](../../ComponentStore/__init__.py) registries:
* **Booster Motor**: Auto-discovered from `vehicle.propulsion` matching `BOOSTER_COMPONENTS` (e.g. `SolidMotor`). Provides `propellant_mass`, `burn_time`, `isp_sl`, and `isp_vacuum`.
* **Airframe Body**: Auto-discovered from `vehicle.bodies` matching `BODY_COMPONENTS`. Provides `diameter` for reference area $A_{ref} = \frac{\pi}{4} d_{ref}^2$.
* **Aero Surfaces (Fins)**: Auto-discovered from `vehicle.aero_surfaces` matching `AERO_COMPONENTS` (e.g. `Fins`). Provides fin count for wave drag.
* **Mass**: Reads `vehicle.mass_properties.total_mass`.

*Disambiguation*: If the vehicle defines multiple components in a subsystem (e.g., booster motor + sustainer ramjet, or wings + aft fins), pass `motor_name`, `body_name`, or `fins_name` explicitly.

## Simulation Modes

| Mode | `stop_at_burnout` | Description |
| :--- | :---: | :--- |
| **Boost Phase** (default) | `True` | Integrates strictly from ignition to motor burnout ($t = t_{burn}$). Returns burnout velocity, Mach, altitude, range, and max dynamic pressure. |
| **Full Flight** | `False` | Continues integration past burnout through unpowered ballistic coast until apogee and ground impact ($h \le h_{ground}$). Returns apogee altitude/time, total flight range, total duration, and impact speed. |

## Output Data Structure

The analysis returns a standardized `AnalysisResults` container:
* **`results.data`**: SI scalar outputs accessible via dictionary key indexing (`results["burnout_mach"]`):
  * `burnout_time`, `burnout_velocity`, `burnout_mach`, `burnout_altitude`, `range_at_burnout`
  * `q_max` (maximum dynamic pressure in Pa)
  * `apogee_altitude`, `apogee_time`, `apogee_range` (when `stop_at_burnout=False`)
  * `flight_time`, `flight_range`, `impact_velocity` (when `stop_at_burnout=False`)
* **`results.metadata`**: Rich metadata containing:
  * `_boost_samples`: Frozen [`TrajectorySamples`](point_mass_3dof.py) dataclass for the powered boost phase (typed NumPy arrays: `t_s`, `x_m`, `h_m`, `v_ms`, `mach`, `q_pa`).
  * `_samples`: Frozen `TrajectorySamples` dataclass for the complete flight.
  * Model documentation, warnings, ground impact flags.

## Generated Artifacts (Disk Logging)

When `enable_logging=True`, `FlightLogger` writes artifacts to `FlightLogs/PointMass3DOFBoostAnalysis_<timestamp>/`:
* `results.json`: Complete scalar metrics and serialized dense trajectory samples.
* `summary.csv`: Key scalar metrics in CSV format.
* `boost_phase.png`: 2x2 multi-panel plot ($V(t)$, $h(t)$, $M(t)$, $q(t)$) for the boost phase.
* `full_flight.png`: Full boost + coast trajectory to apogee and impact (when `stop_at_burnout=False`).
* `launch_angle_sweep.csv` & `launch_angle_sweep.png`: Burnout Mach, burnout altitude, and apogee sensitivity across launch angles.

## Usage Examples

### 1. High-Level Study Runner (`run_boost_study`)

Runs the baseline trajectory, sensitivity sweep, generates all plots, and saves disk artifacts:

```python
from pathlib import Path
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import run_boost_study

# 1. Load vehicle configuration
config_path = Path("Hangar/examples/ALVRJ/ALVRJ.toml")
vehicle = BaseVehicleConfig.from_toml(config_path)

# 2. Run study (ALVRJ defines both strakes and fins, so fins_name is explicit)
results = run_boost_study(
    vehicle,
    fins_name="aft_control_fins",
    launch_angle_deg=83.0,
    altitude_m=0.0,
    stop_at_burnout=False,
    enable_logging=True,
    show_figures=False,
)

# 3. Access scalar outputs (canonical SI floats)
print(f"Burnout velocity: {results['burnout_velocity']:.1f} m/s (Mach {results['burnout_mach']:.2f})")
print(f"Burnout altitude: {results['burnout_altitude']:.1f} m")
print(f"Max dynamic pressure: {results['q_max']:.0f} Pa")
print(f"Apogee altitude:  {results['apogee_altitude']:.1f} m")
print(f"Total range:      {results['flight_range']:.1f} m")

# 4. Access dense trajectory samples directly
samples = results.metadata["_boost_samples"]
print(f"Recorded {len(samples.t_s)} boost telemetry points.")
```

### 2. Standard Framework Analysis (`PointMass3DOFBoostAnalysis`)

Direct workflow integration via the `BaseAnalysis` interface:

```python
from YAADO_Core.modules.flight_dynamics.methods.point_mass_3dof import PointMass3DOFBoostAnalysis

analysis = PointMass3DOFBoostAnalysis()
analysis.setup(
    vehicle,
    launch_angle_deg=83.0,
    altitude_m=0.0,
    fins_name="aft_control_fins",
    stop_at_burnout=True,
    enable_logging=False,  # Zero disk I/O for fast optimization / sweeps
)
results = analysis.execute()
```