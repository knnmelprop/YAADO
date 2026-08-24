"""Supersonic fin polar for the MELprop ramjet rocket (Ackeret fallback).

The MELprop ramjet rocket uses rectangular steel fins with a maximum
thickness of 30 mm over a 176.8 mm chord (``t/c ~ 0.17``, see
``Hangar/generic_vehicle/fusion_extraction_v6.yaml``). At the cruise
design point the fins operate at Mach 1.5-3.5, where a sharp double-wedge
(diamond) section is used to minimise wave drag.

**Why this is not an XFOIL wrapper in practice.** XFOIL is a panel +
integral boundary-layer method valid only for incompressible/weakly
compressible, subsonic-to-transonic flow (roughly Mach < 0.7-0.8). The
fin cruise regime (Mach 1.5-3.5) is *outside XFOIL's domain of validity
by construction* -- running XFOIL there would silently produce garbage,
not merely "unavailable" results. Per project rule #7 (see repo
``CLAUDE.md``: "AVL tylko dla Ma < 0.6 ... powyzej - korelacje
empiryczne"), the analogous rule for a panel/BL method like XFOIL is
applied here: outside its subsonic validity window we replace it with
the physically appropriate closed-form theory, **linearised supersonic
thin-airfoil (Ackeret) theory**, rather than attempting to force XFOIL
to run out of range.

:class:`XFOILAnalysis` therefore:

1. Checks :mod:`YAADO_Core.solver_registry` for a registered ``xfoil`` binary.
   If present *and* the requested Mach were subsonic, it would delegate
   to XFOIL (left as a documented TODO -- no MELprop analysis currently
   asks XFOIL to run in its valid subsonic window, so no subprocess
   driver has been implemented yet; see ``TODO`` below).
2. For the supersonic fin regime targeted by this module (Mach 1.5-3.5),
   XFOIL is *never* invoked (it would be invalid), and the analysis
   always uses the Ackeret analytical fallback, emitting a
   ``warnings.warn`` that documents the fallback and its validity
   limits.

Ackeret linearized supersonic thin-airfoil theory (double-wedge section)
--------------------------------------------------------------------------
For a symmetric double-wedge (diamond) airfoil with maximum thickness at
mid-chord, each half-chord surface is a flat panel inclined at the wedge
half-angle ``tau = atan(t/c)`` (small-angle convention: ``t/c`` is the
tangent of the half-angle measured from the chord line, which is exact
for a symmetric diamond with the ridge at 50% chord). For a thin
symmetric section at angle of attack ``alpha`` in inviscid linearised
supersonic flow (Anderson, *Fundamentals of Aerodynamics*, chapter on
linearized supersonic flow):

    CL = 4 * alpha / sqrt(M^2 - 1)
    CD = 4 * (alpha^2 + tau^2) / sqrt(M^2 - 1)

with ``alpha`` and ``tau`` in radians. The ``alpha^2`` term is
wave drag due to lift, and the ``tau^2`` term is wave drag due to
thickness (form/wave drag of the symmetric double wedge at zero lift).
Both expressions require Ma > 1 (the ``sqrt(M^2 - 1)`` singularity means
the theory blows up approaching Mach 1 and is invalid below it); this
module additionally rejects Ma <= 1.05 as too close to the singularity
to trust the linearisation.

Theory reference:
    Anderson, J. D., *Fundamentals of Aerodynamics*, chapter "Linearized
    Supersonic Flow" (Ackeret's rule for thin-airfoil supersonic lift
    and wave drag). Ames Research Staff, "Equations, Tables, and Charts
    for Compressible Flow", NACA Report 1135 (1953).

TODO:
    * If a future MELprop analysis needs XFOIL in its valid subsonic
      window (e.g. fin section at boost-initiation speeds), implement
      the subprocess driver here: emit an XFOIL command deck for the
      double-wedge coordinates, drive ``xfoil`` via subprocess with a
      batch command file, and parse the polar (CL, CD, CM vs alpha).
      See ``analyses/aero/avl_builder.py`` for the sibling AVL
      subprocess pattern to mirror.
"""

from __future__ import annotations

import json
import math
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if __name__ == "__main__" and __package__ in (None, ""):
    # Allow `python3 analyses/aero/xfoil_runner.py` direct execution by
    # putting the repository root on sys.path (mirrors barrowman_stability.py).
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (backend must be set first)

