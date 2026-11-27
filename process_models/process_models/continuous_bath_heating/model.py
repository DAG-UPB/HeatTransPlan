"""Continuous bath heating: energy demand, manuscript Eq. (15)-(17), Fig. 6.

Fig. 1: Thermal activation solid products > Continuous bath heating. Examples: galvanization, washing,
boiling large scale. A bath is kept at T_bath; the heat demand is the product dipped into it (15) plus the losses
through the walls (16) and from the open surface by convection and radiation (17).
Standard library only, so the app can run it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from process_models.base import InputSpec, ProcessModel

VERSION = "1.0"

SIGMA = 5.67e-8            # W/(m2 K4), Stefan-Boltzmann constant (manuscript nomenclature)
K = 273.15

_REF_IN = "Sect. 'Continuous bath heating', input list"

INPUTS = (
    # ---- required (manuscript: input list below Eq. 17, plus Eq. 16) -----------------------
    InputSpec("product_flow_kg_h", "Product mass flow through the bath", "kg/h", True, "m_product",
              example=20000.0, ref=_REF_IN, note="Manuscript: 'mass'; for a continuous bath a mass flow."),
    InputSpec("cp_product", "Specific heat capacity of the product", "kJ/(kg K)", True, "cp,product",
              example=0.5, ref=_REF_IN),
    InputSpec("T_product_in", "Product inlet temperature", "degC", True, "T_product,in", example=20.0, ref=_REF_IN),
    InputSpec("T_bath", "Bath target temperature", "degC", True, "T_bath", example=170.0, ref=_REF_IN),
    InputSpec("A_surface", "Open surface area of the bath", "m2", True, "A_surface", example=20.0, ref=_REF_IN),
    InputSpec("A_wall", "Wall area of the bath", "m2", True, "A_wall", example=60.0, ref="Eq. (16)",
              note="In Eq. (16), not in the input list."),
    InputSpec("U_bath", "Heat transfer coefficient of the bath walls (insulation)", "W/(m2 K)", True, "U_bath",
              example=0.5, ref=_REF_IN),
    InputSpec("T_amb", "Ambient temperature", "degC", True, "T_ambient", example=20.0, ref=_REF_IN),
    InputSpec("alpha", "Convective heat transfer coefficient at the surface", "W/(m2 K)", True, "alpha",
              example=10.0, ref=_REF_IN),
    # ---- optional --------------------------------------------------------------------------
    InputSpec("emissivity", "Emissivity of the bath surface", "-", False, "epsilon", default=0.95, example=0.95,
              ref="Eq. (17), Fig. 6", note="In Eq. (17), not in the input list; default 0.95, not from manuscript."),
    InputSpec("utility_flow_kg_h", "Utility mass flow (heating medium)", "kg/h", False, "m_utility",
              default=None, example=None, ref="Sect. 'Continuous bath heating', last paragraph",
              note="With the utility inlet temperature, gives the utility return temperature."),
    InputSpec("T_utility_in", "Utility inlet temperature", "degC", False, "T_in", default=None, example=None,
              ref="Fig. 6"),
    InputSpec("cp_utility", "Specific heat capacity of the utility", "kJ/(kg K)", False, "", default=4.18,
              example=4.18, note="Default: water, not from manuscript."),
    InputSpec("dT_latent", "Temperature glide of the bath heating stream", "K", False, "", default=1.0, example=1.0,
              note="Not from manuscript: the bath takes heat at T_bath; the pinch analysis needs T_supply != T_target."),
)


@dataclass
class BathHeatingResult:
    inputs: dict
    Q_product: float               # Eq. (15)
    Q_trans: float                 # Eq. (16)
    Q_surface_convection: float    # Eq. (17), 1st term
    Q_surface_radiation: float     # Eq. (17), 2nd term
    Q_heating: float
    T_utility_out: float | None    # from the thermal balance of the utility, if given
    Q_cooling: float = 0.0         # the model has no cooling demand
    warnings: list = field(default_factory=list)

    @property
    def Q_surface(self) -> float:
        return self.Q_surface_convection + self.Q_surface_radiation

    def summary(self) -> list[dict]:
        rows = [
            ("Heating of the product", "m_product*cp*(T_bath - T_product,in)", self.Q_product, "kW", "Eq. (15)"),
            ("Transmission losses (walls)", "U_bath*A_wall*(T_bath - T_amb)", self.Q_trans, "kW", "Eq. (16)"),
            ("Surface losses, convection", "alpha*A_surface*(T_bath - T_amb)", self.Q_surface_convection, "kW", "Eq. (17), 1st term"),
            ("Surface losses, radiation", "eps*sigma*A_surface*(T_bath^4 - T_amb^4)", self.Q_surface_radiation, "kW", "Eq. (17), 2nd term"),
            ("HEATING DEMAND (bath)", "Q_product + Q_trans + Q_surface", self.Q_heating, "kW", "Eq. (15)-(17)"),
        ]
        if self.T_utility_out is not None:
            rows.append(("Utility return temperature", "T_in - Q_heating/(m_utility*cp_utility)",
                         self.T_utility_out, "degC", "thermal balance"))
        cols = ("Quantity", "Symbol", "Value", "Unit", "Manuscript ref.")
        return [dict(zip(cols, r)) for r in rows]

    def stream_table(self) -> list[dict]:
        """The bath takes all its heat at T_bath: one cold stream with a small glide."""
        T_b, dT = self.inputs["T_bath"], self.inputs["dT_latent"]
        return [{"stream": "bath heating", "type": "cold", "T_supply_degC": T_b, "T_target_degC": T_b + dT,
                 "CP_kW_per_K": self.Q_heating / dT, "Q_kW": self.Q_heating}]


def calculate(values: dict) -> BathHeatingResult:
    """Heat demand of a continuously heated bath, manuscript Eq. (15)-(17), summed.

    Q_product = m_product*cp_product*(T_bath - T_product,in)                                    (15)
    Q_trans   = U_bath*A_wall*(T_bath - T_ambient)                                              (16)
    Q_surface = alpha*A_surface*(T_bath - T_ambient) + eps*sigma*A_surface*(T_bath^4 - T_ambient^4)  (17)
    Radiation with absolute temperatures. Evaporation from the surface (mentioned in the text) is not in Eq. (17).
    """
    v = values
    m = v["product_flow_kg_h"] / 3600.0                                  # kg/s
    T_b, T_a = v["T_bath"], v["T_amb"]

    if m <= 0 or v["cp_product"] <= 0:
        raise ValueError("product mass flow and cp must be > 0")
    if min(v["A_surface"], v["A_wall"], v["U_bath"], v["alpha"]) < 0 or not 0 <= v["emissivity"] <= 1:
        raise ValueError("areas, U_bath and alpha must be >= 0, emissivity between 0 and 1")
    if v["dT_latent"] <= 0:
        raise ValueError("dT_latent must be > 0")
    if v["T_product_in"] > T_b:
        raise ValueError(f"T_product_in ({v['T_product_in']}) must not be above the bath temperature ({T_b}).")

    # Eq. (15)
    Q_prod = m * v["cp_product"] * (T_b - v["T_product_in"])
    # Eq. (16), W -> kW
    Q_trans = v["U_bath"] * v["A_wall"] * (T_b - T_a) / 1000.0
    # Eq. (17), W -> kW
    Q_conv = v["alpha"] * v["A_surface"] * (T_b - T_a) / 1000.0
    Q_rad = v["emissivity"] * SIGMA * v["A_surface"] * ((T_b + K) ** 4 - (T_a + K) ** 4) / 1000.0
    Q_heating = Q_prod + Q_trans + Q_conv + Q_rad
    if Q_heating <= 0:
        raise ValueError("Heating demand <= 0: the bath gains more heat from the ambient than the product takes.")

    warns, T_u_out = [], None
    m_u, T_u_in = v["utility_flow_kg_h"], v["T_utility_in"]
    if T_u_in is not None and T_u_in <= T_b:
        warns.append(f"Utility inlet ({T_u_in} degC) is not above the bath temperature ({T_b} degC).")
    if m_u is not None and T_u_in is not None:
        if m_u <= 0 or v["cp_utility"] <= 0:
            raise ValueError("utility mass flow and cp must be > 0")
        T_u_out = T_u_in - Q_heating / (m_u / 3600.0 * v["cp_utility"])
        if T_u_out < T_b:
            warns.append(f"Utility return ({T_u_out:.1f} degC) would be below the bath temperature: more utility flow needed.")
    if T_b < T_a:
        warns.append("Bath is colder than ambient: the loss terms are negative.")

    return BathHeatingResult(
        inputs=dict(v), Q_product=Q_prod, Q_trans=Q_trans, Q_surface_convection=Q_conv,
        Q_surface_radiation=Q_rad, Q_heating=Q_heating, T_utility_out=T_u_out, warnings=warns,
    )


MODEL = ProcessModel(
    key="continuous_bath_heating", name="Continuous bath heating", version=VERSION,
    process_type="Thermal activation solid products", category="Continuous bath heating",
    manuscript_refs="Eq. (15)-(17), Fig. 6",
    inputs=INPUTS, run=calculate,
)
