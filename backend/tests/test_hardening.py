"""Limits that keep one request from tying up the server: each one answers
with a clear message rather than running for minutes or taking gigabytes."""

import asyncio
import base64
import io
import json
import time
import zipfile

import numpy as np
import pandas as pd
import pytest



def _pinch(client, streams=None, t_min=10.0):
    streams = streams or [
        {"name": "H1", "CP": 10.0, "T_supply": 120.0, "T_target": 40.0},
        {"name": "C1", "CP": 8.0, "T_supply": 30.0, "T_target": 110.0},
        {"name": "H2", "CP": 4.0, "T_supply": 90.0, "T_target": 30.0},
        {"name": "C2", "CP": 5.0, "T_supply": 60.0, "T_target": 150.0},
    ]
    r = client.post("/api/analysis/pinch", json={"streams": streams, "T_min": t_min})
    assert r.status_code == 200, r.text
    return r.json()


# ── 1. COP formula ─────────────────────────────────────────────────────────


def test_nested_powers_fail_fast_with_a_clear_error(client):
    started = time.perf_counter()
    for expr in ("((((9**64)**64)**64)**64)**64", "(9**64)**64", "((((9**64)**64)**64)**64)**64 * carnot"):
        r = client.post("/api/analysis/cop-formula/validate",
                        json={"expression": expr, "T_source": 60, "T_sink": 110})
        assert r.status_code == 200
        out = r.json()
        assert out["valid"] is False
        assert out["error"]
    assert time.perf_counter() - started < 2


def test_formula_numbers_are_floats():
    from app.utils.cop_formula import FormulaError, compile_formula, cop_from_formula

    with pytest.raises(FormulaError, match="too large"):
        cop_from_formula("(9**64)**64", 60.0, 110.0)
    with pytest.raises(FormulaError, match="too large"):
        compile_formula("1" * 400 + " * carnot")
    # A negative number to a fractional power is complex in Python: no COP.
    with pytest.raises(FormulaError):
        cop_from_formula("(-8) ** 0.5", 60.0, 110.0)
    # Ordinary formulas still give the same numbers.
    assert float(cop_from_formula("0.5 * carnot", 60.0, 110.0)) == pytest.approx(0.5 * 383.15 / 50)
    assert float(cop_from_formula("T_lift ** 2 + 7 % 3", 60.0, 110.0)) == 2501.0
    assert float(cop_from_formula("4", 60.0, 110.0)) == 4.0


# ── 2. Distance and CSV export ─────────────────────────────────────────────


def _repeated_project(n):
    """One subprocess listed n times: a small body asking for a huge file."""
    return {"processes": [{"name": "A", "lat": 48.0, "lon": 11.0, "streams": [{"name": "s"}]}],
            "proc_groups": [[0] * n]}


def test_distance_export_is_capped(client):
    from app.services.project_csv import MAX_DISTANCE_NODES

    ok = client.post("/api/io/export-distances", json=_repeated_project(3))
    assert ok.status_code == 200
    r = client.post("/api/io/export-distances", json=_repeated_project(MAX_DISTANCE_NODES + 1))
    assert r.status_code == 413
    assert str(MAX_DISTANCE_NODES) in r.json()["detail"]
    started = time.perf_counter()
    assert client.post("/api/io/export-distances", json=_repeated_project(1_000_000)).status_code == 413
    assert time.perf_counter() - started < 5


def test_csv_export_is_capped(client):
    from app.services.project_csv import MAX_CSV_ROWS

    r = client.post("/api/io/export-csv", json=_repeated_project(MAX_CSV_ROWS + 1))
    assert r.status_code == 413
    assert "streams" in r.json()["detail"]


# ── 3. The optimization's inputs ───────────────────────────────────────────


def test_pinch_streams_are_bounded(client):
    from app.models.analysis import MAX_PINCH_STREAMS

    many = [{"CP": 1.0, "T_supply": 100.0, "T_target": 50.0}] * (MAX_PINCH_STREAMS + 1)
    assert client.post("/api/analysis/pinch", json={"streams": many, "T_min": 10}).status_code == 422
    hot = {"CP": 1.0, "T_supply": 1e9, "T_target": 50.0}
    cold = {"CP": 1.0, "T_supply": 20.0, "T_target": 80.0}
    assert client.post("/api/analysis/pinch", json={"streams": [hot, cold], "T_min": 10}).status_code == 422
    assert client.post("/api/analysis/pinch",
                       json={"streams": [cold, cold], "T_min": 1e9}).status_code == 422


