"""The Action's shell steps treat every input as data, and its gate is explicit.

These tests run the `run:` bodies of action.yml with bash, the way a runner
does (`bash --noprofile --norc -eo pipefail`), with each step's `env:` resolved
from the inputs under test. No step may contain an expression or `eval`, so the
body that runs here is the body that runs on GitHub.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPOS = ROOT / "examples" / "repos"
EXAMPLES = ROOT / "examples"
ACTION = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
STEPS = {s["name"]: s for s in ACTION["runs"]["steps"]}
DEFAULTS = {k: v.get("default", "") for k, v in ACTION["inputs"].items()}
EXPR = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="bash is needed to run the Action's steps")

# Each one has broken a shell script somewhere. `$(...)`, backticks and `;`
# create a canary file if they are ever executed.
HOSTILE = [
    "dir with spaces",
    "it's \"quoted\"",
    "$(touch pwned-subst)",
    "`touch pwned-tick`",
    "x; touch pwned-semi",
    "line1\nline2",
    "-leading-dash",
    "--help",
]

# The CLI and gh, replaced: they record their argv (one JSON list per line)
# and write what the Action expects to find.
STUB_CLI = """\
import json, os, sys
argv = sys.argv[1:]
with open(os.environ["AA_ARGV_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(argv) + "\\n")
out = next((a.split("=", 1)[1] for a in argv if a.startswith("--output=")), None)
fmt = argv[argv.index("--format") + 1] if "--format" in argv else None
if out and os.environ.get("AA_STUB_WRITE", "1") == "1":
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"verdict": os.environ.get("AA_STUB_VERDICT", "PASS")}) if fmt == "json" else "report")
sys.exit(int(os.environ.get("AA_STUB_EXIT", "0")))
"""

STUB_GH = """\
import json, os, sys
argv = sys.argv[1:]
with open(os.environ["AA_ARGV_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(["gh"] + argv) + "\\n")
if argv[:1] == ["api"] and "--paginate" in argv:
    bot = {"login": "github-actions[bot]"}
    comments = [{"id": 1, "user": bot, "body": "unrelated"}]
    if os.environ.get("AA_THIRD_PARTY_BODY"):
        comments.append({"id": 13, "user": {"login": "someone"}, "body": os.environ["AA_THIRD_PARTY_BODY"]})
    if os.environ.get("AA_EXISTING_BODY"):
        comments.append({"id": 42, "user": bot, "body": os.environ["AA_EXISTING_BODY"]})
    print(json.dumps(comments))
"""


def _stub(bin_dir: pathlib.Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _resolve(value: str, inputs: dict[str, str], context: dict[str, str]) -> str:
    def sub(m: re.Match) -> str:
        expr = m.group(1)
        if expr.startswith("inputs."):
            return inputs[expr.removeprefix("inputs.")]
        return context.get(expr, "")

    return EXPR.sub(sub, str(value))


class Runner:
    """A workspace, a RUNNER_TEMP and the files a runner hands to each step."""

    def __init__(self, tmp: pathlib.Path, stub_cli: bool = True):
        self.work = tmp / "work"
        self.temp = tmp / "runner-temp"
        self.bin = tmp / "bin"
        for d in (self.work, self.temp, self.bin):
            d.mkdir()
        self.log = tmp / "argv.log"
        self.log.touch()
        if stub_cli:
            _stub(self.bin, "agent-assurance", STUB_CLI)
        _stub(self.bin, "gh", STUB_GH)
        real = pathlib.Path(sys.executable).parent
        self.path = os.pathsep.join([str(self.bin), str(real), os.environ.get("PATH", "")])

    def step(self, name: str, inputs: dict[str, str] | None = None, extra_env: dict[str, str] | None = None):
        step = STEPS[name]
        merged = {**DEFAULTS, **(inputs or {})}
        output = self.temp / "github_output"
        summary = self.temp / "step_summary"
        output.write_text("", encoding="utf-8")
        summary.write_text("", encoding="utf-8")
        env = {
            "PATH": self.path,
            "HOME": os.environ.get("HOME", str(self.work)),
            "RUNNER_TEMP": str(self.temp),
            "GITHUB_OUTPUT": str(output),
            "GITHUB_STEP_SUMMARY": str(summary),
            "GITHUB_ACTION_PATH": str(ROOT),
            "AA_ARGV_LOG": str(self.log),
        }
        env.update({k: _resolve(v, merged, {}) for k, v in (step.get("env") or {}).items()})
        env.update(extra_env or {})
        proc = subprocess.run(
            [BASH, "--noprofile", "--norc", "-eo", "pipefail", "-c", step["run"]],
            check=False,
            cwd=self.work,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return proc, _outputs(output.read_text(encoding="utf-8"))

    def calls(self) -> list[list[str]]:
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def canaries(self, tmp: pathlib.Path) -> list[str]:
        return sorted(str(p) for p in tmp.rglob("pwned*"))


def _outputs(text: str) -> dict[str, str]:
    """Parse GITHUB_OUTPUT: `k=v` lines and `k<<DELIM` ... `DELIM` blocks."""
    out: dict[str, str] = {}
    lines = iter(text.splitlines())
    for line in lines:
        if "<<" in line and "=" not in line.split("<<", 1)[0]:
            key, delim = line.split("<<", 1)
            body = []
            for nxt in lines:
                if nxt == delim:
                    break
                body.append(nxt)
            out[key] = "\n".join(body)
        elif "=" in line:
            key, value = line.split("=", 1)
            out[key] = value
    return out


def _dotted(path: str) -> str:
    return "./" + path if path.startswith("-") else path


# --- static: no expression and no eval inside a shell body --------------------


def test_no_run_body_holds_an_expression_or_eval():
    for step in ACTION["runs"]["steps"]:
        body = step.get("run", "")
        assert "${{" not in body, f"expression inside run: of {step['name']!r}; pass it through env:"
        assert not re.search(r"\beval\b", body), f"eval inside run: of {step['name']!r}"


def test_every_input_reaches_the_shell_through_env():
    used = set()
    for step in ACTION["runs"]["steps"]:
        for value in (step.get("env") or {}).values():
            used.update(m.removeprefix("inputs.") for m in EXPR.findall(str(value)) if m.startswith("inputs."))
    # Inputs consumed by `uses:` steps (with:) or only in `if:` do not need env.
    assert {"mode", "directory", "manifest", "check", "policy", "fail-on", "fail-on-delta", "sarif", "card", "attest"} <= used


# --- hostile values are data -----------------------------------------------------


@pytest.mark.parametrize("hostile", HOSTILE, ids=range(len(HOSTILE)))
def test_scan_argv_carries_hostile_values_verbatim(tmp_path, hostile):
    run = Runner(tmp_path)
    (run.work / hostile).mkdir()
    (run.work / hostile / "agent-assurance.yaml").write_text("x", encoding="utf-8")
    inputs = {
        "mode": "scan",
        "directory": hostile,
        "manifest": f"{hostile}/agent-assurance.yaml",
        "policy": f"{hostile}.policy.yaml",
        "sarif": f"{hostile}.sarif",
        "card": f"{hostile}.html",
    }
    proc, out = run.step("Run Agent Assurance", inputs)
    assert proc.returncode == 0, proc.stderr
    assert out == {"verdict": "PASS", "gate": "open"}
    base = ["scan", _dotted(hostile), "--check=all", f"--manifest={hostile}/agent-assurance.yaml", f"--policy={hostile}.policy.yaml"]
    assert run.calls() == [
        base + ["--format", "md", "--output=aa-report.md", "--fail-on=fail"],
        base + ["--format", "json", f"--output={run.temp}/aa-report.json", "--fail-on=fail"],
        base + ["--format", "sarif", f"--output={hostile}.sarif"],
        base + ["--format", "html", f"--output={hostile}.html"],
    ]
    assert run.canaries(tmp_path) == []
    # printf %q keeps the logged command on one line: no forged workflow command.
    assert not any(line.startswith("::") for line in proc.stdout.splitlines())


@pytest.mark.parametrize("hostile", HOSTILE, ids=range(len(HOSTILE)))
def test_check_and_diff_argv_carry_hostile_values_verbatim(tmp_path, hostile):
    run = Runner(tmp_path)
    proc, _ = run.step("Run Agent Assurance", {"mode": "check", "manifest": hostile, "policy": hostile})
    assert proc.returncode == 0, proc.stderr
    assert run.calls()[0] == ["check", "all", _dotted(hostile), f"--policy={hostile}", "--format", "md", "--output=aa-report.md", "--fail-on=fail"]

    run.log.write_text("", encoding="utf-8")
    proc, _ = run.step("Run Agent Assurance", {"mode": "diff", "directory": hostile, "fail-on": "review"})
    assert proc.returncode == 0, proc.stderr
    assert run.calls()[0] == [
        "diff", f"{run.temp}/aa-base/{hostile}", _dotted(hostile), "--fail-on-delta",
        "--format", "md", "--output=aa-report.md", "--fail-on=review",
    ]
    assert run.canaries(tmp_path) == []


@pytest.mark.parametrize("hostile", HOSTILE, ids=range(len(HOSTILE)))
def test_attest_argv_and_subjects_survive_hostile_values(tmp_path, hostile):
    run = Runner(tmp_path)
    (run.work / hostile).mkdir()
    (run.work / hostile / "agent-assurance.yaml").write_text("x", encoding="utf-8")
    # The statement needs subjects; the default stub writes a verdict instead.
    statement = {"subject": [{"name": "agent-assurance.yaml"}, {"name": "EOF"}]}
    _stub(run.bin, "agent-assurance", STUB_CLI.replace("sys.exit(", f"open(out, 'w').write({json.dumps(json.dumps(statement))})\nsys.exit("))
    inputs = {"mode": "scan", "attest": "write", "directory": hostile, "manifest": f"{hostile}/agent-assurance.yaml", "check": "all"}
    proc, out = run.step("Write attestation (optional, unsigned)", inputs)
    assert proc.returncode == 0, proc.stderr
    assert run.calls() == [["attest", _dotted(hostile), "--check=all", f"--manifest={hostile}/agent-assurance.yaml", "--output=aa-attestation.json"]]
    # A subject named EOF (or a directory with a newline) cannot end the output early.
    assert out["subjects"] == "\n".join(os.path.normpath(os.path.join(hostile, n)) for n in ("agent-assurance.yaml", "EOF"))
    assert set(out) == {"subjects"}
    assert run.canaries(tmp_path) == []


def test_comment_marker_reaches_jq_as_data(tmp_path):
    if shutil.which("jq") is None:
        pytest.skip("jq is needed for the comment step")
    run = Runner(tmp_path)
    (run.work / "aa-report.md").write_text("report", encoding="utf-8")
    hostile = 'a" or true or "$(touch pwned-jq)'
    marker = f"<!-- agent-assurance:{hostile} -->"
    proc, _ = run.step(
        "Comment on the pull request (mode: diff)",
        {"directory": hostile},
        {"REPO": "o/r", "PR": "7", "GH_TOKEN": "x", "AA_EXISTING_BODY": marker + "\nold"},
    )
    assert proc.returncode == 0, proc.stderr
    assert ["gh", "api", "-X", "PATCH", "repos/o/r/issues/comments/42", "-F", "body=@aa-comment.md"] in run.calls()
    assert (run.work / "aa-comment.md").read_text(encoding="utf-8").startswith(marker + "\n")
    assert run.canaries(tmp_path) == []

    # A filter injection would have matched the unrelated comment too; data does not.
    proc, _ = run.step(
        "Comment on the pull request (mode: diff)",
        {"directory": hostile},
        {"REPO": "o/r", "PR": "7", "GH_TOKEN": "x", "AA_EXISTING_BODY": "something else"},
    )
    assert ["gh", "pr", "comment", "7", "--body-file", "aa-comment.md"] in run.calls()


# --- inputs are validated before anything runs ----------------------------------------


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("mode", "scna"),
        ("mode", "scan; touch pwned"),
        ("fail-on", "warn"),
        ("fail-on", "REVIEW"),
        ("fail-on-delta", "yes"),
        ("attest", "true"),
        ("check", "--help"),
        ("check", "-x"),
        ("check", ""),
    ],
)
def test_invalid_gate_inputs_are_usage_errors(tmp_path, name, value):
    run = Runner(tmp_path)
    proc, _ = run.step("Validate inputs", {name: value})
    assert proc.returncode == 2
    assert f"::error::agent-assurance: input '{name}'" in proc.stdout
    if value:
        assert value not in proc.stdout  # the value is never echoed
    assert run.canaries(tmp_path) == []


def test_a_third_party_comment_with_the_marker_is_never_edited(tmp_path):
    if shutil.which("jq") is None:
        pytest.skip("jq is needed for the comment step")
    run = Runner(tmp_path)
    (run.work / "aa-report.md").write_text("report", encoding="utf-8")
    marker = "<!-- agent-assurance:. -->"
    env = {"REPO": "o/r", "PR": "7", "GH_TOKEN": "x", "AA_THIRD_PARTY_BODY": marker + "\nfake PASS"}
    proc, _ = run.step("Comment on the pull request (mode: diff)", {}, env)
    assert proc.returncode == 0, proc.stderr
    calls = run.calls()
    assert not any("PATCH" in c for c in calls)
    assert ["gh", "pr", "comment", "7", "--body-file", "aa-comment.md"] in calls

    # With the bot's own comment present as well, the bot's is the one updated.
    run.log.write_text("", encoding="utf-8")
    proc, _ = run.step("Comment on the pull request (mode: diff)", {}, {**env, "AA_EXISTING_BODY": marker + "\nold"})
    assert proc.returncode == 0, proc.stderr
    patches = [c for c in run.calls() if "PATCH" in c]
    assert patches == [["gh", "api", "-X", "PATCH", "repos/o/r/issues/comments/42", "-F", "body=@aa-comment.md"]]


@pytest.mark.parametrize("value", ["TRUE", "True", "False", "FALSE", "true", "false"])
@pytest.mark.parametrize("name", ["comment", "upload-sarif"])
def test_non_gate_booleans_follow_the_case_insensitive_if(tmp_path, name, value):
    """GitHub's `if:` compares strings without case, so TRUE posts; no false warning."""
    proc, _ = Runner(tmp_path).step("Validate inputs", {name: value})
    assert proc.returncode == 0 and proc.stdout == ""


@pytest.mark.parametrize(
    "directory",
    ["..", "../other", "a/../../b", "a/..", "/etc", "/", "//x"],
)
def test_diff_directory_must_stay_inside_the_base_tree(tmp_path, directory):
    run = Runner(tmp_path)
    proc, _ = run.step("Validate inputs", {"mode": "diff", "directory": directory})
    assert proc.returncode == 2
    assert "::error::agent-assurance: input 'directory'" in proc.stdout


@pytest.mark.parametrize("directory", [".", "sub/dir", "a..b", "..hidden", "-dash"])
def test_diff_directory_inside_the_tree_is_accepted(tmp_path, directory):
    proc, _ = Runner(tmp_path).step("Validate inputs", {"mode": "diff", "directory": directory})
    assert proc.returncode == 0, proc.stdout


def test_scan_directory_is_not_restricted(tmp_path):
    proc, _ = Runner(tmp_path).step("Validate inputs", {"mode": "scan", "directory": "/abs/../path"})
    assert proc.returncode == 0


@pytest.mark.parametrize("name", ["comment", "upload-sarif"])
def test_non_gate_booleans_warn_but_keep_their_meaning(tmp_path, name):
    run = Runner(tmp_path)
    proc, _ = run.step("Validate inputs", {name: "yes"})
    assert proc.returncode == 0
    assert f"::warning::agent-assurance: input '{name}'" in proc.stdout


def test_defaults_are_valid(tmp_path):
    proc, _ = Runner(tmp_path).step("Validate inputs")
    assert proc.returncode == 0 and proc.stdout == ""


# --- gate semantics, with the real CLI ------------------------------------------------


def _real(tmp_path) -> Runner:
    if shutil.which("agent-assurance", path=str(pathlib.Path(sys.executable).parent)) is None:
        pytest.skip("agent-assurance is not installed next to this Python")
    return Runner(tmp_path, stub_cli=False)


@pytest.mark.parametrize(
    ("inputs", "verdict", "gate", "warns"),
    [
        ({"manifest": str(EXAMPLES / "safe-agent.yaml")}, "PASS", "open", False),
        ({"manifest": str(EXAMPLES / "safe-agent.yaml"), "fail-on": "review"}, "PASS", "open", False),
        ({"manifest": str(EXAMPLES / "high-agent.yaml")}, "REVIEW", "open", True),
        ({"manifest": str(EXAMPLES / "high-agent.yaml"), "fail-on": "review"}, "REVIEW", "tripped", False),
        ({"manifest": str(EXAMPLES / "dangerous-agent.yaml")}, "FAIL", "tripped", False),
        ({"manifest": str(EXAMPLES / "dangerous-agent.yaml"), "fail-on": "review"}, "FAIL", "tripped", False),
        # Unverifiable (an MCP server nobody can classify) is REVIEW, never PASS.
        ({"mode": "scan", "directory": str(REPOS / "mcp-unknown-server")}, "REVIEW", "open", True),
        ({"mode": "scan", "directory": str(REPOS / "mcp-unknown-server"), "fail-on": "review"}, "REVIEW", "tripped", False),
        ({"mode": "scan", "directory": str(REPOS / "mcp-promise-broken")}, "FAIL", "tripped", False),
    ],
    ids=["pass", "pass-strict", "review", "review-strict", "fail", "fail-strict", "unknown", "unknown-strict", "broken"],
)
def test_gate_per_verdict_and_fail_on(tmp_path, inputs, verdict, gate, warns):
    run = _real(tmp_path)
    proc, out = run.step("Run Agent Assurance", inputs)
    assert proc.returncode == 0, proc.stderr
    assert out == {"verdict": verdict, "gate": gate}
    assert ("::warning::Agent Assurance verdict is REVIEW" in proc.stdout) is warns


def test_diff_mode_gates_on_the_head_verdict(tmp_path):
    run = _real(tmp_path)
    shutil.copytree(REPOS / "mcp-promise-kept", run.temp / "aa-base" / "head")
    shutil.copytree(REPOS / "mcp-promise-broken", run.work / "head")
    proc, out = run.step("Run Agent Assurance", {"mode": "diff", "directory": "head"})
    assert proc.returncode == 0, proc.stderr
    assert out == {"verdict": "FAIL", "gate": "tripped"}


@pytest.mark.parametrize("hostile", HOSTILE, ids=range(len(HOSTILE)))
def test_real_cli_scans_a_hostile_directory(tmp_path, hostile):
    run = _real(tmp_path)
    shutil.copytree(REPOS / "mcp-promise-kept", run.work / hostile)
    inputs = {"mode": "scan", "directory": hostile, "manifest": f"{hostile}/agent-assurance.yaml", "fail-on": "review", "card": f"{hostile}.html"}
    proc, out = run.step("Run Agent Assurance", inputs)
    assert proc.returncode == 0, proc.stderr
    assert out == {"verdict": "PASS", "gate": "open"}
    assert (run.work / f"{hostile}.html").is_file()
    assert run.canaries(tmp_path) == []


def test_missing_manifest_is_an_error_not_a_pass(tmp_path):
    run = _real(tmp_path)
    proc, out = run.step("Run Agent Assurance", {"manifest": "nope.yaml"})
    assert proc.returncode == 2
    assert out["verdict"] == "ERROR"


@pytest.mark.parametrize(
    ("stub_env", "code", "verdict", "gate"),
    [
        # exit 0 but nothing written (e.g. a help text): no result, so no pass.
        ({"AA_STUB_WRITE": "0"}, 2, "ERROR", "tripped"),
        # A verdict outside PASS/REVIEW/FAIL is not a result either.
        ({"AA_STUB_VERDICT": "UNKNOWN"}, 2, "ERROR", "tripped"),
        # exit 0 with a FAIL verdict cannot open the gate.
        ({"AA_STUB_VERDICT": "FAIL"}, 0, "FAIL", "tripped"),
        # A crash (exit 1 without output) is an error.
        ({"AA_STUB_WRITE": "0", "AA_STUB_EXIT": "1"}, 2, "ERROR", "tripped"),
        # A usage error is ERROR even when a report with a verdict was written.
        ({"AA_STUB_EXIT": "2"}, 2, "ERROR", "tripped"),
    ],
    ids=["no-output", "unknown-verdict", "fail-exit-0", "crash", "usage"],
)
def test_no_verdict_never_reads_as_a_pass(tmp_path, stub_env, code, verdict, gate):
    run = Runner(tmp_path)
    proc, out = run.step("Run Agent Assurance", {}, stub_env)
    assert proc.returncode == code
    assert out == {"verdict": verdict, "gate": gate}


def test_a_stale_report_from_an_earlier_run_is_not_reused(tmp_path):
    run = Runner(tmp_path)
    (run.work / "aa-report.md").write_text("old PASS report", encoding="utf-8")
    (run.temp / "aa-report.json").write_text('{"verdict": "PASS"}', encoding="utf-8")
    proc, out = run.step("Run Agent Assurance", {}, {"AA_STUB_WRITE": "0"})
    assert proc.returncode == 2
    assert out["verdict"] == "ERROR"
