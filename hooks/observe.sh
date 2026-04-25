#!/usr/bin/env bash
# hooks/observe.sh — post-tool-use observation hook.
#
# Pattern from everything-claude-code's continuous-learning skill: every
# tool invocation produces a tiny structured observation, written to a
# project-scoped JSONL log. Over time the log becomes a record of *what
# Claude actually did* on this project — useful for debugging stuck
# sessions, auditing security-relevant tool calls, and feeding future
# self-evals.
#
# Usage (from a Claude Code PostToolUse hook):
#   observe.sh <tool-name> <success|failed> [details...]
#
# Examples:
#   observe.sh Bash success "git status"
#   observe.sh Bash failed "git push to archived repo"
#   observe.sh Edit success "scripts/scaffold.py:23"
#   observe.sh Read success "agents/architect.md (2400 lines)"
#
# Where the log lives:
#   <project>/.foundation-memory/observations.jsonl
#
# Shared env-var contract with telemetry.py and governance.sh:
#   WORKFORCE_TELEMETRY=off       → silent no-op (overrides everything)
#   WORKFORCE_MULTI_TERMINAL=1    → auto-create .foundation-memory/
#
# This hook is profile-gated via hooks/dispatcher.sh — listed in the
# 'hooks' array of profiles/full.json (and any other profile that
# enables it).

set -euo pipefail

tool="${1:-unknown}"
result="${2:-unknown}"
shift 2 || true
details="${*:-}"

# Hard opt-out always wins.
if [[ "${WORKFORCE_TELEMETRY:-}" == "off" ]]; then
  exit 0
fi

project_dir="${WORKFORCE_PROJECT_DIR:-$(pwd)}"
mem_dir="${project_dir}/.foundation-memory"

if [[ ! -d "$mem_dir" ]]; then
  if [[ "${WORKFORCE_MULTI_TERMINAL:-}" != "1" ]]; then
    # Opt-in only; don't auto-create unless multi-terminal is active.
    exit 0
  fi
  mkdir -p "$mem_dir"
fi

ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
log="${mem_dir}/observations.jsonl"

# Detect the engineer that ran this tool. The conductor exports
# WORKFORCE_ENGINEER when spawning each terminal; unset elsewhere.
engineer="${WORKFORCE_ENGINEER:-unknown}"
run_id="${WORKFORCE_RUN_ID:-}"

# Write JSONL line via python3 (already a hard dep) for safe escaping —
# stays bash-3.2 compatible (macOS default).
export OB_TS="$ts" OB_TOOL="$tool" OB_RESULT="$result" OB_DETAILS="$details" \
       OB_ENGINEER="$engineer" OB_RUN_ID="$run_id"
python3 -c "
import json, os
record = {
    'ts': os.environ['OB_TS'],
    'tool': os.environ['OB_TOOL'],
    'result': os.environ['OB_RESULT'],
    'engineer': os.environ['OB_ENGINEER'],
}
if os.environ['OB_RUN_ID']:
    record['run_id'] = os.environ['OB_RUN_ID']
if os.environ['OB_DETAILS']:
    record['details'] = os.environ['OB_DETAILS'][:280]  # cap at 280 chars
print(json.dumps(record, ensure_ascii=False))
" >> "$log"
