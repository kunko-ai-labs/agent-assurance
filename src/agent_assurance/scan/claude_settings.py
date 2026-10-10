"""Scanner for Claude Code project permissions:
`.claude/settings.json` and `.claude/settings.local.json`.

Reference: Claude Code settings documentation, "permissions" section
(https://docs.claude.com/en/docs/claude-code/settings), as read on 2026-09-17.
Rules are strings of the form `Tool` or `Tool(specifier)`, listed under
`permissions.allow`, `permissions.ask` and `permissions.deny`. Precedence is
deny > ask > allow. `permissions.defaultMode` can auto-approve classes of
tools ("acceptEdits") or everything ("bypassPermissions").

What a rule means for assurance — and this is the part worth getting right:
Claude Code's built-in tools exist whether or not they are listed. A rule does
not *grant* a capability; it decides whether a **human approves** its use.
So `allow` = the capability runs with no one watching (approval "auto"),
`ask` = a person confirms, `deny` = the capability is removed. Autonomy, not
access class, is what these files change.

Rules are collapsed per capability class: ten `allow: Bash(...)` rules are one
shell grant, not ten capabilities. A scoped rule (`Bash(npm test:*)`) keeps the
class but is marked scoped; a scoped rule whose command is read-only
(`Bash(git status:*)`, `Bash(grep:*)`) is a read, not an execute.

Built-in tools map to classes as follows; anything else is UNKNOWN:
  Bash                              -> execute (shell); read if only read-only commands
  Edit, Write, MultiEdit, NotebookEdit -> write (filesystem)
  Read, Glob, Grep, LS              -> read (filesystem)
  WebFetch, WebSearch               -> read (web)
  Agent, Task                       -> execute (subagents) — delegation
  mcp__<server>__<tool>, mcp__<server> -> the server's class from the catalogue
"""

from __future__ import annotations

import json
import os
import re

from .. import policy
from ..manifest import Tool, ToolAccess
from . import catalog
from .base import Observation, Scanner, Source

FILES = (".claude/settings.json", ".claude/settings.local.json")

_BUILTIN: dict[str, tuple[ToolAccess, str]] = {
    "Bash": (ToolAccess.EXECUTE, "shell"),
    "Edit": (ToolAccess.WRITE, "filesystem"),
    "Write": (ToolAccess.WRITE, "filesystem"),
    "MultiEdit": (ToolAccess.WRITE, "filesystem"),
    "NotebookEdit": (ToolAccess.WRITE, "filesystem"),
    "Read": (ToolAccess.READ, "filesystem"),
    "Glob": (ToolAccess.READ, "filesystem"),
    "Grep": (ToolAccess.READ, "filesystem"),
    "LS": (ToolAccess.READ, "filesystem"),
    "WebFetch": (ToolAccess.READ, "web"),
    "WebSearch": (ToolAccess.READ, "web"),
    "Agent": (ToolAccess.EXECUTE, "subagents"),
    "Task": (ToolAccess.EXECUTE, "subagents"),
    # Claude Code housekeeping tools: they read instructions or session state.
    "Skill": (ToolAccess.READ, "claude-code"),
    "SlashCommand": (ToolAccess.READ, "claude-code"),
    "TodoWrite": (ToolAccess.READ, "claude-code"),
    "TodoRead": (ToolAccess.READ, "claude-code"),
    "BashOutput": (ToolAccess.READ, "shell"),
    "KillShell": (ToolAccess.READ, "shell"),
    "ExitPlanMode": (ToolAccess.READ, "claude-code"),
}
# First word(s) of a scoped Bash rule that only reads. Deliberately short and
# boring; anything not here is treated as execute. Multi-word entries are
# matched longest-prefix-first, so `git remote -v` is safe to add while a bare
# `git remote` stays execute (it can add/remove remotes). `gh api` and
# `git tag` are deliberately absent for the same reason: both can write.
_READ_ONLY_COMMANDS = {
    "ls", "cat", "head", "tail", "less", "grep", "rg", "find", "fd", "wc", "echo",
    "pwd", "which", "type", "env", "printenv", "tree", "stat", "file", "diff",
    "du", "df", "uname",
    "git status", "git diff", "git log", "git show", "git branch", "git blame",
    "git fetch", "git rev-parse", "git describe", "git remote -v",
    "gh pr view", "gh pr list", "gh pr diff", "gh issue view", "gh issue list",
    "gh run list", "gh run view",
    "node --version", "python --version", "npm ls", "pip list", "cargo tree", "go list",
}
_RULE_RE = re.compile(r"^(?P<tool>[A-Za-z_][A-Za-z0-9_]*)(?:\((?P<spec>.*)\))?$")
_MODE_TO_APPROVAL = {"allow": "auto", "ask": "ask"}


def _bash_class(spec: str | None) -> tuple[ToolAccess, bool]:
    """(class, scoped) for a Bash rule specifier."""
    if not spec or spec.strip() in ("*", ":*"):
        return ToolAccess.EXECUTE, False
    cmd = spec.split(":", 1)[0].strip()
    words = cmd.split()
    read_only = _READ_ONLY_COMMANDS | set(policy.current().read_only_commands)
    for n in (3, 2, 1):
        if " ".join(words[:n]) in read_only:
            return ToolAccess.READ, True
    return ToolAccess.EXECUTE, True


