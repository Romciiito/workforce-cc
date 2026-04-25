# workforce-cc

Agentic workflows for Claude Code (and four other harnesses). Six slash commands that cover the full lifecycle of a software project, sharing a common multi-terminal pipeline:

| Skill | When to use | What it produces |
|-------|-------------|------------------|
| **`/foundation`** | Greenfield — empty directory, a rough idea | A validated `intent.md`, full design pipeline, scaffolded project, drift-checked workplan, 6 project-specific build agents |
| **`/workforce`** | Existing project — running or stale | A health score, a (conditional) `intent.md`, conservative plan of which agents to run, missing docs created, drift report |
| **`/sync`** | Any moment you want a 5-second health check | A one-screen summary — no agents, no file writes |
| **`/perf`** | Pre-launch — "why is this slow / what'll bottleneck under load?" | `performance-model.md` — top-3 bottlenecks, measurement plan, sequencing |
| **`/security`** | Threat model / auth review / pre-launch security check | `security-model.md` — CRITICAL/HIGH threats, Phase 0 checklist, compliance verdicts |
| **`/harness`** | Add Cursor/Codex/Gemini support to an existing project | Adapter files for selected harnesses |

The first three flow through one shared backbone: **Intent Validator → Conductor → Alignment Guard**, with each engineer-agent running in its own terminal with its own 1M context window. Communication is via artifacts on disk, not in-conversation handoffs. The last three are slim wrappers around a single engineer (`performance-analyst`, `security-analyst`) or the harness installer.

---

## Install

```bash
git clone https://github.com/Romciiito/workforce-cc ~/.foundation
cd ~/.foundation && ./install.sh
```

Common forms:

```bash
./install.sh                                            # install everything (legacy, == --profile full)
./install.sh --profile foundation                       # greenfield bootstrap only
./install.sh --profile workforce                        # existing-project audit only
./install.sh --profile minimal                          # just /sync; no agents, no hooks
./install.sh --harnesses claude,cursor                  # adapters for two harnesses
./install.sh --harnesses claude,cursor,codex,opencode,gemini  # all five
./install.sh --dry-run                                  # preview without writing
./install.sh --force                                    # overwrite existing agent files
./install.sh --uninstall                                # remove everything this installer placed

# Legacy flags still work:
./install.sh --only foundation
./install.sh --only workforce
```

The installer:

1. Symlinks each profile's skills into `~/.claude/skills/`.
2. Copies agents from `agents/_shared/`, `agents/orchestrators/`, `agents/foundation/`, `agents/workforce/` into `~/.claude/agents/` (per profile).
3. Writes the repo path to `~/.foundation-path`, the profile name to `~/.workforce-profile`, and the harness selection to `~/.workforce-harnesses`.

Dependencies: `python3`, `git`, and (for `/foundation` only) `npx` + `jinja2` (`pip install jinja2`).

---

## Supported AI-coding-agent harnesses

workforce-cc was originally a Claude Code system, but it now ships adapter files for five harnesses. Each adapter writes harness-specific context into a project so the workforce-cc artifacts (intent, dispatch, alignment-report, ADRs) are visible to whatever harness the user runs.

| Harness | Files written | Orchestration support |
|---|---|---|
| **claude** | `CLAUDE.md`, `.claude/agents/`, `.claude/settings.local.json` | Full — runs all orchestrator agents |
| **cursor** | `.cursor/rules/00-workforce-cc.mdc`, `.cursor/rules/01-orchestration-pointers.mdc` | Context-only |
| **codex** | `AGENTS.md` | Context-only |
| **opencode** | `.opencode/agents/workforce-cc.md` | Context-only |
| **gemini** | `GEMINI.md` | Context-only |

**"Context-only"** means the harness sees the workforce-cc artifacts and recommends running `/foundation`, `/workforce`, `/sync`, or `/perf` in Claude Code when the user wants orchestration. The harness doesn't run intent-validator / conductor / alignment-guard itself.

Select harnesses two ways:

```bash
# Use a profile's default (each profile defaults to ['claude']):
./install.sh --profile full

# Override the profile's harness list at install time:
./install.sh --profile full --harnesses claude,cursor

# Explicit selection without a profile:
./install.sh --harnesses claude,codex,gemini
```

Per-project rendering is driven by [`scripts/harness_install.py`](scripts/harness_install.py), which reads `harnesses/<name>/manifest.json` and applies each declared `writes` entry. See [`harnesses/README.md`](harnesses/README.md) for the adapter framework.

---

