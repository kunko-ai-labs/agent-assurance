"""Blast Radius check (AA-001).

Answers the CISO question: "if this agent is compromised or misbehaves, how
much can it break?" It does NOT judge whether the agent is good — it measures
the potential impact surface, transparently, from the manifest alone.

Maps to OWASP Agentic Top 10 ASI08 (Cascading failures) and ASI03 (Identity &
privilege abuse). Adapted from OWASP APTS SC-020 (external action allowlist),
whose intent — bounding what an autonomous system can reach — transfers cleanly.

Compliance mappings (rationale in docs/compliance-mapping.md):
  - OWASP LLM08 (Excessive Agency): the check measures exactly that — the
    permissions, functionality and autonomy granted to the agent.
  - EU AI Act Art. 14 (Human oversight): auto-approved tools and autonomy
    levels are the raw material for a human-oversight assessment.
  - NIST AI RMF MAP-5: the check assesses the magnitude of potential impacts.
  - ISO/IEC 42001 A.5.2 (AI system impact assessment): a per-commit, automated
    impact assessment of the AI system.
"""

from __future__ import annotations

from typing import ClassVar

from .. import policy, risk
from ..manifest import Manifest
from .base import Check, CheckResult, Context, StandardRef, Status

# Bands that warrant a gate. LOW/MEDIUM pass; HIGH -> review; CRITICAL -> fail.
REVIEW_BANDS = {"HIGH"}
FAIL_BANDS = {"CRITICAL"}


class BlastRadiusCheck(Check):
    check_id = "AA-001"
    title = "Blast Radius"
    standards: ClassVar[list[StandardRef]] = [
        StandardRef("OWASP-ASI", "ASI08", "maps"),
        StandardRef("OWASP-ASI", "ASI03", "maps"),
        StandardRef("OWASP-APTS", "APTS-SC-020", "adapted"),
        StandardRef("OWASP-LLM", "LLM08", "maps"),
        StandardRef("EU-AI-ACT", "Art. 14", "maps"),
        StandardRef("NIST-AI-RMF", "MAP-5", "maps"),
        StandardRef("ISO-42001", "A.5.2", "maps"),
    ]

    def run(self, manifest: Manifest, ctx: Context) -> CheckResult:
        p = risk.assess(manifest)
        gate = policy.current().gate

        if p.band in gate.fail_bands:
            status = Status.FAIL
        elif p.band in gate.review_bands or p.unknown_capabilities:
            # An unclassified capability means the radius is not fully known;
            # that is never a silent PASS.
            status = Status.REVIEW
        else:
            status = Status.PASS

        details: list[str] = []
        if p.systems:
            details.append("Systems affected: " + ", ".join(sorted(p.systems)))
        if p.data_classes:
            details.append("Sensitive data: " + ", ".join(sorted(p.data_classes)))
        if p.write_capabilities:
            details.append("Write capabilities: " + ", ".join(p.write_capabilities))
        if p.external_side_effects:
            details.append(
                "External side effects: " + ", ".join(p.external_side_effects)
            )
        if p.irreversible_actions:
            details.append(
                "Irreversible actions: " + ", ".join(p.irreversible_actions)
            )
        if p.unknown_capabilities:
            details.append(
                "Unknown capabilities (scored as write): "
                + ", ".join(p.unknown_capabilities)
            )
        if p.auto_approved:
            details.append("Runs without human approval: " + ", ".join(p.auto_approved))
        details.append(f"Autonomy: L{manifest.autonomy}")
        details.append(f"Risk score: {p.score} ({p.band})")

        summary = f"Blast radius {p.band} (score {p.score})"
        if p.unknown_capabilities:
            summary += f" — {len(p.unknown_capabilities)} unknown capabilit{'y' if len(p.unknown_capabilities) == 1 else 'ies'}"

        return CheckResult(
            check_id=self.check_id,
            title=self.title,
            status=status,
            summary=summary,
            details=details,
            standards=self.standards,
            data={
                "score": p.score,
                "band": p.band,
                "systems": sorted(p.systems),
                "data_classes": sorted(p.data_classes),
                "write_capabilities": p.write_capabilities,
                "external_side_effects": p.external_side_effects,
                "irreversible_actions": p.irreversible_actions,
                "unknown_capabilities": p.unknown_capabilities,
                "auto_approved": p.auto_approved,
                "factors": [
                    {"points": f.points, "reason": f.reason} for f in p.factors
                ],
            },
        )
