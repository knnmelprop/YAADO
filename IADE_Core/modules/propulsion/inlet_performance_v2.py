# MELprop-IADE | analyses.propulsion.inlet_performance_v2 | v0.1.0
"""Taylor-Maccoll conical-inlet performance, superseding the wedge model.

Stage 3 (inlet half) of the 2026-07-11 RamP rerun (research finding
Section 3). This SUPERSEDES -- does not overwrite -- the earlier
:mod:`analyses.propulsion.inlet_performance`, which approximated the
axisymmetric conical shock with a 2-D wedge theta-beta-Mach relation. That
approximation is qualitatively wrong for the as-drawn 42 deg spike: a 2-D
wedge detaches at ~29.8 deg at Mach 2.5, so the wedge model would predict a
DETACHED shock, whereas the true axisymmetric **Taylor-Maccoll** conical
solution stays attached up to ~46 deg at Mach 2.5. Getting this right is the
whole point of redoing the inlet.

Geometry (drawing_dimensions_raw.yaml): external cone half-angle 42 deg,
internal 60 deg, centerbody 85x62 mm. The physical interpretation of the
drawing dimensions is NOT yet settled (see that file's notes), so this module
evaluates BOTH plausible readings of the "42 deg" callout:

    * 42 deg as the cone HALF-angle (as literally dimensioned), and
    * 21 deg half-angle (i.e. 42 deg as the INCLUDED angle),

and reports recovery for each against the MIL-E-5007D reference GOAL
``pt2/pt0 = 1 - 0.075 (M-1)^1.35`` (~0.866 at Mach 2.5) -- a reference goal,
not a hard pass/fail limit.

Method: full Taylor-Maccoll conical-flow integration for the external cone
(oblique conical shock -> isentropic compression to the cone surface),
followed by a terminal normal shock to subsonic and a subsonic-diffuser loss.
The internal 60 deg surface is treated as the cowl/subsonic-diffuser contour
(after the strong external cone the flow is only weakly supersonic, so a
second attached 60 deg compression cone is not physical) -- its detailed
internal-contraction loss needs the duct area schedule, which the drawing
does not give: flagged PROVISIONAL.

Explicit failure-mode reporting (research finding Section 3): shock-on-lip,
subcritical/buzz risk (shock detachment at off-design low Mach), and the
absence of boundary-layer bleed as an unmodeled loss.

References: Anderson, *Modern Compressible Flow*, 3rd ed. (Taylor-Maccoll,
Ch. 10; oblique/normal shocks, Ch. 3-4); MIL-E-5007D total-pressure-recovery
standard; Ferri & Nucci (buzz criterion, qualitative here).
"""

from __future__ import annotations

import csv
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from IADE_Core.modules.propulsion.cycle_v2.hp_stream_thrust_cycle import GAMMA_COLD  # noqa: E402

_HERE = Path(__file__).resolve().parent
CSV_PATH = _HERE / "inlet_performance_v2.csv"

#: MIL-E-5007D reference-recovery coefficients (M > 1).
MIL_E_5007_COEFF: float = 0.075
MIL_E_5007_EXP: float = 1.35

#: As-drawn external cone half-angle [deg] and its included-angle reading.
CONE_HALF_ANGLE_DEG: float = 42.0
CONE_HALF_ANGLE_ALT_DEG: float = 21.0  # 42 deg read as the included angle

#: Design and off-design flight Mach numbers.
DESIGN_MACH: float = 2.5
OFF_DESIGN_MACH: tuple[float, ...] = (2.0, 3.0)

#: PROVISIONAL subsonic-diffuser total-pressure ratio applied after the
#: terminal normal shock. source: typical short annular diffuser ~0.97;
#: replace when the internal duct area schedule (60 deg cowl) is modeled.
PI_SUBSONIC_DIFFUSER: float = 0.97


def mil_e_5007d_recovery(mach: float) -> float:
    """MIL-E-5007D reference total-pressure recovery for M > 1.

    Args:
        mach: Freestream Mach number.

    Returns:
        Reference recovery pt2/pt0 [-] (1.0 for M <= 1).
    """
    if mach <= 1.0:
        return 1.0
    return 1.0 - MIL_E_5007_COEFF * (mach - 1.0) ** MIL_E_5007_EXP


def _theta_from_beta(mach1: float, beta_rad: float, gamma: float) -> float:
    """theta-beta-Mach flow deflection for an oblique shock."""
    s = math.sin(beta_rad)
    num = mach1 * mach1 * s * s - 1.0
    den = mach1 * mach1 * (gamma + math.cos(2.0 * beta_rad)) + 2.0
    return math.atan(2.0 / math.tan(beta_rad) * num / den)


