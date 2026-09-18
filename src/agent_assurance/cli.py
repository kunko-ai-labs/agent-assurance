"""agent-assurance CLI.

Commands:
  agent-assurance validate <manifest|policy> [--policy FILE]
  agent-assurance check [blast-radius|all] <manifest> [--format md|json|sarif] [--output FILE]
  agent-assurance scan <dir> [--manifest FILE] [--format ...] [--output FILE]
  agent-assurance diff <base-dir> <head-dir> [--fail-on-delta] [--format ...]
  agent-assurance attest <dir> [--manifest FILE] -o attestation.json

Exit codes: 0 = pass/review, 1 = FAIL, 2 = usage/manifest error.
Use --fail-on {fail,review} to control what gates the pipeline.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import yaml

from . import __version__, attest, diff, engine, policy, reports
from .checks import CHECK_ALIASES
from .checks.base import Context, Status
from .manifest import Manifest, ManifestError
from .scan import scan_directory

# Every renderer takes (report, manifest_path). Only SARIF needs the path today
# (code scanning must resolve the finding to a real file in the repo), but the
# uniform signature keeps cmd_check free of per-format branching.
_FORMATS = {
    "md": lambda report, _path: reports.to_markdown(report),
    "markdown": lambda report, _path: reports.to_markdown(report),
    "json": lambda report, _path: reports.to_json(report),
    "sarif": lambda report, path: reports.to_sarif(report, manifest_path=path),
    "html": lambda report, _path, theme="auto": reports.to_html(report, theme=theme),
}

# Exit codes are the contract the GitHub Action relies on.
EXIT_OK = 0
EXIT_GATE = 1
EXIT_USAGE = 2


def _load(path: str) -> Manifest | None:
    """Load a manifest, or print the error and return None (caller exits 2)."""
    try:
        return Manifest.from_file(path)
    except FileNotFoundError:
        print(f"error: manifest not found: {path}", file=sys.stderr)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
    return None


def _emit(report: engine.AssuranceReport, args: argparse.Namespace, anchor: str) -> None:
    if args.format == "html":
        output = reports.to_html(report, theme=getattr(args, "theme", "auto"))
    else:
        output = _FORMATS[args.format](report, anchor)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(output)
        print(f"wrote {args.format} report to {args.output}", file=sys.stderr)
    else:
        print(output)


def _gate(report: engine.AssuranceReport, fail_on: str) -> int:
    gate_fail = report.verdict is Status.FAIL
    gate_review = report.verdict in (Status.FAIL, Status.REVIEW)
    if fail_on == "review" and gate_review:
        return EXIT_GATE
    if fail_on == "fail" and gate_fail:
        return EXIT_GATE
    return EXIT_OK


def _resolve_checks(name: str) -> list[str] | None:
    if name in ("all", "*"):
        return None
    cid = CHECK_ALIASES.get(name, name)
    return [cid]


def _apply_policy(args: argparse.Namespace, directory: str | None = None) -> int:
    """Activate --policy, or <directory>/agent-assurance.policy.yaml if present."""
    policy.reset()
    path = getattr(args, "policy", None) or (policy.discover(directory) if directory else None)
    if not path:
        return EXIT_OK
    try:
        policy.activate(policy.load(path))
    except FileNotFoundError:
        print(f"error: policy not found: {path}", file=sys.stderr)
        return EXIT_USAGE
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    return EXIT_OK


def _is_policy_file(path: str) -> bool:
    """A policy file is recognised by its apiVersion, not its name."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except (FileNotFoundError, yaml.YAMLError):
        return False
    return isinstance(raw, dict) and raw.get("apiVersion") == policy.API_VERSION


def _policy_override_summary(pol: policy.Policy) -> str:
    """One line naming what a policy changes relative to the built-in model."""
    default = policy.Policy()

    def _changed_leaves(new: dict, old: dict, prefix: str = "") -> list[str]:
        leaves: list[str] = []
        for key, value in new.items():
            previous = old.get(key)
            if isinstance(value, dict) and isinstance(previous, dict):
                leaves.extend(_changed_leaves(value, previous, f"{prefix}{key}."))
            elif value != previous:
                leaves.append(f"{prefix}{key}={value!r}")
        return leaves

    parts: list[str] = []
    weight_leaves = _changed_leaves(pol.weights.model_dump(), default.weights.model_dump())
    if weight_leaves:
        shown = ", ".join(weight_leaves[:4])
        if len(weight_leaves) > 4:
            shown += f", +{len(weight_leaves) - 4} more"
        parts.append(f"weights ({shown})")
    band_leaves = _changed_leaves(pol.bands.model_dump(), default.bands.model_dump())
    if band_leaves:
        parts.append(f"bands ({', '.join(band_leaves)})")
    if pol.gate != default.gate:
        parts.append(f"gate (review={pol.gate.review_bands}, fail={pol.gate.fail_bands})")
    if pol.promise != default.promise:
        parts.append("promise (breaking access/data classes)")
    if pol.read_only_commands:
        parts.append(f"read_only_commands (+{len(pol.read_only_commands)})")
    if pol.catalog:
        parts.append(f"catalog (+{len(pol.catalog)} entries)")
    if pol.tool_definition_files:
        parts.append(f"tool_definition_files (+{len(pol.tool_definition_files)})")
    return ", ".join(parts) if parts else "none — every value equals the built-in default"


