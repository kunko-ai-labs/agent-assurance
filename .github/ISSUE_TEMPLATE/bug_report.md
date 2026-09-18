---
name: "🐛 Bug Report"
about: "A wrong verdict, a crash, a wrong exit code or an integration that does not behave as documented"
title: "[BUG] "
labels: ["type:bug", "priority:medium", "status:todo"]
assignees: ""
---

<!--
╔══════════════════════════════════════════════════════════════════════════════╗
║  🐛 BUG REPORT — how to use this template                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Pipeline: Triage (Sev) → MRE (failing test) → Root cause → Fix + test →      ║
║            Review → Release → Lessons learned                                 ║
║                                                                               ║
║  1. Pick the severity with the decision tree below (first match, top-down)    ║
║  2. Apply labels: severity:sev0..sev3 and priority (Sev0→critical,            ║
║     Sev1→high, Sev2→medium, Sev3→low)                                         ║
║  3. Wrong verdict? Fill the "Verdict" block — it is the evidence we need      ║
║  4. Security issue (execute / read a secret / network / PASS what should      ║
║     FAIL because of a bypass)? Do NOT file here — use the private advisory    ║
╚══════════════════════════════════════════════════════════════════════════════╝
-->

## 🔄 Remediation pipeline

> The assignee ticks these as the bug moves. Sev0/Sev1 require the root-cause block below before the PR.

- [ ] **1 · Triage** — severity and priority labels set
- [ ] **2 · MRE** — a failing test reproduces it (fixture under `examples/repos/` if a config is involved)
- [ ] **3 · Root cause** — the rule/line that is wrong, and why it was written that way
- [ ] **4 · Fix + test** — PR `fix(scope): [BUG] …` with the minimal change, test now green
- [ ] **5 · Review** — CI green, maintainer approval
- [ ] **6 · Release** — shipped in vX.Y.Z; release notes mention it
- [ ] **7 · Lessons learned** — one line in the PR: what would have caught this earlier

---

## 🐛 Description

<!-- What happens, in one paragraph. -->

---

## 🚨 Severity — decision tree

> Tick the **first** condition that applies, top-down. When in doubt, pick the more severe.

- [ ] **Sev0** — a promise is **PASS** while the configuration grants an undeclared *breaking* capability (write / delete / execute / external_send / financial / sensitive data), or the tool executed something, read a secret value or reached the network
- [ ] **Sev1** — a promise is **FAIL** on an acceptable configuration and blocks pipelines; a crash on a valid input; a wrong exit code
- [ ] **Sev2** — wrong class, system, scope or file:line; a report format (JSON/SARIF/HTML/attestation) is malformed; an integration (Action, MCP, hook, pre-commit) misbehaves
- [ ] **Sev3** — cosmetic: wording, ordering, docs mismatch

---

## 🧪 Reproduction

**Version / environment:** `agent-assurance --version`, Python, OS or Action mode

**Command(s):**

```bash

```

**Observed configuration** (redact values, keep names):

```json

```

**Declared manifest** (or "none"):

```yaml

```

**Active policy** (`agent-assurance.policy.yaml`, or "none"):

---

## ⚖️ Verdict (wrong-verdict bugs)

| | |
|---|---|
| **Direction** | too strict / too lenient / wrong class or system / wrong location |
| **The tool said** | paste `--format json` or the markdown, including *Sources scanned* |
| **It should have said** | |
| **Rule in question** | link the row in `docs/how-it-works.md` you think is wrong or missing |

---

## ✅ Expected behaviour

---

## 🔍 Root cause (assignee; required for Sev0/Sev1)

<!-- Why 1 → Why 2 → Why 3 → … until a rule, a default or a missing test. -->

- **Why 1:**
- **Why 2:**
- **Why 3:**
- **Fix:**
- **Test that would have caught it:**
