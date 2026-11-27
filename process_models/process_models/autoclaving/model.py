"""Autoclaving (batch): energy demand, manuscript Eq. (12)-(14), Fig. 5.

Fig. 1: Thermal activation solid products > Autoclaving. Examples: sterilization, hardening, boiling small scale.
Product, packaging and autoclave are heated from T_start to T_steri (12), held there (14) and cooled to T_final (13).
Standard library only, so the app can run it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from process_models.base import InputSpec, ProcessModel

VERSION = "1.0"

_REF_IN = "Sect. 'Autoclaving', input list"
_NOT_IN_EQ = "Listed in the manuscript but not used in Eq. (12)-(14): only checked and shown in the P&ID."
_STEEL = "Default 0.50 kJ/(kg K) (steel), not from manuscript."

INPUTS = (
    # ---- required (manuscript: input list below Eq. 14) -----------------------------------
    InputSpec("m_product", "Mass of product per batch", "kg", True, "m_product", example=500.0, ref=_REF_IN),
    InputSpec("cp_product", "Specific heat capacity of the product", "kJ/(kg K)", True, "cp,product",
              example=3.6, ref=_REF_IN),
    InputSpec("m_packaging", "Mass of packaging per batch", "kg", True, "m_packaging", example=100.0, ref=_REF_IN,
              note="0 for unpackaged products."),
    InputSpec("m_autoclave", "Mass of the autoclave", "kg", True, "m_autoclave", example=1500.0, ref=_REF_IN),
    InputSpec("T_start", "Initial temperature", "degC", True, "T_start", example=20.0, ref=_REF_IN),
    InputSpec("T_steri", "Sterilization (target) temperature", "degC", True, "T_steri", example=121.0, ref=_REF_IN),
    InputSpec("T_final", "Final temperature after cooling", "degC", True, "T_final", example=40.0, ref=_REF_IN),
    InputSpec("t_heating_min", "Heating time", "min", True, "t_heating", example=20.0, ref=_REF_IN),
    InputSpec("t_holding_min", "Holding time", "min", True, "t_holding", example=15.0, ref=_REF_IN),
    InputSpec("t_cooling_min", "Cooling time", "min", True, "t_cooling", example=20.0, ref=_REF_IN),
    # ---- optional --------------------------------------------------------------------------
    InputSpec("cp_packaging", "Specific heat capacity of the packaging", "kJ/(kg K)", False, "cp,packaging",
              default=0.50, example=0.50, ref=_REF_IN, note=_STEEL),
    InputSpec("cp_autoclave", "Specific heat capacity of the autoclave", "kJ/(kg K)", False, "cp,autoclave",
              default=0.50, example=0.50, ref=_REF_IN, note=_STEEL),
    InputSpec("loss_area", "Outer surface of the autoclave", "m2", False, "A_autoclave",
              default=0.0, example=0.0, ref="Eq. (12)-(14) loss terms", note="0 = no heat losses."),
    InputSpec("U_value", "Overall heat transfer coefficient to ambient", "W/(m2 K)", False, "U_autoclave",
              default=1.0, example=1.0, ref="Eq. (12)-(14) loss terms", note="Only effective if loss_area > 0."),
    InputSpec("T_amb", "Ambient temperature", "degC", False, "T_amb", default=20.0, example=20.0,
              ref="Eq. (12)-(14) loss terms"),
    InputSpec("utility_flow_kg_h", "Utility mass flow (steam, hot water)", "kg/h", False, "m_utility",
              default=None, example=None, ref=_REF_IN, note=_NOT_IN_EQ),
    InputSpec("T_utility_in", "Utility inlet temperature", "degC", False, "T_inlet",
              default=None, example=None, ref=_REF_IN, note=_NOT_IN_EQ),
    InputSpec("duty_basis", "Duty handed to the pinch analysis", "-", False, "",
              default="phase", kind="choice", choices=("phase", "cycle"),
              note="phase: power during each phase, Eq. (12)-(14) as in the manuscript. cycle: energy per batch "
                   "divided by the cycle time (the phases do not run at the same time). Not from manuscript."),
    InputSpec("dT_latent", "Temperature glide of the holding stream", "K", False, "", default=1.0, example=1.0,
              note="Not from manuscript: the pinch analysis needs T_supply != T_target."),
)


@dataclass
class AutoclavingResult:
    inputs: dict
    heat_capacity_kJ_K: float      # sum m_i * cp_i
    # Eq. (12)
    Q_sensible_heating: float
    Q_loss_heating: float
    Q_heating: float
    # Eq. (14)
    Q_holding: float
    # Eq. (13)
    Q_sensible_cooling: float
    Q_loss_cooling: float
    Q_cooling: float
    # per batch
    E_heating_MJ: float
    E_holding_MJ: float
    E_cooling_MJ: float
    t_cycle_min: float
    warnings: list = field(default_factory=list)

    @property
    def E_demand_MJ(self) -> float:
        """Heat demand per batch: heating and holding."""
        return self.E_heating_MJ + self.E_holding_MJ

    def summary(self) -> list[dict]:
        t_c = self.t_cycle_min * 60
        rows = [
            ("Heat capacity of product, packaging, autoclave", "sum m_i*cp_i", self.heat_capacity_kJ_K, "kJ/K", "-"),
            ("Heating, sensible", "sum m_i*cp_i*(T_steri - T_start)/t_heating", self.Q_sensible_heating, "kW", "Eq. (12), 1st term"),
            ("Heat losses during heating", "(1/t) sum A*U*(T_i - T_amb)", self.Q_loss_heating, "kW", "Eq. (12), 2nd term"),
            ("HEATING DEMAND (heating phase)", "Q_heating", self.Q_heating, "kW", "Eq. (12)"),
            ("HOLDING DEMAND (holding phase)", "A*U*(T_steri - T_amb)", self.Q_holding, "kW", "Eq. (14)"),
            ("Cooling, sensible", "sum m_i*cp_i*(T_steri - T_final)/t_cooling", self.Q_sensible_cooling, "kW", "Eq. (13), 1st term"),
            ("Heat losses during cooling", "(1/t) sum A*U*(T_i - T_amb)", self.Q_loss_cooling, "kW", "Eq. (13), 2nd term (subtracted)"),
            ("COOLING DEMAND (cooling phase)", "Q_cooling", self.Q_cooling, "kW", "Eq. (13)"),
            ("Heat demand per batch (heating + holding)", "Q_heating*t_h + Q_holding*t_hold", self.E_demand_MJ, "MJ", "-"),
            ("Cooling energy per batch", "Q_cooling*t_c", self.E_cooling_MJ, "MJ", "-"),
            ("Cycle time", "t_heating + t_holding + t_cooling", self.t_cycle_min, "min", "-"),
            ("Heat demand, cycle average", "E_demand / t_cycle", self.E_demand_MJ * 1000 / t_c, "kW", "-"),
            ("Cooling demand, cycle average", "E_cooling / t_cycle", self.E_cooling_MJ * 1000 / t_c, "kW", "-"),
        ]
        cols = ("Quantity", "Symbol", "Value", "Unit", "Manuscript ref.")
        return [dict(zip(cols, r)) for r in rows]

    def stream_table(self) -> list[dict]:
        """Heating (cold), holding (cold, at T_steri) and cooling (hot), as phase or cycle-average duties."""
        v = self.inputs
        if v["duty_basis"] == "cycle":
            t_c = self.t_cycle_min * 60
            Q_h, Q_hold, Q_c = (e * 1000 / t_c for e in (self.E_heating_MJ, self.E_holding_MJ, self.E_cooling_MJ))
        else:
            Q_h, Q_hold, Q_c = self.Q_heating, self.Q_holding, self.Q_cooling
        T_s, dT = v["T_steri"], v["dT_latent"]
        rows = [{"stream": "batch heating", "type": "cold", "T_supply_degC": v["T_start"], "T_target_degC": T_s,
                 "CP_kW_per_K": Q_h / (T_s - v["T_start"]), "Q_kW": Q_h}]
        if Q_hold > 0:
            rows.append({"stream": "holding", "type": "cold", "T_supply_degC": T_s, "T_target_degC": T_s + dT,
                         "CP_kW_per_K": Q_hold / dT, "Q_kW": Q_hold})
        rows.append({"stream": "batch cooling", "type": "hot", "T_supply_degC": T_s, "T_target_degC": v["T_final"],
                     "CP_kW_per_K": Q_c / (T_s - v["T_final"]), "Q_kW": Q_c})
        return rows


def calculate(values: dict) -> AutoclavingResult:
    """Energy demand of a batch autoclave, manuscript Eq. (12)-(14).

    Q_heating = sum m_i*cp_i*(T_steri - T_start)/t_heating + (1/t) sum A*U*(T_i - T_amb)     (12)
    Q_cooling = sum m_i*cp_i*(T_steri - T_final)/t_cooling - (1/t) sum A*U*(T_i - T_amb)     (13)
    Q_holding = A*U*(T_steri - T_amb)                                                         (14)

    Assumption (manuscript does not define T_i): the loss term uses the mean temperature of the phase, i.e. the
    time average for the linear profile of Fig. 5.
    """
    v = values
    C = v["m_product"] * v["cp_product"] + v["m_packaging"] * v["cp_packaging"] + v["m_autoclave"] * v["cp_autoclave"]
    t_h, t_hold, t_c = (v[k] * 60.0 for k in ("t_heating_min", "t_holding_min", "t_cooling_min"))    # s
    T_start, T_s, T_f = v["T_start"], v["T_steri"], v["T_final"]
    AU = v["loss_area"] * v["U_value"] / 1000.0                                                     # kW/K

    if min(v["m_product"], v["m_packaging"], v["m_autoclave"]) < 0 or v["m_product"] <= 0:
        raise ValueError("masses must be >= 0 and the product mass > 0")
    if min(v["cp_product"], v["cp_packaging"], v["cp_autoclave"]) <= 0:
        raise ValueError("specific heat capacities must be > 0")
    if t_h <= 0 or t_c <= 0 or t_hold < 0:
        raise ValueError("heating and cooling time must be > 0, holding time >= 0")
    if not T_start < T_s:
        raise ValueError(f"T_start ({T_start}) must be below the sterilization temperature ({T_s}).")
    if not T_f < T_s:
        raise ValueError(f"T_final ({T_f}) must be below the sterilization temperature ({T_s}).")

    # Eq. (12)
    Q_sens_h = C * (T_s - T_start) / t_h
    Q_loss_h = AU * (0.5 * (T_start + T_s) - v["T_amb"])
    # Eq. (14)
    Q_hold = AU * (T_s - v["T_amb"])
    # Eq. (13)
    Q_sens_c = C * (T_s - T_f) / t_c
    Q_loss_c = AU * (0.5 * (T_s + T_f) - v["T_amb"])
    Q_cooling = Q_sens_c - Q_loss_c
    if Q_cooling <= 0:
        raise ValueError("Cooling demand <= 0: heat losses exceed the sensible cooling load.")

    warns = []
    if v["T_utility_in"] is not None and v["T_utility_in"] <= T_s:
        warns.append(f"Utility inlet ({v['T_utility_in']} degC) is not above the sterilization temperature ({T_s} degC).")
    if Q_hold < 0:
        warns.append("Ambient is warmer than the sterilization temperature: the holding term is negative.")

    Q_heating = Q_sens_h + Q_loss_h
    return AutoclavingResult(
        inputs=dict(v), heat_capacity_kJ_K=C,
        Q_sensible_heating=Q_sens_h, Q_loss_heating=Q_loss_h, Q_heating=Q_heating, Q_holding=Q_hold,
        Q_sensible_cooling=Q_sens_c, Q_loss_cooling=Q_loss_c, Q_cooling=Q_cooling,
        E_heating_MJ=Q_heating * t_h / 1000, E_holding_MJ=Q_hold * t_hold / 1000, E_cooling_MJ=Q_cooling * t_c / 1000,
        t_cycle_min=(t_h + t_hold + t_c) / 60, warnings=warns,
    )


MODEL = ProcessModel(
    key="autoclaving", name="Autoclaving", version=VERSION,
    process_type="Thermal activation solid products", category="Autoclaving",
    manuscript_refs="Eq. (12)-(14), Fig. 5",
    inputs=INPUTS, run=calculate,
)
