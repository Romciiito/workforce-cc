# The workforce-cc rebuild — narrative

This document tells the story of how workforce-cc went from a two-skill monorepo (`/foundation` + `/workforce` with monolithic orchestrators) to a six-skill, five-harness, three-role architecture across 36 commits. It complements [`docs/decisions/`](decisions/) — the ADRs document *individual* load-bearing decisions in isolation; this document tells the *arc* so a future maintainer can understand how the pieces compose.

For the current architecture see [`docs/architecture.md`](architecture.md). For how to use the system see [`docs/running-a-session.md`](running-a-session.md). This document is for the maintainer asking "why is this the way it is?"

---

## Starting point

`workforce-cc` was a Claude-Code skill repo with two slash commands:

- `/foundation` — Socratic brainstorm → parallel analysis → architecture → workplan → scaffold → activate orchestrator.
- `/workforce` — scan an existing project → score 5 dimensions → conditionally spawn agents → write missing docs.
- Plus `/sync` — a 5-second read-only health summary.

Two orchestrator agents (`foundation-orchestrator`, `workforce-orchestrator`) drove each pipeline. They were monolithic — input gating, decomposition, dispatch, integration, drift checking all in one prompt.

The repo was archived on GitHub (read-only). Initial work was a bug-fix branch: post-rebrand path bugs, test coverage from zero, an `env_prefix` scaffold bug that was silently corrupting CI YAML for python stacks. That work landed as commit `c42e40f` — 46 tests as the baseline.

---

## The architectural shift (Chunks 1–12)

The user wanted a fundamentally different system. Each engineer-agent should run in its own terminal with its own 1M context window, communicating only through artifacts on disk. The single orchestrator becomes three roles. Skills become thin wrappers over a shared spine. We borrow patterns from five reference repos (agent-dispatch, everything-claude-code, claude-code-system-prompts, leaked Claude Code source, build-your-own-x) — patterns only, code-style and verbatim-source kept clean.

**Chunks 1-2 (foundations):**
- Chunk 1: Artifact contract. One single source of truth — `docs/artifact-contract.md` declaring every artifact, its owner, its readers, its required headings. `scripts/workforce_paths.py` becomes the read-shim for orchestration artifacts (stored under `.workforce/`) vs engineer outputs (stored at project root).
- Chunk 2: Catalog scaffolding. `catalogs/ecc/` mirrors affaan-m/everything-claude-code; `scripts/catalog_sync.py` populates it on demand; `catalogs/workforce/enabled.json` is the per-project allowlist.

**Chunks 3-5 (the spine):**
- Chunk 3: Three orchestrator agent definitions land in `agents/orchestrators/`:
  - `intent-validator` (Opus, blocking) — Socratic input gate. Refuses to dispatch until `intent.md` is falsifiable. Three modes: greenfield, revision, pass-through.
  - `conductor` (Opus, three sub-modes: dispatch / monitor / integrate) — never authors deliverables, manages by defining and enforcing interfaces. 3-iteration convergence cap.
  - `alignment-guard` (Opus, two modes: vision / cross-check) — PASS / PASS-WITH-NOTES / BLOCK. HIGH severity → BLOCK mechanically.
- Chunk 4: `pipeline_runner.py` rewrite. New SpawnPayload + StatusRecord dataclasses, envelope template (`_envelope.md.jinja`), status polling (`status` and `blocked-scan` subcommands). Strictly additive — every existing test stays green.
- Chunk 5: `skills/_backbone/BACKBONE.md` + four templates document the canonical Validator → Conductor → Guard pipeline as a reusable spine.

**Chunks 6-7 (wiring the skills):**
- Chunk 6: `/foundation` gets Phase -1 (intent-validator, blocking) before Phase 0 brainstorm, and Phase 3.6 (alignment-guard, blocking on HIGH) before Phase 4 build-team activation.
- Chunk 7: `/workforce` gets Phase 0.5 (intent-validator, conditional) and Phase 4.5 (alignment-guard, advisory). Conservative-by-design: a BLOCK in workforce surfaces required actions; doesn't auto-revert.

