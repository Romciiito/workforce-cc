# ADR 004 — Install profiles + legacy `--only` flag

**Status**: Accepted (Chunk 9)

## Context

Pre-rebuild, `install.sh` had three modes (`--only foundation`, `--only workforce`, both). After Chunks 3 + 9 added orchestrator agents, hooks, and the catalog system, the install surface grew. Operators wanted to install only the parts they used — e.g. a project that just wants `/sync` doesn't need any agents at all.

## Decision

Introduce **profiles** — declarative JSON files under `profiles/<name>.json` that list which skills, agent packs, and hooks an install activates:

```json
{
  "name": "minimal",
  "description": "Just /sync; no agents, no hooks.",
  "skills": ["sync"],
  "agent_packs": [],
  "hooks": []
}
```

Four ship by default: `full` (everything), `foundation` (greenfield), `workforce` (audit), `minimal` (sync only).

`install.sh --profile <name>` reads the JSON, walks the listed packs, and writes `~/.workforce-profile` so the hook dispatcher knows which hooks to fire.

The legacy `install.sh --only foundation|workforce|both` flag is preserved unchanged. Default behavior (no flag) is identical to `--profile full`.

## Consequences

**Easier:**
- Adding a new "Minimal but with one agent" profile is a JSON file, no shell change.
- Hooks can be selectively enabled per profile (`governance` only in full + workforce, etc.).
- Operators can `cat profiles/<name>.json` to see exactly what they'll get before running install.
- `--dry-run` shows the planned actions without writing.

**Harder:**
- Two entry points (`--only` and `--profile`) until the legacy flag is removed.
- Profile JSON schema needs to be kept in sync with directory structure (`agent_packs` enum lists `_shared`, `orchestrators`, `foundation`, `workforce`).

**Accepted:**
- Profile + `--only` will both exist for at least one release. Tests pin both surfaces.

## Alternatives considered

- **Drop `--only` and force migration.** Rejected: too many existing install instructions in third-party docs and tutorials reference `--only`. Cost of preserving the flag is one if-else branch.
- **Auto-detect profile from directory contents.** Rejected: fragile; operators sometimes want explicit minimal installs even when a project root looks empty.
- **One install with a runtime feature flag.** Rejected: install-time selectivity is the right place to gate cost. Runtime flags add latency to every spawn.

## Sources

- everything-claude-code's `--profile core|developer|security|research|full` flag. Their profiles are richer (manifest-driven with state tracking); ours are simpler — just declarative JSON, no manifest layer. Easier to reason about; sufficient for the current scope.
