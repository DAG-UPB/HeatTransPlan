"""Conductive drying: energy demand, manuscript Eq. (10), (11), (5), (7)-(9), Fig. 4.

Fig. 1: Drying > Conductive drying. Examples: belt drying, textile drying, contact drum drying.
The wet product is heated to the surface temperature of the heated plate, drum or belt (10) and its moisture is
evaporated there (11). An air stream carries the vapour away (5); its outlet is cooled to T3 like in convective
drying (7)-(9). Standard library only, so the app can run it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from process_models import humid_air as ha
from process_models.base import InputSpec, ProcessModel

VERSION = "1.0"

_REF_IN = "Sect. 'Conductive drying', input list"
_NOT_LISTED = "In Eq. (10), not in the input list."

INPUTS = (
    # ---- required (manuscript: input list below Eq. 11, plus Eq. 10 and the text) ----------------
    InputSpec("product_flow_kg_h", "Product mass flow rate", "kg/h", True, "m_product",
              example=30000.0, ref=_REF_IN),
    InputSpec("w_in", "Initial moisture content of the product", "kg/kg", True, "w_in",
              example=0.5, ref=_REF_IN, note="Eq. (11): water evaporated = m_product * (w_in - w_out)."),
    InputSpec("w_out", "Final moisture content of the product", "kg/kg", True, "w_out",
              example=0.075, ref=_REF_IN),
    InputSpec("T_surface", "Drying surface temperature", "degC", True, "T_surface",
              example=135.0, ref=_REF_IN),
    InputSpec("T_product_in", "Product inlet temperature", "degC", True, "T_inlet",
              example=15.0, ref="Eq. (10)", note=_NOT_LISTED),
    InputSpec("cp_wet", "Specific heat capacity of the wet product", "kJ/(kg K)", True, "cp,wet",
              example=2.7, ref="Eq. (10)", note=_NOT_LISTED),
    InputSpec("air_flow_kg_h", "Air mass flow rate (dry air)", "kg/h", True, "m_air",
              example=106250.0, ref=_REF_IN),
    InputSpec("T1", "Air inlet temperature", "degC", True, "T1", example=15.0, ref=_REF_IN),
    InputSpec("x1_g_kg", "Air inlet absolute humidity", "g/kg", True, "x1", example=6.43, ref=_REF_IN),
    InputSpec("T2", "Air outlet temperature", "degC", True, "T2", example=70.0,
              ref="Sect. 'Conductive drying', text", note="'must be known' (text), not in the input list."),
    # ---- optional --------------------------------------------------------------------------
    InputSpec("h_v", "Evaporation enthalpy of water", "kJ/kg", False, "h_v,water",
              default=None, example=2181.0, ref="Eq. (11)",
              note="Default: 2501 - 2.37*T_surface (water at the surface temperature), not from manuscript."),
    InputSpec("T_return", "Air temperature after cooling", "degC", False, "T3",
              default=None, example=25.0, ref="Eq. (8)", note="Not in the input list; default = T1."),
    InputSpec("dT_latent", "Temperature glide of the evaporation stream", "K", False, "",
              default=1.0, example=1.0,
              note="Not from manuscript: the pinch analysis needs T_supply != T_target."),
    InputSpec("pressure_Pa", "Air pressure", "Pa", False, "p", default=ha.P_ATM, example=ha.P_ATM,
              note="Not from manuscript; used for dew point and saturation."),
)


def derive_defaults(values: dict) -> dict:
    """Derived defaults: h_v of water at the surface temperature, air cooled back to its inlet temperature."""
    return {"h_v": (2501.0 - 2.37 * values["T_surface"], "2501 - 2.37*T_surface, not from manuscript"),
            "T_return": (values["T1"], "= T1, not from manuscript")}


@dataclass
class ConductiveDryingResult:
    inputs: dict
    Q_sensible: float              # Eq. (10)
    Q_latent_heating: float        # Eq. (11)
    Q_heating: float
    water_removed_kg_h: float
    x1: float
    x2: float                      # Eq. (5), kg/kg
    T_dew: float
    Q_dew: float                   # Eq. (7)
    Q_latent: float                # Eq. (8)
    Q_cooling: float               # Eq. (9)
    condensate_kg_h: float
    warnings: list = field(default_factory=list)

    def summary(self) -> list[dict]:
        rows = [
            ("Sensible heating of the wet product", "m_product*cp_wet*(T_surface - T_inlet)", self.Q_sensible, "kW", "Eq. (10)"),
            ("Evaporation of the moisture", "m_product*(w_in - w_out)*h_v", self.Q_latent_heating, "kW", "Eq. (11)"),
            ("HEATING DEMAND (heated surface)", "Q_sensible + Q_latent", self.Q_heating, "kW", "Eq. (10) + (11)"),
            ("Water removed from the product", "m_product*(w_in - w_out)", self.water_removed_kg_h, "kg/h", "Eq. (11)"),
            ("Outlet air humidity", "x2 = x1 + m_water/m_air", self.x2 * 1000, "g/kg", "Eq. (5)"),
            ("Dew point of the outlet air", "T_dew(x2)", self.T_dew, "degC", "-"),
            ("Sensible cooling to the dew point", "m_air*(h_outlet - h_dew)", self.Q_dew, "kW", "Eq. (7)"),
            ("Latent cooling (condensation)", "m_air*(h_dew - h_return)", self.Q_latent, "kW", "Eq. (8)"),
            ("COOLING DEMAND (outlet air)", "Q_dew + Q_latent", self.Q_cooling, "kW", "Eq. (9)"),
            ("Condensate", "m_air*(x2 - x3)", self.condensate_kg_h, "kg/h", "-"),
        ]
        cols = ("Quantity", "Symbol", "Value", "Unit", "Manuscript ref.")
        return [dict(zip(cols, r)) for r in rows]

    def stream_table(self) -> list[dict]:
        """Product heating and evaporation at the surface (cold), outlet air cooling and condensation (hot)."""
        v, T_s, dT = self.inputs, self.inputs["T_surface"], self.inputs["dT_latent"]
        rows = []
        if T_s > v["T_product_in"]:
            rows.append({"stream": "product heating", "type": "cold", "T_supply_degC": v["T_product_in"],
                         "T_target_degC": T_s, "CP_kW_per_K": self.Q_sensible / (T_s - v["T_product_in"]),
                         "Q_kW": self.Q_sensible})
        rows.append({"stream": "evaporation at the surface", "type": "cold", "T_supply_degC": T_s,
                     "T_target_degC": T_s + dT, "CP_kW_per_K": self.Q_latent_heating / dT, "Q_kW": self.Q_latent_heating})
        cool = {"T_dew": self.T_dew, "Q_dew": self.Q_dew, "Q_latent": self.Q_latent}
        return rows + ha.exhaust_streams(v["T2"], v["T_return"], cool)


def calculate(values: dict) -> ConductiveDryingResult:
    """Energy demand of conductive drying, manuscript Eq. (10), (11), (5), (7)-(9). m_air is dry air."""
    v = values
    m_p, m_air = v["product_flow_kg_h"] / 3600.0, v["air_flow_kg_h"] / 3600.0      # kg/s
    x1, p, T2, T3 = v["x1_g_kg"] / 1000.0, v["pressure_Pa"], v["T2"], v["T_return"]

    if m_p <= 0 or m_air <= 0 or v["cp_wet"] <= 0 or v["h_v"] <= 0:
        raise ValueError("mass flows, cp_wet and h_v must be > 0")
    if not 0 <= v["w_out"] < v["w_in"]:
        raise ValueError(f"moisture contents must satisfy 0 <= w_out < w_in (w_in = {v['w_in']}, w_out = {v['w_out']}).")
    if v["T_product_in"] > v["T_surface"]:
        raise ValueError(f"T_product_in ({v['T_product_in']}) must not be above the surface temperature ({v['T_surface']}).")
    if x1 < 0 or x1 >= ha.x_sat(v["T1"], p):
        raise ValueError(f"x1 ({x1 * 1000:.2f} g/kg) must be >= 0 and below saturation at T1.")
    if T3 > T2:
        raise ValueError(f"T_return ({T3}) must not be above the air outlet temperature T2 ({T2}).")

    # Eq. (10)
    Q_sens = m_p * v["cp_wet"] * (v["T_surface"] - v["T_product_in"])
    # Eq. (11)
    m_water = m_p * (v["w_in"] - v["w_out"])
    Q_lat = m_water * v["h_v"]
    # Eq. (5)
    x2 = x1 + m_water / m_air
    if T2 < ha.dew_point(x2, p):
        raise ValueError(f"Outlet air would be supersaturated (T2 = {T2} degC, x2 = {x2 * 1000:.1f} g/kg): "
                         "more air or a higher outlet temperature is needed.")
    # Eq. (7)-(9)
    cool = ha.cool_down(m_air, T2, x2, T3, p)

    warns = []
    if T2 > v["T_surface"]:
        warns.append("The air leaves hotter than the drying surface.")

    return ConductiveDryingResult(
        inputs=dict(v), Q_sensible=Q_sens, Q_latent_heating=Q_lat, Q_heating=Q_sens + Q_lat,
        water_removed_kg_h=m_water * 3600, x1=x1, x2=x2, T_dew=cool["T_dew"], Q_dew=cool["Q_dew"],
        Q_latent=cool["Q_latent"], Q_cooling=cool["Q_cooling"], condensate_kg_h=cool["condensate_kg_s"] * 3600,
        warnings=warns,
    )


MODEL = ProcessModel(
    key="conductive_drying", name="Conductive drying", version=VERSION,
    process_type="Drying", category="Conductive drying",
    manuscript_refs="Eq. (5), (9)-(11), Fig. 4",
    inputs=INPUTS, run=calculate, derive_defaults=derive_defaults,
)
