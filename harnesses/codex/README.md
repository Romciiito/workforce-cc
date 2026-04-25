# codex harness adapter

Codex CLI (OpenAI's terminal-native coding tool) reads `AGENTS.md` at the project root as canonical context. The adapter writes a single AGENTS.md that:

- Identifies the project + stack + env prefix.
- Lists where to find canonical workforce-cc artifacts.
- Documents behavioral rules.
- Recommends switching to Claude Code for orchestration tasks.

**Limitations:** Codex doesn't run the workforce-cc orchestrators. AGENTS.md surfaces context only.

**Why one file?** Codex's AGENTS.md format is intentionally single-file. We don't fight the harness's idioms.
