# Architecture — merged Foundation + Workforce

Two skills, one repo. This doc describes how they coexist and how the pieces fit together.

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
                                    │
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                       ▼
        scripts/                agents/                 templates/
   scaffold.py             _shared/   (both)        CLAUDE.md.jinja
   health_score.py         foundation/              workplan.md.jinja
   suggest_skills.py       workforce/               stacks/<stack>/…
   install_skill.py                                 agents/<role>.md.jinja
   pipeline_runner.py                               …
   telemetry.py
```

---

## Two skills, one pool

`/foundation` and `/workforce` do different jobs. They never run concurrently in the same session. But they share the agent pool:

| | Foundation pipeline | Workforce pipeline | Shared agents |
|-|--------------------|--------------------|-----------------|
| Analysis | idea-refiner, market-researcher, stack-selector, output-validator, workplan-builder | scanner, gap-analyst, vision-keeper | architect, security-analyst, requirements-engineer, test-strategist, performance-analyst |
| Meta | foundation-orchestrator, model-selector | workforce-orchestrator, doc-writer | agent-generator, agent-router |
| Build (generated per project) | — | — | backend-developer, frontend-developer, devops-engineer, test-writer, code-reviewer, debugger |

The build agents are written **into the project**, not into `~/.claude/agents/`. That's why the `templates/agents/*.md.jinja` files exist and why `agent-generator` runs in both pipelines.

---

## The install contract

`install.sh` guarantees three things:

1. **Skill symlinks** — `~/.claude/skills/foundation`, `~/.claude/skills/workforce`, `~/.claude/skills/sync` each point back to this repo. Editing a SKILL.md here is visible immediately.
2. **Agent copies** — every `.md` in `agents/_shared/`, `agents/foundation/`, `agents/workforce/` is copied into `~/.claude/agents/`. These are **copies**, not symlinks, because Claude Code's agent loader expects stable files.
3. **Path beacon** — `~/.foundation-path` contains the absolute repo path. SKILL.md files read it to locate scripts and templates, so they work regardless of where the user cloned the repo.

The contract is deliberately simple so the user can move, rename, or delete the repo safely — re-running `install.sh` re-establishes everything.

---

## Pipeline boundaries

**Foundation is the creator.** It only runs in empty directories (or ones with nothing but `CLAUDE.md` from `/init`). Its outputs are write-through: every agent writes a single canonical file, and Phase 3's scaffold script never asks permission before overwriting planning docs.

**Workforce is the auditor.** It only runs in populated directories. Its outputs are additive: it creates missing docs, flags stale docs with an `## ⚠ Update Needed` section, and never overwrites or deletes anything.

**/sync is the observer.** It runs one Python script, parses JSON, and exits. No agents, no files.

The `agent-generator` is the single point where both pipelines meet — it reads the docs written by either and emits the build team. Its `create` vs. `diff` mode selects the appropriate behavior.

---

## Cross-skill handoffs

Neither orchestrator invokes the other skill. Instead, they **recommend**:

- `foundation-orchestrator` says *"your last Foundation run was 30+ days ago and 40 feature-commits have landed — run `/workforce` to resync the docs"*
- `workforce-orchestrator` says *"this directory has no CLAUDE.md, no workplan, no docs — `/workforce` is not the right tool here, run `/foundation` instead"*

The user decides. This preserves an important invariant: no state is produced in a session the user didn't explicitly authorize.

---

## Memory and telemetry (opt-in)

If a project creates `.foundation-memory/`, agents in their task protocol append to `.foundation-memory/telemetry.jsonl` via `scripts/telemetry.py`. Each line is one event:

```json
{"ts":"2026-04-23T10:15:33+00:00","agent":"backend-developer","event":"task-complete","task":"REQ-F-012","duration_sec":420.0}
```

This is not a metrics system. It's a session-spanning breadcrumb trail — useful when reviewing *what happened* across many sessions without rereading transcripts.

If `.foundation-memory/` doesn't exist, `telemetry.py` silently exits. The default is off.

---

## Extending

- **Adding a stack**: create `templates/stacks/<name>/structure.json`, add it to `STACK_PERMISSIONS` in `scripts/scaffold.py`, add recommended skills to `skill-catalog.json`, reference it in `skills/foundation/SKILL.md` Phase 1B.
- **Adding a shared agent**: drop the `.md` into `agents/_shared/`; re-run `./install.sh --force`. Both orchestrators' routing tables are already expressive enough to pick it up, but you may want to register it in `agent-router.md`.
- **Adding a new skill**: create `skills/<name>/SKILL.md`, add a `link_skill <name>` call in `install.sh`.
- **Removing bloat**: agents + skills are standalone files. Delete the file, re-run `./install.sh --force`. No code changes needed elsewhere.

---

## Non-goals

- Not a state machine. Orchestrators read files, not a runtime graph.
- Not a queue. Agents don't talk to each other — they communicate through files (`workplan.md`, `decisions.md`).
- Not a replacement for human review. The human verification checkpoint in Foundation Phase 3.5 and the user confirmation in Workforce Phase 1.5 are mandatory. The system will not proceed past them unattended.
