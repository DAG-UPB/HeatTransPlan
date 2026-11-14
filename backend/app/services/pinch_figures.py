"""Figures derived from a pinch result: what the hot streams give off, the
maximum heat recovery, the utilities at a chosen share of that recovery, and
the pockets of the grand composite curve.

The single place these are computed. PinchResult carries the ones that do not
depend on the share (total_hot_duty, max_heat_recovery, gcc_pockets); the page
reads them from there. The share-dependent ones (at_recovery_share) are used by
the optimization and the report; the page's slider applies the same formula
(frontend/src/components/analysis/recoveryShare.ts), held to the same answers
by tests/fixtures/recovery_share_reference.json.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

EPS = 1e-6


def total_hot_duty(streams_data: Iterable[Dict[str, Any]]) -> float:
    """Heat the hot streams give off, kW (streams_data of a pinch result)."""
    return sum(
        abs(float(s["cp"]) * (float(s["tt"]) - float(s["ts"])))
        for s in streams_data
        if float(s["ts"]) > float(s["tt"])
    )


def max_heat_recovery(streams_data: Iterable[Dict[str, Any]], cold_utility: float) -> float:
    """Heat recovered between streams at full recovery: what the hot streams
    give off, less what still has to be cooled away. Never below 0."""
    return max(total_hot_duty(streams_data) - float(cold_utility), 0.0)


def unrecovered_heat(pinch: Any, recovery_pct: float) -> float:
    """Heat not recovered when only recovery_pct % of the maximum heat
    recovery is credited, kW."""
    return (1.0 - float(recovery_pct) / 100.0) * max_heat_recovery(pinch.streams_data, pinch.cold_utility)


def at_recovery_share(pinch: Any, recovery_pct: float) -> Dict[str, float]:
    """Utilities and recovery when only recovery_pct % of the maximum heat
    recovery is credited. Each kW not recovered has to be heated in above the
    pinch and cooled away below it, on top of the pinch minimums."""
    maximum = max_heat_recovery(pinch.streams_data, pinch.cold_utility)
    unrecovered = unrecovered_heat(pinch, recovery_pct)
    return {
        "unrecovered": unrecovered,
        "hot_utility": float(pinch.hot_utility) + unrecovered,
        "cold_utility": float(pinch.cold_utility) + unrecovered,
        "heat_recovery": maximum - unrecovered,
    }


# ── Pockets of the grand composite curve ────────────────────────────────────
#
# Moving away from the pinch, the GCC should only move right: above the pinch
# every interval needs heat, below it every interval has heat to spare. Where
# it turns back left, an interval with the opposite balance sits next to it and
# the two exchange heat internally: a pocket. Closing it with a vertical line
# gives the pocketless profile, the envelope
#
#   above the pinch:  env(T) = min { H(T') : T' >= T }
#   below the pinch:  env(T) = min { H(T') : T' <= T }
#
# and the pocket is the area between the curve and that envelope.


def _side(pts: List[Tuple[float, float]], out: Dict[str, Any]) -> None:
    """Pockets on one side of the pinch. pts run from the far end towards the
    pinch, so the running minimum of H is the envelope."""
    # The curve refined with the points where it crosses the envelope level,
    # so each pocket closes exactly on its vertical line.
    curve: List[Tuple[float, float, float]] = []  # H, T, envelope
    m = float("inf")
    for k, (h, t) in enumerate(pts):
        if k > 0:
            h0, t0 = pts[k - 1]
            if (h0 - m) * (h - m) < 0:
                f = (m - h0) / (h - h0)
                curve.append((m, t0 + f * (t - t0), m))
        m = min(m, h)
        curve.append((h, t, m))

    # Each run where the curve stands right of the envelope is one pocket:
    # along the curve, then back down the envelope's vertical line.
    run: List[Tuple[float, float, float]] = []

    def close() -> None:
        nonlocal run
        if len(run) > 2:
            width = max(h - e for h, _, e in run)
            if width > EPS:
                out["x"].extend([h for h, _, _ in run] + [e for _, _, e in reversed(run)] + [None])
                out["y"].extend([t for _, t, _ in run] + [t for _, t, _ in reversed(run)] + [None])
                out["heat"] += width
        run = []

    prev: Optional[Tuple[float, float, float]] = None
    for p in curve:
        inside = p[0] - p[2] > EPS
        # A pocket opens at the last point on the envelope before it.
        if inside and not run and prev is not None:
            run.append(prev)
        if inside or run:
            run.append(p)
        if not inside and run:
            close()
        prev = p
    close()


def gcc_pockets(H: List[float], T: List[float], pinch_t: float) -> Dict[str, Any]:
    """Polygons of the pockets for a Plotly 'toself' fill, one per pocket,
    separated by None (x, y), and the heat exchanged inside them: the summed
    width of each pocket, kW (heat)."""
    pts = [(float(h), float(t)) for h, t in zip(H, T)]
    out: Dict[str, Any] = {"x": [], "y": [], "heat": 0.0}
    # Above the pinch from the top down, below it from the bottom up. Python's
    # sort is stable, as JavaScript's: equal temperatures keep their order.
    _side(sorted((p for p in pts if p[1] >= pinch_t - EPS), key=lambda p: -p[1]), out)
    _side(sorted((p for p in pts if p[1] <= pinch_t + EPS), key=lambda p: p[1]), out)
    return out
