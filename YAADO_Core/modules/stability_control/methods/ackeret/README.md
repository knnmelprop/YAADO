# Ackeret Supersonic Fin Check

* **Method class**: `AckeretFinAnalysis` in [`ackeret_fin_check.py`](ackeret_fin_check.py)
* **Fidelity**: Level 0 (closed-form linearized supersonic theory)
* **Status**: Repaired and verified.

This module gives a second, independent estimate of the supersonic static margin. It replaces the fin terms of the [Barrowman build-up](../barrowman/README.md) with linearized supersonic (Ackeret) thin-airfoil theory, and it reports both results side by side. Use it to check Barrowman above Mach 1. It is not a design value.

## Fin Set Model

For a fin set with $N$ fins, exposed span $s$, mean chord $\bar c$ and panel area $A_p = s \bar c$:

$$a_{2D} = \frac{4}{\sqrt{M^2 - 1}}, \qquad
C_{N\alpha} = K_{fb} \, \frac{N}{2} \, \frac{a_{2D}}{1 + 2/AR} \, \frac{A_p}{A_{ref}}, \qquad
AR = \frac{s}{\bar c}, \qquad K_{fb} = 1 + \frac{R}{s + R}$$

* $N/2$ is the number of loaded panels at any roll angle ($\sum \sin^2 \varphi_i = N/2$ for $N \ge 3$).
* The CP is the centroid of the trapezoidal planform, because the supersonic loading is uniform.
* The nose and shoulder use the slender-body terms of the Barrowman build-up.

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

* The finite-span factor $1/(1 + 2/AR)$ is the classical low-aspect-ratio downwash correction. It is not a supersonic tip-cone correction, so it is approximate for low-aspect-ratio fins.
* No fin-fin interference, no body lift, and no thickness effects.
