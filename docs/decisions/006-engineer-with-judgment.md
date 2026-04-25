# ADR 006 — Engineer-with-judgment prompt style

**Status**: Accepted (Chunks 4, 12, 14, 20)

## Context

Pre-rebuild, several engineer agents (especially `requirements-engineer`) read as procedural template-fillers. Given the same input, they would produce structurally similar but content-thin output: the right headings populated with restated input, no genuine surfacing of what the upstream brainstorm or spec missed. Multi-terminal dispatch made this worse — engineers in their own 1M context windows had no consistent shape that demanded judgment.

Three sources converged on a fix:

- **claude-code-system-prompts** verification-agent: "Your entire value is in finding the last 20%."
- **agent-dispatch** per-agent task doc: explicit territory + verification command + escalation.
- **leaked Claude Code source** Tool schema: per-tool permission state.

## Decision

Every dispatched engineer agent — both analysis pool (architect, security-analyst, requirements-engineer, idea-refiner, market-researcher, stack-selector, workplan-builder, performance-analyst, test-strategist, scanner, gap-analyst, doc-writer, agent-generator) and build pool (backend-developer, frontend-developer, devops-engineer, test-writer, code-reviewer, debugger) — carries the same prompt shape:

1. **Adversarial self-critique block** with five canonical traps tailored per role:
   - Verification avoidance.
   - Seduced by the first 80% (or symptom-vs-cause for debugging roles).
   - Confirmation bias / role-specific bias.
   - Three-reviewer test (or three-engineer / three-X equivalent).
   - Vague-language hunt or severity-discipline check.

2. **Read-only constraint block** that:
   - Names the engineer's owned output(s).
   - Lists upstream artifacts the engineer must NOT modify.
   - Documents the escalation pattern: surface findings via the engineer's own `## Open issues` section, never edit upstream files.
   - Constrains Bash to read-only inspection commands.

3. **Pre-output `approach.md`** discipline: every dispatched engineer writes `runs/<ts>/<engineer>/approach.md` *before* producing its declared output. The conductor reads it during integration to compare planned vs delivered.

## Consequences

**Easier:**
- Engineer prompts read consistently — operators learn the shape once.
- Drift between upstream artifacts is caught at gate boundaries (Open issues sections feed Alignment Guard).
- The Conductor can integrate cross-cuts because every engineer has the same artifact-ownership semantics.

**Harder:**
- Each agent prompt grew ~50 lines. Mitigation: the new sections are at the bottom; the engineer's role-specific instructions stay at the top where they're easiest to scan.
- Self-critique adds latency to every engineer run. Mitigation: the cost is small relative to the cost of integrating misaligned outputs.

**Accepted:**
- Some traps don't quite fit some roles. Per-role tailoring (e.g. debugger uses "symptom-vs-cause" instead of "first 80%") is allowed and tested.

## Alternatives considered

- **One generic shape applied verbatim to every agent.** Rejected: traps that are sharp for an architect ("Year-1 vs Year-3 differences") are noise for a doc-writer.
- **Self-critique as a separate post-hoc agent.** Rejected: doubles agent count; operators have to remember to run it; integration cost outweighs the simplicity gain.
- **Trust the model to self-critique without explicit prompting.** Rejected: tested empirically — without the explicit checklist, models routinely skip the verification step. The checklist works.

## Sources

- claude-code-system-prompts: adversarial self-critique paragraph; "your entire value is in finding the last 20%".
- agent-dispatch: per-agent task doc with territory + verification + escalation.
- leaked Claude Code source: Tool schema with per-tool permission state — informed our SpawnPayload shape.
