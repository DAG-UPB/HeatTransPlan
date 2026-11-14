"""The optimization's balance for one operating point, as the heat pump view
shows it while the temperatures are tried out by hand (search.py does the same
along the whole grid).

For a sink temperature the demand is read off the sink profile; the COP says
how much of it must come from waste heat; the source profile says how much
waste heat there is down to the source temperature. The optimizer keeps the
points where the two match.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

import numpy as np


def profile_at(H: Sequence[float], T: Sequence[float], t: float) -> Optional[float]:
    """The profile's duty at a temperature: linear between points, held at the
    ends (numpy's interp, as the optimizer reads it). T ascending."""
    if len(T) == 0 or len(H) == 0:
        return None
    return float(np.interp(t, np.asarray(T, dtype=float), np.asarray(H, dtype=float)))


def balance(q_sink: float, cop: float, q_available: float) -> Optional[Dict[str, Any]]:
    """Waste heat needed for the whole sink duty against what is there.
    Within 1 % (at least 1 kW) counts as on both profiles. None when the COP
    or the duty make no balance (COP <= 1, no duty)."""
    if not (cop > 1) or not (q_sink > 0):
        return None
    needed = q_sink * (cop - 1) / cop
    gap = q_available - needed
    tolerance = max(1.0, 0.01 * needed)
    state = "balanced" if abs(gap) <= tolerance else ("source_limited" if gap < 0 else "demand_limited")
    return {
        "needed": needed,
        "p_el": q_sink / cop,
        "gap": gap,
        "state": state,
        "q_sink_possible": min(q_sink, q_available * cop / (cop - 1)),
    }


def point_balance(cop: float, source_profile, sink_profile, t_source: float, t_sink: float,
                  q_sink_default: Optional[float] = None) -> Dict[str, Any]:
    """Demand off the sink profile at t_sink (q_sink_default where there is
    no profile), waste heat off the source profile at t_source, and the
    balance of the two at this COP."""
    q_sink = profile_at(sink_profile.H, sink_profile.T, t_sink) if sink_profile else None
    if q_sink is None:
        q_sink = q_sink_default
    q_available = profile_at(source_profile.H, source_profile.T, t_source) if source_profile else None
    bal = balance(q_sink, cop, q_available) if q_sink is not None and q_available is not None else None
    return {"q_sink": q_sink, "q_available": q_available, "balance": bal}
