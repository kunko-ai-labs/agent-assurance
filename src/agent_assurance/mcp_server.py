"""agent-assurance as an MCP server: the agent asks before it widens itself.

Point Claude Code / Cursor / any MCP client at `agent-assurance-mcp` and the
agent can, from inside a session:

  - `scan`         what does this repo currently let me do, and does it match
                   the promise in agent-assurance.yaml?
  - `would_break`  if I added this MCP server (or this permission rule), would
                   the promise break? — before touching any file.
  - `check`        blast radius of a manifest.

Everything is the same deterministic engine as the CLI; nothing here calls an
LLM. Requires the optional extra: `pip install "agent-assurance[mcp]"`.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile

from . import engine
from .checks.base import Context
from .diff import compute
from .diff import to_markdown as diff_markdown
from .manifest import Manifest, ManifestError
from .reports import to_markdown
from .scan import scan_directory

try:
    from mcp.server.mcpserver import MCPServer
    from mcp.types import ToolAnnotations
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "agent-assurance-mcp needs the MCP SDK: pip install 'agent-assurance[mcp]'"
    ) from exc

# Every tool declares what it does, the same way we ask agents to. All three
# only read the repository: `would_break` simulates the change in a temporary
# copy it creates and removes itself; the repository is never touched.
_READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)

server = MCPServer(
    name="agent-assurance",
    instructions=(
        "Deterministic assurance for AI agents. Before adding an MCP server or a "
        "permission rule to a repository, call would_break to learn whether it "
        "breaks the promise declared in agent-assurance.yaml. Use scan to see the "
        "current reach and verdict."
    ),
)


def _read_json(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def _patch_json(path: str, block: str, name: str, value: dict) -> None:
    data = _read_json(path)
    data.setdefault(block, {})[name] = value
    _write_json(path, data)


def _report(directory: str, manifest: str | None) -> str:
    declared = None
    path = manifest or os.path.join(directory, "agent-assurance.yaml")
    if os.path.isfile(path):
        try:
            declared = Manifest.from_file(path)
        except ManifestError as exc:
            return f"error: {exc}"
    result = scan_directory(directory, declared)
    if not result.found_anything and declared is None:
        return "nothing to scan: no supported agent configuration and no manifest declared"
    ctx = Context(declared=declared, observed=result.observed)
    return to_markdown(engine.run(result.observed, None, ctx, result.sources))


@server.tool(
    annotations=_READ_ONLY,
    description="Observe what this repository's agent configuration grants and verify it against agent-assurance.yaml. Returns the markdown report with verdicts AA-001 (blast radius) and AA-002 (declared vs observed).",
)
def scan(directory: str = ".", manifest: str | None = None) -> str:
    return _report(directory, manifest)


@server.tool(annotations=_READ_ONLY, description="Blast radius of a manifest alone (no scan).")
def check(manifest: str = "agent-assurance.yaml") -> str:
    try:
        m = Manifest.from_file(manifest)
    except (FileNotFoundError, ManifestError) as exc:
        return f"error: {exc}"
    return to_markdown(engine.run(m))


@server.tool(
    annotations=_READ_ONLY,
    description="Would adding this change break the repository's promise? Pass either mcp_server (a JSON object as it would appear under mcpServers, plus its name) or claude_permission (a rule such as 'Bash(*)' with mode allow/ask). Nothing is written to the repository; the change is simulated in a temporary copy.",
)
def would_break(
    directory: str = ".",
    mcp_server_name: str | None = None,
    mcp_server: dict | None = None,
    claude_permission: str | None = None,
    claude_permission_mode: str = "allow",
) -> str:
    tmp = tempfile.mkdtemp(prefix="aa-would-break-")
    try:
        head = os.path.join(tmp, "head")
        os.makedirs(head)
        for rel in (
            "agent-assurance.yaml",
            ".mcp.json",
            ".cursor/mcp.json",
            ".vscode/mcp.json",
            ".gemini/settings.json",
            ".claude/settings.json",
            ".claude/settings.local.json",
        ):
            src = os.path.join(directory, rel)
            if os.path.isfile(src):
                os.makedirs(os.path.dirname(os.path.join(head, rel)), exist_ok=True)
                shutil.copy(src, os.path.join(head, rel))

        if mcp_server_name and mcp_server is not None:
            _patch_json(os.path.join(head, ".mcp.json"), "mcpServers", mcp_server_name, mcp_server)
        if claude_permission:
            path = os.path.join(head, ".claude", "settings.json")
            data = _read_json(path)
            data.setdefault("permissions", {}).setdefault(claude_permission_mode, []).append(
                claude_permission
            )
            _write_json(path, data)

        d = compute(directory, head)
        if d is None:
            return "nothing to compare: no agent configuration or manifest"
        if d.promise_regressed:
            verdict = "WOULD BREAK THE PROMISE"
        elif d.promise_stretched:
            verdict = "would stretch the promise (undeclared reach, review)"
        elif d.regressed:
            verdict = "would widen reach"
        else:
            verdict = "safe within the promise"
        return f"**{verdict}**\n\n" + diff_markdown(d)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
