"""Tests for the Claude Code skill and its plugin scaffolding.

Why this exists: SKILL.md is documentation consumed by a coding agent, and
documentation rots. The CLI surface is the contract the GitHub Action relies
on, so every command the skill teaches is parsed here with the real
argparse parser from cli.py — an invented flag or subcommand turns the
suite red. Likewise the config files the skill lists are checked against
the scanners' actual FILES lists, and the plugin/marketplace manifests are
validated as JSON with the fields a plugin installer needs.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

from agent_assurance import __version__, cli
from agent_assurance.checks import ALL_CHECKS, CHECK_ALIASES
from agent_assurance.scan import KNOWN_UNSUPPORTED, codex_toml, claude_settings, mcp_json, tool_defs

REPO = Path(__file__).resolve().parents[1]
CONTRIB = REPO / "contrib" / "claude-code"
SKILL = CONTRIB / "skills" / "agent-assurance" / "SKILL.md"
PLUGIN_JSON = CONTRIB / ".claude-plugin" / "plugin.json"
HOOKS_JSON = CONTRIB / "hooks" / "hooks.json"
MARKETPLACE_JSON = REPO / ".claude-plugin" / "marketplace.json"
README = CONTRIB / "README.md"
HOOK_SCRIPT = CONTRIB / "aa-post-edit.sh"


def _skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def _bash_blocks(text: str) -> list[str]:
    """Contents of every fenced code block tagged bash (or untagged)."""
    blocks = []
    for m in re.finditer(r"```(?:bash|sh)?\n(.*?)```", text, re.DOTALL):
        blocks.append(m.group(1))
    return blocks


def _documented_commands(text: str) -> list[str]:
    """Every `agent-assurance ...` command line the skill teaches."""
    commands = []
    for block in _bash_blocks(text):
        for line in block.splitlines():
            line = line.strip().lstrip("$ ").strip()
            if line.startswith("agent-assurance "):
                commands.append(line)
    assert commands, "the skill must teach at least one agent-assurance command"
    return commands


def _scanned_files() -> set[str]:
    """Every filename the scanners actually detect, plus the promise files."""
    files = {
        "agent-assurance.yaml",
        "agent-assurance.policy.yaml",
        codex_toml.FILE,
        *claude_settings.FILES,
        *tool_defs.FILES,
        *(rel for rel, _, _ in mcp_json.FILES),
        *KNOWN_UNSUPPORTED,
    }
    return files


def test_skill_exists_and_has_frontmatter():
    assert SKILL.is_file(), f"missing skill file: {SKILL}"
    text = _skill_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "SKILL.md must start with YAML frontmatter"
    front = m.group(1)
    assert re.search(r"^name:\s*\S+", front, re.M), "frontmatter needs a name"
    assert re.search(r"^description:\s*\S+", front, re.M), "frontmatter needs a description"


def test_every_documented_command_parses_with_the_real_cli():
    """No invented subcommands or flags: each command must survive build_parser()."""
    parser = cli.build_parser()
    for cmd in _documented_commands(_skill_text()):
        argv = shlex.split(cmd)[1:]  # drop the program name; parse_args takes argv
        try:
            parser.parse_args(argv)
        except SystemExit as exc:
            if exc.code:  # --version exits 0 through SystemExit; that is fine
                raise AssertionError(
                    f"documented command does not parse with cli.build_parser(): {cmd!r} (exit {exc.code})"
                ) from exc


def test_documented_checks_are_real_checks():
    """--check values and AA-NNN ids in the skill must exist in the registry."""
    text = _skill_text()
    valid = {"all", *CHECK_ALIASES, *CHECK_ALIASES.values(), *ALL_CHECKS}
    for m in re.finditer(r"--check\s+(`?)(\S+?)\1(?=[\s`.,;]|$)", text):
        value = m.group(2).rstrip("`")
        assert value in valid, f"unknown --check value: {value!r}"
    known_ids = set(ALL_CHECKS)
    for m in re.finditer(r"AA-\d{3}", text):
        assert m.group(0) in known_ids, f"unknown check id: {m.group(0)!r}"


def test_documented_config_files_are_actually_scanned():
    """Filenames in the discovery table must be files the scanners detect."""
    text = _skill_text()
    discovery = text.split("## 1.")[1].split("## 2.")[0]
    mentioned = set(re.findall(r"`([\w./-]+\.(?:json|toml|yaml|yml|md))`", discovery))
    assert mentioned, "the discovery section must name config files"
    unknown = mentioned - _scanned_files()
    assert not unknown, f"files the skill lists but no scanner detects: {sorted(unknown)}"


def test_plugin_json_is_valid_and_versioned():
    data = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    assert data["name"] == "agent-assurance"
    assert data["description"], "plugin.json needs a description"
    assert data["version"] == __version__, "plugin version must track the package version"


def test_hooks_json_registers_the_existing_hook_script():
    assert HOOK_SCRIPT.is_file(), "the plugin hook must reuse the existing aa-post-edit.sh"
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    entries = data["hooks"]["PostToolUse"]
    assert entries, "hooks.json must register a PostToolUse hook"
    commands = [h["command"] for e in entries for h in e["hooks"]]
    assert any("aa-post-edit.sh" in c for c in commands), (
        "the plugin hook must point at the existing aa-post-edit.sh, not a duplicate"
    )
    assert any("Edit" in e.get("matcher", "") for e in entries)


def test_marketplace_json_points_at_the_plugin_directory():
    data = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
    plugins = data["plugins"]
    entry = next(p for p in plugins if p["name"] == "agent-assurance")
    source = entry["source"].lstrip("./")
    assert (REPO / source).is_dir(), f"marketplace source must exist: {entry['source']}"
    assert (REPO / source / ".claude-plugin" / "plugin.json").is_file()
    assert entry["version"] == __version__


def test_readme_documents_plugin_and_skill_install():
    text = README.read_text(encoding="utf-8")
    assert "skills/agent-assurance/SKILL.md" in text, "README must document the skill install path"
    assert "marketplace add" in text, "README must document the plugin marketplace install"
    assert "aa-post-edit.sh" in text, "README must keep documenting the hook"
    assert "agent-assurance-mcp" in text, "README must keep documenting the MCP server"
