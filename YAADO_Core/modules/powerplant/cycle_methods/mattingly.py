"""Mattingly parametric real-ramjet cycle, per unit air mass flow.

Mattingly, *Elements of Propulsion: Gas Turbines and Rockets*, 2nd ed., AIAA,
2006, Sec. 7.3 (ideal ramjet) and 7.6 (real ramjet). Stations: 0 freestream,
2 diffuser exit, 4 combustor exit, 9 nozzle exit. Two gases: air ahead of the
combustor (``gamma_c``), products behind it (``gamma_t``), same gas constant.

    tau_r = 1 + (gamma_c - 1)/2 M0^2,  pi_r = tau_r^(gamma_c/(gamma_c - 1))
    pi_d = pi_d_max * eta_r,  eta_r = 1 - 0.075 (M0 - 1)^1.35 for M0 <= 5,
                              800 / (M0^4 + 935) above        (MIL-E-5007D)
    tau_lambda = cp_t Tt4 / (cp_c T0)
    f = (tau_lambda - tau_r) / (eta_b h / (cp_c T0) - tau_lambda)
    Pt9/P9 = (P0/P9) pi_r pi_d pi_b pi_n
    F/m0 = a0 [ (1 + f) V9/a0 - M0 + (1 + f) (R T9/T0) / (R V9/a0) (1 - P0/P9) / gamma_c ]

The cycle is independent of engine size: it shows which flight Mach number and
combustor temperature give the best specific thrust and fuel consumption.
Heiser & Pratt evaluates a sized engine with a fixed nozzle.
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import astuple, fields, replace
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np

if TYPE_CHECKING:
    from matplotlib.figure import Figure

import YAADO_Core.Foundation.constants as const
from YAADO_Core.ComponentStore import RAMJET_COMPONENTS
from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.atmosphere import isa_atmosphere
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.powerplant.containers import (
    CycleMachPoint,
    RamjetCycleInputs,
    RamjetCycleResults,
)
from YAADO_Core.modules.powerplant.cycle_methods.heiser_pratt import (
    HeiserPrattCycleAnalysis,
)
from YAADO_Core.modules.powerplant.inlet_methods.taylor_maccoll import (
    mil_e_5007d_recovery,
)


def stagnation_temperature(static_temperature: float, mach: float, gamma: float) -> float:
    """Total temperature [K]: ``T (1 + (gamma - 1)/2 M^2)``."""
    return static_temperature * (1.0 + 0.5 * (gamma - 1.0) * mach * mach)


def stagnation_pressure(static_pressure: float, mach: float, gamma: float) -> float:
    """Total pressure [Pa]: ``p (1 + (gamma - 1)/2 M^2)^(gamma/(gamma - 1))``."""
    return static_pressure * (1.0 + 0.5 * (gamma - 1.0) * mach * mach) ** (gamma / (gamma - 1.0))


def ram_recovery(mach: float) -> float:
    """MIL-E-5007D ram recovery ``eta_r``: 1 up to Mach 1, then the shock-loss term.

    ``1 - 0.075 (M - 1)^1.35`` for Mach 1 to 5 and ``800 / (M^4 + 935)`` above
    (Mattingly, Eq. 4.12).
    """
    if mach <= 5.0:
        return mil_e_5007d_recovery(mach)
    return 800.0 / (mach**4 + 935.0)


def _cp(gamma: float) -> float:
    """Specific heat at constant pressure [J/(kg K)] for the air gas constant."""
    return gamma * const.R_AIR / (gamma - 1.0)


def ideal_ramjet_specific_thrust(
    mach: float, t0: float, tt4: float, gamma: float = const.GAMMA_AIR
) -> float:
    """Ideal-ramjet specific thrust [N s/kg] with ``f << 1`` (Mattingly, Eq. 7.17).

    ``F/m0 = a0 M0 (sqrt(tau_lambda / tau_r) - 1)`` with one gas and no losses.
    """
    a0 = math.sqrt(gamma * const.R_AIR * t0)
    tau_r = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
    return a0 * mach * (math.sqrt(tt4 / t0 / tau_r) - 1.0)


def _expand(
    inputs: RamjetCycleInputs, pi_d: float, pi_b: float, pi_n: float, eta_b: float,
    p0_over_p9: float,
) -> tuple[float, float, float, float, float]:
    """Fuel-air ratio, specific thrust, exit Mach, T9/T0 and V9/a0 for given losses.

    Raises:
        ValueError: If there is no heat addition or no nozzle expansion.
    """
    gc, gt = inputs.gamma_c, inputs.gamma_t
    t0 = isa_atmosphere(inputs.altitude).temperature
    a0 = math.sqrt(gc * const.R_AIR * t0)
    m0 = inputs.mach
    tau_r = 1.0 + 0.5 * (gc - 1.0) * m0 * m0
    pi_r = tau_r ** (gc / (gc - 1.0))
    tau_lambda = _cp(gt) * inputs.tt4 / (_cp(gc) * t0)
    if inputs.tt4 <= t0 * tau_r or tau_lambda <= tau_r:
        raise ValueError(
            f"Combustor exit temperature {inputs.tt4:.0f} K adds no heat at Mach {m0:g} "
            f"(freestream total temperature {t0 * tau_r:.0f} K)."
        )
    f = (tau_lambda - tau_r) / (eta_b * inputs.fuel_lhv / (_cp(gc) * t0) - tau_lambda)

    pt9_over_p9 = p0_over_p9 * pi_r * pi_d * pi_b * pi_n
    if pt9_over_p9 <= 1.0:
        raise ValueError(f"Nozzle pressure ratio Pt9/P9 = {pt9_over_p9:.3f} cannot expand the flow.")
    expansion = pt9_over_p9 ** ((gt - 1.0) / gt)
    m9 = math.sqrt(2.0 / (gt - 1.0) * (expansion - 1.0))
    t9_over_t0 = (inputs.tt4 / t0) / expansion
    v9_over_a0 = m9 * math.sqrt(gt * t9_over_t0 / gc)
    specific_thrust = a0 * (
        (1.0 + f) * v9_over_a0 - m0 + (1.0 + f) * t9_over_t0 / v9_over_a0 * (1.0 - p0_over_p9) / gc
    )
    return f, specific_thrust, m9, t9_over_t0, v9_over_a0


def evaluate_cycle(
    inputs: RamjetCycleInputs,
    *,
    name: str = "mattingly_cycle",
    fidelity: FidelityLevel = FidelityLevel.LEVEL_2,
) -> RamjetCycleResults:
    """Evaluate the real-ramjet cycle at one flight condition.

    Raises:
        ValueError: If there is no heat addition, no nozzle expansion or no net thrust.
    """
    t0 = isa_atmosphere(inputs.altitude).temperature
    a0 = math.sqrt(inputs.gamma_c * const.R_AIR * t0)
    m0 = inputs.mach
    pi_d = inputs.pi_d_max * ram_recovery(m0)
    f, specific_thrust, m9, t9_over_t0, v9_over_a0 = _expand(
        inputs, pi_d, inputs.pi_b, inputs.pi_n, inputs.eta_b, inputs.p0_over_p9
    )
    if specific_thrust <= 0.0:
        raise ValueError(
            f"No net thrust at Mach {m0:g} with Tt4 = {inputs.tt4:.0f} K "
            f"(F/m0 = {specific_thrust:.1f} N s/kg): raise tt4 or lower the Mach number."
        )
    lossless_thrust = _expand(inputs, 1.0, 1.0, 1.0, 1.0, 1.0)[1]

    kinetic_gain = a0 * a0 * ((1.0 + f) * v9_over_a0**2 - m0 * m0)
    thermal = kinetic_gain / (2.0 * f * inputs.fuel_lhv)
    propulsive = 2.0 * m0 * a0 * specific_thrust / kinetic_gain
    return RamjetCycleResults(
        name=name,
        fidelity=fidelity,
        inputs=inputs,
        t0=t0,
        tt0=stagnation_temperature(t0, m0, inputs.gamma_c),
        v0=m0 * a0,
        pi_d=pi_d,
        fuel_air_ratio=f,
        specific_thrust=specific_thrust,
        tsfc=f / specific_thrust,
        specific_impulse=specific_thrust / (f * const.G0),
        mach_exit=m9,
        v_exit=v9_over_a0 * a0,
        t_exit=t9_over_t0 * t0,
        thermal_efficiency=thermal,
        propulsive_efficiency=propulsive,
        overall_efficiency=thermal * propulsive,
        lossless_specific_thrust=lossless_thrust,
    )


def run_mach_sweep(results: RamjetCycleResults) -> list[CycleMachPoint]:
    """Cycle performance across Mach at the run's ``tt4``, altitude and losses.

    Points where the cycle cannot run (no heat addition or no expansion) are skipped.
    """
    machs = np.linspace(
        MattinglyCycleAnalysis.SWEEP_MACH_MIN,
        max(MattinglyCycleAnalysis.SWEEP_MACH_MAX, 1.25 * results.inputs.mach),
        MattinglyCycleAnalysis.SWEEP_POINTS,
    )
    points = []
    for m in machs:
        try:
            r = evaluate_cycle(replace(results.inputs, mach=float(m)))
        except ValueError:
            continue
        if r.specific_thrust <= 0.0:
            continue
        points.append(
            CycleMachPoint(
                mach=float(m),
                specific_thrust=r.specific_thrust,
                tsfc=r.tsfc,
                fuel_air_ratio=r.fuel_air_ratio,
                thermal_efficiency=r.thermal_efficiency,
                propulsive_efficiency=r.propulsive_efficiency,
                overall_efficiency=r.overall_efficiency,
            )
        )
    return points


def format_mach_sweep_csv(points: list[CycleMachPoint]) -> str:
    """CSV text of the Mach sweep."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(f.name for f in fields(CycleMachPoint))
    writer.writerows(astuple(p) for p in points)
    return buffer.getvalue()


