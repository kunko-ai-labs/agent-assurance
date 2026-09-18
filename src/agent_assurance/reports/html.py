"""Capability card — a single-file HTML "nutrition label" for one agent.

Built from the same data as the JSON report (never a second truth), with no
external assets, no JavaScript and no network, so it can be attached to a
ticket, sent to an auditor or opened on a phone. Style is deliberately plain:
the verdict, the promise, what was observed with file:line, the score
breakdown, and what the scan looked at.
"""

from __future__ import annotations

import datetime as _dt
from html import escape as _e

from .. import __version__
from ..checks.base import Status
from ..engine import AssuranceReport

_LABEL = {Status.PASS: "PASS", Status.REVIEW: "REVIEW", Status.FAIL: "FAIL"}

_CSS = """
:root{--bg:#f6f8fa;--panel:#fff;--fg:#1f2328;--muted:#57606a;--line:#d0d7de;--row:#eaeef2;--code:#f6f8fa;--link:#0969da;
      --pass:#1a7f37;--review:#9a6700;--fail:#cf222e;color-scheme:light dark}
:root[data-theme="dark"]{--bg:#0d1117;--panel:#161b22;--fg:#e6edf3;--muted:#8b949e;--line:#30363d;--row:#21262d;--code:#0d1117;--link:#58a6ff;
      --pass:#3fb950;--review:#d29922;--fail:#f85149}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#0d1117;--panel:#161b22;--fg:#e6edf3;--muted:#8b949e;--line:#30363d;--row:#21262d;--code:#0d1117;--link:#58a6ff;
      --pass:#3fb950;--review:#d29922;--fail:#f85149}}
body{margin:0;padding:24px 16px;font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;color:var(--fg);background:var(--bg)}
main{max-width:880px;margin:0 auto;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:24px 28px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
a{color:var(--link)}.meta{color:var(--muted);font-size:13px}
.badge{display:inline-block;padding:4px 12px;border-radius:999px;color:#fff;font-weight:700;letter-spacing:.3px}
.badge.pass{background:var(--pass)}.badge.review{background:var(--review)}.badge.fail{background:var(--fail)}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--row);vertical-align:top}
th{color:var(--muted);font-weight:600}code{background:var(--code);padding:1px 4px;border-radius:4px;font-size:12.5px}
.k{font-weight:600}.muted{color:var(--muted)}.pill{display:inline-block;padding:1px 7px;border-radius:999px;font-size:12px;border:1px solid var(--line)}
.pill.fail{border-color:var(--fail);color:var(--fail)}.pill.review{border-color:var(--review);color:var(--review)}.pill.pass{border-color:var(--pass);color:var(--pass)}
ul{padding-left:20px;margin:6px 0}footer{margin-top:28px;color:var(--muted);font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:12px 0}
.card{border:1px solid var(--line);border-radius:6px;padding:10px 12px}.card .v{font-size:20px;font-weight:700}
section.delta{border-left:4px solid var(--accent);padding:8px 14px;margin-bottom:20px;background:var(--code)}
section.delta .title{font-weight:700;color:var(--accent)}
"""


def _status_pill(s: Status) -> str:
    return f'<span class="pill {s.value.lower()}">{_LABEL[s]}</span>'


