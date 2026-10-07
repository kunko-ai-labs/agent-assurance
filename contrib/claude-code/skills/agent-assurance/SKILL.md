---
name: agent-assurance
description: Verify a project's agent configuration (MCP servers, Claude Code permissions, Codex config, tool definitions) against its declared promise using the same checks the agent-assurance GitHub Action runs. Use when asked to audit agent permissions, check an agent's blast radius, or before/after changing .mcp.json, .claude/settings.json, .codex/config.toml, agent-tools.json, or agent-assurance.yaml.
---

# Agent Assurance — run the checks from inside the coding agent

This skill runs the exact checks the `kunko-ai-labs/agent-assurance` GitHub
Action runs, but locally, from the project you are working in. The CLI is the
same one, the report formats are the same ones, and the exit codes mean the
same things — so a local verdict and the CI verdict are directly comparable.

## 0. Prerequisites

`agent-assurance` must be installed and on `PATH`:

```bash
pipx install agent-assurance
agent-assurance --version
```

Expected output: `agent-assurance 0.6.0` (any version >= the repo's is fine).

Run every command below from the project root.

## 1. Discover the agent configuration in this project

`scan` reads these files, exactly as the Action does in scan mode. Check which
ones exist before you run anything — the list tells you where the agent's
reach is declared:

| File | What it grants the agent |
|---|---|
| `agent-assurance.yaml` | The declared promise: agent name, autonomy level (L0–L4), tools, data |
| `agent-assurance.policy.yaml` | Organisation policy (auto-discovered next to the manifest) |
| `.mcp.json` | MCP servers for Claude Code |
| `.cursor/mcp.json` | MCP servers for Cursor |
| `.gemini/settings.json` | MCP servers for Gemini CLI |
| `.vscode/mcp.json` | MCP servers for VS Code |
| `.claude/settings.json`, `.claude/settings.local.json` | Claude Code permission rules (allow/ask/deny, defaultMode) |
| `.codex/config.toml` | MCP servers for Codex |
| `agent-tools.json`, `agent-tools.yaml`, `agent-tools.yml` | Serialized tool definitions |

Two files are recognised but reported as "detected, not supported" rather
than parsed: `AGENTS.md` (instructions, not permissions) and
`claude_desktop_config.json` (user scope, not a repo file).

If the manifest is hand-written, sanity-check it first:

```bash
agent-assurance validate ./agent-assurance.yaml
```

Expected output on success: `ok: ./agent-assurance.yaml is a valid
agent-assurance/v1 manifest` plus a one-line summary (agent name, autonomy,
tool and data counts).

## 2. Run the checks — the same commands the Action runs

The Action resolves every mode to one CLI invocation; run the same one
locally. For a working tree this is almost always `scan`:

```bash
agent-assurance scan . --check all --format md --fail-on fail
```

- `scan .` observes the repo's agent configuration and verifies it against
  `./agent-assurance.yaml` when the file exists.
- `--check all` runs every registered check (`blast-radius`, i.e. AA-001, and
  `declared-vs-observed`, i.e. AA-002). Pass `--check blast-radius` to run one.
- `--format md` renders the same Markdown the Action posts to the job
  summary and (in diff mode) to the PR comment. Alternatives: `json` for
  machines, `sarif` for code-scanning tools, `html` for a one-page card.
- `--fail-on fail` (the Action default) exits 1 only on FAIL. Use
  `--fail-on review` to also gate on REVIEW.

When the promise file exists and you want the manifest alone, without
observing the repo:

```bash
agent-assurance check all ./agent-assurance.yaml --format md --fail-on fail
```

For a pull request, compare the two trees the way the Action's diff mode
does (it checks the base out into a worktree; locally any two directories
work):

```bash
agent-assurance diff /tmp/aa-base . --fail-on-delta --format md
```

Machine-readable output for follow-up tooling:

```bash
agent-assurance scan . --check all --format json --output aa-report.json
agent-assurance scan . --check all --format sarif --output aa.sarif
```

Exit codes are the Action's contract: **0** = PASS or REVIEW (nothing gated),
**1** = the gate tripped (FAIL, or REVIEW with `--fail-on review`),
**2** = usage or manifest error — never a verdict.

If there is nothing to scan (no supported config file and no manifest), the
command exits 2 with "error: nothing to scan" — that is expected, not a bug.

## 3. Read the scorecard in plain language

The markdown report starts with one verdict line, which is the **worst**
check result: FAIL beats REVIEW beats PASS.

- `✅ **AGENT ASSURANCE PASSED**` — every check is within the promise. Safe
  to merge on this evidence alone.
- `⚠️ **AGENT ASSURANCE — REVIEW RECOMMENDED**` — something needs a human
  look but nothing is known-broken. Typical causes: an MCP server not in the
  catalogue (classified UNKNOWN), or a capability inferred from a name rather
  than observed. Read the check details, decide, then either scope the config
  or accept the risk explicitly.
- `❌ **AGENT ASSURANCE FAILED**` — a check is red. Do not merge until it is
  fixed or the promise is deliberately updated.

Then one section per check:

**AA-001 — Blast Radius.** A transparent, rule-based score of how much damage
the agent could do, with its bands: LOW (0+), MEDIUM (8+), HIGH (16+),
CRITICAL (28+). No LLM is in the scoring path. The details list the affected
systems, the sensitive data classes touched, which capabilities run without
human approval, and the declared autonomy level. A high band is not a moral
judgement — it is a number you either accept in the promise or reduce in the
config.

**AA-002 — Declared vs Observed.** Compares what the config files grant
against what `agent-assurance.yaml` declares. Every `BROKEN` line names the
exact file and line, for example:

```
- BROKEN — `claude-code.shell[Bash(*)]` runs **without human approval**, but declared autonomy is L2 (.claude/settings.json:7)
```

The `<details>` block at the end lists every source file scanned, whether it
was parsed or only detected, and one line of notes per file — start there if
a result surprises you.

## 4. Point at the fix, then re-run

Match the failure to the fix:

- **AA-002 promise broken by a permission rule** — either tighten the config
  (scope `Bash(*)` down to read-only commands, remove
  `defaultMode: bypassPermissions`, move secrets out of `env`) or, if the
  wider reach is intended and approved, update `agent-assurance.yaml` so the
  promise says what the config does. A promise you do not mean is worse than
  no promise.
- **AA-001 band higher than you want** — the band follows the config, not the
  manifest: reduce the grants (fewer auto-approved write/execute rules,
  narrower MCP servers) until the score lands where you want it.
- **REVIEW on an unknown server or inferred class** — add the server to your
  organisation catalogue (via `agent-assurance.policy.yaml`) or scope the
  rule to the tools you actually need.
- **Manifest error (exit 2)** — run
  `agent-assurance validate ./agent-assurance.yaml`; the error names the
  offending field.

After each fix, re-run the scan. The gate is green when the exit code is 0
under the same `--fail-on` the Action uses.

If this plugin was installed with its hook, every future edit to an agent
configuration file is checked automatically after the edit — the hook feeds
the verdict back as an error in the same turn, so regressions are caught at
the keystroke, not at the PR.
