# Convective drying

**Version 1.0.** Fig. 1: *Drying › Convective drying*. Manuscript section *Convective drying*, Eq. (3)–(9), Fig. 3
(p. 7–9), validation p. 17 (spray dryer, Table 1).

**Examples** (same model): spray drying (milk, coffee, egg powder, whey protein), granulate drying (plastic
granulates, pharmaceutical granules, silica gel), ring drying (soya products, casein, Epsom salt, calcium carbonate,
paper sludge), flash drying (starch, potato and sauce powder, silicates).

Air is heated from `T0` to `T1` at constant humidity (3), takes up the water removed from the product (4), (5) and
leaves at `T2` (6). The outlet air is cooled to `T3`: sensibly to its dew point (7), then with condensation (8), (9).
Moist-air properties: `process_models/humid_air.py`.

| File | Content |
|---|---|
| `model.py` | the model the app runs |
| `convective_drying.ipynb` | spray dryer with the manuscript's inputs, figures, P&ID, validation |
| `pid.svg` | simplified P&ID of the example, written by the notebook |
| `test_model.py` | Eq. (3)–(9) on the manuscript's inputs, losses, invalid inputs |

**Inputs:** required are product flow, `w1`, `w2`, air flow (dry air), `T0`, `T1`, `x0`. Optional are the return
temperature `T3` (default `T0`), the UA-value of the dryer, `T_amb` and the pressure.

**Streams for the pinch analysis:** air heating (cold), outlet air to the dew point and condensation (hot).

**Assumptions:** `m_air` is dry air; `T_average` in Eq. (6) is the mean of `T1` and `T2`; moist air as an ideal
gas mixture (cp 1.006 / 1.86 kJ/(kg K), h_v 2501 kJ/kg, Magnus formula), not from the manuscript.

**Validation and open points** (details in the notebook):
- Energy demand: this model 11,056.6 kW, reference 11,134.4 kW (−0.70 %). The manuscript's 10,915.81 kW is exactly
  55.7 · 1.005 · 195, i.e. dry air only.
- Outlet temperature: Eq. (6) without losses gives 132.5 °C, not 77.9 °C; it needs a dryer UA-value of about
  26.3 kW/K, which the manuscript does not state.
- Outlet humidity: Eq. (5) gives 35.16 g/kg, the reference 34.35 g/kg.
- Not stated: dry or moist air flow, basis of `w`, `T_average`.
