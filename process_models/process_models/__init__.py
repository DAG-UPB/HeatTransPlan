"""Energy demand models of industrial thermal processes.

Every subfolder with a model.py is one process; model.py defines MODEL (a ProcessModel).
The app only uses PROCESSES and run_process(); notebooks, P&IDs and literature are not imported.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from .base import InputSpec, ProcessModel, resolve_inputs

PROCESSES: dict[str, ProcessModel] = {}
for _m in pkgutil.iter_modules(__path__):
    if _m.ispkg and (Path(__path__[0]) / _m.name / "model.py").exists():
        _model = importlib.import_module(f"{__name__}.{_m.name}.model").MODEL
        PROCESSES[_model.key] = _model


def run_process(key: str, **inputs):
    """Run a process model. Returns (result, audit rows)."""
    model = PROCESSES[key]
    values, audit = resolve_inputs(model, inputs)
    return model.run(values), audit


__all__ = ["InputSpec", "ProcessModel", "PROCESSES", "resolve_inputs", "run_process"]
