# Contributing

## What lives where

| Path | Audience | What |
|---|---|---|
| `src/agent_assurance/` | developers | the product: scanners, checks, risk model, reports, CLI, MCP server |
| `action.yml`, `.pre-commit-hooks.yaml`, `contrib/` | users | ways to run it (GitHub Action, pre-commit, Claude Code hook/MCP) |
| `examples/` | users, tests | manifests and mini-repos that double as fixtures and demos |
| `schema/` | users | JSON schemas for the manifest and the policy file |
| `docs/` | users, buyers, auditors | how it works, integrations, roadmap, real-world scans, landscape, images |
| `tests/` | developers | contract tests (exit codes, SARIF, YAML shape, every fixture's verdict) |

Launch material (video, composition, share copy) is **not** in this repo; the video is attached to the release.

## Branches

- `main` — releasable at all times. Only merges from `develop` (or hotfixes). Every release is a tag `vX.Y.Z` plus a moving `vX.Y` for the Action.
- `develop` — integration branch. Day-to-day work lands here through feature branches.
- `feat/*`, `fix/*`, `docs/*` — short-lived; open a PR into `develop`. The CI (`ci.yml`) and the dogfood (`assurance.yml`) run on every PR.
- `demo/*` — living demos that must stay red (see PR #16). Never merged.

Release: `develop` → PR → `main` → bump version in `pyproject.toml` and `__init__.py` → tag → GitHub release with notes → move the `vX.Y` tag.

## Before you push

```bash
pip install -e ".[dev]"
ruff check src tests && pytest -q
```

Rules that do not bend (see `CLAUDE.md`): no LLM in the verdict; nothing executed or sent; unknown is `UNKNOWN`; exit codes `0/1/2` are a contract; a step name with `:` in `action.yml` goes in quotes; a new scanner or check comes with a fixture in `examples/repos/`, a test, and a job in `assurance.yml`; a new MCP catalogue entry cites its source.

Before a release: scan a few real public repos (`docs/real-world.md`) and re-check `docs/landscape.md`.
