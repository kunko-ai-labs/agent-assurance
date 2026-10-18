"""Policy file: tune the model, never silently. No policy = built-in model."""

from __future__ import annotations

import json
import pathlib

import pytest

from agent_assurance import cli, policy, risk
from agent_assurance.manifest import Manifest
from agent_assurance.scan import catalog

REPOS = pathlib.Path(__file__).resolve().parents[1] / "examples" / "repos"
ORG = REPOS / "policy-org"
KEPT = REPOS / "mcp-promise-kept"


def test_defaults_equal_documented_model():
    p = policy.Policy()
    assert p.is_default
    assert p.weights.tools.as_map() == risk.TOOL_WEIGHTS
    assert p.weights.data.as_map() == risk.DATA_WEIGHTS
    assert p.bands.table() == risk.BANDS
    assert p.weights.production == risk.PRODUCTION_WEIGHT
    assert p.weights.auto_approval == risk.AUTO_APPROVAL_WEIGHT


def test_policy_is_discovered_and_recorded(tmp_path):
    out = tmp_path / "r.json"
    cli.main(["scan", str(ORG), "--format", "json", "-o", str(out)])
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["policy"]["name"] == "acme-corp-2026-09"
    assert len(r["policy"]["sha256"]) == 64
    assert r["policy"]["path"].endswith("agent-assurance.policy.yaml")


def test_policy_catalog_turns_unknown_into_known():
    loaded = policy.load(str(ORG / "agent-assurance.policy.yaml"))
    assert catalog.lookup("acme-erp", "") is None
    policy.activate(loaded)
    entry = catalog.lookup("acme-erp", "")
    assert entry is not None and entry.system == "acme-erp" and entry.source.startswith("internal")


def test_policy_gate_and_promise_semantics(tmp_path):
    out = tmp_path / "r.json"
    code = cli.main(["scan", str(ORG), "--format", "json", "-o", str(out)])
    r = json.loads(out.read_text(encoding="utf-8"))
    aa1 = next(c for c in r["checks"] if c["id"] == "AA-001")
    aa2 = next(c for c in r["checks"] if c["id"] == "AA-002")
    # stricter gate: MEDIUM is already review
    assert aa1["data"]["band"] == "MEDIUM" and aa1["status"] == "REVIEW"
    # external_send removed from breaking: the remote server is review, not broken
    assert aa2["status"] == "REVIEW" and aa2["data"]["broken"] == []
    assert code == cli.EXIT_OK


def test_policy_weights_change_the_score(tmp_path):
    pol = tmp_path / "p.yaml"
    pol.write_text("apiVersion: agent-assurance/policy/v1\nname: heavy\nweights:\n  tools: {read: 10}\n", encoding="utf-8")
    m = Manifest.from_file(str(KEPT / "agent-assurance.yaml"))
    assert risk.assess(m).score == 3
    policy.activate(policy.load(str(pol)))
    assert risk.assess(m).score == 21  # two reads at 10 + internal data 1


