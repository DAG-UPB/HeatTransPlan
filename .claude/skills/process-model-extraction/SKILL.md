---
name: process-model-extraction
description: Turn a process energy demand model from a paper into a HeatTransPlan process model (model.py, notebook, test, README) following the existing six models. Use when the user puts literature into process_models/process_models/literature/ and asks to generate, extract, build or implement the model, or types /process-model-extraction.
---

# Extract a process model from literature

Reference implementations: `process_models/process_models/continuous_heating_of_fluid/` (with comparison against
an original notebook) and `process_models/process_models/thermal_phase_change/` (latent streams, two input
alternatives). Copy their structure and style; read `model.py`, the notebook and `test_model.py` before writing.

One folder per level-2 category of the manuscript's Fig. 1 (`process_models/README.md` shows the tree); the
level-3 processes (distillation, pasteurization, ...) are only examples listed at the top of the notebook and
README. All six level-2 categories of Fig. 1 are built (v1.0). Sources live in one shared folder,
`process_models/process_models/literature/` (the manuscript `manuscript_process_models.pdf` and a README with every
reference); there is no literature folder per category. Shared helpers: `humid_air.py` (moist air, drying models).
`continuous_bath_heating`/`convective_drying`/`conductive_drying`/`autoclaving` show the batch `duty_basis` choice,
moist-air cooling with condensation and generic notebook plots.

Phase change streams: the app's pinch analysis needs `T_supply != T_target`, so latent heat gets a small glide
input (`dT_latent`, default 1 K): evaporation above, condensation below the saturation temperature.

## 0  Get from the user (ask what is missing, one message)
- Folder name (lowercase, underscores: it is the import name) and the source file in the shared `literature/`.
- Which section / equations to implement.
- Worked example or validation numbers in the paper (inputs and expected result).
- Batch or continuous. For batch processes ask: time-averaged duty over the cycle (default, matches the
  steady-state pinch analysis) or peak duty.

## 1  Read the paper
- Read the whole section, its figure, and the validation part. PDFs: Read with `pages`; .docx: convert first.
- Never fill a gap silently. Collect everything the paper leaves open (undefined symbols, missing units, inputs
  in the list but not in the equations, numbers that do not reproduce) and ask the user. What is still open goes
  into the README under "Open points".

## 2  Extraction table (show it to the user before coding)
| Paper symbol | Meaning | Unit | Required? | Default + source | Paper reference |
- Required = the paper lists it as input and there is no sensible default.
- A default not taken from the paper is marked "not from manuscript" in the InputSpec note.
- One row per equation: equation number -> which function/term computes it.

## 3  Files to write (in `process_models/process_models/<name>/`)
1. `__init__.py`: empty.
2. `model.py`: standard library only (no numpy, pandas, matplotlib), so the app can run it.
   - `VERSION = "1.0"`
   - `INPUTS`: tuple of `InputSpec` from `process_models.base` (key, label, unit, required, symbol, default,
     example, kind/choices, ref, note).
   - `derive_defaults(values)` only if a default depends on other inputs.
   - A result dataclass with every term of every equation, `warnings`, `summary() -> list[dict]` and
     `stream_table() -> list[dict]` with exactly these keys per stream:
     `stream, type ("hot"|"cold"), T_supply_degC, T_target_degC, CP_kW_per_K, Q_kW`.
   - `calculate(values)`: one comment per equation with its number; raise `ValueError` with a clear message
     on impossible inputs (wrong temperature order, non-positive flows, negative demand).
   - `MODEL = ProcessModel(key, name, version, process_type, category, manuscript_refs, inputs, run, derive_defaults)`.
3. `<name>.ipynb` (build it with a small script in the scratchpad that writes the JSON; same sections as the reference
   notebooks):
   - first code cell with the fallback import:
     `try: import process_models` / `except ImportError: sys.path.insert(0, str(Path.cwd().parents[1]))`
   - 1 example with only the required inputs (input table, results, stream data)
   - 2 figures (demand breakdown, stream data, sensitivity) and a simplified P&ID, saved as `pid.svg`
   - 3 validation against the paper's numbers, with the open points in a markdown cell
   - 4 comparison with an existing implementation if there is one (old notebook, legacy code): run the old
     code unchanged in its own namespace and compare on fixed and random inputs, errors included.
4. `test_model.py`: the paper's worked example, one physical invariant (e.g. losses raise heating), one invalid input.
5. `README.md`: version, paper section and equations, inputs, assumptions, open points.
6. Add the source to `process_models/process_models/literature/README.md`: full citation, section, equations,
   pages. Norms: cite with page and year. Ask before committing a source that is not openly licensed.
7. Add a row to the table in `process_models/README.md`.

## 4  Verify (all must pass before reporting)
- `cd process_models && ../backend/.venv/bin/python -m pytest process_models`
- Run every notebook code cell headless from the process folder (no nbconvert installed):
  `../../../backend/.venv/bin/python -c "import json,matplotlib; matplotlib.use('Agg'); ns={'__name__':'__main__'}; [exec(c['source'] if isinstance(c['source'],str) else ''.join(c['source']), ns) for c in json.load(open('<name>.ipynb'))['cells'] if c['cell_type']=='code']"`
- `from process_models import PROCESSES` lists the new key (run from outside the repo root: there the outer
  folder shadows the package).
- Restore `pid.svg` with git if only the headless run rewrote it.

## Rules
- Never touch the user's literature or original notebooks; leave them byte for byte.
- No company, case or course names in code, notebook or README.
- Code and notebook in English. Do not commit or push unless the user asks.
- Report: extraction table, what was validated against which paper numbers, open points.