def oblique_shock(mach1: float, beta_rad: float, gamma: float) -> tuple[float, float, float]:
    """Oblique-shock deflection, downstream Mach, and total-pressure ratio.

    Args:
        mach1: Upstream Mach.
        beta_rad: Shock angle [rad].
        gamma: Ratio of specific heats.

    Returns:
        Tuple ``(delta_rad, mach2, pt2_over_pt1)``.
    """
    m1n = mach1 * math.sin(beta_rad)
    delta = _theta_from_beta(mach1, beta_rad, gamma)
    m2n = math.sqrt((1.0 + 0.5 * (gamma - 1.0) * m1n * m1n) / (gamma * m1n * m1n - 0.5 * (gamma - 1.0)))
    mach2 = m2n / math.sin(beta_rad - delta)
    ptr = (
        ((gamma + 1.0) * m1n * m1n / ((gamma - 1.0) * m1n * m1n + 2.0)) ** (gamma / (gamma - 1.0))
        * ((gamma + 1.0) / (2.0 * gamma * m1n * m1n - (gamma - 1.0))) ** (1.0 / (gamma - 1.0))
    )
    return delta, mach2, ptr


def normal_shock(mach: float, gamma: float) -> tuple[float, float]:
    """Normal-shock downstream Mach and total-pressure ratio.

    Args:
        mach: Upstream (supersonic) Mach.
        gamma: Ratio of specific heats.

    Returns:
        Tuple ``(mach2, pt2_over_pt1)``. Returns ``(mach, 1.0)`` if M <= 1.
    """
    if mach <= 1.0:
        return mach, 1.0
    m2 = math.sqrt((1.0 + 0.5 * (gamma - 1.0) * mach * mach) / (gamma * mach * mach - 0.5 * (gamma - 1.0)))
    ptr = (
        ((gamma + 1.0) * mach * mach / ((gamma - 1.0) * mach * mach + 2.0)) ** (gamma / (gamma - 1.0))
        * ((gamma + 1.0) / (2.0 * gamma * mach * mach - (gamma - 1.0))) ** (1.0 / (gamma - 1.0))
    )
    return m2, ptr


def _nd_speed_from_mach(mach: float, gamma: float) -> float:
    """Non-dimensional speed V/Vmax for a given Mach."""
    return 1.0 / math.sqrt(1.0 + 2.0 / ((gamma - 1.0) * mach * mach))


def _tm_rhs(theta: float, y: list[float], gamma: float) -> list[float]:
    """Taylor-Maccoll ODE right-hand side (nondim velocities)."""
    v_r, v_t = y
    a2 = 0.5 * (gamma - 1.0) * (1.0 - v_r * v_r - v_t * v_t)
    dv_r = v_t
    dv_t = (v_r * v_t * v_t - a2 * (2.0 * v_r + v_t / math.tan(theta))) / (a2 - v_t * v_t)
    return [dv_r, dv_t]


def cone_angle_for_beta(mach1: float, beta_rad: float, gamma: float) -> tuple[float | None, float]:
    """Cone half-angle produced by a given conical-shock angle (Taylor-Maccoll).

    Integrates the Taylor-Maccoll equation from the shock inward until the
    normal velocity component vanishes (flow parallel to the cone surface).

    Args:
        mach1: Freestream Mach.
        beta_rad: Conical-shock angle [rad].
        gamma: Ratio of specific heats.

    Returns:
        Tuple ``(cone_half_angle_rad or None, pt2_over_pt1)``. ``None`` if the
        integration finds no tangency (no cone for this shock angle).
    """
    delta, mach2, ptr = oblique_shock(mach1, beta_rad, gamma)
    w2 = _nd_speed_from_mach(mach2, gamma)
    v_r0 = w2 * math.cos(beta_rad - delta)
    v_t0 = -w2 * math.sin(beta_rad - delta)

    def _event(theta: float, y: list[float], gamma: float = gamma) -> float:
        return y[1]

    _event.terminal = True  # type: ignore[attr-defined]
    _event.direction = 1  # type: ignore[attr-defined]  # V_theta rises to 0
    sol = solve_ivp(
        _tm_rhs, [beta_rad, 1e-4], [v_r0, v_t0], args=(gamma,),
        events=_event, max_step=0.002, rtol=1e-8, atol=1e-11,
    )
    if sol.t_events[0].size > 0:
        return float(sol.t_events[0][0]), ptr
    return None, ptr


