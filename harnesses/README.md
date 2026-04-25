# Harness adapters

Each harness directory contains the files that workforce-cc deploys into a project to make the harness aware of the system. Different harnesses read different files (Claude Code reads `CLAUDE.md`; Cursor reads `.cursor/rules/*.mdc`; Codex reads `AGENTS.md`; etc.). The harness adapter layer keeps the workforce-cc *content* canonical (one source of truth in `templates/CLAUDE.md.jinja`) and renders harness-specific *files* on top.

| Directory | Harness | Reads | Status |
|---|---|---|---|
| `claude/` | Anthropic Claude Code | `CLAUDE.md`, `.claude/agents/`, `.claude/settings.local.json` | First-class |
| `cursor/` | Cursor IDE | `.cursor/rules/*.mdc` (each sub-rule a separate file) | Adapter shim |
| `codex/` | OpenAI Codex CLI | `AGENTS.md` (single file) | Adapter shim |
| `opencode/` | opencode (open-source CLI) | `.opencode/agents/*.md`, `opencode.json` | Adapter shim |
| `gemini/` | Google Gemini CLI | `GEMINI.md`, `.gemini/agents/` | Adapter shim |

## Adapter shape

Each harness directory ships:

- `manifest.json` — what files this adapter writes, their target paths in a project, and any harness-specific transforms.
- `README.md` — quick notes on the harness's quirks (which env vars matter, how it discovers agents, whether it supports MCP).
- Optional: harness-specific templates (e.g. `cursor/rules.template.mdc`, `codex/AGENTS.template.md`) that map workforce-cc concepts onto the harness's idioms.

## How adapters get installed

`install.sh --harnesses claude,cursor` resolves to a list of harness directories. For each, the installer reads `manifest.json` and:

1. Renders the harness's templates with the same context (`{{ project_name }}`, `{{ env_prefix }}`, the orchestrator role list, etc.) that drives the canonical `CLAUDE.md.jinja`.
2. Writes the rendered files into the project at the paths the manifest declares.
3. Copies any agent-pool subset the harness understands.

Selection happens two ways, with `--harnesses` winning over the profile:

```bash
./install.sh --profile full --harnesses claude        # claude only
./install.sh --profile workforce                      # uses profile's "harnesses" list
./install.sh --harnesses claude,cursor,codex          # explicit, ignores profile
```

If a profile doesn't declare `harnesses`, the default is `["claude"]` — workforce-cc was originally a Claude Code skill set and the legacy install behavior is preserved.

## What stays canonical, what's harness-specific

**Canonical (lives once in workforce-cc, never duplicated per harness):**

- All agent prompts (`agents/orchestrators/`, `agents/_shared/`, `agents/foundation/`, `agents/workforce/`).
- The artifact contract (`docs/artifact-contract.md`).
- The backbone documentation (`skills/_backbone/`).
- Catalogs (`catalogs/ecc/`, `catalogs/mcp/`).
- Hooks (`hooks/`).

**Harness-specific (lives in `harnesses/<name>/`):**

- Where the harness expects to find agents (`.claude/agents/` vs `.cursor/rules/` vs `AGENTS.md`).
- How the harness expects rules to be formatted (Markdown with frontmatter vs `.mdc` chunks).
- Which features of workforce-cc the harness can use (Claude Code: full orchestration; Codex: just AGENTS.md context; etc.).

## Adding a new harness

1. Create `harnesses/<name>/`.
2. Write `manifest.json` declaring the files this harness writes.
3. Add the harness to `profiles/schema.json`'s `harnesses` enum.
4. Add tests under `tests/test_harness_<name>.py`.
5. Update `harnesses/README.md` (this file) with the harness's row in the table.

## Deferred

Per the original plan, multi-harness was deferred. This chunk delivers the **adapter framework** — a `manifest.json`-driven installer plus stub adapters for Cursor/Codex/opencode/Gemini. The stub adapters write a single AGENTS-equivalent file pointing at the canonical workforce-cc docs; full per-harness orchestration (e.g. opencode's own agent runner) is a future deepening, not a prerequisite. Operators using non-Claude harnesses get *context* about the workforce-cc system; orchestration still requires Claude Code today.
