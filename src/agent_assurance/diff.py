"""Base vs head: what did this change do to the agent's reach and its promise?

`compute()` scans two checked-out trees (the PR base and head, typically) and
answers three questions a reviewer actually has:

  1. Which capabilities appeared, disappeared or changed hands (auto-approval,
     scope)?
  2. Did the blast radius move band?
  3. Did the promise (AA-002) go from kept to broken — and by what, exactly?

Cosmetic changes (ordering, comments, whitespace) produce no delta because the
comparison is on observed capabilities, not on file text.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import engine
from .checks.base import Context, Status
from .manifest import Manifest, Tool
from .scan import scan_directory

_BAND_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
_STATUS_ORDER = {Status.PASS: 0, Status.REVIEW: 1, Status.FAIL: 2}


def _key(t: Tool) -> tuple:
    return (t.name, t.type.value, t.system or "", t.approval or "", t.scoped)


def _describe(t: Tool) -> str:
    bits = [f"`{t.name}`", f"**{t.type.value}**"]
    if t.system:
        bits.append(f"on `{t.system}`")
    if t.approval == "auto":
        bits.append("auto-approved" + (" (scoped)" if t.scoped else ""))
    elif t.approval == "ask":
        bits.append("asks a human")
    if t.source:
        bits.append(f"({t.source})")
    return " ".join(bits)


@dataclass
class DiffReport:
    base: engine.AssuranceReport
    head: engine.AssuranceReport
    added: list[Tool] = field(default_factory=list)
    removed: list[Tool] = field(default_factory=list)
    band_from: str = "LOW"
    band_to: str = "LOW"
    promise_from: Status | None = None  # None = no manifest on that side
    promise_to: Status | None = None
    newly_broken: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)

    @property
    def band_up(self) -> bool:
        return _BAND_ORDER[self.band_to] > _BAND_ORDER[self.band_from]

    @property
    def band_down(self) -> bool:
        return _BAND_ORDER[self.band_to] < _BAND_ORDER[self.band_from]

    @property
    def promise_regressed(self) -> bool:
        """Kept (or stretched) -> broken, or new broken items on an already broken promise."""
        if self.promise_to is not Status.FAIL:
            return False
        return self.promise_from is not Status.FAIL or bool(self.newly_broken)

    @property
    def promise_stretched(self) -> bool:
        """Kept -> review: undeclared reach or unknowns, nothing breaking."""
        return self.promise_to is Status.REVIEW and self.promise_from is Status.PASS

    @property
    def has_delta(self) -> bool:
        return bool(self.added or self.removed) or self.band_from != self.band_to or self.promise_from != self.promise_to

    @property
    def regressed(self) -> bool:
        """What `--fail-on-delta` gates on: reach grew, band rose or promise broke."""
        return self.band_up or self.promise_regressed or any(t.type.value != "read" for t in self.added)

    def baseline_states(self) -> dict[str, str]:
        """SARIF baselineState per check id on the head side."""
        states: dict[str, str] = {}
        base_status = {r.check_id: r.status for r in self.base.results}
        for r in self.head.results:
            before = base_status.get(r.check_id)
            if r.status is Status.PASS:
                states[r.check_id] = "unchanged" if before is Status.PASS else "updated"
            elif before is None or before is Status.PASS:
                states[r.check_id] = "new"
            elif before is r.status:
                states[r.check_id] = "unchanged"
            else:
                states[r.check_id] = "updated"
        return states


def _report_for(directory: str, manifest_override: str | None) -> engine.AssuranceReport | None:
    declared = None
    path = manifest_override or os.path.join(directory, "agent-assurance.yaml")
    if os.path.isfile(path):
        declared = Manifest.from_file(path)
    result = scan_directory(directory, declared)
    if not result.found_anything and declared is None:
        return None
    ctx = Context(declared=declared, observed=result.observed)
    return engine.run(result.observed, None, ctx, result.sources)


def _aa(report: engine.AssuranceReport, check_id: str):
    return next((r for r in report.results if r.check_id == check_id), None)


def compute(base_dir: str, head_dir: str, manifest: str | None = None) -> DiffReport | None:
    """Returns None when neither side has anything to compare."""
    base = _report_for(base_dir, manifest)
    head = _report_for(head_dir, manifest)
    if base is None and head is None:
        return None
    if base is None:
        # Base had nothing: every head capability is new. Reuse head's shape with no results.
        base = engine.AssuranceReport(manifest=head.manifest.model_copy(update={"tools": [], "data": []}))
    if head is None:
        head = engine.AssuranceReport(manifest=base.manifest.model_copy(update={"tools": [], "data": []}))

    base_keys = {_key(t): t for t in base.manifest.tools}
    head_keys = {_key(t): t for t in head.manifest.tools}
    added = [t for k, t in head_keys.items() if k not in base_keys]
    removed = [t for k, t in base_keys.items() if k not in head_keys]

    b1, h1 = _aa(base, "AA-001"), _aa(head, "AA-001")
    b2, h2 = _aa(base, "AA-002"), _aa(head, "AA-002")
    base_broken = set(b2.data.get("broken", [])) if b2 else set()
    head_broken = set(h2.data.get("broken", [])) if h2 else set()

    return DiffReport(
        base=base,
        head=head,
        added=added,
        removed=removed,
        band_from=b1.data["band"] if b1 else "LOW",
        band_to=h1.data["band"] if h1 else "LOW",
        promise_from=b2.status if b2 else None,
        promise_to=h2.status if h2 else None,
        newly_broken=sorted(head_broken - base_broken),
        fixed=sorted(base_broken - head_broken),
    )


def to_markdown(d: DiffReport) -> str:
    m = d.head.manifest
    lines = ["## \U0001f916 Agent Assurance — what this change does", ""]
    if d.promise_regressed:
        lines.append("❌ **PROMISE BROKEN BY THIS CHANGE**")
    elif d.promise_stretched:
        lines.append("⚠️ **PROMISE STRETCHED — undeclared reach, review**")
    elif d.band_up:
        lines.append("⚠️ **BLAST RADIUS GREW**")
    elif not d.has_delta:
        lines.append("✅ **No change to what the agent can do**")
    else:
        lines.append("✅ **Reach changed, promise kept**")
    lines.append("")
    lines.append(f"**Agent:** `{m.agent.name}` v{m.agent.version} · **Autonomy:** L{m.autonomy}")
    lines.append(f"**Blast radius:** {d.band_from} → **{d.band_to}**" + (" ⬆️" if d.band_up else " ⬇️" if d.band_down else ""))
    if d.promise_to is not None:
        before = d.promise_from.value if d.promise_from else "no manifest"
        lines.append(f"**Promise (AA-002):** {before} → **{d.promise_to.value}**")
    lines.append("")

    if d.newly_broken:
        lines.append("### ❌ Newly broken")
        lines += [f"- {x}" for x in d.newly_broken]
        lines.append("")
    if d.added:
        lines.append("### ➕ Capabilities added")
        lines += [f"- {_describe(t)}" for t in d.added]
        lines.append("")
    if d.removed:
        lines.append("### ➖ Capabilities removed")
        lines += [f"- {_describe(t)}" for t in d.removed]
        lines.append("")
    if d.fixed:
        lines.append("### ✅ Fixed")
        lines += [f"- {x}" for x in d.fixed]
        lines.append("")
    if d.head.declared is not None:
        decl = d.head.declared
        classes = ", ".join(sorted({t.type.value for t in decl.tools})) or "no tools"
        lines.append(f"<sub>Declared promise: {classes}; autonomy L{decl.autonomy}. "
                     "Edit `agent-assurance.yaml` if this change is intended.</sub>")
    else:
        lines.append("<sub>No `agent-assurance.yaml` declared: nothing to hold this change against. "
                     "Add one to turn reach changes into promise checks.</sub>")
    lines.append("")
    lines.append("<sub>Generated by [agent-assurance](https://github.com/kunko-ai-labs/agent-assurance) · "
                 "transparent, rule-based, no LLM in the verdict.</sub>")
    return "\n".join(lines)


def to_dict(d: DiffReport) -> dict:
    from .reports.json_report import to_dict as report_dict

    return {
        "apiVersion": "agent-assurance/v1",
        "kind": "diff",
        "regressed": d.regressed,
        "has_delta": d.has_delta,
        "band": {"from": d.band_from, "to": d.band_to},
        "promise": {
            "from": d.promise_from.value if d.promise_from else None,
            "to": d.promise_to.value if d.promise_to else None,
            "newly_broken": d.newly_broken,
            "fixed": d.fixed,
        },
        "added": [t.model_dump(mode="json") for t in d.added],
        "removed": [t.model_dump(mode="json") for t in d.removed],
        "base": report_dict(d.base),
        "head": report_dict(d.head),
    }


def to_html(d: DiffReport, theme: str = "auto") -> str:
    """Capability card of the head side, with the delta on top."""
    from html import escape as _e

    from .reports.html import _md_inline
    from .reports.html import to_html as card

    head = card(d.head, theme=theme)
    if d.promise_regressed:
        title, color = "PROMISE BROKEN BY THIS CHANGE", "var(--fail)"
    elif d.promise_stretched or d.band_up:
        title, color = "REACH GREW — REVIEW", "var(--review)"
    elif not d.has_delta:
        title, color = "NO CHANGE TO WHAT THE AGENT CAN DO", "var(--pass)"
    else:
        title, color = "REACH CHANGED, PROMISE KEPT", "var(--pass)"
    parts = [f'<section class="delta" style="--accent:{color}">']
    parts.append(f'<div class="title">{title}</div>')
    parts.append(f'<div class="muted">Blast radius {_e(d.band_from)} → <strong>{_e(d.band_to)}</strong>'
                 + (f' · Promise {_e(d.promise_from.value if d.promise_from else "none")} → <strong>{_e(d.promise_to.value)}</strong>' if d.promise_to else "") + "</div>")
    if d.newly_broken:
        parts.append("<div class=\"k\">Newly broken</div><ul>" + "".join(f"<li>{_md_inline(x)}</li>" for x in d.newly_broken) + "</ul>")
    if d.added:
        parts.append("<div class=\"k\">Added</div><ul>" + "".join(f"<li>{_md_inline(_describe(t))}</li>" for t in d.added) + "</ul>")
    if d.removed:
        parts.append("<div class=\"k\">Removed</div><ul>" + "".join(f"<li>{_md_inline(_describe(t))}</li>" for t in d.removed) + "</ul>")
    parts.append("</section>")
    return head.replace("<main>", "<main>" + "".join(parts), 1)
