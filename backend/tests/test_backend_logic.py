"""What the page used to compute in the browser and now gets from the backend:
the pinch figures (hot duty, maximum recovery, the share of it, GCC pockets),
the heat pump view's balance, the CSV exports and import, the economics
defaults. Each is held to what the page computed before (fixtures written
from the old frontend code) and, where the page still computes, to the same
fixture the frontend tests read."""

import json
import re
from datetime import date
from pathlib import Path

import pytest

from app.config import EXAMPLES_DIR
from app.models.analysis import PinchResult
from app.models.project import ProjectState
from app.models.report import ReportRequest, ScenarioReportData
from app.services.economics import DEFAULTS, PRESETS
from app.services.optimization.balance import balance, profile_at
from app.services.pinch_figures import at_recovery_share, gcc_pockets
from app.services.project_analysis import selected_streams
from app.services.project_csv import distance_csv, project_csv, read_project_csv
from app.services.report import generate_html_report

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _example(name="heat_integration_example_1.json"):
    return json.loads((EXAMPLES_DIR / name).read_text(encoding="utf-8"))


# ── Pinch figures ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("case", _fixture("gcc_pockets_reference.json"),
                         ids=lambda c: f"{c['example']}@{c['t_min']}")
def test_gcc_pockets_are_the_ones_the_page_drew(case):
    got = gcc_pockets(case["H"], case["T"], case["pinch_temperature"])
    assert got == case["pockets"]


def test_gcc_pockets_close_with_a_vertical_line():
    assert gcc_pockets([60, 30, 0, 10, 20], [20, 50, 80, 110, 140], 80) == {"x": [], "y": [], "heat": 0.0}
    # Above the pinch (80 °C): out to 40 at 110 °C, back to 20 at 130 °C, on
    # to 50 at the top: the vertical at H = 20 closes it at 95 °C. Below: out
    # to 30 at 60 °C, back to 10 at 50 °C, on to 40 at 20 °C.
    p = gcc_pockets([40, 10, 30, 0, 40, 20, 50], [20, 50, 60, 80, 110, 130, 150], 80)
    assert p["heat"] == pytest.approx(40)
    assert p["x"].count(None) == 2
    upper = p["y"][:p["y"].index(None)]
    assert min(upper) == pytest.approx(95)


@pytest.mark.parametrize("pct", [0, 33, 100])
def test_pinch_answer_carries_the_figures_the_page_shows(client, pct):
    state = _example()
    streams = selected_streams(ProjectState(**state), {f"stream_{p}_{s}": True for p in range(3) for s in range(2)})
    pinch = client.post("/api/analysis/pinch", json={
        "streams": [{"name": s["name"], "CP": s["CP"], "T_supply": s["Tin"], "T_target": s["Tout"]} for s in streams],
        "T_min": 10}).json()
    hot = sum(s["Q"] for s in streams if s["type"] == "Hot")
    assert pinch["total_hot_duty"] == pytest.approx(hot)
    assert pinch["max_heat_recovery"] == pytest.approx(hot - pinch["cold_utility"])
    assert pinch["gcc_pockets"]["heat"] >= 0
    # Sent back (the page does, to the report), the figures are recomputed.
    again = PinchResult(**{**pinch, "max_heat_recovery": -1, "total_hot_duty": -1})
    assert again.max_heat_recovery == pinch["max_heat_recovery"]
    share = at_recovery_share(again, pct)
    d = (1 - pct / 100) * pinch["max_heat_recovery"]
    assert share == pytest.approx({"unrecovered": d, "hot_utility": pinch["hot_utility"] + d,
                                   "cold_utility": pinch["cold_utility"] + d,
                                   "heat_recovery": pinch["max_heat_recovery"] - d})


def test_recovery_share_reference_matches_the_backend():
    """The fixture the page's recoveryShare.test.ts reads holds what
    at_recovery_share answers."""
    for row in _fixture("recovery_share_reference.json"):
        p = row["pinch"]
        cold = p["cold_utility"]
        pinch = PinchResult(pinch_temperature=0, hot_utility=p["hot_utility"], cold_utility=cold, T_min=10,
                            temperatures=[], problem_table=[], heat_cascade=[], unfeasible_heat_cascade=[],
                            streams_data=[{"cp": 1.0, "ts": cold + p["max_heat_recovery"], "tt": 0.0}])
        assert pinch.max_heat_recovery == pytest.approx(p["max_heat_recovery"], rel=1e-12, abs=1e-9)
        assert at_recovery_share(pinch, row["recovery_pct"]) == pytest.approx(row["expected"], rel=1e-12, abs=1e-9)


