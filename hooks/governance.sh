#!/usr/bin/env bash
# hooks/governance.sh — record orchestration decisions to a JSONL audit trail.
#
# Called by alignment-guard, conductor, and intent-validator after each
# major decision (PASS/BLOCK, dispatch wave, intent revision). Writes a
# single JSON line per call into <project>/.foundation-memory/governance.jsonl
# if telemetry is enabled.
#
# Usage:
#   governance.sh <agent> <event> [reason...]
#
# Examples:
#   governance.sh alignment-guard pass "no findings"
#   governance.sh alignment-guard block "HIGH: scope creep in architecture"
#   governance.sh conductor dispatch "wave 1: 4 engineers"
#   governance.sh intent-validator revision "user added 'Out of scope'"
#
# Respects the same env-var contract as scripts/telemetry.py:
#   WORKFORCE_TELEMETRY=off → silent no-op
#   WORKFORCE_MULTI_TERMINAL=1 → auto-create .foundation-memory/

set -euo pipefail

agent="${1:-unknown}"
event="${2:-unknown}"
shift 2 || true
reason="${*:-}"

# Hard opt-out always wins.
if [[ "${WORKFORCE_TELEMETRY:-}" == "off" ]]; then
  exit 0
fi

project_dir="${WORKFORCE_PROJECT_DIR:-$(pwd)}"
mem_dir="${project_dir}/.foundation-memory"

if [[ ! -d "$mem_dir" ]]; then
  if [[ "${WORKFORCE_MULTI_TERMINAL:-}" != "1" ]]; then
    # Telemetry is opt-in; don't auto-create unless we're in multi-terminal mode.
    exit 0
  fi
  mkdir -p "$mem_dir"
fi

ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
log="${mem_dir}/governance.jsonl"

# Pass values via env vars rather than bash heredoc interpolation so the
# script stays bash-3.2 compatible (macOS default) and JSON-escapes any
# special characters in reason safely.
export GH_TS="$ts" GH_AGENT="$agent" GH_EVENT="$event" GH_REASON="$reason"
python3 -c "
import json, os
print(json.dumps({
    'ts': os.environ['GH_TS'],
    'agent': os.environ['GH_AGENT'],
    'event': os.environ['GH_EVENT'],
    'reason': os.environ['GH_REASON'],
}, ensure_ascii=False))
" >> "$log"
