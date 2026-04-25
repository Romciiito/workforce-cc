# ADR 005 — Hooks are profile-gated and unconditionally callable

**Status**: Accepted (Chunks 9, 10, 16)

## Context

Three hooks ship today: `governance.sh` (audit decisions), `config-protection.sh` (block lint-config edits), `observe.sh` (post-tool-use observation). Without a gating mechanism, every spawned agent would have to know whether each hook is installed in the user's environment, gate its calls accordingly, and handle missing-hook errors gracefully. That's prompt-engineering noise that scales with hook count.

## Decision

Hooks are **profile-gated** + **unconditionally callable** by agents.

- **Profile-gated**: `profiles/<name>.json` lists which hooks the profile enables. The hook dispatcher (`hooks/dispatcher.sh`) reads this and skips disabled hooks silently.
- **Unconditionally callable**: agents fire `hooks/dispatcher.sh fire <name> <args>` without checking whether the hook is enabled. If it's disabled, the dispatcher silently returns 0. If it's missing entirely, same.

Agents see the dispatcher as a single entry point: `fire <name> <args>` always works. The runtime decides whether the hook actually runs.

Runtime overrides (no install change required):
- `WORKFORCE_HOOK_PROFILE=minimal` — switch to a different profile's hook list.
- `WORKFORCE_DISABLED_HOOKS=observe,config-protection` — disable per-hook.
- `WORKFORCE_TELEMETRY=off` — global hard opt-out (overrides everything).

## Consequences

**Easier:**
- Agent prompts call hooks unconditionally — no gating logic in prompts.
- Operators control the hook set without reinstalling.
- Adding a new hook is one .sh file + one entry in a profile.

**Harder:**
- A bug in a hook can silently fail. Mitigation: hook scripts use `set -euo pipefail` and tests assert dispatcher behavior end-to-end.
- The dispatcher introduces one bash subprocess per hook call. Negligible at human time scales; might matter if we ever wanted ultra-low-latency hooks.

**Accepted:**
- The "silent no-op" semantics could surprise an operator wondering why a hook didn't fire. Mitigation: `dispatcher.sh list` shows enabled hooks per profile; operators can verify expectation before debugging.

## Alternatives considered

- **Each agent checks `which hook-name` before firing.** Rejected: multiplies prompt complexity by hook count.
- **Hook auto-discovery from `hooks/` directory.** Rejected: removes the operator's ability to disable hooks installed for other profiles.
- **Plugin-style hooks (each hook is a binary).** Rejected: bash scripts are sufficient and zero-dependency for our use cases.

## Sources

- everything-claude-code's hook dispatcher with `ECC_HOOK_PROFILE=` runtime control. Same pattern, different env var prefix (`WORKFORCE_*` not `ECC_*`).
- The unconditional-call discipline is original — keeps agent prompts free of environment checks.
