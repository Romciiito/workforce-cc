---
name: workforce
description: >
  On-call AI workforce for existing projects. Triggers on /workforce, "check
  my project", "audit my project", "project health", "align my project", or
  "workforce". Scans the project, determines its state, discusses with the user
  only where intent is unclear, then spawns exactly the specialist agents the
  project needs — no more, no less. Works on any project at any stage.
  Conservative: only adds missing docs, never restructures or overwrites.
---

# Workforce

You are the entry point for the Workforce system. Your job is to run the pipeline below and hand off to the `workforce-orchestrator`, which makes all agent-spawning decisions.

**Base directory for scripts**: the repo-level `scripts/` directory. `install.sh` writes the repo root to `~/.foundation-path` — read it and prepend to invocations: `FOUNDATION_ROOT=$(cat ~/.foundation-path); python3 "$FOUNDATION_ROOT/scripts/health_score.py" --project-dir .`.

---

## When to trigger

Trigger on: `/workforce`, "check my project", "audit my project", "project health", "align my project", "am I on track", "workforce", or any request to review/tidy/assess an existing project's state.

Do NOT trigger on new greenfield projects — those use `/foundation`.

---

## Pipeline

Execute phases in order. Each phase must complete before the next begins.

The pipeline now flows through the shared backbone described in [`skills/_backbone/BACKBONE.md`](../_backbone/BACKBONE.md). Phase 0 (scan) runs first because the audit has nothing without it. Phase 0.5 (intent validation) runs **conditionally** when the user's request is vague. Phase 4 (alignment-guard) is a final drift check before WORKFORCE.md is written.

---

### PHASE 0 — SCAN

Spawn the `scanner` agent. It reads the project without touching any files.

```
Spawn: scanner
  Reads:  file tree, git log, existing docs, stack files
  Output: project-snapshot.md (written to project root)
```

Wait for `project-snapshot.md` to exist before proceeding.

---

### PHASE 0.5 — INTENT VALIDATION (conditional)

**Run this phase only when the user's request is vague.** A request like "audit my project" or "check if we're on track" needs intent before the orchestrator scores anything. A request like "is `auth.py:foo` covered by tests?" already has a concrete answerable question — skip this phase and let the orchestrator run.

**Trigger heuristic** — run intent-validator when **all** of the following are true:

1. The user's prompt does not name a specific file, function, or feature.
2. There is no `.workforce/intent.md` younger than 14 days.
3. There is no `vision.md` younger than 30 days, OR the most recent commits diverge significantly from `vision.md`.

When triggered, spawn:

```
Spawn: intent-validator
  Reads:  user prompt, project-snapshot.md, vision.md (if exists),
          CLAUDE.md (if exists), README.md (if exists)
  Output: .workforce/intent.md
  Mode:   B (revision) if vision.md exists; A (greenfield) otherwise
```

Wait for `.workforce/intent.md` to exist before proceeding to Phase 1. The intent file gives the workforce-orchestrator a falsifiable goal to score against, instead of guessing what "audit" means for this user.

If the trigger heuristic does not fire (request is concrete), skip this phase and proceed to Phase 1 directly.

---

### PHASE 1 — ORCHESTRATOR ASSESSMENT

Spawn the `workforce-orchestrator` agent. It reads `project-snapshot.md`, scores the project, and produces a workforce plan.

```
Spawn: workforce-orchestrator
  Reads:  project-snapshot.md, vision.md (if exists), CLAUDE.md (if exists),
          workplan.md (if exists), .claude/agents/ (if exists)
  Output: workforce-plan.md
```

The workforce-orchestrator decides which agents to spawn. It does NOT spawn them yet — it writes the plan first.

---

### PHASE 1.5 — USER REVIEW OF PLAN

Read `workforce-plan.md` and present a summary to the user:

```
WORKFORCE ASSESSMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Project:       <name>
Stack:         <detected>
Maturity:      <early / mid / mature>
Last activity: <N commits in last 30 days>

Health scores:
  Vision clarity:     <score>/10  (<status>)
  Documentation:      <score>/10  (<N of M docs present>)
  Security baseline:  <score>/10  (<N of M checklist items>)
  Agent coverage:     <score>/10  (<present / missing>)
  Workplan freshness: <score>/10  (<current / stale / missing>)

Agents to spawn:
  <list from workforce-plan.md — agent + reason>

Docs to create (conservative — add only):
  <list of missing docs>

Respond:
  "confirm"          → proceed with the plan
  "skip <agent>"     → remove an agent from the plan
  "add <agent>"      → add an agent not in the plan
  "vision only"      → run only vision alignment, nothing else
```