def plot_mach_sweep(points: list[CycleMachPoint], results: RamjetCycleResults) -> Figure:
    """Plot specific thrust, TSFC, fuel-air ratio and efficiencies against Mach.

    Args:
        points: Output of :func:`run_mach_sweep`.
        results: Results of the run, marked on each panel.

    Returns:
        The matplotlib Figure instance.
    """
    import matplotlib.pyplot as plt

    machs = [p.mach for p in points]
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 8.0), sharex=True)
    panels = (
        (axes[0, 0], [p.specific_thrust for p in points], "Specific thrust F/m0 [N s/kg]",
         results.specific_thrust),
        (axes[0, 1], [1e6 * p.tsfc for p in points], "TSFC [mg/(N s)]", 1e6 * results.tsfc),
        (axes[1, 0], [p.fuel_air_ratio for p in points], "Fuel-air ratio f [-]",
         results.fuel_air_ratio),
    )
    for ax, values, label, run_value in panels:
        ax.plot(machs, values, lw=2.0)
        ax.plot(results.inputs.mach, run_value, "o", color="k")
        ax.set_ylim(bottom=0.0)
        ax.set_ylabel(label)
    ax = axes[1, 1]
    ax.plot(machs, [p.thermal_efficiency for p in points], label="Thermal")
    ax.plot(machs, [p.propulsive_efficiency for p in points], label="Propulsive")
    ax.plot(machs, [p.overall_efficiency for p in points], lw=2.0, label="Overall")
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Efficiency [-]")
    ax.legend(fontsize=8)
    for ax in axes.flat:
        ax.grid(True, alpha=0.3)
    for ax in axes[1]:
        ax.set_xlabel("Flight Mach number [-]")
    fig.suptitle(
        f"Real ramjet cycle, Tt4 = {results.inputs.tt4:.0f} K, {results.inputs.altitude:.0f} m"
    )
    fig.tight_layout()
    return fig


