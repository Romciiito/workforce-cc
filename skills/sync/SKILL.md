---
name: sync
description: >
  Lightweight health check for an existing Foundation or Workforce project.
  Triggers on /sync, "quick check", "sync my project", "how healthy is this",
  or "sync". Runs the workforce health_score.py script and prints a one-screen
  summary with scores, drift indicators, and a recommended next action
  (foundation rerun, full workforce, or proceed). Does NOT spawn any agents,
  does NOT create any files — pure read-only assessment. Runs in ~5 seconds.
---

# /sync — Quick Health Check

You are the entry point for a fast, read-only health check of an existing project. Your job is to run one script, parse its output, and suggest the next action — without spawning agents, without creating files, without modifying anything.

Use `/sync` as the light-touch alternative to `/workforce`:

| | /sync | /workforce |
|---|-------|------------|
| Duration | ~5 sec | 5–15 min |
| Writes files | no | yes |
| Spawns agents | no | yes (analysis + doc-writer) |
| Good for | weekly check, pre-commit, "am I drifting?" | monthly audit, post-refactor |

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

### Step 2 — Parse and render

Read `/tmp/sync-score.json` and produce this summary (extract every number from the JSON; do not estimate):

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

Bands:
   0–15  critical — run /workforce with full plan
  16–30  attention — run /workforce, accept recommended agents
  31–40  healthy — drift check; /workforce vision-only if nothing specific
  41–50  excellent — continue building, no action

Drift indicators:
  - <any individual dimension below 4 — list with suggested action>
  - <stale docs from docs_status>

Recommended next action:
  <one sentence — e.g. "Run /workforce — security score 3 means security-model.md is missing">
```

### Step 3 — Do nothing else

That's it. Do not spawn agents. Do not write files. Do not commit. The user sees the summary and decides whether to escalate to `/workforce` or continue.

---

## Edge cases

- **No `~/.foundation-path`**: the installer wasn't run. Print the install command and exit.
- **Script returns non-zero**: print the error verbatim and suggest running `git status` to ensure the project is in a clean state.
- **Project is empty (no files)**: print "This project looks empty — use `/foundation` instead to bootstrap it." Do not compute scores.
- **Not a git repo**: scores will be lower-quality (no commit history for staleness). Note this in the output.

---

## Rules

- Never spawn agents from `/sync`
- Never write files (not even `.sync-log` — keep it pure)
- Never suggest what to do next in vague terms — always a specific action tied to the lowest-scoring dimension
- Runs must complete in under 10 seconds; if the health script hangs, interrupt and report "health score timed out"
