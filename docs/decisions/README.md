# Architecture Decision Records (ADRs)

A short record of every load-bearing architectural choice made during the workforce-cc rebuild (Chunks 1–25). Each ADR follows the same shape:

- **Status** — Accepted / Superseded / Reverted.
- **Context** — what problem this decision solves and what made it necessary.
- **Decision** — the choice made.
- **Consequences** — what becomes easier, what becomes harder, what we accept.
- **Alternatives considered** — other options and why they were rejected.

ADRs are deliberately short. Anything longer than ~150 lines belongs as a doc, not an ADR.

## Catalog

| # | Title | Status |
|---|---|---|
| [001](001-three-orchestrator-roles.md) | Three orchestrator roles, not one | Accepted |
| [002](002-workforce-directory.md) | `.workforce/` for orchestration artifacts | Accepted |
| [003](003-catalogs-as-folder-mirrors.md) | Catalogs as folder mirrors, not git submodules | Accepted |
| [004](004-install-profiles.md) | Install profiles + legacy `--only` flag | Accepted |
| [005](005-profile-gated-hooks.md) | Hooks are profile-gated and unconditionally callable | Accepted |
| [006](006-engineer-with-judgment.md) | Engineer-with-judgment prompt style | Accepted |
| [007](007-deprecation-headers-not-removal.md) | Deprecation headers, not file removal | Accepted |
| [008](008-multi-terminal-via-files.md) | Multi-terminal communication via files only | Accepted |

## When to write a new ADR

Whenever a new chunk introduces a load-bearing choice — meaning a choice that, if reverted, would require coordinated changes across multiple files. Routine implementation details don't need ADRs.

If you're not sure: write the ADR. The cost of writing it is minutes; the cost of a future contributor having to reverse-engineer the reasoning is hours.
