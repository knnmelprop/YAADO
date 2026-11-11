"""Ramjet combustor and nozzle sizing at one flight condition, after Grzywka.

Stations follow Grzywka (*Analiza numeryczna komory spalania i dyszy silnika
strumieniowego*, Politechnika Warszawska, 2022): 1 combustor inlet, 2 combustor
exit, 21 choked throat, 3 nozzle exit expanded to ambient pressure.

    pt1 = eta_inlet pt0,  Tt1 = Tt0
    pt2 = pi_cc pt1,      f = (cp_t Tt2 - cp_c Tt1) / (eta_b h - cp_t Tt2)
    A21 = mdot_exit / (choked mass flux at pt2, Tt2)
    T3 = Tt2 (p0 / pt_n)^((gamma_t - 1)/gamma_t),  V3 = sqrt(2 cp_t (Tt2 - T3))
    A3 = mdot_exit / (rho3 V3),  F = mdot_exit V3 - mdot_air V0

Heiser & Pratt analyses a nozzle of given area ratio; this module finds the
throat and exit that pass the flow and expand it fully. Three thrust levels use
the nozzle total pressure ``pt_n``: pt1 (ideal), pt2 (combustor loss) and
``pi_nozzle pt2`` (real).
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
    GrzywkaCycleResults,
    GrzywkaInputs,
    NozzleSizingPoint,
)
from YAADO_Core.modules.powerplant.cycle_methods.heiser_pratt import (
    R_PRODUCTS,
    HeiserPrattCycleAnalysis,
    choked_mass_flux,
)


def fully_expanded_exit(
    tt: float, pt_nozzle: float, p0: float, gamma: float
) -> tuple[float, float, float]:
    """Exit temperature [K], velocity [m/s] and Mach number at ambient pressure.

    Raises:
        ValueError: If ``pt_nozzle <= p0`` (no expansion).
    """
    if pt_nozzle <= p0:
        raise ValueError(f"Nozzle total pressure {pt_nozzle:.0f} Pa cannot expand to {p0:.0f} Pa")
    cp = gamma * R_PRODUCTS / (gamma - 1.0)
    t_exit = tt * (p0 / pt_nozzle) ** ((gamma - 1.0) / gamma)
    v_exit = math.sqrt(2.0 * cp * (tt - t_exit))
    return t_exit, v_exit, v_exit / math.sqrt(gamma * R_PRODUCTS * t_exit)


def _circle_diameter(area: float) -> float:
    return math.sqrt(4.0 * area / math.pi)


def evaluate_sizing(
    inputs: GrzywkaInputs,
    *,
    name: str = "grzywka_nozzle",
    fidelity: FidelityLevel = FidelityLevel.LEVEL_2,
) -> GrzywkaCycleResults:
    """Size the throat and the fully expanded exit at one flight condition.

    Raises:
        ValueError: If the combustor adds no heat, the nozzle cannot choke with
            the real total pressure, or the cycle gives no net thrust.
    """
    gc, gt = inputs.gamma_cold, inputs.gamma_hot
    atmosphere = isa_atmosphere(inputs.altitude)
    t0, p0 = atmosphere.temperature, atmosphere.pressure
    v0 = inputs.mach * math.sqrt(gc * const.R_AIR * t0)
    stagnation = 1.0 + 0.5 * (gc - 1.0) * inputs.mach**2
    tt0 = t0 * stagnation
    pt0 = p0 * stagnation ** (gc / (gc - 1.0))
    if inputs.tt4 <= tt0:
        raise ValueError(
            f"Combustor exit temperature {inputs.tt4:.0f} K adds no heat at Mach "
            f"{inputs.mach:g} (flight total temperature {tt0:.0f} K)."
        )

    cp_c = gc * const.R_AIR / (gc - 1.0)
    cp_t = gt * R_PRODUCTS / (gt - 1.0)
    burner_margin = inputs.eta_b * inputs.fuel_lhv - cp_t * inputs.tt4
    if burner_margin <= 0.0:
        raise ValueError(f"tt4 = {inputs.tt4:.0f} K is not reachable with this fuel")
    f = (cp_t * inputs.tt4 - cp_c * tt0) / burner_margin

    pt1 = inputs.eta_inlet * pt0
    pt2 = inputs.pi_cc * pt1
    pt_real = inputs.pi_nozzle * pt2
    critical = ((gt + 1.0) / 2.0) ** (gt / (gt - 1.0))
    if pt_real / p0 < critical:
        raise ValueError(
            f"Nozzle pressure ratio {pt_real / p0:.2f} is below the critical {critical:.2f}: "
            f"the throat cannot choke at Mach {inputs.mach:g}."
        )

    flux = choked_mass_flux(pt2, inputs.tt4, gt, R_PRODUCTS)
    if inputs.throat_area is not None:
        mdot_air = flux * inputs.throat_area / (1.0 + f)
    elif inputs.mdot_air is not None:
        mdot_air = inputs.mdot_air
    else:
        assert inputs.capture_area is not None  # guaranteed by GrzywkaInputs
        mdot_air = atmosphere.density * v0 * inputs.capture_area
    mdot_exit = mdot_air * (1.0 + f)
    throat_area = mdot_exit / flux

    def thrust(pt_nozzle: float) -> float:
        _, v_exit, _ = fully_expanded_exit(inputs.tt4, pt_nozzle, p0, gt)
        return mdot_exit * v_exit - mdot_air * v0

    t_exit, v_exit, mach_exit = fully_expanded_exit(inputs.tt4, pt_real, p0, gt)
    thrust_real = mdot_exit * v_exit - mdot_air * v0
    if thrust_real <= 0.0:
        raise ValueError(f"No net thrust at Mach {inputs.mach:g} with Tt4 = {inputs.tt4:.0f} K.")
    exit_area = mdot_exit * R_PRODUCTS * t_exit / (p0 * v_exit)

    return GrzywkaCycleResults(
        name=name,
        fidelity=fidelity,
        inputs=inputs,
        t0=t0,
        p0=p0,
        v0=v0,
        tt0=tt0,
        pt0=pt0,
        pt_combustor_inlet=pt1,
        pt_combustor_exit=pt2,
        fuel_air_ratio=f,
        mdot_air=mdot_air,
        mdot_exit=mdot_exit,
        capture_area=mdot_air / (atmosphere.density * v0),
        throat_area=throat_area,
        throat_diameter=_circle_diameter(throat_area),
        exit_area=exit_area,
        exit_diameter=_circle_diameter(exit_area),
        area_ratio=exit_area / throat_area,
        mach_exit=mach_exit,
        v_exit=v_exit,
        t_exit=t_exit,
        thrust_ideal=thrust(pt1),
        thrust_cc_loss=thrust(pt2),
        thrust_real=thrust_real,
        specific_impulse=thrust_real / (f * mdot_air * const.G0),
    )


def run_mach_sweep(results: GrzywkaCycleResults) -> list[NozzleSizingPoint]:
    """Nozzle size and thrust across Mach for the run's inlet capture area and losses.

    The capture area stays fixed, as for a real inlet, so the throat and exit that
    the flow needs change with Mach. Points where the combustor adds no heat or the
    nozzle cannot choke are left out.
    """
    fixed_inlet = replace(
        results.inputs, capture_area=results.capture_area, mdot_air=None, throat_area=None
    )
    machs = np.linspace(
        GrzywkaNozzleAnalysis.SWEEP_MACH_MIN,
        max(GrzywkaNozzleAnalysis.SWEEP_MACH_MAX, 1.25 * results.inputs.mach),
        GrzywkaNozzleAnalysis.SWEEP_POINTS,
    )
    points = []
    for m in machs:
        try:
            r = evaluate_sizing(replace(fixed_inlet, mach=float(m)))
        except ValueError:
            continue
        points.append(
            NozzleSizingPoint(
                mach=float(m),
                thrust_real=r.thrust_real,
                specific_impulse=r.specific_impulse,
                throat_diameter=r.throat_diameter,
                exit_diameter=r.exit_diameter,
                area_ratio=r.area_ratio,
            )
        )
    return points


def format_mach_sweep_csv(points: list[NozzleSizingPoint]) -> str:
    """CSV text of the sizing sweep."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(f.name for f in fields(NozzleSizingPoint))
    writer.writerows(astuple(p) for p in points)
    return buffer.getvalue()


