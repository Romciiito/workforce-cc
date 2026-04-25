#!/usr/bin/env bash
# hooks/dispatcher.sh — profile-gated hook runner.
#
# Reads which hooks the active profile enables and runs only those. Other
# hooks under hooks/ are skipped without error. Used by install.sh and by
# any caller that wants to fire one of the enabled hooks.
#
# Usage:
#   hooks/dispatcher.sh list                       # print enabled hooks
#   hooks/dispatcher.sh fire <hook-name> [args...] # run one enabled hook
#   hooks/dispatcher.sh fire-all [args...]         # run every enabled hook in order
#
# Profile resolution:
#   1. $WORKFORCE_PROFILE if set                  (e.g. "foundation")
#   2. ~/.workforce-profile (file)                (written by install.sh)
#   3. profiles/full.json                         (default)
#
# Per-hook gating:
#   $WORKFORCE_DISABLED_HOOKS="governance,..."    # disable specific hooks
#   $WORKFORCE_HOOK_PROFILE="minimal"             # alias to a profile name (overrides resolution above)
#
# Hooks are bash scripts in hooks/<name>.sh. They receive the same args
# `dispatcher.sh fire` was called with.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_DIR="${ROOT_DIR}/hooks"
PROFILES_DIR="${ROOT_DIR}/profiles"

# ── Profile resolution ──────────────────────────────────────────────────────
resolve_profile() {
  if [[ -n "${WORKFORCE_HOOK_PROFILE:-}" ]]; then
    echo "$WORKFORCE_HOOK_PROFILE"
    return
  fi
  if [[ -n "${WORKFORCE_PROFILE:-}" ]]; then
    echo "$WORKFORCE_PROFILE"
    return
  fi
  local beacon="${HOME}/.workforce-profile"
  if [[ -f "$beacon" ]]; then
    cat "$beacon"
    return
  fi
  echo "full"
}

profile_file() {
  local name="$1"
  echo "${PROFILES_DIR}/${name}.json"
}

# Extract the hooks list from a profile JSON. Uses python3 because we already
# require it for the rest of the toolchain — no jq dependency.
read_enabled_hooks() {
  local profile="$1"
  local pf
  pf="$(profile_file "$profile")"
  if [[ ! -f "$pf" ]]; then
    echo "ERROR: unknown profile: $profile (no $pf)" >&2
    exit 1
  fi
  python3 -c "
import json, sys
data = json.load(open('$pf'))
for h in data.get('hooks', []) or []:
    print(h)
"
}

is_disabled() {
  local hook="$1"
  IFS=',' read -ra disabled <<< "${WORKFORCE_DISABLED_HOOKS:-}"
  for d in "${disabled[@]:-}"; do
    [[ "$(echo -n "$d" | xargs)" == "$hook" ]] && return 0
  done
  return 1
}

list_enabled_hooks() {
  local profile
  profile="$(resolve_profile)"
  while IFS= read -r hook; do
    [[ -z "$hook" ]] && continue
    if is_disabled "$hook"; then
      continue
    fi
    if [[ ! -f "${HOOKS_DIR}/${hook}.sh" ]]; then
      continue
    fi
    echo "$hook"
  done < <(read_enabled_hooks "$profile")
}

# ── Subcommands ──────────────────────────────────────────────────────────────
cmd="${1:-}"

case "$cmd" in
  list)
    list_enabled_hooks
    ;;
  fire)
    shift
    target="${1:-}"
    [[ -z "$target" ]] && { echo "usage: dispatcher.sh fire <hook-name> [args...]" >&2; exit 1; }
    shift
    enabled=$(list_enabled_hooks)
    if ! grep -qx "$target" <<< "$enabled"; then
      # Not enabled / not present — silent no-op, like a noop hook.
      exit 0
    fi
    exec bash "${HOOKS_DIR}/${target}.sh" "$@"
    ;;
  fire-all)
    shift
    while IFS= read -r hook; do
      [[ -z "$hook" ]] && continue
      bash "${HOOKS_DIR}/${hook}.sh" "$@" || {
        echo "WARNING: hook ${hook} returned $?" >&2
      }
    done < <(list_enabled_hooks)
    ;;
  *)
    echo "usage: $0 {list | fire <hook> [args...] | fire-all [args...]}" >&2
    exit 1
    ;;
esac
