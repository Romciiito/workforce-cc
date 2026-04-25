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
#   --only foundation   install only the Foundation skill + shared agents
#   --only workforce    install only the Workforce skill + shared agents
#   --force             overwrite existing agent files (defaults to skip-if-exists)
#   --uninstall         remove skills + agents installed by this repo

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"
SKILLS_DIR="${CLAUDE_DIR}/skills"
AGENTS_DIR="${CLAUDE_DIR}/agents"

MODE="both"
FORCE=0
UNINSTALL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --only) MODE="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help)
      grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

echo ""
echo "Foundation + Workforce — install"
echo "────────────────────────────────"
echo "  Repo root:   $ROOT_DIR"
echo "  Mode:        $MODE"
[[ $FORCE -eq 1 ]] && echo "  Force:       yes (agent files will be overwritten)"
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

mkdir -p "$SKILLS_DIR" "$AGENTS_DIR"

# ── Skill linker ────────────────────────────────────────────────────────────────
link_skill() {
  local name="$1"
  local src="${ROOT_DIR}/skills/${name}"
  local dst="${SKILLS_DIR}/${name}"

  if [[ $UNINSTALL -eq 1 ]]; then
    if [[ -L "$dst" ]]; then
      rm "$dst"; echo "  - removed skill link: $dst"
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
    [[ -f "$target" ]] && { rm "$target"; echo "  - removed agent: ${prefix}${base}"; }
    return
  fi

  if [[ -f "$target" && $FORCE -eq 0 ]]; then
    echo "  = agent ${prefix}${base} (exists, pass --force to overwrite)"
  else
    cp "$src" "$target"; echo "  + agent ${prefix}${base}"
  fi
}

# ── Install skills ──────────────────────────────────────────────────────────────
echo "Skills:"
case "$MODE" in
  foundation) link_skill foundation; link_skill sync ;;
  workforce)  link_skill workforce; link_skill sync ;;
  both)       link_skill foundation; link_skill workforce; link_skill sync ;;
  *) echo "Unknown --only value: $MODE"; exit 1 ;;
esac
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

# shared agents — always installed (usable by both skills), no prefix
for f in "${ROOT_DIR}/agents/_shared/"*.md; do
  [[ -e "$f" ]] || continue
  copy_agent "$f" ""
done

# orchestrators — the new three-role spine (intent-validator, conductor,
# alignment-guard). Always installed regardless of --only mode; both skills
# delegate to them. Policy-relevant: agents/deprecated/README.md is *not*
# walked here — it's documentation, not an agent.
for f in "${ROOT_DIR}/agents/orchestrators/"*.md; do
  [[ -e "$f" ]] || continue
  copy_agent "$f" ""
done

if [[ "$MODE" == "foundation" || "$MODE" == "both" ]]; then
  for f in "${ROOT_DIR}/agents/foundation/"*.md; do
    [[ -e "$f" ]] || continue
    copy_agent "$f" ""
  done
fi

if [[ "$MODE" == "workforce" || "$MODE" == "both" ]]; then
  for f in "${ROOT_DIR}/agents/workforce/"*.md; do
    [[ -e "$f" ]] || continue
    copy_agent "$f" ""
  done
fi
echo ""

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
  echo ""
  echo "  Beacon:  ~/.foundation-path → $ROOT_DIR"
fi
