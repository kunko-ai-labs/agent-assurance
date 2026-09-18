## What this changes

<!-- one paragraph: what and why -->

## Checklist

- [ ] `ruff check src tests && pytest -q` pass locally
- [ ] New scanner / check / catalogue entry comes with: a fixture in `examples/repos/`, a test, a job in `.github/workflows/assurance.yml`, and (catalogue) its source
- [ ] No LLM in the verdict; nothing executed; no network; secret values never read
- [ ] Exit codes `0/1/2` unchanged (or the change is called out as breaking)
- [ ] Docs updated (`README.md` only for what a first-time reader needs; detail in `docs/`)
