# Backbone

The shared spine that `/foundation` and `/workforce` both run through. Not a user-facing skill — there is no `/backbone` slash-command. This is documentation of the canonical pipeline that the two skills delegate to.

The backbone has three roles, three sub-modes for one of them, and a fixed set of artifact templates. Skills that use the backbone supply two things: an **engineer pool** (which engineer-agents to dispatch) and **trigger conditions** (when to skip phases — e.g. `/workforce` skips the brainstorm-equivalent if `vision.md` already exists).

```
                    ┌──────────────────┐
   user prompt ───► │ Intent Validator │  → .workforce/intent.md
                    └────────┬─────────┘
                             │  (refuses to dispatch until intent.md is falsifiable)
                             ▼
                    ┌──────────────────┐
                    │ Conductor        │  → .workforce/dispatch.md
                    │   --mode=dispatch│
                    └────────┬─────────┘
                             │  (per-engineer contracts; territory; verification)
                             ▼
                ┌────────────┴────────────┐
                │  N engineer terminals    │  each in its own 1M context
                │  (separate tmux windows) │  each writes:
                │   architect              │    runs/<ts>/<engineer>/approach.md
                │   security-analyst       │    <declared output>.md
                │   stack-selector         │    status/<engineer>.json
                │   ...                    │
                └────────────┬─────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Conductor        │  polls status/*.json
                    │   --mode=monitor │
                    └────────┬─────────┘
                             │  (BLOCKED → escalating retry; all-DONE → next gate)
                             ▼
                    ┌──────────────────┐
                    │ Alignment Guard  │  → .workforce/alignment-report.md
                    │   --mode=cross-check│  PASS / PASS-WITH-NOTES / BLOCK
                    └────────┬─────────┘
                             │  (HIGH severity → BLOCK; halt; surface required actions)
                             ▼
                    ┌──────────────────┐
                    │ Conductor        │  → .workforce/integration.md
                    │   --mode=integrate│  (cross-cuts, blocked items, next dispatch)
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Alignment Guard  │  → .workforce/alignment-report.md (vision)
                    │   --mode=vision  │
                    └────────┬─────────┘
                             │  (final drift check vs intent.md)
                             ▼
                          DONE
```

## Roles

The three roles live in `agents/orchestrators/`:

- [`intent-validator.md`](../../agents/orchestrators/intent-validator.md)
- [`conductor.md`](../../agents/orchestrators/conductor.md) — three sub-modes: `dispatch`, `monitor`, `integrate`
- [`alignment-guard.md`](../../agents/orchestrators/alignment-guard.md) — two modes: `vision`, `cross-check`

## Templates

Four canonical artifact templates live alongside this file. Each downstream skill renders these by passing them through the appropriate orchestrator:

- [`intent.template.md`](intent.template.md) — what the Intent Validator writes
- [`dispatch.template.md`](dispatch.template.md) — what the Conductor writes in dispatch mode
- [`integration.template.md`](integration.template.md) — what the Conductor writes in integrate mode
- [`alignment-report.template.md`](alignment-report.template.md) — what the Alignment Guard writes

Templates are **examples + required-section lists**, not Jinja templates that get rendered at runtime. The orchestrator agents read them as references; their actual output is generated freely within the documented schema. The artifact contract (`docs/artifact-contract.md`) is what enforces the schema.

## Spawn contract

Every dispatched engineer terminal receives a [SpawnPayload](../../scripts/spawn_payload.py) JSON, rendered through [`templates/agents/_envelope.md.jinja`](../../templates/agents/_envelope.md.jinja). The engineer:

1. Reads inputs.
2. Writes `runs/<ts>/<engineer>/approach.md`.
3. Executes within declared territory.
4. Writes declared outputs.
5. Runs verification.
6. Writes `status/<engineer>.json` with state DONE | BLOCKED.

The Conductor never spawns an engineer that doesn't fit this contract.

## Engineer pool

A skill that uses the backbone supplies its own engineer pool. The pool is just a list of engineer names — the actual agent files live under `agents/_shared/`, `agents/foundation/`, or `agents/workforce/`.

Today's pools:

- **`/foundation` pool**: `idea-refiner`, `market-researcher`, `security-analyst`, `requirements-engineer`, `architect`, `stack-selector`, `workplan-builder`. Plus `model-selector` and `output-validator` for legacy phases.
- **`/workforce` pool**: `scanner`, `gap-analyst`, `security-analyst`, `architect`, `requirements-engineer`, `doc-writer`, `agent-generator`. Plus `vision-keeper` for legacy phases.

Catalog allowlist (`catalogs/workforce/enabled.json`) extends the pool with entries the project enabled — e.g. `ecc.agent.security-reviewer` becomes available for the conductor to spawn.

## When to skip phases

A backbone-using skill may skip phases based on project state:

| Condition | Skip |
|---|---|
| `intent.md` already exists and matches the current request | `intent-validator` |
| The request is concrete (specific file/bug/feature) | Most engineers — dispatch only the relevant ones |
| No multi-engineer dispatch happens (single agent runs in this terminal) | `monitor` (no parallel terminals to poll) |
| Only one wave; no integration needed | `integrate` (still write `integration.md` for the audit trail, but it's a thin one-paragraph file) |

Skipping is at the skill's discretion. The backbone is a contract, not a script.

## Where artifacts live

Orchestration artifacts live under `.workforce/`. Engineer outputs live at the project root. See [`docs/artifact-contract.md`](../../docs/artifact-contract.md) for the canonical list.

## Adding a skill that uses the backbone

1. Create `skills/<your-skill>/SKILL.md`.
2. In its phase ordering, replace any "orchestrator picks agents" logic with: `intent-validator` → `conductor --mode=dispatch` → engineer pool → `conductor --mode=monitor` → `alignment-guard` → `conductor --mode=integrate` → `alignment-guard --mode=vision`.
3. Define the engineer pool (which agents the conductor may spawn).
4. Document any phases the skill specifically *adds* before/after the backbone (e.g. `/foundation` adds Phase 2 skill suggestions and Phase 3 scaffold after the backbone runs).
5. Don't reinvent the orchestration. The backbone is the canonical spine; downstream skills are domain wrappers.

## Why a backbone

Before this design, `/foundation` and `/workforce` had separate orchestrators (`foundation-orchestrator`, `workforce-orchestrator`) doing similar work in different shapes. Adding a third skill would have meant a third orchestrator. The backbone gives every skill the same spine — input gate, decomposition, dispatch, monitor, integrate, drift check — and lets each skill focus on what makes it different (engineer pool, trigger conditions, post-backbone work).

This is the same pattern Claude Code's coordinator system uses internally (Research → Synthesis → Implementation → Verification): a fixed framework, a variable agent pool. We borrowed the shape, redesigned for our system.
