"""The page "What the AI assistant gets": filled at build time from the MCP
server's own code, so it always shows exactly what an assistant receives.

ai_briefing.md holds the words around it and a marker per part. On
source-read, each marker is replaced with Markdown built from
mcp_server/heattransplan_mcp/texts.py (the instructions, ways of working,
rules and guided-study questions) and server.py (every tool with its
parameters and description, by section). The code is read, not imported: the
docs build needs neither the MCP SDK nor the backend.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MCP = ROOT / "mcp_server" / "heattransplan_mcp"
PAGE = "ai_briefing"


def _constants(path: Path) -> dict:
    """Module-level NAME = <literal> assignments of a Python file."""
    out = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


def _text_block(text: str) -> str:
    return "```text\n" + text.rstrip() + "\n```"


def _signature(fn: ast.AsyncFunctionDef | ast.FunctionDef) -> str:
    args = fn.args
    plain = args.posonlyargs + args.args
    defaults = [None] * (len(plain) - len(args.defaults)) + list(args.defaults)
    parts = []
    for arg, default in zip(plain, defaults):
        parts.append(arg.arg if default is None else f"{arg.arg}={ast.unparse(default)}")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        parts.append(arg.arg if default is None else f"{arg.arg}={ast.unparse(default)}")
    return f"{fn.name}({', '.join(parts)})"


def _decorated(fn, name: str) -> bool:
    for d in fn.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        if ast.unparse(target) == name:
            return True
    return False


def _tools() -> str:
    source = (MCP / "server.py").read_text(encoding="utf-8")
    sections = [(i + 1, m.group(1).strip())
                for i, line in enumerate(source.splitlines())
                if (m := re.match(r"# ── (.+?) ─", line))]
    funcs = [n for n in ast.parse(source).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    tools = [f for f in funcs if _decorated(f, "tool")]
    prompts = [f for f in funcs if _decorated(f, "mcp.prompt")]

    out, current = [], None
    for fn in tools:
        section = next((name for line, name in reversed(sections) if line < fn.lineno), "General")
        if section != current:
            out.append(f"\n### {section}\n")
            current = section
        doc = " ".join((ast.get_docstring(fn) or "").split())
        out.append(f"`{_signature(fn)}`\n: {doc}\n")
    head = f"{len(tools)} tools. Each description below is the text the assistant reads.\n"
    if prompts:
        out.append("\n### Prompts\n\nReady-made requests a client can offer the user.\n")
        for fn in prompts:
            out.append(f"`{fn.name}`\n: {' '.join((ast.get_docstring(fn) or '').split())}\n")
    return head + "\n".join(out)


def _parts() -> dict:
    t = _constants(MCP / "texts.py")
    topics = "\n".join(
        f"- `{name}`: [{Path(page).stem.replace('_', ' ')}]({page})" for name, page in t["TOPICS"].items()
    )
    guide = "\n\n".join(f"### `guide(\"{step}\")`\n\n{_text_block(text)}" for step, text in t["GUIDE"].items())
    return {
        "INSTRUCTIONS": _text_block(t["INSTRUCTIONS"]),
        "MODES": "\n".join(f"- {text}" for text in t["MODES"].values()),
        "RULES": "\n".join(f"- {text}" for text in t["RULES"]),
        "TOPICS": topics,
        "GUIDE": guide,
        "TOOLS": _tools(),
    }


def _fill(app, docname, source):
    if docname != PAGE:
        return
    parts = _parts()
    source[0] = re.sub(r"<!-- briefing:(\w+) -->", lambda m: parts[m.group(1)], source[0])


def setup(app):
    app.connect("source-read", _fill)
    return {"parallel_read_safe": True}