def _validate_policy(path: str) -> int:
    try:
        pol = policy.load(path)
    except FileNotFoundError:
        print(f"error: policy not found: {path}", file=sys.stderr)
        return EXIT_USAGE
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    print(f"ok: {path} is a valid {policy.API_VERSION} policy")
    print(f"    name={pol.name} sha256={pol.sha256}")
    print(f"    overrides: {_policy_override_summary(pol)}")
    return EXIT_OK


def cmd_validate(args: argparse.Namespace) -> int:
    if args.policy and args.file:
        print("error: pass a file or --policy, not both", file=sys.stderr)
        return EXIT_USAGE
    target = args.policy or args.file
    if not target:
        print(
            "error: nothing to validate: pass a manifest, a policy file, or --policy PATH",
            file=sys.stderr,
        )
        return EXIT_USAGE
    if args.policy or _is_policy_file(target):
        return _validate_policy(target)
    if not os.path.isfile(target):
        print(f"error: file not found: {target}", file=sys.stderr)
        return EXIT_USAGE
    m = _load(target)
    if m is None:
        return EXIT_USAGE
    print(f"ok: {target} is a valid agent-assurance/v1 manifest")
    print(f"    agent={m.agent.name} v{m.agent.version} autonomy=L{m.autonomy} "
          f"tools={len(m.tools)} data={len(m.data)}")
    return EXIT_OK


def cmd_check(args: argparse.Namespace) -> int:
    if _apply_policy(args, os.path.dirname(os.path.abspath(args.manifest))) != EXIT_OK:
        return EXIT_USAGE
    m = _load(args.manifest)
    if m is None:
        return EXIT_USAGE
    try:
        check_ids = _resolve_checks(args.check)
        report = engine.run(m, check_ids)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    _emit(report, args, args.manifest)
    return _gate(report, args.fail_on)


def _scan_report(args: argparse.Namespace):
    """Shared by scan and attest: (report, declared_path) or (None, exit code)."""
    root = args.directory
    if not os.path.isdir(root):
        print(f"error: not a directory: {root}", file=sys.stderr)
        return None, EXIT_USAGE
    if _apply_policy(args, root) != EXIT_OK:
        return None, EXIT_USAGE
    declared = None
    manifest_path = args.manifest or os.path.join(root, "agent-assurance.yaml")
    if args.manifest or os.path.isfile(manifest_path):
        declared = _load(manifest_path)
        if declared is None:
            return None, EXIT_USAGE
    else:
        manifest_path = None
    result = scan_directory(root, declared)
    if not result.found_anything and declared is None:
        print(
            "error: nothing to scan: no supported agent configuration found "
            f"in {root} and no manifest declared",
            file=sys.stderr,
        )
        for src in result.sources:
            print(f"  detected but not supported: {src.path} ({src.kind})", file=sys.stderr)
        return None, EXIT_USAGE
    ctx = Context(declared=declared, observed=result.observed)
    try:
        report = engine.run(result.observed, _resolve_checks(args.check), ctx, result.sources)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None, EXIT_USAGE
    return (report, manifest_path), EXIT_OK


def cmd_scan(args: argparse.Namespace) -> int:
    got, code = _scan_report(args)
    if got is None:
        return code
    report, manifest_path = got
    # SARIF anchor: the first scanned file, relative to the scanned directory.
    anchor = next((s.path for s in report.sources if s.supported), manifest_path or "agent-assurance.yaml")
    _emit(report, args, anchor)
    return _gate(report, args.fail_on)


def cmd_attest(args: argparse.Namespace) -> int:
    """Write an in-toto statement; the exit code still reports the gate so a
    pipeline can archive the evidence *and* stop on a broken promise."""
    got, code = _scan_report(args)
    if got is None:
        return code
    report, manifest_path = got
    statement = attest.build(args.directory, manifest_path, report)
    text = attest.to_json(statement)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
        subjects = ", ".join(s["name"] for s in statement["subject"])
        print(f"wrote attestation to {args.output} (subjects: {subjects})", file=sys.stderr)
    else:
        print(text)
    return _gate(report, args.fail_on)


