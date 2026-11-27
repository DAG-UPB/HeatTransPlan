"""Moist air as an ideal gas mixture, for the drying models (manuscript Eq. (3), (5)-(9)).

Temperatures in degC, absolute humidity x in kg water / kg dry air, enthalpy in kJ / kg dry air.
The constants are the usual textbook values, not from the manuscript; the manuscript's Eq. (6) uses the same
three (cp,air, cp,vapor, h_v,water).
"""
from __future__ import annotations

import math

CP_AIR = 1.006      # kJ/(kg K), dry air
CP_VAPOR = 1.86     # kJ/(kg K), water vapour
H_V0 = 2501.0       # kJ/kg, evaporation enthalpy of water at 0 degC
P_ATM = 101325.0    # Pa


def enthalpy(T: float, x: float) -> float:
    """h(T, x) = cp_air*T + x*(h_v0 + cp_vapor*T)  [kJ/kg dry air]."""
    return CP_AIR * T + x * (H_V0 + CP_VAPOR * T)


def p_sat(T: float) -> float:
    """Saturation pressure of water [Pa], Magnus formula (good from -45 to about 100 degC)."""
    return 611.2 * math.exp(17.62 * T / (243.12 + T))


def x_sat(T: float, p: float = P_ATM) -> float:
    """Absolute humidity of saturated air [kg/kg]; inf where water boils at p."""
    ps = p_sat(T)
    return math.inf if ps >= p else 0.622 * ps / (p - ps)


def dew_point(x: float, p: float = P_ATM) -> float:
    """Dew point temperature [degC] of air with absolute humidity x (inverse Magnus)."""
    a = math.log(x * p / (0.622 + x) / 611.2)
    return 243.12 * a / (17.62 - a)


def cool_down(m_air: float, T2: float, x2: float, T3: float, p: float = P_ATM) -> dict:
    """Cooling of the outlet air from T2 to T3, manuscript Eq. (7)-(9). m_air in kg/s (dry air), results in kW.

    Sensible cooling to the dew point (7), then condensation down to T3 (8); the air leaves saturated at T3.
    If T3 is above the dew point, everything is sensible and the latent part is 0.
    """
    T_dew = dew_point(x2, p)
    h2 = enthalpy(T2, x2)
    if T3 < T_dew:
        h_dew, x3 = enthalpy(T_dew, x2), x_sat(T3, p)
        h3 = enthalpy(T3, x3)
        Q_dew, Q_latent = m_air * (h2 - h_dew), m_air * (h_dew - h3)        # Eq. (7), (8)
    else:
        x3, h3 = x2, enthalpy(T3, x2)
        Q_dew, Q_latent = m_air * (h2 - h3), 0.0
    return {"T_dew": T_dew, "x3": x3, "h2": h2, "h3": h3, "Q_dew": Q_dew, "Q_latent": Q_latent,
            "Q_cooling": Q_dew + Q_latent,                                    # Eq. (9)
            "condensate_kg_s": m_air * (x2 - x3)}


def exhaust_streams(T2: float, T3: float, cool: dict) -> list[dict]:
    """Hot streams of the outlet air: sensible part down to the dew point, then condensation down to T3."""
    T_low = max(cool["T_dew"], T3)
    rows = []
    if T2 > T_low and cool["Q_dew"] > 0:
        rows.append({"stream": "exhaust air, sensible", "type": "hot", "T_supply_degC": T2, "T_target_degC": T_low,
                     "CP_kW_per_K": cool["Q_dew"] / (T2 - T_low), "Q_kW": cool["Q_dew"]})
    if cool["Q_latent"] > 0:
        rows.append({"stream": "exhaust air, condensation", "type": "hot", "T_supply_degC": cool["T_dew"],
                     "T_target_degC": T3, "CP_kW_per_K": cool["Q_latent"] / (cool["T_dew"] - T3),
                     "Q_kW": cool["Q_latent"]})
    return rows
