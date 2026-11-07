# Heiser & Pratt Ramjet Cycle

* **Method class**: `HeiserPrattCycleAnalysis` in [`heiser_pratt.py`](heiser_pratt.py)
* **Fidelity**: Level 2 (1-D station cycle)
* **Status**: Repaired and verified. The other files in this folder are not repaired.

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

   $$f = \frac{c_{p,h} T_{t4} - c_{p,c} T_{t0}}{\eta_b \, LHV - c_{p,h} T_{t4}}$$

3. The choked throat gives the mass flow:

   $$\dot{m}_{exit} = A_t \, p_{t4} \sqrt{\frac{\gamma_h}{R T_{t4}}} \left(\frac{2}{\gamma_h + 1}\right)^{\frac{\gamma_h + 1}{2(\gamma_h - 1)}}, \quad \dot{m}_{air} = \frac{\dot{m}_{exit}}{1 + f}$$

4. The nozzle area ratio gives the exit Mach number.
5. The exit state gives the net thrust:

   $$F = \dot{m}_{exit} V_e - \dot{m}_{air} V_0 + (p_e - p_0) A_e$$

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
| `inlet_recovery` | `eta_inlet` | $p_{t2} / p_{t0}$ at `design_mach` | 0.874 |
| `combustor_pressure_ratio` | `pi_cc` | $p_{t4} / p_{t2}$ | 0.8924 |
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

* The ideal ramjet matches a hand calculation. With one gas, no losses, and a perfectly expanded nozzle, $M_e = M_0$ and $V_e = V_0 \sqrt{T_{t4} / T_{t0}}$.
* The isentropic relations match tabulated values.
* The differences between the three thrust models match their closed-form terms.
* The `ALVRJ` throat and exit areas match the TOML diameters.

These tests check the equations. No test compares the module with engine test data or CFD.

## Reference

W. H. Heiser and D. T. Pratt, *Hypersonic Airbreathing Propulsion*, AIAA Education Series, 1994. The station numbers follow this style. The thrust calculation uses exit momentum and exit pressure, not the complete stream-thrust method.
