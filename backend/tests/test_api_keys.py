"""API keys (app/api_keys.py): signed, so the server keeps nothing; every
/api route and /mcp wants one; a few endpoints stay open."""

import logging
import os
import time

import pytest
from fastapi.testclient import TestClient

from app import api_keys
from app.main import app
from app.rate_limit import RateLimit
from app.services import activity_log

MCP = {"Accept": "application/json, text/event-stream"}
TOOLS_LIST = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
PROTECTED = "/api/analysis/economics/defaults"


@pytest.fixture
def keys_on(monkeypatch):
    monkeypatch.setattr(api_keys, "SECRET", b"s" * 32)
    monkeypatch.setattr(api_keys, "BLOCKLIST", set())
    monkeypatch.setattr(api_keys, "API_KEYS", [])
    with TestClient(app) as c:
        yield c


def _id(key):
    return key.split(".")[0].removeprefix("htp_page_").removeprefix("htp_")


def test_without_a_secret_everything_is_open_as_before(client):
    assert client.get(PROTECTED).status_code == 200
    assert client.post("/mcp", headers=MCP, json=TOOLS_LIST).status_code == 200
    assert client.get("/api/features").json()["api_key"] is False
    assert client.post("/api/keys").status_code == 404
    assert client.post("/api/keys/page").json() == {"key": None, "expires_at": None}


def test_a_user_key_passes_a_bad_one_gets_403(keys_on, monkeypatch):
    c = keys_on
    assert c.get("/api/features").json()["user_keys"] is True
    key = c.post("/api/keys").json()["key"]
    assert key.startswith("htp_")
    assert c.get(PROTECTED, headers={"X-API-Key": key}).status_code == 200
    assert c.get(PROTECTED, headers={"Authorization": f"Bearer {key}"}).status_code == 200
    assert c.post("/mcp", headers={**MCP, "X-API-Key": key}, json=TOOLS_LIST).status_code == 200

    head, sig = key.split(".")
    tampered = f"{head}.{'A' if sig[0] != 'A' else 'B'}{sig[1:]}"
    other_id = f"htp_{'x' * 22}.{sig}"
    for bad in (None, "", tampered, other_id, "nonsense", f"{key}.extra", "htp_.abc"):
        h = {"X-API-Key": bad} if bad is not None else {}
        assert c.get(PROTECTED, headers=h).status_code == 403, bad
        assert c.post("/mcp", headers={**MCP, **h}, json=TOOLS_LIST).status_code == 403, bad

    # Another secret: the same key is no longer valid (the emergency switch).
    monkeypatch.setattr(api_keys, "SECRET", b"t" * 32)
    assert c.get(PROTECTED, headers={"X-API-Key": key}).status_code == 403


def test_a_blocklisted_key_is_refused_others_are_not(keys_on, monkeypatch):
    c = keys_on
    bad, good = c.post("/api/keys").json()["key"], c.post("/api/keys").json()["key"]
    monkeypatch.setattr(api_keys, "BLOCKLIST", {_id(bad)})
    assert c.get(PROTECTED, headers={"X-API-Key": bad}).status_code == 403
    assert c.post("/mcp", headers={**MCP, "X-API-Key": bad}, json=TOOLS_LIST).status_code == 403
    assert c.get(PROTECTED, headers={"X-API-Key": good}).status_code == 200


def test_a_page_token_lasts_a_day(keys_on):
    c = keys_on
    out = c.post("/api/keys/page").json()
    assert out["key"].startswith("htp_page_")
    assert abs(out["expires_at"] - (time.time() + api_keys.PAGE_TTL)) < 60
    assert c.get(PROTECTED, headers={"X-API-Key": out["key"]}).status_code == 200
    assert api_keys.check(out["key"], now=out["expires_at"] - 1) == "page:" + _id(out["key"])
    assert api_keys.check(out["key"], now=out["expires_at"]) is None
    # The expiry is signed: pushing it out breaks the signature.
    key_id, exp, sig = out["key"].split(".")
    assert api_keys.check(f"{key_id}.{int(exp) + 86400}.{sig}") is None
    old, _ = api_keys.issue_page_token(now=time.time() - api_keys.PAGE_TTL - 1)
    assert c.get(PROTECTED, headers={"X-API-Key": old}).status_code == 403


def test_operator_keys_still_work(keys_on, monkeypatch):
    monkeypatch.setattr(api_keys, "API_KEYS", ["op-secret"])
    assert keys_on.get(PROTECTED, headers={"X-API-Key": "op-secret"}).status_code == 200
    # Operator keys alone (no secret) still switch checking on.
    monkeypatch.setattr(api_keys, "SECRET", b"")
    assert keys_on.get(PROTECTED).status_code == 403
    assert keys_on.get(PROTECTED, headers={"X-API-Key": "op-secret"}).status_code == 200