from YAADO_Core.Foundation.analysis_base import AnalysisResults, BaseAnalysis, FidelityLevel  # noqa: E402
from YAADO_Core.Foundation.solver_registry import DEFAULT_REGISTRY  # noqa: E402

#: Fin section geometry (Fusion Assembly v6 / fusion_extraction_v6.yaml).
FIN_CHORD_M = 0.1768
FIN_THICKNESS_MAX_M = 0.030
FIN_DESIGN_MACH = 2.5

#: t/c derived from the real Fusion 360 geometry above (NOT a placeholder:
#: both chord and max thickness are extracted, verified values).
FIN_THICKNESS_TO_CHORD = FIN_THICKNESS_MAX_M / FIN_CHORD_M  # ~= 0.1697

#: Fallback t/c used only if a vehicle config lacks fin thickness data.
#: SZACOWANY (estimated) -- typical thin supersonic double-wedge fin.
_DEFAULT_THICKNESS_TO_CHORD_ESTIMATE = 0.06

#: Ackeret validity window enforced in :meth:`XFOILAnalysis.setup`.
MIN_MACH = 1.5
MAX_MACH = 3.5
#: Reject Mach numbers at/below this value: sqrt(M^2-1) is singular at
#: M=1 and the linearisation is untrustworthy near/below it.
MIN_MACH_ABSOLUTE = 1.05
MIN_ALPHA_DEG = -10.0
MAX_ALPHA_DEG = 10.0

_RESULTS_JSON_PATH = Path(__file__).with_name("xfoil_runner_results.json")
_POLAR_PNG_PATH = Path(__file__).with_name("xfoil_runner_polar.png")


def ackeret_polar(mach: float, alpha_deg: float, t_c: float) -> tuple[float, float]:
    """Compute CL, CD for a symmetric double-wedge section (Ackeret theory).

    Args:
        mach: Freestream Mach number. Must satisfy ``mach > 1`` (checked
            by the caller; this function does not re-validate the full
            envelope so it can be reused for quick hand checks).
        alpha_deg: Angle of attack in degrees.
        t_c: Thickness-to-chord ratio of the double wedge. The wedge
            half-angle is ``tau = atan(t_c)`` (max thickness at
            mid-chord, symmetric diamond convention).

    Returns:
        Tuple ``(CL, CD)``, dimensionless.

    Raises:
        ValueError: If ``mach <= 1.0`` (Ackeret theory is undefined at
            and below Mach 1).
    """
    if mach <= 1.0:
        raise ValueError(f"Ackeret theory requires Mach > 1, got {mach}")

    alpha_rad = math.radians(alpha_deg)
    tau_rad = math.atan(t_c)
    beta = math.sqrt(mach**2 - 1.0)

    cl = 4.0 * alpha_rad / beta
    cd = 4.0 * (alpha_rad**2 + tau_rad**2) / beta
    return cl, cd


@dataclass
class XfoilCase:
    """Supersonic fin polar run specification.

    Attributes:
        mach_list: Freestream Mach numbers to sweep, each within
            ``[MIN_MACH, MAX_MACH]``.
        alpha_deg_list: Angles of attack [deg] to sweep, each within
            ``[MIN_ALPHA_DEG, MAX_ALPHA_DEG]``.
        thickness_to_chord: Double-wedge ``t/c`` (max thickness at
            mid-chord convention). Defaults to the real Fusion 360 fin
            geometry value.
    """

    mach_list: list[float] = field(default_factory=lambda: [1.5, 2.0, 2.5, 3.0, 3.5])
    alpha_deg_list: list[float] = field(
        default_factory=lambda: [-10.0, -5.0, 0.0, 5.0, 10.0]
    )
    thickness_to_chord: float = FIN_THICKNESS_TO_CHORD


