"""Live sessions: a page subscribes, the AI runs commands on it, the page
answers. The server keeps nothing of the project, and the code the user
gives the AI does not let anyone act as the page."""

import asyncio
import json

import pytest

from app.services import live


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    monkeypatch.setattr(live, "_sessions", {})


def _parse(chunk: str) -> dict:
    event = chunk.split("\n")[0].removeprefix("event: ")
    data = json.loads(chunk.split("data: ", 1)[1])
    return {"event": event, **data}


def _new(client):
    """A session as the page gets it: its code and its own page token."""
    created = client.post("/api/live/sessions").json()
    return created["session_id"], {"X-Live-Page-Token": created["page_token"]}


def test_a_command_reaches_the_page_and_its_answer_comes_back():
    async def scenario():
        session = live.create()
        stream = live.events(session)
        assert _parse(await stream.__anext__())["event"] == "hello"

        call = asyncio.create_task(live.send_command(session, "set_t_min", {"value": 15}))
        cmd = _parse(await stream.__anext__())
        assert (cmd["event"], cmd["name"], cmd["args"]) == ("command", "set_t_min", {"value": 15})
        assert live.resolve(session, cmd["id"], True, {"t_min": 15})
        assert await call == {"t_min": 15}

        assert _parse(await stream.__anext__())["event"] == "ai_log"  # the change, for the page's list
        call = asyncio.create_task(live.send_command(session, "explode", {}))
        cmd = _parse(await stream.__anext__())
        live.resolve(session, cmd["id"], False, error="Unknown command")
        with pytest.raises(RuntimeError, match="Unknown command"):
            await call
        await stream.aclose()
        assert not session.connected

    asyncio.run(scenario())


def test_a_command_without_a_page_fails_fast(client):
    sid, mine = _new(client)
    # Sessions are not listed: the code is the user's key to their page. (Without
    # a built frontend the answer is a JSON 404, with one its page: neither lists it.)
    assert sid not in client.get("/api/live/sessions").text
    r = client.post(f"/api/live/sessions/{sid}/commands", json={"name": "navigate", "args": {"page": "home"}})
    assert r.status_code == 409
    assert client.get(f"/api/live/sessions/{sid}", headers=mine).json()["session_id"] == sid


def test_the_code_alone_cannot_act_as_the_page(client):
    """Whoever has the code (the AI, or someone who saw it) cannot listen to
    the page's events, answer for it, lift its pause, end or look up its
    session: only the page's own token can."""
    sid, mine = _new(client)
    assert "page_token" not in client.get(f"/api/live/sessions/{sid}", headers=mine).json()
    for headers in ({}, {"X-Live-Page-Token": "guessed"}):
        assert client.get(f"/api/live/sessions/{sid}/events", headers=headers).status_code == 403
        assert client.get(f"/api/live/sessions/{sid}", headers=headers).status_code == 403
        assert client.post(f"/api/live/sessions/{sid}/commands/abc/result", headers=headers,
                           json={"ok": True, "result": {"fake": "data"}}).status_code == 403
        assert client.put(f"/api/live/sessions/{sid}/pause", headers=headers,
                          json={"paused": False}).status_code == 403
        assert client.delete(f"/api/live/sessions/{sid}", headers=headers).status_code == 403
    assert live.get(sid) is not None
    # The page itself can.
    assert client.put(f"/api/live/sessions/{sid}/pause", headers=mine, json={"paused": True}).json() == {"paused": True}
    assert client.delete(f"/api/live/sessions/{sid}", headers=mine).status_code == 200
    assert live.get(sid) is None


def test_a_code_holder_cannot_answer_a_command_or_read_it():
    """A command the code holder sends (e.g. set_project with state None)
    goes to the page alone, which asks its user (frontend/src/live/commands.ts);
    the code holder can neither see it nor answer it in the page's place."""
    async def scenario():
        session = live.create()
        stream = live.events(session)
        await stream.__anext__()
        wipe = asyncio.create_task(live.send_command(session, "set_project", {"state": None}, 1))
        cmd = _parse(await stream.__anext__())
        assert cmd["name"] == "set_project"  # it is the page's to decide
        assert session.is_page(session.page_token) and not session.is_page("") and not session.is_page(None)
        live.resolve(session, cmd["id"], False, error="The user declined this on the page.")
        with pytest.raises(RuntimeError, match="declined"):
            await wipe
        assert list(session.log) == []  # nothing was changed, nothing listed
        await stream.aclose()

    asyncio.run(scenario())


