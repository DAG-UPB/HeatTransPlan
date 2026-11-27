# Process models

Energy demand models of industrial thermal processes. Enter a few process parameters, get the heat demand and the
hot and cold streams for the pinch analysis. The app finds the models by itself and uses only their `model.py`.

One folder per process category (level 2 of the manuscript's Fig. 1, *Classification of Industrial Thermal
Processes*). The processes below each category (distillation, pasteurization, ...) are examples of the same model.

```
Industrial thermal processes
├── Drying
│   ├── convective_drying/              v1.0   spray, granulate, ring, flash drying
│   └── conductive_drying/              v1.0   belt, textile, contact drum drying
├── Thermal activation solid products
│   ├── autoclaving/                    v1.0   sterilization, hardening, boiling small scale
│   └── continuous_bath_heating/        v1.0   galvanization, washing, boiling large scale
├── Thermal activation fluid products
│   └── continuous_heating_of_fluid/    v1.0   pasteurization, continuous sterilization
└── Thermal separation
    └── thermal_phase_change/           v1.0   distillation, evaporation, stripping

literature/                             the manuscript and the references of all categories
humid_air.py                            moist-air properties, shared by the two drying models
```

| Category | Folder | Manuscript | Validation against the manuscript |
|---|---|---|---|
| Convective drying | [convective_drying/](process_models/convective_drying/) | Eq. (3)–(9), Fig. 3 | spray dryer inputs: 11,056.6 kW vs reference 11,134.4 kW (−0.70 %); outlet temperature needs an unstated UA-value |
| Conductive drying | [conductive_drying/](process_models/conductive_drying/) | Eq. (5), (9)–(11), Fig. 4 | evaporation demand 7,724 kW reproduced; surface temperature and cp of the wet product not given |
| Autoclaving | [autoclaving/](process_models/autoclaving/) | Eq. (12)–(14), Fig. 5 | inputs of the batch case not given |
| Continuous bath heating | [continuous_bath_heating/](process_models/continuous_bath_heating/) | Eq. (15)–(17), Fig. 6 | inputs of the bath case not given |
| Continuous heating of fluid | [continuous_heating_of_fluid/](process_models/continuous_heating_of_fluid/) | Eq. (18), (19), Fig. 7 | pasteurization case reproduced (291.3 kW) |
| Thermal phase change | [thermal_phase_change/](process_models/thermal_phase_change/) | Eq. (20), (21), Fig. 8 | inputs of the distillation case not given |

All models are version 1.0. Each README lists the open points found in the manuscript.

## One folder per process category

```
process_models/<category>/
  model.py           the model the app runs: INPUTS, calculate(), MODEL
  <category>.ipynb   imports model.py; examples, figures, P&ID, validation
  pid.svg            simplified P&ID, written by the notebook
  test_model.py      worked example and checks
  README.md          examples, assumptions, open points
```

Every folder with a `model.py` that defines `MODEL` shows up in `process_models.PROCESSES`. Only the `.py` files
are packaged; notebooks, P&IDs and literature stay in the repository.
The manuscript and the references of all categories are in [process_models/literature/](process_models/literature/).

## Setup (Python 3.11 or newer)

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -e "process_models[notebook,dev]"     # Windows: .venv\Scripts\pip
```

Then open a notebook and pick this `.venv` as the kernel (the notebooks also run without installing, with any
kernel that has numpy, pandas and matplotlib). Tests: `cd process_models && ../.venv/bin/python -m pytest process_models`.

With the app's backend venv instead: `backend/.venv/bin/python -m pip install -e "process_models[notebook,dev]"`.
