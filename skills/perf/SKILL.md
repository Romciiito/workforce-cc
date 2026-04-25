---
name: perf
description: >
  Slim wrapper around the performance-analyst engineer. Triggers on /perf,
  "perf check", "why is this slow", "pre-launch perf review". Spawns ONLY
  performance-analyst — no orchestration, no other agents. Produces
  performance-model.md with bottleneck ranking, measurement plan, and
  remediation sequencing. Read-only diagnosis; never fixes anything.
---

# /perf — Performance Diagnosis

You are the entry point for a focused performance-analyst run. Your job is to spawn the `performance-analyst` agent against the current project, surface its output, and exit. No orchestration spine, no alignment guard, no integration step — `/perf` is the lightweight equivalent of `/sync` for performance.

This skill exists because:

- `/foundation` and `/workforce` are heavyweight; you don't want to run a full pipeline just to surface bottlenecks before a launch.
- `/sync` is read-only and gives a 5-second health summary; it doesn't read source code.
- Sometimes the operator wants exactly one engineer's analysis, not an integrated multi-engineer run.

---

## When to trigger

- `/perf`
- "why is this slow"
- "perf check before launch"
- "pre-launch perf review"
- "what's likely to bottleneck under load"
- Whenever the operator wants performance-analyst's output without `/foundation` or `/workforce` ceremony.

---

## When NOT to trigger

- The performance issue requires a fix, not a diagnosis. Use `/workforce` (which can dispatch performance-analyst + debugger) or invoke debugger directly.
- The performance-model.md was already generated recently (read it first; re-running without new code is wasted analysis).
- The project has no architecture.md or major source files yet. performance-analyst needs something concrete to analyse.

---

## Procedure

### Step 1 — Verify the project has enough context

```bash
test -f architecture.md && test -d src/
```

If either is missing, halt and surface to the user:

```
/perf needs a project to analyse. I don't see architecture.md or a src/ directory.
- If this is a greenfield project, run /foundation first.
- If the project is in a non-standard layout, point me at the file or
  directory you want analysed.
```

### Step 2 — Read existing performance-model.md (if any)

If `performance-model.md` exists and was modified within the last 7 days, mention it to the user and ask whether to:

- **Replace it** — re-run performance-analyst from scratch.
- **Refine it** — performance-analyst reads the existing file as a starting point and adds findings.
- **Just read it** — surface the existing file's top three findings; don't re-run.

If no recent file exists, proceed.

### Step 3 — Spawn performance-analyst

```
Spawn: performance-analyst
  Reads:  architecture.md (required), source code (project),
          security-model.md (if exists, for perf-relevant controls),
          requirements.md (NFRs)
  Output: performance-model.md
```

The agent runs Opus per its frontmatter. It writes a single artifact and exits.

### Step 4 — Surface the top findings

Read the new (or refined) `performance-model.md` and print:

```
PERFORMANCE DIAGNOSIS — <project>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Top bottlenecks (highest impact first):

  1. <one-line summary>            — <NFR cite>
  2. <one-line summary>            — <NFR cite>
  3. <one-line summary>            — <NFR cite>

Measurement plan: <one sentence — when to run it, what tool>

Recommended sequencing (don't optimise out of order):
  Phase 1 (next 2 weeks):  <items>
  Phase 2 (post-MVP):      <items>
  Tracked but not now:     <items>

Full report:  performance-model.md
```

Do not optimise anything. Do not spawn other agents. The user reviews the report and decides whether to escalate to `/workforce` or to dispatch a code-side fix.

---

## Edge cases

- **`performance-model.md` already exists and is fresh (< 24h)**: ask the user before re-running. Performance analysis is wasted work without new code.
- **Project has no NFRs (`requirements.md` missing or thin)**: performance-analyst will note this and produce a thinner ranking. Surface the gap to the user — recommend `/workforce` to fill in NFRs first.
- **Project is a CLI / static site**: most "perf" concerns are bundle size, startup time, and not server load. performance-analyst handles this; just surface to the user that the report focuses on the right axes.
- **Project has 100k+ files**: performance-analyst sample-reads strategically; this is a known limitation. The report's "areas not analysed" section flags what was skipped.

---

## Rules

- Spawn only performance-analyst. No alignment-guard, no conductor, no other engineers.
- Never write performance-model.md yourself. The agent writes it.
- Never recommend a specific code change. The performance-analyst's role ends at ranking + measurement; fixing is a different agent's job.
- If the user asks "now fix the top bottleneck", point them to `/workforce` with backend-developer or debugger in the plan.
