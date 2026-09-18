# Roadmap

What shipped, what is next, and why. Issues on GitHub are the live backlog; this file is the narrative.

| Version | What | Why |
|---|---|---|
| v0.2 (done) | `scan` for MCP configs + Claude Code permissions; AA-002 declared vs observed | The manifest becomes an attestation |
| v0.3 (done) | `diff` base vs head; Action `mode: diff` with PR comment; MCP server + hook; Cursor/Gemini/VS Code configs | The promise is enforced where the change happens |
| v0.4 (done) | **Attestation** per commit/release: in-toto statement, Sigstore-signed via `actions/attest` | Evidence that survives the repo — what AI Act art. 12 and SOC 2 reviewers actually ask for |
| v0.5 (done) | **Capability card** (HTML), **organisation policy** (weights, gate, promise semantics, own catalogue), Codex `config.toml`, serialized tool definitions with inferred classes | Readable outside the repo; tunable without forking; business agents, not only coding agents |
| v0.5.1 (done) | First PyPI release through Trusted Publishing; release pipeline with Sigstore build provenance; every action pinned by SHA; OpenSSF Scorecard, CodeQL, Dependabot | The repo is public: supply-chain hygiene has to be visible, not promised |
| next | Verified Sigstore signing in CI once public; `gh attestation verify` walkthrough; more catalogue entries from real-world scans; a `--baseline` to accept a known state | Adoption feedback decides the order |

Runtime governance (intercepting calls, approvals, ledgers) is a different product and stays out of scope here: this tool checks what the repo says the agent can do, and holds it to its word.
