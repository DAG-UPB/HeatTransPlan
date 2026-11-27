"""Eq. (15)-(17) by hand, the utility return temperature, invalid inputs.

The manuscript gives no inputs for its bath heating case (1,142.37 kW), so there is no worked example.
"""
import pytest

from process_models import PROCESSES, run_process

KEY = "continuous_bath_heating"
BASE = dict(product_flow_kg_h=3600, cp_product=0.5, T_product_in=20, T_bath=170, A_surface=20, A_wall=60,
            U_bath=0.5, T_amb=20, alpha=10)


def test_registered():
    assert KEY in PROCESSES


def test_equations_by_hand():
    r, _ = run_process(KEY, **BASE, emissivity=0.9)
    assert r.Q_product == pytest.approx(1 * 0.5 * 150)                                            # Eq. (15)
    assert r.Q_trans == pytest.approx(0.5 * 60 * 150 / 1000)                                      # Eq. (16)
    rad = 0.9 * 5.67e-8 * 20 * (443.15 ** 4 - 293.15 ** 4) / 1000
    assert r.Q_surface == pytest.approx(10 * 20 * 150 / 1000 + rad)                               # Eq. (17)
    assert r.Q_heating == pytest.approx(r.Q_product + r.Q_trans + r.Q_surface)
    assert r.stream_table()[0]["Q_kW"] == pytest.approx(r.Q_heating)


def test_utility_return():
    r, _ = run_process(KEY, **BASE, utility_flow_kg_h=10000, T_utility_in=200)
    assert r.T_utility_out == pytest.approx(200 - r.Q_heating / (10000 / 3600 * 4.18))


def test_invalid_inputs():
    with pytest.raises(ValueError):
        run_process(KEY, **{**BASE, "T_product_in": 200})     # product hotter than the bath
    with pytest.raises(ValueError):
        run_process(KEY, **BASE, emissivity=1.5)
