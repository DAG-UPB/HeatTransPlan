"""Live sessions: an open page that an AI (through the MCP server) can watch
and drive.

The server never holds the project: the page does. A session is only a
relay. The page registers one and listens on an event stream for commands
(read the project, apply an edit, navigate, select streams, pick a heat
pump, ...). It runs each command with the same functions its own buttons
call, then posts the result back, which is what the command call returns.

Two secrets, for two parties:
- the code (session id, 8 hex): what the user gives the AI. It only lets
  the AI address the page: find it and send it commands. The page itself
  asks the user before any command that deletes or replaces, whoever sent it.
- the page token: returned once, to the page that made the session. Only it
  may listen to the event stream (one listener), answer commands, pause,
  resume and end the session. A code holder can therefore neither read what
  the AI sends and gets nor answer in the page's place.

A session also carries an id the AI may address the page by (project_id, a
random id with no data behind it) and the AI's activity list, in memory,
noted here from the commands actually sent. When the page's stream closes
and it does not reconnect within DISCONNECT_GRACE_SECONDS (a reload does),
the session ends and all of it is gone, also what others keep for it (see
on_end).

Held in memory: the backend runs as one process (see the Dockerfile).
ponytail: one process only; a shared broker (e.g. Redis) when it runs on more.
"""

from __future__ import annotations

import asyncio
import json
import re
import secrets
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from app.services import activity_log

# A page that closed its stream has this long to reconnect (a reload) before
# its session ends. Also the limit for a session no page ever connected to.
DISCONNECT_GRACE_SECONDS = 120
# Keeps proxies from closing a quiet stream.
HEARTBEAT_SECONDS = 15
# Open sessions at once, so nobody can fill the server's memory with them.
MAX_SESSIONS = 1000
# Events waiting for a page that does not read them; a command beyond that fails.
QUEUE_SIZE = 256

CODE = re.compile(r"[0-9a-f]{8}")
PROJECT_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")

# Commands that only read: not on the page's activity list.
READS = {"get_view", "get_results", "list_commands", "wait_idle", "get_project", "export_csv",
         "export_distances_csv", "confirm_ai_action", "generate_report"}
# Arguments too big or too private to show in full on the activity list.
BULKY = {"state", "data", "changes", "model", "content", "html"}


class SessionNotConnected(Exception):
    """No page is listening on the session, so a command cannot run."""


class SessionPaused(Exception):
    """The user paused the AI on the page: nothing runs until they resume."""


class TooManySessions(Exception):
    """The server holds as many sessions as it allows."""


class PageBusy(Exception):
    """The page has not read its earlier events; it gets no more for now."""


@dataclass
class Session:
    id: str
    project_id: str
    # Only the page has it (see the module's docstring).
    page_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    created: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    # The page's event queue while it listens; one listener only.
    subscriber: Optional[asyncio.Queue] = None
    pending: Dict[str, asyncio.Future] = field(default_factory=dict)
    # Set by the user on the page; the AI then can do nothing until resumed.
    paused: bool = False
    # What the AI did, newest last, for the page's activity list.
    log: deque = field(default_factory=lambda: deque(maxlen=100))

    @property
    def connected(self) -> bool:
        return self.subscriber is not None

    def summary(self) -> Dict[str, Any]:
        return {
            "session_id": self.id,
            "project_id": self.project_id,
            "connected": self.connected,
            "last_seen": self.last_seen,
            "paused": self.paused,
        }

    def is_page(self, token: Optional[str]) -> bool:
        return bool(token) and secrets.compare_digest(token.encode(), self.page_token.encode())


_sessions: Dict[str, Session] = {}
# Called with each session that ends, so what others keep for it goes too
# (the MCP server's analysis, models and downloads, app/mcp_http.py).
_end_hooks: List[Callable[[Session], None]] = []


def on_end(hook: Callable[[Session], None]) -> Callable[[], None]:
    """Call hook(session) whenever a session ends. Returns the undo."""
    _end_hooks.append(hook)
    return lambda: _end_hooks.remove(hook) if hook in _end_hooks else None


def end(session_id: str) -> bool:
    """End a session. False when there was no such session."""
    session = _sessions.pop(session_id, None)
    if session is None:
        return False
    for future in session.pending.values():
        if not future.done():
            future.set_exception(SessionNotConnected("The page closed its session."))
    session.pending.clear()
    session.log.clear()
    if session.subscriber is not None:
        _offer(session.subscriber, {"type": "ended"})
    for hook in list(_end_hooks):
        try:
            hook(session)
        except Exception:  # a hook's failure must not keep the session alive
            pass
    return True


def prune() -> None:
    """End the sessions whose page is gone (a timer does it too, see
    _end_unless_back; this catches what it missed)."""
    now = time.time()
    for sid in [s.id for s in _sessions.values()
                if not s.connected and now - s.last_seen > DISCONNECT_GRACE_SECONDS]:
        end(sid)


async def _end_unless_back(session: Session) -> None:
    """After the page's stream closed (or a session was made): end the
    session unless a page is connected by then."""
    await asyncio.sleep(DISCONNECT_GRACE_SECONDS)
    if (_sessions.get(session.id) is session and not session.connected
            and time.time() - session.last_seen >= DISCONNECT_GRACE_SECONDS - 1):
        end(session.id)


