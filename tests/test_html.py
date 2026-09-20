"""Capability card: single file, no scripts, same facts as the JSON report."""

from __future__ import annotations

import json
import pathlib
import re

from agent_assurance import cli

REPOS = pathlib.Path(__file__).resolve().parents[1] / "examples" / "repos"
KEPT = str(REPOS / "mcp-promise-kept")
BROKEN = str(REPOS / "mcp-promise-broken")


def test_card_is_self_contained_and_matches_json(tmp_path):
    html, js = tmp_path / "c.html", tmp_path / "c.json"
    cli.main(["scan", BROKEN, "--format", "html", "-o", str(html)])
    cli.main(["scan", BROKEN, "--format", "json", "-o", str(js)])
    text = html.read_text(encoding="utf-8")
    data = json.loads(js.read_text(encoding="utf-8"))
    assert text.startswith("<!doctype html>") and "<script" not in text and "http" not in text.split("<footer>")[0].replace("https://in-toto", "")
    assert ">FAIL<" in text and "analytics-helper" in text
    for t in data["checks"][0]["data"]["write_capabilities"]:
        assert t in text
    for line in data["checks"][1]["data"]["broken"]:
        # markdown bits become html; check the tool name survives
        assert line.split("`")[1] in text if "`" in line else True
    assert ".mcp.json:11" in text and "Sources scanned" in text


def test_card_without_manifest(tmp_path):
    html = tmp_path / "c.html"
    cli.main(["scan", str(REPOS / "mcp-unknown-server"), "--format", "html", "-o", str(html)])
    text = html.read_text(encoding="utf-8")
    assert "no manifest declared" in text and "The promise (declared)" not in text


def test_diff_card_has_delta_on_top(tmp_path):
    html = tmp_path / "d.html"
    cli.main(["diff", KEPT, BROKEN, "--format", "html", "-o", str(html)])
    text = html.read_text(encoding="utf-8")
    assert "PROMISE BROKEN BY THIS CHANGE" in text
    body = text.split("<main>", 1)[1]
    assert body.index("PROMISE BROKEN BY THIS CHANGE") < body.index("analytics-helper")


def test_check_html_on_manifest_alone(tmp_path):
    html = tmp_path / "c.html"
    assert cli.main(["check", "all", str(REPOS.parent / "dangerous-agent.yaml"), "--format", "html", "-o", str(html)]) == cli.EXIT_GATE
    assert "CRITICAL" in html.read_text(encoding="utf-8")


def test_card_theme_flag(tmp_path):
    html = tmp_path / "c.html"
    cli.main(["scan", KEPT, "--format", "html", "--theme", "dark", "-o", str(html)])
    text = html.read_text(encoding="utf-8")
    assert '<html lang="en" data-theme="dark">' in text and "prefers-color-scheme: dark" in text
    cli.main(["scan", KEPT, "--format", "html", "-o", str(html)])
    assert "data-theme" not in html.read_text(encoding="utf-8").split("<head>")[0]  # auto follows the viewer


def test_card_prints_cleanly(tmp_path):
    """US-001-004: the printed card is white, legible, and nothing splits mid-page."""
    html = tmp_path / "c.html"
    cli.main(["scan", BROKEN, "--format", "html", "-o", str(html)])
    text = html.read_text(encoding="utf-8")
    css = text.split("<style>", 1)[1].split("</style>", 1)[0]
    assert "@media print" in css
    printed = css.split("@media print", 1)[1]
    assert "--bg:#fff" in printed and "--panel:#fff" in printed  # white paper, light or dark theme
    assert "box-shadow:none" in printed  # no decoration meant for a screen
    assert "break-inside:avoid" in printed and "page-break-inside:avoid" in printed
    assert ".card" in printed and "section.delta" in printed and "tr" in printed
    assert "print-color-adjust:exact" in printed  # the verdict badge keeps its colour
    assert "footer" in printed and "display:none" not in printed.replace(" ", "")
    # what an auditor needs on paper is in the file itself
    assert re.search(r"by agent-assurance \d+\.\d+\.\d+", text)  # footer: tool version
    policed = tmp_path / "p.html"
    cli.main(["scan", str(REPOS / "policy-org"), "--format", "html", "-o", str(policed)])
    assert re.search(r"Policy: .+? · <code>[0-9a-f]{12}</code>", policed.read_text(encoding="utf-8"))
