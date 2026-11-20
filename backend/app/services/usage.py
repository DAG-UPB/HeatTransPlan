"""Who uses the app and how far they get, anonymously: one SQLite table next
to the activity log (app/services/activity_log.py, same Docker volume).

A row says on which day a visitor did one of a fixed list of things (opened a
page, ran a step of the analysis, loaded the example, ...). The visitor is a
code, not a person: a hash of the address and the browser name with a key
that is made new every day and only ever held in memory, so the same visitor
is one code for a day and cannot be followed from one day to the next, nor
traced back to an address. Nothing is stored in the browser (no cookie).

The owner's own visits are told apart by address: OWNER_IPS (comma separated
addresses or networks, e.g. 131.234.0.0/16 or 2001:db8:1:2::/64) in .env.
The address is compared when the request comes in and only "owner yes/no"
is written, never the address. GET /api/usage/me shows the address the
server sees, to put into OWNER_IPS.

Never the data: event names come from a fixed list (EVENTS, the API routes
in STAGES), anything else is dropped. Rows older than KEEP_DAYS (90) are deleted.
Read it with
    docker compose exec backend python -m app.services.usage [days] [--json]
or as a report in data/usage/ (gitignored): python3 scripts/usage_report.py
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import re
import secrets
import sqlite3
import sys
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.rate_limit import visitor as counted_address
from app.services import activity_log

PATH = os.getenv("USAGE_LOG") or os.path.join(os.path.dirname(activity_log.PATH), "usage.sqlite")
KEEP_DAYS = int(os.getenv("USAGE_KEEP_DAYS", "90"))
MAX_BYTES = 20 * 1024 * 1024
CHECK_EVERY = 200

# What the page reports itself (POST /api/usage/event). Anything else is dropped.
EVENTS = {
    "page:home", "page:data-collection", "page:potential-analysis",
    "ui:try_example", "ui:tour", "ui:page_tour", "ui:language",
    "ui:project_open", "ui:project_save",
}

# How far a visitor got, in the app's order. Each stage is reached by any of
# its events; the API routes are recorded by the request itself (app/main.py).
STAGES = [
    ("Startseite", {"page:home"}),
    ("1 Datenerfassung", {"page:data-collection"}),
    ("Analyse geöffnet", {"page:potential-analysis", "POST /api/analysis/status-quo"}),
    ("2 Pinch-Analyse", {"POST /api/analysis/pinch"}),
    ("3 Wärmepumpe", {"POST /api/analysis/hpi"}),
    ("3 WP-Optimierung", {"POST /api/analysis/hpi-optimization"}),
    ("4 Wirtschaftlichkeit", {"POST /api/analysis/economics"}),
    ("Bericht", {"POST /api/analysis/report"}),
]
API_EVENTS = {e for _, events in STAGES for e in events if e.startswith(("GET ", "POST "))} | {
    "POST /api/io/export-csv", "POST /api/io/import-csv", "POST /api/live/sessions",
    "POST /api/analysis/cop-point", "POST /api/analysis/cop-formula/validate",
    "POST /api/analysis/project",
}

# Crawlers, link previews, uptime checks and scripts are not visitors.
BOTS = re.compile(r"bot|crawl|spider|slurp|preview|monitor|headless|curl|wget|python|httpx|go-http|java/", re.I)


def _networks(text: str) -> list:
    nets = []
    for part in (text or "").replace(";", ",").split(","):
        part = part.strip()
        if part:
            try:
                nets.append(ipaddress.ip_network(part, strict=False))
            except ValueError:
                print(f"usage: OWNER_IPS entry not understood: {part!r}", file=sys.stderr)
    return nets


OWNER = _networks(os.getenv("OWNER_IPS", ""))

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None
_conn_path: Optional[str] = None
# The first row after a start also deletes what is past KEEP_DAYS.
_since_check = CHECK_EVERY
_salt: tuple[str, bytes] = ("", b"")


def _db() -> sqlite3.Connection:
    global _conn, _conn_path
    if _conn is None or _conn_path != PATH:
        conn = sqlite3.connect(PATH, check_same_thread=False, isolation_level=None)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS usage (id INTEGER PRIMARY KEY, time TEXT, day TEXT, "
            "visitor TEXT, owner INTEGER, event TEXT)")
        conn.execute("CREATE INDEX IF NOT EXISTS usage_day ON usage (day)")
        _conn, _conn_path = conn, PATH
    return _conn


def is_owner(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return any(ip.version == net.version and ip in net for net in OWNER)


def visitor_code(address: str, agent: str, day: str) -> str:
    """The same code all day for one address and browser; tomorrow's key is new."""
    global _salt
    if _salt[0] != day:
        _salt = (day, secrets.token_bytes(32))
    raw = f"{counted_address(address)}|{agent}".encode()
    return hmac.new(_salt[1], raw, hashlib.sha256).hexdigest()[:12]


