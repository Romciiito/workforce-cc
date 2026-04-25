# Running a multi-terminal session

A walkthrough of what happens when you actually use workforce-cc, end-to-end. Read this once before your first multi-terminal run; it'll save the "wait, where do I copy this command" moment.

This doc complements [`docs/architecture.md`](architecture.md) (the conceptual map) and [`docs/how-it-works.md`](how-it-works.md) (the Foundation pipeline). Read those first if you haven't.

---

## What "multi-terminal" means

The architecture's premise: each engineer runs in **its own terminal with its own 1M context window**. Communication happens via artifacts on disk, not in-conversation handoffs. This means:

- One terminal runs the **conductor** (decomposes intent → dispatch.md, integrates outputs).
- N additional terminals run **engineer agents** (architect, security-analyst, requirements-engineer, …) in parallel.
- A separate role — **alignment-guard** — runs at gates, reading intent.md vs the integrated artifacts.

You can run all of this in one terminal sequentially (the orchestrator agents will spawn the engineers as sub-agents). The multi-terminal flow shines when:

- The project is large enough that one Claude session would exhaust context before integration.
- You want to watch each engineer's reasoning live.
- You're debugging an engineer that misbehaves — isolated terminals make it easy to inspect their `approach.md` and status file.

---

## Prerequisites

- workforce-cc installed via `./install.sh` (any profile that includes the `orchestrators` agent pack).
- `tmux` if you want windowed multi-terminal mode (recommended). Otherwise the script falls back to background `claude --print` processes with logs under `.tmp/`.
- An interactive `claude` shell on your `$PATH`.

Check the install:

```bash
ls ~/.claude/agents/ | grep -E '^(intent-validator|conductor|alignment-guard)\.md$'
# Should print all three.
cat ~/.foundation-path
# Should print the absolute path to your workforce-cc clone.
```

---

## Mode A — Greenfield bootstrap (`/foundation`)

```
$ mkdir my-saas && cd my-saas
$ claude
> /init                 # creates an empty CLAUDE.md
> /foundation           # starts the pipeline
```

What you'll see:

1. **Phase -1 — Intent Validator.** Socratic questions, one at a time. The agent refuses to write `.workforce/intent.md` until each required section is falsifiable. You may exit and re-invoke the validator if you change your mind about a section.
2. **Phase 0 — Brainstorm.** Existing 5-lens Socratic interrogation; produces `brainstorm.md`.
3. **Phase 1A — parallel analysis.** Four agents (`idea-refiner`, `security-analyst`, `market-researcher`, `requirements-engineer`) spawn simultaneously. If you're in interactive Claude they run as sub-agents; if you want them in real terminals, see "Manual conductor-driven dispatch" below.
4. **Phase 1B — architect + stack-selector.** Parallel.
5. **Phase 1B.5 — output-validator** (legacy cross-check; coexists with alignment-guard for one release).
6. **Phase 1C — workplan-builder.**
7. **Phase 2 — skill suggestions.**
8. **Phase 3 — scaffold.**
9. **Phase 3.5 — confirmation checkpoint.** You type `confirm` or `revise <doc>`.
10. **Phase 3.6 — Alignment Guard (vision).** Reads intent.md vs the integrated artifacts. Returns PASS / PASS-WITH-NOTES / BLOCK. **A BLOCK halts Phase 4 mechanically.** The agent surfaces required actions; you decide whether to re-dispatch upstream agents or accept the gap.
11. **Phase 4 — agent generation + activation.** `agent-generator` writes `.claude/agents/*.md`; `foundation-orchestrator` (or its successor `conductor`) picks up the workplan.

For a small project (~30 tasks, 1-2 tracks), Phase 4 onwards runs comfortably in a single terminal. For larger ones (~70+ tasks, 3+ tracks), see "Manual conductor-driven dispatch".

---

## Mode B — Existing project audit (`/workforce`)

```
$ cd my-existing-repo
$ claude
> /workforce
```

The pipeline:

