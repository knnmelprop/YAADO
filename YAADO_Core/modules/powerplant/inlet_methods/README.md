# Inlet Methods

## Conical Spike Inlet (Taylor-Maccoll)

* **Method class**: `ConicalInletAnalysis` in [`taylor_maccoll.py`](taylor_maccoll.py)
* **Fidelity**: Level 0 (exact inviscid conical flow plus shock relations)
* **Status**: Repaired and verified. `wedge.py` in this folder is not repaired.

This module calculates the total-pressure recovery $p_{t2}/p_{t0}$ of a single-cone external-compression inlet at one flight Mach number:

1. **Conical shock.** An attached shock on the spike, from the Taylor-Maccoll equation (Anderson, *Modern Compressible Flow*, Ch. 10). The solver scans shock angles from just above the Mach angle, so the first crossing is the weak solution, also for thin cones (#130).
2. **Terminal normal shock.** It sits at the Mach number just behind the conical shock. The flow compresses further toward the cone surface, so this is the conservative end of the conical flow field. The run also reports the cone-surface Mach number.
3. **Subsonic diffuser.** A total-pressure ratio.

If the spike is too blunt for an attached shock at the flight Mach number, a normal (bow) shock at the flight Mach number bounds the recovery, and the run warns that the inlet will spill and may buzz. The result is compared with the MIL-E-5007D reference $1 - 0.075 (M - 1)^{1.35}$.

| Input | Setting | From the TOML | Default |
| :--- | :--- | :--- | :--- |
| Flight Mach | `mach` | `design_mach` | - |
| Spike half-angle [deg] | `cone_half_angle_deg` | `spike_half_angle` | Required |
| Diffuser pressure ratio | `pi_diffuser` | - | 0.97 placeholder, flagged |

A logged run also saves `recovery_vs_mach.png` and `recovery_vs_mach.csv`: the recovery of the same spike from Mach 1.2 to 1.5 times the run Mach, next to the MIL-E-5007D curve. Put the recovery into the ramjet's `inlet_recovery` to use it in the Heiser & Pratt cycle.

The public function `solve_conical_shock(mach, cone_half_angle_rad)` returns the shock angle, the Mach numbers behind the shock and on the cone, and the total-pressure ratio. Other analyses can reuse it, for example for nose-cone pressure.

**Limits:**
* Inviscid flow, with no boundary-layer bleed. The recovery is optimistic.
* The shock is assumed to sit on the cowl lip (no spillage at an attached design point).
* Zero angle of attack.
