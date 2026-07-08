# MELprop-IADE | analyses.stability | v0.1.0
"""Static-stability analyses for MELprop-IADE vehicles.

Currently provides a low-order Barrowman (subsonic) / Rogers-extended
(transonic-supersonic) center-of-pressure method for slender body +
fin rockets (Project B — ramjet_rocket). See
:mod:`analyses.stability.barrowman_stability`.
"""

from analyses.stability.barrowman_stability import BarrowmanStabilityAnalysis

__all__ = ["BarrowmanStabilityAnalysis"]