def test_key_in_the_mcp_url_works_and_is_never_logged(keys_on, caplog):
    c = keys_on
    key = c.post("/api/keys").json()["key"]
    seen = {}
    from app import mcp_http
    handler = mcp_http.endpoint.handler

    async def spy(scope, receive, send):
        seen["query"] = scope["query_string"]
        await handler(scope, receive, send)

    mcp_http.endpoint.handler = spy
    try:
        with caplog.at_level(logging.DEBUG):
            r = c.post(f"/mcp?key={key}&x=1", headers=MCP, json=TOOLS_LIST)
            assert r.status_code == 200
            assert key not in r.text
            assert c.post("/mcp?key=htp_wrong.sig", headers=MCP, json=TOOLS_LIST).status_code == 403
            # ?key= is for /mcp only.
            assert c.get(f"{PROTECTED}?key={key}").status_code == 403
            # A logged change made with the key: the row holds no key.
            assert c.post("/api/io/export-csv", json={}, headers={"X-API-Key": key}).status_code == 200
    finally:
        mcp_http.endpoint.handler = handler
    assert seen["query"] == b"x=1"  # the MCP app never sees the key
    rows = activity_log.last(50)
    assert any(r[2] == "POST /api/io/export-csv" for r in rows)
    assert key not in repr(rows) and _id(key) not in repr(rows)
    with open(activity_log.PATH, "rb") as f:
        assert _id(key).encode() not in f.read()
    # The server's logs (not the test client's own, which prints its URLs).
    server_logs = "\n".join(r.getMessage() for r in caplog.records if not r.name.startswith("httpx"))
    assert server_logs and _id(key) not in server_logs


def test_the_open_endpoints_need_no_key(keys_on):
    c = keys_on
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/features").status_code == 200
    assert c.post("/api/keys").status_code == 200
    assert c.post("/api/keys/page").status_code == 200
    # An expired download link: 404 from the route, not 403 from the key check.
    assert c.get("/api/mcp/files/nope/x.csv").status_code == 404
    # The API reference wants a key, like every other /api address.
    assert c.get("/api/docs").status_code == 403
    assert c.get("/api/openapi.json").status_code == 403
    assert c.get("/api/openapi.json", headers={"X-API-Key": c.post("/api/keys").json()["key"]}).status_code == 200
    # Every other /api address wants a key, known or not.
    for path in ("/api/assets/examples", "/api/live/sessions/abc", "/api/nothing-here", "/api"):
        assert c.get(path).status_code == 403, path


def test_issuing_a_key_writes_and_keeps_nothing(keys_on, tmp_path, monkeypatch):
    def snapshot():
        found = set()
        for root in ("/tmp", os.getcwd(), os.path.dirname(os.path.dirname(api_keys.__file__))):
            for d, _, names in os.walk(root):
                if "__pycache__" in d or ".pytest_cache" in d:
                    continue
                found.update(os.path.join(d, n) for n in names)
        return found

    module = {k: (v if not isinstance(v, (set, list, dict)) else type(v)(v))
              for k, v in vars(api_keys).items()}
    before = snapshot()
    keys = {keys_on.post("/api/keys").json()["key"] for _ in range(3)}
    keys |= {keys_on.post("/api/keys/page").json()["key"] for _ in range(3)}
    assert len(keys) == 6
    assert snapshot() - before == set()
    after = vars(api_keys)
    assert {k: after[k] for k in module} == module
    for k in keys:  # nothing to look them up in, yet they all check out
        assert api_keys.check(k)


def test_the_mcp_servers_own_calls_pass_with_keys_on(keys_on):
    key = keys_on.post("/api/keys").json()["key"]
    r = keys_on.post("/mcp", headers={**MCP, "X-API-Key": key}, json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "list_examples", "arguments": {}}})
    out = r.json()["result"]
    assert not out.get("isError"), out
    assert "json" in out["content"][0]["text"]


def test_limits_count_per_key_and_per_address_for_the_open_ones():
    async def ok(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    import asyncio

    limiter = RateLimit(ok, rules=[("/api/keys", 2, 3600), ("/api/", 2, 60)], enabled=True)

    def call(path, who=None, ip="1.2.3.4"):
        sent = []

        async def send(m):
            sent.append(m)

        scope = {"type": "http", "path": path, "headers": [], "client": (ip, 1)}
        if who:
            scope[api_keys.CLIENT] = who
        asyncio.run(limiter(scope, None, send))
        return sent[0]["status"]

    # Two keys behind one address: each has its own limit.
    assert [call("/api/x", "user:a") for _ in range(3)] == [200, 200, 429]
    assert call("/api/x", "user:b") == 200
    # Getting keys counts per address.
    assert [call("/api/keys") for _ in range(3)] == [200, 200, 429]
    assert call("/api/keys", ip="5.6.7.8") == 200


def test_refused_requests_are_limited_per_address(monkeypatch):
    monkeypatch.setattr(api_keys, "SECRET", b"s" * 32)
    monkeypatch.setattr(api_keys, "API_KEYS", [])
    import asyncio

    async def ok(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    check = api_keys.ApiKeyCheck(ok, refusals=(3, 60), enabled=True)

    def call(key="", ip="1.2.3.4"):
        sent = []

        async def send(m):
            sent.append(m)

        headers = [(b"x-api-key", key.encode())] if key else []
        asyncio.run(check({"type": "http", "path": "/api/x", "headers": headers,
                           "query_string": b"", "client": (ip, 1)}, None, send))
        return sent[0]["status"]

    assert [call("htp_bad.sig") for _ in range(4)] == [403, 403, 403, 429]
    assert call(ip="5.6.7.8") == 403  # another address is not affected
    assert call(api_keys.issue_user_key()) == 200  # a valid key is never held back here