def to_html(report: AssuranceReport, generated_at: str | None = None, theme: str = "auto") -> str:
    """`theme`: "auto" follows the viewer's system setting; "dark" / "light" force one."""
    m = report.manifest
    v = report.verdict
    aa1 = next((r for r in report.results if r.check_id == "AA-001"), None)
    aa2 = next((r for r in report.results if r.check_id == "AA-002"), None)
    generated_at = generated_at or _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")

    out: list[str] = []
    attr = f' data-theme="{theme}"' if theme in ("dark", "light") else ""
    out.append(f"<!doctype html><html lang=\"en\"{attr}><head><meta charset=\"utf-8\">")
    out.append('<meta name="viewport" content="width=device-width,initial-scale=1">')
    out.append(f"<title>Agent capability card — {_e(m.agent.name)}</title><style>{_CSS}</style></head><body><main>")

    # Header
    out.append(f'<span class="badge {v.value.lower()}">{_LABEL[v]}</span>')
    out.append(f"<h1>{_e(m.agent.name)} <span class=\"meta\">v{_e(m.agent.version)}</span></h1>")
    fw = m.framework.name or "unknown"
    mode = (
        "declared manifest verified against observed configuration"
        if report.declared is not None
        else ("observed configuration only — no manifest declared" if report.sources else "declared manifest only")
    )
    out.append(f'<div class="meta">Framework: {_e(fw)} · Autonomy: L{m.autonomy} · {_e(mode)}</div>')
    if report.policy:
        out.append(f'<div class="meta">Policy: {_e(report.policy["name"])} · <code>{_e(report.policy["sha256"][:12])}</code></div>')

    # Summary cards
    out.append('<div class="grid">')
    if aa1:
        out.append(f'<div class="card"><div class="muted">Blast radius</div><div class="v">{_e(aa1.data.get("band", "?"))}</div><div class="muted">score {aa1.data.get("score", "?")} · {_status_pill(aa1.status)}</div></div>')
    if aa2:
        out.append(f'<div class="card"><div class="muted">Promise</div><div class="v">{_e(aa2.summary.split(":")[0])}</div><div class="muted">{_status_pill(aa2.status)}</div></div>')
    out.append(f'<div class="card"><div class="muted">Capabilities observed</div><div class="v">{len(m.tools)}</div><div class="muted">{len({t.system for t in m.tools if t.system})} systems</div></div>')
    out.append("</div>")

    # Promise
    if report.declared is not None:
        d = report.declared
        classes = ", ".join(sorted({t.type.value for t in d.tools})) or "no tools"
        data = ", ".join(sorted({x.type.value for x in d.data})) or "none"
        systems = ", ".join(sorted({t.system for t in d.tools if t.system} | {s for x in d.data for s in x.systems})) or "none"
        out.append("<h2>The promise (declared)</h2>")
        out.append(f"<p><span class=\"k\">May do:</span> {_e(classes)} · <span class=\"k\">Data:</span> {_e(data)} · <span class=\"k\">Systems:</span> {_e(systems)} · <span class=\"k\">Autonomy:</span> L{d.autonomy} ({'a human approves actions' if d.autonomy <= 2 else 'acts on its own'})</p>")

    # AA-002 details
    if aa2:
        out.append(f"<h2>Declared vs observed {_status_pill(aa2.status)}</h2>")
        out.append(f"<p>{_e(aa2.summary)}</p><ul>")
        for line in aa2.details[1:]:
            out.append(f"<li>{_md_inline(line)}</li>")
        out.append("</ul>")

    # Observed capabilities
    out.append("<h2>What the configuration grants (observed)</h2>")
    if m.tools:
        out.append("<table><tr><th>Capability</th><th>Class</th><th>System</th><th>Human in the loop</th><th>Source</th></tr>")
        for t in sorted(m.tools, key=lambda t: (t.system or "", t.name)):
            hitl = {"auto": "no — auto-approved" + (" (scoped)" if t.scoped else ""), "ask": "yes — asks"}.get(t.approval or "", "—")
            flags = []
            if t.irreversible:
                flags.append("irreversible")
            if t.production:
                flags.append("production")
            cls = _e(t.type.value) + (f' <span class="muted">({", ".join(flags)})</span>' if flags else "")
            out.append(f"<tr><td><code>{_e(t.name)}</code></td><td>{cls}</td><td>{_e(t.system or '')}</td><td>{_e(hitl)}</td><td class=\"muted\">{_e(t.source or 'declared')}</td></tr>")
        out.append("</table>")
    else:
        out.append('<p class="muted">No tools.</p>')
    if m.data:
        out.append("<p><span class=\"k\">Data reached:</span> " + ", ".join(f"{_e(d.type.value)} ({_e(', '.join(d.systems) or 'unspecified')})" for d in m.data) + "</p>")

    # Blast radius breakdown
    if aa1:
        out.append(f"<h2>Blast radius {_status_pill(aa1.status)}</h2>")
        out.append(f"<p>{_e(aa1.summary)}. Every point is attributable:</p><table><tr><th>Points</th><th>Why</th></tr>")
        for f in aa1.data.get("factors", []):
            out.append(f"<tr><td>+{f['points']}</td><td>{_e(f['reason'])}</td></tr>")
        out.append(f"<tr><td class=\"k\">{aa1.data.get('score')}</td><td class=\"k\">total → {_e(aa1.data.get('band', ''))}</td></tr></table>")
        std = ", ".join(f"{s.framework}:{s.control}" + ("" if s.relation == "maps" else f" ({s.relation})") for s in aa1.standards)
        out.append(f'<p class="muted">Standards: {_e(std)}</p>')

    # Sources
    if report.sources:
        out.append("<h2>Sources scanned</h2><table><tr><th>File</th><th>Kind</th><th>Status</th><th>Notes</th></tr>")
        for s in report.sources:
            status = "parsed" if s.supported else "detected, not supported"
            out.append(f"<tr><td><code>{_e(s.path)}</code></td><td>{_e(s.kind)}</td><td>{status}</td><td class=\"muted\">{_e(s.note)}</td></tr>")
        out.append("</table>")

    out.append(f"<footer>Generated {_e(generated_at)} by agent-assurance {_e(__version__)} · deterministic, rule-based, no LLM in the verdict · <a href=\"https://github.com/kunko-ai-labs/agent-assurance\">github.com/kunko-ai-labs/agent-assurance</a></footer>")
    out.append("</main></body></html>")
    return "\n".join(out)


def _md_inline(s: str) -> str:
    """Escape, then render the two markdown bits the checks use: **bold** and `code`."""
    import re

    t = _e(s)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t
