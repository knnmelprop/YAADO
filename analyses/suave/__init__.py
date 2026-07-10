# MELprop-IADE | analyses.suave | v0.1.0
"""SUAVE-integrated (with 0D-fallback) mission baseline analyses.

Wires the Night-3 propulsion data (RamP stage-2 ramjet, Grzywka
combustor/nozzle cycle) and the stage-1 booster boost-phase trajectory
into a two-segment baseline mission profile. Prefers a real SUAVE
mission-segment solve (:mod:`SUAVE.Analyses.Mission.Segments`) when the
package is importable and functional; degrades gracefully to a
solver-agnostic 0D mission integrator otherwise (this container does not
have the reference SUAVE fork from ``external/suave/trunk/SUAVE`` installed as a top
-level package).
"""