# ── The heat pump view's balance ────────────────────────────────────────────


def test_profile_and_balance_as_the_heat_pump_view_had_them():
    H, T = [0, 100, 300], [50, 60, 80]
    assert [profile_at(H, T, t) for t in (55, 70, 40, 90)] == [50, 200, 0, 300]
    assert profile_at([], [], 60) is None
    b = balance(375, 4.75, 296.0)
    assert b["needed"] == pytest.approx(296.05, abs=0.01)
    assert b["p_el"] == pytest.approx(78.95, abs=0.01)
    assert b["state"] == "balanced"
    short = balance(375, 4.75, 200)
    assert short["state"] == "source_limited"
    assert short["q_sink_possible"] == pytest.approx(200 * 4.75 / 3.75)
    assert balance(375, 4.75, 400)["state"] == "demand_limited"
    assert balance(375, 0.9, 400) is None and balance(0, 3, 10) is None


def test_cop_point_balances_the_profiles(client):
    body = dict(refrigerant="Butane_2", medium_sink="Water", T_source_in=68.0, T_source_out=58.2,
                T_sink_in=78.0, T_sink_out=113.0, delta_t_min=10.0)
    plain = client.post("/api/analysis/cop-point", json=body).json()
    assert plain["balance"] is None and plain["q_sink"] is None
    r = client.post("/api/analysis/cop-point", json={
        **body, "source_profile": {"H": [0, 300, 600], "T": [40, 58.2, 73]},
        "sink_profile": {"H": [0, 375, 900], "T": [73, 113, 150]},
        "T_source_profile": 58.2, "T_sink_profile": 113.0, "q_sink_default": 1.0}).json()
    assert r["q_sink"] == pytest.approx(375) and r["q_available"] == pytest.approx(300)
    want = balance(375, r["cop_2t"], 300)
    assert r["balance"] == pytest.approx(want)
    # No sink profile: the point's own duty.
    r = client.post("/api/analysis/cop-point", json={
        **body, "source_profile": {"H": [0, 300], "T": [40, 73]}, "sink_profile": {"H": [], "T": []},
        "q_sink_default": 375.0}).json()
    assert r["q_sink"] == 375.0


# ── CSV ─────────────────────────────────────────────────────────────────────

CSV_REF = _fixture("project_csv_reference.json")


@pytest.mark.parametrize("name", sorted(CSV_REF["examples"]) + sorted(CSV_REF["projects"]))
def test_csv_exports_are_the_files_the_page_wrote(client, name):
    want = CSV_REF["examples"].get(name) or CSV_REF["projects"][name]
    project = _example(name) if name in CSV_REF["examples"] else want["project"]
    assert project_csv(project) == want["csv"]
    assert distance_csv(project, "manhattan") == want["manhattan"]
    assert distance_csv(project, "euclidean") == want["euclidean"]
    r = client.post("/api/io/export-csv", json=project)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.content.decode("utf-8") == want["csv"]
    for metric in ("manhattan", "euclidean"):
        r = client.post(f"/api/io/export-distances?metric={metric}", json=project)
        assert r.content.decode("utf-8") == want[metric]
    assert client.post("/api/io/export-distances?metric=nope", json=project).status_code == 422


@pytest.mark.parametrize("name", sorted(CSV_REF["examples"]) + sorted(CSV_REF["projects"]))
def test_csv_import_reads_the_export_back(client, name):
    project = _example(name) if name in CSV_REF["examples"] else CSV_REF["projects"][name]["project"]
    text = project_csv(project)
    r = client.post("/api/io/import-csv", files={"file": ("p.csv", text.encode("utf-8"), "text/csv")})
    assert r.status_code == 200, r.text
    back = r.json()
    assert back["imported_processes"] == len(back["processes"])
    # Exported again: the same file, so the same streams for the analysis.
    assert project_csv({**project, **{k: back[k] for k in
                        ("processes", "proc_groups", "proc_group_names", "proc_group_coordinates")}}) == text
    # And valid as a project.
    ProjectState(**{**project, **{k: back[k] for k in ("processes", "proc_groups", "proc_group_names")}})


def test_csv_quotes_inside_a_cell_are_doubled():
    state = {"processes": [{"name": 'The "big" one', "streams": []}], "proc_groups": [[0]], "proc_group_names": ["P"]}
    text = project_csv(state)
    assert '"The ""big"" one"' in text
    assert read_project_csv(text)["processes"][0]["name"] == 'The "big" one'


