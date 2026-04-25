# ADR 012 — Permission modes per dispatched engineer

**Status**: Accepted (Chunk 27)

## Context

Once we had multi-terminal dispatch (ADR 008), operators wanted finer control over how aggressively each spawned engineer could act:

- For **planning runs**: produce plan-level artifacts only; do not execute. Useful when the operator wants to see what an architect *would* do before committing to the work.
- For **trusted runs**: skip "are you sure?" confirmations. The operator has reviewed dispatch.md and trusts the engineer's stated approach.
- For **exploratory runs**: allow the engineer to act outside its declared territory if necessary. Highest trust; reserved for senior debugging or experimental work where the operator is reviewing every diff.
- For **default runs**: stay inside declared territory; ask before any tool call with side effects beyond declared outputs.

A single uniform "execute the task" mode forces the operator to either over-trust (everything is auto) or under-trust (every tool call asks).

## Decision

SpawnPayload gains a `permission_mode` field with four values. Pattern from leaked Claude Code source's multi-mode permission resolution; semantics defined fresh.

```python
class PermissionMode(enum.Enum):
    DEFAULT = "default"  # ask before tool calls outside declared territory
    PLAN    = "plan"     # plan-level artifacts only; no execution
    AUTO    = "auto"     # execute within envelope without asking
    BYPASS  = "bypass"   # may act outside territory; document each excursion
```

The envelope template renders mode-specific instruction language:

- **default**: "Follow the envelope's territory + read-only constraints exactly. Ask before any tool call outside declared territory."
- **plan**: "You **must not execute** any change. Produce plan-level artifacts only."
- **auto**: "You're empowered to execute within the envelope without asking. Skip 'are you sure' confirmations."
- **bypass**: "You may act outside the envelope's territory if the task genuinely requires it. Document each excursion in approach.md and BLOCKED.md if applicable."

The `dispatch.md` task block can declare a permission_mode bullet per task; the conductor sets it based on the wave's purpose.

Backward compatibility: legacy SpawnPayload JSON without `permission_mode` loads with `DEFAULT`. Tests pin both new and legacy paths.

## Consequences

**Easier:**
- Operators can launch a "what would this look like?" wave with `permission_mode=plan` without engineers actually scaffolding anything.
- High-trust runs (a sprint of well-scoped fixes) skip the friction of every tool call asking.
- Senior debugging runs can use `bypass` without the conductor having to explicitly widen each territory declaration.

**Harder:**
- Four modes is more than the operator can hold in mind. Mitigation: default is "the safe one"; the docs explain each mode at the point where it's set (envelope renders mode-specific paragraphs).
- The semantics are advisory — the engineer-agent reads the mode from the envelope and is *trusted* to honour it. There's no enforcement layer that prevents an `auto`-mode engineer from acting outside its territory. Mitigation: the alignment-guard catches drift; the audit trail (hooks/governance.sh + observe.sh) records every tool call.

**Accepted:**
- Some workflows want a fifth mode (e.g. "ask before every tool call regardless of territory" — paranoid). We can add it later if a real need surfaces; YAGNI for now.
- The advisory semantics depend on Claude's instruction-following. Empirically this works; if it stops working, we'd need to wire the modes into a permission middleware (e.g. tool-permission Claude Code hook).

## Alternatives considered

- **Single `auto: true|false` boolean.** Rejected: collapses the planning, default, and bypass cases into one bit. The four-mode design captures the actual operator intents.
- **Per-tool permission map** (`{Bash: ask, Edit: auto, ...}`). Rejected: too fine-grained for the operator to set per-task. The four-mode design picks the right defaults across tool classes.
- **Enforce the modes via Claude Code's permission system.** Deferred: would require a hook integration and is a larger change. The current advisory semantics are the smallest-useful-thing.

## Sources

- Leaked Claude Code source's multi-mode permission resolution (default / plan / auto / bypass). Pattern only; semantics defined fresh in the SpawnPayload docstring.
- The four-mode framing of CI tools like `terraform plan` vs `terraform apply` — the operator chooses the trust level appropriate to the run.
