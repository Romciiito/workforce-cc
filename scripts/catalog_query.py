#!/usr/bin/env python3
"""
catalog_query.py — list, search, enable, and disable catalog entries.

The conductor consults this script (or the underlying ``index.json``)
when picking an engineer pool — extending the built-in pool with entries
the project's allowlist has marked enabled.

Subcommands
-----------

    catalog_query.py list [--catalog ecc] [--kind agent|skill|command|hook|mcp]
                          [--tag <tag>] [--stack <stack>]

    catalog_query.py show <id> [--catalog ecc]

    catalog_query.py enable <id> [--catalog ecc] [--project-dir .]
    catalog_query.py disable <id> [--catalog ecc] [--project-dir .]
    catalog_query.py enabled [--project-dir .]

The ``--project-dir`` option points at the project whose
``catalogs/workforce/enabled.json`` is being read or written. By default
that file lives next to the *user's* project (i.e. the directory
catalogs/workforce/enabled.json from the repo is the *template*; each
project gets its own copy).

Output
------

Human-readable tables by default. Pass ``--json`` for machine-readable
output. Exit codes are 0 for success, 1 for "not found", 2 for "bad
input".

Notes
-----

The script does not install entries into ``~/.claude/``. That is
``install.sh``'s job; this script only manages the **per-project
allowlist** that the conductor reads when deciding which engineers
to dispatch.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOGS_DIR = REPO_ROOT / "catalogs"
DEFAULT_CATALOG = "ecc"


def load_catalog(catalog: str) -> dict:
    path = CATALOGS_DIR / catalog / "index.json"
    if not path.exists():
        raise SystemExit(f"ERROR: catalog index not found: {path}")
    return json.loads(path.read_text())


def find_entry(catalog: str, entry_id: str) -> Optional[dict]:
    data = load_catalog(catalog)
    for entry in data.get("entries", []):
        if entry["id"] == entry_id:
            return entry
    return None


def project_allowlist_path(project_dir: Path) -> Path:
    """Each project gets its own catalogs/workforce/enabled.json.

    For convenience, if the project doesn't have one we fall back to the
    repo's own (which serves as a template).
    """
    project_local = Path(project_dir).resolve() / "catalogs" / "workforce" / "enabled.json"
    if project_local.exists():
        return project_local
    return CATALOGS_DIR / "workforce" / "enabled.json"


def project_allowlist_write_path(project_dir: Path) -> Path:
    """Where to write changes — always project-local."""
    project_dir = Path(project_dir).resolve()
    return project_dir / "catalogs" / "workforce" / "enabled.json"


def load_allowlist(project_dir: Path) -> dict:
    path = project_allowlist_path(project_dir)
    if not path.exists():
        return {"enabled": [], "declined": []}
    return json.loads(path.read_text())


def save_allowlist(project_dir: Path, data: dict) -> Path:
    target = project_allowlist_write_path(project_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "$schema": "../schema.json",
        "description": "Per-project allowlist. Managed by scripts/catalog_query.py.",
        "enabled": sorted(set(data.get("enabled", []))),
        "declined": sorted(set(data.get("declined", []))),
    }
    target.write_text(json.dumps(payload, indent=2) + "\n")
    return target


# ── Subcommands ──────────────────────────────────────────────────────────────


def cmd_list(catalog: str, kind: Optional[str], tag: Optional[str], stack: Optional[str], as_json: bool) -> int:
    data = load_catalog(catalog)
    entries = data.get("entries", [])
    if kind:
        entries = [e for e in entries if e.get("kind") == kind]
    if tag:
        entries = [e for e in entries if tag in e.get("tags", [])]
    if stack:
        entries = [e for e in entries if stack in e.get("stacks", []) or not e.get("stacks")]

    if as_json:
        print(json.dumps(entries, indent=2))
        return 0
    if not entries:
        print(f"No catalog entries match those filters in '{catalog}'.")
        return 0

    print(f"{len(entries)} entries in catalog '{catalog}':")
    print(f"{'ID':<55} {'KIND':<10} SUMMARY")
    print("─" * 100)
    for e in entries:
        eid = e["id"][:55]
        ek = e.get("kind", "?")[:10]
        es = (e.get("summary") or "")[:40]
        print(f"{eid:<55} {ek:<10} {es}")
    return 0


def cmd_show(catalog: str, entry_id: str, as_json: bool) -> int:
    entry = find_entry(catalog, entry_id)
    if not entry:
        print(f"ERROR: no catalog entry with id '{entry_id}' in catalog '{catalog}'.", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps(entry, indent=2))
        return 0
    print(f"id:            {entry['id']}")
    print(f"kind:          {entry.get('kind')}")
    print(f"summary:       {entry.get('summary')}")
    print(f"upstream_path: {entry.get('upstream_path')}")
    print(f"upstream_sha:  {entry.get('upstream_sha')}")
    print(f"tags:          {', '.join(entry.get('tags', []))}")
    if entry.get("stacks"):
        print(f"stacks:        {', '.join(entry['stacks'])}")
    body_path = CATALOGS_DIR / catalog / entry.get("source_path", "")
    print(f"body:          {body_path}{'  (missing)' if not body_path.exists() else ''}")
    return 0


def cmd_enable(catalog: str, entry_id: str, project_dir: Path) -> int:
    entry = find_entry(catalog, entry_id)
    if not entry:
        print(f"ERROR: no catalog entry with id '{entry_id}' in catalog '{catalog}'.", file=sys.stderr)
        return 1
    allowlist = load_allowlist(project_dir)
    enabled = set(allowlist.get("enabled", []))
    declined = set(allowlist.get("declined", []))
    if entry_id in enabled:
        print(f"= {entry_id} (already enabled)")
        return 0
    enabled.add(entry_id)
    declined.discard(entry_id)
    target = save_allowlist(project_dir, {"enabled": list(enabled), "declined": list(declined)})
    print(f"+ enabled {entry_id} in {target}")
    return 0


def cmd_disable(catalog: str, entry_id: str, project_dir: Path) -> int:
    allowlist = load_allowlist(project_dir)
    enabled = set(allowlist.get("enabled", []))
    declined = set(allowlist.get("declined", []))
    if entry_id not in enabled and entry_id in declined:
        print(f"= {entry_id} (already declined)")
        return 0
    enabled.discard(entry_id)
    declined.add(entry_id)
    target = save_allowlist(project_dir, {"enabled": list(enabled), "declined": list(declined)})
    print(f"- disabled {entry_id} in {target}")
    return 0


def cmd_enabled(project_dir: Path, as_json: bool) -> int:
    allowlist = load_allowlist(project_dir)
    if as_json:
        print(json.dumps(allowlist, indent=2))
        return 0
    enabled = allowlist.get("enabled", [])
    declined = allowlist.get("declined", [])
    if not enabled and not declined:
        print(f"No catalog entries enabled or declined in {project_dir}.")
        return 0
    if enabled:
        print(f"{len(enabled)} enabled:")
        for eid in enabled:
            print(f"  + {eid}")
    if declined:
        print(f"\n{len(declined)} declined:")
        for eid in declined:
            print(f"  - {eid}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--json", action="store_true", help="JSON output where applicable")
    ap.add_argument("--catalog", default=DEFAULT_CATALOG, help="Catalog name (default: ecc)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List catalog entries")
    p_list.add_argument("--kind", choices=["agent", "skill", "command", "hook", "mcp"])
    p_list.add_argument("--tag", help="Filter by exact tag")
    p_list.add_argument("--stack", help="Filter by stack (entries with empty stacks list match every filter)")

    p_show = sub.add_parser("show", help="Show one catalog entry")
    p_show.add_argument("entry_id")

    p_enable = sub.add_parser("enable", help="Enable an entry in a project's allowlist")
    p_enable.add_argument("entry_id")
    p_enable.add_argument("--project-dir", type=Path, default=Path.cwd())

    p_disable = sub.add_parser("disable", help="Decline an entry in a project's allowlist")
    p_disable.add_argument("entry_id")
    p_disable.add_argument("--project-dir", type=Path, default=Path.cwd())

    p_enabled = sub.add_parser("enabled", help="Show a project's allowlist")
    p_enabled.add_argument("--project-dir", type=Path, default=Path.cwd())

    args = ap.parse_args(argv)

    if args.cmd == "list":
        return cmd_list(args.catalog, args.kind, args.tag, args.stack, args.json)
    if args.cmd == "show":
        return cmd_show(args.catalog, args.entry_id, args.json)
    if args.cmd == "enable":
        return cmd_enable(args.catalog, args.entry_id, args.project_dir)
    if args.cmd == "disable":
        return cmd_disable(args.catalog, args.entry_id, args.project_dir)
    if args.cmd == "enabled":
        return cmd_enabled(args.project_dir, args.json)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
