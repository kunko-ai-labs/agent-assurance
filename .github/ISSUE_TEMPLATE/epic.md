---
name: "🎯 Epic"
about: "A capability made of several User Stories, with a product goal and a metric"
title: "[EP-XXX] Epic name"
labels: ["epic", "status:todo"]
assignees: ""
---

<!--
╔══════════════════════════════════════════════════════════════════════════════╗
║  🎯 EPIC — how to use this template                                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Use an Epic when:                                                            ║
║  ✅ the work spans several User Stories (> 1 week)                            ║
║  ✅ it adds or changes a capability of the product (a new observed source,    ║
║     a new check, a new enforcement point, a new evidence format)              ║
║  ✅ it has a product goal a user would recognise, and a metric                ║
║                                                                               ║
║  Use a User Story instead when it is one scoped change (1–5 days).            ║
║                                                                               ║
║  Title: [EP-XXX] Name in English — XXX is the next free number               ║
║  (check the Epics list before creating). Example: [EP-002] Policy & tuning   ║
╚══════════════════════════════════════════════════════════════════════════════╝
-->

# 🎯 EPIC: [Name]

## 🧭 Product block

> 🏷️ **Apply labels** (they exist in the repo): one `pillar:*`, one `bet:*`, one or more `persona:*`.

| Field | Value |
|-------|-------|
| **Pillar** | `pillar:observe` (what the repo grants) / `pillar:verdict` (checks & risk model) / `pillar:evidence` (SARIF, card, attestation) / `pillar:enforce` (Action, hook, MCP, pre-commit) / `pillar:trust` (supply chain, docs, transparency) |
| **Persona** | `persona:developer` / `persona:reviewer` / `persona:ciso` / `persona:auditor` |
| **Bet** | `bet:now` (this release) / `bet:next` / `bet:later` / `bet:tech-health` |
| **Milestone** | vX.Y.0 |
| **Primary success metric** | e.g. *"UNKNOWN servers in `docs/real-world.md` drop from 4 to 0"* — never "feature shipped" |
| **Guardrail metric** | what must NOT get worse — e.g. *"no new FAIL on `examples/repos/*-kept`"*, *"exit-code contract unchanged"* |
| **Explicit out-of-scope** | what this epic will NOT build |

---

## 📝 Description

<!-- The problem, in the user's words. Why now. Link `docs/landscape.md` if a competitor angle matters. -->

## 🎯 Goals

- [ ] Goal 1
- [ ] Goal 2

## 📖 User Stories

<!-- Create each with the User Story template; list them here as they are opened. -->

| ID | Title | Status |
|----|-------|--------|
| US-XXX-001 | | `status:todo` |
| US-XXX-002 | | `status:todo` |

## ✅ Epic acceptance

- [ ] All stories closed and released
- [ ] Success metric measured and recorded in the milestone notes
- [ ] Guardrail metric intact (CI self-demo green, contract tests green)
- [ ] Docs updated (`README.md` only for first-time readers; detail in `docs/`)

## 🔗 Dependencies

- Depends on: #
- Blocks: #

## 🔐 House rules check

- [ ] No LLM in the verdict
- [ ] Nothing executed, no network, secret values never read at scan time
- [ ] Not runtime interception (out of scope by design)
