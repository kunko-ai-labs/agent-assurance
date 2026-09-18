# Releasing

1. On `develop`: bump `version` in `pyproject.toml` and `__version__` in `src/agent_assurance/__init__.py`; update `docs/ROADMAP.md`.
2. PR `develop` → `main`; wait for CI.
3. Tag on `main`: `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`, then move the floating tag: `git tag -f vX.Y && git push -f origin vX.Y`.
4. `release.yml` runs on the tag: builds sdist + wheel, checks the tag matches the version, attests build provenance (Sigstore), attaches the files to the GitHub release, and publishes to PyPI through Trusted Publishing.
5. Write the release notes on GitHub (the Marketplace listing updates itself while the checkbox stays on).

## One-time setup for PyPI (owner)

Trusted Publishing means no API token is stored anywhere: PyPI trusts the OIDC identity of this repo's `release.yml` running in the `pypi` environment.

1. Create the PyPI account (2FA required) and, while the project does not exist yet, add a **pending publisher** at https://pypi.org/manage/account/publishing/: owner `kunko-ai-labs`, repository `agent-assurance`, workflow `release.yml`, environment `pypi`.
2. In the repo: Settings → Environments → **New environment** `pypi`. Optional but recommended: restrict it to tags `v*` and require your review before deployment.
3. Push the next tag. The first publish creates the project on PyPI under the pending publisher.
