"""The docs tell users to pin the Action by the release's *commit* SHA (#75).

Release tags are annotated, so `git/ref/tags/<tag> --jq .object.sha` returns the sha of the
tag object, not of the commit it points at: a workflow pinned to it does not run the release.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", *sorted((ROOT / "docs").glob("*.md"))]


def test_no_doc_reads_a_tag_ref_as_the_commit_sha():
    for path in DOCS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"git/refs?/tags/[^\s`]*`?[^\n]*\.object\.sha", text), path.name


def test_the_readme_pins_the_release_commit():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    line = next(x for x in readme.splitlines() if "**Pin by commit SHA**" in x)
    # `commits/<tag>` resolves an annotated tag to the commit it points at
    assert re.search(r"gh api repos/kunko-ai-labs/agent-assurance/commits/v\d+\.\d+\.\d+ "
                     r"--jq \.sha", line), line
    assert "^{}" in line or "^{commit}" in line   # the git-only way, peeled to the commit
