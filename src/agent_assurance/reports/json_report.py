"""JSON renderer — machine-readable output for pipelines and other tools."""

from __future__ import annotations

import json

from ..engine import AssuranceReport


def _grade_dict(report: AssuranceReport) -> dict | None:
    g = report.grade
    if g is None:
        return None
    return {
        "letter": g.letter,
        "letter_before_cap": g.letter_before_cap,
        "score": g.score,
        "capped": g.capped,
        "capped_by": list(g.capped_by),
        "disclaimer": g.disclaimer,
        "pillars": [
            {
                "id": p.pillar,
                "title": p.title,
                "weight": p.weight,
                "score": p.score,
                "detail": p.detail,
            }
            for p in g.pillars
        ],
    }


def to_dict(report: AssuranceReport) -> dict:
    return {
        "apiVersion": "agent-assurance/v1",
        "agent": {
            "name": report.manifest.agent.name,
            "version": report.manifest.agent.version,
        },
        "verdict": report.verdict.value,
        "passed": report.passed,
        "grade": _grade_dict(report),
        "policy": report.policy,
        "checks": [
            {
                "id": r.check_id,
                "title": r.title,
                "status": r.status.value,
                "summary": r.summary,
                "details": r.details,
                "standards": [
                    {
                        "framework": s.framework,
                        "control": s.control,
                        "relation": s.relation,
                    }
                    for s in r.standards
                ],
                "data": r.data,
                "locations": [{"path": loc.path, "line": loc.line} for loc in r.locations],
            }
            for r in report.results
        ],
        "sources": [
            {"path": s.path, "kind": s.kind, "supported": s.supported, "note": s.note}
            for s in report.sources
        ],
    }


def to_json(report: AssuranceReport, indent: int = 2) -> str:
    return json.dumps(to_dict(report), indent=indent, ensure_ascii=False)
