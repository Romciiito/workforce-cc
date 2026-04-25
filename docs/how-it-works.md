# How Foundation Works

Foundation is a Claude Code skill that turns a raw idea into a fully scaffolded, agent-ready project — without any external CLI, API keys, or setup beyond what Claude Code already has.

This document focuses on `/foundation`. For the full system architecture (the shared backbone, three orchestrator roles, multi-terminal spawn contract), see [`architecture.md`](architecture.md).

---

## The Problem It Solves

Starting a project manually with an AI assistant is inefficient:

- You type an idea, the AI responds linearly, one thing at a time.
- Security is an afterthought — you add it when you remember.
- The analysis is shallow — competitors, risks, and edge cases are missed.
- You end up with a chat transcript, not a project.

Foundation replaces that with a structured, parallel, reproducible pipeline that produces a real working scaffold with security baked in from day 0. It now also flows through the shared **Validator → Conductor → Alignment Guard** spine: the Intent Validator forces a falsifiable goal before brainstorming starts, and the Alignment Guard catches drift before the build team is activated.

---

## Architecture Overview

```
User types /foundation
         │
         ▼
PHASE -1 — INTENT VALIDATION (intent-validator, blocking)
  Three modes: A (greenfield Socratic interrogation, max 6 questions),
  B (revision of existing intent), C (pass-through for concrete requests).
  Refuses to advance until .workforce/intent.md has all six required
  sections with falsifiable content.
  Output: .workforce/intent.md

         │
         ▼
PHASE 0 — DEEP BRAINSTORM (interactive, ~15 min)
  Claude asks one question at a time across 5 lenses:
  Problem space → Solution design → Competitive landscape
  → Risk & assumptions → Sustainability
  Output: brainstorm.md

         │
         ▼
PHASE 1A — PARALLEL DEEP ANALYSIS (4 agents simultaneously)
  ┌──────────────────┐ ┌────────────────────┐
  │  idea-refiner    │ │  security-analyst  │
  │  → spec.md       │ │  → security-model  │
  └──────────────────┘ └────────────────────┘
  ┌──────────────────┐ ┌────────────────────┐
  │market-researcher │ │requirements-engineer│
  │→ market-analysis │ │→ requirements.md   │
  └──────────────────┘ └────────────────────┘
  Confirmation checkpoint before proceeding

         │
         ▼
PHASE 1B — ARCHITECTURE + STACK (2 agents simultaneously)
  [architect]      → architecture.md
  [stack-selector] → stack-decision.md

         │
         ▼
PHASE 1C — STRATEGIC WORKPLAN (1 agent)
  [workplan-builder] → workplan.md
  Security items from Phase 1A are mandatory in Phase 0 of workplan

         │
         ▼
PHASE 2 — SKILL SUGGESTIONS (interactive, ~1 min)
  Checks ~/.claude/skills/ vs skill-catalog.json
  User picks which to install; Foundation runs install_skill.py

         │
         ▼
PHASE 3 — SCAFFOLD GENERATION (automated, ~1 min)
  scaffold.py renders Jinja2 templates → project files
  Copies agents, creates dirs, writes settings.local.json

         │
         ▼
PHASE 3.5 — HUMAN VERIFICATION CHECKPOINT
  User must explicitly type "confirm" before Phase 4.
  Otherwise: "revise <doc>" or "revise all".

         │
         ▼
PHASE 3.6 — ALIGNMENT GUARD --mode=vision
  Reads .workforce/intent.md vs spec.md, architecture.md, workplan.md.
  Returns PASS / PASS-WITH-NOTES / BLOCK.
  HIGH severity → BLOCK halts Phase 4 mechanically.
  Output: .workforce/alignment-report.md

         │
         ▼
PHASE 4 — TEAM ACTIVATION
  Summary printed. agent-generator writes 6 build agents
  to .claude/agents/. foundation-orchestrator activated.
```

The full multi-terminal spawn contract used internally by these phases is described in [`architecture.md`](architecture.md). Each engineer agent runs in its own terminal with its own 1M context window; communication is via artifacts on disk.

---

## Key Design Decisions

### Security is structural, not an audit

The `security-analyst` agent runs in Phase 1A alongside the spec and requirements agents. Its output directly populates **Phase 0** of the workplan — meaning security items must be completed before any user-facing code ships. This is not a "we'll add security later" system.

### Brainstorm is Socratic, not a form

Phase 0 asks one question at a time. It challenges shallow answers. It explores five distinct lenses fully before moving on. The result is a `brainstorm.md` with confirmed decisions and resolved open questions — not a list of vague requirements.

### Parallel agents, not sequential

Phases 1A and 1B use parallel agent spawning (Claude Code's `Agent` tool with multiple calls in a single message). This cuts analysis time from ~25 minutes to ~8 minutes.

### WAT framework on by default

Every generated project has `workflows/` and `tools/` directories. This activates the WAT (Workflows, Agents, Tools) framework contract: reusable deterministic scripts in `tools/`, durable instructions in `workflows/`, agent team available immediately.

### Templates are Jinja2 + stack-specific structure

`scaffold.py` renders project files from `templates/` using Jinja2. Each stack has its own `structure.json` that defines directories and stub files. Adding a new stack = one new directory in `templates/stacks/`.

### Runs inside Claude Code

No external process. Claude models handle all intelligence. The only runtime dependency is `python3` with `jinja2` installed — used by `scaffold.py` to generate files deterministically.

---

## Repository Structure

Foundation is now part of a merged monorepo that also contains Workforce and a `/sync` quick-check skill. See [architecture.md](architecture.md) for the full layout. The canonical Foundation-specific pieces are:

- `skills/foundation/SKILL.md` — the pipeline you just read about
- `agents/foundation/*.md` — idea-refiner, market-researcher, stack-selector, output-validator, workplan-builder, foundation-orchestrator, model-selector
- `agents/_shared/*.md` — architect, security-analyst, requirements-engineer, agent-generator, agent-router, test-strategist, performance-analyst
- `scripts/scaffold.py`, `scripts/suggest_skills.py`, `scripts/install_skill.py` — the deterministic helpers
- `templates/` — every Jinja2 file the scaffold renders

---

## Installation

```bash
git clone https://github.com/Romciiito/workforce-cc ~/.foundation
~/.foundation/install.sh
```

Then open any empty project directory in Claude Code and type `/foundation`.

---

## Adding a New Stack

1. Create `templates/stacks/<stack-name>/structure.json` with `dirs` and `files` keys.
2. Add the stack to `STACK_PERMISSIONS` in `scripts/scaffold.py`.
3. Add skill recommendations to `skill-catalog.json`.
4. Reference the new stack name in `skills/foundation/SKILL.md` Phase 1B stack list.

---

## Agent Descriptions

| Agent | Input | Output | Phase |
|---|---|---|---|
| `orchestrator` | workplan.md | Parallel task assignments | Every session |
| `idea-refiner` | brainstorm.md | spec.md | 1A |
| `security-analyst` | brainstorm.md | security-model.md | 1A |
| `market-researcher` | brainstorm.md | market-analysis.md | 1A |
| `requirements-engineer` | brainstorm.md + spec.md | requirements.md | 1A |
| `architect` | all Phase 1A outputs | architecture.md | 1B |
| `stack-selector` | spec + security + requirements | stack-decision.md | 1B |
| `workplan-builder` | all Phase 1A + 1B outputs | workplan.md | 1C |
