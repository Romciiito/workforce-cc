# claude harness adapter

First-class. workforce-cc was originally a Claude Code skill set, so this is the deepest integration:

- **Rules file**: `CLAUDE.md` rendered from `templates/CLAUDE.md.jinja`. Includes the workforce-cc behavioral rules, pointer table to `docs/claude/`, gotchas, project-specific rules from `claude-rules.md`, and pointers to `.workforce/intent.md` / `dispatch.md` / `alignment-report.md`.
- **Agents directory**: `.claude/agents/` populated from the four agent packs (`orchestrators`, `_shared`, `foundation`, `workforce`).
- **Settings**: `.claude/settings.local.json` with stack-appropriate `permissions.allow` entries.

No special quirks — every workforce-cc feature works.
