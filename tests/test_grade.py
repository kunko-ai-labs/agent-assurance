"""Tests for the A-F grade (issue #52).

The grade is a pure function of check results: no LLM, no clock, no
randomness. These tests pin the band boundaries, the pillar arithmetic, the
mandatory-fail cap, and determinism, plus the three surfaces the grade must
reach: the CLI summary, the markdown header, and the JSON report.
"""

from __future__ import annotations

import pathlib

import pytest

from agent_assurance import cli, engine
from agent_assurance import grade as grade_mod
from agent_assurance.checks.base import CheckResult, Status
from agent_assurance.grade import (
    MANDATORY_FAIL_CAP,
    apply_cap,
    band_for_score,
    grade_results,
)
from agent_assurance.manifest import Manifest
from agent_assurance.reports import json_report, markdown

EXAMPLES = pathlib.Path(__file__).resolve().parents[1] / "examples"


def _result(check_id: str, status: Status, data: dict | None = None) -> CheckResult:
    return CheckResult(
        check_id=check_id, title=check_id, status=status, summary="", data=data or {}
    )


def _aa1(status: Status, band: str | None = "LOW", unknowns: int = 0) -> CheckResult:
    data: dict = {}
    if band is not None:
        data["band"] = band
    if unknowns:
        data["unknown_capabilities"] = [f"mcp__srv__tool{i}" for i in range(unknowns)]
    return _result("AA-001", status, data)


def _aa2(status: Status, broken: int = 0, review: int = 0, unknown: int = 0) -> CheckResult:
    return _result(
        "AA-002",
        status,
        {
            "broken": [f"b{i}" for i in range(broken)],
            "review": [f"r{i}" for i in range(review)],
            "unknown": [f"u{i}" for i in range(unknown)],
        },
    )


# --- band boundaries --------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100.0, "A"),
        (90.0, "A"),  # lower bound inclusive
        (89.9, "B"),
        (75.0, "B"),
        (74.9, "C"),
        (60.0, "C"),
        (59.9, "D"),
        (40.0, "D"),
        (39.9, "F"),
        (0.0, "F"),
    ],
)
def test_band_boundaries(score, expected):
    assert band_for_score(score) == expected


# --- pillar arithmetic ------------------------------------------------------


def test_all_pass_is_an_a():
    g = grade_results([_aa1(Status.PASS, "LOW"), _aa2(Status.PASS)])
    assert g is not None
    assert (g.letter, g.score) == ("A", 100.0)
    assert g.capped is False
    assert g.disclaimer == "diagnostic, not certification"


def test_medium_blast_radius_is_a_b():
    # 0.6 * 75 + 0.4 * 100 = 85
    g = grade_results([_aa1(Status.PASS, "MEDIUM"), _aa2(Status.PASS)])
    assert g is not None
    assert (g.letter, g.score) == ("B", 85.0)


def test_high_blast_radius_is_a_c():
    # 0.6 * 40 + 0.4 * 100 = 64
    g = grade_results([_aa1(Status.REVIEW, "HIGH"), _aa2(Status.PASS)])
    assert g is not None
    assert (g.letter, g.score) == ("C", 64.0)
    assert g.capped is False  # REVIEW of a mandatory check does not engage the cap


def test_unknown_capabilities_penalise_impact():
    # impact = 75 - 2*10 = 55; overall = 0.6*55 + 0.4*100 = 73 -> C
    g = grade_results([_aa1(Status.REVIEW, "MEDIUM", unknowns=2), _aa2(Status.PASS)])
    assert g is not None
    assert (g.letter, g.score) == ("C", 73.0)
    assert "unknown" in g.pillars[0].detail


def test_stretched_promise_scores_between_kept_and_broken():
    # promise = 70 - 10 = 60; overall = 0.6*100 + 0.4*60 = 84 -> B
    g = grade_results([_aa1(Status.PASS, "LOW"), _aa2(Status.REVIEW, review=1)])
    assert g is not None
    assert (g.letter, g.score) == ("B", 84.0)


def test_broken_promise_scores_zero():
    g = grade_results([_aa1(Status.PASS, "LOW"), _aa2(Status.FAIL, broken=2)])
    assert g is not None
    assert g.pillars[1].score == 0.0
    # 0.6*100 + 0.4*0 = 60 -> C, and the mandatory-fail cap engages
    assert g.letter == "C"
    assert g.capped is True
    assert g.capped_by == ("AA-002",)


def test_status_fallback_when_check_data_is_missing():
    g = grade_results([_aa1(Status.PASS, band=None), _aa2(Status.PASS)])
    assert g is not None
    assert g.pillars[0].score == 100.0
    assert "status" in g.pillars[0].detail


# --- mandatory-fail cap ------------------------------------------------------


def test_mandatory_fail_caps_the_grade():
    # 0.6*0 + 0.4*100 = 40 -> D; AA-001 is mandatory so the cap engages.
    g = grade_results([_aa1(Status.FAIL, "CRITICAL"), _aa2(Status.PASS)])
    assert g is not None
    assert g.capped is True
    assert g.capped_by == ("AA-001",)
    assert g.letter_before_cap == "D"
    assert g.letter == "D"  # already at/below the cap: the letter stands