1. **Phase 0 — scanner.** Reads file tree, git log, existing docs. Writes `project-snapshot.md`.
2. **Phase 0.5 — Intent Validator (conditional).** Fires only when **all** of:
   - The user prompt is vague (no specific file/function/feature).
   - There's no `.workforce/intent.md` younger than 14 days.
   - There's no current `vision.md` (or it diverges significantly from recent commits).
3. **Phase 1 — workforce-orchestrator scoring.** 5 dimensions; writes `workforce-plan.md`.
4. **Phase 1.5 — user review of plan.** Type `confirm`, `skip <agent>`, `add <agent>`, or `vision only`.
5. **Phase 2 — conditional agent spawning.** Only the approved agents run.
6. **Phase 3 — conservative doc creation.** `doc-writer` adds missing docs; flags stale ones with `## ⚠ Update Needed`.
7. **Phase 4 — agent generation** (if `agent-generator` is in the plan).
8. **Phase 4.5 — Alignment Guard (vision, conditional).** Runs only when intent.md exists. **Non-mutating** — surfaces drift; the human decides whether to re-dispatch.
9. **Phase 5 — health record update.** Writes `WORKFORCE.md`.

`/workforce` is conservative by design. It never overwrites or deletes anything; never auto-reverts on a BLOCK. The failure mode of an overzealous audit is much worse than the failure mode of a too-cautious one.

---

## Mode C — Manual conductor-driven dispatch (multi-terminal)

For large projects, run the spine yourself across many terminals. This is what the architecture was designed for.

### Step 1 — Validate intent

```
Terminal 1 (the orchestrator terminal):
$ claude
> /intent-validator
```

Or invoke directly:

```bash
claude --print "/intent-validator" < <(echo "I want to build $YOUR_REQUEST")
```

The agent writes `.workforce/intent.md`. Read it; revise if needed.

### Step 2 — Conductor: dispatch

```
Terminal 1:
> /conductor --mode=dispatch
```

Output: `.workforce/dispatch.md` with per-engineer contracts and a `## Wave order`. Read it before spawning anyone.

Optionally export multi-terminal env so engineers know who they are:

```bash
export WORKFORCE_MULTI_TERMINAL=1
```

This auto-enables `.foundation-memory/telemetry.jsonl` and `.foundation-memory/observations.jsonl` so you can audit later.

### Step 3 — Spawn wave 1

One command, all engineers in the wave:

```bash
python3 ~/.foundation-path/scripts/pipeline_runner.py dispatch-wave \
  --from .workforce/dispatch.md \
  --wave 1 \
  --mode auto
```

`--mode auto` picks tmux if you're in a tmux session, background `claude --print` otherwise. For predictable behavior, set explicitly:

```bash
# Inside a tmux session — windowed engineers, watch each in real time:
... --mode tmux

# No tmux but want background processes:
... --mode background

# No tmux, no auto-spawn — just print the commands you'd run:
... --mode print
```

Each engineer's terminal:

1. Receives the envelope-rendered prompt with its declared inputs/outputs/verification.
2. Writes `runs/<ts>/<engineer>/approach.md` *before* producing outputs.
3. Executes within its declared territory.
4. Runs verification.
5. Writes `status/<engineer>.json` with `{state: DONE | BLOCKED, …}`.

### Step 4 — Monitor

In Terminal 1, poll:

```bash
python3 ~/.foundation-path/scripts/pipeline_runner.py status \
  --expect architect,security-analyst,requirements-engineer,idea-refiner
```

Output:

```
ENGINEER STATUS — run .workforce/runs/2026-04-25T17-00-00Z
──────────────────────────────────────────────────────────
architect           DONE     1m 04s ago   architecture.md
security-analyst    DONE     2m 11s ago   security-model.md
requirements-eng    BLOCKED  0m 30s ago   missing input: spec.md
idea-refiner        RUNNING  45s ago      —
```

If an engineer is BLOCKED, read its `BLOCKED.md`:

```bash
python3 ~/.foundation-path/scripts/pipeline_runner.py blocked-scan
```