class XFOILAnalysis(BaseAnalysis):
    """Supersonic fin polar via Ackeret linearised thin-airfoil theory.

    Despite the module name, this analysis does **not** drive the XFOIL
    binary for the fin cruise regime: XFOIL is a subsonic/transonic
    panel + boundary-layer code and is invalid at Mach 1.5-3.5 by
    construction. Instead this class implements the physically
    appropriate theory for that regime (Ackeret/linearised supersonic
    thin-airfoil), and documents/validates that substitution explicitly
    (see module docstring). If a registered ``xfoil`` binary is ever
    used, it would only be for a genuinely subsonic case -- see the
    ``TODO`` in the module docstring.

    Attributes:
        fidelity: :attr:`FidelityLevel.LEVEL_1` (linear analytical
            method, same tier as VLM/AVL and DATCOM-style correlations).
    """

    fidelity = FidelityLevel.LEVEL_1

    def __init__(self, name: str = "xfoil_fin_supersonic_polar") -> None:
        super().__init__(name)
        self._case: XfoilCase | None = None

    def setup(self, case: XfoilCase | None = None) -> None:
        """Bind and validate a supersonic fin polar run case.

        Args:
            case: Run case (Mach list, alpha list, t/c). Defaults to a
                new :class:`XfoilCase` built from the real fin geometry.

        Raises:
            ValueError: If any Mach number is outside
                ``[MIN_MACH, MAX_MACH]`` or ``<= MIN_MACH_ABSOLUTE``, or
                any alpha is outside ``[MIN_ALPHA_DEG, MAX_ALPHA_DEG]``.
        """
        case = case or XfoilCase()

        for mach in case.mach_list:
            if mach <= MIN_MACH_ABSOLUTE:
                raise ValueError(
                    f"Mach {mach} too close to/below 1.0 (limit "
                    f"{MIN_MACH_ABSOLUTE}); Ackeret theory is singular at "
                    "Mach 1 and invalid in the transonic band -- use "
                    "empirical transonic bridging (e.g. "
                    "YAADO_Core.modules.stability_control.methods.barrowman.barrowman_stability) instead"
                )
            if not (MIN_MACH <= mach <= MAX_MACH):
                raise ValueError(
                    f"Mach {mach} outside supported supersonic fin envelope "
                    f"[{MIN_MACH}, {MAX_MACH}]"
                )
        for alpha_deg in case.alpha_deg_list:
            if not (MIN_ALPHA_DEG <= alpha_deg <= MAX_ALPHA_DEG):
                raise ValueError(
                    f"alpha {alpha_deg} deg outside supported range "
                    f"[{MIN_ALPHA_DEG}, {MAX_ALPHA_DEG}] deg"
                )

        self._case = case
        self._is_setup = True

    def execute(self) -> AnalysisResults:
        """Compute the supersonic fin polar grid.

        Checks :mod:`YAADO_Core.solver_registry` for a registered/available
        ``xfoil`` binary purely for bookkeeping/metadata purposes: since
        every Mach number accepted by :meth:`setup` is supersonic,
        XFOIL is never dispatched (it would be invalid there), and the
        Ackeret analytical fallback always runs, with a warning
        documenting that substitution.

        Returns:
            AnalysisResults whose ``data`` is a JSON-safe nested dict::

                {
                    "<mach>": {
                        "<alpha_deg>": {
                            "CL": ...,
                            "CD": ...,
                            "CL_over_CD": ...,
                        },
                        ...
                    },
                    ...
                }

            keyed by string-formatted Mach and alpha values.

        Raises:
            RuntimeError: If called before :meth:`setup`.
        """
        if not self._is_setup or self._case is None:
            raise RuntimeError("XFOILAnalysis.execute() called before setup()")

        xfoil_info = DEFAULT_REGISTRY.get("xfoil")
        xfoil_registered_and_present = xfoil_info.is_available()
        # Every Mach accepted by setup() is >= MIN_MACH (1.5), i.e.
        # supersonic and outside XFOIL's valid subsonic/transonic window.
        # XFOIL is therefore never actually dispatched here, even if the
        # binary is present on PATH -- see module TODO for the subsonic
        # delegation path that would use it.
        warnings.warn(
            "XFOILAnalysis: Mach range is supersonic (1.5-3.5); XFOIL "
            "(a subsonic/transonic panel + boundary-layer code) is not "
            "valid in this regime and will not be invoked even though "
            f"xfoil binary registered={xfoil_registered_and_present}. "
            "Falling back to Ackeret linearised supersonic thin-airfoil "
            "theory (valid for attached, inviscid, small-disturbance "
            "supersonic flow; not applicable if shocks detach or "
            "boundary-layer separation occurs).",
            stacklevel=2,
        )

        data: dict[str, dict[str, dict[str, float]]] = {}
        for mach in self._case.mach_list:
            mach_key = f"{mach:g}"
            data[mach_key] = {}
            for alpha_deg in self._case.alpha_deg_list:
                cl, cd = ackeret_polar(mach, alpha_deg, self._case.thickness_to_chord)
                cl_over_cd = cl / cd if cd != 0.0 else float("nan")
                data[mach_key][f"{alpha_deg:g}"] = {
                    "CL": cl,
                    "CD": cd,
                    "CL_over_CD": cl_over_cd,
                }

        return AnalysisResults(
            name=self.name,
            fidelity=self.fidelity,
            data=data,  # type: ignore[arg-type]  # nested JSON-safe grid, not scalars
            metadata={
                "method": "ackeret_linearized_supersonic",
                "thickness_to_chord": self._case.thickness_to_chord,
                "xfoil_binary_available": xfoil_registered_and_present,
                "mach_range": [MIN_MACH, MAX_MACH],
                "alpha_deg_range": [MIN_ALPHA_DEG, MAX_ALPHA_DEG],
            },
        )

    def validate_results(self, results: AnalysisResults) -> bool:
        """Sanity-check the polar grid against the Ackeret formula directly.

        Recomputes CL for the first (mach, alpha) entry and compares to
        the stored value within a tight relative tolerance, guarding
        against silent unit or sign-convention errors.
        """
        if not results.data:
            return False
        mach_key = next(iter(results.data))
        alpha_key = next(iter(results.data[mach_key]))
        mach = float(mach_key)
        alpha_deg = float(alpha_key)
        t_c = results.metadata.get("thickness_to_chord", FIN_THICKNESS_TO_CHORD)
        expected_cl, _ = ackeret_polar(mach, alpha_deg, t_c)
        stored_cl = results.data[mach_key][alpha_key]["CL"]
        return math.isclose(stored_cl, expected_cl, rel_tol=1e-9)


