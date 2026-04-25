# ADR 010 — MCP catalog as a separate namespace

**Status**: Accepted (Chunk 17, extended in Chunk 22)

## Context

Chunk 2 introduced `catalogs/ecc/` for the affaan-m/everything-claude-code mirror. Chunk 17 added MCP server configurations as a second catalog. The question was whether to:

(a) Add MCP entries to the same `catalogs/ecc/index.json`, or
(b) Make MCP a separate `catalogs/mcp/` namespace with its own index.

ECC entries are agents/skills/commands — **prompts and behaviors** that the conductor can dispatch or that engineers can read. MCP entries are **server configurations** that operators install into a project's `.claude/settings.local.json` so a Claude session can call out to the server's tools. Different shape, different consumers.

## Decision

Two separate catalogs, separate JSON Schemas, separate query scripts:

- `catalogs/ecc/index.json` — agents/skills/commands. Schema: `catalogs/schema.json`. Query: `scripts/catalog_query.py`.
- `catalogs/mcp/index.json` — MCP server configs. Schema: `catalogs/mcp-schema.json`. Query: `scripts/mcp_query.py`.

Each catalog has its own `LICENSE` file with appropriate upstream attribution. Entries are added independently; nothing structural is shared between the two beyond the `catalogs/` parent directory.

The MCP catalog ships six seed entries (github, postgres, filesystem-extra, memory, sequential-thinking, fetch) covering the most common needs. New entries follow the same `manifest`-style schema as the Cursor / Codex / etc. harness adapters: declarative, reviewable, license-gated.

Foundation Phase 2.5 (added in Chunk 22) reads `catalogs/mcp/index.json` filtered by stack, presents recommendations to the user, and emits `mcp_query.py emit <id> --apply` per accepted server. The MCP catalog is opt-in throughout — no auto-install.

## Consequences

**Easier:**
- Adding a new MCP server is one entry in `catalogs/mcp/index.json` + (optional) attribution in the catalog's LICENSE. No risk of accidentally affecting the ECC agent allowlist.
- Different schemas evolve independently. ECC entries can grow `tags` and `stacks`; MCP entries grow `category` and `use_when` bullets.
- Two separate query scripts mean operators can search them differently (`catalog_query.py list --kind agent` vs `mcp_query.py list --category database`).

**Harder:**
- Two namespaces to remember. Mitigation: README + ADR cover both; query scripts are named by namespace.
- Cross-catalog references (e.g. an ECC skill that recommends a specific MCP server) require name-spacing. We use the prefix convention: `ecc.agent.<name>`, `mcp.<server-id>`.

**Accepted:**
- Some duplication in test setup (test_catalog_*.py vs test_mcp_catalog.py). Worth it for the schema separation.

## Alternatives considered

- **Single unified catalog** with a `kind` field of `agent | skill | command | mcp`. Rejected: MCP entries' shape (command + args + env + use_when) doesn't fit the agent-style index. Either we'd compromise the schema for both, or we'd put MCP entries inside `extra` blobs.
- **MCP entries embedded in each project's settings.local.json directly, no catalog.** Rejected: every project would re-invent its MCP recommendations from scratch. The catalog gives operators a vetted starting point.
- **Mirror upstream's mcp-servers.json verbatim.** Rejected: their format is broader (HTTP transports, dual-syntax). We started narrower (command-only) and can extend the schema enum if needed.

## Sources

- everything-claude-code's `mcp-servers.json` shape — central config with descriptions, env-var placeholders, command + args. Our schema is narrower; we add `use_when` bullets explicitly so operators see when to install AND when not to.
- The MCP protocol spec itself for server discovery semantics.
