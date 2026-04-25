#!/usr/bin/env bash
# Unified installer for Foundation + Workforce.
#
# Installs:
#   1. ~/.claude/skills/foundation         → skills/foundation   (symlink)
#   2. ~/.claude/skills/workforce          → skills/workforce    (symlink)
#   3. ~/.claude/agents/<name>.md          copies of agents/_shared/*, agents/foundation/*,
#                                          and agents/workforce/*. Filenames are kept as-is —
#                                          the per-pack agents are already uniquely named
#                                          (foundation-orchestrator.md, workforce-orchestrator.md, etc.),
#                                          so no extra prefixing is applied. The installer aborts
#                                          if it ever detects a same-name collision across packs.
#   4. ~/.foundation-path                  absolute path to this repo (consumed by SKILL.md)
#
# Flags:
#   --profile <name>      install per profiles/<name>.json (full | foundation |
#                         workforce | minimal). Reads skills + agent_packs +
#                         hooks + harnesses from the JSON.
#   --harnesses <list>    comma-separated harness selection, overrides the
#                         profile's harnesses list. Available: claude, cursor,
#                         codex, opencode, gemini. Default: claude.
#   --only foundation     install only the Foundation skill + shared agents (legacy)
#   --only workforce      install only the Workforce skill + shared agents (legacy)
#   --dry-run             print planned actions without writing
#   --force               overwrite existing agent files (defaults to skip-if-exists)
#   --uninstall           remove skills + agents installed by this repo

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"
SKILLS_DIR="${CLAUDE_DIR}/skills"
AGENTS_DIR="${CLAUDE_DIR}/agents"

MODE="both"
FORCE=0
UNINSTALL=0
PROFILE=""
DRY_RUN=0
HARNESSES_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --only) MODE="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --harnesses) HARNESSES_OVERRIDE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help)
      grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

# ── Profile resolution ──────────────────────────────────────────────────────
# When --profile is set, it overrides --only with the profile's skills + agent
# packs + hooks. Profile JSON is read by python3 (already a hard dep, no jq
# required). The legacy --only flag continues to work unchanged when --profile
# is not passed; default behavior preserved.
PROFILE_SKILLS=""
PROFILE_PACKS=""
PROFILE_HOOKS=""
PROFILE_HARNESSES=""
if [[ -n "$PROFILE" ]]; then
  PROFILE_FILE="${ROOT_DIR}/profiles/${PROFILE}.json"
  if [[ ! -f "$PROFILE_FILE" ]]; then
    echo "ERROR: profile not found: ${PROFILE}. Files in profiles/ — $(ls "${ROOT_DIR}/profiles/" 2>/dev/null | grep '\.json$' | tr '\n' ' ')"
    exit 1
  fi
  if ! command -v python3 &>/dev/null; then
    echo "ERROR: --profile requires python3"; exit 1
  fi
  PROFILE_SKILLS="$(python3 -c "
import json
d = json.load(open('${PROFILE_FILE}'))
print(' '.join(d.get('skills', [])))
")"
  PROFILE_PACKS="$(python3 -c "
import json
d = json.load(open('${PROFILE_FILE}'))
print(' '.join(d.get('agent_packs', [])))
")"
  PROFILE_HOOKS="$(python3 -c "
import json
d = json.load(open('${PROFILE_FILE}'))
print(' '.join(d.get('hooks', []) or []))
")"
  PROFILE_HARNESSES="$(python3 -c "
import json
d = json.load(open('${PROFILE_FILE}'))
# Default to ['claude'] when missing — preserves legacy behavior.
print(' '.join(d.get('harnesses') or ['claude']))
")"
fi

# --harnesses overrides the profile's harnesses list. Comma-separated.
# Validates against the manifest-schema enum: claude / cursor / codex / opencode / gemini.
EFFECTIVE_HARNESSES_STR=""
if [[ -n "$HARNESSES_OVERRIDE" ]]; then
  EFFECTIVE_HARNESSES_STR="$(echo "$HARNESSES_OVERRIDE" | tr ',' ' ')"
