"""Eq. (10), (11), (5), (9) by hand, the manuscript's evaporation demand (p. 20), invalid inputs."""
import pytest

from process_models import PROCESSES, run_process

KEY = "conductive_drying"
# manuscript p. 18 / 20: paper drying, 30,000 kg/h, 50 % -> 7.5 %, air 106,250 kg/h at 15 degC, 6.43 g/kg, T2 70, T3 25
PAPER = dict(product_flow_kg_h=30000, w_in=0.5, w_out=0.075, T_surface=135, T_product_in=15, cp_wet=2.7,
             air_flow_kg_h=106250, T1=15, x1_g_kg=6.43, T2=70, T_return=25)


def test_registered():
    assert KEY in PROCESSES


def test_equations_by_hand():
    r, _ = run_process(KEY, **PAPER)
    m = 30000 / 3600
    assert r.Q_sensible == pytest.approx(m * 2.7 * 120)                                  # Eq. (10)
    assert r.Q_latent_heating == pytest.approx(m * 0.425 * (2501 - 2.37 * 135))          # Eq. (11)
    assert r.x2 == pytest.approx(0.00643 + m * 0.425 / (106250 / 3600))                  # Eq. (5)
    assert r.Q_cooling == pytest.approx(r.Q_dew + r.Q_latent)                            # Eq. (9)


def test_manuscript_evaporation_demand():
    # p. 20: "The evaporation energy demand is calculated as 7,724 kW" (surface at 135 degC, read from Fig. 12)
    r, _ = run_process(KEY, **PAPER)
    assert r.Q_latent_heating == pytest.approx(7724, abs=1)


def test_streams_carry_the_demand():
    r, _ = run_process(KEY, **PAPER)
    st = r.stream_table()
    assert sum(s["Q_kW"] for s in st if s["type"] == "cold") == pytest.approx(r.Q_heating)
    assert sum(s["Q_kW"] for s in st if s["type"] == "hot") == pytest.approx(r.Q_cooling)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        run_process(KEY, **{**PAPER, "T_product_in": 150})     # product hotter than the surface
    with pytest.raises(ValueError):
        run_process(KEY, **{**PAPER, "air_flow_kg_h": 2000})   # too little air: supersaturated outlet