def _trim(db: sqlite3.Connection, today: str) -> None:
    cutoff = (datetime.fromisoformat(today) - timedelta(days=KEEP_DAYS)).date().isoformat()
    db.execute("DELETE FROM usage WHERE day < ?", (cutoff,))
    if os.path.getsize(PATH) > MAX_BYTES:
        db.execute("DELETE FROM usage WHERE id <= (SELECT (MIN(id) + MAX(id)) / 2 FROM usage)")
        db.execute("VACUUM")


def record(address: Optional[str], agent: Optional[str], event: str,
           now: Optional[datetime] = None) -> bool:
    """One row, if the event is a known one and the visitor is not a bot.
    Never raises: counting must not fail a request."""
    global _since_check
    agent = (agent or "")[:300]
    if event not in EVENTS and event not in API_EVENTS:
        return False
    if not address or not agent or BOTS.search(agent):
        return False
    try:
        now = now or datetime.now(timezone.utc)
        day = now.date().isoformat()
        with _lock:
            db = _db()
            db.execute("INSERT INTO usage (time, day, visitor, owner, event) VALUES (?,?,?,?,?)",
                       (now.isoformat(timespec="seconds"), day, visitor_code(address, agent, day),
                        int(is_owner(address)), event))
            _since_check += 1
            if _since_check >= CHECK_EVERY:
                _since_check = 0
                _trim(db, day)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"usage: {type(exc).__name__}", file=sys.stderr)
        return False


def summary(days: int = 30, today: Optional[str] = None) -> dict:
    """Visitors per day, how far each visit got, and what was used, for the
    last `days` days. A visit is one visitor code (one visitor, one day)."""
    today = today or datetime.now(timezone.utc).date().isoformat()
    since = (datetime.fromisoformat(today) - timedelta(days=days - 1)).date().isoformat()
    with _lock:
        rows = _db().execute(
            "SELECT day, visitor, owner, event FROM usage WHERE day >= ? ORDER BY id", (since,)).fetchall()
    per_day: dict = defaultdict(lambda: {"visitors": set(), "owner": set()})
    visits: dict = defaultdict(set)
    used: Counter = Counter()
    used_by: dict = defaultdict(set)
    for day, code, owner, event in rows:
        per_day[day]["owner" if owner else "visitors"].add(code)
        if owner:
            continue
        visits[(day, code)].add(event)
        used[event] += 1
        used_by[event].add((day, code))
    reached = [0] * len(STAGES)
    stopped = [0] * len(STAGES)
    for events in visits.values():
        last = -1
        for i, (_, stage_events) in enumerate(STAGES):
            if events & stage_events:
                reached[i] += 1
                last = i
        if last >= 0:
            stopped[last] += 1
    return {
        "since": since,
        "days": [{"day": d, "visitors": len(v["visitors"]), "owner_visits": len(v["owner"])}
                 for d, v in sorted(per_day.items())],
        "visits": len(visits),
        "funnel": [{"stage": name, "reached": reached[i], "stopped_here": stopped[i]}
                   for i, (name, _) in enumerate(STAGES)],
        "used": [{"event": e, "times": n, "visits": len(used_by[e])} for e, n in used.most_common()],
    }


def _print(days: int) -> None:
    s = summary(days)
    print(f"Seit {s['since']}: {s['visits']} Besuche (ohne dich)\n")
    print("Tag         Besucher  du")
    for d in s["days"]:
        print(f"{d['day']}  {d['visitors']:>8}  {d['owner_visits']:>2}")
    print("\nWie weit Besuche kamen        erreicht  hier aufgehört")
    for f in s["funnel"]:
        print(f"  {f['stage']:<26}  {f['reached']:>8}  {f['stopped_here']:>14}")
    print("\nWas benutzt wurde             mal  in Besuchen")
    for u in s["used"]:
        print(f"  {u['event']:<34}  {u['times']:>5}  {u['visits']:>5}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--json"]
    n = int(args[0]) if args else 30
    if "--json" in sys.argv:
        import json
        print(json.dumps(summary(n), ensure_ascii=False))
    else:
        _print(n)
