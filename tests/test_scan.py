"""Scan + AA-002 (declared vs observed): the promise is verified, not trusted.

Fixtures under examples/repos/ are the demo and the contract:
  mcp-promise-kept    declared read-only, config grants read-only   -> PASS
  mcp-promise-broken  same declaration, config adds write + send    -> FAIL
  mcp-unknown-server  no declaration, one server nobody recognises  -> REVIEW
"""

from __future__ import annotations

import json
import pathlib

import pytest

from agent_assurance import cli
from agent_assurance.checks.base import Status
from agent_assurance.manifest import Manifest, ToolAccess
from agent_assurance.scan import catalog, scan_directory

REPOS = pathlib.Path(__file__).resolve().parents[1] / "examples" / "repos"
KEPT = str(REPOS / "mcp-promise-kept")
BROKEN = str(REPOS / "mcp-promise-broken")
UNKNOWN = str(REPOS / "mcp-unknown-server")


# --- scanner ----------------------------------------------------------------


def test_mcp_json_is_observed_with_provenance():
    result = scan_directory(KEPT)
    assert result.found_anything
    assert [s.path for s in result.sources if s.supported] == [".mcp.json"]
    names = {t.name: t for t in result.observed.tools}
    assert names["postgres.query"].type is ToolAccess.READ
    assert names["postgres.query"].source == ".mcp.json:3"
    assert names["fetch.fetch"].source == ".mcp.json:7"


def test_unknown_server_is_unknown_not_guessed():
    result = scan_directory(UNKNOWN)
    assert result.unknowns == ["acme-erp"]
    unknown = [t for t in result.observed.tools if t.type is ToolAccess.UNKNOWN]
    assert unknown and unknown[0].system == "acme-erp"
    # Remote transport is egress; a Bearer header is a credential. Value never read.
    types = {t.name: t.type for t in result.observed.tools}
    assert types["acme-erp.remote"] is ToolAccess.EXTERNAL_SEND
    assert any(d.type.value == "credential" for d in result.observed.data)


def test_unsupported_files_are_listed_not_silent():
    result = scan_directory(UNKNOWN)
    unsupported = [s for s in result.sources if not s.supported]
    assert [s.path for s in unsupported] == ["AGENTS.md"]


def test_declared_metadata_survives_merge():
    declared = Manifest.from_file(str(pathlib.Path(KEPT) / "agent-assurance.yaml"))
    result = scan_directory(KEPT, declared)
    assert result.observed.agent.name == "analytics-helper"
    assert result.observed.autonomy == 2
    # ...but capabilities come from the scan, not the declaration.
    assert all(t.source for t in result.observed.tools)


@pytest.mark.parametrize(
    ("name", "cmd", "system"),
    [
        ("anything", "npx -y @modelcontextprotocol/server-github", "github"),
        ("gh", "node ./local.js", "github"),
        ("my-slack-bot", "", "slack"),
        ("brave-search", "", "web"),
        ("totally-new", "node server.js", None),
        ("digital-ocean", "", None),  # token match: "git" must not match "digital"
    ],
)
def test_catalog_lookup(name, cmd, system):
    entry = catalog.lookup(name, cmd)
    assert (entry.system if entry else None) == system


# --- AA-002 through the CLI --------------------------------------------------


def _scan_json(directory: str, tmp_path) -> tuple[int, dict]:
    out = tmp_path / "r.json"
    code = cli.main(["scan", directory, "--format", "json", "-o", str(out)])
    return code, json.loads(out.read_text(encoding="utf-8"))


def test_promise_kept_passes(tmp_path):
    code, r = _scan_json(KEPT, tmp_path)
    assert code == cli.EXIT_OK
    aa2 = next(c for c in r["checks"] if c["id"] == "AA-002")
    assert aa2["status"] == "PASS"
    assert aa2["data"]["broken"] == []


