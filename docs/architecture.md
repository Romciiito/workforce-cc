# Architecture — workforce-cc

Three skills, one shared backbone, three orchestrator roles, N engineer terminals. This doc describes how the pieces fit together.

```
                            ~/.claude/skills/
                            ┌─────────────────┐
                            │  foundation  →  │──┐
                            │  workforce   →  │──┼──► skills/<name>/SKILL.md
                            │  sync        →  │──┘    (symlinked from this repo)
                            └─────────────────┘
                                    │
                                    ▼
                          ~/.foundation-path  ──► absolute path to this repo
                          ~/.workforce-profile ──► active install profile (full | foundation | workforce | minimal)
                                    │
        ┌───────────────────────────┼───────────────────────────────┐
        ▼                           ▼                               ▼
    scripts/                    agents/                         skills/_backbone/
  workforce_paths.py        orchestrators/  ← three roles    BACKBONE.md  ← spine doc
  pipeline_runner.py            (intent-validator,           intent.template.md
  spawn_payload.py               conductor,                  dispatch.template.md
  catalog_*.py                   alignment-guard)            integration.template.md
  scaffold.py                  _shared/   ← engineer pool    alignment-report.template.md
  health_score.py              foundation/    (greenfield)
  telemetry.py                 workforce/     (audit)
  migrate_legacy_*.py          deprecated/    (migration policy)

    catalogs/                   templates/                    hooks/
  ecc/{index.json, bodies/}   agents/_envelope.md.jinja     dispatcher.sh
  workforce/enabled.json      agents/<role>.md.jinja        governance.sh
  schema.json                 stacks/<stack>/…              config-protection.sh
                              docs/, github-actions/

    profiles/                   .github/workflows/
  full.json                   test.yml         ← pytest 3.11/3.12/3.13 + shellcheck
  foundation.json             link-check.yml   ← lychee on .md files
  workforce.json
  minimal.json
```

---

## The backbone (spine of every skill)

Every skill flows through the same three-role pipeline:

```
       Intent Validator  →  Conductor[dispatch]  →  N engineer terminals
                                                       (each in its own
                                                        1M context window)
                                  │
                                  ▼
                         Conductor[monitor]  ←──── status/<engineer>.json
                                  │
                                  ▼
                         Alignment Guard      →    alignment-report.md
                                  │
                                  ▼
                         Conductor[integrate] →    integration.md
```

