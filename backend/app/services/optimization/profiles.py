"""Source and sink curves: cleaning, temperature grid, partial heat recovery."""

from __future__ import annotations
import numpy as np
import pandas as pd

from app.models.analysis import PinchResult
from app.services import pinch_figures


def _prepare_xy_curve(x, y, is_source=False):
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    
    if len(x) == 0:
        return np.array([]), np.array([])
        
    df_curve = pd.DataFrame({"x": x, "y": y})
    if is_source:
        df_curve = df_curve.sort_values(by=["x", "y"], ascending=[True, False]).reset_index(drop=True)
    else:
        df_curve = df_curve.sort_values(by=["x", "y"], ascending=[True, True]).reset_index(drop=True)
        
    x_vals = df_curve["x"].to_numpy(copy=True)
    for i in range(1, len(x_vals)):
        if x_vals[i] <= x_vals[i-1]:
            x_vals[i] = x_vals[i-1] + 1e-6
            
    df_curve["x"] = x_vals
    return df_curve["x"].to_numpy(dtype=float), df_curve["y"].to_numpy(dtype=float)


def _make_temperature_grid(T_min, T_max, step=1.0):
    if T_max < T_min:
        return np.array([])
    return np.arange(T_min, T_max + step * 0.5, step, dtype=float)


def _unrecovered_heat(pinch: PinchResult, recovery_pct: float) -> float:
    """Heat not recovered at the given share of the maximum recovery, kW.

    Each kW not recovered has to be heated in above the pinch and cooled away
    below it, so it flows through the pinch: the whole GCC moves right by this
    much (app/services/pinch_figures.py).
    """
    return pinch_figures.unrecovered_heat(pinch, recovery_pct)


def _shift(curve: dict, d: float) -> dict:
    return {**curve, "H": [float(h) + d for h in curve["H"]]}
