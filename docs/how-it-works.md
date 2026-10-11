# How it works

The model behind the verdicts: what is read, how it is classified, how points are added, and how an organisation tunes it. Nothing here is a black box; every rule is in the source and every number is reproducible by hand.

## The manifest is the promise

Every check consumes the same representation, `agent-assurance/v1`. Written by hand it is a declaration; produced by `scan` it is an observation, with `source: path:line` on every tool.

```yaml
apiVersion: agent-assurance/v1
agent:
  name: support-agent
  version: 1.0.0
framework:
  name: langgraph
tools:
  - name: crm.read
    type: read
    system: crm
  - name: crm.write
    type: write
    system: crm
data:
  - type: pii
    systems: [crm]
autonomy: 2          # a human approves actions
delegation:
  enabled: false
```

Schema: [`schema/agent-assurance.schema.json`](../schema/agent-assurance.schema.json). The manifest is framework-agnostic on purpose: it describes *what the agent may reach*, not how it is built.

## What the scanner understands

**MCP server configs** — `.mcp.json` (Claude Code), `.cursor/mcp.json`, `.gemini/settings.json`, `.vscode/mcp.json`, `.codex/config.toml` (Codex CLI). Each server becomes a system. Its access classes come from the catalogue entry for its package or name (e.g. `@modelcontextprotocol/server-github` → read, write). A remote `url` is network egress; an `env`/`headers` name that looks like a credential is credential access (the value is never read). The same server declared for several hosts counts once. A server not in the catalogue is `UNKNOWN`.

**Claude Code permissions** — `.claude/settings.json` and `settings.local.json`. Claude Code's built-in tools exist whether or not they are listed; a rule decides whether a **human approves** the call. So `allow` = runs without approval, `ask` = a person confirms, `deny` = removed. Precedence: deny > ask > allow. Rules collapse per capability class: ten `allow: Bash(...)` rules are one shell grant, not ten.

| Rule | Class | Notes |
|---|---|---|
| `Read`, `Glob`, `Grep`, `LS`, `WebFetch`, `WebSearch` | read | |
| `Edit`, `Write`, `MultiEdit`, `NotebookEdit` | write | +2 points if `allow` and unscoped |
| `Bash`, `Bash(*)` | execute, unscoped | +2 points if `allow`; breaks a promise of autonomy ≤ L2 |
| `Bash(git status:*)`, `Bash(grep:*)`, `Bash(ls:*)`… | read (scoped) | read-only commands are not "the agent runs shell unattended" |
| `Bash(find:*)`, `Bash(git diff:*)`, `Bash(rg:*)`, `Bash(env:*)`… | execute (scoped) | these commands run programs or write files with some options (`find -exec`, `git diff --output`, `rg --pre`, `env <cmd>`); only an exact rule whose every option only reads is a read |
| a rule with `;`, `&&`, `\|`, `>`, `<`, `$`, backticks or parentheses | execute (scoped) | the rule runs more than the listed command |
| `Bash(npm test:*)`, any other scoped command | execute (scoped) | no auto-approval penalty; AA-002 says *review*, not *broken* |
| `Agent`, `Task` | execute (subagents) | |
| `mcp__<server>__<tool>`, `mcp__<server>` | the server's widest class from the catalogue | a single tool is scoped; a whole server is not |
| `defaultMode: acceptEdits` / `bypassPermissions` | write / execute, auto-approved | |
| anything else, or a rule that does not parse | unknown | scored as write, never as safe |

What the read-only classification assumes and does not see:

- A wildcard rule for a command that reads with any arguments (`Bash(cat:*)`, `Bash(grep:*)`, `Bash(echo:*)`) is a read only because Claude Code refuses to extend a prefix rule over shell operators and redirections (`cat a | sh`, `echo x > ~/.bashrc`) at run time. The scanner checks the rule text, not the text the wildcard later matches.
- Behaviour set by the user's environment or git configuration (pagers, `diff.external`, textconv drivers) is not visible in a rule. `gh … view` and `gh … list` rules allow `--web`, which opens the browser on a GitHub page; this is counted as a read.
- Only a plain command name can be a read: a path, an extension, a version suffix, upper case or non-ASCII (`/usr/bin/find`, `git.exe`, `python3.12`, `LS`, `ſh`) makes the rule execute, and so does `git` followed by a global option (`-c`, `-C`, `--exec-path`).