def test_cap_pulls_a_high_raw_grade_down_to_c():
    # Synthetic: a mandatory FAIL whose pillar data still scores well. The cap
    # is status-driven, so it applies regardless of the pillar arithmetic.
    g = grade_results([_aa1(Status.FAIL, "LOW"), _aa2(Status.PASS)])
    assert g is not None
    assert g.letter_before_cap == "A"
    assert g.letter == MANDATORY_FAIL_CAP == "C"
    assert g.capped is True


@pytest.mark.parametrize(
    ("letter", "capped_by", "expected"),
    [
        ("A", ("AA-001",), "C"),
        ("B", ("AA-001", "AA-002"), "C"),
        ("C", ("AA-002",), "C"),
        ("D", ("AA-001",), "D"),
        ("F", ("AA-001",), "F"),
        ("A", (), "A"),  # no failing mandatory check: untouched
    ],
)
def test_apply_cap(letter, capped_by, expected):
    assert apply_cap(letter, capped_by) == expected


def test_non_mandatory_fail_does_not_cap():
    # AA-999 is not a registered check, so it cannot be mandatory and its
    # pillar is unmapped: the grade stays A.
    g = grade_results([_aa1(Status.PASS, "LOW"), _result("AA-999", Status.FAIL)])
    assert g is not None
    assert g.letter == "A"
    assert g.capped is False


# --- skipped checks ----------------------------------------------------------


def test_skipped_check_leaves_its_pillar_unassessed():
    # AA-002 skipped (plain `check` on one manifest): only impact counts.
    g = grade_results([_aa1(Status.PASS, "MEDIUM")])
    assert g is not None
    assert [p.pillar for p in g.pillars] == ["impact"]
    assert (g.letter, g.score) == ("B", 75.0)


def test_no_assessed_pillars_means_no_grade():
    assert grade_results([]) is None
    assert grade_results([_result("AA-999", Status.PASS)]) is None


# --- determinism -------------------------------------------------------------


def test_deterministic_same_input_same_grade():
    results = [
        _aa1(Status.REVIEW, "MEDIUM", unknowns=1),
        _aa2(Status.REVIEW, review=2, unknown=1),
    ]
    first = grade_results(results)
    assert first is not None
    for _ in range(50):
        assert grade_results(results) == first


def test_deterministic_regardless_of_result_order():
    a = grade_results([_aa1(Status.PASS, "HIGH"), _aa2(Status.REVIEW, review=1)])
    b = grade_results([_aa2(Status.REVIEW, review=1), _aa1(Status.PASS, "HIGH")])
    assert a == b


def test_no_time_or_randomness_imports():
    # The module must not import anything time- or randomness-dependent.
    source = pathlib.Path(grade_mod.__file__).read_text(encoding="utf-8")
    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    for banned in ("datetime", "random", "time", "uuid", "secrets"):
        assert not any(banned in line for line in import_lines), import_lines


# --- integration: real runs --------------------------------------------------


def _run_example(name: str) -> engine.AssuranceReport:
    manifest = Manifest.from_file(str(EXAMPLES / name))
    return engine.run(manifest)


def test_safe_agent_grades_a():
    report = _run_example("safe-agent.yaml")
    assert report.grade is not None
    assert report.grade.letter == "A"
    assert report.grade.capped is False


def test_high_agent_grades_d():
    report = _run_example("high-agent.yaml")
    assert report.grade is not None
    assert report.grade.letter == "D"


def test_dangerous_agent_grades_f_capped():
    report = _run_example("dangerous-agent.yaml")
    g = report.grade
    assert g is not None
    assert g.letter == "F"
    assert g.capped is True
    assert g.capped_by == ("AA-001",)


# --- surfaces ----------------------------------------------------------------


def test_markdown_header_shows_grade_and_disclaimer():
    report = _run_example("safe-agent.yaml")
    md = markdown.to_markdown(report)
    assert "**Grade:** `A` (100/100)" in md
    assert "diagnostic, not certification" in md
    assert "<summary>Grade breakdown</summary>" in md
    assert "| Impact | 60% | 100/100 |" in md


def test_markdown_shows_cap_note():
    report = _run_example("dangerous-agent.yaml")
    md = markdown.to_markdown(report)
    assert "**Grade:** `F` (0/100)" in md
    assert "Mandatory check AA-001 failed" in md


def test_json_report_carries_grade_field():
    report = _run_example("safe-agent.yaml")
    payload = json_report.to_dict(report)
    g = payload["grade"]
    assert g["letter"] == "A"
    assert g["score"] == 100.0
    assert g["capped"] is False
    assert g["disclaimer"] == "diagnostic, not certification"
    assert [p["id"] for p in g["pillars"]] == ["impact"]


def test_cli_summary_includes_grade(capsys):
    code = cli.main(["check", "all", str(EXAMPLES / "safe-agent.yaml")])
    assert code == cli.EXIT_OK
    err = capsys.readouterr().err
    assert "grade: A (100/100) — diagnostic, not certification" in err


def test_cli_summary_includes_cap(capsys):
    code = cli.main(["check", "all", str(EXAMPLES / "dangerous-agent.yaml")])
    assert code == cli.EXIT_GATE
    err = capsys.readouterr().err
    assert "grade: F (0/100) — capped at C by AA-001" in err
