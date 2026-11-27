"""Thermal phase change: energy demand, manuscript Eq. (20) and (21), Fig. 8.

Fig. 1: Thermal separation > Thermal phase change. Examples: distillation, evaporation, stripping.
A liquid feed is heated to its boiling temperature T_v and the component with the lower boiling point
(mass fraction w) is evaporated. The vapour is condensed afterwards and both products (distillate and
residue) are cooled to T_out. Standard library only, so the app can run it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from process_models.base import InputSpec, ProcessModel

VERSION = "1.0"

# Evaporated component: liquid cp [kJ/(kg K)] and latent heat at the normal boiling point [kJ/kg]
# NOTE: typical values, NOT taken from the manuscript -> please check/replace.
COMPONENT_PRESETS = {
    "Water": (4.19, 2257.0),
    "Ethanol": (2.44, 841.0),
    "Methanol": (2.53, 1100.0),
}

_REF_IN = "Sect. 'Thermal phase change', input list"
_NOT_IN_EQ = "Listed in the manuscript but not used in Eq. (20)/(21): only checked and shown in the P&ID."

INPUTS = (
    # ---- required (manuscript: input list below Eq. 21) -----------------------------------
    InputSpec("mass_flow_kg_h", "Feed mass flow rate", "kg/h", True, "m_product",
              example=1000.0, ref=_REF_IN),
    InputSpec("T_in", "Feed inlet temperature", "degC", True, "T_in",
              example=20.0, ref=_REF_IN),
    InputSpec("T_v", "Boiling temperature", "degC", True, "T_v",
              example=92.0, ref=_REF_IN),
    InputSpec("T_out", "Outlet temperature of both products after cooling", "degC", True, "T_out",
              example=25.0, ref=_REF_IN),
    InputSpec("cp_residue", "Specific heat capacity of the residue (component not evaporated)", "kJ/(kg K)",
              True, "cp,product2", example=4.19, ref=_REF_IN),
    # ---- optional --------------------------------------------------------------------------
    InputSpec("w", "Mass fraction of the evaporated component", "-", False, "w",
              default=None, example=0.1, ref=_REF_IN,
              note="Give w or the evaporated mass flow (manuscript: 'mass fraction w or flow rate')."),
    InputSpec("evaporated_flow_kg_h", "Mass flow of the evaporated component", "kg/h", False, "m_product*w",
              default=None, example=100.0, ref=_REF_IN,
              note="Alternative to w: w = evaporated mass flow / feed mass flow."),
    InputSpec("component", "Evaporated component (selects default cp and h_v)", "-", False, "",
              default="Water", kind="choice", choices=tuple(COMPONENT_PRESETS),
              note="Only used to pick defaults if cp_evaporated or h_v is not given."),
    InputSpec("cp_evaporated", "Specific heat capacity of the evaporated component (liquid)", "kJ/(kg K)",
              False, "cp,product1", default=None, example=2.44, ref=_REF_IN,
              note="Required in the manuscript; here optional -> preset of the selected component."),
    InputSpec("h_v", "Latent heat of vaporization of the evaporated component", "kJ/kg", False, "h_v",
              default=None, example=841.0, ref=_REF_IN,
              note="Required in the manuscript; here optional -> preset at the normal boiling point. "
                   "Enter h_v at T_v for vacuum or pressure operation."),
    InputSpec("T_utility_in", "Utility inlet temperature (heating medium)", "degC", False, "T_inlet",
              default=None, example=150.0, ref=_REF_IN, note=_NOT_IN_EQ),
    InputSpec("T_utility_out", "Utility outlet temperature (heating medium)", "degC", False, "T_outlet",
              default=None, example=140.0, ref=_REF_IN, note=_NOT_IN_EQ),
    InputSpec("dT_latent", "Temperature glide of the evaporation and condensation streams", "K", False, "",
              default=1.0, example=1.0,
              note="Not from manuscript: the pinch analysis needs T_supply != T_target, so the latent heat "
                   "is spread over this small glide (evaporation above T_v, condensation below T_v)."),
)


def derive_defaults(values: dict) -> dict:
    """Derived defaults: cp_evaporated and h_v from the component preset, w from the evaporated mass flow."""
    c = values["component"]
    cp, h_v = COMPONENT_PRESETS[c]
    out = {"cp_evaporated": (cp, f"preset ({c}), not from manuscript"),
           "h_v": (h_v, f"preset ({c}, normal boiling point), not from manuscript")}
    if values["w"] is None and values["evaporated_flow_kg_h"] is not None and values["mass_flow_kg_h"] > 0:
        out["w"] = (values["evaporated_flow_kg_h"] / values["mass_flow_kg_h"],
                    "evaporated mass flow / feed mass flow")
    return out


@dataclass
class ThermalPhaseChangeResult:
    inputs: dict
    # Eq. (20)
    Q_sensible_heating_evaporated: float   # m*w*cp1*(T_v - T_in)
    Q_latent_heating: float                # m*w*h_v
    Q_sensible_heating_residue: float      # m*(1-w)*cp2*(T_v - T_in)
    Q_heating: float
    # Eq. (21)
    Q_latent_cooling: float                # m*w*h_v
    Q_sensible_cooling_distillate: float   # m*w*cp1*(T_v - T_out)
    Q_sensible_cooling_residue: float      # m*(1-w)*cp2*(T_v - T_out)
    Q_cooling: float
    CP_liquid: float                       # m*(w*cp1 + (1-w)*cp2) [kW/K], feed and both products as liquid
    evaporated_flow_kg_h: float
    warnings: list = field(default_factory=list)

    def summary(self) -> list[dict]:
        m = self.inputs["mass_flow_kg_h"]
        rows = [
            ("Sensible heating, evaporated component", "m*w*cp1*(T_v - T_in)", self.Q_sensible_heating_evaporated, "kW", "Eq. (20), 1st term"),
            ("Latent heat, evaporation", "m*w*h_v", self.Q_latent_heating, "kW", "Eq. (20), 1st term"),
            ("Sensible heating, residue", "m*(1-w)*cp2*(T_v - T_in)", self.Q_sensible_heating_residue, "kW", "Eq. (20), 2nd term"),
            ("HEATING DEMAND", "Q_heating", self.Q_heating, "kW", "Eq. (20)"),
            ("Latent heat, condensation", "m*w*h_v", self.Q_latent_cooling, "kW", "Eq. (21), 1st term"),
            ("Sensible cooling, distillate", "m*w*cp1*(T_v - T_out)", self.Q_sensible_cooling_distillate, "kW", "Eq. (21), 1st term"),
            ("Sensible cooling, residue", "m*(1-w)*cp2*(T_v - T_out)", self.Q_sensible_cooling_residue, "kW", "Eq. (21), 2nd term"),
            ("COOLING DEMAND", "Q_cooling", self.Q_cooling, "kW", "Eq. (21)"),
            ("Evaporated mass flow", "m*w", self.evaporated_flow_kg_h, "kg/h", "-"),
            ("Heat capacity flow rate (liquid)", "m*(w*cp1 + (1-w)*cp2)", self.CP_liquid, "kW/K", "-"),
            ("Specific heating demand per kg feed", "Q_heating / m", self.Q_heating / m * 3600, "kJ/kg", "-"),
            ("Specific heating demand per kg evaporated", "Q_heating / (m*w)", self.Q_heating / self.evaporated_flow_kg_h * 3600, "kJ/kg", "-"),
        ]
        cols = ("Quantity", "Symbol", "Value", "Unit", "Manuscript ref.")
        return [dict(zip(cols, r)) for r in rows]

    def stream_table(self) -> list[dict]:
        """Stream data for the pinch analysis: feed preheating, evaporation, condensation, product cooling.

        The latent streams get the small glide dT_latent (T_supply != T_target); streams with no duty are left out.
        """
        v, T_v, dT, Q_lat = self.inputs, self.inputs["T_v"], self.inputs["dT_latent"], self.Q_latent_heating
        rows = []
        if T_v > v["T_in"]:
            rows.append({"stream": "feed preheating", "type": "cold", "T_supply_degC": v["T_in"], "T_target_degC": T_v,
                         "CP_kW_per_K": self.CP_liquid, "Q_kW": self.CP_liquid * (T_v - v["T_in"])})
        rows.append({"stream": "evaporation", "type": "cold", "T_supply_degC": T_v, "T_target_degC": T_v + dT,
                     "CP_kW_per_K": Q_lat / dT, "Q_kW": Q_lat})
        rows.append({"stream": "condensation", "type": "hot", "T_supply_degC": T_v, "T_target_degC": T_v - dT,
                     "CP_kW_per_K": Q_lat / dT, "Q_kW": Q_lat})
        if T_v > v["T_out"]:
            rows.append({"stream": "product cooling", "type": "hot", "T_supply_degC": T_v, "T_target_degC": v["T_out"],
                         "CP_kW_per_K": self.CP_liquid, "Q_kW": self.CP_liquid * (T_v - v["T_out"])})
        return rows


def calculate(values: dict) -> ThermalPhaseChangeResult:
    """Energy demand of a thermal phase change (distillation, evaporation, stripping), manuscript Eq. (20), (21).

    Q_heating = m*w*(h_v + cp1*(T_v - T_in))  + m*(1-w)*cp2*(T_v - T_in)            (20)
    Q_cooling = m*w*(h_v + cp1*(T_v - T_out)) + m*(1-w)*cp2*(T_v - T_out)           (21)

    cp1 / h_v: evaporated component, cp2: residue. One boiling temperature T_v for the whole separation
    and no heat losses, as in the manuscript.
    """
    v = values
    m = v["mass_flow_kg_h"] / 3600.0                     # kg/s
    w, cp1, cp2, h_v = v["w"], v["cp_evaporated"], v["cp_residue"], v["h_v"]
    T_in, T_v, T_out = v["T_in"], v["T_v"], v["T_out"]

    if w is None:
        raise ValueError("Give the mass fraction w or the evaporated mass flow.")
    if m <= 0 or cp1 <= 0 or cp2 <= 0 or h_v <= 0:
        raise ValueError("mass flow, cp values and h_v must be > 0")
    if not 0 < w <= 1:
        raise ValueError(f"w ({w}) must be between 0 and 1 (0 < w <= 1).")
    m_evap = v["evaporated_flow_kg_h"]
    if m_evap is not None and abs(w * v["mass_flow_kg_h"] - m_evap) > 1e-9 * max(1.0, m_evap):
        raise ValueError(f"w ({w}) and the evaporated mass flow ({m_evap} kg/h) do not match; give only one.")
    if T_in > T_v:
        raise ValueError(f"T_in ({T_in}) must not be above the boiling temperature ({T_v}).")
    if T_out > T_v:
        raise ValueError(f"T_out ({T_out}) must not be above the boiling temperature ({T_v}).")
    if v["dT_latent"] <= 0:
        raise ValueError("dT_latent must be > 0")

    # Eq. (20)
    Q_heating = m * w * (h_v + cp1 * (T_v - T_in)) + m * (1 - w) * cp2 * (T_v - T_in)
    # Eq. (21)
    Q_cooling = m * w * (h_v + cp1 * (T_v - T_out)) + m * (1 - w) * cp2 * (T_v - T_out)

    warns = []
    T_u_in, T_u_out = v["T_utility_in"], v["T_utility_out"]
    if T_u_in is not None and T_u_in <= T_v:
        warns.append(f"Utility inlet ({T_u_in} degC) is not above the boiling temperature ({T_v} degC): "
                     "it cannot evaporate the product.")
    if T_u_in is not None and T_u_out is not None and T_u_out > T_u_in:
        warns.append("Utility outlet is above the utility inlet: a heating medium cools down.")

    return ThermalPhaseChangeResult(
        inputs=dict(v),
        Q_sensible_heating_evaporated=m * w * cp1 * (T_v - T_in),
        Q_latent_heating=m * w * h_v,
        Q_sensible_heating_residue=m * (1 - w) * cp2 * (T_v - T_in),
        Q_heating=Q_heating,
        Q_latent_cooling=m * w * h_v,
        Q_sensible_cooling_distillate=m * w * cp1 * (T_v - T_out),
        Q_sensible_cooling_residue=m * (1 - w) * cp2 * (T_v - T_out),
        Q_cooling=Q_cooling,
        CP_liquid=m * (w * cp1 + (1 - w) * cp2),
        evaporated_flow_kg_h=w * v["mass_flow_kg_h"],
        warnings=warns,
    )


MODEL = ProcessModel(
    key="thermal_phase_change", name="Thermal phase change", version=VERSION,
    process_type="Thermal separation", category="Thermal phase change",
    manuscript_refs="Eq. (20), (21), Fig. 8",
    inputs=INPUTS, run=calculate, derive_defaults=derive_defaults,
)