**Serialized tool definitions** (business agents) — `agent-tools.json|yaml` at the root, plus any file listed in the policy's `tool_definition_files`: OpenAI function tools, OpenAI Agents SDK, MCP tool objects, Claude client tools, LangChain / LangGraph / CrewAI serialized metadata. A tool definition has a name and a description, not an access class, so the class is **inferred** from verbs (`refund` → financial, `delete` → delete, `send` → external_send, `run` → execute, `update` → write, `search` → read; anything else UNKNOWN) and the tool is marked `inferred`. It scores like its class, but AA-002 reports an undeclared inferred class as *review*, never *broken*: a guess must not fail a build. Nothing is imported or executed.

Every scan ends with a **Sources scanned** table: files parsed, files detected but not supported (`AGENTS.md`, `claude_desktop_config.json`), and what was deduced from each. A repo with nothing scannable and nothing declared exits 2 — never an empty PASS.

## The risk model is transparent

Not an "AI risk score". Every point is attributable:

| Property | Points |
|---|---|
| tool `read` / `execute`,`write`,`external_send` / `delete`,`financial` | 1 / 3 / 5 |
| data `pii` / `health`,`financial` / `credential` | 3 / 4 / 5 |
| production system | +5 |
| irreversible action | +5 |
| delegation enabled | +3 |
| autonomy above L2 | +2 per level |
| tool of unknown class (`UNKNOWN`) | 3 (scored as write, never as safe) |
| non-read, unscoped tool auto-approved by the host | +2 |

Bands: LOW `<8` · MEDIUM `<16` · HIGH `<28` · CRITICAL `>=28`. HIGH → review, CRITICAL → fail (configurable with `--fail-on`). Weights live in one file, [`risk.py`](../src/agent_assurance/risk.py) — and an organisation can override them without forking:

## Organisation policy

`agent-assurance.policy.yaml` next to the manifest (or `--policy`), schema in [`schema/`](../schema/agent-assurance.policy.schema.json):

```yaml
apiVersion: agent-assurance/policy/v1
name: acme-corp-2026-09
weights: { tools: { read: 1, write: 3 }, auto_approval: 2 }   # any subset; defaults fill the rest
bands: { medium: 8, high: 16, critical: 28 }
gate: { review_bands: [MEDIUM], fail_bands: [HIGH, CRITICAL] }  # stricter than default
promise:
  breaking_access: [write, delete, execute, financial]           # external_send only reviews here
  breaking_data: [pii, health, credential]
read_only_commands: [make lint, poetry run pytest]              # added to the built-in list; see below for what it cannot add
catalog:                                                        # your own MCP servers: no longer UNKNOWN
  - system: acme-erp
    aliases: [acme-erp]
    packages: [acme-erp-mcp]
    capabilities: [{ suffix: read, access: read }]
    data: [financial]
    source: "platform team: ERP MCP v2 is read-only"
tool_definition_files: [agents/tools.yaml]
```

`read_only_commands` adds commands that read with any arguments. It is deny by default: an entry counts only if its command name is plain ASCII matching `^[a-z][a-z0-9_-]*$` (no path, extension, version dots, glob or shell syntax) and is outside the refused families: shells, interpreters (`python*`, `node*`, `perl*`…), wrappers that run another command (`env`, `xargs`, `sudo`, `timeout`…), pagers, editors, programs that write their output (`sed`, `tee`, `tar`…), and `find`/`fd`. An entry can never widen a command that has a built-in option allow-list (`find`, `fd`, `rg`, `tree`, `file`, `env`, `git diff/log/show/branch`) or be a bare prefix of a built-in command (`git`, `gh pr`). Every ignored entry is reported, with its reason, by `validate` and in the scan's source notes. The policy file is read from the scanned tree, so a change to it also shows in the report's policy name and sha256.

No policy = the built-in model, exactly (asserted in tests). With a policy, every report, card and attestation records its name and sha256: a verdict is reproducible only with the policy that produced it. Example: [`examples/repos/policy-org`](../examples/repos/policy-org).

## Design rules (what you can rely on)

- **Deterministic.** No LLM anywhere in the verdict. Same input, same output, reproducible by hand.
- **Nothing executed, nothing sent.** Config files are read; MCP servers are never started; secret values are never read, only variable names; no network.
- **Unknown is a result, not a silence.** Unrecognised servers and tools are `UNKNOWN`, score conservatively, and block a "promise kept".
- **Honest standards mapping.** OWASP ASI controls are `maps`; a control borrowed from OWASP APTS (autonomous pentest platforms) or from EU AI Act art. 12 is `adapted`. No conformance is claimed that does not exist.
- **Contracts are tested.** Exit codes, SARIF shape, Action YAML and every fixture's verdict run in CI on Python 3.10–3.12.
