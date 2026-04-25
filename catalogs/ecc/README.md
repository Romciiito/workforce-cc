# ECC catalog

Mirror of selected entries from [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code), redistributed under MIT.

## Layout

- `index.json` — metadata for every entry, schema in [`../schema.json`](../schema.json).
- `bodies/` — the actual markdown files (agents, skills, commands). Populated by `scripts/catalog_sync.py`.
- `LICENSE` — upstream MIT license.

## How entries get here

Entries are added by running:

```bash
python3 scripts/catalog_sync.py --from /path/to/everything-claude-code/clone
```

The sync script:
1. Reads agent / skill / command files from the upstream clone.
2. Parses frontmatter for `name`, `description`.
3. Writes one body per entry into `bodies/`.
4. Updates `index.json` with the entry metadata + content hash.

It never deletes existing entries unless `--prune` is passed; entries that disappear upstream are flagged but kept.

## Per-project allowlist

The 290 entries are NOT auto-installed into `~/.claude/`. A project's `/workforce` run reads `index.json`, recommends a subset based on the project's stack, and writes only the *enabled* entries to `catalogs/workforce/enabled.json` after user confirmation. See [`../workforce/enabled.json`](../workforce/enabled.json).

## Drift detection

`scripts/catalog_check.py --check-drift` re-reads upstream and compares each entry's content hash against `index.json`. Drift is reported but not auto-applied — upgrades are deliberate.

## Attribution

When a workforce-cc project consumes a catalog entry, the project's `decisions.md` records the source attribution:

```
Used catalog entry `ecc.security-reviewer` from affaan-m/everything-claude-code (MIT, commit abc1234) — installed to .claude/agents/security-reviewer.md.
```