elif [[ -n "$PROFILE_HARNESSES" ]]; then
  EFFECTIVE_HARNESSES_STR="$PROFILE_HARNESSES"
else
  # Legacy mode (no --profile, no --harnesses): default to claude.
  EFFECTIVE_HARNESSES_STR="claude"
fi

# Validate every requested harness exists.
if [[ $UNINSTALL -eq 0 ]]; then
  for h in $EFFECTIVE_HARNESSES_STR; do
    if [[ ! -d "${ROOT_DIR}/harnesses/${h}" ]]; then
      echo "ERROR: unknown harness: ${h}. Available: $(ls "${ROOT_DIR}/harnesses/" 2>/dev/null | grep -v '^README' | grep -v '\.json$' | tr '\n' ' ')"
      exit 1
    fi
  done
fi

echo ""
echo "Foundation + Workforce — install"
echo "────────────────────────────────"
echo "  Repo root:   $ROOT_DIR"
if [[ -n "$PROFILE" ]]; then
  echo "  Profile:     ${PROFILE}"
  echo "  Skills:      ${PROFILE_SKILLS}"
  echo "  Packs:       ${PROFILE_PACKS}"
  echo "  Hooks:       ${PROFILE_HOOKS:-(none)}"
else
  echo "  Mode:        $MODE  (legacy; pass --profile <name> for profiled installs)"
fi
echo "  Harnesses:   ${EFFECTIVE_HARNESSES_STR}${HARNESSES_OVERRIDE:+ (--harnesses override)}"
[[ $FORCE -eq 1 ]] && echo "  Force:       yes (agent files will be overwritten)"
[[ $DRY_RUN -eq 1 ]] && echo "  Dry-run:     yes (no files will be written)"
[[ $UNINSTALL -eq 1 ]] && echo "  Action:      UNINSTALL"
echo ""

# ── Dependency checks ──────────────────────────────────────────────────────────
check_dep() {
  local cmd="$1" hint="$2"
  if ! command -v "$cmd" &>/dev/null; then
    echo "  MISSING  $cmd  →  $hint"; MISSING_DEPS=1
  else
    echo "  OK       $cmd"
  fi
}

if [[ $UNINSTALL -eq 0 ]]; then
  MISSING_DEPS=0
  echo "Dependencies:"
  check_dep python3 "install Python 3.9+"
  check_dep git "install git from https://git-scm.com"

  if [[ "$MODE" != "workforce" ]]; then
    check_dep npx "install Node.js from https://nodejs.org (needed for skill install)"
    if python3 -c "import jinja2" 2>/dev/null; then
      echo "  OK       python3 jinja2"
    else
      echo "  MISSING  python3 jinja2  →  pip install jinja2"; MISSING_DEPS=1
    fi
  fi

  [[ $MISSING_DEPS -eq 1 ]] && { echo "Install deps above, re-run."; exit 1; }
  echo ""
fi

if [[ $DRY_RUN -eq 0 ]]; then
  mkdir -p "$SKILLS_DIR" "$AGENTS_DIR"
fi

# ── Skill linker ────────────────────────────────────────────────────────────────
link_skill() {
  local name="$1"
  local src="${ROOT_DIR}/skills/${name}"
  local dst="${SKILLS_DIR}/${name}"

  if [[ $UNINSTALL -eq 1 ]]; then
    if [[ -L "$dst" ]]; then
      [[ $DRY_RUN -eq 1 ]] && { echo "  - would remove skill link: $dst"; return; }
      rm "$dst"; echo "  - removed skill link: $dst"
    fi
    return
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    if [[ -L "$dst" ]]; then
      local cur; cur=$(readlink "$dst")
      if [[ "$cur" == "$src" ]]; then
        echo "  = skill $name (already linked)"
      else
        echo "  ↺ would update skill link: $name"
      fi
    elif [[ -e "$dst" ]]; then
      echo "  ! skill $name (exists but not a symlink — would error on real run)"
    else
      echo "  + would link skill: $name"
    fi
    return
  fi

  if [[ -L "$dst" ]]; then
    local cur; cur=$(readlink "$dst")
    if [[ "$cur" == "$src" ]]; then
      echo "  = skill $name (already linked)"
    else
      ln -sf "$src" "$dst"; echo "  ↺ skill $name (updated link)"
    fi
  elif [[ -e "$dst" ]]; then
    echo "  ERROR: $dst exists and is not a symlink — remove it manually"; exit 1
  else
    ln -s "$src" "$dst"; echo "  + skill $name"
  fi
}

