"""Files the tools take from or hand back to the user, locally or online."""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import secrets
import time
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

from heattransplan_mcp.api import ApiError

# ── Files ───────────────────────────────────────────────────────────────────
# Run locally (stdio) the tools read and write files on the user's computer.
# Served online (the backend's /mcp, see backend/app/mcp_http.py) the server
# must never touch its own disk for a caller: files come in as content and go
# out as download links. A link works once: the file leaves the server's
# memory when it is downloaded, when the link expires unused, or when the
# page it was made for closes (forget).

HOSTED = False
# Public address of the app, for download links; set per request when hosted.
BASE_URL: ContextVar[str] = ContextVar("BASE_URL", default=os.getenv("PUBLIC_URL", ""))
DOWNLOAD_SECONDS = 600
# Memory the links may hold: per file, per page and in all. Reports carry
# map snapshots and site plans, hence megabytes.
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_PAGE_BYTES = 50 * 1024 * 1024
MAX_PAGE_FILES = 10
MAX_TOTAL_BYTES = 200 * 1024 * 1024
# A file handed in as content (base64 or text).
MAX_INPUT_BYTES = 25 * 1024 * 1024
# token → (file name, bytes, media type, expiry, owner: the page's project id).
# ponytail: in memory, one process (as live sessions).
_downloads: Dict[str, tuple] = {}


def _read_input(file_path: Optional[str], content: Any) -> tuple[str, bytes]:
    """(name, bytes) of a file the user gives: by content, or by a local path."""
    name = Path(file_path).name if file_path else "upload"
    if isinstance(content, (dict, list)):
        # JSON given as text arrives parsed.
        data = json.dumps(content).encode("utf-8")
    elif content is not None:
        if len(content) > MAX_INPUT_BYTES * 4 // 3 + 4:
            raise ApiError(f"The file is too large (over {MAX_INPUT_BYTES // 2**20} MB).")
        try:
            data = base64.b64decode(content, validate=True)
        except (binascii.Error, ValueError):
            data = content.encode("utf-8")
    elif HOSTED:
        raise ApiError("This HeatTransPlan server runs online and cannot open files on the user's "
                       "computer. Pass the file as content (base64, or text for CSV/JSON), or ask "
                       "the user to load it on the page.")
    elif not file_path:
        raise ApiError("Give file_path or content.")
    else:
        path = Path(file_path).expanduser()
        try:
            return path.name, path.read_bytes()
        except OSError as exc:
            raise ApiError(f"Cannot open {path}: {exc.strerror}") from exc
    if len(data) > MAX_INPUT_BYTES:
        raise ApiError(f"The file is too large (over {MAX_INPUT_BYTES // 2**20} MB).")
    return name, data


def _deliver(file_path: Optional[str], default_name: str, data: bytes, media_type: str,
             owner: str = "") -> str:
    """Write a result to the user's computer, or online hand out a download
    link for the page with project id `owner`, which goes when that page closes."""
    if not HOSTED:
        if not file_path:
            raise ApiError("file_path is needed: where to save it.")
        path = Path(file_path).expanduser()
        path.write_bytes(data)
        return f"Saved to {path}"
    if not owner:
        raise ApiError("A download needs the open page: give its Connect AI code.")
    if len(data) > MAX_FILE_BYTES:
        raise ApiError(f"The file is too large to hand out (over {MAX_FILE_BYTES // 2**20} MB).")
    now = time.time()
    sweep(now)
    # A page's own oldest links make room for its new one; other pages' never do.
    mine = [t for t, f in _downloads.items() if f[4] == owner]  # oldest first
    while mine and (len(mine) >= MAX_PAGE_FILES or
                    sum(len(_downloads[t][1]) for t in mine) + len(data) > MAX_PAGE_BYTES):
        _downloads.pop(mine.pop(0), None)
    if sum(len(f[1]) for f in _downloads.values()) + len(data) > MAX_TOTAL_BYTES:
        raise ApiError("The server holds too many downloads right now; try again in a few minutes.")
    token = secrets.token_urlsafe(16)
    name = re.sub(r"[^\w.-]", "_", Path(file_path).name) if file_path else default_name
    _downloads[token] = (name, data, media_type, now + DOWNLOAD_SECONDS, owner)
    return (f"Download link for the user (works once, valid for 10 minutes while the page is "
            f"open): {BASE_URL.get().rstrip('/')}/api/mcp/files/{token}/{quote(name)}")


def sweep(now: Optional[float] = None) -> None:
    """Drop the links that expired (also on a timer online, app/mcp_http.py)."""
    now = time.time() if now is None else now
    for token in [t for t, f in _downloads.items() if f[3] < now]:
        _downloads.pop(token, None)


def forget(owner: str) -> None:
    """The page closed: its links go with it."""
    for token in [t for t, f in _downloads.items() if f[4] == owner]:
        _downloads.pop(token, None)


def download(token: str, name: str) -> Optional[tuple]:
    """A file handed out by _deliver, once: it is removed as it is taken.
    None when the link expired, was used, or names another file."""
    sweep()
    found = _downloads.get(token)
    if not found or found[0] != name:
        return None
    return _downloads.pop(token)