## The three-role spine

```
       ┌──────────────────┐
prompt │ Intent Validator │  → .workforce/intent.md
       └────────┬─────────┘
                │  (refuses to dispatch until intent.md is falsifiable)
                ▼
       ┌──────────────────┐
       │ Conductor        │  → .workforce/dispatch.md
       │   --mode=dispatch│
       └────────┬─────────┘
                │  (per-engineer contracts: territory / inputs / outputs / verification)
                ▼
   ┌────────────┴────────────┐
   │  N engineer terminals    │  each in its own 1M context, separate tmux window or `claude --print`
   │  (architect, security-  │  each writes:
   │   analyst, ...)          │    runs/<ts>/<engineer>/approach.md
   │                          │    <declared output>.md (e.g. architecture.md)
   │                          │    status/<engineer>.json (RUNNING|BLOCKED|DONE)
   └────────────┬─────────────┘
                │
                ▼
       ┌──────────────────┐
       │ Conductor        │  polls status/*.json
       │   --mode=monitor │  (BLOCKED → escalating retry; all-DONE → next gate)
       └────────┬─────────┘
                ▼
       ┌──────────────────┐
       │ Alignment Guard  │  → .workforce/alignment-report.md
       │   --mode=cross-  │  PASS / PASS-WITH-NOTES / BLOCK
       │   check or vision│  (HIGH severity → BLOCK, mechanically)
       └────────┬─────────┘
                ▼
       ┌──────────────────┐
       │ Conductor        │  → .workforce/integration.md
       │   --mode=integrate│ (cross-cuts, blocked items, next dispatch)
       └────────┬─────────┘
                ▼
              DONE
```

The roles live in [`agents/orchestrators/`](agents/orchestrators/) and the shared backbone documentation is in [`skills/_backbone/BACKBONE.md`](skills/_backbone/BACKBONE.md).

---

## Two execution modes — and which one you actually triggered

workforce-cc dispatches engineer agents in **two different ways** depending on whether you're inside a tmux session. They produce visibly similar conversations but have very different runtime properties.

### Mode A — single-session sub-agents (default, no tmux)

When you run `/foundation` or `/workforce` without tmux, Claude Code's built-in `Agent` tool fans out **sub-agents inside your current session**. The conductor and N engineers all run as part of one Claude Code conversation.

- **Context**: all sub-agents share **one 1M-token window** with your main session.
- **Model / settings**: every sub-agent inherits whatever your session is using.
- **Comm**: sub-agents return text to the parent agent within Claude's runtime.
- **Good for**: small-to-medium projects where one 1M window is enough budget.
- **Failure mode**: large projects (~70+ tasks, many parallel tracks) exhaust context before integration.

This is what most users get out of the box. No special setup needed; the `Agent` tool ships with Claude Code.

### Mode B — multi-terminal, separate `claude` processes (tmux required)

When you launch `pipeline_runner.py dispatch-wave` from inside a tmux session, the conductor's `dispatch.md` is parsed and **each engineer is spawned as its own `claude` process** in a separate tmux window.

- **Context**: each engineer gets its **own** 1M-token window (separate API session).
- **Model / settings**: each engineer can run on a different model, with its own permission mode (`default | plan | auto | bypass`), its own hooks.
- **Comm**: engineers communicate **only** via files on disk — `runs/<ts>/<engineer>/approach.md` (plan-before-action), the declared outputs (e.g. `architecture.md`), and `status/<engineer>.json` (`RUNNING | BLOCKED | DONE`). The conductor polls the status files; nothing happens in conversation.
- **Good for**: large projects, long-running runs, debugging an engineer that misbehaves (its terminal is right there to inspect).
- **Failure mode**: extra setup (tmux must already be running); harder to follow the whole arc visually because attention is split across windows.

### How to trigger each mode

| You want | What to run |
|---|---|
| Mode A (sub-agents in your session) — most users | `claude` → `/foundation` or `/workforce`. Done. |
| Mode B (real separate terminals) — large projects | `tmux new -s workforce` first, then `claude` → `/foundation` or `/workforce`. After the conductor writes `.workforce/dispatch.md`, run `python3 ~/.foundation-path/scripts/pipeline_runner.py dispatch-wave --from .workforce/dispatch.md --wave 1 --mode tmux` from any tmux window. New windows open per engineer. |
| Mode B headless (no live windows) | `pipeline_runner.py dispatch-wave --mode background` — engineers run as `nohup claude --print` processes; logs land in `.tmp/track-<engineer>.log`. |
| Just print the spawn commands | `pipeline_runner.py dispatch-wave --mode print` — it tells you what to copy into separate terminals manually. |

