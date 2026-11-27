"""Eq. (12)-(14) by hand, losses, phase vs cycle duty, invalid inputs.

The manuscript gives no inputs for its batch sterilization case (62.65 MJ), so there is no worked example.
"""
import pytest

from process_models import PROCESSES, run_process

KEY = "autoclaving"
BASE = dict(m_product=500, cp_product=3.6, m_packaging=100, m_autoclave=1500, T_start=20, T_steri=121,
            T_final=40, t_heating_min=20, t_holding_min=15, t_cooling_min=20)


def test_registered():
    assert KEY in PROCESSES


def test_equations_by_hand():
    r, _ = run_process(KEY, **BASE, loss_area=10, U_value=2)
    C = 500 * 3.6 + 100 * 0.5 + 1500 * 0.5
    assert r.Q_heating == pytest.approx(C * 101 / 1200 + 10 * 2 * (70.5 - 20) / 1000)      # Eq. (12)
    assert r.Q_cooling == pytest.approx(C * 81 / 1200 - 10 * 2 * (80.5 - 20) / 1000)       # Eq. (13)
    assert r.Q_holding == pytest.approx(10 * 2 * 101 / 1000)                              # Eq. (14)


def test_cycle_basis_spreads_the_batch_energy():
    r, _ = run_process(KEY, **BASE, duty_basis="cycle")
    heating = r.stream_table()[0]
    assert heating["Q_kW"] == pytest.approx(r.E_heating_MJ * 1000 / (55 * 60))
    assert heating["Q_kW"] < r.Q_heating


def test_losses_raise_heating_lower_cooling():
    r, _ = run_process(KEY, **BASE)
    r_loss, _ = run_process(KEY, **BASE, loss_area=10, U_value=2)
    assert r_loss.Q_heating > r.Q_heating and r_loss.Q_cooling < r.Q_cooling and r_loss.Q_holding > 0


def test_invalid_inputs():
    with pytest.raises(ValueError):
        run_process(KEY, **{**BASE, "T_final": 130})       # cooled to above the sterilization temperature
    with pytest.raises(ValueError):
        run_process(KEY, **{**BASE, "t_heating_min": 0})