def test_a_too_wide_temperature_span_is_refused(client):
    pinch = _pinch(client, [
        {"CP": 10.0, "T_supply": 1990.0, "T_target": 1000.0},
        {"CP": 10.0, "T_supply": 990.0, "T_target": -200.0},
        {"CP": 10.0, "T_supply": -250.0, "T_target": 980.0},
        {"CP": 10.0, "T_supply": 1000.0, "T_target": 1980.0},
    ])
    started = time.perf_counter()
    r = client.post("/api/analysis/hpi-optimization", json={"pinch_result": pinch, "profile_mode": "composite"})
    assert r.status_code == 422
    assert "grid points" in r.json()["detail"]
    assert time.perf_counter() - started < 10


def test_a_formula_envelope_is_bounded(client):
    pinch = _pinch(client)
    formula = {"expression": "0.5 * carnot", "T_sink_max": 1e6}
    r = client.post("/api/analysis/hpi-optimization", json={"pinch_result": pinch, "cop_formula": formula})
    assert r.status_code == 422


def _spec(**changes):
    spec = {
        "kind": "nn", "temps": ["T_source_out", "T_sink_out"], "mean": [50.0, 100.0], "scale": [10.0, 20.0],
        "layers": [{"W": [[0.1], [0.2]], "b": [3.0]}],
        "envelope": {"T_source_min": 0, "T_source_max": 100, "T_sink_min": 50, "T_sink_max": 150,
                     "cop_min": 1, "cop_max": 10},
    }
    spec.update(changes)
    return spec


def test_trained_model_specs_are_bounded():
    from pydantic import ValidationError
    from app.models.cop_training import MAX_CATEGORIES, MAX_NETWORK_WEIGHTS, CustomCopModelSpec

    CustomCopModelSpec(**_spec())
    # Two hidden layers of 400: 160,000 weights in the middle one alone.
    big = [{"W": [[0.0] * 400] * 2, "b": [0.0] * 400},
           {"W": [[0.0] * 400] * 400, "b": [0.0] * 400},
           {"W": [[0.0]] * 400, "b": [0.0]}]
    assert 400 * 400 > MAX_NETWORK_WEIGHTS
    with pytest.raises(ValidationError, match="weights"):
        CustomCopModelSpec(**_spec(layers=big))
    many = {"refrigerant": [f"R{i}" for i in range(MAX_CATEGORIES + 1)]}
    with pytest.raises(ValidationError, match="per category"):
        CustomCopModelSpec(**_spec(cats=["refrigerant"], categories=many,
                                   layers=[{"W": [[0.1]] * (MAX_CATEGORIES + 3), "b": [1.0]}]))
    with pytest.raises(ValidationError, match="envelope"):
        CustomCopModelSpec(**_spec(envelope={**_spec()["envelope"], "T_sink_max": 1e6}))
    with pytest.raises(ValidationError):
        CustomCopModelSpec(**_spec(temps=["T_source_out", "T_sink_out"] * 1000))


def test_a_large_network_cannot_run_for_minutes(client, monkeypatch):
    from app.services.optimization import search

    monkeypatch.setattr(search, "MAX_CUSTOM_MODEL_WORK", 1.0)
    r = client.post("/api/analysis/hpi-optimization",
                    json={"pinch_result": _pinch(client), "custom_cop_model": _spec()})
    assert r.status_code == 422
    assert "trained model" in r.json()["detail"]


def test_the_network_runs_in_chunks():
    from app.models.cop_training import CustomCopModelSpec
    from app.services.cop_training import model

    spec = CustomCopModelSpec(**_spec(layers=[{"W": [[0.1, -0.2], [0.3, 0.4]], "b": [0.5, 0.1]},
                                              {"W": [[1.0], [2.0]], "b": [3.0]}]))
    n = model.PREDICT_CHUNK * 2 + 5
    t = {"T_source_out": np.linspace(0, 100, n), "T_sink_out": np.linspace(50, 150, n)}
    x = (np.stack([t["T_source_out"], t["T_sink_out"]], axis=1) - spec.mean) / spec.scale
    a = np.maximum(x @ np.array([[0.1, -0.2], [0.3, 0.4]]) + [0.5, 0.1], 0)
    expected = (a @ np.array([[1.0], [2.0]]) + 3.0)[:, 0]
    assert np.allclose(model.predict(spec, t, {}), expected, rtol=0, atol=1e-12)


