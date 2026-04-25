# Artifact Contract

This is the canonical list of **every artifact** the workforce-cc system reads or writes during a `/foundation` or `/workforce` run. Each artifact has exactly one **owner** (the role that writes it) and zero or more **readers**. New artifacts must be added here — `tests/test_artifact_contract.py` parses this file and a new artifact appearing anywhere in the codebase that's not declared here will fail CI.

The contract has three classes of artifact:

1. **Orchestration artifacts** — `intent.md`, `dispatch.md`, `integration.md`, `alignment-report.md`, per-engineer `approach.md` and `BLOCKED.md`. Owned by the three orchestrator roles (Intent Validator, Conductor, Alignment Guard) introduced in Chunk 3 and the engineer agents they dispatch. Live under `.workforce/` in the project root.
2. **Engineer outputs** — `brainstorm.md`, `spec.md`, `architecture.md`, `stack-decision.md`, `validation-report.md`, `requirements.md`, `security-model.md`, `market-analysis.md`, `workplan.md`, `vision.md`, `WORKFORCE.md`, `project-snapshot.md`, `decisions.md`. Today these live at the project root and continue to do so for backward compatibility.
3. **Per-run / status artifacts** — `runs/<ts>/<engineer>/approach.md` and `status/<engineer>.json`. Always under `.workforce/`. Excluded from version control by `.workforce/.gitignore`.

## Project-side directory layout

```
<project>/
├── .workforce/
│   ├── intent.md                      ← owner: intent-validator
│   ├── dispatch.md                    ← owner: conductor (dispatch mode)
│   ├── integration.md                 ← owner: conductor (integrate mode)
│   ├── alignment-report.md            ← owner: alignment-guard
│   ├── runs/<ISO_TS>/<engineer>/
│   │   └── approach.md                ← owner: dispatched engineer
│   ├── status/<engineer>.json         ← owner: dispatched engineer
│   └── .gitignore                     ← excludes runs/ and status/
├── brainstorm.md, spec.md, ...        ← engineer outputs (project root, unchanged)
└── ...
```

A read-shim (`scripts/workforce_paths.py`) resolves `intent.md` from either `.workforce/intent.md` or the project root, in that order. Writes go to `.workforce/` only. This means existing projects with root-level orchestration artifacts keep being read; new runs write to the new location.

---

## Orchestration artifacts

### `intent.md`
- **Owner**: `intent-validator` (Chunk 3).
- **Readers**: `conductor`, `alignment-guard`, every dispatched engineer.
- **Required headings**:
  - `## What it is`
  - `## Who it's for`
  - `## Concrete success`
  - `## Constraints`
  - `## Out of scope`
  - `## Open questions`
- **Notes**: Refusal artifact. `intent-validator` will not write this until every section has falsifiable content (no "TBD", no "we'll figure it out").

### `dispatch.md`
- **Owner**: `conductor` (dispatch mode).
- **Readers**: every dispatched engineer, `alignment-guard`.
- **Required headings**:
  - `## Run summary`
  - `## Tasks`
  - For each task under `### Task N — <name>`:
    - `Territory` (file globs the engineer owns)
    - `Inputs` (artifact list)
    - `Outputs` (artifact list)
    - `Verification` (literal command(s))
    - `Success criteria`
    - `Escalation` (when to write `BLOCKED.md`)

### `integration.md`
- **Owner**: `conductor` (integrate mode).
- **Readers**: user, `alignment-guard`.
- **Required headings**:
  - `## Run summary`
  - `## Artifacts produced`
  - `## Cross-cuts`
  - `## Blocked items`
  - `## Next dispatch`

### `alignment-report.md`
- **Owner**: `alignment-guard`.
- **Readers**: `conductor`, user.
- **Required headings**:
  - `## Mode` (one of: `vision`, `cross-check`)
  - `## Status` (one of: `PASS`, `PASS-WITH-NOTES`, `BLOCK`)
  - `## Findings`
  - `## Required actions`

### `runs/<ts>/<engineer>/approach.md`
- **Owner**: the dispatched engineer.
- **Readers**: `conductor` (integrate mode), `alignment-guard`.
- **Required headings**:
  - `## Goal restated`
  - `## Plan`
  - `## Risks`
  - `## Verification`
- **Notes**: Engineer must write this **before** producing the declared output(s). It records what they intend to do and how they'll verify it.

