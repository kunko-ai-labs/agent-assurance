# Releasing

1. On `staging`, through a squashed pull request: bump `version` in `pyproject.toml` and `__version__` in `src/agent_assurance/__init__.py`, update the pinned examples (`README.md`, `docs/integrations.md`, `.pre-commit-hooks.yaml`) and add the row to `docs/ROADMAP.md`.
2. Build and check what will ship: `python -m build`, then list the sdist and the wheel. Install the sdist and run the tests from the extracted sdist on Python 3.10, 3.11 and 3.12.
3. Open the pull request `staging` → `main` and wait for CI, including the `branch-flow` check. Only the maintainer merges into `main`, with **Create a merge commit**, never squash (see the merge table in `CONTRIBUTING.md`).
4. Tag the merge commit on `main`: `git tag -a vX.Y.Z -m "vX.Y.Z" <sha> && git push origin vX.Y.Z`. Check the sha first: the `release-tags` ruleset makes every `v*.*.*` tag immutable, so a pushed release tag cannot be deleted or moved. A wrong tag is fixed with a new patch release, not by re-tagging.
5. `release.yml` runs on the tag: builds sdist + wheel, checks the tag matches the version, attests build provenance (Sigstore), creates the GitHub release if it does not exist yet (with generated notes you can edit afterwards), attaches the files, and publishes to PyPI through Trusted Publishing. Approve the `pypi` deployment when the environment asks for review.
6. Write the release notes on GitHub (`gh release edit vX.Y.Z --notes-file <file>`). The Marketplace listing updates itself while the checkbox stays on. Verify a file: `gh attestation verify <file> -R kunko-ai-labs/agent-assurance`.
7. Move the floating tag for the Action: `git tag -fa vX.Y -m "vX.Y" <sha> && git push -f origin vX.Y`. The ruleset covers only `v*.*.*`, so `vX.Y` can move.
8. Sync `main` into `develop` with a pull request merged with **Create a merge commit**. After a `hotfix/*` release, also sync `main` into `staging` the same way.

If PyPI already has a broken version, yank it on PyPI (never delete it) and release the next patch version.

## One-time setup for PyPI (owner)

Trusted Publishing means no API token is stored anywhere: PyPI trusts the OIDC identity of this repo's `release.yml` running in the `pypi` environment.

1. Create the PyPI account (2FA required) and, while the project does not exist yet, add a **pending publisher** at https://pypi.org/manage/account/publishing/: owner `kunko-ai-labs`, repository `agent-assurance`, workflow `release.yml`, environment `pypi`.
2. In the repo: Settings → Environments → **New environment** `pypi`. Optional but recommended: restrict it to tags `v*` and require your review before deployment.
3. Push the next tag. The first publish creates the project on PyPI under the pending publisher.
