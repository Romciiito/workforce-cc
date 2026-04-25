---
name: sync
description: >
  Lightweight health check for an existing workforce-cc project.
  Triggers on /sync, "quick check", "sync my project", "how healthy is this",
  or "sync". Runs the workforce health_score.py script, peeks at .workforce/
  for the latest run state (intent.md / dispatch.md / alignment-report.md),
  and prints a one-screen summary with scores, drift indicators, and a
  recommended next action. Does NOT spawn any agents, does NOT create any
  files — pure read-only assessment. Runs in ~5 seconds.
---

# /sync — Quick Health Check

You are the entry point for a fast, read-only health check of an existing project. Your job is to run one script, parse its output, optionally peek at the project's `.workforce/` orchestration artifacts, and suggest the next action — without spawning agents, without creating files, without modifying anything.

Use `/sync` as the light-touch alternative to `/workforce`:

| | /sync | /workforce |
|---|-------|------------|
| Duration | ~5 sec | 5–15 min |
| Writes files | no | yes |
| Spawns agents | no | yes (Validator → Conductor → Guard + analysis + doc-writer) |
| Good for | weekly check, pre-commit, "am I drifting?" | monthly audit, post-refactor |
| Reads orchestration state | yes (.workforce/) | yes (.workforce/) |

---

## Procedure

### Step 1 — Run the health score script

```bash
FOUNDATION_ROOT=$(cat ~/.foundation-path 2>/dev/null)
if [[ -z "$FOUNDATION_ROOT" ]]; then
  echo "Foundation/Workforce not installed. Run install.sh from the repo first."
  exit 1
fi
python3 "$FOUNDATION_ROOT/scripts/health_score.py" --project-dir . --json > /tmp/sync-score.json
```

### Step 2 — Peek at orchestration state (read-only)

Optional: if `.workforce/` exists, surface the most recent orchestration artifacts so the operator sees where the project is in its current workflow.

```bash
WF=".workforce"
if [[ -d "$WF" ]]; then
  test -f "$WF/intent.md"          && INTENT_AGE=$(date -ur "$WF/intent.md"          +%s 2>/dev/null || stat -f%m "$WF/intent.md")
  test -f "$WF/dispatch.md"        && DISPATCH_AGE=$(stat -f%m "$WF/dispatch.md"        2>/dev/null)
  test -f "$WF/alignment-report.md" && ALIGN_AGE=$(stat -f%m "$WF/alignment-report.md"  2>/dev/null)
  test -d "$WF/status"             && STATUS_FILES=$(ls -1 "$WF/status"/*.json 2>/dev/null | wc -l | tr -d ' ')
fi
```

Read these (no shell required — use the Read tool):
- `.workforce/intent.md` — first 3 lines (the title) + the timestamp on disk.
- `.workforce/alignment-report.md` — extract `## Status` line (PASS / PASS-WITH-NOTES / BLOCK).
- `.workforce/status/*.json` — count how many engineers reported DONE vs BLOCKED in the last run.

If `.workforce/` doesn't exist, skip this step. Note in the summary: `Orchestration: no .workforce/ — never run`.

### Step 3 — Parse and render

Read `/tmp/sync-score.json` and any `.workforce/` state, then produce:

```
PROJECT SYNC — <project name from CLAUDE.md or dir name>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Health:
  Vision      <N>/10  <one-line status>
  Docs        <N>/10  <one-line status>
  Security    <N>/10  <one-line status>
  Agents      <N>/10  <one-line status>
  Workplan    <N>/10  <one-line status>
  ─────────────────
  Overall     <N>/50  <band label>

Orchestration state (.workforce/):
  Intent:           <captured YYYY-MM-DD | not present>
  Last dispatch:    <YYYY-MM-DD HH:MM | none>
  Last alignment:   <PASS | PASS-WITH-NOTES | BLOCK | none>
  Engineers (last run): <N DONE / M BLOCKED / K total>

Bands:
   0–15  critical — run /workforce with full plan
  16–30  attention — run /workforce, accept recommended agents
  31–40  healthy — drift check; /workforce vision-only if nothing specific
  41–50  excellent — continue building, no action

Drift indicators:
  - <any individual dimension below 4 — list with suggested action>
  - <stale docs from docs_status>
  - <BLOCKED engineers in the last run that haven't been resolved>
  - <alignment-report.md status BLOCK that hasn't been re-checked>

Recommended next action:
  <one sentence — pinned to the lowest-scoring dimension OR the freshest BLOCK>
```

### Step 4 — Do nothing else

That's it. Do not spawn agents. Do not write files. Do not commit. The user sees the summary and decides whether to escalate to `/workforce` or continue.

---

## Edge cases

- **No `~/.foundation-path`**: the installer wasn't run. Print the install command and exit.
- **Script returns non-zero**: print the error verbatim and suggest running `git status` to ensure the project is in a clean state.
- **Project is empty (no files)**: print "This project looks empty — use `/foundation` instead to bootstrap it." Do not compute scores.
- **Not a git repo**: scores will be lower-quality (no commit history for staleness). Note this in the output.
- **`.workforce/` exists but is empty / partial**: a half-finished run. Note "Orchestration: incomplete run detected" and recommend `/workforce` to resume.
- **`.workforce/alignment-report.md` is BLOCK**: surface the BLOCK first; the lowest health score is no longer the right primary recommendation.

---

## Rules

- Never spawn agents from `/sync`
- Never write files (not even `.sync-log` — keep it pure)
- Never suggest what to do next in vague terms — always a specific action tied to the lowest-scoring dimension OR the freshest unresolved BLOCK from `.workforce/alignment-report.md`
- Runs must complete in under 10 seconds; if the health script hangs, interrupt and report "health score timed out"
- A BLOCK in `.workforce/alignment-report.md` takes precedence over a low health score — surface it first
