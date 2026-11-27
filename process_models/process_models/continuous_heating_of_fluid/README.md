# Continuous heating of fluid

**Version 1.0.** Fig. 1: *Thermal activation of fluid products › Continuous heating of fluid*. Manuscript section
*Continuous heating of fluids*, Eq. (18), (19), Fig. 7 (p. 12–13), validation p. 18–19.

**Examples** (same model): pasteurization (dairy products, beverages, fruit juice, tea and coffee concentrate),
continuous sterilization (cream and sauces, liquid pharmaceuticals, UHT milk).

The product is heated from `T_in` to the process temperature `T_process` (`T_pasteur` in the manuscript), held,
and cooled to `T_out`. That gives one cold stream (heating) and one hot stream (cooling) for the pinch analysis.

| File | Content |
|---|---|
| `model.py` | the model the app runs |
| `continuous_heating_of_fluid.ipynb` | example, figures, P&ID, validation, comparison with the original notebook |
| `energy_demand_models_notebook_1.ipynb` | original notebook (written for pasteurization), unchanged; `model.py` gives the same results (5000 random cases), except that it rejects a negative heating demand |
| `pid.svg` | simplified P&ID of the example, written by the notebook |
| `test_model.py` | manuscript example: 3135 kg/h, 4 → 90 → 4 °C, cp 3.89 kJ/(kg K) gives 291.3 kW |

**Inputs:** required are mass flow, `T_in`, `T_process`, `T_out`. Optional are cp (product preset otherwise),
safety margin and heat losses (`A`, `U`, `T_amb`; no losses by default).

**Assumptions** (the manuscript leaves these open):
- `T_i` in the loss term is the mean temperature of the stage (time average for a linear profile).
- The holding time does not enter the energy demand.
- The cp presets are typical values, not from the manuscript.

**Open points in the manuscript:** the printed 456 kg/h does not give 291.3 kW (3135 kg/h does). `T_out` is not
stated. The relative deviation of 4.29 % refers to the model value, not the reference value.
