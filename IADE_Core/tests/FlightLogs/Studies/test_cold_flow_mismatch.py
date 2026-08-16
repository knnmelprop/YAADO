# MELprop-IADE | tests.unit.test_cold_flow_mismatch | v0.1.0
"""Stage 4 test: CO2-surrogate vs reacting-kerosene mixing mismatch calc."""

from __future__ import annotations

from FlightLogs.Studies.co2_surrogate_mismatch import StreamState, representative_case


def test_surrogate_denser_than_reacting_products() -> None:
    """Cold CO2 surrogate is much denser than the hot reacting products."""
    res = representative_case()
    assert res["rho_surrogate_co2"] > res["rho_reacting_products"]
    assert res["density_ratio_surrogate_over_reacting"] > 5.0


def test_momentum_flux_ratio_large_mismatch() -> None:
    """The surrogate/reacting momentum-flux-ratio mismatch is order 10x."""
    res = representative_case()
    assert res["momentum_flux_ratio_mismatch"] > 5.0


def test_streamstate_ideal_gas() -> None:
    """StreamState density and momentum flux follow the ideal-gas relations."""
    s = StreamState("t", 300.0, 300000.0, 287.05, 100.0)
    assert abs(s.density_kg_m3 - 300000.0 / (287.05 * 300.0)) < 1e-9
    assert abs(s.momentum_flux - s.density_kg_m3 * 100.0 ** 2) < 1e-6
