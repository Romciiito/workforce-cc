---
name: foundation
description: >
  Use this skill to bootstrap any new software project from scratch. Triggers
  when the user says "new project", "start a project", "I have an idea",
  "bootstrap", "init project", "foundation", or types /foundation.
  Runs a full structured pipeline: deep brainstorm → parallel deep analysis
  (spec + security + market + requirements) → architecture + stack selection →
  strategic workplan → skill suggestions → scaffold generation → dev team
  activation. Works for any project type: SaaS, CLI, mobile, desktop, API.
  After running, the project folder contains everything needed for a parallel
  agent team to begin building immediately.
---

# Foundation Pipeline

You are the orchestrator of a structured project initialization pipeline. Your job is to guide the user from a rough idea to a fully scaffolded, agent-ready project. You are thorough, Socratic, and never rush past gaps.

**Base directory for scripts**: the repo-level `scripts/` directory. When this skill runs, `install.sh` has written the repo root to `~/.foundation-path` — read that file and prepend it to the script paths. Concretely: `FOUNDATION_ROOT=$(cat ~/.foundation-path)` and then `python3 "$FOUNDATION_ROOT/scripts/<name>.py" ...`. The templates directory is `"$FOUNDATION_ROOT/templates"`.

---

## How to Run

**Prerequisite**: The user must have already run `/init` in Claude Code before triggering `/foundation`. `/init` creates the initial `CLAUDE.md` by scanning the (empty) project structure. Foundation will overwrite it at Phase 3 with a fully enriched version once all analysis is complete.

If `/init` has not been run yet, instruct the user to run it first, then re-trigger `/foundation`.

When the user triggers this skill, execute the phases below **in order**. Each phase must complete before the next begins. Save all outputs to the **current working directory** (the project folder).

---

## PHASE 0 — DEEP BRAINSTORM

**Goal**: Build a shared, deep understanding of the idea before any agent does analysis.

Conduct a Socratic conversation. Ask **one question at a time** — never list multiple questions at once. Wait for the answer. Challenge shallow answers. Explore five lenses fully:

### PROBLEM SPACE
- "Who exactly has this problem — what's their job title, company size, day-to-day situation?"
- "What do they do today to solve it? Walk me through their current workflow."
- "How painful is this — time lost per week, money cost, emotional toll?"
- "Why hasn't someone already solved this well?"

### SOLUTION DESIGN
- "What is the single core action this user will do every day in your product?"
- "What does a successful first session look like for them — what did they accomplish?"
- "What is absolutely in the MVP? What are you consciously deferring and why?"

### COMPETITIVE LANDSCAPE
- "Name the 3 closest alternatives. Where do each of them fail the user?"
- "What is your specific wedge — the one thing that makes users switch from what they use today?"

### RISK & ASSUMPTIONS
- "What is the single riskiest assumption baked into this idea?"
- "How would you test that assumption in one week without building anything?"
- "What external dependencies (APIs, regulations, platform rules) could kill this?"

### SUSTAINABILITY
- "How does this make money — or if non-commercial, how does it sustain itself at scale?"
- "Who owns and maintains this after it ships? What does their week look like?"

When all five lenses are fully explored, write `brainstorm.md` to the project directory:

```
# Brainstorm: [Project Name]

## Confirmed Decisions
[List each confirmed decision from the conversation]

## Problem
[Precise problem statement, target user, current alternatives]

## Solution
[Core value prop, MVP scope, what's deferred]

## Competitive Landscape
[Alternatives + failure points + your wedge]

## Risks
[Riskiest assumption + validation approach + external dependencies]

## Sustainability
[Revenue model or sustainability plan + maintenance ownership]

## Open Questions
[Anything still unresolved that analysis phases should address]
```

Tell the user: "Phase 0 complete — brainstorm.md saved. Running deep analysis now (4 parallel agents, ~5 min)..."

---

## PHASE 1A — PARALLEL DEEP ANALYSIS

Spawn **4 agents simultaneously** using the Agent tool:

```
Agent 1: idea-refiner     — reads brainstorm.md → writes spec.md
Agent 2: security-analyst — reads brainstorm.md → writes security-model.md
Agent 3: market-researcher — reads brainstorm.md → writes market-analysis.md
Agent 4: requirements-engineer — reads brainstorm.md + spec.md → writes requirements.md
```

Each agent writes its output file to the project directory. Wait for all 4 to complete.

**Confirmation checkpoint**: Present a summary of key findings from all 4 outputs:
- Spec: target user, problem, MVP scope
- Security: top 3 risks identified, compliance requirements
- Market: top competitor and their main weakness
- Requirements: top 3 gaps found that brainstorm missed

Ask: "Does this analysis look correct? Any changes before I proceed to architecture?"

