"""Check framework: the base types every assurance check implements.

A check consumes a Manifest and returns a CheckResult. Checks map to standards
(primarily OWASP Agentic Top 10 / ASI; APTS where the control genuinely
transfers from the pentest domain; and, since issue #53, the compliance
frameworks a CISO actually gets asked about: EU AI Act, NIST AI RMF,
ISO/IEC 42001 and the OWASP LLM Top 10). Keeping this contract tiny is what
lets the GitHub Action stay a thin wrapper over a growing set of checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

from ..manifest import Manifest


class Status(str, Enum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    FAIL = "FAIL"


# The closed vocabulary for StandardRef.framework. A typo'd framework name in
# a new check must fail loudly (the test in test_compliance_mapping.py iterates
# the whole registry), not silently produce a report column nobody recognizes.
KNOWN_FRAMEWORKS: frozenset[str] = frozenset(
    {
        # Compliance frameworks (issue #53).
        "EU-AI-ACT",  # EU Artificial Intelligence Act (Regulation (EU) 2024/1689)
        "NIST-AI-RMF",  # NIST AI Risk Management Framework (AI 100-1)
        "ISO-42001",  # ISO/IEC 42001 AI management system, Annex A controls
        "OWASP-LLM",  # OWASP Top 10 for LLM Applications (2025 edition)
        # Existing mappings.
        "OWASP-ASI",  # OWASP Agentic AI Top 10 (security initiative)
        "OWASP-APTS",  # OWASP Agentic Pentesting Standard (transferred domain)
        "arXiv",  # published-paper basis, when a check implements one
    }
)


@dataclass
class StandardRef:
    """A mapping from a check to a published standard control.

    `relation` is honest about strength:
      - "maps"        : the control is directly about this (business agents)
      - "adapted"     : transferred from a neighbouring domain (e.g. APTS pentest)

    The full rationale for each check's mappings — why a ref is "maps" rather
    than "adapted", and where gaps are deliberately left unmapped — lives in
    docs/compliance-mapping.md. Leave a check unmapped rather than inventing a
    mapping.
    """

    framework: str  # one of KNOWN_FRAMEWORKS
    control: str  # "ASI08", "APTS-SC-020", "Art. 14", "MAP-5", "A.5.2", "LLM08"
    relation: str = "maps"


@dataclass
class Location:
    """Where a finding is anchored in the repo (for SARIF and humans)."""

    path: str
    line: int = 1


@dataclass
class Context:
    """What a check may look at besides the manifest it runs on.

    `declared` is the hand-written manifest (the promise). `observed` is what
    the scanners found in the repo's configuration. Both are None when the CLI
    runs a plain `check` on a single manifest.
    """

    declared: Manifest | None = None
    observed: Manifest | None = None


@dataclass
class CheckResult:
    check_id: str
    title: str
    status: Status
    summary: str
    details: list[str] = field(default_factory=list)
    standards: list[StandardRef] = field(default_factory=list)
    # Machine-readable extras for JSON/SARIF consumers.
    data: dict = field(default_factory=dict)
    # Anchors for the finding; empty means "the manifest as a whole".
    locations: list[Location] = field(default_factory=list)


class Check:
    """Base class. Subclasses set id/title/standards and implement run()."""

    check_id: str = "AA-000"
    title: str = "Unnamed check"
    standards: ClassVar[list[StandardRef]] = []

    def applicable(self, ctx: Context) -> bool:
        """Whether this check makes sense with the inputs at hand."""
        return True

    def run(self, manifest: Manifest, ctx: Context) -> CheckResult:  # pragma: no cover
        raise NotImplementedError
