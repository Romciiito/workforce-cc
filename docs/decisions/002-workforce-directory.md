# ADR 002 — `.workforce/` for orchestration artifacts

**Status**: Accepted (Chunk 1)

## Context

Pre-rebuild, every artifact (vision.md, brainstorm.md, architecture.md, workplan.md, …) lived at the project root. After Chunk 3 introduced the three orchestrator roles, four new artifacts joined the set: `intent.md`, `dispatch.md`, `integration.md`, `alignment-report.md`. Plus per-run scratch (`runs/<ts>/<engineer>/approach.md`, `status/<engineer>.json`, optional `BLOCKED.md`).

Putting all of those at the project root would have:

1. Cluttered the user's view of their own files.
2. Made `.gitignore` discipline harder — `runs/` and `status/` should never be committed; orchestration artifacts at root would need per-file `.gitignore` entries.
3. Confused engineer outputs (which the user wants visible — `architecture.md`) with orchestration outputs (which are infrastructure).

## Decision

Orchestration artifacts live under `<project>/.workforce/`:

```
.workforce/
├── intent.md
├── dispatch.md
├── integration.md
├── alignment-report.md
├── runs/<ts>/<engineer>/approach.md
├── status/<engineer>.json
└── .gitignore                ← excludes runs/ and status/
```

Engineer outputs (`architecture.md`, `spec.md`, `vision.md`, `brainstorm.md`, etc.) **stay at the project root** — they're the user's project, not infrastructure.

A read shim — [`scripts/workforce_paths.py`](../../scripts/workforce_paths.py) — resolves orchestration names from either `.workforce/` (preferred) or the project root (legacy fallback). Existing projects with root-level `vision.md` or `WORKFORCE.md` keep being read.

## Consequences

**Easier:**
- `.gitignore` has one entry: `.workforce/runs/`, `.workforce/status/`. The orchestration artifacts at the top of `.workforce/` are committed automatically as a record of "what we said we were building".
- Engineers can grep the project root for their inputs without false hits from per-run scratch.
- Clean separation: "things that describe the project" (root) vs "things that describe the run" (`.workforce/`).

**Harder:**
- One more directory for new contributors to learn.
- The shim adds a small read overhead; negligible in practice.

**Accepted:**
- `vision.md` and `intent.md` cover overlapping territory for one release. They consolidate when ADR 001's deprecation completes.

## Alternatives considered

- **All artifacts at project root.** Rejected: clutter + .gitignore complexity + confusion of project-vs-run state.
- **Symlink `.workforce/` artifacts to root for backward compat.** Rejected: symlinks fragment on Windows and break on `git clone` mirrors that don't preserve them.
- **Hidden directory `.foundation-runtime/`.** Rejected: too generic; `.workforce/` is project-scoped and self-documenting.

## Sources

- The decision to vendor `.workforce/.gitignore` automatically came from observing real usage of agent-dispatch's `dispatch/` artifacts — operators forgot to add them to .gitignore and committed pile of run logs.
