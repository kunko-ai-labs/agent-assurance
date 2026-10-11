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
(`Bash(git status:*)`, `Bash(grep:*)`) is a read, not an execute. Read-only
means every command the rule can let through only reads: `Bash(find:*)` also
lets `find -exec` through, so it is execute; shell operators make any rule
execute; a rule that does not parse is UNKNOWN, never dropped.

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
import shlex
import unicodedata

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
# Read-only Bash rules. Deny by default: a rule is a read only when every
# command it can let through only reads; anything else is execute.
#
# Commands with no option that runs a program, writes or deletes: a read with
# any arguments, so a prefix rule (`Bash(grep:*)`) is a read.
_READ_ONLY_ANY_ARGS = {
    "ls", "cat", "head", "tail", "grep", "wc", "echo", "pwd", "which", "type",
    "printenv", "stat", "diff",
    "git status", "git blame",
    "gh pr view", "gh pr list", "gh issue view", "gh issue list", "gh run list", "gh run view",
}
# Commands that read with some options and run programs or write files with
# others (`find -exec`, `fd -x`, `rg --pre`, `tree -o`, `file -C`,
# `git diff --output`, `git branch -D`, `env <cmd>`). A read only for an exact
# rule (no `*`) whose every option is listed here; a wildcard rule is execute.
_GIT_DIFF_OPTS = {
    "--", "-p", "--patch", "-u", "-s", "--no-patch", "--raw", "--stat", "--numstat", "--shortstat",
    "--dirstat", "--summary", "--name-only", "--name-status", "--cached", "--staged", "--merge-base",
    "--color", "--no-color", "--word-diff", "--color-words", "--color-moved", "-w", "--ignore-all-space",
    "-b", "--ignore-space-change", "--ignore-blank-lines", "--unified", "-M", "--find-renames",
    "--find-copies", "--diff-filter", "--relative", "--no-relative", "--exit-code", "--quiet", "--check",
    "--minimal", "--patience", "--histogram", "-R", "--abbrev", "--full-index", "--binary",
    "--no-ext-diff", "--no-textconv", "--no-prefix", "--src-prefix", "--dst-prefix", "-z", "--no-index",
}
_GIT_LOG_OPTS = _GIT_DIFF_OPTS | {
    "--oneline", "--graph", "--decorate", "--no-decorate", "--all", "--branches", "--tags", "--remotes",
    "-n", "--max-count", "--skip", "--since", "--until", "--after", "--before", "--author", "--committer",
    "--grep", "-i", "--regexp-ignore-case", "--format", "--pretty", "--reverse", "--first-parent",
    "--no-merges", "--merges", "--follow", "-S", "-G", "--date", "--abbrev-commit", "--left-right",
    "--cherry-pick", "--boundary", "--topo-order", "--date-order", "--no-walk", "--full-history",
}
_CHECKED: dict[str, frozenset[str]] = {
    "find": frozenset({
        "-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename", "-regex", "-iregex",
        "-regextype", "-type", "-xtype", "-size", "-empty", "-mtime", "-mmin", "-atime", "-amin",
        "-ctime", "-cmin", "-newer", "-anewer", "-cnewer", "-user", "-group", "-uid", "-gid",
        "-nouser", "-nogroup", "-perm", "-links", "-inum", "-samefile", "-lname", "-ilname",
        "-readable", "-writable", "-executable", "-maxdepth", "-mindepth", "-depth", "-prune",
        "-print", "-print0", "-printf", "-ls", "-quit", "-true", "-false", "-not", "-a", "-and",
        "-o", "-or", "-follow", "-L", "-H", "-P", "-xdev", "-mount", "-noleaf", "-daystart",
    }),
    "fd": frozenset({
        "-H", "--hidden", "-I", "--no-ignore", "--no-ignore-vcs", "-u", "--unrestricted", "-s",
        "--case-sensitive", "-i", "--ignore-case", "-g", "--glob", "--regex", "-F", "--fixed-strings",
        "-a", "--absolute-path", "-L", "--follow", "-p", "--full-path", "-0", "--print0", "-d",
        "--max-depth", "--min-depth", "--exact-depth", "-t", "--type", "-e", "--extension", "-E",
        "--exclude", "-S", "--size", "--changed-within", "--changed-before", "--max-results", "-1",
        "-q", "--quiet", "--prune", "--one-file-system", "-c", "--color",
    }),
    "rg": frozenset({
        "--", "-i", "--ignore-case", "-s", "--case-sensitive", "-S", "--smart-case", "-w", "--word-regexp",
        "-x", "--line-regexp", "-F", "--fixed-strings", "-e", "--regexp", "-n", "--line-number", "-N",
        "--no-line-number", "-l", "--files-with-matches", "--files-without-match", "-c", "--count",
        "--count-matches", "-o", "--only-matching", "-v", "--invert-match", "-g", "--glob", "--iglob",
        "-t", "--type", "-T", "--type-not", "--hidden", "-u", "--unrestricted", "--no-ignore", "-L",
        "--follow", "-A", "-B", "-C", "--context", "--after-context", "--before-context", "-m",
        "--max-count", "-d", "--max-depth", "--files", "--json", "--vimgrep", "--heading",
        "--no-heading", "--color", "-H", "--with-filename", "-I", "--no-filename", "-0", "--null",
        "-U", "--multiline", "-P", "--pcre2", "--sort", "--sortr", "--stats", "--trim", "-q",
        "--quiet", "--column", "-M", "--max-columns", "-a", "--text", "--type-list", "--no-messages",
    }),
    "tree": frozenset({
        "-a", "-d", "-l", "-f", "-i", "-q", "-N", "-L", "-P", "-I", "--gitignore", "--noreport",
        "-s", "-h", "--du", "-p", "-u", "-g", "-D", "-F", "-C", "-n", "-J", "-X", "--dirsfirst",
        "--prune", "--matchdirs", "--filelimit", "-t", "-r", "-c", "-v", "-U", "--sort", "--charset",
    }),
    "file": frozenset({
        "-b", "--brief", "-i", "--mime", "--mime-type", "--mime-encoding", "--extension", "-L",
        "--dereference", "-h", "--no-dereference", "-k", "--keep-going", "-N", "--no-pad", "-0",
        "-E", "-r", "--raw", "-s", "--special-files",
    }),
    "env": frozenset(),  # `env` alone prints the environment; `env <cmd>` runs <cmd>
    "git diff": frozenset(_GIT_DIFF_OPTS),
    "git log": frozenset(_GIT_LOG_OPTS),
    "git show": frozenset(_GIT_LOG_OPTS),
    "git branch": frozenset({
        "-a", "--all", "-r", "--remotes", "-v", "-vv", "--verbose", "--show-current", "--color",
        "--no-color", "--column", "--no-column", "--format", "--sort", "--merged", "--no-merged",
        "--contains", "--no-contains", "--points-at", "--list", "-i", "--ignore-case",
    }),
}
# Commands whose positional arguments are not just paths or revisions.
_NO_POSITIONAL = {"env"}
# `git branch <name>` creates a branch; with --list, positionals are patterns.
# (`-l` is not accepted: older git read it as --create-reflog.)
_POSITIONAL_ONLY_WITH = {"git branch": {"--list"}}
# Per command: numeric option values and attached counts that only read
# (`-mtime -7`, `-size -10k`, `rg -A3`, `git log -n5`, `git diff -U3`).
# Never a blanket pattern: `git branch -m5` renames a branch.
_NUMERIC_TOKEN = {
    "find": re.compile(r"^-\d+[a-zA-Z]?$"),
    "rg": re.compile(r"^-[ABCmM]\d+$"),
    "git diff": re.compile(r"^-(?:U\d+|M\d+%?)$"),
    "git log": re.compile(r"^-(?:U\d+|M\d+%?|n?\d+)$"),
    "git show": re.compile(r"^-(?:U\d+|M\d+%?|n?\d+)$"),
}
# For commands with option-dependent behaviour, brace expansion and globs can
# turn an argument into an option (`{-delete,-print}`, `?delete` matching a
# file named `-delete`); `*` is already a rule wildcard.
_EXPANSION = re.compile(r"[?\[\]{}]")
# Never a read, whatever an organisation policy says: they run another
# program, interpret a script, open a pager or editor, or write their output.
# Refused by prefix, so variants are refused too (`python3-dbg`, `nodejs`,
# `fdfind`, `bundle`, `gtar3`).
_REFUSED_FAMILIES = (
    # shells
    "sh", "bash", "rbash", "zsh", "dash", "ksh", "mksh", "fish", "csh", "tcsh", "ash", "busybox",
    "pwsh", "powershell", "xonsh", "elvish",
    # interpreters
    "python", "pypy", "node", "deno", "bun", "ruby", "irb", "perl", "php", "lua", "tclsh", "wish",
    "osascript", "rscript", "julia", "java", "jshell", "groovy",
    # wrappers that run another command
    "env", "xargs", "nohup", "sudo", "doas", "time", "timeout", "nice", "stdbuf", "watch", "setsid",
    "chroot", "flock", "ionice", "taskset", "unbuffer", "parallel", "strace", "ltrace", "gdb",
    "systemd-run", "pkexec", "runuser", "nsenter", "unshare", "script",
    # search tools that run a program per result; package runners
    "find", "fd", "pip",
)
_REFUSED_NAMES = (
    "exec", "eval", "command", "builtin", "source",
    "less", "more", "most", "man", "vim", "nvim", "view", "emacs", "nano",
    "awk", "gawk", "mawk", "nawk", "sed", "gsed", "tee", "sort", "tar", "gtar", "bsdtar",
    "open", "xdg-open", "npx", "bunx", "pnpx", "ssh", "curl", "wget",
)
# Names too short to refuse by prefix (`ex` would refuse `expr`): refused with
# any version, debug or variant suffix.
_REFUSED_SHORT = re.compile(r"^(?:ex|ed|su|nu|uv|dd|vi)(?:[-_.]?\d[\w.-]*|-?dbg|[wx])?$")
# The only command names that can be a read: plain ASCII, lower case, no
# path, no extension, no version dots, no glob.
_PLAIN_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")
_POLICY_FORBIDDEN = re.compile(r"[*?\[\]{}/\\;&|<>`$()\n\r]")
_BUILTIN_KEYS = [k.split() for k in (*_CHECKED, *_READ_ONLY_ANY_ARGS)]
# Shell operators, redirections and substitutions: the rule runs more than the command.
_SHELL_META = re.compile(r"[;&|<>`$()\n\r]")
# Tool names include MCP server names, which may carry `-` and `.`.
_RULE_RE = re.compile(r"^(?P<tool>[A-Za-z_][A-Za-z0-9_.-]*)(?:\((?P<spec>.*)\))?$", re.DOTALL)
_MODE_TO_APPROVAL = {"allow": "auto", "ask": "ask"}