def test_promise_broken_fails_and_points_at_the_line(tmp_path):
    code, r = _scan_json(BROKEN, tmp_path)
    assert code == cli.EXIT_GATE
    assert r["verdict"] == "FAIL"
    aa2 = next(c for c in r["checks"] if c["id"] == "AA-002")
    assert aa2["status"] == "FAIL"
    assert any("github.write" in m and "write" in m for m in aa2["data"]["broken"])
    assert any("slack.post_message" in m for m in aa2["data"]["broken"])
    assert {loc["path"] for loc in aa2["locations"]} == {".mcp.json"}
    assert {loc["line"] for loc in aa2["locations"]} == {11, 16}


def test_unknown_without_declaration_is_review_not_pass(tmp_path):
    code, r = _scan_json(UNKNOWN, tmp_path)
    assert code == cli.EXIT_OK  # REVIEW does not gate by default...
    assert r["verdict"] == "REVIEW"
    assert cli.main(["scan", UNKNOWN, "--fail-on", "review", "-o", str(tmp_path / "x.md")]) == cli.EXIT_GATE
    # ...and AA-002 is simply not run when there is nothing declared.
    assert [c["id"] for c in r["checks"]] == ["AA-001"]


def test_unknown_with_declaration_blocks_promise_kept(tmp_path):
    """A promise cannot be called kept over something we do not understand."""
    (tmp_path / ".mcp.json").write_text(
        '{"mcpServers": {"mystery": {"command": "node", "args": ["server.js"]}}}',
        encoding="utf-8",
    )
    declared = pathlib.Path(KEPT) / "agent-assurance.yaml"
    out = tmp_path / "r.json"
    cli.main(["scan", str(tmp_path), "-m", str(declared), "--format", "json", "-o", str(out)])
    r = json.loads(out.read_text(encoding="utf-8"))
    aa2 = next(c for c in r["checks"] if c["id"] == "AA-002")
    assert aa2["status"] == "REVIEW"
    assert aa2["summary"].startswith("Promise not verifiable")
    assert aa2["data"]["unknown"] and aa2["data"]["broken"] == []


def test_unknown_plus_undeclared_secret_is_a_broken_promise(tmp_path):
    """The fixture's unknown server also holds a token and talks to a remote
    host: those are undeclared credential + egress, which break the promise."""
    declared = pathlib.Path(KEPT) / "agent-assurance.yaml"
    out = tmp_path / "r.json"
    code = cli.main(["scan", UNKNOWN, "-m", str(declared), "--format", "json", "-o", str(out)])
    r = json.loads(out.read_text(encoding="utf-8"))
    aa2 = next(c for c in r["checks"] if c["id"] == "AA-002")
    assert code == cli.EXIT_GATE and aa2["status"] == "FAIL"
    assert aa2["data"]["unknown"] and aa2["data"]["broken"]


def test_nothing_to_scan_is_a_usage_error(tmp_path, capsys):
    (tmp_path / "AGENTS.md").write_text("# instructions\n", encoding="utf-8")
    assert cli.main(["scan", str(tmp_path)]) == cli.EXIT_USAGE
    err = capsys.readouterr().err
    assert "nothing to scan" in err and "AGENTS.md" in err


@pytest.mark.parametrize(
    ("rel", "payload"),
    [
        (".cursor/mcp.json", '{"mcpServers": {"github": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"]}}}'),
        (".gemini/settings.json", '{"theme": "x", "mcpServers": {"github": {"command": "github-mcp-server", "args": ["stdio"]}}}'),
        (".vscode/mcp.json", '{"servers": {"github": {"type": "http", "url": "https://api.githubcopilot.com/mcp"}}}'),
    ],
)
def test_other_hosts_share_the_mcp_scanner(tmp_path, rel, payload):
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(payload, encoding="utf-8")
    result = scan_directory(str(tmp_path))
    assert result.found_anything and result.sources[0].path == rel
    assert any(t.system == "github" and t.type is ToolAccess.WRITE for t in result.observed.tools)


def test_scan_sarif_anchors_each_finding(tmp_path):
    out = tmp_path / "aa.sarif"
    cli.main(["scan", BROKEN, "--format", "sarif", "-o", str(out)])
    sarif = json.loads(out.read_text(encoding="utf-8"))
    aa2 = next(r for r in sarif["runs"][0]["results"] if r["ruleId"] == "AA-002")
    assert aa2["kind"] == "fail" and aa2["level"] == "error"
    locs = [(loc["physicalLocation"]["artifactLocation"]["uri"], loc["physicalLocation"]["region"]["startLine"]) for loc in aa2["locations"]]
    assert locs == [(".mcp.json", 11), (".mcp.json", 16)]