def max_attached_cone_half_angle(mach1: float, gamma: float, n_scan: int = 60) -> float:
    """Maximum cone half-angle with an attached conical shock at ``mach1``.

    Args:
        mach1: Freestream Mach.
        gamma: Ratio of specific heats.
        n_scan: Scan resolution over the shock-angle range.

    Returns:
        Maximum attached cone half-angle [rad].
    """
    mach_angle = math.asin(1.0 / mach1)
    best = 0.0
    for beta in np.linspace(mach_angle + 0.02, math.radians(89.0), n_scan):
        tc, _ = cone_angle_for_beta(mach1, float(beta), gamma)
        if tc is not None and tc > best:
            best = tc
    return best


def solve_conical_shock(
    mach1: float, cone_half_angle_rad: float, gamma: float, n_scan: int = 60
) -> tuple[float, float, float] | None:
    """Solve for the attached conical-shock angle at a given cone half-angle.

    Args:
        mach1: Freestream Mach.
        cone_half_angle_rad: Target cone half-angle [rad].
        gamma: Ratio of specific heats.
        n_scan: Bracket-scan resolution.

    Returns:
        ``(beta_rad, mach_behind_shock, pt2_over_pt1)`` for the weak
        (attached) solution, or ``None`` if the shock is detached.
    """
    mach_angle = math.asin(1.0 / mach1)
    betas = np.linspace(mach_angle + 0.02, math.radians(89.0), n_scan)
    prev_tc: float | None = None
    prev_beta: float | None = None
    for beta in betas:
        tc, _ = cone_angle_for_beta(mach1, float(beta), gamma)
        if tc is None:
            continue
        if prev_tc is not None and (prev_tc - cone_half_angle_rad) * (tc - cone_half_angle_rad) <= 0.0:
            beta_sol = brentq(
                lambda b: cone_angle_for_beta(mach1, b, gamma)[0] - cone_half_angle_rad,
                prev_beta, float(beta), xtol=1e-7,
            )
            delta, mach2, ptr = oblique_shock(mach1, beta_sol, gamma)
            return beta_sol, mach2, ptr
        prev_tc, prev_beta = tc, float(beta)
    return None


@dataclass
class InletResult:
    """Conical-inlet recovery result at one flight condition and cone angle."""

    mach0: float
    cone_half_angle_deg: float
    attached: bool
    beta_deg: float | None
    mach_behind_cone: float | None
    pt_conical: float | None
    mach_before_terminal: float | None
    pt_terminal_normal: float | None
    pt_subsonic_diffuser: float
    overall_recovery: float | None
    mil_e_5007d_reference: float
    meets_reference_goal: bool | None
    failure_modes: list[str] = field(default_factory=list)


