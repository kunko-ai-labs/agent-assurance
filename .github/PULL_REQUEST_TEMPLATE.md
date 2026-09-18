<!-- Title: `type(scope): summary` — e.g. `feat(scan): read Windsurf mcp_config.json`, `fix(aa-002): scoped Bash grants are review, not broken`, `docs(readme): …` -->

## Summary

<!-- What changes and why, in a few lines. Link the issue: "Closes #NN". -->

Closes #

## Type

- [ ] Bug fix
- [ ] New observed source / catalogue entry / check
- [ ] Report format or integration (Action, MCP, hook, pre-commit)
- [ ] Docs
- [ ] CI / release / supply chain
- [ ] **Breaking change** (exit codes, JSON/SARIF shape, manifest or policy schema) — say what and why below

## How this was verified

<!-- Commands you ran and what you saw. For a verdict change: the fixture before/after. For a catalogue entry: the source you read. -->

## House rules

- [ ] `ruff check src tests && pytest -q` pass locally
- [ ] No LLM in the verdict; nothing executed; no network at scan time; secret values never read
- [ ] A new scanner / check / catalogue entry ships with a fixture in `examples/repos/`, a test, a job in `.github/workflows/assurance.yml`, and (catalogue) its source
- [ ] Exit codes `0 / 1 / 2` unchanged
- [ ] Docs updated (`README.md` only for what a first-time reader needs; detail in `docs/`)
- [ ] Any new third-party action is pinned by commit SHA
