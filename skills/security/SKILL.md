---
name: security
description: >
  Slim wrapper around the security-analyst engineer. Triggers on /security,
  "threat model", "auth review", "is this secure", "pre-launch security
  review", "owasp check". Spawns ONLY security-analyst — no orchestration,
  no other agents. Produces security-model.md (created or refined) with
  threat model, Phase 0 checklist, compliance verdict. Diagnosis-only;
  fix work is dispatched separately.
---

# /security — Security review

Sister skill to `/perf`. Same shape: spawn one engineer (security-analyst), surface its output, exit. No orchestration spine, no alignment guard, no other engineers.

This skill exists because:

- `/foundation` is heavyweight; you don't want to bootstrap a project to get a threat model for an existing codebase.
- `/workforce` is appropriate but spawns multiple agents; sometimes you want only the security read.
- `/perf` exists for the analogous performance case — symmetric pattern.

## When to trigger

- `/security`
- "threat model"
- "auth review"
- "is this secure"
- "pre-launch security review"
- "OWASP check"
- "should this controller require auth"
- Whenever the operator wants security-analyst's output without `/foundation` or `/workforce` ceremony.

## When NOT to trigger

- The operator wants a *fix*, not a diagnosis. Use `/workforce` (which can dispatch security-analyst + a code-side fixer) or invoke debugger / backend-developer directly with a security finding.
- A current `security-model.md` already exists and is fresh (< 7 days). Read it first. Re-running security-analyst against unchanged code is wasted analysis.
- The project is greenfield and has no `architecture.md` or `spec.md`. security-analyst needs concrete inputs. Run `/foundation` first.

## Procedure

### Step 1 — Verify the project has enough context

```bash
# The agent reads spec.md (or architecture.md) and the source if present.
test -f spec.md || test -f architecture.md || test -d src/
```

If none exist, halt:

```
/security needs a project context. I don't see spec.md, architecture.md,
or a src/ directory.
- For a greenfield project, run /foundation first.
- For a non-standard layout, point me at the file or directory you want
  threat-modeled.
```

### Step 2 — Read existing security-model.md (if any)

If `security-model.md` exists and is fresh (< 7 days), surface its top three Phase 0 items + open risks. Ask whether to:

- **Replace it** — re-run security-analyst from scratch.
- **Refine it** — security-analyst reads the existing file as a starting point and adds/updates findings.
- **Just read it** — surface the existing file's top findings; don't re-run.

If no recent file exists, proceed to Step 3.

### Step 3 — Spawn security-analyst

```
Spawn: security-analyst
  Reads:  spec.md (preferred), brainstorm.md, architecture.md (if exists),
          requirements.md (if exists, for sec-relevant NFRs),
          source code (project) if no spec/architecture
  Output: security-model.md
```

The agent runs Sonnet per its frontmatter. It writes a single artifact and exits.

### Step 4 — Surface the top findings

Read the new (or refined) `security-model.md` and print:

```
SECURITY MODEL — <project>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Top threats (highest severity first):

  CRITICAL  <one-line summary>            — <attack vector>
  HIGH      <one-line summary>            — <attack vector>
  HIGH      <one-line summary>            — <attack vector>

Phase 0 checklist (must complete before MVP ships):
  - [ ] <item>
  - [ ] <item>
  - [ ] <item>
  ... <N> total Phase 0 items

Compliance verdicts:
  - GDPR:    <yes / no / not applicable>
  - SOC 2:   <yes / no / not applicable>
  - HIPAA:   <yes / no / not applicable>
  ... per applicable framework

Full report:  security-model.md
```

Do not implement controls. Do not spawn other agents. The user reviews the report and decides whether to escalate to `/workforce` or to dispatch a code-side fix (backend-developer + code-reviewer).

## Edge cases

- **`security-model.md` exists and is fresh (< 24h)**: ask the user before re-running. Re-analysing without new code yields the same model with shuffled wording.
- **Project has no `architecture.md` or `spec.md`**: security-analyst will produce a thinner model based on source-only inspection. Surface the gap and recommend running `/foundation` to fill in the gaps first.
- **CRITICAL findings**: surface them prominently in the output even if the operator's reaction is "I'll handle that later." Critical means critical.
- **Compliance frameworks not previously declared**: security-analyst will note this as `[NEEDS USER INPUT]`. Surface it; don't guess at applicable frameworks.

## Rules

- Spawn only security-analyst. No alignment-guard, no conductor, no other engineers.
- Never write `security-model.md` yourself. The agent writes it.
- Never recommend a specific code-side fix. security-analyst's role ends at threat-model + checklist + compliance; fixing is a different agent's job.
- Never round CRITICAL down to HIGH because the fix is expensive — surface it as CRITICAL and let the operator decide cost-vs-risk.
- If the user asks "now fix the top threat", point them to `/workforce` with backend-developer + code-reviewer in the plan.