# ── 4. Map images ──────────────────────────────────────────────────────────


def _png(w, h):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 200, 200)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_a_huge_map_image_is_refused(client):
    small = client.post("/api/analysis/map-preview",
                        json={"map_snapshots_encoded": {"OpenStreetMap": _png(64, 48)}})
    assert small.status_code == 200 and small.json()["map_b64"]
    r = client.post("/api/analysis/map-preview",
                    json={"map_snapshots_encoded": {"OpenStreetMap": _png(5000, 5000)}})
    assert r.status_code == 413
    assert "megapixels" in r.json()["detail"]
    r = client.post("/api/analysis/report", json={"map_snapshots_encoded": {"OpenStreetMap": _png(5000, 5000)}})
    assert r.status_code == 413


def test_an_overlong_map_text_is_refused(monkeypatch):
    from app.services import map_service

    monkeypatch.setattr(map_service, "MAX_IMAGE_B64", 10)
    with pytest.raises(map_service.MapImageTooLarge):
        map_service._open_snapshot(_png(4, 4))


# ── 5. COP training uploads ────────────────────────────────────────────────


def test_too_many_columns_are_refused(client):
    from app.services.cop_training.data import MAX_COLUMNS

    df = pd.DataFrame(np.ones((5, MAX_COLUMNS + 1)), columns=[f"c{i}" for i in range(MAX_COLUMNS + 1)])
    r = client.post("/api/analysis/cop-model/inspect", files={"file": ("d.csv", df.to_csv(index=False).encode())})
    assert r.status_code == 400
    assert "columns" in r.json()["detail"]


def test_too_many_rows_are_refused_before_reading(client, monkeypatch):
    from app.services.cop_training import data

    monkeypatch.setattr(data, "MAX_READ_ROWS", 100)
    df = pd.DataFrame({"a": np.arange(101.0), "b": 1.0, "COP": 3.0})
    buf = io.BytesIO()
    df.to_parquet(buf)
    r = client.post("/api/analysis/cop-model/inspect", files={"file": ("d.parquet", buf.getvalue())})
    assert r.status_code == 400 and "rows" in r.json()["detail"]
    r = client.post("/api/analysis/cop-model/inspect", files={"file": ("d.csv", df.to_csv(index=False).encode())})
    assert r.status_code == 400 and "rows" in r.json()["detail"]


def test_an_excel_bomb_is_refused(client, monkeypatch):
    from app.services.cop_training import data

    monkeypatch.setattr(data, "MAX_UNPACKED_BYTES", 1000)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/worksheets/sheet1.xml", b"\0" * 10_000)
    r = client.post("/api/analysis/cop-model/inspect", files={"file": ("d.xlsx", buf.getvalue())})
    assert r.status_code == 400 and "unpacks" in r.json()["detail"]
    r = client.post("/api/analysis/cop-model/inspect", files={"file": ("d.xlsx", b"not a zip")})
    assert r.status_code == 400


def test_free_text_categories_are_refused(client):
    from app.models.cop_training import MAX_CATEGORIES

    n = 200
    rng = np.random.default_rng(0)
    t_src = rng.uniform(20, 60, n)
    df = pd.DataFrame({"T_src": t_src, "T_sink": t_src + 40, "COP": 3.0 + rng.normal(0, 0.1, n),
                       "refrigerant": [f"R{i % (MAX_CATEGORIES + 1)}" for i in range(n)]})
    mapping = {"T_source_out": "T_src", "T_sink_out": "T_sink", "COP": "COP", "refrigerant": "refrigerant"}
    r = client.post("/api/analysis/cop-model/train", files={"file": ("d.csv", df.to_csv(index=False).encode())},
                    data={"mapping": json.dumps(mapping)})
    assert r.status_code == 400
    assert "different values" in r.json()["detail"]


# ── 6. CPU work off the event loop ─────────────────────────────────────────


def test_cpu_bound_handlers_are_plain_functions():
    """FastAPI runs a plain `def` in its thread pool; an `async def` would
    hold up every other request while it computes."""
    from app.routers import analysis, cop_training, io_routes

    for router, path in [
        (io_routes, "/import-json"), (io_routes, "/import-csv"), (io_routes, "/export-json"),
        (io_routes, "/export-csv"), (io_routes, "/export-distances"), (analysis, "/status-quo"),
        (analysis, "/cop-formula/validate"), (cop_training, "/inspect"),
    ]:
        routes = [r for r in router.router.routes if getattr(r, "path", None) == path]
        assert routes, path
        assert not any(asyncio.iscoroutinefunction(r.endpoint) for r in routes), path


