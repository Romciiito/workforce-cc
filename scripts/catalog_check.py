#!/usr/bin/env python3
"""
catalog_check.py — validate catalogs/<source>/index.json against its bodies
and (optionally) detect drift from upstream.

Subcommands
-----------

    catalog_check.py validate [--catalog ecc]
        Asserts:
          * Every index entry has a matching body file under bodies/.
          * Every body file is referenced by exactly one index entry.
          * IDs are unique and match the schema id-pattern.
          * tags include `kind:<kind>` and `source:<catalog>`.

    catalog_check.py drift --from /path/to/upstream/clone [--catalog ecc]
        For each entry, recomputes upstream_sha against the upstream clone
        and reports differences. Exit 0 if no drift, 1 if drift found.

Both subcommands print machine-readable JSON when --json is passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOGS_DIR = REPO_ROOT / "catalogs"

ID_PATTERN = re.compile(r"^[a-z][a-z0-9._-]*$")


def short_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:16]


def load_index(catalog: str) -> dict:
    path = CATALOGS_DIR / catalog / "index.json"
    if not path.exists():
        raise SystemExit(f"ERROR: catalog index not found: {path}")
    return json.loads(path.read_text())


def cmd_validate(catalog: str, as_json: bool) -> int:
    index = load_index(catalog)
    catalog_dir = CATALOGS_DIR / catalog
    bodies_dir = catalog_dir / "bodies"

    failures: list[str] = []
    seen_ids: set[str] = set()
    referenced_bodies: set[Path] = set()

    for entry in index.get("entries", []):
        eid = entry.get("id", "<missing>")
        if eid in seen_ids:
            failures.append(f"duplicate id: {eid}")
        seen_ids.add(eid)
        if not ID_PATTERN.match(eid):
            failures.append(f"bad id format: {eid}")

        # Tags must include the kind tag and source tag.
        kind = entry.get("kind")
        tags = entry.get("tags", [])
        if kind and f"kind:{kind}" not in tags:
            failures.append(f"{eid}: missing 'kind:{kind}' tag")
        if f"source:{catalog}" not in tags:
            failures.append(f"{eid}: missing 'source:{catalog}' tag")

        sp = entry.get("source_path")
        if not sp:
            failures.append(f"{eid}: missing source_path")
            continue
        body = catalog_dir / sp
        if not body.exists():
            failures.append(f"{eid}: body file missing at {sp}")
            continue
        referenced_bodies.add(body.resolve())

    # Detect orphan bodies (files on disk not referenced by any entry).
    if bodies_dir.exists():
        for body in bodies_dir.rglob("*.md"):
            if body.resolve() not in referenced_bodies:
                failures.append(f"orphan body file (no index entry): {body.relative_to(catalog_dir)}")

    if as_json:
        print(json.dumps({"catalog": catalog, "ok": not failures, "failures": failures}, indent=2))
    else:
        if failures:
            print(f"VALIDATE FAILED for catalog '{catalog}' ({len(failures)} issues):")
            for f in failures:
                print(f"  - {f}")
        else:
            print(f"VALIDATE OK — catalog '{catalog}' has {len(index.get('entries', []))} entries.")
    return 1 if failures else 0


def cmd_drift(catalog: str, source: Path, as_json: bool) -> int:
    if not source.is_dir():
        raise SystemExit(f"ERROR: --from path is not a directory: {source}")
    index = load_index(catalog)

    drifted: list[dict] = []
    missing_upstream: list[str] = []

    for entry in index.get("entries", []):
        eid = entry["id"]
        upstream_path = entry.get("upstream_path")
        if not upstream_path:
            continue
        upstream_file = source / upstream_path
        if not upstream_file.exists():
            missing_upstream.append(eid)
            continue
        new_sha = short_hash(upstream_file.read_bytes())
        if new_sha != entry.get("upstream_sha"):
            drifted.append(
                {
                    "id": eid,
                    "kind": entry.get("kind"),
                    "old_sha": entry.get("upstream_sha"),
                    "new_sha": new_sha,
                }
            )

    has_changes = bool(drifted or missing_upstream)
    if as_json:
        print(
            json.dumps(
                {
                    "catalog": catalog,
                    "drifted": drifted,
                    "missing_upstream": missing_upstream,
                },
                indent=2,
            )
        )
    else:
        if drifted:
            print(f"DRIFT in catalog '{catalog}' — {len(drifted)} entries changed upstream:")
            for d in drifted:
                print(f"  ↻ {d['id']:<60} {d['old_sha']} → {d['new_sha']}")
        if missing_upstream:
            print(f"MISSING upstream files for {len(missing_upstream)} entries:")
            for eid in missing_upstream:
                print(f"  ✗ {eid}")
        if not has_changes:
            print(f"DRIFT OK — catalog '{catalog}' is in sync with upstream.")
    return 1 if has_changes else 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--json", action="store_true", help="JSON output for machine consumption")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate", help="Validate index ↔ bodies consistency")
    p_val.add_argument("--catalog", default="ecc")

    p_drift = sub.add_parser("drift", help="Compare against upstream clone")
    p_drift.add_argument("--catalog", default="ecc")
    p_drift.add_argument("--from", dest="source", required=True)

    args = ap.parse_args(argv)

    if args.cmd == "validate":
        return cmd_validate(args.catalog, args.json)
    if args.cmd == "drift":
        return cmd_drift(args.catalog, Path(args.source).expanduser().resolve(), args.json)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
