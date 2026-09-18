# Agent Assurance

[![CI](https://github.com/kunko-ai-labs/agent-assurance/actions/workflows/ci.yml/badge.svg)](https://github.com/kunko-ai-labs/agent-assurance/actions/workflows/ci.yml) [![Self-demo: the gate blocks what it should](https://github.com/kunko-ai-labs/agent-assurance/actions/workflows/assurance.yml/badge.svg)](https://github.com/kunko-ai-labs/agent-assurance/actions/workflows/assurance.yml) [![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

**Declare what your agent may do. Verify it on every edit, every PR, every release.**

Your repo *promises* what an AI agent is allowed to do (`agent-assurance.yaml`: read the CRM, no external send, a human approves actions). Agent Assurance *observes* what the configuration actually grants — MCP servers, Claude Code permissions, tool definitions — and fails the change when the promise is broken, pointing at the file and line that broke it. Then it leaves a signed record of what the agent could do, and when.

No dashboard, no backend, no LLM in the verdict, no network calls, nothing executed. Rules you can read; numbers you can reproduce by hand.

![A PR adds a GitHub MCP server to a read-only agent and gets blocked](docs/demo.gif)

```bash
pipx install git+https://github.com/kunko-ai-labs/agent-assurance@v0.5.0   # PyPI: coming with v0.5.1
agent-assurance scan .        # what does this repo let the agent do — and does it match the promise?
```

▶ [22-second launch video](https://github.com/kunko-ai-labs/agent-assurance/releases/download/v0.5.0/brag.mp4)

---

## What it catches

| Situation | What Agent Assurance says |
|---|---|
| A PR adds `@modelcontextprotocol/server-github` to an agent declared read-only | **Promise broken:** `github.write` grants write, not declared (`.mcp.json:17`); blast radius LOW → HIGH |
| `.claude/settings.json` gets `allow: Bash(*)` while the manifest says a human approves (L2) | **Promise broken:** `Bash(*)` runs without human approval, but declared autonomy is L2 |
| A server config carries `GITHUB_PERSONAL_ACCESS_TOKEN` | Access to **credential** data, not declared — the value is never read, only the name |
| A server nobody recognises appears | `UNKNOWN`, scored conservatively; **promise not verifiable** — never a silent pass |
| Twenty `allow: Bash(git status:*)`-style rules | One read-only shell grant, not twenty unattended shells — no false alarm |
| A tool named `billing.issue_refund` shows up in the agent's tool definitions | **financial**, inferred from the name → *review*, never *fail* on a guess |

Live: [the demo PR](https://github.com/kunko-ai-labs/agent-assurance/pull/16) stays red on purpose. Real repos, scanned as-is: [`docs/real-world.md`](docs/real-world.md).

![The PR comment on the live demo](docs/pr-comment.png)

## Why this and not a scanner

Vulnerability scanners look for poisoned tools and leaked secrets. Permission-diff bots show what changed. Neither answers the governance question: **does this agent still do only what we said it does?**

| | Vulnerability scanners (Snyk agent-scan, Cisco MCP Scanner, agentshield) | Permission-diff bots (agentcapdiff & co.) | **Agent Assurance** |
|---|---|---|---|
| Finds poisoned tools, leaked secrets | ✅ | — | — (use them for that) |
| Shows what a PR changed | — | ✅ | ✅ |
| **Verifies a declared promise** | — | — | ✅ file:line |
| Knows *having* a power ≠ *using it without a human* | — | — | ✅ |
| OWASP Agentic Top 10 mapping | — | — | ✅ |
| Signed, per-commit evidence (in-toto / Sigstore) | — | — | ✅ |
| LLM in the verdict | some | — | never |

Checked 2026-09-17; details and sources in [`docs/landscape.md`](docs/landscape.md). This is the governance layer *under* a scanner, not a replacement for one.

**Not for you if** you want prompt-injection or tool-poisoning detection (use a scanner), runtime interception of tool calls (a different product), or a score for agents that have no configuration in a repo (there is nothing to observe).

## One promise, three enforcement points

| When | How | What you see |
|---|---|---|
| **While the agent edits** | [MCP server](contrib/claude-code/) (`would_break`) or [Claude Code hook](contrib/claude-code/) | The agent is told, in the same turn, that its edit breaks the promise |
| **In the pull request** | GitHub Action `mode: diff` | One comment, updated on every push, plus a red check |
| **On every push / release** | Action `mode: scan` + SARIF + `attest` | Findings in the Security tab; an in-toto attestation (Sigstore-signed when public) of what the agent could do at that commit |

Same engine, same words, everywhere.

## Two inputs, two checks

**Declared** — the promise, written by the team in `agent-assurance.yaml`: capability classes, systems, data, autonomy.
**Observed** — what the configuration actually grants: MCP configs for Claude Code, Cursor, Gemini CLI, VS Code and Codex; Claude Code permissions (`allow` = no human in the loop); serialized tool definitions (OpenAI, MCP, Claude, LangChain, CrewAI). Unknown is `UNKNOWN`, never guessed.

| Check | Question | Fails when |
|---|---|---|
| **AA-001 Blast Radius** | If this agent misbehaves, how much can it break? | CRITICAL band (review on HIGH or any `UNKNOWN`) |
| **AA-002 Declared vs Observed** | Does the configuration stay within the promise? | Undeclared write / delete / execute / send / financial, sensitive data, or an unscoped auto-approval under a human-approves promise |

Details, weights and the organisation policy file: [`docs/how-it-works.md`](docs/how-it-works.md).

## Use it

```yaml
# .github/workflows/agent-assurance.yml
permissions: { contents: read, pull-requests: write }
steps:
  - uses: actions/checkout@v4
  - uses: kunko-ai-labs/agent-assurance@v0.5
    with:
      mode: diff                 # on pull_request; use scan on push
      manifest: agent-assurance.yaml
      card: aa-card.html         # optional: shareable capability card
      attest: write              # optional: in-toto evidence (sign = Sigstore)
```

CLI (`scan`, `diff`, `check`, `attest`, `validate`; formats `md`, `json`, `sarif`, `html`), pre-commit, MCP server, Claude Code hook and the Python API: [`docs/integrations.md`](docs/integrations.md).

**Exit codes are a contract:** `0` pass · `1` gate tripped · `2` usage error.

### Running third-party code in your CI — what you should check

- **Pin by commit SHA**, not by tag: `uses: kunko-ai-labs/agent-assurance@<sha> # v0.5.0`. Tags can move; a SHA cannot. Dependabot keeps the comment and the SHA in step. Our own workflows pin every action the same way.
- **What the Action does:** `pip install` of this repository at that SHA, then runs the CLI on your files. It makes **no network calls** of its own (the only outbound traffic is `pip` and, if you opt in, `upload-sarif` / `attest` to GitHub). It executes nothing from your repo, never starts an MCP server, never reads a secret's value.
- **Least privilege:** `contents: read` is enough for `check` and `scan`; add `pull-requests: write` only for the diff comment, `security-events: write` only for SARIF upload, `id-token: write` + `attestations: write` only for signing.
- **Verify what you get:** every release is signed; `gh attestation verify` on the artifacts, and the [OpenSSF Scorecard](https://scorecard.dev/viewer/?uri=github.com/kunko-ai-labs/agent-assurance) of this repo is public.

## The capability card

`--format html` produces a single self-contained file — the agent's nutrition label — for auditors, customers or your manager. Light or dark, follows the viewer.

![Capability card for a broken promise](docs/capability-card.png)

## Rules you can rely on

- **Deterministic.** No LLM anywhere in the verdict.
- **Nothing executed, nothing sent.** Config files are read; MCP servers never started; secret values never read; no network.
- **Unknown is a result, not a silence.** And a guess (an inferred class) never fails a build on its own.
- **Honest mapping.** OWASP ASI controls are `maps`; anything borrowed (OWASP APTS, EU AI Act art. 12) is `adapted`. No conformance claimed.
- **Tested contracts.** Exit codes, SARIF, Action YAML and every fixture's verdict, on Python 3.10–3.12.

## FAQ

**Does it read my secrets?** No. It looks at the *names* of environment variables and headers (`GITHUB_TOKEN`, `Authorization`) to know a credential is in play; values are never read, logged or hashed.

**Does it work without the manifest?** Yes: `scan` without `agent-assurance.yaml` reports the observed blast radius and a "Sources scanned" table. Add the manifest to turn reach into a promise (AA-002).

**What about our private MCP servers?** They come out `UNKNOWN`: scored conservatively, and a promise cannot be called kept over them. Add them to your [organisation policy](docs/how-it-works.md#organisation-policy) catalogue — one entry with its source — and they are classified like any other.

**Is the risk score "AI"?** No. It is a table of weights in one file, every point has a reason, and the report shows the sum. Same input, same number, forever.

**Can it stop the agent at runtime?** No, by design. It checks what the repo says the agent can do — at edit time, in the PR, at release. Runtime enforcement is a different product.

Roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md) · Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md) · Good first issues: [`label:good first issue`](https://github.com/kunko-ai-labs/agent-assurance/labels/good%20first%20issue)

## License

Apache-2.0 © 2026 Kunko AI Labs
