# ADR 011 — Spawning waves from `dispatch.md`, not from arguments

**Status**: Accepted (Chunk 18)

## Context

Chunk 4 introduced the SpawnPayload + envelope template. The conductor writes per-engineer contracts to `.workforce/dispatch.md` with all fields (territory, inputs, outputs, verification, success criteria, escalation, permission_mode). The original spawn ergonomics required operators to:

1. Read `dispatch.md` by eye.
2. Construct a payload JSON file per engineer.
3. Run `pipeline_runner.py spawn-payload --payload <each-file>` once per engineer.
4. Repeat for each wave.

That's friction that disincentivises the multi-terminal flow the architecture is built around.

## Decision

Add `pipeline_runner.py dispatch-wave --from .workforce/dispatch.md --wave N`. The command:

1. Parses `dispatch.md` per the schema in `skills/_backbone/dispatch.template.md`:
   - `## Run id` — captured for SpawnPayload.run_id.
   - `## Wave order` — numbered list resolves to engineer names.
   - `## Tasks` — `### Task N — <engineer>` headings + bulleted Territory / Inputs / Outputs / Verification / Success criteria / Escalation / (optionally) Permission mode.
2. For each engineer in the chosen wave, builds a SpawnPayload from the parsed task fields.
3. Renders the envelope template with that payload.
4. Spawns the engineer via tmux / background / print mode.

Now the operator workflow is:

```bash
# Conductor writes dispatch.md
claude --print "/conductor --mode=dispatch"

# One command fires the whole wave
python3 scripts/pipeline_runner.py dispatch-wave --from .workforce/dispatch.md --wave 1
```

The parser is forgiving: missing run_id triggers `new_run_id()` per engineer; missing fields default to sensible values; missing inputs default to `["intent.md"]`. The conductor's full schema is the source of truth, but the parser handles minimally-specified dispatch docs gracefully.

## Consequences

**Easier:**
- Running a wave is one command, not N commands.
- The conductor's output (dispatch.md) is the input to the spawner — no payload-JSON intermediary that could drift from the dispatch.
- Dry-run mode (`--dry-run`) lets the operator preview which engineers will spawn before committing.

**Harder:**
- The parser is markdown-not-JSON; new dispatch.md sections need explicit parser support. Mitigation: the schema in `skills/_backbone/dispatch.template.md` is the canonical reference; the parser tracks it.
- Forgiving parsing can mask conductor mistakes (e.g. forgetting an Outputs field). Mitigation: the parser logs missing fields when verbose; the engineer's envelope clearly states "Outputs: (none)" if the parser found nothing.

**Accepted:**
- Markdown is a slightly fragile contract. If the conductor invents new bullet patterns, the parser misses them silently. Mitigation: tests assert the parser handles every documented field.

## Alternatives considered

- **Conductor writes JSON sidecar files per engineer.** Rejected: doubles the artifacts the conductor produces and creates a synchronisation problem (does the human read the .md or the .json?).
- **Operator constructs the payload JSON manually before each spawn.** Rejected: this was the pre-Chunk-18 friction; the whole point is to remove it.
- **Spawn engineer from a single payload file the operator names directly** (`spawn-payload --payload x.json`). Kept as the lower-level command for cases where the operator wants per-engineer customisation; `dispatch-wave` is the wave-level convenience.

## Sources

- agent-dispatch's wave-based dispatch model (their runtime/orchestrator scripts pipe a dispatch document through to multi-agent spawn). Pattern only — fresh implementation against our markdown schema.
