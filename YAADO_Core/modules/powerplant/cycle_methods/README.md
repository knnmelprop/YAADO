# Heiser & Pratt Ramjet Cycle

* **Method class**: `HeiserPrattCycleAnalysis` in [`heiser_pratt.py`](heiser_pratt.py)
* **Fidelity**: Level 2 (1-D station cycle)
* **Status**: Repaired and verified, like the [Mattingly parametric cycle](#mattingly-parametric-cycle) and the [Grzywka nozzle sizing](#grzywka-combustor-and-nozzle-sizing) below.

This module calculates the thrust of a ramjet at one flight condition. It uses a 1-D station model with one gas in the inlet and a different gas after the combustor. The nozzle has a finite area ratio, so the exit pressure can differ from the ambient pressure.

## Station Model

```mermaid
flowchart LR
    S0["0: freestream<br/>cold gas"] -->|"pt2 = eta_inlet * pt0"| S2["2: diffuser exit<br/>Tt2 = Tt0"]
    S2 -->|"pt4 = pi_cc * pt2<br/>heat addition to Tt4"| S4["4: combustor exit<br/>hot gas"]
    S4 -->|"pt_e = pi_nozzle * pt4<br/>choked throat"| Se["e: nozzle exit"]
```

The model calculates each result in this sequence:

1. The ISA model gives the freestream state at the flight altitude.
2. The burner energy balance gives the fuel-air ratio:

   ```math
   f = \frac{c_{p,h} T_{t4} - c_{p,c} T_{t0}}{\eta_b \, LHV - c_{p,h} T_{t4}}
   ```

3. The choked throat gives the mass flow:

   ```math
   \dot{m}_{exit} = A_t \, p_{t4} \sqrt{\frac{\gamma_h}{R T_{t4}}} \left(\frac{2}{\gamma_h + 1}\right)^{\frac{\gamma_h + 1}{2(\gamma_h - 1)}}, \quad \dot{m}_{air} = \frac{\dot{m}_{exit}}{1 + f}
   ```

4. The nozzle area ratio gives the exit Mach number.
5. The exit state gives the net thrust:

   ```math
   F = \dot{m}_{exit} V_e - \dot{m}_{air} V_0 + (p_e - p_0) A_e
   ```

## Thrust Models

The analysis always reports three thrust values at the same mass flow. Compare them to see the thrust that each loss removes.

| Result | Combustor loss | Nozzle loss | Use |
| :--- | :---: | :---: | :--- |
| `thrust_ideal` | No | No | Upper limit |
| `thrust_cc_loss` | Yes | No | Effect of the combustor loss |
| `thrust_real` | Yes | Yes | Nominal value |

## Vehicle Input

The analysis finds the ramjet with `RAMJET_COMPONENTS`. A vehicle without a ramjet gets an error. If a vehicle has more than one ramjet, pass `engine_name` to the analysis class. The Flight Deck and `yaado -b` accept one ramjet only.

The analysis reads these values from the ramjet:

| TOML field | Setting | Unit | If you do not set it |
| :--- | :--- | :---: | :--- |
| `design_mach` | `mach` | - | Required field |
| `combustor_temp` | `tt4` | K | Required field |
| `nozzle_area_ratio` | None | - | Required field |
| `nozzle_throat_diameter` | `mdot_air` (air flow in kg/s) | m | You must give one of the two |
| `fuel_type` | `gamma_hot`, `fuel_lhv` | -, J/kg | Kerosene values. Other fuels must set both. |

A setting replaces the TOML value for one run. The flight altitude is a setting only (`altitude_m`, default 10,000 m).

## Losses

Losses have a large effect on the result. Give measured or calculated values for your engine.

| TOML field | Setting | Definition | Placeholder |
| :--- | :--- | :--- | :---: |
| `inlet_recovery` | `eta_inlet` | $`p_{t2} / p_{t0}`$ at `design_mach` | 0.874 |
| `combustor_pressure_ratio` | `pi_cc` | $`p_{t4} / p_{t2}`$ | 0.8924 |
| `nozzle_pressure_ratio` | `pi_nozzle` | Nozzle total-pressure ratio | 0.97 |
| `combustion_efficiency` | `eta_b` | Fraction of the fuel heating value released | 0.95 |

The analysis uses the first available value in this order:

1. The setting from the Flight Deck form, `--set`, or Python.
2. The field on the ramjet in the TOML file.
3. The placeholder.

Put the losses on the engine in the vehicle TOML. These numbers show the format only:

```toml
[propulsion.sustainer]
type = "ramjet_engine"
design_mach = 2.6
combustor_temp = 2150.0
nozzle_area_ratio = 2.25
nozzle_throat_diameter = 0.25
inlet_recovery = 0.85
combustor_pressure_ratio = 0.92
nozzle_pressure_ratio = 0.97
combustion_efficiency = 0.93
```

WARNING: Do not use a result as a design value if it shows placeholder losses. The placeholders do not come from your engine, so the thrust can be incorrect.

The analysis lists each placeholder in `results.assumed_losses` and in the execution log. The Flight Deck and `yaado -b` also show a warning. The `ALVRJ` example has no loss data, so all four of its losses are placeholders.

## Usage

Use the Flight Deck:

1. Run `uv run yaado`.
2. Load a vehicle with a ramjet in the Hangar.
3. Press `f` to open the Flight Deck.
4. Select **Heiser & Pratt Ramjet Cycle**.
5. Change the parameters. A blank input uses the value from the vehicle.
6. Press `r` to run the solver.

Use the bare CLI:

```bash
uv run yaado -b --vehicle Hangar/examples/ALVRJ/ALVRJ.toml --solver heiser_pratt_cycle \
    --set altitude_m=12000 --set eta_inlet=0.8
```

Use Python:

```python
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.powerplant.cycle_methods.heiser_pratt import HeiserPrattCycleAnalysis

vehicle = BaseVehicleConfig.from_toml("Hangar/examples/ALVRJ/ALVRJ.toml")
analysis = HeiserPrattCycleAnalysis()
analysis.setup(vehicle, altitude_m=12000.0, enable_logging=False)
results = analysis.execute()
print(results.thrust_real, results.assumed_losses)
```

## Results

`HeiserPrattResults` is a frozen dataclass with SI values. These are the main fields:

| Field | Unit | Meaning |
| :--- | :---: | :--- |
| `thrust_real` | N | Net thrust with all losses |
| `specific_impulse` | s | Net thrust per unit fuel weight flow |
| `mdot_air` | kg/s | Air mass flow |
| `fuel_air_ratio` | - | Fuel flow per unit air flow |
| `capture_area` | m² | Freestream tube area that supplies `mdot_air` |
| `mach_exit`, `v_exit` | -, m/s | Nozzle exit Mach number and velocity |
| `p_exit_over_p0` | - | Exit pressure divided by ambient pressure |
| `a_throat`, `a_exit` | m² | Nozzle throat and exit areas |
| `assumed_losses` | - | Loss fields that use a placeholder |

## Run Artifacts

The Flight Deck and `yaado -b` write these files to `FlightLogs/<vehicle>/heiser_pratt_cycle_<timestamp>/`:

| File | Content |
| :--- | :--- |
| `results.json`, `summary.csv` | All results and their units |
| `execution.log` | Inputs, results, and placeholder warnings |
| `figures/cycle_stations.png` | Total temperature and total pressure at each station, and the three thrust models |
| `figures/mach_sweep.png` | Thrust, specific impulse, exit pressure ratio, and capture area against Mach number |
| `artifacts/mach_sweep.csv` | The data of the Mach sweep |

The `--no-sweep` option removes the two files of the Mach sweep.

The Mach sweep keeps the nozzle throat and the losses of the run constant. It shows a trend, not an engine map.

CAUTION: Do not use the sweep where the required capture area is above the run capture area. A real inlet sized for the run cannot supply that air. Thrust in that range can be too high.

## Limits

The model has these limits:

* **Gas properties**: Each gas has a constant ratio of specific heats. The hot gas uses the gas constant of air.
* **Inlet**: The model has no inlet geometry. It assumes that the inlet supplies the flow that the throat sets. Compare `capture_area` with your inlet.
* **Losses**: Each loss is one constant number. The analysis does not change `inlet_recovery` with Mach number.
* **Nozzle**: The throat always chokes, and the flow fills the nozzle. The model does not include flow separation when the exit pressure is low.
* **Combustor**: The model does not include thermal choking or a stoichiometric limit on the fuel-air ratio.
* **Installed thrust**: The result excludes external drag, spillage drag, and bleed drag.

## Verification

The unit tests are in [`test_heiser_pratt.py`](../../../../tests/YAADO_Core/modules/powerplant/test_heiser_pratt.py). They do these checks:

* The ideal ramjet matches a hand calculation. With one gas, no losses, and a perfectly expanded nozzle, $`M_e = M_0`$ and $`V_e = V_0 \sqrt{T_{t4} / T_{t0}}`$.
* The isentropic relations match tabulated values.
* The differences between the three thrust models match their closed-form terms.
* The `ALVRJ` throat and exit areas match the TOML diameters.

These tests check the equations. No test compares the module with engine test data or CFD.

## Reference

W. H. Heiser and D. T. Pratt, *Hypersonic Airbreathing Propulsion*, AIAA Education Series, 1994. The station numbers follow this style. The thrust calculation uses exit momentum and exit pressure, not the complete stream-thrust method.

## Mattingly Parametric Cycle

* **Method class**: `MattinglyCycleAnalysis` in [`mattingly.py`](mattingly.py)
* **Fidelity**: Level 2 (1-D parametric cycle)

This analysis calculates a real ramjet cycle per unit air mass flow, after Mattingly, *Elements of Propulsion: Gas Turbines and Rockets*, 2nd ed., AIAA, 2006, Sec. 7.3 and 7.6. Engine size does not enter. Use it to choose the flight Mach number and the combustor temperature before you size the engine with Heiser & Pratt.

Stations are 0 (freestream), 2 (diffuser exit), 4 (combustor exit) and 9 (nozzle exit). The air uses $`\gamma_c`$ and the products $`\gamma_t`$, with the gas constant of air:

```math
\tau_r = 1 + \tfrac{\gamma_c - 1}{2} M_0^2, \qquad \tau_\lambda = \frac{c_{p,t} T_{t4}}{c_{p,c} T_0}, \qquad f = \frac{\tau_\lambda - \tau_r}{\eta_b h / (c_{p,c} T_0) - \tau_\lambda}
```

```math
\frac{P_{t9}}{P_9} = \frac{P_0}{P_9} \pi_r \pi_d \pi_b \pi_n, \qquad \pi_d = \pi_{d,max} \, \eta_r(M_0)
```

```math
\frac{F}{\dot m_0} = a_0 \left[(1 + f)\frac{V_9}{a_0} - M_0 + (1 + f)\frac{T_9 / T_0}{V_9 / a_0}\,\frac{1 - P_0/P_9}{\gamma_c}\right]
```

$`\eta_r`$ is the MIL-E-5007D ram recovery: $`1 - 0.075 (M_0 - 1)^{1.35}`$ up to Mach 5 and $`800 / (M_0^4 + 935)`$ above. The analysis also reports TSFC, specific impulse, and the thermal, propulsive and overall efficiencies.

### Inputs

| TOML field | Setting | If you do not set it |
| :--- | :--- | :--- |
| `design_mach` | `mach` | Required field |
| `combustor_temp` | `tt4` | Required field |
| `inlet_recovery` | `pi_d_max` | `pi_d_max = inlet_recovery / eta_r(design_mach)`, so the recovery at the design Mach is the TOML value. Placeholder 0.95. |
| `combustor_pressure_ratio` | `pi_b` | Placeholder 0.8924 |
| `nozzle_pressure_ratio` | `pi_n` | Placeholder 0.97 |
| `combustion_efficiency` | `eta_b` | Placeholder 0.95 |
| `fuel_type` | `gamma_hot`, `fuel_lhv` | Kerosene values. Other fuels must set both. |

The flight altitude (`altitude_m`, default 10,000 m) and the exit pressure ratio (`p0_over_p9`, default 1: perfectly expanded) are settings only. The run lists each placeholder, as Heiser & Pratt does.

A combustor temperature at or below the flight total temperature, or a cycle without net thrust, is an error with a clear message.

### Run Artifacts

A logged run also saves `figures/cycle_vs_mach.png` and `artifacts/cycle_vs_mach.csv`: specific thrust, TSFC, fuel-air ratio and the efficiencies from Mach 1.2 to 5 (or to 1.25 times the run Mach, if higher), at the run's Tt4, altitude and losses. Mach numbers without heat addition or net thrust are left out.

### Verification

The tests in [`test_mattingly_cycle.py`](../../../../tests/YAADO_Core/modules/powerplant/test_mattingly_cycle.py) check:

* the isentropic relations against NACA 1135;
* the ideal ramjet against a hand calculation;
* that the lossless one-gas cycle gives $`V_9 = V_0 \sqrt{\tau_\lambda / \tau_r}`$ with the $`(1 + f)`$ term;
* the two-gas energy balance;
* that every loss lowers the specific thrust;
* that the ALVRJ fuel-air ratio matches Heiser & Pratt.

## Grzywka Combustor and Nozzle Sizing

* **Method class**: `GrzywkaNozzleAnalysis` in [`grzywka.py`](grzywka.py)
* **Fidelity**: Level 2 (1-D station model)

Heiser & Pratt analyzes a nozzle that you already have. This analysis sizes one: it finds the choked throat that passes the flow, and the exit that expands it to ambient pressure at one flight condition. The stations follow Grzywka (*Analiza numeryczna komory spalania i dyszy silnika strumieniowego*, Politechnika Warszawska, 2022):

| Station | Plane | Relation |
| :---: | :--- | :--- |
| 1 | Combustor inlet | $`p_{t1} = \eta_{inlet} \, p_{t0}`$, $`T_{t1} = T_{t0}`$ |
| 2 | Combustor exit | $`p_{t2} = \pi_{cc} \, p_{t1}`$, $`f = \dfrac{c_{p,t} T_{t4} - c_{p,c} T_{t1}}{\eta_b h - c_{p,t} T_{t4}}`$ |
| 21 | Throat, choked | $`A_{21} = \dot m_{exit} / (\text{choked mass flux at } p_{t2}, T_{t4})`$ |
| 3 | Exit, $`p_3 = p_0`$ | $`T_3 = T_{t4} (p_0/p_{tn})^{(\gamma_t - 1)/\gamma_t}`$, $`V_3 = \sqrt{2 c_{p,t} (T_{t4} - T_3)}`$, $`A_3 = \dot m_{exit} / (\rho_3 V_3)`$ |

The thrust $`F = \dot m_{exit} V_3 - \dot m_{air} V_0`$ has three levels. Each uses a different nozzle total pressure $`p_{tn}`$:
* **Ideal:** $`p_{t1}`$.
* **Combustor loss:** $`p_{t2}`$.
* **Real:** $`\pi_{nozzle} \, p_{t2}`$. The exit size and the specific impulse refer to this level.

### Air Flow

The captured air flow comes from one source:
1. **`capture_area`:** the freestream tube area, with full capture: $`\dot m_{air} = \rho_0 V_0 A_c`$.
2. **`mdot_air`:** the air flow itself.
3. **Neither:** the flow that the ramjet's `nozzle_throat_diameter` passes when choked, as in Heiser & Pratt. The sized throat is then the TOML throat. If the sized area ratio differs from the TOML `nozzle_area_ratio` by more than 10 %, the run warns that the TOML nozzle under- or overexpands the flow.

The losses, Mach number, combustor temperature and fuel come from the ramjet, with the same fallbacks and placeholder warnings as Heiser & Pratt.

### Errors

These conditions stop the run with a clear message:
* The combustor exit is at or below the flight total temperature.
* The real nozzle total pressure is below the critical ratio $`((\gamma_t + 1)/2)^{\gamma_t/(\gamma_t - 1)}`$, so the throat cannot choke.
* The cycle has no net thrust.

### Run Artifacts

A logged run saves `figures/nozzle_vs_mach.png` and `artifacts/nozzle_vs_mach.csv`, which cover Mach 1.5 to 4 at the run's capture area and losses. The capture area stays fixed, as for a real inlet. They show:
* real thrust and specific impulse;
* the throat and exit diameters that the flow needs;
* the area ratio for full expansion.

The figure shows how much a fixed nozzle is off its ideal size across the speed range.

### Verification

The tests in [`test_grzywka_cycle.py`](../../../../tests/YAADO_Core/modules/powerplant/test_grzywka_cycle.py) check:
* the fully expanded exit and the energy balance by hand;
* that the throat passes the flow when choked, and that the exit satisfies continuity at $`p_0`$;
* the order of the three thrust levels;
* that on the ALVRJ throat, the air flow and fuel-air ratio match Heiser & Pratt, and the fully expanded nozzle gives at least Heiser & Pratt's thrust.
