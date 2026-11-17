"""The project as CSV: one row per stream, the distances between the
processes, and reading the stream CSV back into a project.

The one CSV format of the app. The page's "Export CSV" button, the page's
export_csv command and the MCP server's export_csv tool all get it from here
(POST /api/io/export-csv), and POST /api/io/import-csv reads it back.

The format is the one the page wrote before it moved here (semicolon
separated, every cell quoted; the values in °C, kg/s, kJ/(kg·K), kW/K and kW,
read the way the analysis reads them). The page's JavaScript decided what an
empty or missing value is, so the helpers below follow its rules (_truthy,
_or, _number, _js_str): the same project gives the same file as before.
"""

from __future__ import annotations

import csv
import io
import math
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.services.project_analysis import stream_info
from app.utils.geo_utils import haversine_distance, manhattan_spherical_distance

HEADER = [
    "Name", "Heat Capacity", "Mass Flow", "CP-Value [kW/K]", "Input Temperature [°C]",
    "Output Temperature [°C]", "Stream Type", "Process", "Subprocess", "Q (kW)", "Lat", "Lon",
    "Hours", "Water In", "Water Out", "Density", "Pressure", "Notes",
]
# Between a subprocess and its sub-subprocess in the Subprocess column.
CHILD_SEP = " › "

_MISSING = object()  # a key that is not there (JavaScript's undefined)

# The project comes in as sent, and a process group may list one subprocess
# any number of times: without a cap a small body asks for a huge file.
#   distance matrix: n² cells, so 500 subprocesses are 250,000 distances
#   stream CSV: a large site has a few hundred streams
MAX_DISTANCE_NODES = 500
MAX_CSV_ROWS = 100_000


class ProjectTooLarge(ValueError):
    """The project would give a file larger than the limits above."""


# ── JavaScript's value rules ────────────────────────────────────────────────


def _truthy(v: Any) -> bool:
    if v is None or v is _MISSING or v is False or v == "" or (isinstance(v, (int, float)) and v == 0):
        return False
    return not (isinstance(v, float) and math.isnan(v))


def _or(*values: Any) -> Any:
    """a || b || c: the first truthy value, else the last."""
    for v in values[:-1]:
        if _truthy(v):
            return v
    return values[-1]


def _number(v: Any) -> float:
    """JavaScript's Number(v)."""
    if v is _MISSING:
        return math.nan
    if v is None or v is False:
        return 0.0
    if v is True:
        return 1.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        t = v.strip()
        if not t:
            return 0.0
        try:
            return float(t) if re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?|[+-]?Infinity", t) else math.nan
        except ValueError:
            return math.nan
    return math.nan


