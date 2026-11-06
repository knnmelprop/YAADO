"""Heiser & Pratt ramjet station cycle with separate cold and hot gas properties.

Calorically perfect, two-gas, 1-D station model:

    0 -> freestream (ISA, cold gamma).
    2 -> diffuser exit. Adiabatic, ``Tt2 = Tt0``, ``pt2 = eta_inlet * pt0``.
    4 -> combustor exit. ``pt4 = pi_cc * pt2``. Gamma switches to the hot value.
    e -> nozzle exit. The throat is choked and the exit Mach follows from the
         finite nozzle area ratio, so the exit pressure is generally not ambient
         and a pressure-thrust term ``(p_e - p0) * A_e`` is kept.

Three thrust models are always reported, all at the same mass flow:

    thrust_ideal   -- no combustor or nozzle total-pressure loss.
    thrust_cc_loss -- combustor loss only.
    thrust_real    -- both losses. Nominal for downstream use.

The nozzle loss lowers the exit pressure only, so the exit velocity is the same
in all three models.
"""

from __future__ import annotations

import math
from typing import Any

from scipy.optimize import brentq

import YAADO_Core.Foundation.constants as const
from YAADO_Core.ComponentStore import RAMJET_COMPONENTS
from YAADO_Core.Foundation.analysis_base import BaseAnalysis, FidelityLevel
from YAADO_Core.Foundation.atmosphere import isa_atmosphere
from YAADO_Core.Foundation.vehicle_base import BaseVehicleConfig
from YAADO_Core.modules.powerplant.containers import (
    HeiserPrattInputs,
    HeiserPrattResults,
    NozzleExpansion,
)

#: Gas constant of the products [J/(kg*K)]. Equal to air: the mean molar mass of
#: near-stoichiometric kerosene-air products differs from air by less than 1 %.
R_PRODUCTS: float = const.R_AIR

#: Upper bracket of the supersonic area-Mach root search [-].
_MACH_SEARCH_MAX: float = 50.0


def area_ratio_from_mach(mach: float, gamma: float) -> float:
    """Isentropic area ratio ``A/A*`` for a given Mach and gamma.

    Args:
        mach: Local Mach number (> 0).
        gamma: Ratio of specific heats.

    Returns:
        ``A/A*`` [-].
    """
    g = gamma
    return (1.0 / mach) * (
        (2.0 / (g + 1.0)) * (1.0 + 0.5 * (g - 1.0) * mach * mach)
    ) ** ((g + 1.0) / (2.0 * (g - 1.0)))


def supersonic_mach_from_area_ratio(area_ratio: float, gamma: float) -> float:
    """Supersonic Mach number for a given isentropic area ratio ``A/A*``.

    Args:
        area_ratio: ``A/A*`` (>= 1).
        gamma: Ratio of specific heats.

    Returns:
        Supersonic Mach number [-].

    Raises:
        ValueError: If ``area_ratio < 1`` (no supersonic solution).
    """
    if area_ratio < 1.0:
        raise ValueError(f"area_ratio {area_ratio} < 1: no supersonic solution")
    if math.isclose(area_ratio, 1.0, rel_tol=1e-9):
        return 1.0
    return brentq(
        lambda m: area_ratio_from_mach(m, gamma) - area_ratio,
        1.0 + 1e-9,
        _MACH_SEARCH_MAX,
        xtol=1e-10,
    )


def choked_mass_flux(pt: float, tt: float, gamma: float, r_gas: float) -> float:
    """Mass flow per unit throat area for choked (Ma = 1) flow.

    Args:
        pt: Total pressure at the throat [Pa].
        tt: Total temperature at the throat [K].
        gamma: Ratio of specific heats.
        r_gas: Specific gas constant [J/(kg*K)].

    Returns:
        Mass flux [kg/(s*m^2)].
    """
    g = gamma
    return pt * math.sqrt(g / (r_gas * tt)) * (2.0 / (g + 1.0)) ** ((g + 1.0) / (2.0 * (g - 1.0)))