def _watch(session: Session) -> None:
    try:
        asyncio.get_running_loop().create_task(_end_unless_back(session))
    except RuntimeError:
        pass  # no event loop (a plain function call): prune() catches it


def create() -> Session:
    prune()
    if len(_sessions) >= MAX_SESSIONS:
        raise TooManySessions("Too many open AI sessions on this server; try again later.")
    code = secrets.token_hex(4)
    while code in _sessions:
        code = secrets.token_hex(4)
    session = Session(id=code, project_id=str(uuid.uuid4()))
    _sessions[session.id] = session
    # A session no page ever connects to ends as a closed one does.
    _watch(session)
    return session


def valid_key(key: str) -> bool:
    """A code or a project id as this module makes them, nothing else."""
    return bool(CODE.fullmatch(key) or PROJECT_ID.fullmatch(key))


def get(session_id: str) -> Optional[Session]:
    return _sessions.get(session_id) if CODE.fullmatch(session_id or "") else None


def connected_session(key: str) -> Optional[Session]:
    """The session of a page that is open and connected, found by its code or
    its project id. The AI works only on such a page."""
    if not valid_key(key or ""):
        return None
    if CODE.fullmatch(key):
        s = _sessions.get(key)
        return s if s and s.connected else None
    for s in _sessions.values():
        if s.connected and s.project_id == key:
            return s
    return None


def _detail(name: str, args: Dict[str, Any], tool: Optional[str]) -> str:
    """A command in a line for the user: an edit by its label, else its
    arguments (big or private ones only by name)."""
    if name == "edit_project":
        text = str(args.get("label") or "edit")
    else:
        parts = []
        for k, v in args.items():
            if v is None or k == "ask":
                continue
            if k in BULKY:
                parts.append(f"{k}=…")
                continue
            t = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
            parts.append(f"{k}={t[:60] + '…' if len(t) > 60 else t}")
        text = ", ".join(parts)
        if tool and tool != name:
            text = f"{name} {text}".strip()
    return text[:500]


def record(session: Session, tool: str, detail: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """Note what the AI did: in full on the page's activity list (its user sees
    it), anonymously in the activity log (the tool and the names of the fields
    it set, never their values)."""
    entry = {"time": time.time(), "tool": tool, "detail": detail}
    session.log.append(entry)
    _publish(session, {"type": "ai_log", **entry})
    names = [f for f in fields or [] if isinstance(f, str) and f.isidentifier()]
    activity_log.write("ai", tool, ", ".join(names[:40]))
    return entry


def _offer(queue: asyncio.Queue, event: Dict[str, Any]) -> bool:
    try:
        queue.put_nowait(event)
        return True
    except asyncio.QueueFull:
        return False


def _publish(session: Session, event: Dict[str, Any]) -> bool:
    """To the page, if it listens and keeps up. False when it got nothing."""
    return session.subscriber is not None and _offer(session.subscriber, event)


def set_paused(session: Session, paused: bool) -> None:
    """The user's pause: the server refuses the AI's commands while it holds,
    and the page shows it (after a reload too, from the hello event)."""
    session.paused = paused
    _publish(session, {"type": "paused", "paused": paused})


async def send_command(session: Session, name: str, args: Dict[str, Any], timeout: float = 30.0,
                       tool: Optional[str] = None) -> Any:
    """Run a command on the page and return what it answered. What the page
    changed goes on its activity list from here, so nobody can add to it."""
    if not session.connected:
        raise SessionNotConnected(f"No page is connected to session {session.id}.")
    if session.paused:
        raise SessionPaused("The user has paused the AI on this page.")
    command_id = uuid.uuid4().hex
    future: asyncio.Future = asyncio.get_running_loop().create_future()
    session.pending[command_id] = future
    try:
        if not _publish(session, {"type": "command", "id": command_id, "name": name, "args": args}):
            raise PageBusy("The page is not keeping up with the AI's commands; try again shortly.")
        result = await asyncio.wait_for(future, timeout)
    finally:
        session.pending.pop(command_id, None)
    if name not in READS and _sessions.get(session.id) is session:
        changes = args.get("changes") if name == "edit_project" else None
        fields = list(changes) if isinstance(changes, dict) else list(args)
        record(session, tool or name, _detail(name, args, tool), fields)
    return result


def resolve(session: Session, command_id: str, ok: bool, result: Any = None, error: Optional[str] = None) -> bool:
    """The page's answer to a command. False when nobody waits for it any more."""
    future = session.pending.get(command_id)
    if future is None or future.done():
        return False
    if ok:
        future.set_result(result)
    else:
        future.set_exception(RuntimeError(error or "The page could not run the command."))
    return True


async def events(session: Session) -> AsyncIterator[str]:
    """The session's event stream in text/event-stream format, for its page.
    One listener: a new one (the page reloaded, or the tab was duplicated)
    takes over, and the old stream ends with a `replaced` event."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
    old = session.subscriber
    session.subscriber = queue
    if old is not None:
        # Room for the last word even when the old queue is full.
        while not _offer(old, {"type": "replaced"}):
            old.get_nowait()
    session.last_seen = time.time()
    try:
        yield f"event: hello\ndata: {json.dumps(session.summary())}\n\n"
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue
            session.last_seen = time.time()
            yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
            if event["type"] in ("replaced", "ended"):
                return
    finally:
        if session.subscriber is queue:
            session.subscriber = None
            session.last_seen = time.time()
            if _sessions.get(session.id) is session:
                _watch(session)