### `BLOCKED.md`
- **Owner**: dispatched engineer (only when blocked — written per engineer, optional).
- **Readers**: `conductor`, user.
- **Required headings**:
  - `## What I tried`
  - `## Why blocked`
  - `## What unblocks me`

### `status/<engineer>.json`
- **Owner**: dispatched engineer.
- **Readers**: `conductor` (monitor mode).
- **Required schema**:
  ```json
  {
    "state": "RUNNING | BLOCKED | DONE",
    "ts": "ISO-8601",
    "engineer": "architect",
    "run_id": ".workforce/runs/<ts>",
    "reason": "free text — required when state=BLOCKED",
    "artifacts": ["architecture.md", "..."]
  }
  ```

---

## Engineer outputs (existing)

These artifacts pre-date the new architecture. They live at the project root, not under `.workforce/`, for backward compatibility with existing projects.

### `brainstorm.md`
- **Owner**: `/foundation` Phase 0 (today).
- **Readers**: `idea-refiner`, `security-analyst`, `market-researcher`, `requirements-engineer`, `vision-keeper`.
- **Schema**: pre-existing; documented in `skills/foundation/SKILL.md` Phase 0.

### `spec.md`
- **Owner**: `idea-refiner`.
- **Readers**: `architect`, `stack-selector`, `output-validator`, `workplan-builder`.
- **Schema**: pre-existing.

### `security-model.md`
- **Owner**: `security-analyst`.
- **Readers**: `architect`, `requirements-engineer`, `output-validator`, `workplan-builder`, scaffold templates.
- **Schema**: pre-existing.

### `market-analysis.md`
- **Owner**: `market-researcher`.
- **Readers**: `architect`, `stack-selector`, `requirements-engineer`.
- **Schema**: pre-existing.

### `requirements.md`
- **Owner**: `requirements-engineer`.
- **Readers**: `architect`, `output-validator`, `workplan-builder`.
- **Schema**: pre-existing.

### `architecture.md`
- **Owner**: `architect`.
- **Readers**: `stack-selector`, `output-validator`, `workplan-builder`, scaffold templates.
- **Schema**: pre-existing.

### `stack-decision.md`
- **Owner**: `stack-selector`.
- **Readers**: `output-validator`, `workplan-builder`.
- **Schema**: pre-existing.

### `validation-report.md`
- **Owner**: `output-validator`.
- **Readers**: user (Phase 1B.5 review), `workplan-builder` (must-PASS gate).
- **Schema**: pre-existing.

### `workplan.md`
- **Owner**: `workplan-builder`.
- **Readers**: `foundation-orchestrator`, all engineer agents, `workforce-orchestrator`, `conductor` (post-Chunk 6).
- **Schema**: pre-existing.

### `vision.md`
- **Owner**: `vision-keeper` (Mode A creates it, Modes B/C update `last_confirmed`).
- **Readers**: `workforce-orchestrator`, `gap-analyst`, `alignment-guard` (post-Chunk 3).
- **Schema**: pre-existing.

### `project-snapshot.md`
- **Owner**: `scanner`.
- **Readers**: `workforce-orchestrator`, `vision-keeper`.
- **Schema**: pre-existing.

### `WORKFORCE.md`
- **Owner**: `/workforce` SKILL Phase 5 (health record).
- **Readers**: `workforce-orchestrator` (last-run context).
- **Schema**: pre-existing.

### `decisions.md`
- **Owner**: any agent (append-only journal).
- **Readers**: any agent, especially `foundation-orchestrator` (last 20 entries for resume context).
- **Schema**: append-only; each entry timestamped.

### `claude-rules.md`
- **Owner**: `workplan-builder` (writes project-specific behavioral rules).
- **Readers**: `scaffold.py` (consumed at Phase 3 to enrich `CLAUDE.md`).
- **Schema**: pre-existing.

---

## Test enforcement

`tests/test_artifact_contract.py` parses this document and asserts:

1. Every artifact has all four required fields (Owner, Readers, headings or schema).
2. Every artifact name referenced in `agents/**/*.md` and `skills/**/*.md` either appears here or matches a wildcard in this contract (e.g. `runs/<ts>/<engineer>/approach.md` matches `runs/.+/.+/approach.md`).
3. No two artifacts share an owner declaration that contradicts another (single-writer invariant).

Before adding a new artifact anywhere in the codebase, **add it here first**.