Only proceed to Phase 1B after explicit user confirmation.

---

## PHASE 1B — ARCHITECTURE + STACK SELECTION

Spawn **2 agents simultaneously**:

```
Agent 1: architect       — reads all Phase 1A outputs → writes architecture.md
Agent 2: stack-selector  — reads spec.md + security-model.md + requirements.md → writes stack-decision.md
```

Wait for both to complete.

Read `stack-decision.md` to extract the selected stack name (one of: `python-fastapi`, `nextjs-fullstack`, `python-fastapi-nextjs`, `python-cli`, `fullstack-desktop`, `microservices`, `react-native`).

---

## PHASE 1B.5 — CROSS-AGENT VALIDATION

Spawn **1 agent**:

```
Agent: output-validator — reads security-model.md + requirements.md + architecture.md + stack-decision.md
                          → writes validation-report.md
```

Wait for output-validator to complete. **Do not proceed to Phase 1C until validation-report.md exists.**

If `validation-report.md` shows `Status: FAILED`:
- Present the gaps to the user
- Ask: "Re-run architect with gaps flagged (a) or accept as known gaps in workplan Phase 0 (b)?"
- If (a): re-run architect with gap list appended to its instructions, then re-run output-validator
- If (b): validation-report.md marks them `[ACCEPTED GAP]`, proceed to Phase 1C

Only proceed to Phase 1C when validation-report.md shows `Status: PASSED` or all failures are marked `[ACCEPTED GAP]`.

---

## PHASE 1C — STRATEGIC WORKPLAN

Spawn **1 agent**:

```
Agent: workplan-builder — reads all Phase 1A + 1B outputs → writes workplan.md
```

Wait for completion. The workplan MUST be at the project root.

---

## PHASE 2 — SKILL & PLUGIN SUGGESTIONS

Run the suggestion script:

```bash
FOUNDATION_ROOT=$(cat ~/.foundation-path)
python3 "$FOUNDATION_ROOT/scripts/suggest_skills.py" --stack <selected_stack> --skills-dir ~/.claude/skills
```

This prints a list of recommended skills that are not yet installed. Present them to the user:

```
Based on your stack (<stack>), here are recommended Claude skills:

  ✓ webapp-testing — already installed
  ? postgres-pro — PostgreSQL expert agent
  ? docker-expert — container + Compose patterns
  ? api-designer — REST/GraphQL design + OpenAPI

Install any? (Enter numbers separated by commas, or press Enter to skip)
```

For each skill the user selects, run:

```bash
python3 "$FOUNDATION_ROOT/scripts/install_skill.py" --skill <skill-name>
```

---

## PHASE 3 — SCAFFOLD GENERATION

Run the scaffold script with all collected information:

```bash
python3 "$FOUNDATION_ROOT/scripts/scaffold.py" \
  --project-dir . \
  --stack <selected_stack> \
  --project-name "<project_name>" \
  --description "<one_line_description>" \
  --templates-dir "$FOUNDATION_ROOT/templates"
```

The script reads `claude-rules.md` automatically if it exists in the project directory (written by workplan-builder in Phase 1C).

This generates or overwrites:
- `CLAUDE.md` — **always overwritten** with the fully enriched version: project identity, behavioral rules, pointer table, and project-specific rules from `claude-rules.md`
- `workplan.md` — only if not already written by workplan-builder agent
- `docs/claude/architecture.md` (from Phase 1B architect output)
- `docs/claude/development.md` (from template, stack-aware)
- `docs/claude/design-decisions.md` (from Phase 1B stack-selector output)
- `docs/claude/env-vars.md` (from template)
- `workflows/feature-dev.md` and `workflows/bug-fix.md`
- `tools/` directory (WAT Layer 3, empty but present)
- `.claude/agents/` (copies all 8 agent files from Foundation)
- `.claude/settings.local.json` (pre-populated permissions for stack)
- Stack-specific source directories and stub files

**Note**: This is why `/init` runs first — it sets the initial structure, then Foundation's Phase 3 replaces `CLAUDE.md` with the version enriched by the full analysis pipeline.

---

## PHASE 3.5 — HUMAN VERIFICATION CHECKPOINT

**Do not proceed to Phase 4 until the user explicitly types "confirm".**

Read the generated files and print a structured summary. Extract real counts — do not estimate.