class MattinglyCycleAnalysis(BaseAnalysis[RamjetCycleResults]):
    """Mattingly parametric real-ramjet cycle at the ramjet's design point.

    Example:
        analysis = MattinglyCycleAnalysis()
        analysis.setup(vehicle, altitude_m=12000.0)
        results = analysis.execute()
        tsfc = results.tsfc
    """

    fidelity = FidelityLevel.LEVEL_2

    DEFAULT_ALTITUDE_M: ClassVar[float] = HeiserPrattCycleAnalysis.DEFAULT_ALTITUDE_M

    #: Diffuser pressure ratio without shock losses (Mattingly's pi_d_max).
    DEFAULT_PI_D_MAX: ClassVar[float] = 0.95

    SWEEP_MACH_MIN: ClassVar[float] = 1.2
    SWEEP_MACH_MAX: ClassVar[float] = 5.0
    SWEEP_POINTS: ClassVar[int] = 39

    def __init__(self, name: str = "mattingly_cycle") -> None:
        super().__init__(name)
        self._inputs: RamjetCycleInputs | None = None
        self._assumed: tuple[str, ...] = ()

    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        engine_name: str | None = None,
        mach: float | None = None,
        altitude_m: float = DEFAULT_ALTITUDE_M,
        tt4: float | None = None,
        pi_d_max: float | None = None,
        pi_b: float | None = None,
        pi_n: float | None = None,
        eta_b: float | None = None,
        p0_over_p9: float = 1.0,
        gamma_hot: float | None = None,
        fuel_lhv: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Resolve the ramjet and build the cycle inputs.

        Args:
            vehicle: Vehicle with a ramjet propulsion component.
            engine_name: Ramjet to use if the vehicle has more than one.
            mach: Flight Mach number. Defaults to ``design_mach``.
            altitude_m: ISA flight altitude [m].
            tt4: Combustor-exit total temperature [K]. Defaults to ``combustor_temp``.
            pi_d_max: Diffuser ratio without shock losses. Defaults to the ramjet's
                ``inlet_recovery`` divided by the MIL-E-5007D term at ``design_mach``,
                then to a placeholder.
            pi_b: Combustor total-pressure ratio. Defaults to
                ``combustor_pressure_ratio``, then to a placeholder.
            pi_n: Nozzle total-pressure ratio. Defaults to ``nozzle_pressure_ratio``,
                then to a placeholder.
            eta_b: Combustion efficiency. Defaults to ``combustion_efficiency``, then
                to a placeholder.
            p0_over_p9: Ambient over exit static pressure; 1 is perfectly expanded.
            gamma_hot: Ratio of specific heats of the products. Required unless the
                ramjet burns kerosene.
            fuel_lhv: Fuel lower heating value [J/kg]. Required unless the ramjet
                burns kerosene.
            **kwargs: Not accepted; present for the ``BaseAnalysis`` signature.

        Raises:
            TypeError: If an unknown setting is passed.
            ValueError: If the vehicle has no ramjet, the fuel properties are missing,
                or a setting is out of range.
        """
        if kwargs:
            raise TypeError(f"Unknown settings for '{self.name}': {sorted(kwargs)}")
        engine = vehicle.find_single_component(RAMJET_COMPONENTS, engine_name)
        defaults = HeiserPrattCycleAnalysis
        is_kerosene = engine.fuel_type.strip().lower() == defaults.DEFAULT_FUEL_TYPE
        if not is_kerosene and (gamma_hot is None or fuel_lhv is None):
            raise ValueError(
                f"fuel_type='{engine.fuel_type}' has no default properties: "
                "pass both gamma_hot and fuel_lhv."
            )

        assumed: list[str] = []

        def resolve(override: float | None, vehicle_value: float | None, label: str,
                    default: float) -> float:
            if override is not None:
                return override
            if vehicle_value is not None:
                return vehicle_value
            assumed.append(label)
            return default

        tabulated_pi_d_max = (
            None
            if engine.inlet_recovery is None
            else engine.inlet_recovery / ram_recovery(engine.design_mach)
        )
        inputs = RamjetCycleInputs(
            mach=engine.design_mach if mach is None else mach,
            altitude=altitude_m,
            tt4=engine.combustor_temp if tt4 is None else tt4,
            pi_d_max=resolve(pi_d_max, tabulated_pi_d_max, "inlet_recovery", self.DEFAULT_PI_D_MAX),
            pi_b=resolve(pi_b, engine.combustor_pressure_ratio, "combustor_pressure_ratio",
                         defaults.DEFAULT_PI_CC),
            pi_n=resolve(pi_n, engine.nozzle_pressure_ratio, "nozzle_pressure_ratio",
                         defaults.DEFAULT_PI_NOZZLE),
            eta_b=resolve(eta_b, engine.combustion_efficiency, "combustion_efficiency",
                          defaults.DEFAULT_ETA_B),
            p0_over_p9=p0_over_p9,
            gamma_c=const.GAMMA_AIR,
            gamma_t=defaults.DEFAULT_GAMMA_HOT if gamma_hot is None else gamma_hot,
            fuel_lhv=const.LHV_KEROSENE if fuel_lhv is None else fuel_lhv,
        )
        for label, value in (("pi_d_max", inputs.pi_d_max), ("pi_b", inputs.pi_b),
                             ("pi_n", inputs.pi_n), ("eta_b", inputs.eta_b)):
            if not 0.0 < value <= 1.0:
                raise ValueError(f"{label} must be in (0, 1], got {value}")
        if inputs.mach <= 0.0 or inputs.p0_over_p9 <= 0.0:
            raise ValueError("mach and p0_over_p9 must be > 0")

        self._inputs = inputs
        self._assumed = tuple(assumed)
        self.logger.info(
            "Configured Mattingly cycle for vehicle '%s' (M=%.2f, h=%.0f m, Tt4=%.0f K)",
            vehicle.name,
            inputs.mach,
            inputs.altitude,
            inputs.tt4,
        )
        if assumed:
            self.logger.warning("Placeholder values used for: %s", ", ".join(assumed))

    def _compute(self, **kwargs: Any) -> RamjetCycleResults:
        """Evaluate the cycle at the configured flight condition."""
        if self._inputs is None:
            raise RuntimeError(f"Analysis '{self.name}' must be setup before computation.")
        results = replace(
            evaluate_cycle(self._inputs, name=self.name, fidelity=self.fidelity),
            assumed=self._assumed,
        )
        self.logger.info(
            "F/m0=%.1f N s/kg, TSFC=%.2f mg/(N s), f=%.4f, Isp=%.0f s, eta_o=%.3f",
            results.specific_thrust,
            1e6 * results.tsfc,
            results.fuel_air_ratio,
            results.specific_impulse,
            results.overall_efficiency,
        )
        return results

    def validate_results(self, results: RamjetCycleResults) -> bool:
        """Check finite values, burning fuel, supersonic exit and efficiencies in (0, 1).

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        if not all(math.isfinite(v) for v in results.scalars().values()):
            return False
        if results.fuel_air_ratio <= 0.0:
            return False
        return 0.0 < results.thermal_efficiency < 1.0 and results.propulsive_efficiency > 0.0
