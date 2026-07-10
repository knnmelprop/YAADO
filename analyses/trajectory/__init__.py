# MELprop-IADE | analyses.trajectory | v0.1.0
"""Low-order trajectory analyses (point-mass, 3-DOF) for MELprop vehicles.

This package holds solver-agnostic, self-contained trajectory scripts that
sit alongside (but are not part of) the OpenMDAO/`core.mission_builder`
mission layer. They are meant for quick, low-order sizing checks — e.g. the
stage-1 solid-booster boost phase for Project B (two-stage ramjet rocket) —
using `scipy.integrate.solve_ivp` rather than a full MDO problem.
"""
