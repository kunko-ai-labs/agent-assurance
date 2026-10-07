"""Compliance coverage matrix: which checks map to which frameworks.

Both the markdown and the JSON renderers show the same matrix, so it is built
once, here, from the checks that actually ran (report.results). A framework
with no refs for a check is an explicit gap, rendered as an empty list (JSON)
or an em-dash cell (markdown) — never silently omitted. The point is to make
coverage *visible*, including where it is missing: a CISO can see at a glance
which compliance frameworks this run speaks to and which it does not.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .checks.base import KNOWN_FRAMEWORKS, CheckResult, StandardRef

# Canonical column order: the four compliance frameworks from issue #53 first
# (in the order the issue lists them), then the pre-existing ones.
FRAMEWORK_ORDER: tuple[str, ...] = (
    "EU-AI-ACT",
    "NIST-AI-RMF",
    "ISO-42001",
    "OWASP-LLM",
    "OWASP-ASI",
    "OWASP-APTS",
    "arXiv",
)

assert set(FRAMEWORK_ORDER) == set(KNOWN_FRAMEWORKS), (
    "matrix columns must cover the whole framework vocabulary"
)


@dataclass
class CoverageRow:
    """One row of the matrix: a check and its refs per framework.

    `mappings` has an entry for EVERY framework in FRAMEWORK_ORDER; an empty
    list is an explicit gap (the check says nothing about that framework).
    """

    check_id: str
    title: str
    status: str
    mappings: dict[str, list[StandardRef]] = field(default_factory=dict)


def coverage_matrix(results: list[CheckResult]) -> list[CoverageRow]:
    """Build the framework x checks matrix from the checks that ran."""
    rows: list[CoverageRow] = []
    for r in results:
        mappings: dict[str, list[StandardRef]] = {fw: [] for fw in FRAMEWORK_ORDER}
        for s in r.standards:
            if s.framework in mappings:
                mappings[s.framework].append(s)
            # A framework outside the vocabulary is a bug in the check, not in
            # the matrix: the test in test_compliance_mapping.py fails on it.
        rows.append(
            CoverageRow(
                check_id=r.check_id,
                title=r.title,
                status=r.status.value,
                mappings=mappings,
            )
        )
    return rows


def cell_text(refs: list[StandardRef]) -> str:
    """Render one matrix cell: mapped control(s), or an em dash for a gap.

    The "(adapted)" suffix keeps the markdown table honest the same way the
    per-check "Standards:" line already does.
    """
    if not refs:
        return "\u2014"
    return ", ".join(r.control + ("" if r.relation == "maps" else f" ({r.relation})") for r in refs)