**Intent Validator** — Socratic input gate. Refuses to dispatch until `.workforce/intent.md` has all six required sections (What it is / Who it's for / Concrete success / Constraints / Out of scope / Open questions) with falsifiable content. Three modes: A (greenfield interrogation), B (revision), C (pass-through for concrete requests).

**Conductor** — never authors deliverables. Three sub-modes:
- `dispatch` — decompose intent into independently-completable engineer tasks; write per-task contracts (territory, inputs, outputs, verification, success criteria, escalation) to `.workforce/dispatch.md`.
- `monitor` — poll `.workforce/status/*.json`; surface BLOCKED engineers with retry recommendations (NARROW → BROAD → FRESH escalation, max 3 tiers).
- `integrate` — read engineer artifacts on all-DONE; write `.workforce/integration.md` with cross-cuts, blocked items, and the next dispatch (max 3 convergence iterations per intent).

**Alignment Guard** — gate role. Two modes: `vision` (drift between intent and integrated artifacts) and `cross-check` (consistency between parallel engineer outputs). Returns PASS / PASS-WITH-NOTES / BLOCK. HIGH severity findings produce BLOCK mechanically; the agent does not soften.

The backbone documentation lives in [`skills/_backbone/BACKBONE.md`](../skills/_backbone/BACKBONE.md). The three role definitions live in [`agents/orchestrators/`](../agents/orchestrators/).

---

## Three skills, one pool

| | Foundation pipeline | Workforce pipeline | Shared agents |
|-|--------------------|--------------------|-----------------|
| Backbone gates | Phase -1 (blocking) + Phase 3.6 | Phase 0.5 (conditional) + Phase 4.5 (conditional) | — |
| Analysis | idea-refiner, market-researcher, stack-selector, output-validator, workplan-builder | scanner, gap-analyst, vision-keeper | architect, security-analyst, requirements-engineer, test-strategist, performance-analyst |
| Meta | foundation-orchestrator, model-selector | workforce-orchestrator, doc-writer | agent-generator, agent-router |
| Orchestrator spine (shared) | intent-validator, conductor, alignment-guard | intent-validator, conductor, alignment-guard | — |
| Build (generated per project) | — | — | backend-developer, frontend-developer, devops-engineer, test-writer, code-reviewer, debugger |

The build agents are written **into the project's** `.claude/agents/`, not into `~/.claude/agents/`. That's why `templates/agents/*.md.jinja` exists and why `agent-generator` runs in both pipelines.

The four legacy orchestrator-style agents (`foundation-orchestrator`, `workforce-orchestrator`, `vision-keeper`, `output-validator`) remain in service for one release; they have deprecation headers pointing to their replacements. See [`agents/deprecated/README.md`](../agents/deprecated/README.md) for the migration policy.

---

## The install contract

`install.sh` guarantees:

1. **Profile resolution** — either via `--profile <name>` (reads `profiles/<name>.json`) or legacy `--only foundation|workforce|both`. Default = `both` (== `--profile full`).
2. **Skill symlinks** — `~/.claude/skills/<name>` for each skill in the active profile. Editing a `SKILL.md` here is visible immediately.
3. **Agent copies** — for each pack in the active profile (`_shared`, `orchestrators`, `foundation`, `workforce`), every `.md` is copied into `~/.claude/agents/`. README.md files in pack dirs are skipped.
4. **Beacons**:
   - `~/.foundation-path` — absolute repo path. SKILL.md files read it to locate scripts and templates.
   - `~/.workforce-profile` — active profile name. The hook dispatcher reads it to decide which hooks to fire.
5. **Collision check** — fails fast if two packs ship an agent with the same filename.

Re-runs are idempotent. `--dry-run` previews actions without writing.

---

## Spawn contract

Every dispatched engineer receives a [`SpawnPayload`](../scripts/spawn_payload.py) JSON, rendered through [`templates/agents/_envelope.md.jinja`](../templates/agents/_envelope.md.jinja):

```json
{
  "run_id": ".workforce/runs/2026-04-25T17-00-00Z",
  "engineer": "architect",
  "inputs":  ["intent.md", "spec.md"],
  "outputs": ["architecture.md"],
  "status_file": ".workforce/status/architect.json",
  "deadline_min": 30,
  "retry_tier": "none | narrow | broad | fresh",
  "shared_locks": ["workplan.md"]
}
```

The engineer terminal must write three things:

1. `runs/<ts>/<engineer>/approach.md` — plan-before-action.
2. The declared output(s) — e.g. `architecture.md`.
3. `status/<engineer>.json` — `{state: RUNNING|BLOCKED|DONE, ts, reason?, artifacts}`.

The Conductor's `monitor` mode polls these status files (mtime + JSON parse). On BLOCKED → escalating retry. On all-DONE → invoke Alignment Guard, then `conductor[integrate]`.

The envelope template carries the engineer-with-judgment shape: adversarial self-critique block, read-only constraint on files outside declared territory, BLOCKED.md schema, mandate to write `approach.md` *before* producing outputs. The most-used engineer prompts (`architect`, `security-analyst`, `requirements-engineer`) carry the same shape inline so they preserve the discipline whether dispatched by the conductor or invoked directly.

---

## Pipeline boundaries

**`/foundation` is the creator.** Only runs in empty directories (or ones with nothing but `CLAUDE.md` from `/init`). Adds a Phase -1 (intent-validator, blocking) before brainstorm and a Phase 3.6 (alignment-guard, blocking on HIGH) before the build team is activated. Outputs are write-through: every agent writes a single canonical file, and Phase 3's scaffold never asks permission before overwriting planning docs.

**`/workforce` is the auditor.** Only runs in populated directories. Adds Phase 0.5 (intent-validator, conditional — fires only when the request is vague AND no current `intent.md`/`vision.md` exists) and Phase 4.5 (alignment-guard, conditional and **non-mutating** — surfaces drift but does not auto-revert anyone's work). Outputs are additive: missing docs created, stale docs flagged, never overwrites or deletes.

**`/sync` is the observer.** One Python script, parsed JSON, exit. No agents, no files.

The `agent-generator` is the single point where both pipelines meet — it reads the docs written by either and emits the build team. `create` vs. `diff` mode selects the appropriate behavior.

---

## Cross-skill handoffs

Neither pipeline invokes the other skill automatically. Both **recommend**:

- `foundation-orchestrator` says *"your last Foundation run was 30+ days ago and 40 feature-commits have landed — run `/workforce` to resync the docs"*.
- `workforce-orchestrator` says *"this directory has no CLAUDE.md, no workplan, no docs — `/workforce` is not the right tool here, run `/foundation` instead"*.

The user decides. No state is produced in a session the user didn't explicitly authorize.

---

## Memory, telemetry, and governance

Three layers, all opt-in by default; auto-enabled in multi-terminal mode:

- **`.foundation-memory/telemetry.jsonl`** — per-session breadcrumb trail. `scripts/telemetry.py` records `task-start`, `task-complete`, `task-failed`, `agent-spawn`, `phase-gate-passed`, `decision-recorded`. Auto-enables when `WORKFORCE_MULTI_TERMINAL=1`. Hard opt-out via `WORKFORCE_TELEMETRY=off`.
- **`.foundation-memory/governance.jsonl`** — per-decision audit trail written by `hooks/governance.sh`. The orchestrator agents fire it after dispatch, monitor, integrate, alignment, and intent-validator decisions. Same env-var contract as telemetry.
- **`.workforce/runs/<ts>/`** — per-run scratch space. Each engineer's `approach.md`, optional `BLOCKED.md`, and any per-engineer scratch artifacts. Excluded from version control by `.workforce/.gitignore`.

If neither dir exists and the env var isn't set, all three layers silently no-op.

---

## Extending

- **Adding a stack**: create `templates/stacks/<name>/structure.json`, add it to `STACK_PERMISSIONS` in `scripts/scaffold.py`, add recommended skills to `skill-catalog.json`, reference it in `skills/foundation/SKILL.md` Phase 1B.
- **Adding a shared engineer**: drop the `.md` into `agents/_shared/`; re-run `./install.sh --force`. Make it conform to the engineer-with-judgment shape (adversarial self-critique + read-only block). Register it in `agent-router.md`.
- **Adding an orchestrator role**: don't, unless you've thought hard. The Validator → Conductor → Guard split is intentionally minimal.
- **Adding a new skill**: create `skills/<name>/SKILL.md`, add a profile entry in `profiles/<name>.json`, the installer's `link_skill` loop picks it up automatically once it's in a profile's `skills` list.
- **Adding a hook**: drop a `<name>.sh` into `hooks/`, add the name to a profile's `hooks` array, fire it via `hooks/dispatcher.sh fire <name>`.
- **Adding a catalog**: create `catalogs/<source>/{index.json, bodies/, README.md, LICENSE}`. Match the JSON Schema in `catalogs/schema.json`. Use `scripts/catalog_sync.py` patterns; register in `scripts/catalog_query.py` if needed.
- **Removing bloat**: agents + skills + hooks are standalone files. Delete the file, re-run `./install.sh --force`. No code changes needed elsewhere.

---

## Non-goals

- Not a state machine. Orchestrators read files, not a runtime graph. Communication is via artifacts on disk.
- Not a queue. Engineers don't talk to each other directly. The Conductor manages by defining and enforcing interfaces.
- Not a replacement for human review. The Foundation Phase 3.5 confirmation and Workforce Phase 1.5 user review are mandatory. Alignment Guard's BLOCK halts the next wave; the human decides whether to re-dispatch upstream agents or accept the gap.
- Not a runtime model orchestrator. We ship prompts and contracts; the LLM (Claude in `claude --print` or interactive sessions) is the runtime. This is by design — the system has no in-memory state across runs.
