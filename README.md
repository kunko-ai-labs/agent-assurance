# Agent Assurance

**Declare what your agent may do. Verify it on every edit, every PR, every release.**

Your repo *promises* what an AI agent is allowed to do (`agent-assurance.yaml`: read the CRM, no external send, a human approves actions). Agent Assurance *observes* what the configuration actually grants — MCP servers, Claude Code permissions, tool definitions — and fails the change when the promise is broken, pointing at the file and line that broke it. Then it leaves a signed record of what the agent could do, and when.

No dashboard, no backend, no LLM in the verdict, no network calls, nothing executed. Rules you can read; numbers you can reproduce by hand.

![A PR adds a GitHub MCP server to a read-only agent and gets blocked](docs/demo.gif)

```bash
pipx install agent-assurance
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

Vulnerability scanners look for poisoned tools and leaked secrets. Permission-diff bots show what changed. Neither answers the governance question: **does this agent still do only what we said it does?** Agent Assurance answers it deterministically, maps every finding to the **OWASP Top 10 for Agentic Applications**, knows the difference between *having* a power and *using it without a human*, and leaves a per-commit record an auditor can reconstruct — the shape EU AI Act art. 12 asks for. What else exists and where this sits: [`docs/landscape.md`](docs/landscape.md).

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

## The capability card

`--format html` produces a single self-contained file — the agent's nutrition label — for auditors, customers or your manager. Light or dark, follows the viewer.

![Capability card for a broken promise](docs/capability-card.png)

## Rules you can rely on

- **Deterministic.** No LLM anywhere in the verdict.
- **Nothing executed, nothing sent.** Config files are read; MCP servers never started; secret values never read; no network.
- **Unknown is a result, not a silence.** And a guess (an inferred class) never fails a build on its own.
- **Honest mapping.** OWASP ASI controls are `maps`; anything borrowed (OWASP APTS, EU AI Act art. 12) is `adapted`. No conformance claimed.
- **Tested contracts.** Exit codes, SARIF, Action YAML and every fixture's verdict, on Python 3.10–3.12.

Roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md) · Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md)

## License

Apache-2.0 © 2026 Kunko AI Labs
