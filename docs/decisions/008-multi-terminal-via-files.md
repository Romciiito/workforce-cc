# ADR 008 — Multi-terminal communication via files only

**Status**: Accepted (Chunks 4, 18)

## Context

The user's architectural insistence: each engineer runs in its own terminal with its own 1M context window. This is the design's core commitment — without it, the system is just sequential agent dispatch with extra ceremony.

But isolated 1M windows can't talk to each other in-conversation. The conductor in Terminal 1 can't ask the architect in Terminal 2 a clarifying question mid-flight. Each terminal is a black box from the others' perspective.

The naive options:
1. Have the conductor poll Claude Code's session list and inject messages — fragile, requires deep IDE integration.
2. Have engineers ping a shared queue (Redis, SQS, …) — adds infra dependency to a system that ships zero infra.
3. Communication via files on disk only.

## Decision

**Engineers communicate only through artifacts on disk.** No in-conversation handoffs, no shared queue, no IPC.

The contract:

- The conductor writes `dispatch.md` with per-engineer contracts.
- Each engineer reads its declared inputs (filesystem).
- Each engineer writes its declared outputs (filesystem).
- Each engineer writes a status file (`.workforce/status/<engineer>.json`) with state RUNNING / BLOCKED / DONE.
- The conductor polls the status files (`pipeline_runner.py status`).
- On BLOCKED, the engineer also writes a `BLOCKED.md` describing what it tried and what would unblock it.

The conductor never speaks to engineers directly. It writes contracts and reads results.

## Consequences

**Easier:**
- Zero infrastructure: it's all filesystem.
- Audit trail: every artifact is on disk, version-controllable.
- Fault tolerance: if an engineer's terminal crashes, the status file persists and the conductor can re-dispatch.
- Multi-day projects: pause and resume without losing state.

**Harder:**
- No real-time clarifying questions. If an engineer is uncertain, it writes a BLOCKED.md and exits cleanly. The conductor + user resolve, then re-dispatch with `retry_tier=narrow|broad|fresh`.
- Polling latency. The conductor's `monitor` mode reads status files on each poll; there's an interval. In practice this is fine — engineers run minutes, polls run seconds.
- Engineers can't chat. They learn about each other only via integrated artifacts after the wave completes.

**Accepted:**
- Some classes of work that benefit from real-time back-and-forth (UI iteration with a designer, debug-oriented investigation) don't fit the multi-terminal flow well. Use the legacy single-terminal mode for those.

## Alternatives considered

- **Shared message queue (Redis pub/sub, SQS).** Rejected: adds infra; doesn't help with the actual problem (engineers reasoning in isolated 1M windows).
- **Conductor-as-proxy: engineers send messages to the conductor, who routes.** Rejected: the conductor's job is to manage contracts, not to be a synchronous router. Putting it on the message path makes it a bottleneck.
- **In-process agent dispatch (sub-agents in the same Claude session).** Already supported as the legacy single-terminal flow; multi-terminal is for when *that* is no longer enough.

## Spawn contract

Defined in [`scripts/spawn_payload.py`](../../scripts/spawn_payload.py). Each engineer terminal receives a JSON payload:

```json
{
  "run_id": ".workforce/runs/<ISO_TS>",
  "engineer": "architect",
  "inputs":  ["intent.md", "spec.md"],
  "outputs": ["architecture.md"],
  "status_file": ".workforce/status/architect.json",
  "deadline_min": 30,
  "retry_tier": "none|narrow|broad|fresh",
  "shared_locks": ["workplan.md"]
}
```

The envelope template ([`templates/agents/_envelope.md.jinja`](../../templates/agents/_envelope.md.jinja)) renders this into the engineer's prompt. The shape is borrowed from leaked Claude Code's Tool schema with permission state — patterns only, fresh implementation.

## Sources

- agent-dispatch: per-agent contract + verification field + escalating retry.
- Leaked Claude Code source: Tool schema with permission state (informed the SpawnPayload shape).
- The "files only" discipline is original; the closest priors are CI/CD pipelines (each stage's output is a file) and Make-style build systems (rules read inputs, write outputs, no in-flight communication).
