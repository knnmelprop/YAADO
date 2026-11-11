# DATCOM-Class Supersonic Stability

* **Method class**: `DatcomStabilityAnalysis` in [`datcom_class_sweep.py`](datcom_class_sweep.py)
* **Fidelity**: Level 1 (supersonic component build-up)
* **Status**: Repaired and verified.

This module calculates the center of pressure (CP) and the static margin of a slender finned rocket in supersonic flight. It is an in-house build-up in the style of Missile DATCOM, **not** a wrapper around the USAF Digital DATCOM program.

## Component Build-up

All slopes refer to $`A_{ref} = \pi d^2 / 4`$. Positions are from the nose tip.

* **Nose and shoulder**: the slender-body terms of the [Barrowman build-up](../barrowman/README.md). They do not depend on Mach number. The viscous cross-flow term grows with $`\alpha^2`$, so it adds nothing to the slope at $`\alpha = 0`$.
* **Each fin set**: the two exposed panels joined at the root form the exposed wing, with aspect ratio $`AR = 2s/\bar c`$:

```math
C_{N\alpha} = K_{fb} \, \frac{N}{2} \, \frac{4}{\beta} \, \eta \, \frac{A_{panel}}{A_{ref}}, \qquad \eta = \max\left(\tfrac{1}{2},\; 1 - \frac{1}{2 \beta AR}\right), \qquad \beta = \sqrt{M^2 - 1}
```

  * $`\eta`$ is the Puckett tip-loss factor. It is exact for a rectangular wing with $`\beta AR \ge 1`$ and approximate otherwise.
  * The fin CP is the planform centroid: half the MAC at the MAC station.

The fin slope is the same as the supersonic slope of the Barrowman build-up. This method differs in two ways: it uses the supersonic fin CP, and it stays in supersonic flow instead of bridging to subsonic flow.

## Settings

| Setting | Unit | Default |
| :--- | :---: | :--- |
| `mach` | - | 2.0 (must be > 1) |
| `cg_from_nose` | m | Vehicle CG |
| `sm_required` | cal | 10 % of the body length |

The vehicle input is the same as for Barrowman. A logged run saves `cp_vs_mach.png` and `cp_vs_mach.csv`, from Mach 1.2 to 3 (or to the run Mach, if higher). The CSV gives the CP, so you can calculate the static margin for any CG.

## Warnings

The run warns when:

* Mach is below 1.2.
* A fin set has $`\beta AR \lt 1`$, so its tip-loss factor is held at the floor.
* The static margin is below the required value, or negative.

## Limits

* Linear theory: small angles of attack, no body lift, no fin-fin interference.
* Nose slope from slender-body theory, with no supersonic nose correction.
* Fin sets are trapezoidal, with $`K_{fb}`$ from subsonic slender-body theory.
