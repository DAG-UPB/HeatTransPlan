"""Pasteurization (continuous heating of fluids): energy demand, manuscript Eq. (18) and (19).

Taken unchanged from energy_demand_models (2).ipynb, section 2; only pandas was replaced by plain lists,
so the app can use it. pasteurization.ipynb checks that both give the same results.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from process_models.base import InputSpec, ProcessModel

VERSION = "1.0"

# Default specific heat capacities [kJ/(kg K)]
# NOTE: typical values, NOT taken from the manuscript -> please check/replace.
PRODUCT_CP_PRESETS = {
    "Juice (generic)": 3.89,   # = 3890 J/(kg K) from the example in main.py
    "Whole milk": 3.93,
    "Skim milk": 3.97,
    "Water": 4.18,
}

_REF_IN = "Sect. 'Continuous heating of fluids', input list"

INPUTS = (
    # ---- required (manuscript: input list below Eq. 19) -----------------------------------
    InputSpec("mass_flow_kg_h", "Product mass flow rate", "kg/h", True, "m_product",
              example=3135.0, ref=_REF_IN),
    InputSpec("T_in", "Product inlet temperature", "degC", True, "T_in",
              example=4.0, ref=_REF_IN),
    InputSpec("T_pasteur", "Pasteurization temperature", "degC", True, "T_pasteur",
              example=90.0, ref=_REF_IN),
    InputSpec("T_out", "Outlet temperature after cooling", "degC", True, "T_out",
              example=4.0, ref=_REF_IN),
    # ---- optional --------------------------------------------------------------------------
    InputSpec("product", "Product (selects default cp)", "-", False, "",
              default="Juice (generic)", kind="choice", choices=tuple(PRODUCT_CP_PRESETS),
              note="Only used to pick a default cp if cp is not given."),
    InputSpec("cp", "Specific heat capacity of product", "kJ/(kg K)", False, "cp,product",
              default=None, example=3.89, ref=_REF_IN,
              note="Required in the manuscript; here optional -> preset of the selected product."),
    InputSpec("T_safety_margin", "Safety margin above pasteurization temperature", "K", False,
              "dT_margin", default=0.0, example=0.0, ref="Sect. 'Continuous heating of fluids' (1st paragraph)",
              note="Manuscript: temperature 'slightly exceeded', not quantified -> 0 K."),
    InputSpec("loss_area", "Heat-losing surface (pipes, holding tube, exchangers)", "m2", False,
              "A_pasteur", default=0.0, example=0.0, ref="Eq. (18), (19) loss term",
              note="0 = no heat losses (as in the validation case)."),
    InputSpec("U_value", "Overall heat transfer coefficient to ambient", "W/(m2 K)", False,
              "U_pasteur", default=1.0, example=1.0, ref="Eq. (18), (19) loss term",
              note="Dummy value; only effective if loss_area > 0."),
    InputSpec("T_amb", "Ambient temperature", "degC", False, "T_amb",
              default=20.0, example=20.0, ref="Eq. (18), (19) loss term"),
)


def derive_defaults(values: dict) -> dict:
    """Derived defaults: cp from product preset."""
    p = values["product"]
    return {"cp": (PRODUCT_CP_PRESETS[p], f"preset ({p}), not from manuscript")}


@dataclass
class PasteurizationResult:
    inputs: dict
    T_pasteur_eff: float           # pasteurization temperature incl. safety margin [degC]
    # Eq. (18)
    Q_sensible_heating: float
    Q_loss_heating: float
    Q_heating: float
    # Eq. (19)
    Q_sensible_cooling: float
    Q_loss_cooling: float
    Q_cooling: float
    CP_flow: float                 # m_dot * cp [kW/K]
    warnings: list = field(default_factory=list)

    def summary(self) -> list[dict]:
        rows = [
            ("Heating demand, sensible", "m*cp*(T_pasteur - T_in)", self.Q_sensible_heating, "kW", "Eq. (18), 1st term"),
            ("Heat losses during heating", "(1/t) sum A*U*(T_i - T_amb)", self.Q_loss_heating, "kW", "Eq. (18), 2nd term"),
            ("HEATING DEMAND", "Q_heating", self.Q_heating, "kW", "Eq. (18)"),
            ("Cooling demand, sensible", "m*cp*(T_pasteur - T_out)", self.Q_sensible_cooling, "kW", "Eq. (19), 1st term"),
            ("Heat losses during cooling", "(1/t) sum A*U*(T_i - T_amb)", self.Q_loss_cooling, "kW", "Eq. (19), 2nd term (subtracted)"),
            ("COOLING DEMAND", "Q_cooling", self.Q_cooling, "kW", "Eq. (19)"),
            ("Sum heating + cooling (gross)", "Q_heating + Q_cooling", self.Q_heating + self.Q_cooling, "kW", "= classes.py calculate_total_energy()[2]"),
            ("Heat capacity flow rate", "m*cp", self.CP_flow, "kW/K", "-"),
        ]
        cols = ("Quantity", "Symbol", "Value", "Unit", "Manuscript ref.")
        return [dict(zip(cols, r)) for r in rows]

    def stream_table(self) -> list[dict]:
        """Stream data of the two product streams (hand-over to the pinch analysis of the overall system)."""
        T_p, v = self.T_pasteur_eff, self.inputs
        return [
            {"stream": "product heating", "type": "cold", "T_supply_degC": v["T_in"], "T_target_degC": T_p,
             "CP_kW_per_K": self.Q_heating / (T_p - v["T_in"]), "Q_kW": self.Q_heating},
            {"stream": "product cooling", "type": "hot", "T_supply_degC": T_p, "T_target_degC": v["T_out"],
             "CP_kW_per_K": self.Q_cooling / (T_p - v["T_out"]), "Q_kW": self.Q_cooling},
        ]


def calculate(values: dict) -> PasteurizationResult:
    """Energy demand of continuous pasteurization, manuscript Eq. (18) and (19).

    Q_heating = m*cp*(T_pasteur - T_in)  + (1/t) * sum_i A*U*(T_i - T_amb)          (18)
    Q_cooling = m*cp*(T_pasteur - T_out) - (1/t) * sum_i A*U*(T_i - T_amb)          (19)

    Assumption (manuscript does not define T_i): the product temperature in the loss term is the
    mean temperature of the respective stage, i.e. the time average for a linear profile.
    The holding time does not enter the energy model (manuscript, first paragraph of the section).
    """
    v = values
    m = v["mass_flow_kg_h"] / 3600.0                     # kg/s
    cp = v["cp"]                                         # kJ/(kg K)
    T_p = v["T_pasteur"] + v["T_safety_margin"]
    T_in, T_out = v["T_in"], v["T_out"]
    A, U, T_amb = v["loss_area"], v["U_value"], v["T_amb"]

    if m <= 0 or cp <= 0:
        raise ValueError("mass flow and cp must be > 0")
    if not T_in < T_p:
        raise ValueError(f"T_in ({T_in}) must be below the pasteurization temperature ({T_p}).")
    if not T_out < T_p:
        raise ValueError(f"T_out ({T_out}) must be below the pasteurization temperature ({T_p}).")

    CP_flow = m * cp                                     # kW/K  (kg/s * kJ/(kg K))

    # Eq. (18)
    Q_sens_h = CP_flow * (T_p - T_in)
    Q_loss_h = A * U * (0.5 * (T_in + T_p) - T_amb) / 1000.0       # W -> kW
    Q_heating = Q_sens_h + Q_loss_h
    # Eq. (19)
    Q_sens_c = CP_flow * (T_p - T_out)
    Q_loss_c = A * U * (0.5 * (T_p + T_out) - T_amb) / 1000.0
    Q_cooling = Q_sens_c - Q_loss_c

    warns = []
    if Q_cooling <= 0:
        raise ValueError("Cooling demand <= 0: heat losses exceed the sensible cooling load.")
    if A > 0 and T_out < T_amb - 1e-9:
        warns.append("T_out is below ambient temperature: loss term in Eq. (19) becomes negative (heat gain).")

    return PasteurizationResult(
        inputs=dict(v), T_pasteur_eff=T_p,
        Q_sensible_heating=Q_sens_h, Q_loss_heating=Q_loss_h, Q_heating=Q_heating,
        Q_sensible_cooling=Q_sens_c, Q_loss_cooling=Q_loss_c, Q_cooling=Q_cooling,
        CP_flow=CP_flow, warnings=warns,
    )


MODEL = ProcessModel(
    key="pasteurization", name="Pasteurization", version=VERSION,
    process_type="Thermal activation of fluid products", category="Continuous heating of fluids",
    manuscript_refs="Eq. (18), (19), Fig. 7",
    inputs=INPUTS, run=calculate, derive_defaults=derive_defaults,
)
