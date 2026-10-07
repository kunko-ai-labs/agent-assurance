"""Compliance mapping tests (issue #53).

Locks in three things:
1. The framework vocabulary is closed: every StandardRef used by any
   registered check must belong to KNOWN_FRAMEWORKS, so a typo in a new
   check fails here instead of silently producing an unrecognised column.
2. The expected compliance mappings for AA-001 and AA-002 (the rationale
   lives in docs/compliance-mapping.md).
3. The coverage matrix: built once in coverage.py, rendered identically in
   markdown and JSON, with gaps explicit (em dash / empty list), never hidden.
"""

from __future__ import annotations

import pathlib

from agent_assurance import engine
from agent_assurance.checks import ALL_CHECKS
from agent_assurance.checks.base import (
    KNOWN_FRAMEWORKS,
    CheckResult,
    StandardRef,
    Status,
)
from agent_assurance.coverage import FRAMEWORK_ORDER, cell_text, coverage_matrix
from agent_assurance.manifest import Manifest
from agent_assurance.reports.json_report import to_dict
from agent_assurance.reports.markdown import to_markdown

EXAMPLES = pathlib.Path(__file__).resolve().parents[1] / "examples"

ISSUE_53_FRAMEWORKS = {"EU-AI-ACT", "NIST-AI-RMF", "ISO-42001", "OWASP-LLM"}


def _results_from_registry() -> list[CheckResult]:
    """CheckResults carrying the real standards each check declares."""
    return [
        CheckResult(
            check_id=cls.check_id,
            title=cls.title,
            status=Status.PASS,
            summary="fixture",
            standards=list(cls.standards),
        )
        for cls in ALL_CHECKS.values()
    ]


def _refs(check_id: str) -> list[StandardRef]:
    return list(ALL_CHECKS[check_id].standards)


# --- Vocabulary -------------------------------------------------------------


def test_issue_53_frameworks_are_in_the_vocabulary():
    assert ISSUE_53_FRAMEWORKS <= KNOWN_FRAMEWORKS


def test_every_framework_used_by_every_check_is_known():
    """A typo'd framework name in a new check must fail here, loudly."""
    unknown = {
        (cls.check_id, s.framework)
        for cls in ALL_CHECKS.values()
        for s in cls.standards
        if s.framework not in KNOWN_FRAMEWORKS
    }
    assert unknown == set()


def test_matrix_columns_cover_the_whole_vocabulary():
    assert set(FRAMEWORK_ORDER) == set(KNOWN_FRAMEWORKS)


# --- AA-001 mappings ---------------------------------------------------------


def test_blast_radius_compliance_mappings():
    refs = {(s.framework, s.control, s.relation) for s in _refs("AA-001")}
    assert ("OWASP-LLM", "LLM08", "maps") in refs
    assert ("EU-AI-ACT", "Art. 14", "maps") in refs
    assert ("NIST-AI-RMF", "MAP-5", "maps") in refs
    assert ("ISO-42001", "A.5.2", "maps") in refs
    # Pre-existing mappings must survive.
    assert ("OWASP-ASI", "ASI08", "maps") in refs
    assert ("OWASP-APTS", "APTS-SC-020", "adapted") in refs


# --- AA-002 mappings ---------------------------------------------------------


def test_declared_vs_observed_compliance_mappings():
    refs = {(s.framework, s.control, s.relation) for s in _refs("AA-002")}
    assert ("OWASP-LLM", "LLM07", "maps") in refs
    # Normalised to the issue #53 vocabulary (was "EU-AI-Act"/"Art.12").
    assert ("EU-AI-ACT", "Art. 12", "adapted") in refs
    assert ("NIST-AI-RMF", "MEASURE-3", "maps") in refs
    assert ("ISO-42001", "A.9.2", "maps") in refs
    assert ("OWASP-ASI", "ASI03", "maps") in refs
    assert ("OWASP-ASI", "ASI04", "maps") in refs


# --- Matrix ------------------------------------------------------------------


def test_matrix_has_every_framework_per_row_and_explicit_gaps():
    rows = {r.check_id: r for r in coverage_matrix(_results_from_registry())}
    assert set(rows) == set(ALL_CHECKS)
    for row in rows.values():
        assert list(row.mappings) == list(FRAMEWORK_ORDER)
    # Nothing maps to arXiv yet — the gap is explicit, not an omission.
    assert rows["AA-001"].mappings["arXiv"] == []
    assert rows["AA-002"].mappings["arXiv"] == []
    # ... and AA-002 has no OWASP-APTS mapping either.
    assert rows["AA-002"].mappings["OWASP-APTS"] == []
    # Populated cells carry the real refs.
    assert [s.control for s in rows["AA-001"].mappings["EU-AI-ACT"]] == ["Art. 14"]


def test_cell_text_renders_controls_and_honest_gaps():
    assert cell_text([]) == "\u2014"
    aa1 = _refs("AA-001")
    assert "Art. 14" in cell_text([s for s in aa1 if s.framework == "EU-AI-ACT"])
    assert "(adapted)" in cell_text([s for s in aa1 if s.framework == "OWASP-APTS"])
    assert "(adapted)" not in cell_text([s for s in aa1 if s.framework == "EU-AI-ACT"])


# --- Renderers ----------------------------------------------------------------


def test_markdown_report_contains_coverage_matrix():
    m = Manifest.from_file(str(EXAMPLES / "safe-agent.yaml"))
    md = to_markdown(engine.run(m, ["AA-001"]))
    assert "### \U0001f4ca Coverage matrix" in md
    assert "| Check | EU-AI-ACT | NIST-AI-RMF | ISO-42001 | OWASP-LLM |" in md
    assert "AA-001 \u2014 Blast Radius" in md
    assert "Art. 14" in md
    # The arXiv gap is visible as an em dash, not silently dropped.
    assert "| \u2014 |" in md
    assert "compliance-mapping.md" in md


def test_json_report_contains_coverage_matrix():
    m = Manifest.from_file(str(EXAMPLES / "safe-agent.yaml"))
    cov = to_dict(engine.run(m, ["AA-001"]))["coverage"]
    assert cov["frameworks"] == list(FRAMEWORK_ORDER)
    (row,) = cov["rows"]
    assert row["check_id"] == "AA-001"
    assert set(row["mappings"]) == set(FRAMEWORK_ORDER)
    assert row["mappings"]["EU-AI-ACT"] == [{"control": "Art. 14", "relation": "maps"}]
    assert row["mappings"]["OWASP-APTS"] == [{"control": "APTS-SC-020", "relation": "adapted"}]
    assert row["mappings"]["arXiv"] == []


def test_matrix_is_additive_verdict_semantics_unchanged():
    """Issue #53 must not change check behaviour or verdict aggregation."""
    m = Manifest.from_file(str(EXAMPLES / "safe-agent.yaml"))
    report = engine.run(m, ["AA-001"])
    assert report.verdict is Status.PASS
    assert report.results[0].status is Status.PASS
