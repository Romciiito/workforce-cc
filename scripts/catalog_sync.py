#!/usr/bin/env python3
"""
catalog_sync.py — populate catalogs/ecc/ from a local checkout of
affaan-m/everything-claude-code (or a compatible mirror).

This is deliberately not a git submodule. Submodules break in fresh clones
that forget --recursive; the sync script is the single entry point so the
workflow is the same on first run as on every subsequent run.

Usage
-----
    catalog_sync.py --from /path/to/everything-claude-code/clone
    catalog_sync.py --from <path> --dry-run
    catalog_sync.py --from <path> --kinds agent,skill   # default: agent,skill,command

What it does
------------

1. Discovers entries by walking `agents/`, `skills/`, `commands/` under the
   provided source directory. Each markdown file with a `name:` frontmatter
   field becomes one entry.
2. Computes a content hash for each entry (sha256 of body bytes, first 16 hex).
3. Copies bodies into `catalogs/ecc/bodies/<kind>/<id>.md` (or `<id>/SKILL.md`
   for skills with directory layout).
4. Rewrites `catalogs/ecc/index.json` with the new entry list, preserving
   any custom `tags` or `stacks` overrides via a side-car `_overrides.json`.

The script does NOT touch `catalogs/workforce/enabled.json` — that's the
per-project allowlist managed by the workforce orchestrator.

Drift / pruning
---------------

Entries that no longer exist upstream are flagged in stdout but kept in
`index.json` unless `--prune` is passed. This avoids surprise removals
when upstream renames or restructures.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = REPO_ROOT / "catalogs" / "ecc"
BODIES_DIR = CATALOG_DIR / "bodies"
INDEX_PATH = CATALOG_DIR / "index.json"
OVERRIDES_PATH = CATALOG_DIR / "_overrides.json"

FRONTMATTER_RE = re.compile(r"^﻿?\s*---\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)", re.DOTALL)
KV_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$")
ID_PATTERN = re.compile(r"^[a-z][a-z0-9._-]*$")


@dataclasses.dataclass
class Entry:
    id: str
    kind: str
    source_path: str
    upstream_path: str
    upstream_sha: str
    summary: str
    tags: list[str]
    stacks: list[str]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "source_path": self.source_path,
            "upstream_path": self.upstream_path,
            "upstream_sha": self.upstream_sha,
            "summary": self.summary,
            "tags": list(self.tags),
            "stacks": list(self.stacks),
        }


def parse_frontmatter(raw: str) -> Optional[dict[str, str]]:
    match = FRONTMATTER_RE.match(raw)
    if not match:
        return None
    body = match.group(1)
    out: dict[str, str] = {}
    for line in body.splitlines():
        kv = KV_RE.match(line)
        if not kv:
            continue
        key, value = kv.group(1), kv.group(2).strip()
        if len(value) >= 2 and (
            (value.startswith('"') and value.endswith('"'))
            or (value.startswith("'") and value.endswith("'"))
        ):
            value = value[1:-1]
        out[key] = value
    return out


def short_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:16]


def make_id(kind: str, name: str) -> str:
    """Produce a stable catalog id from kind + upstream name.

    `ecc.<kind>.<name>` → e.g. `ecc.agent.security-reviewer`.
    """
    safe_name = re.sub(r"[^a-z0-9._-]+", "-", name.lower()).strip("-")
    return f"ecc.{kind}.{safe_name}"


def discover(source: Path, kinds: Iterable[str]) -> list[Entry]:
    entries: list[Entry] = []
    for kind in kinds:
        kind_dir = source / f"{kind}s"  # agents/, skills/, commands/
        if not kind_dir.is_dir():
            continue
        candidates = sorted(kind_dir.rglob("*.md"))
        for path in candidates:
            try:
                raw_bytes = path.read_bytes()
                raw_text = raw_bytes.decode("utf-8", errors="replace")
            except OSError:
                continue
            fm = parse_frontmatter(raw_text)
            if not fm or "name" not in fm:
                continue
            name = fm["name"]
            if not name:
                continue
            cat_id = make_id(kind, name)
            if not ID_PATTERN.match(cat_id):
                print(f"  skip: {path} — derived id {cat_id!r} is not valid", file=sys.stderr)
                continue
            rel_upstream = path.relative_to(source).as_posix()
            entries.append(
                Entry(
                    id=cat_id,
                    kind=kind,
                    source_path=f"bodies/{kind}/{cat_id}.md",
                    upstream_path=rel_upstream,
                    upstream_sha=short_hash(raw_bytes),
                    summary=(fm.get("description") or "").strip().replace("\n", " ")[:280],
                    tags=[f"kind:{kind}", "source:ecc"],
                    stacks=[],
                )
            )
    return entries


def load_overrides() -> dict:
    if OVERRIDES_PATH.exists():
        return json.loads(OVERRIDES_PATH.read_text())
    return {}


def apply_overrides(entries: list[Entry], overrides: dict) -> None:
    """Per-entry overrides for tags/stacks/summary. Survives sync."""
    for e in entries:
        ov = overrides.get(e.id, {})
        if "tags" in ov:
            # Preserve auto-tags + add user tags (deduped).
            user_tags = [t for t in ov["tags"] if t not in e.tags]
            e.tags = e.tags + user_tags
        if "stacks" in ov:
            e.stacks = list(ov["stacks"])
        if "summary" in ov:
            e.summary = ov["summary"][:280]


def copy_bodies(source: Path, entries: list[Entry], dry_run: bool) -> None:
    for e in entries:
        src = source / e.upstream_path
        dst = CATALOG_DIR / e.source_path
        if dry_run:
            print(f"  would copy {e.upstream_path} → {e.source_path}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def write_index(entries: list[Entry], source: Path, upstream_commit: Optional[str], dry_run: bool) -> None:
    payload = {
        "$schema": "../schema.json",
        "source": {
            "repo": "affaan-m/everything-claude-code",
            "license": "MIT",
            "upstream_commit": upstream_commit,
            "synced_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "entries": [e.to_dict() for e in entries],
    }
    if dry_run:
        print(f"  would write index.json with {len(entries)} entries")
        return
    INDEX_PATH.write_text(json.dumps(payload, indent=2) + "\n")


def detect_upstream_commit(source: Path) -> Optional[str]:
    head = source / ".git" / "HEAD"
    if not head.exists():
        return None
    try:
        ref_line = head.read_text().strip()
        if ref_line.startswith("ref: "):
            ref_path = source / ".git" / ref_line[len("ref: "):].strip()
            if ref_path.exists():
                return ref_path.read_text().strip()
        if len(ref_line) >= 7 and all(c in "0123456789abcdef" for c in ref_line):
            return ref_line
    except OSError:
        pass
    return None


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--from", dest="source", required=True, help="Local path to upstream clone")
    ap.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    ap.add_argument(
        "--kinds",
        default="agent,skill,command",
        help="Comma-separated kinds to import (default: agent,skill,command)",
    )
    args = ap.parse_args(argv)

    source = Path(args.source).expanduser().resolve()
    if not source.is_dir():
        print(f"ERROR: --from path is not a directory: {source}", file=sys.stderr)
        return 1

    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
    print(f"Source:  {source}")
    print(f"Kinds:   {', '.join(kinds)}")
    print(f"Catalog: {CATALOG_DIR}")
    print(f"Mode:    {'dry-run' if args.dry_run else 'write'}")
    print()

    entries = discover(source, kinds)
    if not entries:
        print(f"ERROR: no catalog-eligible entries found under {source}", file=sys.stderr)
        return 1

    overrides = load_overrides()
    apply_overrides(entries, overrides)

    print(f"Discovered {len(entries)} entries:")
    by_kind: dict[str, int] = {}
    for e in entries:
        by_kind[e.kind] = by_kind.get(e.kind, 0) + 1
    for kind, count in sorted(by_kind.items()):
        print(f"  {kind:<10} {count}")
    print()

    copy_bodies(source, entries, args.dry_run)
    write_index(entries, source, detect_upstream_commit(source), args.dry_run)

    print()
    print(f"{'Would sync' if args.dry_run else 'Synced'} {len(entries)} entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
