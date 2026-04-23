#!/usr/bin/env python3
"""
Suggest skills from the catalog that are not yet installed.
Reads ~/.claude/skills/ and compares against skill-catalog.json for the chosen stack.
"""

import argparse
import json
import sys
from pathlib import Path


def load_catalog(foundation_root: Path) -> dict:
    catalog_path = foundation_root / "skill-catalog.json"
    if not catalog_path.exists():
        print(f"ERROR: skill-catalog.json not found at {catalog_path}", file=sys.stderr)
        sys.exit(1)
    with open(catalog_path) as f:
        return json.load(f)


def get_installed_skills(skills_dir: Path) -> set[str]:
    if not skills_dir.exists():
        return set()
    return {
        p.name
        for p in skills_dir.iterdir()
        if p.is_dir() and (p / "SKILL.md").exists()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Suggest skills for a stack")
    parser.add_argument("--stack", required=True, help="Stack name (e.g. python-fastapi)")
    parser.add_argument(
        "--skills-dir",
        default="~/.claude/skills",
        help="Path to installed skills directory",
    )
    args = parser.parse_args()

    skills_dir = Path(args.skills_dir).expanduser()
    # __file__ is <root>/scripts/suggest_skills.py → root is parent.parent
    foundation_root = Path(__file__).resolve().parent.parent

    catalog = load_catalog(foundation_root)
    recommended = catalog.get(args.stack, [])

    if not recommended:
        print(f"No skill recommendations for stack '{args.stack}'.")
        return

    installed = get_installed_skills(skills_dir)

    results = []
    for skill in recommended:
        status = "installed" if skill in installed else "missing"
        results.append({"name": skill, "status": status})

    # Output JSON for the caller (SKILL.md orchestrator) to parse
    print(json.dumps(results))


if __name__ == "__main__":
    main()