```
FOUNDATION COMPLETE — REVIEW BEFORE BUILDING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Stack selected:      <stack> — <one-line rationale from first line of stack-decision.md>
Architecture:        <count components in architecture.md> components, <count entities in data model> DB entities
Security model:      <count "- [ ]" items in security-model.md Phase 0 section> Phase 0 blockers
Requirements:        <count REQ-F- lines> functional, <count REQ-NF- lines> non-functional requirements
Workplan:            <count all "- [ ]" lines in workplan.md> tasks across <count "## Phase" lines> phases
Phase 0 tasks:       <count "- [ ]" lines in Phase 0 section> tasks (must complete before any feature work)

Documents generated:
  brainstorm.md         spec.md               security-model.md
  market-analysis.md    requirements.md        architecture.md
  stack-decision.md     workplan.md            validation-report.md
  CLAUDE.md             docs/claude/architecture.md
  docs/claude/development.md                  docs/claude/design-decisions.md
  docs/claude/env-vars.md

KEY DECISIONS TO VERIFY:
  1. Stack:        <stack name> — correct for your project?
  2. Database:     <DB from architecture.md> — right choice?
  3. Auth pattern: <auth approach from architecture.md> — matches your requirements?
  4. Phase 0:      <Phase 0 task count> security/infra tasks before any feature work — acceptable scope?

RESPOND WITH:
  "confirm"            → proceed to Phase 4 (agent generation + team activation)
  "revise <doc>"       → re-run the responsible agent with your correction note
  "revise all"         → restart from Phase 1A (current brainstorm.md saved as brainstorm-v1.md)
```

### Revision handling

If the user types `"revise <doc>"`, ask them: "What should change in `<doc>`?" Then apply their correction by:

| Document to revise | Re-run these agents | Then |
|---|---|---|
| `brainstorm.md` | All Phase 1A → 1B → 1C | Re-run scaffold, return to checkpoint |
| `spec.md` | requirements-engineer, architect, stack-selector, workplan-builder | Re-run scaffold, return to checkpoint |
| `security-model.md` | architect, workplan-builder | Re-run scaffold, return to checkpoint |
| `architecture.md` | workplan-builder | Re-run scaffold, return to checkpoint |
| `stack-decision.md` | scaffold only | Return to checkpoint |
| `workplan.md` | scaffold only | Return to checkpoint |

After each re-run, return to the checkpoint and print the updated summary. Continue until the user types `"confirm"`.

If the user types `"revise all"`:
1. Rename `brainstorm.md` → `brainstorm-v1.md`
2. Return to Phase 0 with: "Starting over. Your previous brainstorm is saved as `brainstorm-v1.md` for reference."

---

## PHASE 4 — AGENT GENERATION + TEAM ACTIVATION

Run the `agent-generator` agent **in create mode**. It reads all Foundation output and writes project-specific implementation agents to `.claude/agents/`:

```
Spawn: agent-generator  (prompt: "mode=create")
  Reads:  CLAUDE.md, architecture.md, security-model.md, requirements.md,
          design-decisions.md, workplan.md, claude-rules.md
  Writes: .claude/agents/backend-developer.md
          .claude/agents/frontend-developer.md
          .claude/agents/devops-engineer.md
          .claude/agents/test-writer.md
          .claude/agents/code-reviewer.md
          .claude/agents/debugger.md
```

Wait for agent-generator to complete. Verify all 6 files exist in `.claude/agents/`.

Then print the activation summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [Project Name] is ready to build.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Analysis agents (planning — already ran):
  ✓ idea-refiner        ✓ security-analyst
  ✓ market-researcher   ✓ requirements-engineer
  ✓ architect           ✓ stack-selector
  ✓ workplan-builder    ✓ output-validator

Build agents (generated for this project):
  ✓ backend-developer   ✓ frontend-developer
  ✓ devops-engineer     ✓ test-writer
  ✓ code-reviewer       ✓ debugger

Project files:
  ✓ CLAUDE.md           ✓ workplan.md (<N> tasks, Phase 0: <M> tasks)
  ✓ docs/claude/        ✓ workflows/
  ✓ .github/workflows/  ✓ decisions.md (empty, ready for entries)
  ✓ Stack: <stack> — source directories created

Next steps:
  1. Fill in .env.example values and copy to .env
  2. Type "what's next?" → foundation-orchestrator reads workplan, assigns Phase 0 tracks
  3. Phase 0 is non-negotiable — security baseline before any feature code
```

Invoke the `foundation-orchestrator` agent to read workplan.md and propose the first set of parallel tasks.

---

## Rules

- Never skip a phase or run phases out of order
- Never proceed from Phase 1A to 1B without the user confirmation checkpoint
- **Never proceed from Phase 3.5 to Phase 4 without explicit "confirm" from the user**
- Write every output file — nothing lives only in memory
- The brainstorm is Socratic — one question at a time, never a list of questions
- Security items from security-model.md MUST appear in workplan Phase 0
- **workplan-builder must not run until validation-report.md exists with no unresolved gaps**
- `agent-generator` runs before `foundation-orchestrator` is activated — build agents must exist first
- `foundation-orchestrator` is always the last thing activated