def test_the_older_csv_columns_still_import(client):
    text = ("name,next,conntemp,connm,conncp,stream_no,mdot,temp_in,temp_out,cp\n"
            "Dryer,,,,,1,2,120,40,1.0\nDryer,,,,,2,1,20,60,4.2\n")
    r = client.post("/api/io/import-csv", files={"file": ("old.csv", text.encode(), "text/csv")}).json()
    assert sum(len(p["streams"]) for p in r["processes"]) == 2
    assert "proc_groups" not in r


# ── Economics defaults ──────────────────────────────────────────────────────


def test_economics_defaults_fixture_is_what_the_backend_serves(client):
    """The frontend tests read this fixture: it must stay the backend's."""
    ref = _fixture("economics_defaults.json")
    assert {k: v for k, v in DEFAULTS.items() if k != "year"} == ref["form"]
    assert PRESETS == ref["presets"]
    served = client.get("/api/analysis/economics/defaults").json()
    assert served["form"] == {**ref["form"], "year": date.today().year + 1}
    assert list(served["form"]) == list(DEFAULTS)
    assert served["presets"] == ref["presets"]


# ── The analysis chains ─────────────────────────────────────────────────────


@pytest.mark.parametrize("case", _fixture("selected_streams_reference.json"),
                         ids=lambda c: f"{c['example']}:{len(c['selection'])}")
def test_selected_streams_match_the_fixture_the_page_reads(case):
    got = selected_streams(ProjectState(**_example(case["example"])), case["selection"])
    assert [{k: v for k, v in s.items() if k != "key"} for s in got] == case["streams"]


@pytest.mark.parametrize("pct", [100, 40])
def test_the_pages_chain_and_the_projects_chain_agree(client, pct):
    """The page calls /pinch, /hpi and /hpi-optimization in turn; the MCP
    server calls /project. Same streams, same settings: same answers."""
    state = _example()
    out = client.post("/api/analysis/project", json={"state": state, "recovery_pct": pct}).json()
    streams = selected_streams(ProjectState(**state), out["selection"])
    page_pinch = client.post("/api/analysis/pinch", json={
        "streams": [{"name": s["name"], "CP": s["CP"], "T_supply": s["Tin"], "T_target": s["Tout"]} for s in streams],
        "T_min": out["t_min"]}).json()
    assert page_pinch == out["pinch"]
    hpi = client.post("/api/analysis/hpi", json={
        "pinch_result": page_pinch, "profile_mode": "net_load",
        "hp_types": ["Prototypical Stirling", "VHTHP (HFC/HFO)", "SHP and HTHPs (HFC/HFO)",
                     "SHP and HTHPs (R717)", "Carnot"]}).json()
    assert hpi == out["hpi"]
    opt = client.post("/api/analysis/hpi-optimization", json={
        "pinch_result": page_pinch, "profile_mode": "net_load", "cop_formula": None,
        "custom_cop_model": None, "recovery_pct": pct, "search_temps": ["source_out", "sink_out"],
        "lang": "en"}).json()
    assert opt == out["optimization"]


# ── The report ──────────────────────────────────────────────────────────────


def test_report_shows_the_pinch_cards_at_the_chosen_share(client):
    state = _example()
    out = client.post("/api/analysis/project", json={"state": state, "recovery_pct": 40}).json()
    pinch = PinchResult(**out["pinch"])
    streams = [{k: s[k] for k in ("name", "Tin", "Tout", "CP", "Q", "type")} for s in out["streams"]]

    def report(pct):
        sc = {"name": "All streams", "selected_streams": streams, "pinch_result": out["pinch"],
              "hpi_optimization_result": out["optimization"], "t_min": out["t_min"]}
        if pct is not None:
            sc["recovery_pct"] = pct
        return generate_html_report(ReportRequest(scenarios=[ScenarioReportData(**sc)], selected_streams=streams))

    full, partial = report(None), report(40)
    at40 = at_recovery_share(pinch, 40)
    assert f"{pinch.hot_utility:.2f} kW" in full and f"{pinch.max_heat_recovery:.2f} kW" in full
    assert f"{at40['hot_utility']:.2f} kW" in partial and f"{at40['cold_utility']:.2f} kW" in partial
    assert f"{at40['heat_recovery']:.2f} kW" in partial
    assert "40 % of the maximum heat recovery" in partial and "maximum heat recovery, as" not in full
    stamp = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    assert stamp.sub("", report(100)) == stamp.sub("", full)
    with pytest.raises(ValueError):
        ScenarioReportData(name="x", recovery_pct=120)
