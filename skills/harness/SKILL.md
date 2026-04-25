---
name: harness
description: >
  Apply or refresh harness adapter files (.claude/, .cursor/, AGENTS.md,
  GEMINI.md, .opencode/) for the current project. Triggers on /harness,
  "add cursor support", "regenerate harness adapters", "switch harness".
  Read-only against project source code; writes only the adapter files
  declared in harnesses/<name>/manifest.json. Useful when adopting a new
  harness mid-project, or when a Foundation scaffold ran before
  install.sh wrote ~/.workforce-harnesses.
---

# /harness — Apply harness adapters

You are a thin wrapper around `scripts/harness_install.py`. Your job is to figure out which harnesses the user wants for **this project** and apply each adapter once. You do not orchestrate; you do not write anything outside what the manifests declare.

## When to trigger

- `/harness` (no args) — apply every harness in `~/.workforce-harnesses`.
- `/harness claude` / `/harness cursor,codex` — apply specific harnesses regardless of the beacon.
- "add cursor support" → `/harness cursor`.
- "regenerate the AGENTS.md" → `/harness codex`.
- "I switched my install profile, refresh adapters" → `/harness` reads the new beacon.

## When NOT to trigger

- The harness adapter files are already correct and the operator just wants to *check* the current state. Use `cat` directly, or run `/harness --dry-run`.
- The user wants to install a harness globally (write `~/.claude/agents/` etc.). That's `install.sh`'s job, not this skill's.

## Procedure

### Step 1 — Resolve the harness list

Three sources, first match wins:

1. **Skill arguments** — `/harness claude,cursor` overrides everything.
2. **`~/.workforce-harnesses`** — the beacon written by `install.sh`.
3. **Default `claude`** — if neither exists.

### Step 2 — Validate

For each requested harness, check `harnesses/<name>/manifest.json` exists. If any is missing, halt and surface:

```
Unknown harness: <name>
Available: claude, cursor, codex, opencode, gemini
```

### Step 3 — Apply

```bash
FOUNDATION_ROOT=$(cat ~/.foundation-path)
PROJECT_NAME=$(<derive from CLAUDE.md or current directory name>)
STACK=$(<derive from docs/claude/architecture.md or stack-decision.md>)

for harness in $HARNESSES; do
  python3 "$FOUNDATION_ROOT/scripts/harness_install.py" \
    --harness "$harness" \
    --project-dir . \
    --project-name "$PROJECT_NAME" \
    --stack "$STACK" \
    --description "$(<one-line from CLAUDE.md or vision.md>)"
done
```

For `--dry-run`, pass the flag through.

### Step 4 — Surface results

Print a summary:

```
HARNESS ADAPTERS — applied to .
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✓ claude   → CLAUDE.md, .claude/agents/, .claude/settings.local.json
  ✓ cursor   → .cursor/rules/00-workforce-cc.mdc, .cursor/rules/01-...
  ✓ codex    → AGENTS.md
  ⊘ opencode → not requested
  ⊘ gemini   → not requested

Beacon: ~/.workforce-harnesses → claude,cursor,codex
```

If the operator added a harness not in the beacon (`/harness codex` when beacon = `claude,cursor`), ask whether to update the beacon:

```
The beacon ~/.workforce-harnesses is currently 'claude,cursor'. You just
applied 'codex' adapters which aren't in the beacon. Update the beacon
to 'claude,cursor,codex'? (y/n)
```

If `y`, write the new value. If `n`, the adapters are still applied to this project; future scaffolds won't include codex.

## Edge cases

- **No `~/.foundation-path`**: install.sh wasn't run. Print install command and exit.
- **No `CLAUDE.md` and no project context**: harness adapters need at least a project name + stack. Halt and recommend running `/foundation` first.
- **Adapter for a harness already exists with different content**: the manifest's `overwrite` flag controls behavior. For `overwrite: true` entries (like `CLAUDE.md`), the file is overwritten silently — the adapter is the source of truth. For `overwrite: false` (e.g. `.claude/agents/*`), the file is skipped and a `=` marker appears in output.
- **Stack-specific permissions in `.claude/settings.local.json`**: regenerated only if the file doesn't exist. To force a regeneration, delete the file first or run with `--force` (not yet wired through; future enhancement).

## Rules

- Apply only the harnesses requested. Never silently install all five.
- Never modify project source code. Adapters write under `.claude/`, `.cursor/`, project root (`AGENTS.md` / `GEMINI.md`), and `.opencode/`. Anything else is out of scope.
- The skill is idempotent. Re-running `/harness cursor` against a project that already has `.cursor/rules/*.mdc` re-renders them (the manifest has `overwrite: true` for `.mdc` adapters).
- For dry-run, pass `--dry-run` to `harness_install.py` and print what *would* be applied.
- Beacon updates are opt-in; never silently rewrite `~/.workforce-harnesses` without confirmation.
