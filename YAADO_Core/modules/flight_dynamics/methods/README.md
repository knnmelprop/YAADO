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

Simulation termination control:
    By default, the solver terminates at booster motor burnout (``stop_at_burnout=True``),
    reporting burnout state and ``range_at_burnout``. Setting ``stop_at_burnout=False``
    (via ``operating_state={"stop_at_burnout": False}`` or kwarg) extends the ODE
    past burnout with T = 0 through unpowered coasting to determine full-flight metrics:
    ``apogee_altitude``, ``apogee_time``, total ``flight_time``, total ``flight_range``,
    and ``impact_velocity``.

Usage via YAADO module orchestration:
    Invoke via :func:`run_boost_study` with a configured :class:`~YAADO_Core.Foundation.flight_logger.FlightLogger`
    instance. The function executes the trajectory integration, performs a launch-angle
    sensitivity sweep, and persists structured checkpoints (``results.json``, ``summary.csv``),
    visual trajectory plots (``boost_phase.png``, ``full_flight.png``, ``launch_angle_sweep.png``),
    and sweep data artifacts (``launch_angle_sweep.csv``) directly inside the run logger directory.