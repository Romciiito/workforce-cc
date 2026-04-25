# Deprecated agents

This directory exists to receive the four legacy orchestrator agents once the migration is complete:

- `foundation-orchestrator.md` — superseded by `agents/orchestrators/conductor.md`.
- `workforce-orchestrator.md` — superseded by `agents/orchestrators/conductor.md`.
- `vision-keeper.md` — superseded by `agents/orchestrators/alignment-guard.md` (vision mode) and `agents/orchestrators/intent-validator.md` (Mode A creation).
- `output-validator.md` — superseded by `agents/orchestrators/alignment-guard.md` (cross-check mode).

## Current state

The four legacy files are still in place at:

- `agents/foundation/foundation-orchestrator.md`
- `agents/workforce/workforce-orchestrator.md`
- `agents/workforce/vision-keeper.md`
- `agents/foundation/output-validator.md`

Each has a **deprecation header** appended pointing to the new role. Both skills (`/foundation`, `/workforce`) still invoke them at their existing phases — this is the "coexist for one release" period from the implementation plan. After at least one release of real-world use of the new orchestrators, the legacy files will be physically moved into this directory and reduced to thin shim bodies (one paragraph each, redirecting to the new role).

## Migration policy

**Source repository (this repo)**: legacy files stay in their original locations until the legacy phases are dropped from the SKILL.md files. That cleanup happens in a later chunk, not this one.

**User-installed copies (`~/.claude/agents/`)**: when the migration is run by `scripts/migrate_legacy_orchestrators.py`, any installed legacy agent file is rewritten in place to a thin shim that redirects the user to the new role. The script is idempotent and never deletes — it only rewrites.

## Why deprecate rather than remove

- Users who pinned a specific agent name in their workflows would have their setup silently break on a hard remove.
- The new orchestrators have less production usage; if a regression appears, the legacy agents are still available as a fallback.
- Each legacy agent's prompt-engineering know-how (e.g. vision-keeper's drift-detection logic) is being absorbed into the new orchestrators incrementally rather than rewritten from scratch.

## When does the physical move happen

The physical move (legacy files → `agents/deprecated/`) is gated on these conditions:

1. The new orchestrators have been used in at least three real `/foundation` runs and three `/workforce` runs without major regression.
2. `output-validator`'s cross-check responsibilities are fully covered by `alignment-guard --mode=cross-check` (currently they only partially overlap).
3. `vision-keeper`'s create mode (Mode A) is fully covered by `intent-validator` (currently they're parallel implementations).

Until those conditions hold, deprecation is **header-only**, not file movement.