def test_imports_still_work(client):
    r = client.post("/api/io/import-json", files={"file": ("p.json", b"{}")})
    assert r.status_code == 200 and "state" in r.json()
    csv_text = ("name,next,conntemp,connm,conncp,stream_no,mdot,temp_in,temp_out,cp\n"
                "P1,,,,,1,2,80,40,4.2\n")
    r = client.post("/api/io/import-csv", files={"file": ("p.csv", csv_text.encode())})
    assert r.status_code == 200 and r.json()["imported_processes"] == 1


# ── 7. The report ──────────────────────────────────────────────────────────


def test_report_colours_cannot_inject_css():
    from app.services.report.economics import _render_economics

    evil = "red;background:url(https://example.com/x)' onmouseover='alert(1)"
    econ = {"kpis": [{"label": "L", "value": "1", "unit": "€", "color": evil, "valueColor": evil},
                     {"label": "Ok", "value": "2", "unit": "€", "color": "#2E7D32", "valueColor": "#C62828"}],
            "results": [{"headers": ["a", "b", "c", "d"],
                         "rows": [{"cells": ["1", "2", "3", "4"], "color": evil}]}]}
    html = _render_economics(econ, {"part_4": "", "part_4_in": ""})
    assert "example.com" not in html and "alert" not in html
    assert "border-left-color:#2E7D32;background:#2E7D320F" in html
    assert "color:#C62828" in html


def test_report_charts_carry_no_raw_script():
    from app.services.report.figures import _spec_chart

    spec = {"data": [{"type": "scatter", "x": [1], "y": [2], "name": "</script><script>alert(1)</script>"},
                     {"type": "evil", "x": [1]}],
            "layout": {"title": {"text": "<img src=x onerror=alert(1)>T"},
                       "images": [{"source": "https://example.com/track.png"}]},
            "frames": [{"x": 1}]}
    html = _spec_chart(spec)
    assert "<script>alert" not in html and "</script><script>" not in html
    assert "onerror" not in html
    assert "example.com" not in html
    assert '"evil"' not in html


# ── 8. No temporary files ──────────────────────────────────────────────────


def test_streams_never_become_a_file(client, monkeypatch):
    import tempfile

    def no_files(*a, **k):
        raise AssertionError("a request's streams were written to a file")

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", no_files)
    monkeypatch.setattr(tempfile, "mkstemp", no_files)
    pinch = _pinch(client)
    assert client.post("/api/analysis/hpi", json={"pinch_result": pinch}).status_code == 200
    assert client.post("/api/analysis/hpi-optimization", json={"pinch_result": pinch}).status_code == 200


def test_streams_from_memory_match_a_file(tmp_path):
    from app.modules.pinch.streams import Streams, streams_input

    rows = [(10.0, 120.0, 40.0), (8.0, 30.0, 110.0)]
    path = tmp_path / "s.csv"
    path.write_text("Tmin,10.0\nCP,TSUPPLY,TTARGET\n" + "".join(f"{a},{b},{c}\n" for a, b, c in rows))
    assert Streams(streams_input(10.0, rows)).streamsData == Streams(str(path)).streamsData


# ── 9. Geocoding ───────────────────────────────────────────────────────────


def test_geocoding_waits_its_turn(monkeypatch):
    from app.utils import geo_utils

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return [{"display_name": "X", "lat": "1", "lon": "2"}]

    calls, clock = [], [100.0]
    monkeypatch.setattr(geo_utils.requests, "get", lambda *a, **k: calls.append(clock[0]) or Resp())
    monkeypatch.setattr(geo_utils.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(geo_utils.time, "sleep", lambda s: clock.__setitem__(0, clock[0] + s))
    monkeypatch.setattr(geo_utils, "_nominatim_next", 0.0)

    geo_utils.geocode_address("a")
    geo_utils.geocode_address("b")
    assert calls[1] - calls[0] >= geo_utils.NOMINATIM_INTERVAL
    # Too many waiting already: refused at once instead of holding a thread.
    monkeypatch.setattr(geo_utils, "_nominatim_next", clock[0] + 10)
    with pytest.raises(geo_utils.GeocodeBusy):
        geo_utils.geocode_address("c")
