# MELprop-IADE | analyses.propulsion.cycle_v2 | v0.1.0
"""Heiser & Pratt stream-thrust ramjet cycle rebuild (station-wise gamma).

This subpackage reimplements the ramjet cycle on a Heiser & Pratt
(*Hypersonic Airbreathing Propulsion*, AIAA, 1994) stream-thrust station
framework, with **station-dependent gamma** (cold inlet air ~1.40,
post-combustion products ~1.25-1.30) rather than the single constant
gamma=1.4 of the legacy Grzywka MATLAB model. It is a NEW, complementary
model: the legacy :mod:`analyses.propulsion.combustor_nozzle_cycle` and
:mod:`analyses.propulsion.ramjet_cycle` are left untouched.
"""
