#!/usr/bin/env python3
"""A small usage report from the live app (app/services/usage.py).

Copies the anonymous usage records out of the running backend into
data/usage/ (gitignored, like the report) and writes
data/usage/report_<date>.md: visitors per day, how far visits got in the
analysis and where they stopped, and what was used. Your own visits
(OWNER_IPS) are counted apart and left out of the rest.

    python3 scripts/usage_report.py [days=30] [--project heattransplan]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "usage"


def compose(project: str, *args: str) -> str:
    return subprocess.run(["docker", "compose", "-p", project, *args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout


def bar(n: int, top: int, width: int = 20) -> str:
    return "█" * round(width * n / top) if top else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("days", nargs="?", type=int, default=30)
    ap.add_argument("--project", default="heattransplan")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    compose(a.project, "cp", "backend:/app/logs/usage.sqlite", str(OUT / f"usage_{today}.sqlite"))
    s = json.loads(compose(a.project, "exec", "-T", "backend", "python", "-m", "app.services.usage",
                           str(a.days), "--json"))

    days = s["days"]
    others = sum(d["visitors"] for d in days)
    mine = sum(d["owner_visits"] for d in days)
    lines = [
        f"# Nutzung HeatTransPlan, {s['since']} bis {today}",
        "",
        f"**{s['visits']} Besuche** von anderen (ein Besuch = ein Besucher an einem Tag), "
        f"dazu {mine} von dir. Besucher sind anonym und nur innerhalb eines Tages wiedererkennbar.",
        "",
        "## Besuche pro Tag",
        "",
        "| Tag | andere | du | |",
        "|---|---:|---:|---|",
    ]
    top = max((d["visitors"] for d in days), default=0)
    lines += [f"| {d['day']} | {d['visitors']} | {d['owner_visits']} | {bar(d['visitors'], top)} |"
              for d in days]
    if not days:
        lines.append("| – | 0 | 0 | |")

    lines += ["", "## Wie weit die Besuche kamen", "",
              "*erreicht*: so viele Besuche kamen bis hier; *aufgehört*: für so viele war das der letzte Schritt.",
              "", "| Schritt | erreicht | aufgehört | |", "|---|---:|---:|---|"]
    first = max((f["reached"] for f in s["funnel"]), default=0)
    lines += [f"| {f['stage']} | {f['reached']} | {f['stopped_here']} | {bar(f['reached'], first)} |"
              for f in s["funnel"]]

    lines += ["", "## Was benutzt wurde", "", "| Funktion | mal | in Besuchen |", "|---|---:|---:|"]
    lines += [f"| `{u['event']}` | {u['times']} | {u['visits']} |" for u in s["used"]]
    if not s["used"]:
        lines.append("| – | 0 | 0 |")
    lines.append("")

    report = OUT / f"report_{today}.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"{report}  ({others} Besuche andere, {mine} du)")


if __name__ == "__main__":
    main()