def cmd_diff(args: argparse.Namespace) -> int:
    for d in (args.base, args.head):
        if not os.path.isdir(d):
            print(f"error: not a directory: {d}", file=sys.stderr)
            return EXIT_USAGE
    # The head side's policy governs the comparison (it is what the PR ships).
    if _apply_policy(args, args.head) != EXIT_OK:
        return EXIT_USAGE
    try:
        result = diff.compute(args.base, args.head, args.manifest)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if result is None:
        print("error: nothing to compare: no agent configuration or manifest on either side", file=sys.stderr)
        return EXIT_USAGE

    if args.format in ("md", "markdown"):
        output = diff.to_markdown(result)
    elif args.format == "json":
        output = json.dumps(diff.to_dict(result), indent=2, ensure_ascii=False)
    elif args.format == "html":
        output = diff.to_html(result, theme=getattr(args, "theme", "auto"))
    else:
        anchor = next((s.path for s in result.head.sources if s.supported), "agent-assurance.yaml")
        output = reports.to_sarif(result.head, anchor, result.baseline_states())
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(output)
        print(f"wrote {args.format} diff to {args.output}", file=sys.stderr)
    else:
        print(output)

    if args.fail_on_delta and result.regressed:
        return EXIT_GATE
    return _gate(result.head, args.fail_on)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent-assurance",
        description="Transparent, framework-agnostic assurance checks for AI agents.",
    )
    p.add_argument("--version", action="version", version=f"agent-assurance {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    pv = sub.add_parser("validate", help="validate a manifest or a policy file")
    pv.add_argument(
        "file",
        nargs="?",
        default=None,
        help="manifest (agent-assurance/v1) or policy file; a policy is recognised by its apiVersion",
    )
    pv.add_argument("--policy", default=None, help="validate this policy file explicitly")
    pv.set_defaults(func=cmd_validate)

    pc = sub.add_parser("check", help="run assurance checks")
    pc.add_argument("check", help="check name (e.g. blast-radius) or 'all'")
    pc.add_argument("manifest")
    pc.add_argument("--format", choices=list(_FORMATS.keys()), default="md")
    pc.add_argument("--theme", choices=["auto", "dark", "light"], default="auto", help="html only")
    pc.add_argument("--output", "-o", default=None, help="write report to a file")
    pc.add_argument("--policy", default=None, help="organisation policy file (default: agent-assurance.policy.yaml next to the manifest)")
    pc.add_argument(
        "--fail-on",
        choices=["fail", "review"],
        default="fail",
        help="exit 1 on FAIL (default) or on REVIEW too",
    )
    pc.set_defaults(func=cmd_check)

    ps = sub.add_parser(
        "scan",
        help="observe what the repo's agent configuration grants and verify it "
        "against the declared manifest, if any",
    )
    ps.add_argument("directory", nargs="?", default=".")
    ps.add_argument("--manifest", "-m", default=None, help="declared manifest (the promise)")
    ps.add_argument("--check", default="all", help="check id/alias or 'all'")
    ps.add_argument("--format", choices=list(_FORMATS.keys()), default="md")
    ps.add_argument("--theme", choices=["auto", "dark", "light"], default="auto", help="html only")
    ps.add_argument("--output", "-o", default=None, help="write report to a file")
    ps.add_argument("--fail-on", choices=["fail", "review"], default="fail")
    ps.add_argument("--policy", default=None, help="organisation policy file (default: <dir>/agent-assurance.policy.yaml)")
    ps.set_defaults(func=cmd_scan)

    pa = sub.add_parser("attest", help="write an in-toto statement (evidence) for what the config grants at this commit")
    pa.add_argument("directory", nargs="?", default=".")
    pa.add_argument("--manifest", "-m", default=None)
    pa.add_argument("--check", default="all")
    pa.add_argument("--output", "-o", default=None)
    pa.add_argument("--fail-on", choices=["fail", "review"], default="fail")
    pa.add_argument("--policy", default=None)
    pa.set_defaults(func=cmd_attest)

    pd = sub.add_parser("diff", help="compare two checked-out trees: what did this change do to the agent's reach and promise?")
    pd.add_argument("base")
    pd.add_argument("head")
    pd.add_argument("--manifest", "-m", default=None, help="declared manifest to hold both sides against (default: each side's own)")
    pd.add_argument("--format", choices=list(_FORMATS.keys()), default="md")
    pd.add_argument("--theme", choices=["auto", "dark", "light"], default="auto", help="html only")
    pd.add_argument("--output", "-o", default=None)
    pd.add_argument("--fail-on", choices=["fail", "review"], default="fail", help="gate on the head verdict")
    pd.add_argument("--fail-on-delta", action="store_true", help="also gate when reach grows, the band rises or the promise breaks")
    pd.add_argument("--policy", default=None, help="organisation policy file (default: <head>/agent-assurance.policy.yaml)")
    pd.set_defaults(func=cmd_diff)
    return p


def main(argv: list[str] | None = None) -> int:
    """Always returns an int; argparse usage errors surface as exit 2 too."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