**Chunks 8-10 (deprecation + profiles + governance):**
- Chunk 8: Deprecation headers on the four legacy orchestrators (`foundation-orchestrator`, `workforce-orchestrator`, `vision-keeper`, `output-validator`). `scripts/migrate_legacy_orchestrators.py` rewrites installed copies as shims, idempotently and reversibly.
- Chunk 9: `install.sh --profile` (full / foundation / workforce / minimal) + `--dry-run`. Hook dispatcher (`hooks/dispatcher.sh`) with `governance.sh` and `config-protection.sh` — profile-gated, unconditionally callable.
- Chunk 10: catalog wiring + governance hook integration. Conductor reads `catalogs/workforce/enabled.json` to extend the engineer pool with catalog entries. Each orchestrator agent fires `dispatcher.sh fire governance ...` after major decisions; the dispatcher silently no-ops if governance isn't in the active profile.

**Chunks 11-12 (engineer-with-judgment):**
- Chunk 11: `pipeline_runner.spawn` defaults to envelope rendering. `--legacy-prompt` opt-out preserves the pre-Chunk-11 one-liner for back-compat.
- Chunk 12: First wave of engineer prompt-style upgrades. `architect`, `security-analyst`, `requirements-engineer` — adversarial self-critique block + read-only constraint block, role-tailored.

By the end of Chunk 12 the system has a complete spine, three orchestrator roles, profile-gated install, hooks, catalogs, and engineer-with-judgment shape on the most-used analysis engineers.

---

## The fill-out (Chunks 13–25)

The skeleton is complete; now fill it out.

**Chunks 13-15 (docs + extending the prompt-style + the bug-fix workflow):**
- Chunk 13: README + architecture.md + how-it-works.md refreshed for the new spine.
- Chunk 14: Engineer-with-judgment shape extends to nine more agents (the Foundation analysis pool + workforce engineers).
- Chunk 15: Execution-trace methodology in `templates/workflows/bug-fix.md` — pattern from agent-dispatch. Every bug fix now produces a five-field trace (entry-point → call-chain → root-cause → fix-site → verification) before any fix discussion.

**Chunks 16-17 (more borrows):**
- Chunk 16: `hooks/observe.sh` — post-tool-use observation hook. JSONL audit trail of every tool call. Pattern from everything-claude-code's continuous-learning.
- Chunk 17: MCP catalog (`catalogs/mcp/`). Six seed servers (github / postgres / fetch / memory / sequential-thinking / filesystem-extra). `scripts/mcp_query.py` for list / show / emit. ADR 010 documents the separate-namespace decision.

**Chunks 18-19 (multi-terminal ergonomics):**
- Chunk 18: `pipeline_runner.py dispatch-wave --from .workforce/dispatch.md --wave N` parses the conductor's dispatch document and fires every engineer in the wave with one command. ADR 011 captures why the parser reads markdown directly rather than per-engineer JSON sidecars.
- Chunk 19: `/sync` skill refresh — peeks at `.workforce/` orchestration state, surfaces alignment-report status, prioritises a fresh BLOCK over the lowest health-score dimension.

**Chunks 20-21 (build agents + walkthrough):**
- Chunk 20: Engineer-with-judgment shape extends to the six build-agent jinja templates (backend / frontend / devops / test-writer / code-reviewer / debugger). Every Foundation-bootstrapped project now ships build agents with the same discipline as the analysis pool.
- Chunk 21: `docs/running-a-session.md` walks through the full multi-terminal flow with concrete commands. Test pin every relative-path link.

**Chunks 22-23 (catalog + routing wiring):**
- Chunk 22: Foundation Phase 2.5 surfaces MCP suggestions filtered by stack.
- Chunk 23: agent-router knows about the orchestrator roles + catalog allowlist + adds Rule 0 (vague request → intent-validator) + Rule 3.5 (multi-engineer → conductor) + Rule 3.6 (drift → alignment-guard).

**Chunks 24-25 (license + integration test):**
- Chunk 24: LICENSE at repo root (was overdue) + scaffold templates absorb the new orchestration artifact pointers. CLAUDE.md.jinja env_prefix moves from a brittle `{{ project_name | upper | replace }}` chain to the `{{ env_prefix }}` variable scaffold already provides.
- Chunk 25: End-to-end integration test for all 7 stacks. Caught a real bug — microservices' docker-compose.yml had a triple-brace `${{{ env_prefix }}_...}` Jinja-confusing pattern that `render_string()` was silently swallowing. Fixed.

