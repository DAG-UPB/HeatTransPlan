# Conductive drying

**Version 1.0.** Fig. 1: *Drying › Conductive drying*. Manuscript section *Conductive drying*, Eq. (10), (11), (5),
(7)–(9), Fig. 4 (p. 9–10), validation p. 18 (paper drying, Table 2) and p. 20.

**Examples** (same model): belt drying (fruit pieces, vegetable flakes, pharmaceutical powders, ceramics), textile
drying (cotton and synthetic fabrics, towels and linens), contact drum drying (paper, baby food, food pastes,
gelatin, yeast extract).

The wet product is heated to the surface temperature (10) and its moisture evaporates there (11). An air stream
carries the vapour away (5); its outlet is cooled to `T3` like in convective drying (7)–(9).

| File | Content |
|---|---|
| `model.py` | the model the app runs |
| `conductive_drying.ipynb` | paper drying with the manuscript's inputs, figures, P&ID, validation |
| `pid.svg` | simplified P&ID of the example, written by the notebook |
| `test_model.py` | Eq. (10), (11), (5), (9) by hand, the manuscript's 7,724 kW evaporation demand, invalid inputs |

**Inputs:** required are product flow, `w_in`, `w_out`, `T_surface`, product inlet temperature and `cp_wet` (both in
Eq. (10), not in the input list), air flow (dry air), `T1`, `x1` and the air outlet temperature `T2` ("must be known").
Optional are `h_v` (default 2501 − 2.37 · `T_surface`), `T3` (default `T1`), `dT_latent` and the pressure.

**Streams for the pinch analysis:** product heating and evaporation at the surface (cold, evaporation with a 1 K
glide), outlet air to the dew point and condensation (hot).

**Validation and open points** (details in the notebook):
- Evaporation demand reproduced: 7,724.6 kW with `h_v` at 135 °C (manuscript p. 20: 7,724 kW).
- Surface temperature, product inlet temperature and `cp_wet` are not given; with 135 °C (Fig. 12) and 15 °C the
  9,472 kW need `cp_wet` = 1.75 kJ/(kg K).
- The reference outlet moisture 120.0 g/kg is exactly the water taken up, without the inlet humidity (Eq. (5): 126.4 g/kg).
- Eq. (7)–(9) give about 9,650 kW cooling from 70 °C to 25 °C, not the 2,227 kW of p. 20.
- The printed RMSE is 525.25 kW, but |9,472.00 − 9,996.25| = 524.25 kW.
- The heating of the air from `T1` to `T2` inside the dryer is not part of Eq. (10)/(11).
