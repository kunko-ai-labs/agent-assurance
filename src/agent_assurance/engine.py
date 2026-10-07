"""Assurance engine: runs checks over a manifest and aggregates the verdict.

The engine is intentionally thin. It is shared by the CLI and the GitHub Action,
so both produce identical results. The overall verdict is the worst status of
any check (FAIL > REVIEW > PASS).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import grade as _grade
from . import policy as _policy
from .checks import ALL_CHECKS
from .checks.base import CheckResult, Context, Status
from .manifest import Manifest
from .scan.base import Source

# Ordering for "worst wins" aggregation.
_SEVERITY = {Status.PASS: 0, Status.REVIEW: 1, Status.FAIL: 2}


@dataclass
class AssuranceReport:
    manifest: Manifest
    results: list[CheckResult] = field(default_factory=list)
    # Present when the report came from `scan`: what was looked at.
    sources: list[Source] = field(default_factory=list)
    declared: Manifest | None = None
    # {"name", "path", "sha256"} of the policy that produced the verdict; None = defaults.
    policy: dict | None = None

    @property
    def verdict(self) -> Status:
        worst = Status.PASS
        for r in self.results:
            if _SEVERITY[r.status] > _SEVERITY[worst]:
                worst = r.status
        return worst

    @property
    def passed(self) -> bool:
        return self.verdict != Status.FAIL

    @property
    def grade(self) -> _grade.Grade | None:
        """Overall A-F grade for this run; None when no pillar was assessed."""
        return _grade.grade_results(self.results)


def run(
    manifest: Manifest,
    check_ids: list[str] | None = None,
    ctx: Context | None = None,
    sources: list[Source] | None = None,
) -> AssuranceReport:
    """Run the requested checks (or all of them) against a manifest.

    Checks that need inputs the caller did not provide (e.g. AA-002 needs a
    declared and an observed manifest) are skipped, not failed: a plain
    `check` on one manifest is a complete, valid run.
    """
    ctx = ctx or Context()
    selected = check_ids or list(ALL_CHECKS.keys())
    results: list[CheckResult] = []
    for cid in selected:
        check_cls = ALL_CHECKS.get(cid)
        if check_cls is None:
            raise KeyError(f"unknown check id: {cid}")
        check = check_cls()
        if not check.applicable(ctx):
            continue
        results.append(check.run(manifest, ctx))
    return AssuranceReport(
        manifest=manifest,
        results=results,
        sources=list(sources or []),
        declared=ctx.declared,
        policy=_policy.describe(),
    )