def test_policy_read_only_commands_extend_defaults(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text('{"permissions": {"allow": ["Bash(poetry run pytest:*)"]}}', encoding="utf-8")
    (tmp_path / "agent-assurance.policy.yaml").write_text(
        "apiVersion: agent-assurance/policy/v1\nname: t\nread_only_commands: [poetry run pytest]\n", encoding="utf-8"
    )
    out = tmp_path / "r.json"
    cli.main(["scan", str(tmp_path), "--format", "json", "-o", str(out)])
    r = json.loads(out.read_text(encoding="utf-8"))
    tools = r["checks"][0]["data"]
    assert tools["write_capabilities"] == [] and tools["auto_approved"] == []


def test_invalid_policy_is_usage_error(tmp_path, capsys):
    bad = tmp_path / "p.yaml"
    bad.write_text("apiVersion: agent-assurance/policy/v9\n", encoding="utf-8")
    assert cli.main(["scan", str(KEPT), "--policy", str(bad)]) == cli.EXIT_USAGE
    bad.write_text("apiVersion: agent-assurance/policy/v1\nweights: {tools: {read: many}}\n", encoding="utf-8")
    assert cli.main(["scan", str(KEPT), "--policy", str(bad)]) == cli.EXIT_USAGE
    assert "invalid policy" in capsys.readouterr().err
    assert cli.main(["scan", str(KEPT), "--policy", str(tmp_path / "nope.yaml")]) == cli.EXIT_USAGE


def test_policy_does_not_leak_between_runs(tmp_path):
    out = tmp_path / "r.json"
    cli.main(["scan", str(ORG), "--format", "json", "-o", str(out)])
    cli.main(["scan", str(KEPT), "--format", "json", "-o", str(out)])
    assert json.loads(out.read_text(encoding="utf-8"))["policy"] is None


def test_validate_policy_reports_name_sha256_and_overrides(tmp_path, capsys):
    pol = tmp_path / "p.yaml"
    pol.write_text(
        "apiVersion: agent-assurance/policy/v1\n"
        "name: acme-corp\n"
        "weights:\n  tools: {read: 10}\n"
        "read_only_commands: [poetry run pytest]\n",
        encoding="utf-8",
    )
    assert cli.main(["validate", "--policy", str(pol)]) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "valid agent-assurance/policy/v1 policy" in out
    assert "name=acme-corp" in out
    assert "sha256=" in out
    assert "weights (tools.read=10)" in out
    assert "read_only_commands (+1)" in out


def test_validate_detects_a_policy_by_api_version(tmp_path, capsys):
    pol = tmp_path / "not-named-policy.yaml"
    pol.write_text("apiVersion: agent-assurance/policy/v1\nname: detected\n", encoding="utf-8")
    assert cli.main(["validate", str(pol)]) == cli.EXIT_OK
    assert "detected" in capsys.readouterr().out


def test_validate_policy_with_no_overrides_says_so(tmp_path, capsys):
    pol = tmp_path / "p.yaml"
    pol.write_text("apiVersion: agent-assurance/policy/v1\nname: empty\n", encoding="utf-8")
    assert cli.main(["validate", "--policy", str(pol)]) == cli.EXIT_OK
    assert "every value equals the built-in default" in capsys.readouterr().out


def test_validate_command_rejects_invalid_policies(tmp_path, capsys):
    bad = tmp_path / "p.yaml"
    bad.write_text("apiVersion: agent-assurance/policy/v9\n", encoding="utf-8")
    assert cli.main(["validate", "--policy", str(bad)]) == cli.EXIT_USAGE
    assert "unsupported policy apiVersion" in capsys.readouterr().err

    bad.write_text(
        "apiVersion: agent-assurance/policy/v1\nweights: {tools: {read: many}}\n",
        encoding="utf-8",
    )
    assert cli.main(["validate", "--policy", str(bad)]) == cli.EXIT_USAGE
    assert "invalid policy" in capsys.readouterr().err

    bad.write_text("apiVersion: agent-assurance/policy/v1\nname: [broken\n", encoding="utf-8")
    assert cli.main(["validate", "--policy", str(bad)]) == cli.EXIT_USAGE
    assert "invalid policy YAML" in capsys.readouterr().err

    assert cli.main(["validate", "--policy", str(tmp_path / "missing.yaml")]) == cli.EXIT_USAGE


def test_validate_still_validates_a_manifest_and_requires_a_target(tmp_path, capsys):
    manifest = KEPT / "agent-assurance.yaml"
    assert cli.main(["validate", str(manifest)]) == cli.EXIT_OK
    assert "valid agent-assurance/v1 manifest" in capsys.readouterr().out

    assert cli.main(["validate"]) == cli.EXIT_USAGE
    assert "nothing to validate" in capsys.readouterr().err

    both = cli.main(["validate", str(manifest), "--policy", str(manifest)])
    assert both == cli.EXIT_USAGE
    assert "not both" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("weights: {tools: {write: -3}}", "greater than or equal to 0"),
        ("weights: {data: {credential: -1}}", "greater than or equal to 0"),
        ("weights: {production: -5}", "greater than or equal to 0"),
        ("bands: {medium: 20, high: 16}", "band bounds must rise strictly"),
        ("bands: {high: 28, critical: 28}", "band bounds must rise strictly"),
        ("bands: {medium: 0}", "band bounds must rise strictly"),
        ("gate: {fail_bands: [critical]}", "unknown band 'critical'"),
        ("gate: {review_bands: [HIGHT]}", "unknown band 'HIGHT'"),
        ("gate: {review_bands: [HIGH], fail_bands: [HIGH, CRITICAL]}", "HIGH are in both"),
        ("gate: {review_bands: [], fail_bands: [HIGH]}", "HIGH fails but CRITICAL"),
        ("gate: {review_bands: [MEDIUM], fail_bands: [CRITICAL]}", "MEDIUM is gated but HIGH"),
        ("promise: {max_autonomy_with_human: 9}", "less than or equal to 5"),
    ],
)
def test_contradictory_policies_are_refused(tmp_path, capsys, body, message):
    """A policy that could open the gate by mistake is a usage error, never a quieter run."""
    pol = tmp_path / "p.yaml"
    pol.write_text(f"apiVersion: agent-assurance/policy/v1\n{body}\n", encoding="utf-8")
    assert cli.main(["validate", "--policy", str(pol)]) == cli.EXIT_USAGE
    assert message in capsys.readouterr().err
    assert cli.main(["scan", str(KEPT), "--policy", str(pol)]) == cli.EXIT_USAGE


@pytest.mark.parametrize(
    "body",
    [
        "gate: {review_bands: [MEDIUM], fail_bands: [HIGH, CRITICAL]}",
        "gate: {review_bands: [LOW, MEDIUM, HIGH, CRITICAL], fail_bands: []}",
        "gate: {review_bands: [], fail_bands: []}",
        "bands: {medium: 1, high: 2, critical: 3}",
    ],
)
def test_consistent_gates_and_bands_are_accepted(tmp_path, body):
    pol = tmp_path / "p.yaml"
    pol.write_text(f"apiVersion: agent-assurance/policy/v1\n{body}\n", encoding="utf-8")
    assert cli.main(["validate", "--policy", str(pol)]) == cli.EXIT_OK