def plot_mach_sweep(points: list[NozzleSizingPoint], results: GrzywkaCycleResults) -> Figure:
    """Plot thrust, specific impulse, nozzle diameters and area ratio against Mach.

    Args:
        points: Output of :func:`run_mach_sweep`.
        results: Results of the run, marked on each panel.

    Returns:
        The matplotlib Figure instance.
    """
    import matplotlib.pyplot as plt

    machs = [p.mach for p in points]
    run_mach = results.inputs.mach
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 8.0), sharex=True)

    ax = axes[0, 0]
    ax.plot(machs, [p.thrust_real for p in points], lw=2.0)
    ax.plot(run_mach, results.thrust_real, "o", color="k")
    ax.set_ylabel("Net thrust, real [N]")
    ax = axes[0, 1]
    ax.plot(machs, [p.specific_impulse for p in points], lw=2.0, color="tab:green")
    ax.plot(run_mach, results.specific_impulse, "o", color="k")
    ax.set_ylabel("Specific impulse [s]")
    ax = axes[1, 0]
    ax.plot(machs, [p.throat_diameter for p in points], lw=2.0, label="Throat")
    ax.plot(machs, [p.exit_diameter for p in points], lw=2.0, label="Exit")
    ax.set_ylabel("Diameter [m]")
    ax.legend(fontsize=8)
    ax = axes[1, 1]
    ax.plot(machs, [p.area_ratio for p in points], lw=2.0, color="tab:purple")
    ax.plot(run_mach, results.area_ratio, "o", color="k")
    ax.set_ylabel("Area ratio for full expansion A3/A21 [-]")

    for ax in axes.flat:
        ax.set_ylim(bottom=0.0)
        ax.grid(True, alpha=0.3)
    for ax in axes[1]:
        ax.set_xlabel("Flight Mach number [-]")
    fig.suptitle(
        f"Nozzle sized for full expansion, capture area {results.capture_area:.4f} m^2, "
        f"Tt4 = {results.inputs.tt4:.0f} K, {results.inputs.altitude:.0f} m"
    )
    fig.tight_layout()
    return fig


