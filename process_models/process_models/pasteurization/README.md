# Pasteurization (continuous heating of fluids)

**Version 1.0**, manuscript section *Continuous heating of fluids*, Eq. (18), (19), Fig. 7.

The product is heated from `T_in` to the pasteurization temperature, held, and cooled to `T_out`. That gives one cold
stream (heating) and one hot stream (cooling) for the pinch analysis.

| File | Content |
|---|---|
| `model.py` | the model the app runs |
| `pasteurization.ipynb` | example, figures, P&ID, validation, comparison with the original notebook |
| `energy_demand_models (2).ipynb` | original notebook, unchanged; `model.py` gives the same results (5000 random cases) |
| `pid.svg` | simplified P&ID of the example, written by `pasteurization.ipynb` |
| `test_model.py` | manuscript example: 3135 kg/h, 4 → 90 → 4 °C, cp 3.89 kJ/(kg K) gives 291.3 kW |

**Inputs:** required are mass flow, `T_in`, `T_pasteur`, `T_out`. Optional are cp (product preset otherwise), safety
margin and heat losses (`A`, `U`, `T_amb`; no losses by default).

**Assumptions** (the manuscript leaves these open):
- `T_i` in the loss term is the mean temperature of the stage (time average for a linear profile).
- The holding time does not enter the energy demand.
- The cp presets are typical values, not from the manuscript.

**Open points in the manuscript:** the printed 456 kg/h does not give 291.3 kW (3135 kg/h does). `T_out` is not
stated. The relative deviation of 4.29 % refers to the model value, not the reference value.
