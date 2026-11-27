"""Worked example of the manuscript validation (pasteurization): 3135 kg/h, cp 3.89 kJ/(kg K), 4 -> 90 -> 4 degC gives 291.3 kW."""
import pytest

from process_models import PROCESSES, run_process

KEY = "continuous_heating_of_fluid"


def test_registered():
    assert KEY in PROCESSES


def test_manuscript_example():
    r, _ = run_process(KEY, mass_flow_kg_h=3000 * 1.045, T_in=4, T_process=90, T_out=4)
    assert r.Q_heating == pytest.approx(291.3, abs=0.05)
    assert r.Q_cooling == pytest.approx(r.Q_heating)
    cold, hot = r.stream_table()
    assert (cold["type"], cold["T_supply_degC"], cold["T_target_degC"]) == ("cold", 4, 90)
    assert (hot["type"], hot["T_supply_degC"], hot["T_target_degC"]) == ("hot", 90, 4)


def test_losses_raise_heating_lower_cooling():
    base = dict(mass_flow_kg_h=1000, T_in=10, T_process=85, T_out=20, cp=3.9)
    r, _ = run_process(KEY, **base)
    r_loss, _ = run_process(KEY, **base, loss_area=5, U_value=2)
    assert r_loss.Q_heating > r.Q_heating and r_loss.Q_cooling < r.Q_cooling


def test_invalid_temperatures():
    with pytest.raises(ValueError):
        run_process(KEY, mass_flow_kg_h=1000, T_in=90, T_process=4, T_out=4)
    with pytest.raises(ValueError):
        run_process(KEY, mass_flow_kg_h=1000, T_in=4, T_out=4)  # T_process missing
