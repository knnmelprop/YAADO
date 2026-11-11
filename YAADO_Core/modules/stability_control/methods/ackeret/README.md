# Ackeret Supersonic Fin Check

* **Method class**: `AckeretFinAnalysis` in [`ackeret_fin_check.py`](ackeret_fin_check.py)
* **Fidelity**: Level 0 (closed-form linearized supersonic theory)
* **Status**: Repaired and verified.

This module is an independent, closed-form check of the fin terms in the [Barrowman build-up](../barrowman/README.md) above Mach 1. It uses two-dimensional supersonic (Ackeret) thin-airfoil theory for every fin set, and it reports its result next to Barrowman's at the same Mach number. It is a cross-check, not a design value.

## Fin Set Model

For a fin set with $N$ fins, exposed span $s$ and panel area $A_p$:

$$C_{N\alpha} = K_{fb} \, \frac{N}{2} \, \frac{4}{\sqrt{M^2 - 1}} \, \frac{A_p}{A_{ref}}, \qquad K_{fb} = 1 + \frac{R}{s + R}$$

* $N/2$ is the number of loaded panels at any roll angle ($\sum \sin^2 \varphi_i = N/2$ for $N \ge 3$).
* The CP is the centroid of the trapezoidal planform, because the supersonic loading is uniform.
* The nose and shoulder use the slender-body terms of the Barrowman build-up.

Without tip loss, this slope is an upper bound on linear theory. Above Mach 1.5, the Barrowman build-up uses the same slope times the Puckett tip-loss factor, and it keeps the subsonic fin CP. The gap between the two results shows how far these two effects move the static margin.

## Settings

| Setting | Unit | Default |
| :--- | :---: | :--- |
| `mach` | - | 2.0 (must be > 1) |
| `cg_from_nose` | m | Vehicle CG |

The vehicle input is the same as for Barrowman. A logged run also saves `method_comparison.png` and `method_comparison.csv`. They compare the tail fin slope and the static margin of both methods from Mach 1.2 to 4 (or to the run Mach, if higher).

## Warnings

The run warns when:

* Mach is below 1.2, where linear supersonic theory is poor.
* A fin set has a subsonic leading edge ($M \cos \Lambda_{LE} < 1$). Two-dimensional Ackeret theory then overpredicts the slope.
* The Ackeret and Barrowman tail-fin CPs differ by more than 1 caliber.
* The vehicle is statically unstable.

## Limits

* No tip loss, so the fin slope is too high for low $\beta \cdot AR$. The warnings flag a subsonic leading edge.
* No fin-fin interference, no body lift and no thickness effects.