def test_ai_switched_off_leaves_the_rest():
    """AI off, as it is without AI_ENABLED: no Connect AI, no live endpoints,
    no /mcp; the rest still works."""
    import subprocess
    import sys
    code = (
        "import os; os.environ.pop('AI_ENABLED', None)\n"
        "from fastapi.testclient import TestClient\nfrom app.main import app\n"
        "with TestClient(app) as c:\n"
        "    f = c.get('/api/features').json()\n"
        "    print(f['ai'], f['mcp'], c.post('/api/live/sessions', json={}).status_code,\n"
        "          c.post('/mcp', json={}).status_code, c.post('/api/io/import-json-body', json={}).status_code)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.split()
    assert out[:2] == ["False", "False"]
    assert out[2] in ("404", "405") and out[3] in ("404", "405") and out[4] == "200"


def test_the_server_keeps_no_project(client):
    """Starting a session sends nothing of the project and stores nothing:
    there is no project store and no endpoint to put one in."""
    import app.services as services
    assert not hasattr(services, "project_service")
    created = client.post("/api/live/sessions").json()
    sid, pid = created["session_id"], created["project_id"]
    mine = {"X-Live-Page-Token": created["page_token"]}
    for method, path in (("POST", "/api/projects"), ("PUT", f"/api/projects/{pid}"),
                         ("PUT", f"/api/live/sessions/{sid}/view")):
        assert client.request(method, path, json={}).status_code in (404, 405)
    assert set(vars(live.get(sid))) == {"id", "project_id", "page_token", "created", "last_seen",
                                        "subscriber", "pending", "paused", "log"}
    assert client.delete(f"/api/live/sessions/{sid}", headers=mine).status_code == 200
    assert live.get(sid) is None


def test_a_closed_page_ends_its_session(monkeypatch):
    """When the page's stream closes and it does not come back within the
    grace time, the session ends, and so does one no page ever connected to."""
    monkeypatch.setattr(live, "DISCONNECT_GRACE_SECONDS", 0.05)

    async def scenario():
        session = live.create()
        never = live.create()
        stream = live.events(session)
        await stream.__anext__()  # hello: the page is connected
        await stream.aclose()  # the page closed
        assert live.get(session.id) is not None  # a reload may follow
        await asyncio.sleep(0.2)
        return session.id, never.id

    for sid in asyncio.run(scenario()):
        assert live.get(sid) is None


def test_a_reloaded_page_keeps_its_session(monkeypatch):
    monkeypatch.setattr(live, "DISCONNECT_GRACE_SECONDS", 0.1)

    async def scenario():
        session = live.create()
        first = live.events(session)
        await first.__anext__()
        await first.aclose()
        second = live.events(session)  # reconnected within the grace time
        await second.__anext__()
        await asyncio.sleep(0.25)
        alive = live.get(session.id) is not None
        await second.aclose()
        return alive

    assert asyncio.run(scenario())


def test_one_listener_a_new_one_takes_over():
    """The page's stream is the only one: a second (a reload, a duplicated
    tab) takes over and the first ends; the session stays connected."""
    async def scenario():
        session = live.create()
        first = live.events(session)
        await first.__anext__()
        second = live.events(session)
        await second.__anext__()
        assert _parse(await first.__anext__())["event"] == "replaced"
        with pytest.raises(StopAsyncIteration):
            await first.__anext__()
        assert session.connected
        call = asyncio.create_task(live.send_command(session, "get_view", {}))
        cmd = _parse(await second.__anext__())
        live.resolve(session, cmd["id"], True, {"page": "/"})
        assert await call == {"page": "/"}
        await second.aclose()
        assert not session.connected

    asyncio.run(scenario())


def test_pausing_stops_the_ai_and_the_page_hears_it(client, monkeypatch):
    sid, mine = _new(client)
    monkeypatch.setattr(live.Session, "connected", property(lambda s: True))
    seen = []
    monkeypatch.setattr(live, "_publish", lambda session, event: seen.append(event) or True)
    assert client.get(f"/api/live/pages/{sid}").json()["session_id"] == sid

    assert client.put(f"/api/live/sessions/{sid}/pause", headers=mine, json={"paused": True}).json() == {"paused": True}
    assert seen[-1] == {"type": "paused", "paused": True}
    assert client.get(f"/api/live/sessions/{sid}", headers=mine).json()["paused"] is True
    assert client.get(f"/api/live/pages/{sid}").status_code == 423
    r = client.post(f"/api/live/sessions/{sid}/commands", json={"name": "navigate", "args": {}})
    assert r.status_code == 423
    client.put(f"/api/live/sessions/{sid}/pause", headers=mine, json={"paused": False})
    assert seen[-1] == {"type": "paused", "paused": False}
    assert client.get(f"/api/live/pages/{sid}").status_code == 200


def test_the_activity_list_is_what_the_server_passed_on(client):
    """The page's list of the AI's changes comes from the commands the server
    sent and the page carried out: reads, refusals and forged entries are not on it."""
    sid, _ = _new(client)
    assert client.post(f"/api/live/pages/{sid}/log", json={"tool": "add_stream", "detail": "forged"}).status_code == 410
    session = live.get(sid)

    async def scenario():
        stream = live.events(session)
        await stream.__anext__()

        async def page():
            async for chunk in stream:
                if chunk.startswith("event: command"):
                    cmd = _parse(chunk)
                    live.resolve(session, cmd["id"], cmd["name"] != "set_project", {"ok": True},
                                 "The user declined this on the page.")

        task = asyncio.create_task(page())
        await live.send_command(session, "get_project", {})
        await live.send_command(session, "edit_project", {"changes": {"processes": []}, "label": "add stream Wort"},
                                tool="add_stream")
        await live.send_command(session, "set_t_min", {"value": 12}, tool="live_set_analysis")
        with pytest.raises(RuntimeError):
            await live.send_command(session, "set_project", {"state": None})
        task.cancel()

    asyncio.run(scenario())
    assert [(e["tool"], e["detail"]) for e in session.log] == [
        ("add_stream", "add stream Wort"), ("live_set_analysis", "set_t_min value=12")]


def test_sessions_and_waiting_events_are_bounded(client, monkeypatch):
    monkeypatch.setattr(live, "MAX_SESSIONS", 2)
    _new(client)
    _new(client)
    assert client.post("/api/live/sessions").status_code == 503

    monkeypatch.setattr(live, "_sessions", {})
    monkeypatch.setattr(live, "QUEUE_SIZE", 2)

    async def scenario():
        session = live.create()
        stream = live.events(session)
        await stream.__anext__()  # listening, but it reads nothing more
        waiting = [asyncio.create_task(live.send_command(session, "get_view", {}, 5)) for _ in range(2)]
        await asyncio.sleep(0)
        with pytest.raises(live.PageBusy):
            await live.send_command(session, "get_view", {})
        assert session.subscriber.qsize() == 2
        live.end(session.id)  # the waiting ones fail at once, they do not hang
        for w in waiting:
            with pytest.raises(live.SessionNotConnected):
                await w
        await stream.aclose()

    asyncio.run(scenario())


def test_only_real_codes_and_project_ids(client):
    """Anything but a code or a project id as the server makes them finds nothing."""
    sid, _ = _new(client)
    for key in ("..%2F..%2Fanalysis", "ABC", sid.upper(), sid + "0", "abc%3Fx=1"):
        assert client.get(f"/api/live/pages/{key}").status_code == 404
    for key in ("../x", sid + "/", "", "4f1c2a9e-0000-1000-8000-000000000000"):
        assert live.connected_session(key) is None and live.get(key) is None


def test_an_ended_session_leaves_nothing(client):
    """Ending a session drops its activity list and what others keep for it
    (the hooks: the MCP server's analysis, models, downloads)."""
    sid, mine = _new(client)
    session = live.get(sid)
    ended = []
    stop = live.on_end(ended.append)
    try:
        live.record(session, "add_stream", "name=Wort cooler")
        client.delete(f"/api/live/sessions/{sid}", headers=mine)
    finally:
        stop()
    assert ended == [session] and list(session.log) == [] and live.get(sid) is None
    assert ended.append not in live._end_hooks