def _plot_polar_grid(results: AnalysisResults, output_path: Path = _POLAR_PNG_PATH) -> Path:
    """Save a two-panel CL/CD-vs-alpha polar plot, one line per Mach.

    Args:
        results: Output of :meth:`XFOILAnalysis.execute`.
        output_path: PNG destination (saved at 150 DPI).

    Returns:
        The path the plot was written to.
    """
    fig, (ax_cl, ax_cd) = plt.subplots(1, 2, figsize=(11.0, 5.0), dpi=150)

    for mach_key, per_alpha in results.data.items():
        alphas = sorted((float(a) for a in per_alpha), key=float)
        cl_values = [per_alpha[f"{a:g}"]["CL"] for a in alphas]
        cd_values = [per_alpha[f"{a:g}"]["CD"] for a in alphas]
        ax_cl.plot(alphas, cl_values, marker="o", label=f"Ma {mach_key}")
        ax_cd.plot(alphas, cd_values, marker="o", label=f"Ma {mach_key}")

    ax_cl.set_xlabel("alpha [deg]")
    ax_cl.set_ylabel("CL [-]")
    ax_cl.set_title("Ackeret CL vs alpha (double-wedge fin)")
    ax_cl.grid(True, alpha=0.3)
    ax_cl.legend(fontsize=8)

    ax_cd.set_xlabel("alpha [deg]")
    ax_cd.set_ylabel("CD [-]")
    ax_cd.set_title("Ackeret CD vs alpha (double-wedge fin)")
    ax_cd.grid(True, alpha=0.3)
    ax_cd.legend(fontsize=8)

    fig.suptitle("MELprop ramjet fin -- supersonic Ackeret polar grid")
    fig.tight_layout()

    output_path = Path(output_path)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def main() -> dict[str, Any]:
    """Run the default supersonic fin polar grid, write JSON + PNG.

    Returns:
        The JSON-serializable results dict (also written to
        ``xfoil_runner_results.json`` next to this module).
    """
    analysis = XFOILAnalysis()
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        analysis.setup()
        results = analysis.execute()

    assert analysis.validate_results(results), "Ackeret polar failed self-consistency check"

    output: dict[str, Any] = {
        "data": results.data,
        "metadata": results.metadata,
    }

    _RESULTS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _RESULTS_JSON_PATH.open("w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)

    _plot_polar_grid(results, _POLAR_PNG_PATH)

    return output


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
    print(f"\nResults written to: {_RESULTS_JSON_PATH}")
    print(f"Plot written to: {_POLAR_PNG_PATH}")
