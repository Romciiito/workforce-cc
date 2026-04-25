# cursor harness adapter

Cursor reads `.cursor/rules/*.mdc` files (one rule per file, with optional metadata frontmatter). The adapter writes:

- `.cursor/rules/00-workforce-cc.mdc` — always-on rule with project identity, where to find canonical context, behavioral rules, and when to switch to Claude Code.
- `.cursor/rules/01-orchestration-pointers.mdc` — non-always-on rule activated by architecture/intent/alignment requests.

**Limitations:** Cursor doesn't run the workforce-cc orchestrators (intent-validator / conductor / alignment-guard). For orchestration the user must switch to Claude Code. The adapter explicitly tells Cursor when to recommend the switch.

**Why two rule files?** Cursor's MDC rules system supports both always-on and conditional rules. The 00-prefix rule is short (project context) and always loaded; the 01-prefix rule is the heavier orchestration-pointer doc and only activates when needed. This keeps Cursor's context window focused.
