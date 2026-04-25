#!/usr/bin/env python3
"""
migrate_legacy_orchestrators.py — rewrite installed legacy agent files
into thin redirect shims.

The four legacy orchestrators (foundation-orchestrator, workforce-orchestrator,
vision-keeper, output-validator) are being superseded by the three new
roles in agents/orchestrators/. While the source repo keeps the legacy
files in service for one release, individual user installs may want to
migrate now — for example, when a user has hardcoded one of the legacy
names in their own workflow and wants to be reminded to switch.

This script does NOT touch the source repo. It only rewrites the user's
installed copies under ``~/.claude/agents/`` (or ``--target-dir``).

Idempotent
----------

Running it twice is a no-op on the second run. The script detects already-
shimmed files by looking for the ``<!-- workforce-cc-shim:v1 -->`` marker.

Reversible
----------

The script writes a backup of every rewritten file to
``<target-dir>/.workforce-backup/<name>.md.bak`` before overwriting. Run
``--restore`` to swap them back.

Usage
-----

    migrate_legacy_orchestrators.py            # preview (dry-run by default)
    migrate_legacy_orchestrators.py --apply
    migrate_legacy_orchestrators.py --restore
    migrate_legacy_orchestrators.py --target-dir ~/some-other-claude-dir/agents
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SHIM_MARKER = "<!-- workforce-cc-shim:v1 -->"

LEGACY_AGENTS = {
    "foundation-orchestrator.md": {
        "new_role": "conductor",
        "new_path": "agents/orchestrators/conductor.md",
        "summary": (
            "Conductor (`agents/orchestrators/conductor.md`) is the engineer-team "
            "manager. It splits this agent's old job into three sub-modes: dispatch, "
            "monitor, integrate. It never authors deliverables — only writes contracts "
            "and integrates artifacts."
        ),
    },
    "workforce-orchestrator.md": {
        "new_role": "conductor",
        "new_path": "agents/orchestrators/conductor.md",
        "summary": (
            "Conductor (`agents/orchestrators/conductor.md`) absorbs the 5-dimension "
            "scoring and the agent-selection logic this agent used to do. The scoring "
            "lives inside `conductor --mode=dispatch`."
        ),
    },
    "vision-keeper.md": {
        "new_role": "intent-validator + alignment-guard",
        "new_path": "agents/orchestrators/intent-validator.md",
        "summary": (
            "Mode A (Socratic create) is now `intent-validator`. Modes B/C (drift "
            "confirm) are now `alignment-guard --mode=vision`. Both are at "
            "`agents/orchestrators/`."
        ),
    },
    "output-validator.md": {
        "new_role": "alignment-guard --mode=cross-check",
        "new_path": "agents/orchestrators/alignment-guard.md",
        "summary": (
            "Cross-checking security/requirements/architecture/stack-decision is now "
            "`alignment-guard --mode=cross-check`. The new role unifies status values "
            "(PASS/PASS-WITH-NOTES/BLOCK) and adds a mandatory adversarial self-critique."
        ),
    },
}

SHIM_TEMPLATE = """\
---
name: {orig_name}
description: "[DEPRECATED] {orig_description} — superseded by {new_role}."
tools: Read
model: sonnet
---

{shim_marker}

# {orig_name} — DEPRECATED

This agent has been replaced by **{new_role}** (`{new_path}`).

{summary}

If you invoked this agent directly, please switch to the new role. If a
skill (`/foundation`, `/workforce`) invoked it, the skill itself will be
updated in a future workforce-cc release; until then this shim returns
a clear error rather than silently performing stale work.

## What this shim does

It refuses to act. Output:

```
This agent is deprecated. Use {new_role} instead.
See {new_path} for the replacement.
```

## How to restore the original behavior temporarily

Run `python3 ~/.foundation-path/scripts/migrate_legacy_orchestrators.py --restore`
to swap this shim back to the original agent. The original is preserved at
`<target-dir>/.workforce-backup/{orig_name}.bak`.

