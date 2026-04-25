# ADR 003 — Catalogs as folder mirrors, not git submodules

**Status**: Accepted (Chunks 2, 17)

## Context

The 290-entry [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code) catalog (48 agents + 183 skills + 59 commands) is too large to hand-write into the repo. We needed a way to reference it that:

1. Survives if upstream disappears or breaks.
2. Lets users pin specific versions.
3. Doesn't require operator intervention on a fresh clone.
4. Allows per-project allowlists rather than a global "install everything" model.

The MCP catalog (Chunk 17) has the same shape but smaller — six entries and growing.

## Decision

Each catalog is a folder under `catalogs/<source>/`:

```
catalogs/ecc/
├── index.json          ← metadata + provenance hash per entry
├── bodies/             ← actual markdown files (synced from upstream)
├── README.md           ← attribution + usage
└── LICENSE             ← upstream license, redistributed
```

Sync happens via `scripts/catalog_sync.py --from /path/to/upstream-clone`. The script:
- Reads agents/skills/commands from the upstream clone.
- Writes one body file per entry into `bodies/<kind>/<id>.md`.
- Updates `index.json` with content hash for drift detection.
- Preserves user-side overrides via `_overrides.json`.

Per-project allowlist: `catalogs/workforce/enabled.json`. Empty by default; the conductor reads it when extending the engineer pool.

## Consequences

**Easier:**
- Fresh clones work without `--recursive`.
- Pin per-entry by content hash; `catalog_check.py drift` reports upstream changes without auto-applying.
- Offline reproducibility: every project's runs can replay against the committed snapshot.
- Multiple catalogs (ECC, MCP, future) follow identical shape.

**Harder:**
- Repo size grows as catalogs are vendored. Mitigation: bodies are markdown; total impact is small.
- Sync requires a local upstream clone the operator has to maintain.

**Accepted:**
- Some drift between upstream and our mirror is inevitable. `catalog_check.py drift` surfaces it; the operator decides when to upgrade.

## Alternatives considered

- **Git submodule.** Rejected: submodules break on fresh clones that forget `--recursive`. The sync script is the single entry point so the workflow is the same on first run as on every subsequent run.
- **Fetch on demand from upstream.** Rejected: makes installation network-dependent and breaks reproducibility.
- **Auto-install everything from the catalog.** Rejected: 290 entries is too many for the model to hold coherently in one session; some entries are domain-specific (e.g. defi-amm-security) and would be noise for most projects.

## Sources

- everything-claude-code's `mcp-servers.json` shape — index + body + use_when bullets.
- build-your-own-x's curation gate — every entry must declare a license; we enforce this in the ISSUE_TEMPLATE.
