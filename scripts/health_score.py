#!/usr/bin/env python3
"""
Quick health score calculator for a project directory.
Used by the orchestrator to get a fast numerical score before spawning agents.
Prints a JSON object with dimension scores.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone


EXPECTED_DOCS = [
    "CLAUDE.md",
    "vision.md",
    "docs/claude/architecture.md",
    "docs/claude/development.md",
    "docs/claude/design-decisions.md",
    "docs/claude/env-vars.md",
    "security-model.md",
]

EXPECTED_AGENTS = [
    "backend-developer.md",
    "frontend-developer.md",
    "devops-engineer.md",
    "test-writer.md",
    "code-reviewer.md",
    "debugger.md",
]


FEATURE_PATTERN = re.compile(r"feat|add |implement|build|create", re.IGNORECASE)
GIT_HASH_RE = re.compile(r"^[0-9a-f]{4,40}$")


def run_git(args: list[str], cwd: Path) -> str:
    """Run a git command without invoking a shell. Returns stdout (stripped) or ''."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
        return result.stdout.strip()
    except (FileNotFoundError, OSError):
        return ""


def count_feature_commits_since(filepath: Path, project_dir: Path) -> int:
    """Count feature commits since a file was last modified."""
    last_hash = run_git(
        ["log", "-1", "--format=%H", "--", str(filepath)],
        project_dir,
    )
    # Defensive: only accept what looks like a real git hash before passing
    # it to another git invocation. Prevents flag injection if the file
    # path ever lets a hostile value bubble up through `git log`.
    if not last_hash or not GIT_HASH_RE.match(last_hash):
        return 0
    log_output = run_git(
        ["log", f"{last_hash}..HEAD", "--oneline"],
        project_dir,
    )
    if not log_output:
        return 0
    return sum(1 for line in log_output.splitlines() if FEATURE_PATTERN.search(line))


def score_vision(project_dir: Path) -> tuple[int, str]:
    vision = project_dir / "vision.md"
    if not vision.exists():
        return 2, "vision.md missing"
    content = vision.read_text()
    stale = count_feature_commits_since(vision, project_dir)
    if stale > 30:
        return 5, f"vision.md exists but {stale} feature commits since last update"
    if "non-negotiables" in content.lower() and "out of scope" in content.lower():
        return 9, "vision.md complete and current"
    return 7, "vision.md exists"


def score_docs(project_dir: Path) -> tuple[int, str]:
    present = sum(1 for d in EXPECTED_DOCS if (project_dir / d).exists())
    stale_count = 0
    for d in EXPECTED_DOCS:
        p = project_dir / d
        if p.exists() and count_feature_commits_since(p, project_dir) > 10:
            stale_count += 1
    score = max(1, round((present / len(EXPECTED_DOCS)) * 10) - stale_count)
    return score, f"{present}/{len(EXPECTED_DOCS)} docs present, {stale_count} stale"


def score_security(project_dir: Path) -> tuple[int, str]:
    sm = project_dir / "security-model.md"
    if not sm.exists():
        return 2, "security-model.md missing"
    content = sm.read_text()
    checked = content.count("- [x]")
    unchecked = content.count("- [ ]")
    total = checked + unchecked
    if total == 0:
        return 4, "security-model.md exists but no checklist items"
    score = max(3, round((checked / total) * 10))
    return score, f"{checked}/{total} Phase 0 items checked"


def score_agents(project_dir: Path) -> tuple[int, str]:
    agents_dir = project_dir / ".claude" / "agents"
    if not agents_dir.exists():
        return 1, ".claude/agents/ missing"
    present = [a for a in EXPECTED_AGENTS if (agents_dir / a).exists()]
    # Check for generic (unrendered) agents
    generic = []
    for a in present:
        content = (agents_dir / a).read_text()
        if "{{ project_name }}" in content or "[ placeholder" in content:
            generic.append(a)
    score = max(1, round((len(present) / len(EXPECTED_AGENTS)) * 10) - len(generic) * 2)
    return score, f"{len(present)}/{len(EXPECTED_AGENTS)} agents, {len(generic)} generic"


def score_workplan(project_dir: Path) -> tuple[int, str]:
    wp = project_dir / "workplan.md"
    if not wp.exists():
        return 1, "workplan.md missing"
    stale = count_feature_commits_since(wp, project_dir)
    content = wp.read_text()
    has_active = "- [ ]" in content
    if stale > 20:
        return 4, f"workplan.md exists but {stale} commits since last update"
    if has_active:
        return 8, "workplan.md active with incomplete tasks"
    return 6, "workplan.md exists"


def main() -> None:
    parser = argparse.ArgumentParser(description="Workforce health score calculator")
    parser.add_argument("--project-dir", default=".", help="Project root directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()

    vision_score, vision_status = score_vision(project_dir)
    docs_score, docs_status = score_docs(project_dir)
    security_score, security_status = score_security(project_dir)
    agents_score, agents_status = score_agents(project_dir)
    workplan_score, workplan_status = score_workplan(project_dir)

    total = vision_score + docs_score + security_score + agents_score + workplan_score

    result = {
        "vision": vision_score,
        "vision_status": vision_status,
        "docs": docs_score,
        "docs_status": docs_status,
        "security": security_score,
        "security_status": security_status,
        "agents": agents_score,
        "agents_status": agents_status,
        "workplan": workplan_score,
        "workplan_status": workplan_status,
        "total": total,
        "max": 50,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\nHealth Scores — {project_dir.name}")
        print("─" * 40)
        print(f"  Vision      {vision_score:2}/10  {vision_status}")
        print(f"  Docs        {docs_score:2}/10  {docs_status}")
        print(f"  Security    {security_score:2}/10  {security_status}")
        print(f"  Agents      {agents_score:2}/10  {agents_status}")
        print(f"  Workplan    {workplan_score:2}/10  {workplan_status}")
        print(f"  {'─'*36}")
        print(f"  Overall     {total:2}/50\n")


if __name__ == "__main__":
    main()
