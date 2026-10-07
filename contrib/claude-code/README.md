# Claude Code integration

Four ways to put the promise in front of the agent itself, not only in front
of the reviewer. They are the same checks the GitHub Action runs — the skill
below resolves to the exact CLI invocations in `action.yml`, so a local
verdict and the CI verdict are directly comparable.

## 1. Plugin — skill + hook in one install (recommended)

`contrib/claude-code/` is a Claude Code plugin. Installing it gives you:

- the **agent-assurance skill** (`skills/agent-assurance/SKILL.md`): discovers
  the agent configuration in the current project, runs the checks locally
  with the same CLI the Action uses, and explains the scorecard in plain
  language with pointers to fixes;
- the **PostToolUse hook** (`aa-post-edit.sh`), registered automatically: the
  agent learns the moment an edit breaks the promise, in the same turn.

Inside Claude Code:

```text
/plugin marketplace add kunko-ai-labs/agent-assurance
/plugin install agent-assurance@kunko-ai-labs
```

Requires `agent-assurance` on `PATH` (`pipx install agent-assurance`). Once
installed, ask for it directly ("run the agent-assurance skill on this
repo") or let it trigger on its description when you touch agent config
files.

## 2. Skill only, without the plugin

Copy the skill file into a skills directory Claude Code reads:

```bash
mkdir -p ~/.claude/skills/agent-assurance
cp contrib/claude-code/skills/agent-assurance/SKILL.md ~/.claude/skills/agent-assurance/
```

Use `<repo>/.claude/skills/agent-assurance/SKILL.md` instead if the skill
should travel with the project rather than with your account. Requires
`agent-assurance` on `PATH` (`pipx install agent-assurance`).

## 3. PostToolUse hook — the agent learns the moment it breaks the promise

`aa-post-edit.sh` runs after every `Edit`/`Write`. If the file is an agent-configuration file and the repo's promise is now broken, the hook exits 2 with the verdict, which Claude Code hands back to the agent as an error to act on.

The plugin (option 1) registers this hook automatically. Without the plugin,
add it to `.claude/settings.json` in the target repo:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          { "type": "command", "command": "/path/to/agent-assurance/contrib/claude-code/aa-post-edit.sh" }
        ]
      }
    ]
  }
}
```

Requires `agent-assurance` on `PATH` (`pipx install agent-assurance`).

Reference: Claude Code hooks documentation (https://docs.claude.com/en/docs/claude-code/hooks), read on 2026-09-17. Hook input arrives as JSON on stdin with `tool_input.file_path`; exit code 2 returns stderr to the model. Plugin layout follows the Claude Code plugin documentation (https://docs.claude.com/en/docs/claude-code/plugins).

## 4. MCP server — the agent asks before it widens itself

```bash
pip install "agent-assurance[mcp]"
claude mcp add agent-assurance -- agent-assurance-mcp
```

Tools exposed: `scan`, `check`, `would_break`. With the server's instructions loaded, an agent that is about to add an MCP server or a permission rule can call `would_break` first and see, in the same shape as the PR comment, whether the change breaks `agent-assurance.yaml`. Nothing is written; the change is simulated in a temporary copy.