# ── Agent copier ────────────────────────────────────────────────────────────────
copy_agent() {
  local src="$1" prefix="$2"
  local base; base=$(basename "$src")
  local target="${AGENTS_DIR}/${prefix}${base}"

  if [[ $UNINSTALL -eq 1 ]]; then
    if [[ -f "$target" ]]; then
      [[ $DRY_RUN -eq 1 ]] && { echo "  - would remove agent: ${prefix}${base}"; return; }
      rm "$target"; echo "  - removed agent: ${prefix}${base}"
    fi
    return
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    if [[ -f "$target" && $FORCE -eq 0 ]]; then
      echo "  = agent ${prefix}${base} (exists, would skip without --force)"
    else
      echo "  + would copy agent ${prefix}${base}"
    fi
    return
  fi

  if [[ -f "$target" && $FORCE -eq 0 ]]; then
    echo "  = agent ${prefix}${base} (exists, pass --force to overwrite)"
  else
    cp "$src" "$target"; echo "  + agent ${prefix}${base}"
  fi
}

# ── Resolve the effective skills + agent packs ──────────────────────────────
# When --profile is set, the profile dictates everything. Otherwise, fall
# back to the legacy --only mode. The two are mutually exclusive at runtime
# but both are kept supported for back-compat.
declare -a EFFECTIVE_SKILLS EFFECTIVE_PACKS

if [[ -n "$PROFILE" ]]; then
  read -r -a EFFECTIVE_SKILLS <<< "$PROFILE_SKILLS"
  read -r -a EFFECTIVE_PACKS <<< "$PROFILE_PACKS"
else
  case "$MODE" in
    foundation) EFFECTIVE_SKILLS=(foundation sync perf harness security) ;;
    workforce)  EFFECTIVE_SKILLS=(workforce sync perf harness security) ;;
    both)       EFFECTIVE_SKILLS=(foundation workforce sync perf harness security) ;;
    *) echo "Unknown --only value: $MODE"; exit 1 ;;
  esac
  # Legacy mode behavior (pre-profile): always install _shared + orchestrators,
  # plus the requested pack(s).
  EFFECTIVE_PACKS=(_shared orchestrators)
  case "$MODE" in
    foundation|both) EFFECTIVE_PACKS+=(foundation) ;;
  esac
  case "$MODE" in
    workforce|both)  EFFECTIVE_PACKS+=(workforce) ;;
  esac
fi

# ── Install skills ──────────────────────────────────────────────────────────────
echo "Skills:"
for skill in "${EFFECTIVE_SKILLS[@]}"; do
  [[ -z "$skill" ]] && continue
  link_skill "$skill"
done
echo ""

# ── Install agents ──────────────────────────────────────────────────────────────
# Sanity check: ensure no two packs ship an agent with the same filename.
# Since copy_agent uses an empty prefix, a duplicate would silently overwrite
# the first copy and leave a confusing partial install. The orchestrators/
# directory is checked alongside the three legacy packs.
if [[ $UNINSTALL -eq 0 ]]; then
  collision_check="$(
    {
      ls -1 "${ROOT_DIR}/agents/_shared/" 2>/dev/null
      ls -1 "${ROOT_DIR}/agents/foundation/" 2>/dev/null
      ls -1 "${ROOT_DIR}/agents/workforce/" 2>/dev/null
      ls -1 "${ROOT_DIR}/agents/orchestrators/" 2>/dev/null
    } | grep -v '^README\.md$' | sort | uniq -d
  )"
  if [[ -n "$collision_check" ]]; then
    echo "ERROR: agent filename collision across packs:"
    echo "$collision_check" | sed 's/^/  /'
    echo "Resolve by renaming the duplicates, then re-run install.sh."
    exit 1
  fi
