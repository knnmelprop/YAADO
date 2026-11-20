# Motor Methods

## BATES Solid Grain (internal ballistics)

* **Module**: [`bates.py`](bates.py)
* **Fidelity**: Level 0 (quasi-steady, analytical)
* **Status**: New. It is not yet connected to `SolidMotor` or to the 3-DOF flight simulation (see #37 and #39).

This module calculates the chamber pressure, thrust and remaining propellant mass of a BATES grain over the burn. A BATES grain is a stack of `N` cylindrical segments with a central core. The outer wall is inhibited, so the propellant burns on the core wall and on both segment ends.

```math
r = a P_c^n, \qquad
A_b(w) = N \left[ \pi (D_i + 2w)(L - 2w) + \frac{\pi}{2}\left(D_o^2 - (D_i + 2w)^2\right) \right]
```

At each burned web `w`, the gas generation equals the nozzle mass flow, which gives the chamber pressure:

```math
\rho_{prop} A_b a P_c^n = \frac{P_c A_t}{c^*}
\quad\Rightarrow\quad
P_c = \left(\frac{a \rho_{prop} c^* A_b}{A_t}\right)^{\frac{1}{1-n}}, \qquad F = C_F P_c A_t
```

The solver steps the web from 0 to `(Do - Di) / 2` and converts it to time with `dt = dw / r`. A segment burns most neutrally when `L = (3 Do + Di) / 2`: the burning area at ignition and at burnout are equal (`neutral_segment_length()`).

### Thrust coefficient

`nozzle_thrust_coefficient(area_ratio, half_angle_rad, gamma, ambient_pressure_ratio)` calculates `C_F` for a conical nozzle. It uses ideal isentropic flow and the cone loss `(1 + cos(alpha)) / 2` on the momentum part. It does not include viscous losses or flow separation. It is called at every step because `pa / Pc` changes during the burn.

### Inputs and outputs

| Item | Type | Meaning |
| :--- | :--- | :--- |
| `BatesGrainConfig` | frozen dataclass | Grain geometry, burn-rate law, propellant, nozzle, ambient pressure (all SI). |
| `solve_bates_burn(config)` | function | Returns a `SolidMotorBurnProfile`. |
| `SolidMotorBurnProfile` | frozen dataclass | Arrays `t`, `web_burned`, `burn_area`, `chamber_pressure`, `thrust`, `propellant_mass`; properties `burn_time`, `total_impulse`, `average_thrust`, `peak_thrust`, `specific_impulse`. |

### Limits

* The ambient pressure is constant over the burn. Tail-off after burnout and ignition transients are not modelled.
* The grain is not eroded, and the burn-rate law is the same for the whole burn.
* The thrust can become negative if `pa / Pc` is large. Check that the chamber pressure is high enough.

### Tests

[`tests/YAADO_Core/modules/powerplant/test_bates_grain.py`](../../../../tests/YAADO_Core/modules/powerplant/test_bates_grain.py)
