#!/usr/bin/env bash
# hooks/config-protection.sh — block edits to lint/format/type-check config
# files that engineers might be tempted to edit instead of fixing the code.
#
# Pattern borrowed from everything-claude-code's config-protection hook.
# Concrete idea: when an engineer hits a lint error, the lazy fix is to
# weaken the lint config; the right fix is to update the code. This hook
# is meant to be called from a PreToolUse hook in a Claude Code project's
# .claude/hooks.json, looking at the file path being written and exiting
# non-zero if it's a known config file.
#
# Usage:
#   config-protection.sh <file-path>
# Exit codes:
#   0 — write is allowed (file is not a protected config)
#   1 — write is blocked (file is a protected config; print reason to stderr)
#
# Override: WORKFORCE_ALLOW_CONFIG_EDIT=1 lets the write through.

set -euo pipefail

target="${1:-}"
if [[ -z "$target" ]]; then
  echo "usage: config-protection.sh <file-path>" >&2
  exit 1
fi

if [[ "${WORKFORCE_ALLOW_CONFIG_EDIT:-}" == "1" ]]; then
  exit 0
fi

# Protected configs — the kind of files an engineer might edit to make a
# lint/typecheck/security error "go away" rather than fixing the underlying code.
protected_patterns=(
  ".eslintrc*"
  "eslint.config.*"
  ".prettierrc*"
  "prettier.config.*"
  ".rubocop.yml"
  "ruff.toml"
  ".ruff.toml"
  "pyproject.toml"          # Python tool configuration; partial — see note below.
  ".pylintrc"
  "mypy.ini"
  ".mypy.ini"
  "tsconfig.json"
  "tsconfig.*.json"
  ".flake8"
  ".bandit"
  "pytest.ini"
  ".github/workflows/*.yml" # CI gates the engineer might be tempted to weaken
)

# Note: pyproject.toml is dual-purpose (build config AND tool config). The
# protection here is loose; in practice the hook should differentiate. For
# now, a clear opt-out (WORKFORCE_ALLOW_CONFIG_EDIT=1) keeps it usable
# without false-positive friction.

for pattern in "${protected_patterns[@]}"; do
  # shellcheck disable=SC2053
  if [[ "$target" == $pattern || "$(basename "$target")" == $pattern ]]; then
    cat <<EOF >&2
config-protection: blocking write to $target

This is a lint/format/type-check/CI configuration file. If you're tempted
to edit it because a check is failing, consider whether the right fix is
in the code rather than in the config.

Override: set WORKFORCE_ALLOW_CONFIG_EDIT=1 to allow this write. Recorded
in governance.jsonl if telemetry is enabled.
EOF
    exit 1
  fi
done

exit 0
