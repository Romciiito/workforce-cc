#!/usr/bin/env python3
"""
Install a Claude Code skill by name using the npx skills CLI.
"""

import argparse
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Install a Claude Code skill")
    parser.add_argument("--skill", required=True, help="Skill name to install")
    args = parser.parse_args()

    skill = args.skill.strip()
    if not skill:
        print("ERROR: --skill must be a non-empty skill name", file=sys.stderr)
        sys.exit(1)

    print(f"Installing skill: {skill}")
    result = subprocess.run(
        ["npx", "skills", "add", skill],
        capture_output=False,
    )

    if result.returncode != 0:
        print(f"ERROR: npx skills add {skill} failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)

    print(f"Skill '{skill}' installed successfully.")


if __name__ == "__main__":
    main()
