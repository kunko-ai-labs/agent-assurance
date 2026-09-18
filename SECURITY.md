# Security policy

Agent Assurance reads configuration files and never executes them, never starts an MCP server, never reads a secret's value and makes no network calls. If you find a way to make it do any of those things, or a way to make it report PASS for something it should flag, that is a security issue.

**Report privately:** open a [GitHub security advisory](https://github.com/kunko-ai-labs/agent-assurance/security/advisories/new). Please include a minimal repo or config that reproduces it. You will get a reply within 7 days.

**Not security issues (open a normal issue):** an MCP server missing from the catalogue, a rule classified in a way you disagree with, a false positive on a scoped `Bash` rule. Those are model questions and we want them in the open.

Supported: the latest minor release (`vX.Y`). Fixes ship as a patch on it.
