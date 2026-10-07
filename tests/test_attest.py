"""attest: an in-toto statement about the files the verdict depends on."""

from __future__ import annotations

import hashlib
import json
import pathlib

from agent_assurance import attest, cli

REPOS = pathlib.Path(__file__).resolve().parents[1] / "examples" / "repos"
KEPT = REPOS / "mcp-promise-kept"
BROKEN = REPOS / "mcp-promise-broken"


def _statement(directory: pathlib.Path, tmp_path) -> tuple[int, dict]:
    out = tmp_path / "att.json"
    code = cli.main(["attest", str(directory), "-o", str(out)])
    return code, json.loads(out.read_text(encoding="utf-8"))


def test_statement_shape_and_subjects(tmp_path):
    code, s = _statement(KEPT, tmp_path)
    assert code == cli.EXIT_OK
    assert s["_type"] == attest.STATEMENT_TYPE
    assert s["predicateType"] == attest.PREDICATE_TYPE
    subjects = {x["name"]: x["digest"]["sha256"] for x in s["subject"]}
    assert set(subjects) == {"agent-assurance.yaml", ".mcp.json"}
    # digests are real sha256 of the files
    for name, digest in subjects.items():
        assert digest == hashlib.sha256((KEPT / name).read_bytes()).hexdigest()


def test_predicate_carries_declared_observed_and_verdict(tmp_path):
    code, s = _statement(BROKEN, tmp_path)
    assert code == cli.EXIT_GATE  # evidence written, gate still reported
    p = s["predicate"]
    assert p["tool"]["name"] == "agent-assurance" and p["tool"]["version"] == cli.__version__
    assert p["declared"]["agent"]["name"] == "analytics-helper"
    assert any(t["source"] for t in p["observed"]["tools"])
    assert p["report"]["verdict"] == "FAIL"
    assert "OWASP-ASI:ASI03" in p["standards"] and "EU-AI-ACT:Art. 12" in p["standards"]
    assert p["generatedAt"].endswith("+00:00")


def test_attest_without_manifest_has_only_config_subjects(tmp_path):
    code, s = _statement(REPOS / "mcp-unknown-server", tmp_path)
    assert code == cli.EXIT_OK
    assert {x["name"] for x in s["subject"]} == {".mcp.json", ".claude/settings.json"}  # AGENTS.md is not parsed
    assert s["predicate"]["declared"] is None


def test_attest_nothing_to_scan_is_usage_error(tmp_path):
    assert cli.main(["attest", str(tmp_path), "-o", str(tmp_path / "x.json")]) == cli.EXIT_USAGE
