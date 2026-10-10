"""Curated catalogue of well-known MCP servers and what they can do.

`.mcp.json` only names a server; the tools it exposes are discovered at runtime.
We refuse to run servers to find out, so the access class comes from this
transparent, versioned table instead. Every entry cites where the classification
comes from (the package or repo whose README lists the tools). If a server is
not here, it is UNKNOWN — the report says so, and a PR adding it here is the fix.

Matching is by package name first (exact, from `args`/`command`), then by a
substring of the server's configured name. Package match wins because names are
free-form ("gh", "github-prod"), packages are not.

Catalogue version: 2026-09-20.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .. import policy
from ..manifest import DataClass, ToolAccess


@dataclass(frozen=True)
class Capability:
    suffix: str  # tool name suffix -> "<server>.<suffix>"
    access: ToolAccess
    irreversible: bool = False


@dataclass(frozen=True)
class CatalogEntry:
    system: str
    capabilities: tuple[Capability, ...]
    data: tuple[DataClass, ...] = ()
    packages: tuple[str, ...] = ()  # npm/pypi package names as they appear in args
    aliases: tuple[str, ...] = ()  # substrings matched against the server name
    source: str = ""  # where the classification comes from


R, W, D, X, S, F = (
    ToolAccess.READ,
    ToolAccess.WRITE,
    ToolAccess.DELETE,
    ToolAccess.EXECUTE,
    ToolAccess.EXTERNAL_SEND,
    ToolAccess.FINANCIAL,
)

CATALOG: tuple[CatalogEntry, ...] = (
    # --- reference servers (modelcontextprotocol/servers) --------------------
    CatalogEntry(
        system="filesystem",
        capabilities=(Capability("read", R), Capability("write", W), Capability("move", W)),
        packages=("@modelcontextprotocol/server-filesystem",),
        aliases=("filesystem", "fs"),
        source="github.com/modelcontextprotocol/servers/tree/main/src/filesystem",
    ),
    CatalogEntry(
        system="git",
        capabilities=(Capability("read", R), Capability("commit", W), Capability("reset", D)),
        packages=("mcp-server-git",),
        aliases=("git",),
        source="github.com/modelcontextprotocol/servers/tree/main/src/git",
    ),
    CatalogEntry(
        system="web",
        capabilities=(Capability("fetch", R),),
        packages=("mcp-server-fetch", "@modelcontextprotocol/server-fetch"),
        aliases=("fetch",),
        source="github.com/modelcontextprotocol/servers/tree/main/src/fetch",
    ),
    CatalogEntry(
        system="memory",
        capabilities=(Capability("read", R), Capability("write", W)),
        packages=("@modelcontextprotocol/server-memory",),
        aliases=("memory",),
        source="github.com/modelcontextprotocol/servers/tree/main/src/memory",
    ),
    CatalogEntry(
        system="reasoning",
        capabilities=(Capability("think", R),),
        packages=("@modelcontextprotocol/server-sequential-thinking",),
        aliases=("sequential-thinking", "sequentialthinking"),
        source="github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking",
    ),
    CatalogEntry(
        system="time",
        capabilities=(Capability("now", R),),
        packages=("mcp-server-time",),
        aliases=("time",),
        source="github.com/modelcontextprotocol/servers/tree/main/src/time",
    ),
    # --- archived reference servers (still widely installed) -----------------
    CatalogEntry(
        system="github",
        capabilities=(
            Capability("read", R),
            Capability("write", W),  # create/update files, issues, PRs
            Capability("push", W),
        ),
        data=(DataClass.INTERNAL,),
        packages=("@modelcontextprotocol/server-github", "github-mcp-server"),
        aliases=("github", "gh"),
        source="github.com/github/github-mcp-server (tools: create_or_update_file, push_files, create_issue, ...)",
    ),
    CatalogEntry(
        system="gitlab",
        capabilities=(Capability("read", R), Capability("write", W)),
        packages=("@modelcontextprotocol/server-gitlab",),
        aliases=("gitlab",),
        source="github.com/modelcontextprotocol/servers-archived/tree/main/src/gitlab",
    ),
    CatalogEntry(
        system="slack",
        capabilities=(Capability("read", R), Capability("post_message", S)),
        data=(DataClass.INTERNAL,),
        packages=("@modelcontextprotocol/server-slack",),
        aliases=("slack",),
        source="github.com/modelcontextprotocol/servers-archived/tree/main/src/slack (slack_post_message)",
    ),
    CatalogEntry(
        system="postgres",
        capabilities=(Capability("query", R),),
        data=(DataClass.INTERNAL,),
        packages=("@modelcontextprotocol/server-postgres",),
        aliases=("postgres", "postgresql", "pg"),
        source="github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres (read-only query)",
    ),
    CatalogEntry(
        system="sqlite",
        capabilities=(Capability("query", R), Capability("write", W)),
        data=(DataClass.INTERNAL,),
        packages=("mcp-server-sqlite",),
        aliases=("sqlite",),
        source="github.com/modelcontextprotocol/servers-archived/tree/main/src/sqlite (write_query, create_table)",
    ),
    CatalogEntry(
        system="browser",
        capabilities=(Capability("navigate", R), Capability("click", X)),
        packages=("@modelcontextprotocol/server-puppeteer", "@playwright/mcp"),
        aliases=("puppeteer", "playwright", "browser"),
        source="github.com/microsoft/playwright-mcp (browser_click, browser_type: acts on the web)",
    ),
    CatalogEntry(
        system="web",
        capabilities=(Capability("search", R),),
        packages=("@modelcontextprotocol/server-brave-search",),
        aliases=("brave", "brave-search"),
        source="github.com/modelcontextprotocol/servers-archived/tree/main/src/brave-search",
    ),
    CatalogEntry(
        system="gdrive",
        capabilities=(Capability("read", R),),
        data=(DataClass.INTERNAL,),
        packages=("@modelcontextprotocol/server-gdrive",),
        aliases=("gdrive", "google-drive"),
        source="github.com/modelcontextprotocol/servers-archived/tree/main/src/gdrive (read-only)",
    ),
    CatalogEntry(
        system="sentry",
        capabilities=(Capability("read", R),),
        packages=("mcp-server-sentry",),
        aliases=("sentry",),
        source="github.com/modelcontextprotocol/servers-archived/tree/main/src/sentry",
    ),
    CatalogEntry(
        system="redis",
        capabilities=(Capability("get", R), Capability("set", W), Capability("delete", D)),
        packages=("@modelcontextprotocol/server-redis",),
        aliases=("redis",),
        source="github.com/modelcontextprotocol/servers-archived/tree/main/src/redis",
    ),
    # --- third-party, high-impact ---------------------------------------------
    CatalogEntry(
        system="stripe",
        capabilities=(
            Capability("read", R),
            Capability("create_payment_link", F),
            Capability("refund", F, irreversible=True),
        ),
        data=(DataClass.FINANCIAL,),
        packages=("@stripe/mcp",),
        aliases=("stripe",),
        source="github.com/stripe/agent-toolkit (modelcontextprotocol: create_refund, create_payment_link)",
    ),
    CatalogEntry(
        system="aws",
        capabilities=(Capability("read", R), Capability("write", W), Capability("delete", D, irreversible=True)),
        data=(DataClass.CREDENTIAL,),
        packages=("awslabs.aws-api-mcp-server", "@aws/mcp"),
        aliases=("aws",),
        source="github.com/awslabs/mcp (aws-api-mcp-server: call_aws executes arbitrary AWS CLI)",
    ),
    CatalogEntry(
        system="aws-docs",
        capabilities=(Capability("search", R), Capability("read", R)),
        packages=("aws-knowledge-mcp-server", "awslabs.aws-documentation-mcp-server"),
        aliases=("aws-knowledge", "aws-docs", "aws-documentation"),
        source="github.com/awslabs/mcp (aws-knowledge-mcp-server: documentation search, read-only)",
    ),
    CatalogEntry(
        system="docs",
        capabilities=(Capability("resolve-library", R), Capability("get-docs", R)),
        packages=("@upstash/context7-mcp",),
        aliases=("context7",),
        source="github.com/upstash/context7 (resolve-library-id, get-library-docs: read-only)",
    ),
    CatalogEntry(
        system="todoist",
        capabilities=(Capability("read", R), Capability("write", W), Capability("delete", D)),
        data=(DataClass.PII,),
        packages=("@doist/todoist-mcp", "todoist-mcp"),
        aliases=("todoist",),
        source="github.com/Doist/todoist-mcp (add/update/complete/delete tasks)",
    ),
    CatalogEntry(
        system="notion",
        capabilities=(Capability("read", R), Capability("write", W)),
        data=(DataClass.INTERNAL,),
        packages=("@notionhq/notion-mcp-server",),
        aliases=("notion",),
        source="github.com/makenotion/notion-mcp-server",
    ),
    CatalogEntry(
        system="linear",
        capabilities=(Capability("read", R), Capability("write", W)),
        packages=("mcp-remote linear",),
        aliases=("linear",),
        source="linear.app/docs/mcp (create/update issues)",
    ),
    CatalogEntry(
        system="atlassian",
        capabilities=(Capability("read", R), Capability("write", W)),
        data=(DataClass.INTERNAL,),
        packages=("mcp-atlassian",),
        aliases=("atlassian", "jira", "confluence"),
        source="github.com/sooperset/mcp-atlassian (jira_create_issue, confluence_update_page)",
    ),
    CatalogEntry(
        system="email",
        capabilities=(Capability("read", R), Capability("send", S)),
        data=(DataClass.PII,),
        packages=("@gongrzhe/server-gmail-autoauth-mcp",),
        aliases=("gmail", "email", "mail"),
        source="npm @gongrzhe/server-gmail-autoauth-mcp (send_email)",
    ),
    # --- AI/agent data platforms (US-001-001) -------------------------------
    CatalogEntry(
        system="supabase",
        capabilities=(Capability("read", R), Capability("write", W), Capability("execute", X)),
        data=(DataClass.INTERNAL,),
        packages=("@supabase/mcp-server-supabase",),
        aliases=("supabase",),
        # Read-only is opt-in: `readOnly` excludes mutating tools only when set,
        # and defaults to false (package README + supabase.com/mcp).
        source="supabase.com/mcp + @supabase/mcp-server-supabase README (readOnly defaults to false), read 2026-09-20",
    ),
    CatalogEntry(
        system="cloudflare",
        capabilities=(
            Capability("read", R),
            Capability("write", W),
            Capability("delete", D, irreversible=True),
        ),
        data=(DataClass.INTERNAL,),
        packages=("@cloudflare/mcp-server-cloudflare",),
        aliases=("cloudflare",),
        source="github.com/cloudflare/mcp-server-cloudflare README (read account configuration and apply suggested changes; Workers bindings, R2, ...), read 2026-09-20",
    ),
    CatalogEntry(
        system="web",
        capabilities=(Capability("scrape", R), Capability("search", R)),
        packages=("firecrawl-mcp",),
        aliases=("firecrawl",),
        source="github.com/firecrawl/firecrawl-mcp-server README (scrape, map, crawl, search, parse, research; read-only search profile), read 2026-09-20",
    ),
    CatalogEntry(
        system="web",
        capabilities=(Capability("search", R), Capability("extract", R)),
        packages=("tavily-mcp",),
        aliases=("tavily",),
        source="github.com/tavily-ai/tavily-mcp README (tavily-search, tavily-extract, map, crawl), read 2026-09-20",
    ),
    CatalogEntry(
        system="web",
        capabilities=(Capability("search", R), Capability("fetch", R)),
        packages=("exa-mcp-server",),
        aliases=("exa",),
        source="github.com/exa-labs/exa-mcp-server README (web_search_exa, web_fetch_exa; optional agent_run), read 2026-09-20",
    ),
)


def _norm(s: str) -> str:
    return s.lower().replace("_", "-")


def _tokens(name: str) -> set[str]:
    """'my-slack-bot' -> {'my', 'slack', 'bot'}; whole name is a token too."""
    n = _norm(name)
    return {n} | {t for t in re.split(r"[-.\s/]+", n) if t}


def _policy_entries() -> tuple[CatalogEntry, ...]:
    return tuple(
        CatalogEntry(
            system=e.system,
            capabilities=tuple(Capability(c.suffix, c.access, c.irreversible) for c in e.capabilities),
            data=tuple(e.data),
            packages=tuple(e.packages),
            aliases=tuple(e.aliases),
            source=e.source,
        )
        for e in policy.current().catalog
    )


def lookup(server_name: str, command_line: str) -> CatalogEntry | None:
    """Find the catalogue entry for a server, or None (-> UNKNOWN).

    Organisation entries from the active policy are consulted first, so a
    team can name its own servers without forking the built-in table.
    """
    entries = _policy_entries() + CATALOG
    cl = _norm(command_line)
    for entry in entries:
        for pkg in entry.packages:
            if _norm(pkg) in cl:
                return entry
    tokens = _tokens(server_name)
    # Longest alias first so "brave-search" wins over a shorter alias; token
    # matching (not substring) keeps "digital" from matching "git".
    candidates = sorted(
        ((alias, entry) for entry in entries for alias in entry.aliases),
        key=lambda t: -len(t[0]),
    )
    for alias, entry in candidates:
        if _norm(alias) in tokens:
            return entry
    return None
