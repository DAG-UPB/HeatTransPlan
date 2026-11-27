"""Convective drying: energy demand, manuscript Eq. (3)-(9), Fig. 3.

Fig. 1: Drying > Convective drying. Examples: spray, granulate, ring and flash drying.
Air is heated from T0 to the drying temperature T1 at constant humidity (3), takes up the water removed from the
product (4), (5) and leaves at T2 (6). The outlet air is then cooled to T3, first sensibly to its dew point, then
with condensation (7)-(9). Standard library only, so the app can run it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from process_models import humid_air as ha
from process_models.base import InputSpec, ProcessModel

VERSION = "1.0"

_REF_IN = "Sect. 'Convective drying', input list"

INPUTS = (
    # ---- required (manuscript: input list below Eq. 9) ------------------------------------
    InputSpec("product_flow_kg_h", "Product mass flow rate", "kg/h", True, "m_product",
              example=12000.0, ref=_REF_IN),
    InputSpec("w1", "Initial moisture content of the product", "kg/kg", True, "w1",
              example=0.5, ref=_REF_IN, note="Eq. (4): water removed = m_product * (w1 - w2)."),
    InputSpec("w2", "Final moisture content of the product", "kg/kg", True, "w2",
              example=0.04, ref=_REF_IN),
    InputSpec("air_flow_kg_h", "Drying air mass flow rate (dry air)", "kg/h", True, "m_air",
              example=200000.0, ref=_REF_IN),
    InputSpec("T0", "Initial air temperature", "degC", True, "T0", example=15.0, ref=_REF_IN),
    InputSpec("T1", "Drying air temperature", "degC", True, "T1", example=210.0, ref=_REF_IN),
    InputSpec("x0_g_kg", "Absolute humidity of the air (x1 = x0)", "g/kg", True, "x0, x1",
              example=6.43, ref=_REF_IN),
    # ---- optional --------------------------------------------------------------------------
    InputSpec("T_return", "Air temperature after cooling", "degC", False, "T3",
              default=None, example=15.0, ref="Eq. (8), Fig. 3", note="Not in the input list; default = T0."),
    InputSpec("UA_W_K", "UA-value of the dryer (heat losses)", "W/K", False, "U*A",
              default=0.0, example=0.0, ref="Eq. (6), Fig. 3", note="Not in the input list; 0 = no losses."),
    InputSpec("T_amb", "Ambient temperature", "degC", False, "T_amb", default=20.0, example=20.0, ref="Eq. (6)"),
    InputSpec("pressure_Pa", "Air pressure", "Pa", False, "p", default=ha.P_ATM, example=ha.P_ATM,
              note="Not from manuscript; used for dew point and saturation."),
)


def derive_defaults(values: dict) -> dict:
    """Derived default: the air is cooled back to its initial temperature."""
    return {"T_return": (values["T0"], "= T0, not from manuscript")}


@dataclass
class ConvectiveDryingResult:
    inputs: dict
    Q_heating: float               # Eq. (3)
    water_removed_kg_h: float      # Eq. (4)
    x1: float                      # kg/kg
    x2: float                      # Eq. (5), kg/kg
    T2: float                      # Eq. (6), degC
    h0: float
    h1: float
    T_dew: float
    Q_dew: float                   # Eq. (7)
    Q_latent: float                # Eq. (8)
    Q_cooling: float               # Eq. (9)
    condensate_kg_h: float
    warnings: list = field(default_factory=list)

    def summary(self) -> list[dict]:
        rows = [
            ("HEATING DEMAND (air heater)", "m_air*(h(T1,x1) - h(T0,x0))", self.Q_heating, "kW", "Eq. (3)"),
            ("Water removed from the product", "m_product*(w1 - w2)", self.water_removed_kg_h, "kg/h", "Eq. (4)"),
            ("Outlet air humidity", "x2 = x1 + m_water/m_air", self.x2 * 1000, "g/kg", "Eq. (5)"),
            ("Outlet air temperature", "T2", self.T2, "degC", "Eq. (6)"),
            ("Dew point of the outlet air", "T_dew(x2)", self.T_dew, "degC", "-"),
            ("Sensible cooling to the dew point", "m_air*(h_outlet - h_dew)", self.Q_dew, "kW", "Eq. (7)"),
            ("Latent cooling (condensation)", "m_air*(h_dew - h_return)", self.Q_latent, "kW", "Eq. (8)"),
            ("COOLING DEMAND (outlet air)", "Q_dew + Q_latent", self.Q_cooling, "kW", "Eq. (9)"),
            ("Condensate", "m_air*(x2 - x3)", self.condensate_kg_h, "kg/h", "-"),
        ]
        cols = ("Quantity", "Symbol", "Value", "Unit", "Manuscript ref.")
        return [dict(zip(cols, r)) for r in rows]

    def stream_table(self) -> list[dict]:
        """Air heating (cold), outlet air cooling to the dew point and condensation (hot)."""
        v = self.inputs
        rows = [{"stream": "air heating", "type": "cold", "T_supply_degC": v["T0"], "T_target_degC": v["T1"],
                 "CP_kW_per_K": self.Q_heating / (v["T1"] - v["T0"]), "Q_kW": self.Q_heating}]
        cool = {"T_dew": self.T_dew, "Q_dew": self.Q_dew, "Q_latent": self.Q_latent}
        return rows + ha.exhaust_streams(self.T2, v["T_return"], cool)


def calculate(values: dict) -> ConvectiveDryingResult:
    """Energy demand of convective drying, manuscript Eq. (3)-(9).

    Assumptions: m_air is dry air; T_average in Eq. (6) is the mean of T1 and T2 (the manuscript does not define it).
    """
    v = values
    m_air, m_p = v["air_flow_kg_h"] / 3600.0, v["product_flow_kg_h"] / 3600.0      # kg/s
    x1, p = v["x0_g_kg"] / 1000.0, v["pressure_Pa"]
    T0, T1, T3, UA = v["T0"], v["T1"], v["T_return"], v["UA_W_K"] / 1000.0           # UA in kW/K

    if m_air <= 0 or m_p <= 0:
        raise ValueError("air and product mass flow must be > 0")
    if not 0 <= v["w2"] < v["w1"]:
        raise ValueError(f"moisture contents must satisfy 0 <= w2 < w1 (w1 = {v['w1']}, w2 = {v['w2']}).")
    if not T0 < T1:
        raise ValueError(f"T0 ({T0}) must be below the drying air temperature T1 ({T1}).")
    if x1 < 0 or UA < 0:
        raise ValueError("humidity and UA-value must be >= 0")
    if x1 >= ha.x_sat(T0, p):
        raise ValueError(f"x0 ({x1 * 1000:.2f} g/kg) is above saturation at T0 ({T0} degC).")

    # Eq. (3): heating at constant humidity x1 = x0
    h0, h1 = ha.enthalpy(T0, x1), ha.enthalpy(T1, x1)
    Q_heating = m_air * (h1 - h0)
    # Eq. (4)
    m_water = m_p * (v["w1"] - v["w2"])
    # Eq. (5)
    x2 = x1 + m_water / m_air
    # Eq. (6) with T_average = (T1 + T2) / 2, solved for T2
    num = (T1 * (ha.CP_AIR + x1 * ha.CP_VAPOR) + ha.H_V0 * (x1 - x2)
           - UA * (T1 / 2 - v["T_amb"]) / m_air)
    T2 = num / (ha.CP_AIR + x2 * ha.CP_VAPOR + UA / (2 * m_air))
    if T2 < ha.dew_point(x2, p):
        raise ValueError(f"Outlet air would be supersaturated (T2 = {T2:.1f} degC, x2 = {x2 * 1000:.1f} g/kg): "
                         "more air, a higher drying temperature or less water.")
    if T3 > T2:
        raise ValueError(f"T_return ({T3}) must not be above the outlet air temperature T2 ({T2:.1f}).")
    # Eq. (7)-(9)
    cool = ha.cool_down(m_air, T2, x2, T3, p)

    warns = []
    if UA > 0 and T3 < v["T_amb"]:
        warns.append("T_return is below ambient temperature.")

    return ConvectiveDryingResult(
        inputs=dict(v), Q_heating=Q_heating, water_removed_kg_h=m_water * 3600, x1=x1, x2=x2, T2=T2,
        h0=h0, h1=h1, T_dew=cool["T_dew"], Q_dew=cool["Q_dew"], Q_latent=cool["Q_latent"],
        Q_cooling=cool["Q_cooling"], condensate_kg_h=cool["condensate_kg_s"] * 3600, warnings=warns,
    )


MODEL = ProcessModel(
    key="convective_drying", name="Convective drying", version=VERSION,
    process_type="Drying", category="Convective drying",
    manuscript_refs="Eq. (3)-(9), Fig. 3",
    inputs=INPUTS, run=calculate, derive_defaults=derive_defaults,
)
