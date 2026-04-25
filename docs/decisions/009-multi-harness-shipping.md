# ADR 009 — Multi-harness shipping with selectable adapters

**Status**: Accepted (Chunk 30)

## Context

workforce-cc was originally a Claude Code skill set. Users running other AI-coding-agent harnesses (Cursor, Codex CLI, opencode, Gemini CLI) had no way to surface the workforce-cc artifacts to those harnesses. The first plan chunk for the rebuild deferred multi-harness shipping; a later user request brought it back: *"I would ship the multi harness approach, include it in readme and be able to select at start which harnesses will be used rather than drop those completely."*

The challenge: most non-Claude harnesses can't run the workforce-cc orchestrators (intent-validator / conductor / alignment-guard). They can read context files but lack the agent-spawning runtime. We need the system to surface workforce-cc *context* across harnesses without claiming each harness offers full orchestration.

## Decision

Introduce a **harness adapter layer**:

- `harnesses/<name>/` — one directory per harness, each with a `manifest.json` describing what files the adapter writes and which workforce-cc features the harness supports.
- `harnesses/manifest-schema.json` — JSON Schema for the manifest format.
- `scripts/harness_install.py` — renders adapters into a project per the manifest's `writes` declarations.
- Profile JSON gains a `harnesses` array (default `["claude"]`).
- `install.sh --harnesses claude,cursor,codex,opencode,gemini` overrides the profile's harness list.
- `~/.workforce-harnesses` beacon persists the selection for downstream tooling.

Five harnesses ship in this chunk:

| Harness | Files | Orchestration |
|---|---|---|
| `claude` | `CLAUDE.md`, `.claude/agents/`, `.claude/settings.local.json` | **Full** — runs all orchestrators |
| `cursor` | `.cursor/rules/00-workforce-cc.mdc`, `01-orchestration-pointers.mdc` | Context-only |
| `codex` | `AGENTS.md` | Context-only |
| `opencode` | `.opencode/agents/workforce-cc.md` | Context-only |
| `gemini` | `GEMINI.md` | Context-only |

**"Context-only"** means the adapter writes content telling the harness *what the workforce-cc artifacts are and where to find them*, with explicit instructions to recommend Claude Code when the user wants orchestration. The harness sees the system; it doesn't run it.

Each adapter is a thin Jinja2 template per harness — no per-harness duplication of orchestrator prompts or agent definitions. The canonical artifacts (`agents/orchestrators/`, `docs/artifact-contract.md`, `skills/_backbone/`) stay in workforce-cc; harnesses only get pointers + behavioral rules + the env_prefix etc.

## Consequences

**Easier:**
- Adding a new harness is one directory + manifest + Jinja2 template + a row in `profiles/schema.json`'s enum.
- Users running mixed harnesses (Cursor for in-IDE work, Claude Code for orchestration) get consistent context across both.
- Operators select harnesses at install time — no all-or-nothing trade-off.
- Manifest-driven design means the installer doesn't need per-harness branches.

**Harder:**
- Five Jinja2 templates to keep in sync as workforce-cc's behavioral rules evolve. Mitigation: keep the canonical content in `templates/CLAUDE.md.jinja` and have other templates render the same `env_prefix`, `critical_rules`, etc. context — drift is bounded to the harness-specific framing language.
- Each harness's quirks (Cursor's `.mdc` format vs Codex's single-file `AGENTS.md`) need their own template author. Mitigation: only Claude is "first-class"; the four shim adapters are deliberately thin.

**Accepted:**
- Non-Claude harnesses won't get full workforce-cc functionality this release. They get *context*. Operators who want orchestration use Claude Code; operators who want in-IDE coding use their preferred harness with workforce-cc context loaded.
- The adapters' "recommend Claude Code for orchestration" framing is a value choice. If a future Cursor / Codex release adds agent-runner capabilities equivalent to Claude Code's, we revisit and graduate that adapter from context-only to full.

## Alternatives considered

- **Skip non-Claude harnesses entirely.** Rejected per the user's explicit request.
- **Replicate the orchestrators per harness.** Rejected: would multiply the agent-prompt maintenance surface by 5×, and the non-Claude harnesses don't have the runtime to run them anyway. The shim approach is honest about what each harness can do.
- **Auto-detect installed harnesses (look for `.cursor/`, etc.).** Rejected: an explicit `--harnesses` flag (or profile field) is more predictable; auto-detection would surprise operators who happen to have an old `.cursor/` directory.
- **One unified `AGENTS.md`-style file all harnesses read.** Rejected: `AGENTS.md` is OpenAI's convention; Cursor reads `.cursor/rules/`, not `AGENTS.md`. Each harness has its own discovery rules; we adapt to each.

## Sources

- everything-claude-code's multi-harness shipping pattern (`.claude/`, `.cursor/`, `.codex/`, `.opencode/`, `.gemini/`). Their approach is broader (per-harness configs at the project level); ours is narrower (per-harness adapter manifest in the *shipping* repo, project-side files generated at scaffold time).
- The ESLint / Prettier "config files everywhere" pattern: each tool has its own discovery rules, so each tool gets its own config file. We follow the same multi-tool reality.