def _num_str(x: float) -> str:
    """JavaScript's String(number): the shortest digits that read back the
    same (as Python's repr), laid out the way JavaScript lays them out."""
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    digits, exp = Decimal(repr(abs(x))).normalize().as_tuple()[1:]
    s = "".join(map(str, digits))
    k = len(s)
    n = k + exp  # value = 0.s × 10^n
    if k <= n <= 21:
        out = s + "0" * (n - k)
    elif 0 < n <= 21:
        out = s[:n] + "." + s[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + s
    else:
        e = n - 1
        out = s[0] + ("." + s[1:] if k > 1 else "") + "e" + ("+" if e >= 0 else "-") + str(abs(e))
    return sign + out


def _js_str(v: Any) -> str:
    """String(v) for the cells; a missing value is an empty cell."""
    if v is None or v is _MISSING:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return _num_str(float(v))
    return str(v)


def _fixed1(x: float) -> str:
    """JavaScript's x.toFixed(1): halves round up, on the exact binary value."""
    return str(Decimal(x).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _get(d: Any, key: str) -> Any:
    return d.get(key, _MISSING) if isinstance(d, dict) else _MISSING


# ── Streams ────────────────────────────────────────────────────────────────


def _stream_cells(s: Dict[str, Any]) -> Dict[str, Any]:
    """A stream's values for its row: read as the analysis reads them, plus
    the extra properties entered with it."""
    info = stream_info(s)
    sv = s.get("stream_values") or {}
    kind = None
    if info["tin"] is not None and info["tout"] is not None:
        kind = "hot" if info["tin"] > info["tout"] else "cold"
    return {**info, "kind": kind, "water_in": sv.get("Water Content In") or None,
            "water_out": sv.get("Water Content Out") or None,
            "density": sv.get("Density") or None, "pressure": sv.get("Pressure") or None}


def _stream_row(name: str, si: Dict[str, Any], group: str, sub: str, place: Dict[str, Any]) -> List[str]:
    return [
        name, _js_str(si["cp"]), _js_str(si["mdot"]), _js_str(si["CP"]), _js_str(si["tin"]),
        _js_str(si["tout"]), si["kind"] or "", group, sub,
        _fixed1(si["Q"]) if _truthy(si["Q"]) else "",
        place["lat"], place["lon"], _js_str(place["hours"]),
        _js_str(_or(si["water_in"], place["water_in"])), _js_str(_or(si["water_out"], place["water_out"])),
        _js_str(_or(si["density"], place["density"])), _js_str(_or(si["pressure"], place["pressure"])),
        _js_str(place["notes"]),
    ]


def _empty_row(group: str, sub: str, place: Dict[str, Any]) -> List[str]:
    return ["", "", "", "", "", "", "", group, sub, "", place["lat"], place["lon"],
            _js_str(place["hours"]), _js_str(place["water_in"]), _js_str(place["water_out"]),
            _js_str(place["density"]), _js_str(place["pressure"]), _js_str(place["notes"])]


def _cells_to_text(rows: List[List[str]]) -> str:
    """Semicolon separated, every cell quoted (quotes inside doubled)."""
    return "\n".join(";".join('"' + c.replace('"', '""') + '"' for c in r) for r in rows)


def _groups(state: Dict[str, Any]):
    """(group index, its name, its coordinates, [(subprocess index, subprocess)])."""
    processes = state.get("processes") or []
    names = state.get("proc_group_names") or []
    coords = state.get("proc_group_coordinates") or {}
    for g, subs in enumerate(state.get("proc_groups") or []):
        name = names[g] if g < len(names) and _truthy(names[g]) else f"Process {g + 1}"
        coord = (coords.get(str(g)) if isinstance(coords, dict)
                 else coords[g] if isinstance(coords, list) and g < len(coords) else None)
        members = [(i, processes[i]) for i in subs
                   if isinstance(i, int) and 0 <= i < len(processes) and processes[i]]
        yield g, name, (coord if isinstance(coord, dict) else {}), members


def project_csv(state: Dict[str, Any]) -> str:
    """The project's streams as CSV text, one row per stream; a subprocess
    without streams gets a row of its own."""
    rows: List[List[str]] = [list(HEADER)]
    for _, g_name, g_coord, members in _groups(state):
        for _, sub in members:
            extra = sub.get("extra_info") or {}
            # A subprocess is located by its process, so every row of a
            # process carries the same coordinate.
            place = {
                "lat": _js_str(_or(_get(g_coord, "lat"), _get(sub, "lat"), "")),
                "lon": _js_str(_or(_get(g_coord, "lon"), _get(sub, "lon"), "")),
                "hours": _or(_get(sub, "hours"), _get(g_coord, "hours"), ""),
                "water_in": _or(_get(extra, "water_content_in"), ""),
                "water_out": _or(_get(extra, "water_content_out"), ""),
                "density": _or(_get(extra, "density"), ""),
                "pressure": _or(_get(extra, "pressure"), ""),
                "notes": _or(_get(extra, "notes"), ""),
            }
            sub_name = _js_str(sub.get("name"))
            streams, children = sub.get("streams") or [], sub.get("children") or []
            if not streams and not children:
                rows.append(_empty_row(g_name, sub_name, place))
                continue
            if len(rows) + len(streams) + len(children) > MAX_CSV_ROWS:
                raise ProjectTooLarge(f"The project has more than {MAX_CSV_ROWS:,} streams to export.")
            for s in streams:
                rows.append(_stream_row(f"{g_name}_{sub_name}_{_js_str(s.get('name'))}",
                                        _stream_cells(s), g_name, sub_name, place))
            for child in children:
                c_extra = child.get("extra_info") or {}
                c_place = {
                    "lat": _js_str(_or(_get(g_coord, "lat"), _get(sub, "lat"), _get(child, "lat"), "")),
                    "lon": _js_str(_or(_get(g_coord, "lon"), _get(sub, "lon"), _get(child, "lon"), "")),
                    "hours": _or(_get(child, "hours"), place["hours"], ""),
                    "water_in": _or(_get(c_extra, "water_content_in"), place["water_in"], ""),
                    "water_out": _or(_get(c_extra, "water_content_out"), place["water_out"], ""),
                    "density": _or(_get(c_extra, "density"), place["density"], ""),
                    "pressure": _or(_get(c_extra, "pressure"), place["pressure"], ""),
                    "notes": _or(_get(c_extra, "notes"), place["notes"], ""),
                }
                c_name = f"{sub_name}{CHILD_SEP}{_js_str(child.get('name'))}"
                c_streams = child.get("streams") or []
                if len(rows) + len(c_streams) > MAX_CSV_ROWS:
                    raise ProjectTooLarge(f"The project has more than {MAX_CSV_ROWS:,} streams to export.")
                if not c_streams:
                    rows.append(_empty_row(g_name, c_name, c_place))
                for s in c_streams:
                    rows.append(_stream_row(f"{g_name}_{c_name}_{_js_str(s.get('name'))}",
                                            _stream_cells(s), g_name, c_name, c_place))
    # On a site plan the positions are plan positions, not geographic ones:
    # Lat/Lon would only mislead, so they are left out.
    if _truthy(state.get("site_plan")):
        lat = HEADER.index("Lat")
        rows = [[c for i, c in enumerate(r) if i not in (lat, lat + 1)] for r in rows]
    return _cells_to_text(rows)


# ── Distances ──────────────────────────────────────────────────────────────


def _finite(x: float) -> Optional[float]:
    return x if math.isfinite(x) else None


def distance_csv(state: Dict[str, Any], metric: str = "manhattan") -> str:
    """Distances between the subprocesses (and their sub-subprocesses) in
    meters, as a matrix; N/A where a position is missing. Each is measured at
    its own position, so the real spread inside a process shows."""
    nodes: List[Tuple[str, Optional[float], Optional[float]]] = []
    too_many = ProjectTooLarge(
        f"Distances can be exported for up to {MAX_DISTANCE_NODES} subprocesses at a time.")
    for _, g_name, g_coord, members in _groups(state):
        for _, sub in members:
            if len(nodes) + 1 + len(sub.get("children") or []) > MAX_DISTANCE_NODES:
                raise too_many
            sub_name = _js_str(sub.get("name"))
            nodes.append((f"{g_name}{CHILD_SEP}{sub_name}",
                          _finite(_number(_or(_get(sub, "lat"), _get(g_coord, "lat")))),
                          _finite(_number(_or(_get(sub, "lon"), _get(g_coord, "lon"))))))
            for child in sub.get("children") or []:
                nodes.append((f"{g_name}{CHILD_SEP}{sub_name}{CHILD_SEP}{_js_str(child.get('name'))}",
                              _finite(_number(_or(_get(child, "lat"), _get(sub, "lat"), _get(g_coord, "lat")))),
                              _finite(_number(_or(_get(child, "lon"), _get(sub, "lon"), _get(g_coord, "lon"))))))
    measure = haversine_distance if metric == "euclidean" else manhattan_spherical_distance
    rows = [["Process Name", *[n[0] for n in nodes]]]
    for i, (name, lat1, lon1) in enumerate(nodes):
        row = [name]
        for j, (_, lat2, lon2) in enumerate(nodes):
            if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
                row.append("N/A")
            elif i == j:
                row.append("0")
            else:
                row.append(_num_str(float(math.floor(measure(lat1, lon1, lat2, lon2) + 0.5))))
        rows.append(row)
    return _cells_to_text(rows)


# ── Reading it back ────────────────────────────────────────────────────────


def _rows(text: str) -> List[Dict[str, str]]:
    sample = text.lstrip("﻿")
    first = sample.split("\n", 1)[0]
    delimiter = ";" if first.count(";") > first.count(",") else ","
    return list(csv.DictReader(io.StringIO(sample), delimiter=delimiter))


def is_project_csv(text: str) -> bool:
    """Whether the text is in this module's format (by its header)."""
    rows = csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=";")
    header = next(rows, [])
    return {"Name", "Process", "Subprocess", "Input Temperature [°C]"}.issubset(header)


# The columns a stream and its subprocess share: a stream's own value, else
# its subprocess's (stream_values key, extra_info key).
_SHARED = (("Water In", "Water Content In", "water_content_in"),
           ("Water Out", "Water Content Out", "water_content_out"),
           ("Density", "Density", "density"), ("Pressure", "Pressure", "pressure"))


def _common(values: List[str]) -> str:
    """The value most rows share (the first of equals): the subprocess's own."""
    return max(dict.fromkeys(values), key=values.count) if values else ""


def read_project_csv(text: str) -> Dict[str, Any]:
    """The processes, process groups, their names and coordinates of a CSV
    written by project_csv, for the caller to put into its project. Values
    come back in °C, kg/s and kJ/(kg·K), as written. Exported again, the
    project gives the same file."""
    processes: List[Dict[str, Any]] = []
    groups: List[List[int]] = []
    names: List[str] = []
    coords: Dict[str, Dict[str, Any]] = {}
    sub_index: Dict[Tuple[str, str], int] = {}
    child_index: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    # Each node's rows, to tell its own values from its streams' afterwards.
    rows_of: Dict[int, List[Dict[str, str]]] = {}
    parent_of: Dict[int, Dict[str, Any]] = {}

    def node(name: str, level: int) -> Dict[str, Any]:
        n = {"name": name, "level": level, "streams": [], "children": [], "hours": "",
             "extra_info": {"notes": "", "water_content_in": "", "water_content_out": "",
                            "density": "", "pressure": ""}}
        rows_of[id(n)] = []
        return n

    for row in _rows(text):
        row = {k: (v or "") for k, v in row.items() if k is not None}
        group, sub_full = row.get("Process", ""), row.get("Subprocess", "")
        if not group and not sub_full and not row.get("Name"):
            continue
        if group not in names:
            names.append(group)
            groups.append([])
            coords[str(len(names) - 1)] = {"lat": _float_or_none(row.get("Lat", "")),
                                           "lon": _float_or_none(row.get("Lon", "")), "hours": ""}
        g = names.index(group)
        sub_name, _, child_name = sub_full.partition(CHILD_SEP)
        if (group, sub_name) not in sub_index:
            sub_index[(group, sub_name)] = len(processes)
            processes.append(node(sub_name, 1))
            groups[g].append(sub_index[(group, sub_name)])
        target = processes[sub_index[(group, sub_name)]]
        if child_name:
            key = (group, sub_name, child_name)
            if key not in child_index:
                child_index[key] = node(child_name, 2)
                parent_of[id(child_index[key])] = target
                target["children"].append(child_index[key])
            target = child_index[key]
        rows_of[id(target)].append(row)
        if row.get("Name"):
            prefix = f"{group}_{sub_full}_"
            name = row["Name"][len(prefix):] if row["Name"].startswith(prefix) else row["Name"]
            target["streams"].append(_stream(name, row))

    def settle(n: Dict[str, Any]) -> None:
        rows = rows_of[id(n)]
        parent = parent_of.get(id(n))
        own = {"notes": _common([r.get("Notes", "") for r in rows]),
               "hours": _common([r.get("Hours", "") for r in rows])}
        for col, _, extra_key in _SHARED:
            own[extra_key] = _common([r.get(col, "") for r in rows])
        # A sub-subprocess shows its parent's values where it has none.
        for k, v in own.items():
            inherited = (parent["hours"] if k == "hours" else parent["extra_info"][k]) if parent else ""
            if v == inherited:
                v = ""
            if k == "hours":
                n["hours"] = v
            else:
                n["extra_info"][k] = v
        # A stream keeps a value only where it differs from its subprocess's.
        for s in n["streams"]:
            for _, sv_key, extra_key in _SHARED:
                shown = n["extra_info"][extra_key] or (parent["extra_info"][extra_key] if parent else "")
                if s["stream_values"].get(sv_key) == shown:
                    s["stream_values"].pop(sv_key)
        for c in n["children"]:
            settle(c)

    for p in processes:
        settle(p)
    return {"processes": processes, "proc_groups": groups, "proc_group_names": names,
            "proc_group_coordinates": coords}


def _float_or_none(v: str) -> Optional[float]:
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def _stream(name: str, row: Dict[str, str]) -> Dict[str, Any]:
    """A stream from its row: the values as written, in base units; CP
    directly when no mass flow and cp were written."""
    tin, tout = row.get("Input Temperature [°C]", ""), row.get("Output Temperature [°C]", "")
    mdot, cp, CP = row.get("Mass Flow", ""), row.get("Heat Capacity", ""), row.get("CP-Value [kW/K]", "")
    values: Dict[str, str] = {"Tin": tin, "Tout": tout}
    display = ["Tin", "Tout"]
    if mdot and cp:
        values.update({"ṁ": mdot, "cp": cp})
        display += ["ṁ", "cp"]
    elif CP:
        values["CP"] = CP
        display.append("CP")
    for col, key, _ in _SHARED:
        if row.get(col):
            values[key] = row[col]
    # A stream as the page makes one; the values were written in base units.
    return {
        "name": name,
        "type": "product",
        "stream_values": values,
        "stream_units": {k: u for k, u in (("Tin", "°C"), ("Tout", "°C"), ("ṁ", "kg/s"),
                                            ("cp", "kJ/(kg·K)"), ("CP", "kW/K")) if k in values},
        "display_vars": display,
    }
