# ADR 001 — Three orchestrator roles, not one

**Status**: Accepted (Chunks 3, 6, 7, 8, 23)

## Context

Pre-rebuild, the system had two orchestrator agents (`foundation-orchestrator`, `workforce-orchestrator`) doing similar work in different shapes. Adding a third skill would have meant a third orchestrator. Both legacy agents tried to do everything in one prompt: input validation, decomposition, dispatch, integration, drift checking. The result was ambiguity at every gate — does the orchestrator silently accept a vague input, or does it interrogate? Does it author deliverables itself, or only delegate?

A single "god orchestrator" also degrades on long-running projects. Validating intent and integrating cross-cuts are different modes of thought; mixing them in one prompt poisons both.

## Decision

Split orchestration into **three roles**, each with its own agent file under `agents/orchestrators/`:

1. **Intent Validator** — Socratic input gate. Refuses to dispatch until `intent.md` is falsifiable. Three modes: greenfield, revision, pass-through.
2. **Conductor** — Decomposition + dispatch + monitor + integrate. Three sub-modes. **Never authors deliverables.** Manages by defining and enforcing interfaces.
3. **Alignment Guard** — Drift / consistency gate. Two modes: vision (intent vs integrated) and cross-check (engineer outputs vs each other). Returns PASS / PASS-WITH-NOTES / BLOCK.

Both `/foundation` and `/workforce` flow through the same Validator → Conductor → Guard spine, with skill-specific engineer pools.

## Consequences

**Easier:**
- Each role has one clear mode of thought; prompts are sharper.
- Adding a new skill (e.g. `/perf`, `/security`) is straightforward: define an engineer pool and let the spine do the rest.
- Drift is caught at gates, not during integration.

**Harder:**
- Three more agent files to maintain.
- A user who hardcoded the legacy orchestrator names needs to migrate (handled by `scripts/migrate_legacy_orchestrators.py`).

**Accepted:**
- Brief redundancy during the deprecation period — `output-validator` and `vision-keeper` Mode-C overlap with Alignment Guard for one release.

## Alternatives considered

- **One unified orchestrator with sub-modes.** Rejected: the same prompt can't be Socratic AND decisive AND drift-checking; one mode poisons the others.
- **Two roles (Validator + Conductor only).** Rejected: drift goes uncaught until users notice the wrong thing got built. The Guard is the cheapest insurance against silent misalignment.
- **Five+ roles** (separate dispatcher / monitor / integrator / vision-checker / cross-checker). Rejected: fragments the Conductor's coherent through-line; raises operator cognitive load with no payoff.

## Sources

- claude-code-system-prompts: 4-phase coordinator pattern.
- agent-dispatch: per-agent contracts + pipeline gates.
