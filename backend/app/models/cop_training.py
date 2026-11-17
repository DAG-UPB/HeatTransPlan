"""Models of the COP training module (app/services/cop_training)."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

# The temperatures a model can read. Training maps only the two outlets (the
# 2-temperature model); the inlets stay accepted for models trained earlier.
# In the order the network sees them, the same as the shipped models
# (Vorlauf Quelle, Rücklauf Quelle, Rücklauf Senke, Vorlauf Senke), so the
# same data trains the same network.
TEMP_ROLES = ["T_source_in", "T_source_out", "T_sink_in", "T_sink_out"]

# Sink temperatures above this are not offered by default, whatever the data
# holds: no heat pump on the market delivers them. The user can set the range.
SINK_CAP = 180.0
CAT_ROLES = ["medium", "refrigerant", "stages"]

# Where a user may say a formula or a trained model is valid (°C, COP): no heat
# pump works outside it, and a wider envelope only makes the search bigger.
ENVELOPE_T_MIN = -100.0
ENVELOPE_T_MAX = 500.0
ENVELOPE_COP_MAX = 100.0
# Distinct values per category column. Each becomes a network input and every
# combination a heat pump, so a column of free text would blow both up.
MAX_CATEGORIES = 50
# Weights of a network sent back for the search. The shipped set-up (two hidden
# layers of 128 and 64) has about 10,000; each one is paid at every grid point.
MAX_NETWORK_WEIGHTS = 100_000


class ColumnMapping(BaseModel):
    """Which column of the uploaded table holds what."""
    T_source_out: str  # source return: heat source leaving the evaporator, °C
    T_sink_out: str  # sink supply: heat leaving the condenser, °C
    COP: str
    medium: Optional[str] = None  # sink medium (water, steam, ...)
    refrigerant: Optional[str] = None
    stages: Optional[str] = None  # number of compressors / stages


class Layer(BaseModel):
    W: List[List[float]]
    b: List[float]


class Term(BaseModel):
    """coef · Π T_role^power, a term of a regression."""
    coef: float
    powers: Dict[str, int] = Field(default_factory=dict)


class CustomCopModelSpec(BaseModel):
    """A trained model as plain numbers, so it can travel with a request and
    be evaluated without loading any code: a neural network (layers, on
    standardised temperatures) or a linear / polynomial regression (terms on
    the temperatures in °C, plus an offset per category value)."""
    name: str = Field("My COP model", max_length=60)
    enabled: bool = True
    kind: Literal["nn", "poly", "linear"] = "nn"
    temps: List[str] = Field(max_length=len(TEMP_ROLES))  # input temperature roles, in order
    cats: List[str] = Field(default_factory=list, max_length=len(CAT_ROLES))  # categorical roles, in order
    mean: List[float] = Field(max_length=len(TEMP_ROLES))
    scale: List[float] = Field(max_length=len(TEMP_ROLES))
    categories: Dict[str, List[str]] = Field(default_factory=dict, max_length=len(CAT_ROLES))
    layers: List[Layer] = Field(default_factory=list, max_length=6)
    terms: List[Term] = Field(default_factory=list, max_length=200)
    offsets: Dict[str, Dict[str, float]] = Field(default_factory=dict, max_length=len(CAT_ROLES))
    # The regression written out, for people; predict() uses terms/offsets.
    formula: str = Field("", max_length=8000)
    # Where the model is offered: by default the training data's range with the
    # sink capped (SINK_CAP); the user may set it, data_envelope keeps the data's.
    envelope: Dict[str, float] = Field(max_length=16)
    data_envelope: Dict[str, float] = Field(default_factory=dict, max_length=16)
    # Medium / refrigerant / stages combinations present in the data; each
    # becomes one heat pump in the optimization.
    combos: List[Dict[str, str]] = Field(default_factory=lambda: [{}], max_length=200)
    metrics: Dict[str, float] = Field(default_factory=dict, max_length=32)

    @model_validator(mode="after")
    def _shapes(self):
        if not {"T_source_out", "T_sink_out"} <= set(self.temps) or not set(self.temps) <= set(TEMP_ROLES):
            raise ValueError("temps must hold T_source_out and T_sink_out, optionally T_source_in and T_sink_in")
        if not set(self.cats) <= set(CAT_ROLES):
            raise ValueError(f"cats must be among {CAT_ROLES}")
        if len(self.mean) != len(self.temps) or len(self.scale) != len(self.temps):
            raise ValueError("mean and scale need one value per temperature")
        if any(len(v) > MAX_CATEGORIES for v in self.categories.values()) or any(
                len(v) > MAX_CATEGORIES for v in self.offsets.values()):
            raise ValueError(f"at most {MAX_CATEGORIES} values per category")
        if self.kind == "nn":
            width = len(self.temps) + sum(len(self.categories.get(c, [])) for c in self.cats)
            if not self.layers:
                raise ValueError("a network needs layers")
            for layer in self.layers:
                if len(layer.W) != width or any(len(row) != len(layer.b) for row in layer.W) or len(layer.b) > 512:
                    raise ValueError("layer shapes do not fit together")
                width = len(layer.b)
            if width != 1:
                raise ValueError("the last layer must have one output")
            if sum(len(layer.W) * len(layer.b) for layer in self.layers) > MAX_NETWORK_WEIGHTS:
                raise ValueError(f"the network has more than {MAX_NETWORK_WEIGHTS:,} weights")
        else:
            if not self.terms:
                raise ValueError("a regression needs terms")
            for term in self.terms:
                if not set(term.powers) <= set(self.temps) or any(not 0 <= p <= 3 for p in term.powers.values()):
                    raise ValueError("terms may only raise the model's temperatures to powers 0–3")
            if not set(self.offsets) <= set(self.cats):
                raise ValueError("offsets only for the model's categories")
        for key in ("T_source_min", "T_source_max", "T_sink_min", "T_sink_max", "cop_min", "cop_max"):
            if key not in self.envelope:
                raise ValueError(f"envelope needs {key}")
        for lo, hi in (("T_source_min", "T_source_max"), ("T_sink_min", "T_sink_max"), ("cop_min", "cop_max")):
            if self.envelope[lo] > self.envelope[hi]:
                raise ValueError(f"envelope: {lo} is above {hi}")
        for key in ("T_source_min", "T_source_max", "T_sink_min", "T_sink_max"):
            if not ENVELOPE_T_MIN <= self.envelope[key] <= ENVELOPE_T_MAX:
                raise ValueError(f"envelope: {key} must lie between {ENVELOPE_T_MIN} and {ENVELOPE_T_MAX} °C")
        for key in ("cop_min", "cop_max"):
            if not 0 <= self.envelope[key] <= ENVELOPE_COP_MAX:
                raise ValueError(f"envelope: {key} must lie between 0 and {ENVELOPE_COP_MAX}")
        return self
