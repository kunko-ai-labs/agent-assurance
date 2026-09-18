## ⚠️ Title format (required)

**`type(scope): [ID] Description`** — type ∈ `feat` `fix` `docs` `ci` `chore` `test` `refactor`; scope ∈ `scan` `aa-001` `aa-002` `catalog` `report` `card` `sarif` `attest` `action` `mcp` `hook` `policy` `cli` `readme`; ID = `US-XXX-YYY`, `BUG`, `CATALOG` or `EP-XXX`.

✅ `feat(scan): [US-001-002] read Windsurf mcp_config.json` · `fix(aa-002): [BUG] scoped Bash grants are review, not broken` · `docs(readme): [US-000-004] FAQ`
❌ `Update cli.py` · `fix: stuff` · `[US-001-002] Windsurf`

---

## 📋 Description

<!-- What changes and why. One paragraph. -->

## 🔗 Related issue

Closes #

## 📝 Type of change

- [ ] 🐛 Bug fix
- [ ] ✨ New observed source / catalogue entry / check
- [ ] 📤 Report format or integration (Action, MCP, hook, pre-commit, SARIF, card, attestation)
- [ ] 📚 Documentation
- [ ] 🔧 CI / release / supply chain
- [ ] 💥 **Breaking change** — exit codes, JSON/SARIF shape, manifest or policy schema (explain below)

## 🧪 How this was verified

<!-- Commands run and what you saw. A verdict change shows the fixture before/after; a catalogue entry names the source. -->

```bash
ruff check src tests && pytest -q
```

## ✅ Checklist

- [ ] Lint and tests green locally (3.10 if you can)
- [ ] New source / check / catalogue entry ships with a fixture in `examples/repos/`, a test, a job in `.github/workflows/assurance.yml`, and (catalogue) its source
- [ ] Exit codes `0 / 1 / 2` unchanged, or the change is marked breaking
- [ ] Any new third-party action pinned by commit SHA
- [ ] Self-review done; no debug output left

## 📄 Documentation

- [ ] `docs/how-it-works.md` updated (model or source changed)
- [ ] `docs/integrations.md` updated (command, format or integration changed)
- [ ] `README.md` touched only if a first-time reader needs it
- [ ] N/A — no user-visible change

## 🔐 House rules

- [ ] No LLM in the verdict
- [ ] Nothing executed, no network at scan time, secret values never read
- [ ] A guess (inferred class) never fails a build on its own
