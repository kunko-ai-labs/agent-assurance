# Compliance mapping

How agent-assurance's checks relate to the compliance frameworks a CISO
actually gets asked about: the EU AI Act, NIST AI RMF, ISO/IEC 42001 and the
OWASP Top 10 for LLM Applications. This document is the honest rationale
behind each mapping — why it is there, where it is weak, and what was
deliberately left unmapped.

## Ground rules

- **"maps"** means the control is directly about what the check measures.
  **"adapted"** means the idea was transferred from a neighbouring domain
  (like the pentest-origin APTS refs). No invented mappings: where no honest
  mapping exists, the check stays unmapped and the matrix shows an em dash.
- **These mappings are evidence, not certification.** A CI gate measuring
  blast radius does not make an organization ISO 42001-compliant or an agent
  EU AI Act-conformant. It produces auditable, deterministic evidence that
  feeds those assessments. Anyone presenting this output as a compliance
  certificate is misreading it.
- The EU AI Act's high-risk obligations (Art. 9–15, 61) apply only where the
  system actually qualifies as high-risk under the Act. The checks do not
  determine that qualification; they measure properties an assessor needs
  regardless.

## AA-001 — Blast Radius

Measures the impact surface of an agent: systems it can reach, sensitive data
classes, write/external/irreversible capabilities, capabilities it could not
classify (scored as write), and its autonomy level, including which tools run
without human approval.

| Framework | Control | Relation | Why it is honest |
|---|---|---|---|
| OWASP-ASI | ASI08 | maps | Cascading failures: the blast radius is the surface a failure cascades through. |
| OWASP-ASI | ASI03 | maps | Identity & privilege abuse: excessive permissions are exactly what the score quantifies. |
| OWASP-APTS | APTS-SC-020 | adapted | Pentest control about bounding what an autonomous system can reach; intent transfers cleanly. |
| OWASP-LLM | LLM08 | maps | *Excessive Agency* (2025) is about agents granted excessive permissions, functionality and autonomy — precisely the three inputs of the blast-radius score. |
| EU-AI-ACT | Art. 14 | maps | *Human oversight*: Art. 14 requires the ability to oversee, intervene in and stop a high-risk system. "Runs without human approval" and the autonomy level are the raw material for that assessment. |
| NIST-AI-RMF | MAP-5 | maps | The MAP function category "impacts are characterized": the check assesses the *magnitude* of potential impacts. Referenced at category level — see "open questions" below. |
| ISO-42001 | A.5.2 | maps | Annex A control "AI system impact assessment". A per-commit, deterministic, fully attributable impact assessment of the AI system. Caveat: ISO 42001 is an organizational management-system standard; this output is *evidence* for the control, not the control itself. |

**Deliberately skipped:** EU AI Act Art. 9 (risk management) — the check is one
input to a risk-management process, not the process; Art. 15 (robustness) — it
measures the impact surface, not resilience to errors. NIST subcategory-level
refs (e.g. MAP-5.1) — not referenced until verified against the official
NIST AI 100-1 tables.

## AA-002 — Declared vs Observed

Compares the manifest's promise ("this agent may read the CRM and nothing
else") against what the repository's configuration actually grants. Fails on
undeclared capability classes, sensitive data reach, and autonomy violations;
refuses "promise kept" while anything is unclassified.

| Framework | Control | Relation | Why it is honest |
|---|---|---|---|
| OWASP-ASI | ASI03 | maps | The agent holds more privilege than declared — identity & privilege abuse. |
| OWASP-ASI | ASI04 | maps | Agentic supply chain: a new MCP server quietly widening reach. |
| EU-AI-ACT | Art. 12 | adapted | *Record-keeping*: Art. 12 requires logs that let an auditor reconstruct what the system could do at a point in time. The per-commit verdict is that capability record. "adapted" because Art. 12 is about the system's own automatically generated logs, not a CI gate. |
| OWASP-LLM | LLM07 | maps | *Insecure Plugin Design* (2025): plugins operating with permissions beyond what was intended. The check verifies each tool/plugin's observed grants stay within the declared grant. Honesty boundary: it covers the *permission-bounding* half of LLM07 — it does not audit input validation inside the plugin. |
| NIST-AI-RMF | MEASURE-3 | maps | The MEASURE category "risk-tracking mechanisms are in place": a per-commit drift detector is exactly such a mechanism. Referenced at category level — see "open questions" below. |
| ISO-42001 | A.9.2 | maps | Annex A control "intended use": the declared manifest states the intended use (capabilities, autonomy, data); the check verifies the observed configuration stays within it. |

**Deliberately skipped:** EU AI Act Art. 61 (incident reporting) — the check
detects drift that *could* feed an incident process, but it is not one;
OWASP-LLM LLM05 (supply chain) — ASI04 already covers the supply-chain angle,
and adding LLM05 would be mapping inflation.

## Gaps (shown as — in the matrix, not hidden)

- **arXiv column is empty for both checks.** Neither check currently
  implements a published paper's method, and we do not claim one.
- **No mapping claims EU AI Act Art. 9, 10, 15 or 61.** Those are
  organizational-process obligations; this tool feeds them with evidence, it
  does not discharge them.
- **NIST mappings stop at category level (MAP-5, MEASURE-3).** Subcategory
  wording was not re-verified against NIST's official publication in this
  pass; tightening to subcategories is a follow-up.

## Open questions

1. Verify NIST AI RMF subcategory wording (MAP-5.x, MEASURE-3.x) directly
   against NIST AI 100-1 before claiming subcategory-level mappings.
2. As new checks land (governance-diff, evidence-contract, action-trust…),
   each must arrive with its mapping rationale already written — the matrix
   grows by construction, and the `KNOWN_FRAMEWORKS` test keeps the
   vocabulary closed.
