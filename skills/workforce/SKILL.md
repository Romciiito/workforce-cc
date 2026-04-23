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