### How to verify which mode you're in

Run, in another window of the same project:

```bash
python3 ~/.foundation-path/scripts/pipeline_runner.py status --project-dir .
```

If the command finds `.workforce/status/<engineer>.json` files, you're in Mode B — those status files only get written by separately-spawned `claude` processes. If the directory is empty (or `.workforce/` doesn't exist), you ran Mode A: the sub-agents lived inside your session and never wrote per-engineer status to disk.

### Why we built it both ways

Mode A is what Claude Code gives you natively — fine for small projects. Mode B is the escape hatch for projects where one shared 1M window isn't enough budget, or where you want each engineer's reasoning visible in real time.

If you ran `/foundation` recently and didn't have tmux open, **you were in Mode A**. The visible "spawning architect, security-analyst, …" output is real — the system did fan out, integrate, and produce artifacts — but every sub-agent shared the same 1M context with your main session. For your next run, if the project has more than ~30 tasks or multiple long-context dependencies (architecture + spec + workplan all need to be considered together), try Mode B.

---

## Repository layout

```
workforce-cc/
├── install.sh                ← unified installer (--profile, --only, --dry-run, --uninstall, --force)
├── profiles/                 ← install profiles (full, foundation, workforce, minimal)
├── skill-catalog.json        ← stack → recommended Claude skills map
│
├── skills/
│   ├── foundation/SKILL.md   ← /foundation pipeline (Phase -1 intent → Phase 4 build team)
│   ├── workforce/SKILL.md    ← /workforce pipeline (scan → score → conditional intent → audit → drift)
│   ├── sync/SKILL.md         ← /sync read-only health check
│   └── _backbone/            ← canonical Validator → Conductor → Guard spine + 4 templates
│
├── agents/
│   ├── orchestrators/        ← the three new roles
│   │   ├── intent-validator.md
│   │   ├── conductor.md
│   │   └── alignment-guard.md
│   ├── _shared/              ← engineer pool (architect, security-analyst, requirements-engineer,
│   │                            agent-generator, agent-router, performance-analyst, test-strategist)
│   ├── foundation/           ← greenfield-only engineers (idea-refiner, market-researcher,
│   │                            stack-selector, output-validator, workplan-builder, model-selector,
│   │                            foundation-orchestrator [DEPRECATED])
│   ├── workforce/            ← audit-only engineers (scanner, gap-analyst, vision-keeper [DEPRECATED],
│   │                            doc-writer, workforce-orchestrator [DEPRECATED])
│   └── deprecated/           ← migration policy + future home for the four legacy orchestrators
│
├── catalogs/
│   ├── ecc/                  ← curated mirror of affaan-m/everything-claude-code (fetched on first sync)
│   ├── workforce/            ← per-project allowlist template
│   └── schema.json           ← JSON Schema for catalog index files
│
├── hooks/
│   ├── dispatcher.sh         ← profile-gated hook runner
│   ├── governance.sh         ← JSONL audit trail of orchestration decisions
│   └── config-protection.sh  ← blocks edits to lint/format/CI configs
│
├── scripts/
│   ├── workforce_paths.py    ← read-shim for .workforce/ vs project root
│   ├── pipeline_runner.py    ← spawn engineers (envelope-by-default), poll status, blocked-scan
│   ├── spawn_payload.py      ← SpawnPayload + StatusRecord dataclasses
│   ├── catalog_sync.py       ← populate catalogs/ecc/ from upstream clone
│   ├── catalog_check.py      ← validate index ↔ bodies, drift detection
│   ├── catalog_query.py      ← list/show/enable/disable catalog entries
│   ├── migrate_legacy_orchestrators.py  ← rewrite installed legacy agents into shims
│   ├── health_score.py       ← 5-dimension scoring (used by /workforce + /sync)
│   ├── scaffold.py           ← Jinja2 templates → project structure (env_prefix, etc.)
│   ├── suggest_skills.py     ← stack → recommended skills
│   ├── install_skill.py      ← npx skills add <name>
│   ├── telemetry.py          ← opt-in JSONL log; auto-enabled in multi-terminal mode
│   └── export_to_workforce_agi.py  ← export agents as ESM skill modules
│
├── templates/
│   ├── agents/_envelope.md.jinja  ← engineer task envelope (rendered into every spawn prompt)
│   ├── agents/*.md.jinja          ← build-agent templates rendered by scaffold.py
│   ├── docs/                      ← architecture, development, design-decisions, env-vars
│   ├── github-actions/            ← CI templates per stack
│   ├── stacks/<name>/structure.json  ← scaffold structure per stack
│   └── workflows/                 ← bug-fix.md, feature-dev.md
│
├── tests/                    ← 295 pytest tests covering scripts, install.sh, agents, skills
├── docs/
│   ├── artifact-contract.md  ← canonical owner/readers/schema for every artifact
│   ├── architecture.md       ← repo architecture
│   └── how-it-works.md       ← Foundation/Workforce design walkthrough
└── .github/
    └── workflows/{test.yml,link-check.yml}
```