def _line_of(text: str, needle: str) -> int:
    for i, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return i
    return 1


def _classify(tool: str) -> tuple[ToolAccess, str] | None:
    if tool in _BUILTIN:
        return _BUILTIN[tool]
    if tool.startswith("mcp__"):
        parts = tool.split("__")  # mcp__<server>__<tool> or mcp__<server>
        server = parts[1] if len(parts) > 1 and parts[1] else tool
        entry = catalog.lookup(server, "")
        if entry is None:
            return (ToolAccess.UNKNOWN, server)
        # Whole-server rule or a tool we cannot name: take the server's widest class.
        widest = max(entry.capabilities, key=lambda c: _RANK.get(c.access, 0)).access
        return (widest, entry.system)
    return None


_RANK = {
    ToolAccess.READ: 0,
    ToolAccess.WRITE: 2,
    ToolAccess.EXECUTE: 2,
    ToolAccess.EXTERNAL_SEND: 2,
    ToolAccess.DELETE: 3,
    ToolAccess.FINANCIAL: 3,
    ToolAccess.UNKNOWN: 1,
}


class ClaudeSettingsScanner(Scanner):
    kind = "claude-code-settings"

    def detect(self, root: str) -> list[str]:
        return [f for f in FILES if os.path.isfile(os.path.join(root, f))]

    def parse(self, root: str, rel_path: str) -> Observation:
        with open(os.path.join(root, rel_path), encoding="utf-8") as fh:
            text = fh.read()
        source = Source(path=rel_path, kind=self.kind, supported=True)
        obs = Observation(source=source)

        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            source.supported = False
            source.note = f"invalid JSON: {exc.msg} (line {exc.lineno})"
            return obs

        perms = raw.get("permissions") if isinstance(raw, dict) else None
        if not isinstance(perms, dict):
            source.note = "no permissions block"
            return obs

        notes: list[str] = []

        # deny wins over everything: collect bare-tool denials first.
        denied_tools: set[str] = set()
        for rule in perms.get("deny") or []:
            m = _RULE_RE.match(str(rule))
            if m and not m.group("spec"):
                denied_tools.add(m.group("tool"))
            if m:
                notes.append(f"deny {rule}")

        # Collapse rules per (class, system, approval, scoped): the report
        # names the rules, the risk model counts the capability once.
        grants: dict[tuple, dict] = {}
        for mode in ("ask", "allow"):
            for rule in perms.get(mode) or []:
                m = _RULE_RE.match(str(rule))
                if not m:
                    continue
                tool, spec = m.group("tool"), m.group("spec")
                if tool in denied_tools:
                    notes.append(f"{mode} {rule} overridden by deny")
                    continue
                line = _line_of(text, str(rule))
                approval = _MODE_TO_APPROVAL[mode]
                if tool == "Bash":
                    access, scoped = _bash_class(spec)
                    system = "shell"
                else:
                    cls = _classify(tool)
                    if cls is None:
                        obs.tools.append(Tool(name=f"claude-code.{rule}", type=ToolAccess.UNKNOWN, system=tool, source=f"{rel_path}:{line}", approval=approval))
                        obs.unknowns.append(str(rule))
                        notes.append(f"{mode} {rule}: unknown tool -> UNKNOWN")
                        continue
                    access, system = cls
                    # A specifier, or a single MCP tool (mcp__srv__tool) rather
                    # than a whole server (mcp__srv), narrows the grant.
                    scoped = bool(spec and spec != "*") or (tool.startswith("mcp__") and tool.count("__") >= 2)
                    if access is ToolAccess.UNKNOWN:
                        obs.unknowns.append(str(rule))
                key = (access, system, approval, scoped)
                g = grants.setdefault(key, {"rules": [], "line": line})
                g["rules"].append(str(rule))
                g["line"] = min(g["line"], line)

        for (access, system, approval, scoped), g in grants.items():
            rules = g["rules"]
            shown = ", ".join(rules[:4]) + (f", +{len(rules) - 4} more" if len(rules) > 4 else "")
            obs.tools.append(
                Tool(
                    name=f"claude-code.{system}[{shown}]",
                    type=access,
                    system=system,
                    source=f"{rel_path}:{g['line']}",
                    approval=approval,
                    scoped=scoped,
                )
            )
            notes.append(f"{'allow' if approval == 'auto' else 'ask'} {len(rules)} rule(s) -> {access.value} {system}{' (scoped)' if scoped else ''}")

        default_mode = perms.get("defaultMode")
        if default_mode == "bypassPermissions":
            where = f"{rel_path}:{_line_of(text, 'bypassPermissions')}"
            obs.tools.append(
                Tool(name="claude-code.defaultMode=bypassPermissions", type=ToolAccess.EXECUTE, system="shell", source=where, approval="auto")
            )
            notes.append("defaultMode=bypassPermissions: every tool runs without approval")
        elif default_mode == "acceptEdits":
            where = f"{rel_path}:{_line_of(text, 'acceptEdits')}"
            obs.tools.append(
                Tool(name="claude-code.defaultMode=acceptEdits", type=ToolAccess.WRITE, system="filesystem", source=where, approval="auto")
            )
            notes.append("defaultMode=acceptEdits: file edits run without approval")

        source.note = "; ".join(notes) if notes else "no rules"
        return obs
