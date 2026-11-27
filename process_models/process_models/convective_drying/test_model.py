"""Eq. (3)-(9) by hand and against the manuscript's spray dryer inputs (p. 17), losses, invalid inputs."""
import pytest

from process_models import PROCESSES, humid_air as ha, run_process

KEY = "convective_drying"
# manuscript p. 17: air 55.7 kg/s, T0 15, x0 6.43 g/kg, T1 210, water removed 1.6 kg/s (product split arbitrary)
SPRAY = dict(product_flow_kg_h=1.6 * 3600 / 0.5, w1=0.55, w2=0.05, air_flow_kg_h=55.7 * 3600,
             T0=15, T1=210, x0_g_kg=6.43)


def test_registered():
    assert KEY in PROCESSES


def test_humid_air():
    assert ha.dew_point(ha.x_sat(40.0)) == pytest.approx(40.0)
    assert ha.enthalpy(20, 0.01) == pytest.approx(1.006 * 20 + 0.01 * (2501 + 1.86 * 20))


def test_spray_dryer_inputs():
    r, _ = run_process(KEY, **SPRAY)
    assert r.Q_heating == pytest.approx(55.7 * (1.006 + 0.00643 * 1.86) * 195)        # Eq. (3)
    assert r.x2 == pytest.approx(0.00643 + 1.6 / 55.7)                                  # Eq. (4), (5)
    assert ha.enthalpy(r.T2, r.x2) == pytest.approx(r.h1)                                # Eq. (6), no losses: isenthalpic
    assert r.Q_cooling == pytest.approx(r.Q_dew + r.Q_latent)                            # Eq. (9)
    assert sum(s["Q_kW"] for s in r.stream_table() if s["type"] == "hot") == pytest.approx(r.Q_cooling)


def test_losses_lower_outlet_temperature():
    r, _ = run_process(KEY, **SPRAY)
    r_loss, _ = run_process(KEY, **SPRAY, UA_W_K=20000)
    assert r_loss.T2 < r.T2 and r_loss.Q_heating == pytest.approx(r.Q_heating)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        run_process(KEY, **{**SPRAY, "w2": 0.6})            # final moisture above initial
    with pytest.raises(ValueError):
        run_process(KEY, **{**SPRAY, "air_flow_kg_h": 5000})  # far too little air: supersaturated outlet
    with pytest.raises(ValueError, match="finite"):
        run_process(KEY, **{**SPRAY, "air_flow_kg_h": float("nan")})  # NaN must not slip through the checks