---

## Artifacts

Every artifact has exactly one writer (the role that owns it) and zero or more readers. The full list lives in [`docs/artifact-contract.md`](docs/artifact-contract.md).

**Per-project orchestration artifacts** (under `.workforce/`):

| Artifact | Owner | Purpose |
|---|---|---|
| `intent.md` | `intent-validator` | Falsifiable goal: who, what, success, constraints, out-of-scope, open questions |
| `dispatch.md` | `conductor[dispatch]` | Per-engineer contracts: territory, inputs, outputs, verification, escalation |
| `runs/<ts>/<eng>/approach.md` | engineer | Plan-before-action: goal restated, plan, risks, verification |
| `status/<engineer>.json` | engineer | RUNNING / BLOCKED / DONE with artifacts list |
| `BLOCKED.md` | engineer (optional) | What I tried / Why blocked / What unblocks me |
| `alignment-report.md` | `alignment-guard` | PASS / PASS-WITH-NOTES / BLOCK + findings + required actions |
| `integration.md` | `conductor[integrate]` | Run summary, artifacts produced, cross-cuts, next dispatch |

**Engineer outputs** (project root, unchanged from before): `brainstorm.md`, `spec.md`, `security-model.md`, `requirements.md`, `architecture.md`, `stack-decision.md`, `validation-report.md`, `workplan.md`, `vision.md`, `WORKFORCE.md`, `project-snapshot.md`, `decisions.md`, `claude-rules.md`.

A read-shim ([`scripts/workforce_paths.py`](scripts/workforce_paths.py)) reads from either `.workforce/` or the project root, so legacy projects keep working.

---

## Catalogs

The `catalogs/` directory holds curated mirrors of upstream agent/skill/command sets, redistributed under their original licenses with attribution.

- [`catalogs/ecc/`](catalogs/ecc/) — mirror of [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code) (MIT). Populated by `python3 scripts/catalog_sync.py --from /path/to/upstream/clone`. Each entry's body lives under `bodies/`; metadata + provenance hash in `index.json`.
- [`catalogs/workforce/enabled.json`](catalogs/workforce/enabled.json) — per-project allowlist. Empty by default. Conductor reads this when extending the engineer pool.

```bash
# List catalog contents
python3 scripts/catalog_query.py list --kind agent

# Enable an entry for the current project
python3 scripts/catalog_query.py enable ecc.agent.security-reviewer

# Show what's enabled
python3 scripts/catalog_query.py enabled
```

`catalogs/<source>/index.json` follows the JSON Schema in [`catalogs/schema.json`](catalogs/schema.json). New catalogs (e.g. `catalogs/<my-source>/`) follow the same pattern.

---

## Engineers as engineers, not script-followers

Every dispatched engineer receives the same envelope (rendered from [`templates/agents/_envelope.md.jinja`](templates/agents/_envelope.md.jinja)):

- Goal restated, constraints, exact inputs and outputs.
- Verification command(s) the engineer commits to running before declaring DONE.
- Adversarial self-critique block (verification avoidance, seduced by the first 80%, three-reviewer test).
- Read-only constraint on files outside declared territory.
- BLOCKED.md schema for clean exits when stuck.
- Mandate to write `approach.md` *before* producing outputs.

The same shape lives directly in the most-used engineer prompts (`architect`, `security-analyst`, `requirements-engineer`) so they carry the discipline whether dispatched by the conductor or invoked directly.

---

## Hooks

Profile-gated; safe to call unconditionally — the dispatcher silently no-ops if a hook isn't enabled in the current profile.

```bash
# List enabled hooks for the current profile
~/.foundation-path/hooks/dispatcher.sh list

# Fire one hook
~/.foundation-path/hooks/dispatcher.sh fire governance \
  alignment-guard pass "no findings"
```

Shipped hooks:

- **`governance.sh`** — JSONL audit trail of orchestration decisions (`alignment-guard pass`, `conductor dispatch`, `intent-validator captured`, …) into `.foundation-memory/governance.jsonl`. Honors `WORKFORCE_TELEMETRY=off` and `WORKFORCE_MULTI_TERMINAL=1`.
- **`config-protection.sh`** — refuses writes to lint/format/typecheck/CI configs (`.eslintrc.*`, `pyproject.toml`, `tsconfig.json`, etc.) unless `WORKFORCE_ALLOW_CONFIG_EDIT=1`. Pattern from everything-claude-code; fresh implementation.

Disable per-hook at runtime: `WORKFORCE_DISABLED_HOOKS=governance,config-protection`. Override the profile entirely: `WORKFORCE_HOOK_PROFILE=minimal`.

---

## Tests

```bash
make install-dev       # pip install -e ".[test]"
make test              # python -m pytest
```

Or manually:

```bash
pip install -e ".[test]"
pytest
```

CI (`.github/workflows/test.yml`) runs the suite on Python 3.11/3.12/3.13 + a shellcheck pass on every push and pull request. `link-check.yml` runs lychee on all `.md` files weekly.

See [tests/README.md](tests/README.md) for what each test file covers.

## Make targets

A [`Makefile`](Makefile) wraps the common operations. Run `make help` to see all targets. Highlights:

```bash
make install              # ./install.sh — claude only, default profile
make install-all          # all five harnesses
make install-minimal      # just /sync, no agents/hooks
make install-dry-run      # preview without writing
make uninstall

make test                 # full pytest suite
make lint                 # bash + python smoke checks (+ shellcheck if installed)
make status               # repo + beacons + test count

make catalog-validate     # check catalogs/ index ↔ bodies + license gate
make catalog-sync ECC_PATH=/path/to/upstream-clone
make mcp-list             # list MCP servers in catalogs/mcp/

make harness-apply        # re-apply ~/.workforce-harnesses adapters here
make harness-apply-all    # apply all five harnesses to current project

make clean                # .pytest_cache, __pycache__, .tmp/, *.egg-info
```

---

## Typical flow

### New project

```
$ mkdir my-saas && cd my-saas
$ claude
> /init
> /foundation
  Phase -1 intent-validator: refuses to dispatch until your idea is falsifiable
  Phase 0 brainstorm
  Phase 1A parallel analysis (4 agents in their own terminals)
  Phase 1B architect + stack-selector
  Phase 1B.5 output-validator
  Phase 1C workplan-builder
  Phase 2 skill suggestions
  Phase 3 scaffold
  Phase 3.5 user confirmation
  Phase 3.6 alignment-guard --mode=vision  (BLOCK halts Phase 4)
  Phase 4 agent-generator + foundation-orchestrator activation
```

### Existing project

```
$ cd some-existing-repo
$ claude
> /workforce
  Phase 0 scan
  Phase 0.5 intent-validator (conditional — fires only when request is vague AND no recent vision.md)
  Phase 1 workforce-orchestrator scoring
  Phase 1.5 user review of plan
  Phase 2 conditional agent spawning
  Phase 3 conservative doc creation
  Phase 4 agent-generator (if in plan)
  Phase 4.5 alignment-guard --mode=vision (advisory — non-mutating)
  Phase 5 health record update
```

### Quick daily check

```
> /sync
  Vision      9/10
  Docs        7/10
  Security    5/10  ← attention: security-model.md Phase 0 has 4 unchecked items
  Agents      8/10
  Workplan    9/10
  Overall    38/50  healthy — drift check only
  Recommendation: run /workforce and accept security-analyst in the plan
```

### Multi-terminal dispatch (manual driver)

```bash
# Conductor writes the dispatch
claude --print "/conductor --mode=dispatch"

# Fire an entire wave (parses dispatch.md, spawns each engineer in its own terminal)
python3 scripts/pipeline_runner.py dispatch-wave --from .workforce/dispatch.md --wave 1

# Watch progress
python3 scripts/pipeline_runner.py status --expect architect,security-analyst,requirements-engineer

# After all DONE, run the alignment guard
claude --print "/alignment-guard --mode=cross-check"

# Then integrate
claude --print "/conductor --mode=integrate"
```

For the full multi-terminal walkthrough — including BLOCKED-engineer handling, audit-trail layers, and troubleshooting — see [`docs/running-a-session.md`](docs/running-a-session.md).

---

## License

MIT. See `LICENSE` if present, or file an issue asking for it.
