Low-order 3-DOF boost-phase trajectory point-mass integrator.

This module integrates a point-mass, vertical-plane (3-DOF: range, altitude,
and their rates) equation of motion for the solid-propellant booster stage
of a rocket vehicle, from ignition to nominal burnout
(``burn_time`` from the vehicle config) or ground impact, whichever comes
first.

Theory / model references:
    - Equations of motion: point-mass flight mechanics, e.g. Anderson,
      *Introduction to Flight*, ch. 9 (rocket/missile trajectory), or
      Sutton & Biblarz, *Rocket Propulsion Elements*, ch. 4.
    - ISA troposphere model: ICAO Doc 7488 (Manual of the ICAO Standard
      Atmosphere), ``0 <= h < 11000 m`` layer, constant lapse rate.
    - Impulse-consistent thrust ``F = mdot * Isp * g0``: Sutton & Biblarz,
      *Rocket Propulsion Elements*, eq. 2-14.
    - Drag build-up (subsonic/transonic/supersonic step CD, fin wave drag):
      simplified DATCOM-style body + fin drag estimate, consistent with the
      empirical (non-AVL) supersonic aero approach.

Limitations of the current model:
    This is a point-mass, 3-DOF model with a fixed launch angle (no pitch
    program or thrust-vector control). A basic zero-lift gravity turn is
    assumed: thrust acts along the body axis at the fixed launch angle;
    aerodynamic lift is not modeled explicitly. For the near-vertical launch
    angle used (83 deg, typical small sounding rocket rail launch), this
    approximation is reasonable through the boost phase. A higher-fidelity
    model would include angle-of-attack-dependent lift and a pitch autopilot.

Note on planned expansion:
    Currently, this solver terminates strictly at motor burnout, returning
    burnout state and ``range_at_burnout`` (it does not simulate unpowered
    coasting to apogee or ground impact). Planned updates will extend the ODE
    past burnout with T = 0 to calculate full-flight metrics (apogee altitude
    and total flight range).

Run as a script to integrate the trajectory, print the burnout state, and
write ``burnout_state.json`` + ``boost_phase.png`` next to this file. It
also runs a launch-angle sensitivity sweep (:func:`run_launch_angle_sweep`,
angles 5-30 deg) and writes ``launch_angle_sweep.csv`` +
``launch_angle_sweep.png``; the recommended angle (smallest swept angle
that avoids ground impact) is added to the JSON as
``recommended_launch_angle_deg``::