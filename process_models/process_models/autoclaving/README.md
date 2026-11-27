# Autoclaving

**Version 1.0.** Fig. 1: *Thermal activation solid products › Autoclaving*. Manuscript section *Autoclaving*,
Eq. (12)–(14), Fig. 5 (p. 10–11), validation p. 18 (batch sterilization).

**Examples** (same model): sterilization (canned food, pet food, pharmaceutical products), hardening
(vulcanization, fiber reinforced plastics), boiling small scale (speciality canned vegetables, small scale meat or sea food).

Batch process: product, packaging and autoclave are heated from `T_start` to `T_steri` (12), held there (14) and
cooled to `T_final` (13).

| File | Content |
|---|---|
| `model.py` | the model the app runs |
| `autoclaving.ipynb` | canned food example, temperature and heat flow over a batch, figures, P&ID, validation |
| `pid.svg` | simplified P&ID of the example, written by the notebook |
| `test_model.py` | Eq. (12)–(14) by hand, losses, phase vs cycle duty, invalid inputs |

**Inputs:** required are the masses of product, packaging and autoclave, `cp_product`, `T_start`, `T_steri`,
`T_final` and the heating, holding and cooling times. Optional are `cp` of packaging and autoclave (default 0.50,
steel), heat losses (`A`, `U`, `T_amb`), utility flow and inlet temperature, `duty_basis` and `dT_latent`.

**Streams for the pinch analysis:** batch heating and holding (cold), batch cooling (hot). `duty_basis = "phase"`
(default) hands over the power of each phase, as in the manuscript; `"cycle"` spreads the energy per batch over the
cycle time. The phases do not run at the same time, so heat recovery between them needs storage (manuscript,
discussion).

**Assumptions:** `T_i` in the loss terms is the mean temperature of the phase (linear profile of Fig. 5); the cp of
packaging and autoclave default to steel, not from the manuscript.

**Open points:** no inputs are given for the validation case (62.65 MJ vs 63.18 MJ); it is not stated whether
62.65 MJ is heating only or heating + holding; the utility flow and inlet temperature are listed but not in Eq. (12)–(14).