fi

echo "Agents:"
# Honor the effective pack list (built above from --profile or --only).
# Order matters: _shared and orchestrators install first so that pack-
# specific agents see them already in place. Use ${[@]+...} to play nice
# with `set -u` when EFFECTIVE_PACKS is empty (e.g. minimal profile).
if [[ ${#EFFECTIVE_PACKS[@]} -eq 0 ]]; then
  echo "  (no agent packs in this profile — skipping agent install)"
else
  for pack in "${EFFECTIVE_PACKS[@]}"; do
    [[ -z "$pack" ]] && continue
    pack_dir="${ROOT_DIR}/agents/${pack}"
    if [[ ! -d "$pack_dir" ]]; then
      echo "  ! pack $pack — directory missing at $pack_dir; skipping"
      continue
    fi
    for f in "${pack_dir}/"*.md; do
      [[ -e "$f" ]] || continue
      # Skip README.md files in pack dirs — they're documentation, not agents.
      [[ "$(basename "$f")" == "README.md" ]] && continue
      copy_agent "$f" ""
    done
  done
fi
echo ""

# ── Install hook beacon ─────────────────────────────────────────────────────
# When a profile declares hooks, write the profile name to ~/.workforce-profile
# so hooks/dispatcher.sh can resolve which hooks to fire at runtime. Legacy
# (--only) installs do not write this file; dispatcher falls back to "full".
if [[ -n "$PROFILE" && $UNINSTALL -eq 0 && $DRY_RUN -eq 0 ]]; then
  echo "$PROFILE" > "${HOME}/.workforce-profile"
elif [[ $UNINSTALL -eq 1 ]]; then
  rm -f "${HOME}/.workforce-profile" 2>/dev/null
fi

# ── Install harness beacon ──────────────────────────────────────────────────
# Comma-separated list of harnesses written to ~/.workforce-harnesses so
# scripts/harness_install.py (invoked at scaffold time) knows which harnesses
# to render adapters for. Always written when not uninstalling — even legacy
# installs default to "claude" so this file's presence indicates "the user
# ran install.sh at least once".
if [[ $UNINSTALL -eq 0 && $DRY_RUN -eq 0 ]]; then
  echo "$EFFECTIVE_HARNESSES_STR" | tr ' ' ',' > "${HOME}/.workforce-harnesses"
elif [[ $UNINSTALL -eq 1 ]]; then
  rm -f "${HOME}/.workforce-harnesses" 2>/dev/null
fi

# ── Write path beacon ──────────────────────────────────────────────────────────
if [[ $UNINSTALL -eq 1 ]]; then
  rm -f "${HOME}/.foundation-path"
  echo "Done — Foundation/Workforce uninstalled."
else
  echo "$ROOT_DIR" > "${HOME}/.foundation-path"
  echo "Done."
  echo ""
  echo "  /foundation   — bootstrap a new project"
  echo "  /workforce    — audit an existing project"
  echo "  /sync         — (if available) quick health check"
  echo "  /perf         — (if available) performance diagnosis"
  echo "  /security     — (if available) threat model + Phase 0 checklist"
  echo "  /harness      — (if available) re-apply harness adapters"
  echo ""
  echo "  Beacon:  ~/.foundation-path     → $ROOT_DIR"
  echo "  Beacon:  ~/.workforce-harnesses → $(echo "$EFFECTIVE_HARNESSES_STR" | tr ' ' ',')"
fi
