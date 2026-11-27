"""Eq. (20)/(21) by hand, the energy balance, the w / evaporated-flow alternative and invalid inputs.

The manuscript gives no inputs for its distillation validation case, so there is no worked example to check against.
"""
import pytest

from process_models import PROCESSES, run_process

KEY = "thermal_phase_change"
BASE = dict(mass_flow_kg_h=3600, T_in=20, T_v=90, T_out=30, cp_residue=4.0, w=0.25, cp_evaporated=2.0, h_v=800)


def test_registered():
    assert KEY in PROCESSES


def test_equations_by_hand():
    r, _ = run_process(KEY, **BASE)            # m = 1 kg/s
    assert r.Q_heating == pytest.approx(0.25 * (800 + 2.0 * 70) + 0.75 * 4.0 * 70)   # Eq. (20): 445 kW
    assert r.Q_cooling == pytest.approx(0.25 * (800 + 2.0 * 60) + 0.75 * 4.0 * 60)   # Eq. (21): 410 kW


def test_energy_balance_and_streams():
    r, _ = run_process(KEY, **BASE)
    # heating - cooling = liquid heat capacity flow * (T_out - T_in)
    assert r.Q_heating - r.Q_cooling == pytest.approx(r.CP_liquid * (BASE["T_out"] - BASE["T_in"]))
    streams = r.stream_table()
    assert sum(s["Q_kW"] for s in streams if s["type"] == "cold") == pytest.approx(r.Q_heating)
    assert sum(s["Q_kW"] for s in streams if s["type"] == "hot") == pytest.approx(r.Q_cooling)
    assert all(s["T_supply_degC"] != s["T_target_degC"] for s in streams)


def test_evaporated_flow_instead_of_w():
    inp = {k: v for k, v in BASE.items() if k != "w"}
    r, _ = run_process(KEY, **inp, evaporated_flow_kg_h=900)
    r_w, _ = run_process(KEY, **BASE)
    assert r.Q_heating == pytest.approx(r_w.Q_heating)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        run_process(KEY, **{**BASE, "T_in": 95})          # feed above the boiling temperature
    with pytest.raises(ValueError):
        run_process(KEY, **{**BASE, "w": None})           # neither w nor the evaporated mass flow
    with pytest.raises(ValueError):
        run_process(KEY, **BASE, evaporated_flow_kg_h=500)  # w and evaporated flow disagree