def test_plain_check_still_runs_only_blast_radius():
    """`check` on one manifest must not change behaviour because AA-002 exists."""
    from agent_assurance import engine

    m = Manifest.from_file(str(pathlib.Path(KEPT) / "agent-assurance.yaml"))
    report = engine.run(m)
    assert [r.check_id for r in report.results] == ["AA-001"]
    assert report.verdict is Status.PASS


# --- Claude Code permissions -------------------------------------------------

CC_KEPT = str(REPOS / "claude-code-approval-kept")
CC_BROKEN = str(REPOS / "claude-code-approval-broken")


def _grants(result):
    """(class, system, approval, scoped) -> tool, for Claude Code observations."""
    return {(t.type, t.system, t.approval, t.scoped): t for t in result.observed.tools}


def test_claude_settings_rules_collapse_into_grants():
    result = scan_directory(CC_KEPT)
    g = _grants(result)
    read = g[(ToolAccess.READ, "filesystem", "auto", False)]
    assert "Read" in read.name and "Glob" in read.name
    write = g[(ToolAccess.WRITE, "filesystem", "ask", False)]
    assert write.source == ".claude/settings.json:9"
    npm = g[(ToolAccess.EXECUTE, "shell", "ask", True)]
    assert "Bash(npm test)" in npm.name
    # deny removes the capability entirely
    assert not any(t.system == "web" for t in result.observed.tools)


def test_scoped_read_only_bash_is_read_not_execute(tmp_path):
    """`allow: Bash(git status:*)` is not 'the agent runs shell unattended'."""
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "settings.json").write_text(
        '{"permissions": {"allow": ["Bash(git status:*)", "Bash(grep:*)", "Bash(ls:*)", "Bash(npm test:*)", "Bash(*)"]}}',
        encoding="utf-8",
    )
    g = _grants(scan_directory(str(tmp_path)))
    assert (ToolAccess.READ, "shell", "auto", True) in g  # git status, grep, ls
    assert (ToolAccess.EXECUTE, "shell", "auto", True) in g  # npm test
    assert (ToolAccess.EXECUTE, "shell", "auto", False) in g  # Bash(*)
    assert len(g) == 3


@pytest.mark.parametrize(
    "rule",
    [
        "Bash(git fetch:*)",
        "Bash(git remote -v:*)",
        "Bash(git rev-parse:*)",
        "Bash(git describe:*)",
        "Bash(gh pr diff:*)",
        "Bash(ls -la:*)",
        "Bash(du:*)",
        "Bash(df:*)",
        "Bash(uname:*)",
        "Bash(node --version:*)",
        "Bash(python --version:*)",
        "Bash(npm ls:*)",
        "Bash(pip list:*)",
        "Bash(cargo tree:*)",
        "Bash(go list:*)",
    ],
)
def test_extended_read_only_bash_is_read(tmp_path, rule):
    """US-001-002: each newly allow-listed command is a scoped read."""
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "settings.json").write_text(
        json.dumps({"permissions": {"allow": [rule]}}), encoding="utf-8"
    )
    g = _grants(scan_directory(str(tmp_path)))
    assert (ToolAccess.READ, "shell", "auto", True) in g, g


@pytest.mark.parametrize("rule", ["Bash(gh api:*)", "Bash(git tag:*)", "Bash(git remote:*)"])
def test_write_capable_bash_stays_execute(tmp_path, rule):
    """US-001-002: commands that can mutate stay execute, never read."""
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "settings.json").write_text(
        json.dumps({"permissions": {"allow": [rule]}}), encoding="utf-8"
    )
    g = _grants(scan_directory(str(tmp_path)))
    assert (ToolAccess.EXECUTE, "shell", "auto", True) in g, g
    assert not any(k[0] is ToolAccess.READ for k in g), g


