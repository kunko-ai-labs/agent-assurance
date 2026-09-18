---
name: "📖 User Story"
about: "One scoped change (1–5 days) with acceptance criteria and a Definition of Done"
title: "[US-XXX-YYY] Title in English"
labels: ["type:story", "priority:medium", "status:todo"]
assignees: ""
---

<!--
╔══════════════════════════════════════════════════════════════════════════════╗
║  📖 USER STORY — how to use this template                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Title: [US-XXX-YYY] Title — XXX = Epic number, YYY = story number            ║
║  Stories without an Epic use EP-000 (backlog): [US-000-YYY]                   ║
║                                                                               ║
║  Labels to apply: type:story · priority:critical|high|medium|low             ║
║                   area:scan|check|report|integration|policy|docs|ci          ║
║                   good-first-issue if a newcomer can do it in one sitting     ║
║                                                                               ║
║  A story is done when the Definition of Done at the bottom is all ticked.    ║
╚══════════════════════════════════════════════════════════════════════════════╝
-->

## Story ID: US-XXX-YYY

| Field | Value |
|-------|-------|
| **Epic** | EP-XXX — name |
| **Priority** | Critical / High / Medium / Low |
| **Area** | Scan / Check / Report / Integration / Policy / Docs / CI |
| **Persona** | Developer / Reviewer / CISO / Auditor |
| **Estimate** | X days |
| **Milestone** | vX.Y.0 |

---

## 📖 User Story

**As a** [persona],
**I want** [capability],
**so that** [outcome I can see or prove].

---

## ✅ Acceptance Criteria

<!-- Given / When / Then. Each criterion maps to at least one test. -->

- [ ] **Given** … **when** … **then** …
- [ ] **Given** … **when** … **then** …

---

## 📋 Technical Notes

<!-- Files to touch, shape of the change, pointers to similar code. -->

- Entry point:
- Similar code:
- Fixture / example to add under `examples/repos/`:

---

## 🔗 Dependencies

- Depends on: #
- Blocks: #

---

## 🔐 Security & house rules

- [ ] No LLM in the verdict
- [ ] Nothing executed, no network, secret values never read
- [ ] Exit codes `0 / 1 / 2` unchanged (or the change is flagged as breaking)
- [ ] A guess (inferred class) never fails a build on its own

---

## 📄 Documentation

- [ ] `docs/how-it-works.md` (if the model or a source changed)
- [ ] `docs/integrations.md` (if a command, format or integration changed)
- [ ] `README.md` only if a first-time reader needs it

---

## 🏁 Definition of Done

- [ ] Code + tests merged into `develop` via PR titled `type(scope): [US-XXX-YYY] …`
- [ ] Fixture in `examples/repos/` and a job in `.github/workflows/assurance.yml` if a source, check or catalogue entry was added
- [ ] `ruff check src tests && pytest -q` green on 3.10–3.12
- [ ] Docs updated per the list above
- [ ] Epic table updated (`status:done`)