def _expand_nozzle(
    inputs: HeiserPrattInputs,
    mdot_air: float,
    mdot_exit: float,
    v0: float,
    p0: float,
    pt_throat: float,
    pt_exit: float,
) -> NozzleExpansion:
    """Expand the products through the nozzle for one total-pressure loss model."""
    gh = inputs.gamma_hot
    a_throat = mdot_exit / choked_mass_flux(pt_throat, inputs.tt4, gh, R_PRODUCTS)
    a_exit = inputs.nozzle_area_ratio * a_throat
    mach_exit = supersonic_mach_from_area_ratio(inputs.nozzle_area_ratio, gh)
    stagnation_ratio = 1.0 + 0.5 * (gh - 1.0) * mach_exit**2
    t_exit = inputs.tt4 / stagnation_ratio
    p_exit = pt_exit / stagnation_ratio ** (gh / (gh - 1.0))
    v_exit = mach_exit * math.sqrt(gh * R_PRODUCTS * t_exit)
    return NozzleExpansion(
        mach_exit=mach_exit,
        t_exit=t_exit,
        p_exit=p_exit,
        v_exit=v_exit,
        a_throat=a_throat,
        a_exit=a_exit,
        momentum_thrust=mdot_exit * v_exit - mdot_air * v0,
        pressure_thrust=(p_exit - p0) * a_exit,
    )


def evaluate_cycle(
    inputs: HeiserPrattInputs,
    name: str = "heiser_pratt_cycle",
    fidelity: FidelityLevel = FidelityLevel.LEVEL_2,
) -> HeiserPrattResults:
    """Evaluate the ramjet cycle at one flight condition.

    Args:
        inputs: Flight condition, losses, nozzle geometry and gas properties.
        name: Analysis name stored on the results.
        fidelity: Fidelity level stored on the results.

    Returns:
        Exit state and the three thrust models.

    Raises:
        ValueError: If ``tt4`` does not exceed ``Tt0`` or the burner energy
            balance has no solution.
    """
    gc = inputs.gamma_cold
    gh = inputs.gamma_hot

    atmosphere = isa_atmosphere(inputs.altitude)
    t0 = atmosphere.temperature
    p0 = atmosphere.pressure
    v0 = inputs.mach * math.sqrt(gc * const.R_AIR * t0)
    stagnation_ratio = 1.0 + 0.5 * (gc - 1.0) * inputs.mach**2
    tt0 = t0 * stagnation_ratio
    pt0 = p0 * stagnation_ratio ** (gc / (gc - 1.0))
    if inputs.tt4 <= tt0:
        raise ValueError(f"tt4={inputs.tt4} K must exceed the recovered total temperature {tt0:.1f} K")

    pt2 = inputs.eta_inlet * pt0
    pt4 = inputs.pi_cc * pt2

    # Fuel-air ratio from the burner energy balance.
    cp_cold = gc * const.R_AIR / (gc - 1.0)
    cp_hot = gh * R_PRODUCTS / (gh - 1.0)
    burner_margin = inputs.eta_b * inputs.fuel_lhv - cp_hot * inputs.tt4
    if burner_margin <= 0.0:
        raise ValueError(
            f"tt4={inputs.tt4} K is not reachable with eta_b * fuel_lhv = "
            f"{inputs.eta_b * inputs.fuel_lhv:.3e} J/kg"
        )
    fuel_air_ratio = (cp_hot * inputs.tt4 - cp_cold * tt0) / burner_margin

    if inputs.mdot_air is not None:
        mdot_air = inputs.mdot_air
    else:
        assert inputs.throat_area is not None  # guaranteed by HeiserPrattInputs
        mdot_air = (
            choked_mass_flux(pt4, inputs.tt4, gh, R_PRODUCTS)
            * inputs.throat_area
            / (1.0 + fuel_air_ratio)
        )
    mdot_exit = mdot_air * (1.0 + fuel_air_ratio)

    real = _expand_nozzle(inputs, mdot_air, mdot_exit, v0, p0, pt4, inputs.pi_nozzle * pt4)
    cc_loss = _expand_nozzle(inputs, mdot_air, mdot_exit, v0, p0, pt4, pt4)
    ideal = _expand_nozzle(inputs, mdot_air, mdot_exit, v0, p0, pt2, pt2)

    return HeiserPrattResults(
        name=name,
        fidelity=fidelity,
        inputs=inputs,
        t0=t0,
        p0=p0,
        v0=v0,
        tt0=tt0,
        pt0=pt0,
        pt2=pt2,
        pt4=pt4,
        fuel_air_ratio=fuel_air_ratio,
        mdot_air=mdot_air,
        mdot_exit=mdot_exit,
        capture_area=mdot_air / (atmosphere.density * v0),
        mach_exit=real.mach_exit,
        t_exit=real.t_exit,
        p_exit=real.p_exit,
        v_exit=real.v_exit,
        a_throat=real.a_throat,
        a_exit=real.a_exit,
        p_exit_over_p0=real.p_exit / p0,
        underexpanded=real.p_exit > p0,
        thrust_ideal=ideal.thrust,
        thrust_cc_loss=cc_loss.thrust,
        thrust_real=real.thrust,
        momentum_thrust=real.momentum_thrust,
        pressure_thrust=real.pressure_thrust,
    )