---

## The polish + multi-harness (Chunks 26–36)

The system now works end-to-end. The remaining chunks document, extend, and demonstrate.

**Chunks 26-29 (record-keeping + permissions + slim wrappers):**
- Chunk 26: ADR catalog (`docs/decisions/`) — 8 ADRs documenting the load-bearing decisions of Chunks 1-25.
- Chunk 27: `permission_mode` (default / plan / auto / bypass) per dispatched engineer. Pattern from leaked Claude Code source. ADR 012 captures why four modes (not one bool, not per-tool maps).
- Chunk 28: catalog license-allowlist gate. `catalog_check.py validate` now enforces redistributable licenses before structural checks.
- Chunk 29: `/perf` slash skill — slim wrapper around performance-analyst. Mirror of /sync in spirit (single agent, surface output, exit). Pattern: any high-leverage single engineer can become a slim wrapper skill.

**Chunks 30-32 (multi-harness):**
- Chunk 30: Multi-harness shipping framework. `harnesses/<name>/manifest.json` declares what files each adapter writes; `scripts/harness_install.py` applies a manifest to a project. Five harnesses: `claude` (first-class) + `cursor` / `codex` / `opencode` / `gemini` (context-only — they surface workforce-cc artifacts but don't run orchestrators). ADR 009 documents the framework.
- Chunk 31: Foundation Phase 3 reads `~/.workforce-harnesses` and applies non-claude adapters automatically. New projects scaffolded after `install.sh --harnesses claude,cursor,codex` get all three adapter files.
- Chunk 32: `/harness` slash skill — re-apply or refresh harness adapters on existing projects, mid-flight. Beacon updates are opt-in (project-scope action shouldn't silently change global state).

**Chunks 33-36 (rounding out):**
- Chunk 33: `running-a-session.md` updated for /perf, /harness, multi-harness selection.
- Chunk 34: Engineer-with-judgment shape applied to the two remaining meta-agents (model-selector, agent-router). Pattern is now complete across all 18 non-orchestrator agents + 6 build-agent templates + 3 orchestrator agents.
- Chunk 35: `/security` slash skill — security-analyst wrapper. Symmetric partner to /perf. Six skills total now.
- Chunk 36: README skills table updated to reflect six skills. ADRs 010-012 written for chunks that warranted them but didn't have one.

---

## How the borrows landed

Mapping from the original five reference repos to where their patterns ended up:

| Source | Pattern | Where it landed |
|---|---|---|
| **claude-code-system-prompts** | 4-phase coordinator | conductor sub-modes (Chunk 3) |
| | Adversarial self-critique paragraph | Every engineer + orchestrator + build-agent template (Chunks 3, 12, 14, 20, 34) |
| | Read-only constraint block | Every engineer + intent-validator + alignment-guard (same chunks) |
| | "Your entire value is in the last 20%" | alignment-guard's framing (Chunk 3) |
| **agent-dispatch** | Execution traces | bug-fix workflow + debugger template (Chunks 15, 20) |
| | Pipeline gates (PASS/BLOCK) | alignment-guard semantics (Chunk 3) |
| | Convergence loop with iteration cap | conductor 3-iteration cap (Chunk 3) |
| | Escalating retry tiers | RetryTier enum (NARROW/BROAD/FRESH) (Chunk 4) |
| | Per-agent task doc with territory | dispatch.md schema + envelope template (Chunks 4, 5) |
| | BLOCKED detection | status polling + BLOCKED.md per engineer (Chunk 4) |
| **everything-claude-code** | Install profiles | profiles/full|foundation|workforce|minimal (Chunk 9) |
| | Hook dispatcher with profile gating | hooks/dispatcher.sh (Chunk 9) |
| | governance + config-protection hooks | hooks/governance.sh + config-protection.sh (Chunk 9) |
| | continuous-learning observation | hooks/observe.sh (Chunk 16) |
| | MCP catalog shape | catalogs/mcp/ (Chunk 17) |
| | Multi-harness shipping | harnesses/ adapter framework (Chunk 30) |
| **leaked Claude Code source** | Tool schema with permission state | SpawnPayload field shape (Chunk 4) |
| | Multi-mode permission resolution | permission_mode (default/plan/auto/bypass) (Chunk 27) |
| | Config migrations pattern | migrate_legacy_orchestrators.py (Chunk 8) |
| **build-your-own-x** | `[**Stack**]` tag prefix | catalog index entry tags (Chunk 2) |
| | Link-checker workflow | .github/workflows/link-check.yml (Chunk 2) |
| | ISSUE_TEMPLATE for catalog contributions | .github/ISSUE_TEMPLATE/catalog-entry.yml (Chunk 2) |
| | Curation gate | catalog_check.py license-allowlist (Chunk 28) |

Code is original throughout. Where a pattern came from a closed-license source (the leaked Claude Code material), only the *shape* and *semantics* were borrowed; the implementation is fresh.

---

## What we deliberately didn't do

- **Hard-remove the legacy orchestrators.** ADR 007 covers the deprecation strategy. Removing files would break installs that hardcode the old names; deprecation headers + `migrate_legacy_orchestrators.py` give operators a clean migration path on their own schedule.
- **Replicate orchestrators per harness.** ADR 009 covers this. Cursor / Codex / Gemini / opencode don't have agent-runner runtimes equivalent to Claude Code's. The non-Claude adapters are explicitly context-only, telling the harness to recommend Claude Code for orchestration.
- **Auto-detect installed harnesses.** Predictability matters more than convenience; `--harnesses` and the beacon are explicit.
- **Auto-install all 290 ECC catalog entries.** ADR 003 covers this. Per-project allowlist via `catalogs/workforce/enabled.json` keeps the install lean.
- **Threats-as-prompt-engineering ("I will pull the plug on your session").** The user explicitly preferred verification commands + structured outputs + escalating retry over operator-catharsis-dressed-as-prompt-engineering. The borrow from agent-dispatch took only the structural ideas (gates, retry, traces), not the threatening tone.

---

## Where to go next (post-rebuild)

Real-world usage will surface what's missing. Likely directions:

- **More slim-wrapper skills** as patterns emerge (`/threat-model`, `/design-review`, `/audit-deps`).
- **Auto-mode classifier** from claude-code-system-prompts — useful for `/workforce` deciding conservative-vs-aggressive.
- **Demo project** as a visual reference of what `/foundation` produces.
- **Self-audit recursion** — workforce-cc's CI runs `/sync` against itself periodically.
- **Expanded MCP catalog** as more servers stabilise upstream.
- **Graduating non-Claude harness adapters** from context-only to full orchestration as harnesses gain agent-runner capabilities.

---

## Test surface

The rebuild ships with **716 pytest tests** distributed across:

- Script-level tests (scaffold, health-score, pipeline_runner, telemetry, catalog_sync, catalog_check, catalog_query, mcp_query, harness_install, migrate_legacy, spawn_payload, etc.)
- Agent prompt-style tests (every engineer + build-agent + orchestrator + meta-agent has structural-invariant tests for the engineer-with-judgment shape)
- SKILL.md tests (every skill has SKILL.md content tests)
- Doc tests (artifact-contract.md, ADR catalog, running-a-session.md pointers, README structural checks)
- Harness adapter tests (manifest sanity + adapter rendering for all 5 harnesses + install.sh integration)
- End-to-end integration (scaffold for all 7 stacks + scaffold-with-harnesses)
- Hook tests (governance, observe, dispatcher with profile gating)

The test suite caught at least four real bugs during the rebuild: the original env_prefix scaffold corruption, the microservices triple-brace, an install.sh agent-collision-check that didn't exist before being demanded by the test, and the dispatcher's bash-3.2 compatibility for older macOS.

---

## Pointers

- [`docs/architecture.md`](architecture.md) — current architecture (the *what*).
- [`docs/running-a-session.md`](running-a-session.md) — operator walkthrough (the *how*).
- [`docs/artifact-contract.md`](artifact-contract.md) — every artifact's owner, readers, schema.
- [`docs/decisions/`](decisions/) — 12 ADRs (the *why* per decision).
- This document — the *narrative* (the *why* of the whole arc).

For PR review, read in this order: README → this document → ADR catalog (skim titles) → architecture.md → running-a-session.md → drill into any ADR or chunk-specific commit message that catches your eye.
