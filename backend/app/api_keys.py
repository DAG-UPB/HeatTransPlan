"""API keys for /api/* and /mcp, issued to anybody with one click and kept
nowhere: a key is signed with API_KEY_SECRET, so checking it needs no
storage. The server keeps no list of keys and no record of who got one.

What keys are for: limits per key instead of per IP (app/rate_limit.py), and
switching off one misused key (API_KEY_BLOCKLIST) without touching anyone
else. They do not keep anyone out: anybody may get one.

  user key    htp_<id>.<sig>             no expiry; POST /api/keys
  page token  htp_page_<id>.<exp>.<sig>  ~24 h; POST /api/keys/page, the page's own
  operator    any value in API_KEYS      as before, accepted as it is

The key comes as X-API-Key or "Authorization: Bearer <key>"; on /mcp also as
?key=<key>, for Claude.ai and ChatGPT, whose connectors cannot send headers.
That parameter is removed before the MCP app sees the request.

API_KEY_SECRET unset and API_KEYS empty: no checking at all (local use,
tests). Changing API_KEY_SECRET invalidates every key at once.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from urllib.parse import parse_qsl, urlencode

from app import rate_limit
from app.rate_limit import INTERNAL_HEADER, INTERNAL_TOKEN

SECRET = os.getenv("API_KEY_SECRET", "").strip().encode()
# Key ids (the part after htp_ / htp_page_ and before the first dot).
BLOCKLIST = {s.strip() for s in os.getenv("API_KEY_BLOCKLIST", "").split(",") if s.strip()}
# Operator keys, accepted as they are.
API_KEYS = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]
PAGE_TTL = 24 * 3600
_SIG = 32  # characters of the signature kept

# Reachable without a key: what the page needs before it has one, the AI's
# one-time download links (opened in the browser; the token is the secret),
# and the API's own documentation.
OPEN_PATHS = {"/api/health", "/api/features", "/api/keys", "/api/keys/page",
              "/api/docs", "/api/docs/oauth2-redirect", "/api/redoc", "/api/openapi.json"}
OPEN_PREFIXES = ("/api/mcp/files/",)
# Where the client's id is left for the rate limit.
CLIENT = "heattransplan.client"
# Refused requests per address and minute before 429: the rate limit only
# sees requests that got past this check.
REFUSALS = (60, 60)


def required() -> bool:
    return bool(SECRET or API_KEYS)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _sign(message: str) -> str:
    return _b64(hmac.new(SECRET, message.encode(), hashlib.sha256).digest())[:_SIG]


def issue_user_key() -> str:
    key_id = _b64(secrets.token_bytes(16))
    return f"htp_{key_id}.{_sign('user:' + key_id)}"


def issue_page_token(now: float | None = None) -> tuple[str, int]:
    key_id = _b64(secrets.token_bytes(16))
    exp = int((time.time() if now is None else now) + PAGE_TTL)
    return f"htp_page_{key_id}.{exp}.{_sign(f'page:{key_id}:{exp}')}", exp


def check(key: str, now: float | None = None) -> str | None:
    """Who the key stands for ("user:<id>", "page:<id>", "operator:<n>"), or
    None if it is not valid."""
    if not key:
        return None
    for n, operator in enumerate(API_KEYS):
        if hmac.compare_digest(key.encode(), operator.encode()):
            return f"operator:{n}"
    if not SECRET:
        return None
    parts = key.split(".")
    if key.startswith("htp_page_") and len(parts) == 3:
        key_id, exp, sig = parts[0][9:], parts[1], parts[2]
        if not exp.isdigit() or int(exp) <= (time.time() if now is None else now):
            return None
        message, who = f"page:{key_id}:{exp}", "page:" + key_id
    elif key.startswith("htp_") and len(parts) == 2:
        key_id, sig = parts[0][4:], parts[1]
        message, who = "user:" + key_id, "user:" + key_id
    else:
        return None
    if not key_id or key_id in BLOCKLIST:
        return None
    if not hmac.compare_digest(sig.encode(), _sign(message).encode()):
        return None
    return who


def _protected(path: str) -> bool:
    if path == "/mcp" or path.startswith("/mcp/"):
        return True
    if path != "/api" and not path.startswith("/api/"):
        return False
    return path not in OPEN_PATHS and not path.startswith(OPEN_PREFIXES)


class ApiKeyCheck:
    """ASGI middleware in front of every route: one place, so no router is
    left open by accident. Leaves the client's id in the scope for the rate
    limit, which runs after it."""

    def __init__(self, app, refusals=REFUSALS, enabled=None):
        self.app = app
        self.refusals = rate_limit.RateLimit(None, rules=[("", *refusals)], misses=refusals,
                                             enabled=rate_limit.ENABLED if enabled is None else enabled)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not required() or not _protected(scope["path"]):
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        # The MCP server's own calls into this backend (app/mcp_http.py).
        if hmac.compare_digest(headers.get(INTERNAL_HEADER, b""), INTERNAL_TOKEN.encode()):
            return await self.app(scope, receive, send)
        key = headers.get(b"x-api-key", b"").decode("latin-1").strip()
        bearer = headers.get(b"authorization", b"").decode("latin-1")
        if not key and bearer[:7].lower() == "bearer ":
            key = bearer[7:].strip()
        if scope["path"] == "/mcp" or scope["path"].startswith("/mcp/"):
            # ?key=: taken out, so the MCP app never sees or echoes it.
            query = parse_qsl(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True)
            rest = [(k, v) for k, v in query if k != "key"]
            if len(rest) != len(query):
                key = key or next(v for k, v in query if k == "key")
                scope = {**scope, "query_string": urlencode(rest).encode("latin-1")}
        who = check(key)
        if who is None:
            if self.refusals.enabled:
                ip, now, limit = (scope.get("client") or ("unknown",))[0], time.monotonic(), self.refusals
                limit._forget_idle(now)
                wait = limit._full(ip, *limit.rules[0][1:], now)
                if wait:
                    return await rate_limit._too_many(send, wait)
                limit.hits[ip].append(now)
            body = json.dumps({"detail": "Missing or invalid API key. Get one with POST /api/keys "
                                         "(or on the page: Connect AI → API key)."}).encode()
            await send({"type": "http.response.start", "status": 403, "headers": [
                (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body})
            return
        await self.app({**scope, CLIENT: who}, receive, send)
