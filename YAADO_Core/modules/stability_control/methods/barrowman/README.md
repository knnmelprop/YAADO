# Barrowman Static Stability

* **Method class**: `BarrowmanStabilityAnalysis` in [`barrowman_stability.py`](barrowman_stability.py)
* **Fidelity**: Level 0 (closed-form component build-up)
* **Status**: Repaired and verified. `barrowman_extended.py` in this folder is not repaired.

This module calculates the center of pressure (CP) and the static margin of a slender finned rocket at one Mach number. It adds up the normal-force-curve slope `CN_alpha` and the CP of each component, after Barrowman and Barrowman, *The Theoretical Prediction of the Center of Pressure* (NARAM-8, 1966).

## Component Build-up

All slopes refer to the body cross-section area `A_ref = pi d^2 / 4`. Positions are from the nose tip.

| Component | `CN_alpha` [1/rad] | CP |
| :--- | :--- | :--- |
| Nose | $2 (d_{base}/d)^2$ | $k \, L_{nose}$: cone 2/3, ogive 0.466, hemisphere 1/3 |
| Shoulder (nose base narrower than the body) | $2 \left(1 - (d_{base}/d)^2\right)$ | At the nose base (a step) |
| Each fin set | $K_{fb} \dfrac{4N (s/d)^2}{1 + \sqrt{1 + \left(\dfrac{2 l_F}{C_r + C_t}\right)^2}}$ | $x_{LE} + \dfrac{X_R (C_r + 2C_t)}{3(C_r + C_t)} + \dfrac{1}{6}\left(C_r + C_t - \dfrac{C_r C_t}{C_r + C_t}\right)$ |

* $K_{fb} = 1 + R/(s + R)$ is the body interference on the fins.
* $l_F$ is the length of the fin mid-chord line, and $X_R = s \tan \Lambda_{LE}$ is the axial distance from the root leading edge to the tip leading edge.

The vehicle CP is the slope-weighted mean, and the static margin is $(x_{CP} - x_{CG}) / d$ in calibers. Positive is stable.

### Mach Number

Only the fin slopes change with Mach number:

* Below Mach 0.8: Prandtl-Glauert, $1/\sqrt{1 - M^2}$.
* Above Mach 1.2: linearized supersonic theory, $\left(4/\sqrt{M^2 - 1}\right) / 2\pi$.
* Between the two, a linear bridge.

Barrowman is a subsonic method. Above Mach 0.8, the run warns that the result is an estimate.

## Vehicle Input

| TOML field | Used for | If you do not set it |
| :--- | :--- | :--- |
| `[bodies.*]` `diameter`, `length`, `nose_type`, `nose_length` | Body and nose | Required (`nose_type` defaults to ogive) |
| `[bodies.*]` `nose_diameter` | Shoulder | Same as the body diameter |
| `[aero_surfaces.*]` with `type = "fins"`: `count`, `span`, `sweep`, `chord_root`, `chord_tip` | Each fin set | Required for every fin set |
| `[aero_surfaces.*]` `root_le_from_nose` | Fin set position | Flush with the aft end of the body. Only one fin set may do this. |
| `[mass_properties]` `cg_from_nose` | Static margin | The body's own mass CG, else an error |

Every fin set counts, so canards and mid-body wings described as fins move the CP forward. Lifting surfaces of `type = "wing"` are not part of the build-up; the run lists them. A body with length/diameter below 5 is rejected, because slender-body theory does not apply.

## Settings

| Setting | Unit | Default |
| :--- | :---: | :--- |
| `mach` | - | 0.3 |
| `cg_from_nose` | m | Vehicle CG. Set it to check the burnout CG. |
| `sm_required` | cal | 10 % of the body length, in calibers |

A logged run also saves `cp_vs_mach.png` and `cp_vs_mach.csv`, a sweep from Mach 0 to 2 (or to the run Mach, if higher).

## Limits

* Linear theory: small angles of attack, no body lift, no vortex lift and no fin-fin interference.
* No boat tail and no flare.
* Fin sets are trapezoidal with straight edges.