class GrzywkaNozzleAnalysis(BaseAnalysis[GrzywkaCycleResults]):
    """Combustor and fully expanded nozzle sized for the ramjet's design point.

    Example:
        analysis = GrzywkaNozzleAnalysis()
        analysis.setup(vehicle, capture_area=0.05)
        results = analysis.execute()
        exit_diameter = results.exit_diameter
    """

    fidelity = FidelityLevel.LEVEL_2

    DEFAULT_ALTITUDE_M: ClassVar[float] = HeiserPrattCycleAnalysis.DEFAULT_ALTITUDE_M

    #: Relative gap between the sized and the TOML nozzle area ratio that the run reports.
    AREA_RATIO_WARNING: ClassVar[float] = 0.10

    SWEEP_MACH_MIN: ClassVar[float] = 1.5
    SWEEP_MACH_MAX: ClassVar[float] = 4.0
    SWEEP_POINTS: ClassVar[int] = 26

    def __init__(self, name: str = "grzywka_nozzle") -> None:
        super().__init__(name)
        self._inputs: GrzywkaInputs | None = None
        self._assumed: tuple[str, ...] = ()
        self._toml_area_ratio: float | None = None

    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        engine_name: str | None = None,
        mach: float | None = None,
        altitude_m: float = DEFAULT_ALTITUDE_M,
        tt4: float | None = None,
        capture_area: float | None = None,
        mdot_air: float | None = None,
        eta_inlet: float | None = None,
        pi_cc: float | None = None,
        pi_nozzle: float | None = None,
        eta_b: float | None = None,
        gamma_hot: float | None = None,
        fuel_lhv: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Resolve the ramjet and build the sizing inputs.

        The air flow comes from ``capture_area`` or ``mdot_air``; with neither, it
        is the flow the ramjet's ``nozzle_throat_diameter`` passes when choked.

        Args:
            vehicle: Vehicle with a ramjet propulsion component.
            engine_name: Ramjet to use if the vehicle has more than one.
            mach: Flight Mach number. Defaults to ``design_mach``.
            altitude_m: ISA flight altitude [m].
            tt4: Combustor-exit total temperature [K]. Defaults to ``combustor_temp``.
            capture_area: Freestream capture area [m^2], full capture.
            mdot_air: Air mass flow [kg/s].
            eta_inlet: Inlet recovery. Defaults to ``inlet_recovery``, then a placeholder.
            pi_cc: Combustor total-pressure ratio. Defaults to
                ``combustor_pressure_ratio``, then a placeholder.
            pi_nozzle: Nozzle total-pressure ratio. Defaults to
                ``nozzle_pressure_ratio``, then a placeholder.
            eta_b: Combustion efficiency. Defaults to ``combustion_efficiency``, then
                a placeholder.
            gamma_hot: Ratio of specific heats of the products. Required unless the
                ramjet burns kerosene.
            fuel_lhv: Fuel lower heating value [J/kg]. Required unless the ramjet
                burns kerosene.
            **kwargs: Not accepted; present for the ``BaseAnalysis`` signature.

        Raises:
            TypeError: If an unknown setting is passed.
            ValueError: If the vehicle has no ramjet, the air flow or fuel properties
                are missing, or a setting is out of range.
        """
        if kwargs:
            raise TypeError(f"Unknown settings for '{self.name}': {sorted(kwargs)}")
        engine = vehicle.find_single_component(RAMJET_COMPONENTS, engine_name)
        defaults = HeiserPrattCycleAnalysis
        if engine.fuel_type.strip().lower() != defaults.DEFAULT_FUEL_TYPE and (
            gamma_hot is None or fuel_lhv is None
        ):
            raise ValueError(
                f"fuel_type='{engine.fuel_type}' has no default properties: "
                "pass both gamma_hot and fuel_lhv."
            )

        throat_area = None
        if capture_area is None and mdot_air is None:
            if engine.nozzle_throat_diameter is None:
                raise ValueError(
                    f"Vehicle '{vehicle.name}': set capture_area or mdot_air, or "
                    "nozzle_throat_diameter on the ramjet."
                )
            throat_area = math.pi / 4.0 * engine.nozzle_throat_diameter**2
            self._toml_area_ratio = engine.nozzle_area_ratio

        assumed: list[str] = []

        def resolve(override: float | None, value: float | None, label: str, default: float) -> float:
            if override is not None:
                return override
            if value is not None:
                return value
            assumed.append(label)
            return default

        self._inputs = GrzywkaInputs(
            mach=engine.design_mach if mach is None else mach,
            altitude=altitude_m,
            tt4=engine.combustor_temp if tt4 is None else tt4,
            eta_inlet=resolve(eta_inlet, engine.inlet_recovery, "inlet_recovery",
                              defaults.DEFAULT_ETA_INLET),
            pi_cc=resolve(pi_cc, engine.combustor_pressure_ratio, "combustor_pressure_ratio",
                          defaults.DEFAULT_PI_CC),
            pi_nozzle=resolve(pi_nozzle, engine.nozzle_pressure_ratio, "nozzle_pressure_ratio",
                              defaults.DEFAULT_PI_NOZZLE),
            eta_b=resolve(eta_b, engine.combustion_efficiency, "combustion_efficiency",
                          defaults.DEFAULT_ETA_B),
            gamma_hot=defaults.DEFAULT_GAMMA_HOT if gamma_hot is None else gamma_hot,
            gamma_cold=const.GAMMA_AIR,
            fuel_lhv=const.LHV_KEROSENE if fuel_lhv is None else fuel_lhv,
            capture_area=capture_area,
            mdot_air=mdot_air,
            throat_area=throat_area,
        )
        self._assumed = tuple(assumed)
        self.logger.info(
            "Configured nozzle sizing for vehicle '%s' (M=%.2f, h=%.0f m, Tt4=%.0f K)",
            vehicle.name,
            self._inputs.mach,
            self._inputs.altitude,
            self._inputs.tt4,
        )
        if assumed:
            self.logger.warning("Placeholder values used for: %s", ", ".join(assumed))

    def _compute(self, **kwargs: Any) -> GrzywkaCycleResults:
        """Size the nozzle at the configured flight condition."""
        if self._inputs is None:
            raise RuntimeError(f"Analysis '{self.name}' must be setup before computation.")
        results = evaluate_sizing(self._inputs, name=self.name, fidelity=self.fidelity)
        notes: list[str] = []
        toml_ratio = self._toml_area_ratio
        if toml_ratio is not None and abs(toml_ratio / results.area_ratio - 1.0) > self.AREA_RATIO_WARNING:
            state = "underexpands" if toml_ratio < results.area_ratio else "overexpands"
            notes.append(
                f"The ramjet's nozzle_area_ratio {toml_ratio:g} {state} the flow here; full "
                f"expansion needs {results.area_ratio:.2f}."
            )
        results = replace(results, assumed_losses=self._assumed, notes=tuple(notes))
        self.logger.info(
            "Thrust ideal/cc/real = %.0f/%.0f/%.0f N, throat %.4f m, exit %.4f m (A3/A21 = %.3f)",
            results.thrust_ideal,
            results.thrust_cc_loss,
            results.thrust_real,
            results.throat_diameter,
            results.exit_diameter,
            results.area_ratio,
        )
        return results

    def validate_results(self, results: GrzywkaCycleResults) -> bool:
        """Check finite values, a supersonic exit and that every loss lowers thrust.

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        if not all(math.isfinite(v) for v in results.scalars().values()):
            return False
        if results.fuel_air_ratio <= 0.0 or results.mach_exit < 1.0 or results.area_ratio < 1.0:
            return False
        return results.thrust_real <= results.thrust_cc_loss <= results.thrust_ideal
