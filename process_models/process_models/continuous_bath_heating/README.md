# Continuous bath heating

**Version 1.0.** Fig. 1: *Thermal activation solid products › Continuous bath heating*. Manuscript section
*Continuous bath heating*, Eq. (15)–(17), Fig. 6 (p. 11–12), validation p. 18.

**Examples** (same model): galvanization (steel sheets and coils, wires, pipes and tubing), washing (cotton and
synthetic fabrics, denim, nonwoven fabrics), boiling large scale (vegetables, precooked pasta, meat and sea food,
fruits for freezing).

A bath is kept at `T_bath`. Its heat demand is the product dipped into it (15) plus the losses through the walls
(16) and from the open surface by convection and radiation (17).

| File | Content |
|---|---|
| `model.py` | the model the app runs |
| `continuous_bath_heating.ipynb` | hot-dip bath example, figures, P&ID, validation |
| `pid.svg` | simplified P&ID of the example, written by the notebook |
| `test_model.py` | Eq. (15)–(17) by hand, utility return temperature, invalid inputs |

**Inputs:** required are product flow, `cp_product`, product inlet temperature, `T_bath`, `A_surface`, `A_wall`
(in Eq. (16), not in the input list), `U_bath`, `T_amb` and `alpha`. Optional are the emissivity (default 0.95),
utility flow, inlet temperature and cp (gives the utility return temperature) and `dT_latent`.

**Streams for the pinch analysis:** one cold stream, the bath heating at `T_bath` (1 K glide). The model has no
cooling demand.

**Open points:** no inputs are given for the validation case (1,142.37 kW vs 1,196.17 kW); Eq. (15) is written with a
mass and an energy (used here with a mass flow); `A_wall` and `ε` are not in the input list; surface evaporation is
mentioned in the text but is not in Eq. (17); the sum of Eq. (15)–(17) is not stated explicitly.
