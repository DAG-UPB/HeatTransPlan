"""Usage counting: anonymous visitors, the owner apart, only known events,
and where visits stopped."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services import usage

UA = "Mozilla/5.0 (X11; Linux x86_64) Firefox/140.0"


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "PATH", str(tmp_path / "usage.sqlite"))
    monkeypatch.setattr(usage, "OWNER", usage._networks("131.234.1.5, 2001:db8:1:2::/64"))


def rows():
    return usage._db().execute("SELECT day, visitor, owner, event FROM usage ORDER BY id").fetchall()


def test_no_address_and_only_known_events():
    assert usage.record("203.0.113.7", UA, "page:home")
    assert not usage.record("203.0.113.7", UA, "page:Brewery Smith 95 °C")
    assert not usage.record("203.0.113.7", "Googlebot/2.1", "page:home")
    assert not usage.record("203.0.113.7", "curl/8.0", "page:home")
    [(day, code, owner, event)] = rows()
    assert (owner, event) == (0, "page:home") and len(code) == 12
    assert "203.0.113" not in open(usage.PATH, "rb").read().decode("latin-1")


def test_same_visitor_one_code_a_day_new_code_the_next():
    d1 = datetime(2026, 11, 20, 9, tzinfo=timezone.utc)
    usage.record("203.0.113.7", UA, "page:home", d1)
    usage.record("203.0.113.7", UA, "page:data-collection", d1 + timedelta(hours=2))
    usage.record("198.51.100.2", UA, "page:home", d1)
    usage.record("203.0.113.7", UA, "page:home", d1 + timedelta(days=1))
    codes = [r[1] for r in rows()]
    assert codes[0] == codes[1] != codes[2]
    assert codes[3] != codes[0]


def test_owner_by_address_or_ipv6_network():
    assert usage.is_owner("131.234.1.5") and usage.is_owner("::ffff:131.234.1.5")
    assert usage.is_owner("2001:db8:1:2:abcd::9") and not usage.is_owner("2001:db8:1:3::9")
    assert not usage.is_owner("131.234.1.6") and not usage.is_owner("unknown")


def test_summary_counts_the_owner_apart_and_where_visits_stopped():
    day = datetime(2026, 11, 20, 9, tzinfo=timezone.utc)
    for event in ("page:home", "page:data-collection", "page:potential-analysis",
                  "POST /api/analysis/pinch"):
        usage.record("203.0.113.7", UA, event, day)
    usage.record("198.51.100.2", UA, "page:home", day)
    usage.record("131.234.1.5", UA, "POST /api/analysis/report", day)
    s = usage.summary(7, today="2026-11-20")
    assert s["visits"] == 2
    assert s["days"] == [{"day": "2026-11-20", "visitors": 2, "owner_visits": 1}]
    funnel = {f["stage"]: (f["reached"], f["stopped_here"]) for f in s["funnel"]}
    assert funnel["Startseite"] == (2, 1)
    assert funnel["2 Pinch-Analyse"] == (1, 1)
    assert funnel["Bericht"] == (0, 0)  # only the owner got there


def test_old_rows_are_deleted():
    now = datetime(2026, 11, 20, tzinfo=timezone.utc)
    usage.record("203.0.113.7", UA, "page:home", now - timedelta(days=usage.KEEP_DAYS + 5))
    usage._trim(usage._db(), now.date().isoformat())
    assert rows() == []


def test_the_page_and_its_requests_are_counted(client):
    client.headers["User-Agent"] = UA
    assert client.post("/api/usage/event", json={"name": "page:potential-analysis"}).status_code == 204
    assert client.post("/api/usage/event", json={"name": "anything else"}).status_code == 204
    client.post("/api/io/export-csv", json={})
    client.post("/api/io/export-csv", json={}, headers={"X-Actor": "ai"})  # the AI is not a visitor
    assert [r[3] for r in rows()] == ["page:potential-analysis", "POST /api/io/export-csv"]
    me = client.get("/api/usage/me").json()
    assert set(me) == {"address", "owner"}