def evaluate_inlet(
    mach0: float, cone_half_angle_deg: float, gamma: float = GAMMA_COLD
) -> InletResult:
    """Evaluate conical-inlet total-pressure recovery at a flight condition.

    Args:
        mach0: Freestream Mach.
        cone_half_angle_deg: External cone half-angle [deg].
        gamma: Ratio of specific heats (cold air).

    Returns:
        An :class:`InletResult` with the recovery chain and failure-mode flags.
    """
    mil = mil_e_5007d_recovery(mach0)
    failure: list[str] = []
    theta_c = math.radians(cone_half_angle_deg)
    theta_max = max_attached_cone_half_angle(mach0, gamma)

    if theta_c > theta_max:
        # Detached bow shock: no attached conical solution. Bound the recovery
        # with a normal shock at the flight Mach (a strong-shock lower bound).
        _, ptr_normal = normal_shock(mach0, gamma)
        failure.append(
            f"DETACHED_SHOCK: cone half-angle {cone_half_angle_deg:.0f} deg exceeds "
            f"the attached limit {math.degrees(theta_max):.1f} deg at M{mach0:.1f} "
            f"-> bow shock, subcritical/spillage, buzz risk"
        )
        return InletResult(
            mach0=mach0, cone_half_angle_deg=cone_half_angle_deg, attached=False,
            beta_deg=None, mach_behind_cone=None, pt_conical=None,
            mach_before_terminal=None, pt_terminal_normal=ptr_normal,
            pt_subsonic_diffuser=PI_SUBSONIC_DIFFUSER,
            overall_recovery=ptr_normal * PI_SUBSONIC_DIFFUSER,
            mil_e_5007d_reference=mil,
            meets_reference_goal=(ptr_normal * PI_SUBSONIC_DIFFUSER) >= mil,
            failure_modes=failure,
        )

    sol = solve_conical_shock(mach0, theta_c, gamma)
    if sol is None:  # pragma: no cover - guarded by theta_max check above
        failure.append("NO_ATTACHED_SOLUTION")
        return InletResult(
            mach0=mach0, cone_half_angle_deg=cone_half_angle_deg, attached=False,
            beta_deg=None, mach_behind_cone=None, pt_conical=None,
            mach_before_terminal=None, pt_terminal_normal=None,
            pt_subsonic_diffuser=PI_SUBSONIC_DIFFUSER, overall_recovery=None,
            mil_e_5007d_reference=mil, meets_reference_goal=None, failure_modes=failure,
        )

    beta, mach_behind, pt_conical = sol
    # Terminal normal shock from the (still supersonic) post-cone Mach.
    _, pt_normal = normal_shock(mach_behind, gamma)
    overall = pt_conical * pt_normal * PI_SUBSONIC_DIFFUSER

    # Failure-mode / limitation flags (research finding Section 3).
    margin_to_detach = math.degrees(theta_max) - cone_half_angle_deg
    if margin_to_detach < 6.0:
        failure.append(
            f"NEAR_DETACHMENT: only {margin_to_detach:.1f} deg of margin to the "
            f"attached-shock limit at M{mach0:.1f} -> strong near-normal conical "
            f"shock (beta={math.degrees(beta):.1f} deg), high loss, buzz-sensitive"
        )
    if overall < mil:
        failure.append(
            f"BELOW_MIL_E_5007D: recovery {overall:.3f} < reference goal {mil:.3f} "
            f"(single external cone + terminal normal shock cannot stage the "
            f"compression enough; cf. the 4-cone chain 0.874, A9)"
        )
    failure.append(
        "NO_BLEED_MODELED: no boundary-layer bleed included -> recovery is "
        "OPTIMISTIC (real recovery lower)"
    )
    failure.append(
        "SHOCK_ON_LIP_UNVERIFIED: cowl-lip position not in the drawing data "
        "-> shock-on-lip match at design is PROVISIONAL"
    )

    return InletResult(
        mach0=mach0, cone_half_angle_deg=cone_half_angle_deg, attached=True,
        beta_deg=math.degrees(beta), mach_behind_cone=mach_behind, pt_conical=pt_conical,
        mach_before_terminal=mach_behind, pt_terminal_normal=pt_normal,
        pt_subsonic_diffuser=PI_SUBSONIC_DIFFUSER, overall_recovery=overall,
        mil_e_5007d_reference=mil, meets_reference_goal=overall >= mil,
        failure_modes=failure,
    )


def run_matrix() -> list[dict[str, Any]]:
    """Evaluate the design + off-design Mach x cone-interpretation matrix."""
    rows: list[dict[str, Any]] = []
    machs = (DESIGN_MACH,) + OFF_DESIGN_MACH
    for cone in (CONE_HALF_ANGLE_DEG, CONE_HALF_ANGLE_ALT_DEG):
        for mach in machs:
            r = evaluate_inlet(mach, cone)
            rows.append(
                {
                    "mach0": mach,
                    "cone_half_angle_deg": cone,
                    "attached": r.attached,
                    "beta_deg": r.beta_deg,
                    "mach_behind_cone": r.mach_behind_cone,
                    "pt_conical": r.pt_conical,
                    "pt_terminal_normal": r.pt_terminal_normal,
                    "overall_recovery": r.overall_recovery,
                    "mil_e_5007d_reference": r.mil_e_5007d_reference,
                    "meets_reference_goal": r.meets_reference_goal,
                    "failure_modes": " | ".join(r.failure_modes),
                }
            )
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path = CSV_PATH) -> None:
    """Write the recovery matrix to CSV."""
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> list[dict[str, Any]]:
    """Run the matrix, write CSV, and print a short table."""
    rows = run_matrix()
    write_csv(rows)
    print(f"{'M0':>4} {'cone':>5} {'att':>4} {'beta':>6} {'M_be':>6} "
          f"{'pt_con':>7} {'overall':>8} {'MIL':>6} {'goal':>5}")
    for r in rows:
        beta = f"{r['beta_deg']:.1f}" if r['beta_deg'] is not None else "  -  "
        mbe = f"{r['mach_behind_cone']:.3f}" if r['mach_behind_cone'] is not None else "  -  "
        ptc = f"{r['pt_conical']:.4f}" if r['pt_conical'] is not None else "  -   "
        ov = f"{r['overall_recovery']:.4f}" if r['overall_recovery'] is not None else "  -   "
        print(f"{r['mach0']:>4.1f} {r['cone_half_angle_deg']:>5.0f} {str(r['attached']):>4} "
              f"{beta:>6} {mbe:>6} {ptc:>7} {ov:>8} {r['mil_e_5007d_reference']:>6.3f} "
              f"{str(r['meets_reference_goal']):>5}")
    return rows


if __name__ == "__main__":
    main()
