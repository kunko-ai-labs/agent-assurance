---
name: "📚 Catalogue entry (MCP server)"
about: "A server came out UNKNOWN and you know what it can do — give us the sourced entry"
title: "[CATALOG] server-name"
labels: ["type:catalog", "area:scan", "priority:low", "status:todo", "good first issue"]
assignees: ""
---

<!--
╔══════════════════════════════════════════════════════════════════════════════╗
║  📚 CATALOGUE ENTRY — how to use this template                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  The catalogue (src/agent_assurance/scan/catalog.py) maps well-known MCP      ║
║  servers to capability classes. Every entry cites its source. UNKNOWN is      ║
║  safe but noisy; a sourced entry turns a guess into a fact.                   ║
║  Rule: when unsure between two classes, choose the wider one and say why.     ║
╚══════════════════════════════════════════════════════════════════════════════╝
-->

## 📦 Server

| Field | Value |
|-------|-------|
| **Package / command** | exactly as it appears in `args` / `command` / `url` |
| **Common config names** | e.g. `github`, `gh` |
| **Transport** | stdio / http / sse |
| **Source (URL + date)** | README or tool list you read |

## 🔑 Capabilities

| Class | Tools that justify it | Irreversible? |
|-------|-----------------------|---------------|
| read | | |
| write | | |
| delete | | |
| execute | | |
| external_send | | |
| financial | | |

## 🗄️ Data classes reached

`internal` / `pii` / `credential` / `financial` / `health` / `public` — and why.

## ✅ Acceptance

- [ ] `CatalogEntry` added with `source`
- [ ] One case in `tests/test_scan.py::test_catalog_lookup`
- [ ] `ruff check src tests && pytest -q` green
