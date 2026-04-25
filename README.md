# Foundation + Workforce

Agentic workflows for Claude Code. One repo, two complementary skills that cover the full lifecycle of a software project:

| Skill | When to use | What it produces |
|-------|-------------|------------------|
| **`/foundation`** | Greenfield — empty directory, a rough idea | A fully scaffolded project with security baked in, a workplan, and 6 project-specific build agents |
| **`/workforce`** | Existing project — running or stale | A health score, a conservative plan of which agents to run, missing docs created, existing docs flagged |
| **`/sync`** | Any moment you want a 5-second health check | A one-screen summary — no agents, no file writes |

Both skills share a common agent pool, template set, and scripts. Switching between them is a keystroke.

---

## Install

```bash
git clone https://github.com/Romciiito/workforce-cc ~/.foundation
cd ~/.foundation && ./install.sh
```

Options:

```bash
./install.sh                 # install both skills + /sync
./install.sh --only foundation
./install.sh --only workforce
./install.sh --force         # overwrite existing agent files
./install.sh --uninstall     # remove everything this installer placed
```

The installer:

1. Symlinks `skills/foundation`, `skills/workforce`, `skills/sync` into `~/.claude/skills/`
2. Copies agents from `agents/_shared/`, `agents/foundation/`, `agents/workforce/` into `~/.claude/agents/`
3. Writes the repo path to `~/.foundation-path` so skills can find the scripts/templates

Dependencies: `python3`, `git`, and (for Foundation only) `npx` + `jinja2` (`pip install jinja2`).

---

## Repository layout

```
foundation/
├── install.sh                ← unified installer (--only foundation|workforce, --force, --uninstall)
├── skill-catalog.json        ← stack → recommended Claude skills map
│
├── skills/                   ← one subdir per slash-command skill
│   ├── foundation/SKILL.md   ← /foundation pipeline
│   ├── workforce/SKILL.md    ← /workforce pipeline
│   └── sync/SKILL.md         ← /sync quick health check
│
├── agents/
│   ├── _shared/              ← usable by both pipelines
│   │   ├── agent-generator.md       (create|diff modes)
│   │   ├── agent-router.md          (picks the right agent for ambiguous requests)
│   │   ├── architect.md
│   │   ├── performance-analyst.md
│   │   ├── requirements-engineer.md
│   │   ├── security-analyst.md
│   │   └── test-strategist.md
│   ├── foundation/           ← only makes sense during greenfield bootstrap
│   │   ├── foundation-orchestrator.md
│   │   ├── idea-refiner.md
│   │   ├── market-researcher.md
│   │   ├── model-selector.md
│   │   ├── output-validator.md
│   │   ├── stack-selector.md
│   │   └── workplan-builder.md
│   └── workforce/            ← only makes sense on existing projects
│       ├── workforce-orchestrator.md
│       ├── scanner.md
│       ├── gap-analyst.md
│       ├── vision-keeper.md
│       └── doc-writer.md
│
├── scripts/                  ← deterministic helpers, called from SKILL.md files
│   ├── scaffold.py           ← renders templates + stack structure into a target dir
│   ├── suggest_skills.py     ← compares installed skills vs. skill-catalog.json
│   ├── install_skill.py      ← npx skills add <name>
│   ├── health_score.py       ← 5-dimension scoring (used by /workforce + /sync)
│   ├── pipeline_runner.py    ← turns orchestrator decisions into tmux/background spawns
│   └── telemetry.py          ← opt-in JSONL log in .foundation-memory/telemetry.jsonl
│
├── templates/                ← Jinja2 templates rendered into new projects
│   ├── CLAUDE.md.jinja   workplan.md.jinja   vision.md.jinja   WORKFORCE.md.jinja
│   ├── agents/               ← build-agent templates (not used directly — agent-generator writes fresh)
│   ├── docs/                 ← architecture, development, design-decisions, env-vars
│   ├── github-actions/       ← CI templates per stack
│   ├── stacks/               ← one subdir per stack, each with structure.json
│   └── workflows/            ← bug-fix.md, feature-dev.md
│
└── docs/
    ├── how-it-works.md       ← the original Foundation design doc
    └── architecture.md       ← this merged repo's architecture
```

---

## Why one repo

Originally Foundation and Workforce were separate. Splitting them made sense when they had no shared code. Now they share:

- **7 agents** (architect, security-analyst, requirements-engineer, agent-generator, agent-router, test-strategist, performance-analyst)
- **All templates**
- **All scripts** (scaffold, health-score, suggest-skills, pipeline-runner)
- **The installer**

Keeping them in two repos meant every change to `architect.md` had to be double-committed. The merge cost: zero — each skill still has its own `SKILL.md` and its own slash-command.

What stayed separate:

- Each skill has its own pipeline (brainstorm → scaffold vs. scan → score → plan)
- Each has its own orchestrator (`foundation-orchestrator` vs. `workforce-orchestrator`) because they do entirely different work
- Each has its own mode of `agent-generator` (create vs. diff)

---

## New in the merged repo

On top of everything Foundation and Workforce already had, this repo adds:

1. **`agent-router`** (shared) — a meta-agent that decides which specialist to spawn for an ambiguous user request. Useful when the user says "help me with X" without naming an agent.

2. **`test-strategist`** (shared) — writes `test-plan.md` ranking every REQ-F by test layer (unit/integration/E2E/load) and deciding mock-vs-real for each external dep. Runs before `test-writer`.

3. **`performance-analyst`** (shared) — static analysis of likely bottlenecks (N+1 queries, sync I/O, missing indexes, bundle size). Writes `performance-model.md` with ranked items and a measurement plan.

4. **`/sync`** — read-only, sub-10-second health check. Runs `health_score.py`, prints the scores, recommends `/workforce` if something's red, does nothing else.

5. **`pipeline_runner.py`** — turns the orchestrator's "spawn these tracks" decision into actual `tmux` windows or background `claude --print` processes, with a clean fallback to printed instructions. The orchestrator no longer has to re-implement terminal spawning every session.

6. **`telemetry.py`** — opt-in JSONL log at `.foundation-memory/telemetry.jsonl`. Agents record task-start/complete/failed events so you can review what happened across sessions.

7. **Cross-skill handoffs** — `foundation-orchestrator` recommends `/workforce` when it detects drift; `workforce-orchestrator` recommends `/foundation` if the project is effectively greenfield. Neither ever auto-invokes the other — the user stays in control.

---

## Typical flow

### New project
```
$ mkdir my-saas && cd my-saas
$ claude
> /init
> /foundation
  ... brainstorm → analysis → architecture → workplan → scaffold ...
> /foundation-orchestrator picks up Phase 0
```

### Existing project
```
$ cd some-existing-repo
$ claude
> /workforce
  ... scan → score → plan → confirm → run agents → update docs ...
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

---

## Tests

The deterministic helpers (`scripts/`) and the installer (`install.sh`)
ship with a pytest suite. CI runs it on Python 3.11/3.12/3.13 plus a
shellcheck pass on every push.

```bash
pip install pytest jinja2
pytest
```

See [tests/README.md](tests/README.md) for what each test file covers.

---

## License

MIT. See `LICENSE` if present, or file an issue asking for it.
