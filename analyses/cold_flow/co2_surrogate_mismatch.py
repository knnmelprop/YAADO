# MELprop-IADE | analyses.cold_flow.co2_surrogate_mismatch | v0.1.0
"""CO2-surrogate vs reacting-kerosene mixing mismatch (screening calc).

Stage 4 of the 2026-07-11 RamP rerun (research finding Section 5). Cold-flow
CO2 + optical (Schlieren / tracer) tests verify **shock structure and gross
total-pressure recovery** well, but they do NOT reproduce the mixing behavior
of the reacting kerosene-air flow. This module quantifies WHY, so the
limitation is documented as a number rather than asserted.

The governing similarity parameters for a jet in a supersonic crossflow are the
**density ratio** and the **jet-to-crossflow momentum-flux ratio**

    J = (rho_jet * u_jet^2) / (rho_cross * u_cross^2),

which set jet penetration and large-scale mixing. A cold CO2 surrogate and the
hot reacting products sit at opposite ends of the density scale (cold dense gas
vs hot light combustion products), so matching one similarity parameter forces a
large mismatch in the other. Numbers below are screening estimates, not a
validated mixing model.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Universal-ish specific gas constants [J/(kg*K)].
R_AIR: float = 287.05
R_CO2: float = 188.9
#: Kerosene-air combustion products (mostly N2/CO2/H2O); near air's molar mass.
R_PRODUCTS: float = 287.0


@dataclass
class StreamState:
    """A gas stream state for the mismatch calc.

    Attributes:
        name: Label.
        temperature_K: Static temperature [K].
        pressure_Pa: Static pressure [Pa].
        gas_constant: Specific gas constant [J/(kg*K)].
        velocity_m_s: Bulk velocity [m/s].
    """

    name: str
    temperature_K: float
    pressure_Pa: float
    gas_constant: float
    velocity_m_s: float

    @property
    def density_kg_m3(self) -> float:
        """Ideal-gas density [kg/m^3]."""
        return self.pressure_Pa / (self.gas_constant * self.temperature_K)

    @property
    def momentum_flux(self) -> float:
        """Momentum flux rho*u^2 [Pa]."""
        return self.density_kg_m3 * self.velocity_m_s ** 2


def compare(
    crossflow: StreamState, surrogate: StreamState, reacting: StreamState
) -> dict[str, float]:
    """Compare surrogate vs reacting injectant against a common crossflow.

    Args:
        crossflow: The combustor air crossflow.
        surrogate: The cold CO2 surrogate jet (same injection velocity).
        reacting: The hot reacting-products jet (same injection velocity).

    Returns:
        Dict of density ratios, momentum-flux ratios J, and their mismatch.
    """
    j_surrogate = surrogate.momentum_flux / crossflow.momentum_flux
    j_reacting = reacting.momentum_flux / crossflow.momentum_flux
    return {
        "rho_crossflow": crossflow.density_kg_m3,
        "rho_surrogate_co2": surrogate.density_kg_m3,
        "rho_reacting_products": reacting.density_kg_m3,
        "density_ratio_surrogate_over_reacting": surrogate.density_kg_m3 / reacting.density_kg_m3,
        "J_surrogate": j_surrogate,
        "J_reacting": j_reacting,
        "momentum_flux_ratio_mismatch": j_surrogate / j_reacting,
    }


def representative_case() -> dict[str, float]:
    """A representative combustor-injection screening comparison.

    PROVISIONAL conditions (source: RamP cycle station 2, ~350 kPa; injectant
    velocity 150 m/s assumed equal for both jets to isolate the density effect;
    replace when the injector schedule and combustor static state are confirmed).

    Returns:
        The :func:`compare` result dict for the representative case.
    """
    p = 350_000.0
    u_jet = 150.0
    crossflow = StreamState("combustor_air", 560.0, p, R_AIR, 120.0)
    # Cold CO2 surrogate, injected near ambient temperature.
    surrogate = StreamState("cold_CO2", 300.0, p, R_CO2, u_jet)
    # Hot reacting kerosene-air products near the flame.
    reacting = StreamState("hot_products", 2200.0, p, R_PRODUCTS, u_jet)
    return compare(crossflow, surrogate, reacting)


def main() -> dict[str, float]:
    """Print the representative screening comparison."""
    res = representative_case()
    print("CO2-surrogate vs reacting-kerosene mixing mismatch (screening):")
    for k, v in res.items():
        print(f"  {k:42s} = {v:10.3f}")
    print(
        f"\n  => cold CO2 is ~{res['density_ratio_surrogate_over_reacting']:.0f}x denser than the "
        f"hot products; its momentum-flux ratio J is\n     ~"
        f"{res['momentum_flux_ratio_mismatch']:.0f}x the reacting value at equal injection "
        f"velocity -> penetration/mixing NOT representative."
    )
    return res


if __name__ == "__main__":
    main()