**Do not proceed until the user responds.** Wait for explicit confirmation.

---

### PHASE 2 — CONDITIONAL AGENT SPAWNING

Based on the confirmed workforce-plan, spawn only the approved agents.

**Ordering rules (enforced by workforce-orchestrator):**
1. `vision-keeper` always runs first if it's in the plan — alignment before analysis
2. Analysis agents run in parallel after vision is confirmed: `gap-analyst`, `security-analyst`, `architect`, `requirements-engineer`
3. `doc-writer` runs after all analysis agents complete
4. `agent-generator` runs last — it needs all docs to exist first

The workforce-orchestrator manages spawning order. Do not spawn out of order.

---

### PHASE 3 — CONSERVATIVE DOC CREATION

After analysis agents complete, the `doc-writer` agent creates only the approved missing docs.

Rules enforced during this phase:
- Never overwrite existing files
- Never delete any file
- Never move or rename any file
- For stale docs: append an `## ⚠ Update Needed` section at the bottom only
- For missing docs: create from template with placeholder text

---

### PHASE 4 — AGENT GENERATION

If `agent-generator` is in the plan:

```
Spawn: agent-generator  (prompt: "mode=diff")
  Reads:  all docs generated in Phase 3 + existing .claude/agents/
  Mode:   diff — update only agents where project context changed
  Output: .claude/agents/*.md (create new, update stale, skip current)
```

---

### PHASE 4.5 — ALIGNMENT GUARD (vision)

**Run this phase only when Phase 0.5 produced an `intent.md`** (or when one was already current). Without `intent.md`, alignment-guard has nothing to check against — the audit is a maintenance pass, not an alignment check.

```
Spawn: alignment-guard --mode=vision
  Reads:  .workforce/intent.md (required for this phase),
          vision.md (if exists), spec.md (if exists),
          architecture.md (if exists), workplan.md (if exists),
          decisions.md (last 20 entries), project-snapshot.md
  Output: .workforce/alignment-report.md
```

The agent returns one of three statuses:

- **PASS** — proceed to Phase 5; record clean alignment in WORKFORCE.md.
- **PASS-WITH-NOTES** — proceed to Phase 5 but list findings in WORKFORCE.md as open items.
- **BLOCK** — surface required actions to the user. The user decides whether to re-dispatch upstream agents (e.g. re-run gap-analyst or doc-writer with corrections) or accept the gap and proceed.

This is a non-mutating gate — the audit pipeline does not auto-revert work because alignment-guard returned BLOCK. It surfaces drift; the human decides.

---

### PHASE 5 — HEALTH RECORD UPDATE

Update (or create) `WORKFORCE.md` at the project root with this run's results:
- Timestamp
- Health scores from Phase 1
- Agents spawned and their outputs
- Open items from gap-analyst
- Recommended next run trigger

---

## Rules

- The workforce-orchestrator decides which agents run — never hardcode a fixed agent list
- Scanner always runs first, agent-generator always runs last
- Never overwrite existing files without explicit user confirmation
- Never spawn agents outside the approved workforce-plan
- If the user says "vision only" — run only vision-keeper, then update WORKFORCE.md
- If `project-snapshot.md` already exists and was written in the last 10 minutes, skip Phase 0 (already fresh)
- Foundation agents (idea-refiner, market-researcher, stack-selector) are never spawned by Workforce
- **Phase 0.5 (intent-validator) is conditional** — fire only when the request is vague AND no current `intent.md`/`vision.md` exists. Concrete requests skip this phase.
- **Phase 4.5 (alignment-guard) runs only when `intent.md` exists** — without it, drift has no anchor.
- Use `scripts/workforce_paths.py write-path <name>` for `intent.md`, `dispatch.md`, `integration.md`, `alignment-report.md` — never hardcode `.workforce/` paths