_Migrated by `scripts/migrate_legacy_orchestrators.py` on {migrated_at}._
"""


def is_already_shimmed(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return SHIM_MARKER in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def backup_dir_for(target_dir: Path) -> Path:
    return target_dir / ".workforce-backup"


def make_shim(orig_path: Path, info: dict) -> str:
    orig_text = orig_path.read_text()
    description = ""
    in_frontmatter = False
    fm_started = False
    for line in orig_text.splitlines():
        if line.strip() == "---":
            if not fm_started:
                fm_started = True
                in_frontmatter = True
                continue
            in_frontmatter = False
            break
        if in_frontmatter and line.startswith("description:"):
            description = line.split(":", 1)[1].strip().strip('"').strip("'").rstrip(".")
            break
    if not description:
        description = orig_path.stem.replace("-", " ").title()
    return SHIM_TEMPLATE.format(
        orig_name=orig_path.stem,
        orig_description=description[:240],
        new_role=info["new_role"],
        new_path=info["new_path"],
        summary=info["summary"],
        shim_marker=SHIM_MARKER,
        migrated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def cmd_migrate(target_dir: Path, apply: bool) -> int:
    target_dir = target_dir.expanduser().resolve()
    if not target_dir.is_dir():
        print(f"ERROR: target dir does not exist: {target_dir}")
        return 1

    backup = backup_dir_for(target_dir)
    actions: list[str] = []
    skipped: list[str] = []

    for filename, info in LEGACY_AGENTS.items():
        orig = target_dir / filename
        if not orig.exists():
            skipped.append(f"  - {filename} (not installed)")
            continue
        if is_already_shimmed(orig):
            skipped.append(f"  - {filename} (already shimmed)")
            continue

        action = "would rewrite" if not apply else "rewrote"
        actions.append(f"  ↻ {filename} → shim pointing to {info['new_role']}")

        if apply:
            backup.mkdir(exist_ok=True)
            backup_path = backup / f"{filename}.bak"
            if not backup_path.exists():
                shutil.copy2(orig, backup_path)
            orig.write_text(make_shim(orig, info))

    print(f"Target: {target_dir}")
    print(f"Backup: {backup}")
    print()
    if actions:
        print(f"{'Would rewrite' if not apply else 'Rewrote'} {len(actions)} legacy agent(s):")
        for line in actions:
            print(line)
    if skipped:
        print(f"\nSkipped {len(skipped)}:")
        for line in skipped:
            print(line)
    if not apply and actions:
        print("\nRun again with --apply to perform the rewrite.")
    return 0


def cmd_restore(target_dir: Path) -> int:
    target_dir = target_dir.expanduser().resolve()
    backup = backup_dir_for(target_dir)
    if not backup.is_dir():
        print(f"No backup directory found at {backup}. Nothing to restore.")
        return 1

    restored: list[str] = []
    missing: list[str] = []
    for filename in LEGACY_AGENTS:
        bak = backup / f"{filename}.bak"
        target = target_dir / filename
        if bak.exists():
            shutil.copy2(bak, target)
            restored.append(f"  + {filename}")
        else:
            missing.append(f"  - {filename} (no backup)")

    print(f"Target: {target_dir}")
    if restored:
        print(f"Restored {len(restored)}:")
        for line in restored:
            print(line)
    if missing:
        print(f"\nNo backup for {len(missing)}:")
        for line in missing:
            print(line)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument(
        "--target-dir",
        type=Path,
        default=Path("~/.claude/agents"),
        help="Directory containing installed agents (default: ~/.claude/agents/)",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Perform the rewrite (default is dry-run preview).",
    )
    ap.add_argument(
        "--restore",
        action="store_true",
        help="Restore originals from .workforce-backup/.",
    )
    args = ap.parse_args(argv)

    if args.restore:
        return cmd_restore(args.target_dir)
    return cmd_migrate(args.target_dir, args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