def _match(words: list[str], table) -> int:
    """How many leading words name a command in `table` (0 if none)."""
    for n in (3, 2, 1):
        if len(words) >= n and " ".join(words[:n]) in table and all(" " not in w for w in words[:n]):
            return n
    return 0


def _command_name(word: str) -> str | None:
    """The program a command word names: NFKC, case-folded, basename, no
    `.exe`. None for anything that is not ASCII after that (`ſh` resolves to
    sh on a case-insensitive file system)."""
    name = unicodedata.normalize("NFKC", word).casefold()
    if not name.isascii():
        return None
    name = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return name.removesuffix(".exe")


def _refused(name: str) -> bool:
    return name.startswith(_REFUSED_FAMILIES) or name.startswith(_REFUSED_NAMES) or bool(_REFUSED_SHORT.match(name))


def _review_policy(pol: policy.Policy) -> tuple[set[str], list[tuple[str, str]]]:
    """Split `read_only_commands` into accepted entries and ignored ones, with
    the reason. Deny by default: an entry counts only if its command is a
    plain ASCII name outside the refused families and it does not touch a
    built-in command."""
    keep: set[str] = set()
    ignored: list[tuple[str, str]] = []
    for entry in pol.read_only_commands:
        words = entry.split()
        if not words or not entry.isascii() or _POLICY_FORBIDDEN.search(entry):
            ignored.append((entry, "not a plain command: no paths, globs, shell syntax or non-ASCII"))
        elif not _PLAIN_NAME.match(words[0]):
            ignored.append((entry, "command name must match ^[a-z][a-z0-9_-]*$"))
        elif _refused(words[0]):
            ignored.append((entry, "runs other programs, interprets scripts, pages, edits or writes"))
        elif _match(words, _CHECKED) or any(len(k) > len(words) and k[: len(words)] == words for k in _BUILTIN_KEYS):
            ignored.append((entry, "cannot widen a built-in command"))
        else:
            keep.add(" ".join(words))
    return keep, ignored


