# MELprop-IADE | SU2 stability post-processing | v0.1.0
"""Extract CN/CA/CM, CP location and static margin from an SU2 run.

This turns raw SU2 force output into the single number the stability
cross-check cares about: the static-margin *sign* (stable vs unstable),
in calibers, about a given CG.

It is deliberately solver-output-driven (no fabricated aero). The CG and the
reference length/diameter are inputs — if the CG is unknown, run a sweep and
read off the neutral point where the margin sign flips.

Typical use::

    python postprocess_coeffs.py \\
        --forces run/aoa04/forces_breakdown.dat \\
        --aoa-deg 4.0 --cg-x-m 1.6084 --diameter-m 0.30 --ref-len-m 0.30
"""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ForceCoeffs:
    """Integrated force/moment coefficients from one SU2 run.

    Attributes:
        cl: Total lift coefficient (wind axes).
        cd: Total drag coefficient (wind axes).
        cmz: Total pitching-moment coefficient about REF_ORIGIN_MOMENT.
        aoa_deg: Angle of attack for this run, degrees.
    """

    cl: float
    cd: float
    cmz: float
    aoa_deg: float

    @property
    def cn(self) -> float:
        """Normal-force coefficient (body axes) from CL, CD and AoA."""
        a = math.radians(self.aoa_deg)
        return self.cl * math.cos(a) + self.cd * math.sin(a)

    @property
    def ca(self) -> float:
        """Axial-force coefficient (body axes) from CL, CD and AoA."""
        a = math.radians(self.aoa_deg)
        return self.cd * math.cos(a) - self.cl * math.sin(a)


_FORCES_PATTERNS = {
    "cl": re.compile(r"Total\s+CL:\s*([-\d.eE+]+)"),
    "cd": re.compile(r"Total\s+CD:\s*([-\d.eE+]+)"),
    "cmz": re.compile(r"Total\s+CMz:\s*([-\d.eE+]+)"),
}


def parse_forces_breakdown(path: Path, aoa_deg: float) -> ForceCoeffs:
    """Parse ``forces_breakdown.dat`` (written by WRT_FORCES_BREAKDOWN= YES).

    Args:
        path: Path to the SU2 ``forces_breakdown.dat`` file.
        aoa_deg: Angle of attack used for this run, degrees.

    Returns:
        A populated :class:`ForceCoeffs`.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If CL/CD/CMz cannot be located in the file.
    """
    text = Path(path).read_text()
    vals: dict[str, float] = {}
    for key, pat in _FORCES_PATTERNS.items():
        m = pat.search(text)
        if m is None:
            raise ValueError(f"Could not find '{key}' in {path}")
        vals[key] = float(m.group(1))
    return ForceCoeffs(cl=vals["cl"], cd=vals["cd"], cmz=vals["cmz"], aoa_deg=aoa_deg)


def cp_location_m(coeffs: ForceCoeffs, cg_x_m: float, ref_len_m: float) -> float:
    """Centre-of-pressure X location, metres, from a single run.

    X_cp = X_moment_ref - (CMz / CN) * ref_len. SU2's CMz is nondimensionalised
    by REF_AREA * REF_LENGTH about REF_ORIGIN_MOMENT (== the CG passed here).

    Args:
        coeffs: Force coefficients for one AoA.
        cg_x_m: Moment reference X (the CG), metres.
        ref_len_m: REF_LENGTH used in the SU2 config, metres.

    Returns:
        Centre-of-pressure X location, metres.

    Raises:
        ValueError: If CN is ~0 (CP undefined, e.g. at zero AoA).
    """
    if abs(coeffs.cn) < 1e-9:
        raise ValueError("CN ~ 0: CP undefined at this AoA (use a nonzero AoA).")
    return cg_x_m - (coeffs.cmz / coeffs.cn) * ref_len_m


def static_margin_cal(x_cp_m: float, cg_x_m: float, diameter_m: float) -> float:
    """Static margin in calibers. Positive ⇒ statically stable.

    Args:
        x_cp_m: Centre-of-pressure X, metres.
        cg_x_m: Centre-of-gravity X, metres.
        diameter_m: Reference body diameter (one caliber), metres.

    Returns:
        Static margin in calibers (dimensionless).
    """
    return (x_cp_m - cg_x_m) / diameter_m


def _main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--forces", required=True, type=Path, help="forces_breakdown.dat")
    p.add_argument("--aoa-deg", required=True, type=float)
    p.add_argument("--cg-x-m", required=True, type=float, help="CG / moment ref X")
    p.add_argument("--diameter-m", required=True, type=float, help="one caliber")
    p.add_argument("--ref-len-m", required=True, type=float, help="REF_LENGTH in cfg")
    a = p.parse_args()

    c = parse_forces_breakdown(a.forces, a.aoa_deg)
    x_cp = cp_location_m(c, a.cg_x_m, a.ref_len_m)
    sm = static_margin_cal(x_cp, a.cg_x_m, a.diameter_m)
    verdict = "STABLE" if sm > 0 else "UNSTABLE"
    print(f"AoA={a.aoa_deg:.1f} deg  CL={c.cl:.4f} CD={c.cd:.4f} CMz={c.cmz:.4f}")
    print(f"CN={c.cn:.4f}  CA={c.ca:.4f}")
    print(f"X_cp={x_cp:.4f} m  X_cg={a.cg_x_m:.4f} m")
    print(f"Static margin = {sm:+.3f} cal  -> {verdict}")


if __name__ == "__main__":
    _main()