You decide whether to retry (narrow / broad / fresh tier — see `agents/orchestrators/conductor.md`'s monitor mode), accept the gap, or abandon.

### Step 5 — Run alignment-guard

Once the wave is DONE:

```
Terminal 1:
> /alignment-guard --mode=cross-check
```

Output: `.workforce/alignment-report.md` with PASS / PASS-WITH-NOTES / BLOCK. **HIGH severity → BLOCK, mechanically.** The agent does not soften.

If BLOCK, read the required actions. Re-dispatch the specific engineers who need to revise their work, then re-run alignment-guard.

### Step 6 — Conductor: integrate

```
> /conductor --mode=integrate
```

Output: `.workforce/integration.md` with cross-cuts found, blocked items, and the recommended next dispatch. Up to **3 convergence iterations** per intent before the run escalates to the user.

### Step 7 — Final vision check

```
> /alignment-guard --mode=vision
```

Drift check against `intent.md`. PASS → run is done; PASS-WITH-NOTES → log findings in `decisions.md`; BLOCK → halt and re-dispatch.

---

## Audit trail

Every multi-terminal run produces three layers of audit data:

```
<project>/
├── .workforce/
│   ├── intent.md
│   ├── dispatch.md
│   ├── integration.md
│   ├── alignment-report.md
│   └── runs/<ts>/<engineer>/
│       ├── approach.md
│       └── BLOCKED.md (only if blocked)
├── .foundation-memory/
│   ├── telemetry.jsonl     ← per-task events from scripts/telemetry.py
│   ├── governance.jsonl    ← per-decision audit from hooks/governance.sh
│   └── observations.jsonl  ← per-tool-call from hooks/observe.sh
```

The hooks fire automatically when their profile is active. To opt out for one run:

```bash
export WORKFORCE_TELEMETRY=off
```

To disable specific hooks without reinstalling:

```bash
export WORKFORCE_DISABLED_HOOKS=observe,config-protection
```

---

## Troubleshooting

### "tmux: not in a session"

You're running `--mode tmux` without being inside a tmux session. Either start one (`tmux new -s workforce`) or use `--mode background`.

### "No engineer reports DONE in monitor mode"

Most likely the spawned terminal failed to start `claude` correctly. Check `.tmp/track-<engineer>.log` for stderr. If `claude --print` was used, the prompt might have been too large; try a narrower territory in dispatch.md.

### "Alignment Guard returned BLOCK but the cause isn't obvious"

Read `.workforce/alignment-report.md` end-to-end. The Findings table lists severity and source artifacts. The Required actions section is mandatory for BLOCK and recommended for PASS-WITH-NOTES.

### "I want to skip the validator for a quick fix"

Pass-through mode is built in. The validator's Mode C handles concrete requests like "fix the bug in `auth.py:foo`" — it produces a one-paragraph `intent.md` and the rest of the pipeline short-circuits. Don't bypass; let the validator decide it's pass-through.

### "I made a typo in intent.md"

Re-invoke the validator. It detects existing `intent.md` and switches to Mode B (revision). Asks only about the parts you changed.

---

## When NOT to use multi-terminal

- Tiny tasks: one bug, one feature, one small refactor. Use the legacy `spawn` command (now envelope-by-default) or just chat with Claude directly.
- Read-only audits where you only want a /sync-style check.
- When you're learning the system. Run a couple of single-terminal sessions first; you'll spot the bottleneck that justifies multi-terminal.

The multi-terminal flow is heavyweight on purpose — it's optimised for projects where the alternative is a multi-day Claude session that runs out of context before integration.

---

## Pointers

- The conductor's prompt: [`agents/orchestrators/conductor.md`](../agents/orchestrators/conductor.md)
- The alignment guard's prompt: [`agents/orchestrators/alignment-guard.md`](../agents/orchestrators/alignment-guard.md)
- The intent validator's prompt: [`agents/orchestrators/intent-validator.md`](../agents/orchestrators/intent-validator.md)
- The shared spine: [`skills/_backbone/BACKBONE.md`](../skills/_backbone/BACKBONE.md)
- The artifact contract: [`docs/artifact-contract.md`](artifact-contract.md)
- The bug-fix workflow with execution traces: [`templates/workflows/bug-fix.md`](../templates/workflows/bug-fix.md)
