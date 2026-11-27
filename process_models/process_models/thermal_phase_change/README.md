# Thermal phase change

**Version 1.0.** Fig. 1: *Thermal separation › Thermal phase change*. Manuscript section *Thermal phase change*,
Eq. (20), (21), Fig. 8 (p. 13–14), validation p. 19 and 23.

**Examples** (same model, the equations do not change): distillation (alcohol, beverages, chemical solvents,
essential oils, purified water), evaporation (fruit juice concentrate, milk and whey concentrate, sugar syrup),
stripping (oil and gas, ammonia, phenol).

A liquid feed is heated to its boiling temperature `T_v`, the component with the lower boiling point (mass
fraction `w`) is evaporated, then condensed, and both products are cooled to `T_out`.

| File | Content |
|---|---|
| `model.py` | the model the app runs |
| `thermal_phase_change.ipynb` | examples (distillation, evaporation), figures, P&ID, validation, consistency checks |
| `pid.svg` | simplified P&ID of the distillation example, written by the notebook |
| `test_model.py` | Eq. (20)/(21) by hand, energy balance, `w` or evaporated flow, invalid inputs |

**Inputs:** required are feed mass flow, `T_in`, `T_v`, `T_out` and cp of the residue, plus `w` *or* the
evaporated mass flow. Optional are the evaporated component (presets for cp and `h_v`: water, ethanol, methanol),
cp of the evaporated component, `h_v`, utility inlet and outlet temperature and the latent glide `dT_latent`.

**Streams for the pinch analysis:** feed preheating (cold), evaporation (cold, `T_v` → `T_v + dT_latent`),
condensation (hot, `T_v` → `T_v − dT_latent`), product cooling (hot). Their duties add up to Eq. (20) and (21).

**Assumptions:**
- One boiling temperature `T_v` for evaporation and condensation, no reflux, no heat losses (as in the manuscript).
- The latent heat is spread over `dT_latent` (default 1 K), because the pinch analysis needs `T_supply ≠ T_target`.
  Not from the manuscript.
- The cp and `h_v` presets are typical values at the normal boiling point, not from the manuscript.

**Open points in the manuscript:**
- No inputs are given for the distillation validation case (1,395.77 vs 1,787.40), so it cannot be recalculated.
  The legacy `classes.DistillationEnergyDemand` or its example would close this.
- p. 19 gives the validation numbers in kW, p. 23 in kJ/kg; the kJ/kg basis (feed or distillate) is not stated.
- 28.06 % is relative to the model value; relative to the reference it is 21.91 %.
- The deviation is put down to missing heat losses; Fig. 8 shows a UA-value of the column, but Eq. (20)/(21) have no loss term.
- Utility inlet and outlet temperatures are listed as inputs but are not in Eq. (20)/(21).