class HeiserPrattCycleAnalysis(BaseAnalysis[HeiserPrattResults]):
    """Ramjet cycle performance at the engine's design point.

    Mach, combustor temperature and nozzle geometry come from the vehicle's ramjet
    component. Mass flow follows from its choked throat, which assumes the inlet
    can supply that flow; check ``capture_area`` against the real inlet.

    Example:
        analysis = HeiserPrattCycleAnalysis()
        analysis.setup(vehicle, altitude_m=12000.0)
        results = analysis.execute()
        thrust = results.thrust_real
    """

    fidelity = FidelityLevel.LEVEL_2

    DEFAULT_ALTITUDE_M: float = 10000.0

    # Placeholder losses until the vehicle schema and an inlet analysis provide them.
    DEFAULT_ETA_INLET: float = 0.874
    DEFAULT_PI_CC: float = 0.8924
    DEFAULT_PI_NOZZLE: float = 0.97
    DEFAULT_ETA_B: float = 0.95

    #: Kerosene-air products at 2000-2400 K. Replace with a NASA-CEA value.
    DEFAULT_GAMMA_HOT: float = 1.28

    #: Fuel the default ``gamma_hot`` and ``fuel_lhv`` apply to.
    DEFAULT_FUEL_TYPE: str = "kerosene"

    def __init__(self, name: str = "heiser_pratt_cycle") -> None:
        super().__init__(name)
        self._inputs: HeiserPrattInputs | None = None

    def _setup(
        self,
        vehicle: BaseVehicleConfig,
        *,
        engine_name: str | None = None,
        mach: float | None = None,
        altitude_m: float = DEFAULT_ALTITUDE_M,
        tt4: float | None = None,
        mdot_air: float | None = None,
        eta_inlet: float = DEFAULT_ETA_INLET,
        pi_cc: float = DEFAULT_PI_CC,
        pi_nozzle: float = DEFAULT_PI_NOZZLE,
        eta_b: float = DEFAULT_ETA_B,
        gamma_hot: float | None = None,
        gamma_cold: float = const.GAMMA_AIR,
        fuel_lhv: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Resolve the ramjet and build the cycle inputs.

        Args:
            vehicle: Vehicle configuration with a ramjet propulsion component.
            engine_name: Ramjet to use if the vehicle has more than one.
            mach: Flight Mach number. Defaults to the engine's ``design_mach``.
            altitude_m: ISA flight altitude [m].
            tt4: Combustor-exit total temperature [K]. Defaults to the engine's
                ``combustor_temp``.
            mdot_air: Air mass flow [kg/s]. Replaces the flow set by the choked
                ``nozzle_throat_diameter``.
            eta_inlet: Inlet total-pressure recovery.
            pi_cc: Combustor total-pressure ratio.
            pi_nozzle: Nozzle total-pressure ratio.
            eta_b: Combustion efficiency.
            gamma_hot: Ratio of specific heats of the products. Required unless
                the engine burns kerosene.
            gamma_cold: Ratio of specific heats of the inlet air.
            fuel_lhv: Fuel lower heating value [J/kg]. Required unless the engine
                burns kerosene.
            **kwargs: Not accepted; present for the ``BaseAnalysis`` signature.

        Raises:
            TypeError: If an unknown setting is passed.
            ValueError: If the vehicle has no ramjet or several without
                ``engine_name``, if the mass flow cannot be resolved, if the fuel
                properties are missing, or if an input is out of range.
        """
        if kwargs:
            raise TypeError(f"Unknown settings for '{self.name}': {sorted(kwargs)}")

        engine = vehicle.find_single_component(RAMJET_COMPONENTS, engine_name)

        is_default_fuel = engine.fuel_type.strip().lower() == self.DEFAULT_FUEL_TYPE
        if not is_default_fuel and (gamma_hot is None or fuel_lhv is None):
            raise ValueError(
                f"fuel_type='{engine.fuel_type}' has no default properties: "
                "pass both gamma_hot and fuel_lhv."
            )

        throat_area = None
        if mdot_air is None:
            if engine.nozzle_throat_diameter is None:
                raise ValueError(
                    f"Vehicle '{vehicle.name}': set nozzle_throat_diameter on the "
                    "ramjet or pass mdot_air to fix the air mass flow."
                )
            throat_area = math.pi / 4.0 * engine.nozzle_throat_diameter**2

        self._inputs = HeiserPrattInputs(
            mach=engine.design_mach if mach is None else mach,
            altitude=altitude_m,
            tt4=engine.combustor_temp if tt4 is None else tt4,
            nozzle_area_ratio=engine.nozzle_area_ratio,
            eta_inlet=eta_inlet,
            pi_cc=pi_cc,
            pi_nozzle=pi_nozzle,
            eta_b=eta_b,
            gamma_hot=self.DEFAULT_GAMMA_HOT if gamma_hot is None else gamma_hot,
            gamma_cold=gamma_cold,
            fuel_lhv=const.LHV_KEROSENE if fuel_lhv is None else fuel_lhv,
            mdot_air=mdot_air,
            throat_area=throat_area,
        )
        self.logger.info(
            "Configured ramjet cycle for vehicle '%s' (M=%.2f, h=%.0f m, Tt4=%.0f K, AR=%.3f)",
            vehicle.name,
            self._inputs.mach,
            self._inputs.altitude,
            self._inputs.tt4,
            self._inputs.nozzle_area_ratio,
        )

    def _compute(self, **kwargs: Any) -> HeiserPrattResults:
        """Evaluate the cycle and return typed results."""
        if self._inputs is None:
            raise RuntimeError(
                f"Analysis '{self.name}' must be setup before computation. Call setup() first."
            )

        results = evaluate_cycle(self._inputs, name=self.name, fidelity=self.fidelity)
        self.logger.info(
            "Thrust ideal/cc-loss/real = %.0f/%.0f/%.0f N, mdot_air=%.2f kg/s, f=%.4f, "
            "M_exit=%.3f, V_exit=%.0f m/s, p_exit/p0=%.2f, capture_area=%.4f m^2",
            results.thrust_ideal,
            results.thrust_cc_loss,
            results.thrust_real,
            results.mdot_air,
            results.fuel_air_ratio,
            results.mach_exit,
            results.v_exit,
            results.p_exit_over_p0,
            results.capture_area,
        )
        return results

    def validate_results(self, results: HeiserPrattResults) -> bool:
        """Sanity-check the cycle against physical bounds.

        Checks that all scalars are finite, that fuel is burned, that the nozzle
        exit is supersonic, and that adding a loss never increases thrust.

        Args:
            results: Results produced by :meth:`execute`.

        Returns:
            True if all checks pass.
        """
        if not all(math.isfinite(value) for value in results.scalars().values()):
            return False
        if results.fuel_air_ratio <= 0.0 or results.mach_exit < 1.0:
            return False
        return results.thrust_real <= results.thrust_cc_loss <= results.thrust_ideal
