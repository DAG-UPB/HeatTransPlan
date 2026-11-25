"""Shared framework for all process models: input description, model entry, input resolution.

Taken from energy_demand_models (2).ipynb, section 1. Plain Python (no pandas), so the app can use it as is.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class InputSpec:
    """Description of ONE model input. Drives validation, defaults, audit table and the UI form."""
    key: str                          # python argument name
    label: str                        # human-readable description
    unit: str
    required: bool                    # True = must be given, False = default is used if missing
    symbol: str = ""                  # symbol as used in the manuscript
    default: Optional[object] = None  # default for optional inputs (None = derived, see derive_defaults)
    example: Optional[object] = None  # pre-filled value in the UI
    kind: str = "float"               # "float" | "choice"
    choices: tuple = ()
    ref: str = ""                     # where the input is introduced in the manuscript
    note: str = ""


@dataclass(frozen=True)
class ProcessModel:
    """One selectable process. Each process folder's model.py defines one as MODEL."""
    key: str
    name: str
    version: str
    process_type: str                 # level 1 of manuscript Fig. 1
    category: str                     # level 2 of manuscript Fig. 1
    manuscript_refs: str
    inputs: tuple
    run: Callable                     # run(values: dict) -> result object with stream_table()
    derive_defaults: Optional[Callable] = None  # values -> {key: (value, source_text)}


def resolve_inputs(model: ProcessModel, user_values: dict):
    """Check required inputs, fill optional ones with defaults and return (values, audit rows)."""
    specs = {s.key: s for s in model.inputs}
    unknown = set(user_values) - set(specs)
    if unknown:
        raise KeyError(f"Unknown input(s) for '{model.key}': {sorted(unknown)}")

    values, source, missing = {}, {}, []
    for s in model.inputs:
        v = user_values.get(s.key)
        if v is None:
            if s.required:
                missing.append(s.key)
                continue
            values[s.key] = s.default
            source[s.key] = "default" if s.default is not None else "derived default"
        else:
            if s.kind == "float":
                v = float(v)
            elif s.kind == "choice" and v not in s.choices:
                raise ValueError(f"'{s.key}' must be one of {list(s.choices)}, got {v!r}")
            values[s.key] = v
            source[s.key] = "user input"
    if missing:
        raise ValueError(f"Missing required input(s): {missing}")

    if model.derive_defaults is not None:
        for k, (val, src) in model.derive_defaults(values).items():
            if values.get(k) is None:
                values[k], source[k] = val, src

    audit = [{
        "Symbol": s.symbol, "Input": s.label, "Value": values[s.key], "Unit": s.unit,
        "Type": "required" if s.required else "optional", "Source": source[s.key],
        "Manuscript / note": " | ".join(x for x in (s.ref, s.note) if x),
    } for s in model.inputs]
    return values, audit