def ignored_policy_entries(pol: policy.Policy | None = None) -> list[tuple[str, str]]:
    """(entry, reason) for every `read_only_commands` entry that is ignored."""
    return _review_policy(pol or policy.current())[1]


def _options_read_only(key: str, args: list[str]) -> bool:
    allowed = _CHECKED[key]
    positional = [a for a in args if not a.startswith("-") or a == "-"]
    if positional and key in _NO_POSITIONAL:
        return False
    if positional and key in _POSITIONAL_ONLY_WITH and not _POSITIONAL_ONLY_WITH[key] & set(args):
        return False
    for a in args:
        if not a.startswith("-") or a == "-":
            continue
        numeric = _NUMERIC_TOKEN.get(key)
        if a.split("=", 1)[0] in allowed or (numeric is not None and numeric.match(a)):
            continue
        return False
    return True


def _bash_class(spec: str | None) -> tuple[ToolAccess, bool]:
    """(class, scoped) for a Bash rule specifier. Deny by default."""
    if not spec or spec.strip() in ("*", ":*"):
        return ToolAccess.EXECUTE, False
    cmd = spec.strip()
    wildcard = cmd.endswith(":*")  # legacy prefix syntax: `Bash(git status:*)`
    if wildcard:
        cmd = cmd[:-2]
    wildcard = wildcard or "*" in cmd  # `*` anywhere matches any text, options included
    if _SHELL_META.search(cmd):
        return ToolAccess.EXECUTE, True
    try:
        words = shlex.split(cmd)
    except ValueError:
        return ToolAccess.EXECUTE, True
    if not words:
        return ToolAccess.EXECUTE, True
    # Only a plain command name can be a read. `git.exe`, `/usr/bin/env`,
    # `python3.12`, `LS` and `ſh` are execute, whatever they resolve to.
    name = _command_name(words[0])
    if name is None or not _PLAIN_NAME.match(words[0]):
        return ToolAccess.EXECUTE, True
    # Built-in knowledge first, so a policy entry cannot widen a risky command.
    n = _match(words, _CHECKED)
    if n:
        key = " ".join(words[:n])
        ok = not wildcard and not _EXPANSION.search(cmd) and _options_read_only(key, words[n:])
        return (ToolAccess.READ if ok else ToolAccess.EXECUTE), True
    if _refused(name):
        return ToolAccess.EXECUTE, True
    if name == "git" and len(words) > 1 and words[1].startswith("-"):
        return ToolAccess.EXECUTE, True  # global options: -c core.pager=…, --exec-path, -C
    accepted, _ = _review_policy(policy.current())
    if _match(words, _READ_ONLY_ANY_ARGS | accepted):
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
                    # Never drop a grant we cannot parse: it is UNKNOWN, not absent.
                    line = _line_of(text, str(rule).splitlines()[0] if str(rule) else str(rule))
                    obs.tools.append(Tool(name=f"claude-code.{rule}", type=ToolAccess.UNKNOWN, system="claude-code", source=f"{rel_path}:{line}", approval=_MODE_TO_APPROVAL[mode]))
                    obs.unknowns.append(str(rule))
                    notes.append(f"{mode} {rule}: unparsed rule -> UNKNOWN")
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

        for entry, reason in ignored_policy_entries():
            notes.append(f"policy read_only_commands entry {entry!r} ignored: {reason}")
        source.note = "; ".join(notes) if notes else "no rules"
        return obs
