"""
Live router — an open page registers here so an AI can watch and drive it.
See app/services/live.py for how sessions, events and commands fit together.

Who may do what: the page (its page token, header X-Live-Page-Token) listens,
answers, pauses, resumes and ends; the AI (the code alone) finds the page
and sends it commands, which the page runs, asking its user first before
anything that deletes or replaces.
"""

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services import live

router = APIRouter()

PAGE_TOKEN = "X-Live-Page-Token"


class Command(BaseModel):
    name: str = Field(max_length=64)
    args: Dict[str, Any] = Field(default_factory=dict)
    timeout: float = Field(30.0, gt=0, le=300)
    # The MCP tool that sent it, for the page's activity list.
    tool: Optional[str] = Field(None, max_length=64, pattern=r"^[a-z_]+$")


class Pause(BaseModel):
    paused: bool


class CommandResult(BaseModel):
    ok: bool
    result: Any = None
    error: Optional[str] = Field(None, max_length=2000)


def _session(session_id: str) -> live.Session:
    session = live.get(session_id)
    if session is None:
        raise HTTPException(404, "Live session not found")
    return session


def _own(session_id: str, token: Optional[str]) -> live.Session:
    """The session, for its page only: the code alone is not enough."""
    session = _session(session_id)
    if not session.is_page(token):
        raise HTTPException(403, "Only the page that opened this session may do this")
    return session


@router.post("/sessions")
async def create_session():
    """Start a session for a page. Nothing of its project is sent or kept:
    the AI reads and edits it through commands the page runs. project_id is
    only a second name the AI can address the page by. page_token is the
    page's own key to its session; it is returned only here."""
    try:
        session = live.create()
    except live.TooManySessions as exc:
        raise HTTPException(503, str(exc)) from exc
    return {**session.summary(), "page_token": session.page_token}


def _page(key: str) -> live.Session:
    session = live.connected_session(key)
    if session is None:
        raise HTTPException(404, "No open page is connected with this code or project")
    return session


@router.get("/pages/{key}")
async def connected_page(key: str):
    """The open, connected page with this code or project id: its project and
    session. 404 when no such page is open, 423 while the user paused the AI."""
    session = _page(key)
    if session.paused:
        raise HTTPException(423, "The user has paused the AI on this page")
    return {"project_id": session.project_id, "session_id": session.id}


@router.post("/pages/{key}/log")
async def log_ai_action(key: str):
    """Gone: the server notes the AI's activity itself, from the commands it
    passed on. 410, not 404, so older MCP servers calling it do not count as
    guessing codes."""
    raise HTTPException(410, "The server records the AI's activity itself")


@router.put("/sessions/{session_id}/pause")
async def pause(session_id: str, body: Pause, token: Optional[str] = Header(None, alias=PAGE_TOKEN)):
    """The user pauses or resumes the AI on their page."""
    session = _own(session_id, token)
    live.set_paused(session, body.paused)
    return {"paused": session.paused}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, token: Optional[str] = Header(None, alias=PAGE_TOKEN)):
    """The session (a reloaded page uses it to reconnect)."""
    return _own(session_id, token).summary()


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, token: Optional[str] = Header(None, alias=PAGE_TOKEN)):
    """Disconnect: the session ends."""
    live.end(_own(session_id, token).id)
    return {"deleted": True}


@router.get("/sessions/{session_id}/events")
async def session_events(session_id: str, token: Optional[str] = Header(None, alias=PAGE_TOKEN)):
    """Server-sent events for the page: `command` when it should run one,
    `ai_log` when the AI did something, `paused` when that changed,
    `replaced` when another listener took over, `ended`."""
    session = _own(session_id, token)
    return StreamingResponse(
        live.events(session),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/commands")
async def run_command(session_id: str, command: Command):
    """Run a command on the page and wait for its answer."""
    session = _session(session_id)
    try:
        result = await live.send_command(session, command.name, command.args, command.timeout,
                                         command.tool)
    except live.SessionNotConnected as exc:
        raise HTTPException(409, str(exc)) from exc
    except live.SessionPaused as exc:
        raise HTTPException(423, str(exc)) from exc
    except live.PageBusy as exc:
        raise HTTPException(503, str(exc)) from exc
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, f"The page did not answer '{command.name}' in time.") from exc
    except RuntimeError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"ok": True, "result": result}


@router.post("/sessions/{session_id}/commands/{command_id}/result")
async def post_result(session_id: str, command_id: str, body: CommandResult,
                      token: Optional[str] = Header(None, alias=PAGE_TOKEN)):
    """The page's answer to a command."""
    if not live.resolve(_own(session_id, token), command_id, body.ok, body.result, body.error):
        raise HTTPException(409, "No command is waiting for this answer")
    return {"ok": True}
