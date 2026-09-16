"""Canonical SI unit type annotations for the YAADO framework.

These semantic type aliases use standard library :mod:`typing.Annotated` to attach
physical unit metadata directly to Python floats with zero runtime performance overhead.
Type checkers (Mypy) see raw floats, while IDE tooltips and reflection helpers
(e.g., in :class:`~YAADO_Core.Foundation.analysis_base.BaseAnalysisResults`)
inspect the attached unit symbol string.

All internal values in YAADO must be stored in canonical SI units.
"""

from __future__ import annotations

from typing import Annotated

# -----------------------------------------------------------------------------
# Fundamental SI Dimensions
# -----------------------------------------------------------------------------

#: Length or distance [m]
Meters = Annotated[float, "m"]

#: Time duration [s]
Seconds = Annotated[float, "s"]

#: Mass [kg]
Kilograms = Annotated[float, "kg"]

#: Absolute temperature [K]
Kelvin = Annotated[float, "K"]

# -----------------------------------------------------------------------------
# Kinematics & Dynamics
# -----------------------------------------------------------------------------

#: Velocity or speed [m/s]
MetersPerSecond = Annotated[float, "m/s"]

#: Linear acceleration [m/s^2]
MetersPerSecond2 = Annotated[float, "m/s^2"]

#: Mass flow rate [kg/s]
KilogramsPerSecond = Annotated[float, "kg/s"]

#: Force or thrust [N]
Newtons = Annotated[float, "N"]

#: Pressure or stress [Pa]
Pascals = Annotated[float, "Pa"]

#: Energy or work [J]
Joules = Annotated[float, "J"]

#: Power [W]
Watts = Annotated[float, "W"]

#: Density [kg/m^3]
KilogramsPerCubicMeter = Annotated[float, "kg/m^3"]

#: Dynamic viscosity [Pa*s]
PascalSeconds = Annotated[float, "Pa*s"]

# -----------------------------------------------------------------------------
# Geometry
# -----------------------------------------------------------------------------

#: Planform, cross-sectional, or reference area [m^2]
SquareMeters = Annotated[float, "m^2"]

#: Volume [m^3]
CubicMeters = Annotated[float, "m^3"]

#: Plane angle in radians [rad]
Radians = Annotated[float, "rad"]

#: Plane angle in degrees [deg] (only at boundary interfaces, internal defaults to radians/SI)
Degrees = Annotated[float, "deg"]

# -----------------------------------------------------------------------------
# Non-Dimensional & Dimensionless Ratios
# -----------------------------------------------------------------------------

#: Dimensionless ratio, Mach number, or aerodynamic coefficient [-]
Dimensionless = Annotated[float, "-"]
