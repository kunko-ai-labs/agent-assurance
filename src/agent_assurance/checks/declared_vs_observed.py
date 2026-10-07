"""Declared vs Observed check (AA-002).

The manifest is a promise: "this agent may read the CRM and nothing else".
The scan is what the repository's configuration actually grants. This check
fails when the configuration grants a class of capability the promise did not
include, and refuses to say "promise kept" while anything is UNKNOWN.

It compares by *capability class* (read / write / delete / execute /
external_send / financial) and by data class, not by tool name: a promise is
about what kind of harm is possible, not about how a tool is spelled.

Maps to OWASP Agentic Top 10 ASI03 (Identity & privilege abuse: the agent
holds more than it should) and ASI04 (Agentic supply chain: a new server
quietly widens reach). Adapted from EU AI Act art. 12 (record-keeping that lets
an auditor reconstruct what the system could do at a point in time): this
verdict, per commit, is that record for capabilities.

Compliance mappings (rationale in docs/compliance-mapping.md):
  - OWASP LLM07 (Insecure Plugin Design): each tool/plugin's observed grants
    are verified against its declared grant — catching excessive permissions.
  - NIST AI RMF MEASURE-3: a per-commit risk-tracking mechanism that detects
    capability drift.
  - ISO/IEC 42001 A.9.2 (intended use): the declared manifest states the
    intended use; the check verifies the observed configuration stays within it.
"""

from __future__ import annotations

from typing import ClassVar

from .. import policy
from ..manifest import DataClass, Manifest, ToolAccess
from .base import Check, CheckResult, Context, Location, StandardRef, Status

# Undeclared capabilities in these classes break the promise outright.
_BREAKING_ACCESS = {
    ToolAccess.WRITE,
    ToolAccess.DELETE,
    ToolAccess.EXECUTE,
    ToolAccess.EXTERNAL_SEND,
    ToolAccess.FINANCIAL,
}
# Undeclared access to these data classes breaks the promise outright.
_BREAKING_DATA = {
    DataClass.PII,
    DataClass.HEALTH,
    DataClass.FINANCIAL,
    DataClass.CREDENTIAL,
}


def _loc(source: str | None) -> Location | None:
    if not source:
        return None
    path, _, line = source.rpartition(":")
    try:
        return Location(path=path or source, line=int(line))
    except ValueError:
        return Location(path=source, line=1)


class DeclaredVsObservedCheck(Check):
    check_id = "AA-002"
    title = "Declared vs Observed"
    standards: ClassVar[list[StandardRef]] = [
        StandardRef("OWASP-ASI", "ASI03", "maps"),
        StandardRef("OWASP-ASI", "ASI04", "maps"),
        StandardRef("EU-AI-ACT", "Art. 12", "adapted"),
        StandardRef("OWASP-LLM", "LLM07", "maps"),
        StandardRef("NIST-AI-RMF", "MEASURE-3", "maps"),
        StandardRef("ISO-42001", "A.9.2", "maps"),
    ]

    def applicable(self, ctx: Context) -> bool:
        return ctx.declared is not None and ctx.observed is not None

    def run(self, manifest: Manifest, ctx: Context) -> CheckResult:
        declared = ctx.declared
        observed = ctx.observed
        assert declared is not None and observed is not None
        pol = policy.current().promise
        breaking_access = set(pol.breaking_access)
        breaking_data = set(pol.breaking_data)

        declared_access = {t.type for t in declared.tools}
        declared_data = {d.type for d in declared.data}
        declared_systems = {t.system for t in declared.tools if t.system} | {
            s for d in declared.data for s in d.systems
        }

        broken: list[str] = []
        review: list[str] = []
        unknown: list[str] = []
        locations: list[Location] = []

        def note(bucket: list[str], msg: str, source: str | None) -> None:
            bucket.append(f"{msg} ({source})" if source else msg)
            loc = _loc(source)
            if loc and loc not in locations:
                locations.append(loc)

        broken_systems: set[str] = set()

        # 1. Undeclared capability classes.
        for t in observed.tools:
            if t.type is ToolAccess.UNKNOWN:
                note(unknown, f"`{t.name}` could not be classified", t.source)
                continue
            if t.type not in declared_access:
                bucket = broken if t.type in breaking_access and not t.inferred else review
                suffix = " (class inferred from its name — verify)" if t.inferred else ""
                note(bucket, f"`{t.name}` grants **{t.type.value}**, not declared{suffix}", t.source)
                if bucket is broken and t.system:
                    broken_systems.add(t.system)

        # 2. Autonomy is a promise too: L0-L2 means a human approves actions.
        #    A host rule that auto-approves a non-read tool removes that human.
        if declared.autonomy <= pol.max_autonomy_with_human:
            for t in observed.tools:
                if t.approval != "auto" or t.type not in breaking_access:
                    continue
                if t.scoped:
                    note(review, f"`{t.name}` is auto-approved (scoped) under declared autonomy L{declared.autonomy}", t.source)
                    continue
                note(
                    broken,
                    f"`{t.name}` runs **without human approval**, but declared autonomy is L{declared.autonomy}",
                    t.source,
                )
                if t.system:
                    broken_systems.add(t.system)

        # 3. Undeclared data classes: sensitive ones break the promise; the
        #    rest are extra reach, reported only for systems not already broken.
        undeclared_data = [d for d in observed.data if d.type not in declared_data]
        for d in undeclared_data:
            if d.type in breaking_data:
                systems = ", ".join(d.systems) or "unspecified"
                note(broken, f"access to **{d.type.value}** data ({systems}), not declared", d.source)
                broken_systems.update(d.systems)
        for d in undeclared_data:
            if d.type not in breaking_data and not set(d.systems) <= broken_systems:
                systems = ", ".join(d.systems) or "unspecified"
                note(review, f"access to **{d.type.value}** data ({systems}), not declared", d.source)

        # 4. Extra reach: declared class, undeclared system. Only worth a line
        #    when that system is not already reported as breaking the promise.
        for t in observed.tools:
            if (
                t.type is not ToolAccess.UNKNOWN
                and t.type in declared_access
                and t.system
                and t.system not in declared_systems
                and t.system not in broken_systems
            ):
                note(review, f"`{t.name}` reaches system `{t.system}`, not declared", t.source)

        if broken:
            status = Status.FAIL
            summary = f"Promise broken: {len(broken)} undeclared capabilit{'y' if len(broken) == 1 else 'ies'}"
        elif review or unknown:
            status = Status.REVIEW
            summary = "Promise not verifiable" if unknown and not review else "Promise stretched: undeclared reach"
        else:
            status = Status.PASS
            summary = "Promise kept: observed capabilities are within the declaration"

        promise = ", ".join(sorted(a.value for a in declared_access)) or "no tools"
        details = [f"Declared: {promise}; data: {', '.join(sorted(d.value for d in declared_data)) or 'none'}"]
        details += [f"BROKEN — {m}" for m in broken]
        details += [f"REVIEW — {m}" for m in review]
        details += [f"UNKNOWN — {m}" for m in unknown]

        return CheckResult(
            check_id=self.check_id,
            title=self.title,
            status=status,
            summary=summary,
            details=details,
            standards=self.standards,
            data={
                "declared_access": sorted(a.value for a in declared_access),
                "observed_access": sorted({t.type.value for t in observed.tools}),
                "broken": broken,
                "review": review,
                "unknown": unknown,
            },
            locations=locations,
        )
