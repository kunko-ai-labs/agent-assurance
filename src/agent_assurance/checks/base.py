"""Check framework: the base types every assurance check implements.

A check consumes a Manifest and returns a CheckResult. Checks map to standards
(primarily OWASP Agentic Top 10 / ASI; APTS where the control genuinely
transfers from the pentest domain). Keeping this contract tiny is what lets the
GitHub Action stay a thin wrapper over a growing set of checks.
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


@dataclass
class StandardRef:
    """A mapping from a check to a published standard control.

    `relation` is honest about strength:
      - "maps"        : the control is directly about this (business agents)
      - "adapted"     : transferred from a neighbouring domain (e.g. APTS pentest)
    """

    framework: str  # "OWASP-ASI", "OWASP-APTS", "arXiv"
    control: str  # "ASI08", "APTS-SC-020", "2609.07395"
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
    # A mandatory check failing caps the overall grade (see grade.py): its
    # FAIL must never be averaged away by good scores elsewhere. Opt-in per
    # check; False by default so new checks stay non-capping until the author
    # decides the failure is load-bearing.
    mandatory: ClassVar[bool] = False

    def applicable(self, ctx: Context) -> bool:
        """Whether this check makes sense with the inputs at hand."""
        return True

    def run(self, manifest: Manifest, ctx: Context) -> CheckResult:  # pragma: no cover
        raise NotImplementedError
