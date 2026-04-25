# ADR 007 — Deprecation headers, not file removal

**Status**: Accepted (Chunk 8)

## Context

Four legacy orchestrator-style agents (`foundation-orchestrator`, `workforce-orchestrator`, `vision-keeper`, `output-validator`) were superseded by the three new orchestrator roles (Chunk 3). The plan called for moving them to `agents/deprecated/`. But Chunks 6 and 7 wired `/foundation` and `/workforce` to keep invoking the legacy agents at their existing phases — both pipelines depend on them for one release.

Physically moving the files mid-rebuild would break the SKILL.md references and force the rebuild's other chunks into a redesign.

## Decision

Two-stage deprecation:

**Stage A (now, Chunk 8):** legacy files stay in `agents/foundation/` and `agents/workforce/`. Each gets a prominent `## ⚠ Deprecation notice` header pointing to its replacement role. `agents/deprecated/README.md` documents the migration policy and the gating conditions for the physical move.

**Stage B (future):** when (1) the new orchestrators have been used in at least three real `/foundation` runs and three `/workforce` runs without major regression, AND (2) `output-validator`'s cross-check responsibilities are fully covered by `alignment-guard --mode=cross-check`, AND (3) `vision-keeper`'s create mode is fully covered by `intent-validator` — then the legacy files physically move into `agents/deprecated/` with a thin shim body redirecting to the new role.

For users with **installed copies** of the legacy agents in `~/.claude/agents/`, [`scripts/migrate_legacy_orchestrators.py`](../../scripts/migrate_legacy_orchestrators.py) rewrites them in place to thin shims. The script is idempotent and reversible — each rewrite preserves the original at `<target-dir>/.workforce-backup/<filename>.bak`.

## Consequences

**Easier:**
- No SKILL.md changes during the deprecation window.
- Users who hardcoded the legacy agent names in their workflows keep working.
- The migration script gives operators an opt-in path before Stage B.
- Reversibility: Stage A is a header edit; trivial to revert.

**Harder:**
- Deprecation headers are markdown — they catch a reader's eye but don't programmatically prevent invocation.
- Legacy agents and their replacements coexist for one release; there's a brief window where two agents could overlap on the same artifact (e.g. both `output-validator` and `alignment-guard --mode=cross-check` could touch validation flow).

**Accepted:**
- Some users will use the legacy agents indefinitely. The migration script handles their installed copies; the source files stay until Stage B.

## Alternatives considered

- **Hard-remove the four files now.** Rejected: breaks `/foundation` and `/workforce`. The whole point of Chunks 6-7 is to add gates *around* the legacy phases, not replace them.
- **Symlink legacy agent files to the new orchestrator files.** Rejected: confuses users who read the file expecting one thing and find another. Also: the new agents have different `name:` frontmatter; symlinking would break Claude Code's name-based agent resolution.
- **Maintain both indefinitely.** Rejected: doubles the maintenance surface and the user-facing complexity.

## Sources

- Leaked Claude Code source: config-migrations pattern. Their migrations rewrite installed config in place with a backup; we apply the same pattern to agent files.
