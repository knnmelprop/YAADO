"""Formatting utilities for compact SI values, units, and aerospace symbols.

Provides clean scalar value and unit formatting for UI labels and pipeline badges.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Terminal.screens.flight_deck import PipelineStage

PARAM_SYMBOLS: dict[str, str] = {
    # Flight Dynamics / Trajectory
    "launch_angle_deg": "γ₀",
    "launch_angle": "γ₀",
    "altitude_m": "h₀",
    "altitude": "h",
    "ground_altitude_m": "h_g",
    "stop_at_burnout": "stop_burnout",
    "t_max_s": "t_max",
    "time_step_s": "dt",
    "v0_ms": "V₀",
    # Aerodynamics
    "mach": "M",
    "mach_number": "M",
    "alpha_deg": "α",
    "beta_deg": "β",
    "reynolds": "Re",
    "dynamic_pressure": "q",
    # Propulsion
    "throttle": "throttle",
    "thrust": "T",
}


def format_compact_value_and_unit(val: object, unit: str) -> tuple[str, str]:
    """Format numeric or string parameter value and SI unit into compact display representation."""
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        return str(val), unit if unit and unit != "-" else ""

    num = float(val)
    if num == 0.0:
        return "0", unit if unit and unit != "-" else ""

    if unit == "deg":
        if abs(num) >= 100 or num.is_integer():
            return f"{num:.0f}", "°"
        return f"{num:.1f}".rstrip("0").rstrip("."), "°"

    if unit == "N":
        if abs(num) >= 1e6:
            return f"{num / 1e6:.2f}".rstrip("0").rstrip("."), "MN"
        if abs(num) >= 1000:
            return f"{num / 1000:.2f}".rstrip("0").rstrip("."), "kN"
        return f"{num:.1f}".rstrip("0").rstrip("."), "N"

    if unit == "Pa":
        if abs(num) >= 1e6:
            return f"{num / 1e6:.2f}".rstrip("0").rstrip("."), "MPa"
        if abs(num) >= 1000:
            return f"{num / 1000:.2f}".rstrip("0").rstrip("."), "kPa"
        return f"{num:.1f}".rstrip("0").rstrip("."), "Pa"

    unit_str = unit if unit and unit != "-" else ""
    if abs(num) < 0.0001 or abs(num) >= 1e6:
        val_str = f"{num:.2e}"
    elif abs(num) >= 1000:
        val_str = f"{num:.0f}"
    elif abs(num) >= 10:
        val_str = f"{num:.1f}".rstrip("0").rstrip(".")
    else:
        val_str = f"{num:.3f}".rstrip("0").rstrip(".")

    return val_str, unit_str


_format_compact_value_and_unit = format_compact_value_and_unit


def format_stage_param_specs(stage: PipelineStage) -> str:
    """Format configured solver stage parameters into compact aerospace symbol badges.

    Args:
        stage: Pipeline stage containing solver descriptor and configured parameter values.

    Returns:
        Space-separated compact symbol string (e.g. 'γ₀=83°  h₀=100m  stop_burnout=True').
    """
    param_map = {p.name: p for p in stage.descriptor.parameters}
    parts: list[str] = []
    for k, v in stage.params.items():
        if k in ("fins_name", "motor_name", "body_name"):
            continue
        p_def = param_map.get(k)
        sym = p_def.symbol if p_def else PARAM_SYMBOLS.get(k, k[:4])
        unit = p_def.unit if p_def else ""
        if isinstance(v, bool):
            parts.append(f"{sym}={v}")
        else:
            val_str, unit_str = format_compact_value_and_unit(v, unit)
            parts.append(f"{sym}={val_str}{unit_str}")
    return "  ".join(parts)