def test_claude_settings_deny_overrides_allow(tmp_path):
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "settings.json").write_text(
        '{"permissions": {"allow": ["Bash(*)", "Read"], "deny": ["Bash"]}}', encoding="utf-8"
    )
    result = scan_directory(str(tmp_path))
    assert [(t.type, t.system) for t in result.observed.tools] == [(ToolAccess.READ, "filesystem")]
    assert "overridden by deny" in result.sources[0].note


def test_claude_settings_bypass_permissions_is_auto_execute(tmp_path):
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "settings.json").write_text(
        '{"permissions": {"defaultMode": "bypassPermissions"}}', encoding="utf-8"
    )
    result = scan_directory(str(tmp_path))
    t = result.observed.tools[0]
    assert t.type is ToolAccess.EXECUTE and t.approval == "auto"


def test_claude_settings_mcp_rule_uses_catalogue_or_unknown(tmp_path):
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "settings.json").write_text(
        '{"permissions": {"allow": ["mcp__github__create_issue", "mcp__acme"]}}', encoding="utf-8"
    )
    result = scan_directory(str(tmp_path))
    g = _grants(result)
    assert (ToolAccess.WRITE, "github", "auto", True) in g
    assert (ToolAccess.UNKNOWN, "acme", "auto", False) in g
    assert result.unknowns == ["mcp__acme"]


def test_approval_promise_kept(tmp_path):
    code, r = _scan_json(CC_KEPT, tmp_path)
    assert code == cli.EXIT_OK and r["verdict"] == "PASS"
    aa2 = next(c for c in r["checks"] if c["id"] == "AA-002")
    assert aa2["status"] == "PASS"


def test_auto_approval_breaks_an_l2_promise(tmp_path):
    """Declared autonomy L2 = a human approves. `allow: Bash(*)` removes them."""
    code, r = _scan_json(CC_BROKEN, tmp_path)
    assert code == cli.EXIT_GATE and r["verdict"] == "FAIL"
    aa2 = next(c for c in r["checks"] if c["id"] == "AA-002")
    assert any("Bash(*)" in m and "without human approval" in m for m in aa2["data"]["broken"])
    aa1 = next(c for c in r["checks"] if c["id"] == "AA-001")
    assert any("Bash(*)" in name for name in aa1["data"]["auto_approved"])
    # No redundant REVIEW lines for systems already reported as broken.
    assert aa2["data"]["review"] == []


def test_scoped_auto_approval_is_review_not_broken(tmp_path):
    """Declared L2 + `allow: Bash(npm test:*)`: a person chose that scope."""
    import shutil

    shutil.copytree(CC_KEPT, tmp_path / "repo")
    (tmp_path / "repo" / ".claude" / "settings.json").write_text(
        '{"permissions": {"allow": ["Read", "Bash(npm test:*)"]}}', encoding="utf-8"
    )
    _, r = _scan_json(str(tmp_path / "repo"), tmp_path)
    aa2 = next(c for c in r["checks"] if c["id"] == "AA-002")
    assert aa2["status"] == "REVIEW"
    assert aa2["data"]["broken"] == [] and any("scoped" in m for m in aa2["data"]["review"])


def test_auto_approval_is_fine_when_autonomy_is_declared(tmp_path):
    """The same config with a declared L3 keeps the promise on approval."""
    import shutil

    shutil.copytree(CC_BROKEN, tmp_path / "repo")
    manifest = tmp_path / "repo" / "agent-assurance.yaml"
    text = manifest.read_text(encoding="utf-8").replace("autonomy: 2", "autonomy: 3")
    manifest.write_text(text, encoding="utf-8")
    _, r = _scan_json(str(tmp_path / "repo"), tmp_path)
    aa2 = next(c for c in r["checks"] if c["id"] == "AA-002")
    assert not any("without human approval" in m for m in aa2["data"]["broken"])


def test_same_server_in_several_hosts_counts_once(tmp_path):
    payload = '{"mcpServers": {"github": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"]}}}'
    (tmp_path / ".mcp.json").write_text(payload, encoding="utf-8")
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor" / "mcp.json").write_text(payload, encoding="utf-8")
    result = scan_directory(str(tmp_path))
    assert len([s for s in result.sources if s.supported]) == 2
    assert len([t for t in result.observed.tools if t.system == "github"]) == 3  # read, write, push — once
