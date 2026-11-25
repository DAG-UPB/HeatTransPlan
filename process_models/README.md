# Process models

Energy demand models of industrial thermal processes. Enter a few process parameters, get the heat demand and the
hot and cold streams for the pinch analysis. The app finds the models by itself and uses only their `model.py`.

| Process | Folder | Version | Status | Manuscript |
|---|---|---|---|---|
| Pasteurization | [pasteurization/](process_models/pasteurization/) | 1.0 | implemented, validated | Eq. (18), (19), Fig. 7 |

## One folder per process

```
process_models/<process>/
  model.py           the model the app runs: INPUTS, calculate(), MODEL
  <process>.ipynb    imports model.py; example, figures, validation
  pid.svg            simplified P&ID, written by the notebook
  test_model.py      worked example as a check
  README.md          assumptions, sources, open points
  literature/        papers, data sheets
```

Every folder with a `model.py` that defines `MODEL` shows up in `process_models.PROCESSES`. Only the `.py` files
are packaged; notebooks, P&IDs and literature stay in the repository.

## Setup and checks

```bash
backend/.venv/bin/python -m pip install -e process_models
cd process_models && ../backend/.venv/bin/python -m pytest process_models
```
