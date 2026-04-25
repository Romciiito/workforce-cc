#!/usr/bin/env python3
"""
harness_install.py — render a harness adapter into a project.

Reads `harnesses/<name>/manifest.json` and applies each `writes` entry to
the target project directory. Supports four kinds of writes:

  - rules-file       Render a Jinja2 template (or copy a literal file)
                     into a single target path.
  - agents-dir       Copy agents from declared packs into a target dir.
  - settings         Invoke a Python callable (today: scripts/scaffold.py
                     write_settings) to generate a JSON settings file.
  - config-file      Copy a static file into the target.

Usage:
    harness_install.py --harness claude --project-dir . \\
        --project-name Acme --stack python-fastapi \\
        --description "An acme app"

    harness_install.py --harness cursor --project-dir . \\
        --project-name Acme --stack python-fastapi --dry-run

Multiple harnesses at once: invoke once per harness from install.sh.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESSES_DIR = REPO_ROOT / "harnesses"
AGENTS_DIR = REPO_ROOT / "agents"

ALLOWED_HARNESSES = frozenset({"claude", "cursor", "codex", "opencode", "gemini"})


def derive_env_prefix(project_name: str) -> str:
    """Mirror the helper in scripts/scaffold.py so harnesses get the same prefix."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", project_name).strip("_").upper()
    if not cleaned or not cleaned[0].isalpha():
        return "APP"
    return cleaned


def load_manifest(harness: str) -> dict:
    path = HARNESSES_DIR / harness / "manifest.json"
    if not path.exists():
        raise SystemExit(f"ERROR: manifest not found at {path}")
    return json.loads(path.read_text())


def render_template(source: Path, ctx: dict) -> str:
    try:
        from jinja2 import Environment, FileSystemLoader, StrictUndefined  # type: ignore
    except ImportError:
        raise SystemExit("ERROR: --harness rendering requires jinja2 (pip install jinja2)")
    env = Environment(
        loader=FileSystemLoader(str(source.parent)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    return env.get_template(source.name).render(**ctx)


def apply_rules_file(entry: dict, project_dir: Path, ctx: dict, dry_run: bool) -> Optional[str]:
    target = project_dir / entry["target"]
    overwrite = bool(entry.get("overwrite", False))
    if target.exists() and not overwrite:
        return f"= {entry['target']} (exists; skipping; manifest sets overwrite=false)"
    source_rel = entry.get("source")
    if not source_rel:
        return f"! {entry['target']} (rules-file kind requires 'source' field)"
    source = REPO_ROOT / source_rel
    if not source.exists():
        return f"! {entry['target']} (source missing: {source_rel})"
    if entry.get("render") == "jinja2":
        rendered = render_template(source, ctx)
    else:
        rendered = source.read_text()
    if dry_run:
        return f"+ would write {entry['target']} ({len(rendered)} bytes)"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered)
    return f"+ {entry['target']}"


def apply_agents_dir(entry: dict, project_dir: Path, dry_run: bool) -> list[str]:
    """Copy agents from declared packs into target dir."""
    target_dir = project_dir / entry["target"]
    packs = entry.get("from_packs", [])
    overwrite = bool(entry.get("overwrite", False))
    notes: list[str] = []
    for pack in packs:
        pack_dir = AGENTS_DIR / pack
        if not pack_dir.is_dir():
            notes.append(f"! pack {pack} missing under agents/")
            continue
        for src in pack_dir.glob("*.md"):
            if src.name == "README.md":
                continue
            dst = target_dir / src.name
            if dst.exists() and not overwrite:
                notes.append(f"= {entry['target']}{src.name} (exists)")
                continue
            if dry_run:
                notes.append(f"+ would copy agents/{pack}/{src.name} → {entry['target']}{src.name}")
                continue
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            notes.append(f"+ {entry['target']}{src.name}")
    return notes


def apply_settings(entry: dict, project_dir: Path, ctx: dict, dry_run: bool) -> str:
    """Today: only one settings source — scripts/scaffold.py:write_settings.

    The helper writes .claude/settings.local.json with stack-appropriate
    permissions. We avoid importing scaffold.py here to keep this script
    standalone; instead we inline the same logic.
    """
    stack = ctx.get("stack")
    target = project_dir / entry["target"]
    overwrite = bool(entry.get("overwrite", False))
    if target.exists() and not overwrite:
        return f"= {entry['target']} (exists; skipping)"

    # Re-use scaffold.py's STACK_PERMISSIONS via importlib so the source
    # of truth stays in scripts/scaffold.py.
    import importlib.util
    spec = importlib.util.spec_from_file_location("scaffold_for_harness", REPO_ROOT / "scripts" / "scaffold.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    perms = mod.STACK_PERMISSIONS.get(stack, mod.STACK_PERMISSIONS.get("python-fastapi", []))
    settings = {"permissions": {"allow": perms}}

    if dry_run:
        return f"+ would write {entry['target']} ({len(perms)} permissions for stack {stack})"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(settings, indent=2) + "\n")
    return f"+ {entry['target']}"


def apply_config_file(entry: dict, project_dir: Path, dry_run: bool) -> str:
    source_rel = entry.get("source")
    if not source_rel:
        return f"! {entry['target']} (config-file kind requires 'source' field)"
    source = REPO_ROOT / source_rel
    target = project_dir / entry["target"]
    overwrite = bool(entry.get("overwrite", False))
    if target.exists() and not overwrite:
        return f"= {entry['target']} (exists; skipping)"
    if dry_run:
        return f"+ would copy {source_rel} → {entry['target']}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return f"+ {entry['target']}"


def install_harness(
    harness: str,
    project_dir: Path,
    project_name: str,
    stack: str,
    description: str,
    critical_rules: str,
    dry_run: bool,
) -> int:
    if harness not in ALLOWED_HARNESSES:
        print(f"ERROR: unknown harness {harness!r}. Allowed: {sorted(ALLOWED_HARNESSES)}", file=sys.stderr)
        return 1
    manifest = load_manifest(harness)

    ctx = {
        "project_name": project_name,
        "stack": stack,
        "description": description,
        "env_prefix": derive_env_prefix(project_name),
        "critical_rules": critical_rules,
    }

    print(f"Harness: {harness}  ({manifest['description']})")
    print(f"Project: {project_dir}")
    print(f"Mode:    {'dry-run' if dry_run else 'write'}")
    print()

    for entry in manifest["writes"]:
        kind = entry["kind"]
        if kind == "rules-file":
            note = apply_rules_file(entry, project_dir, ctx, dry_run)
            if note:
                print(f"  {note}")
        elif kind == "agents-dir":
            for note in apply_agents_dir(entry, project_dir, dry_run):
                print(f"  {note}")
        elif kind == "settings":
            print(f"  {apply_settings(entry, project_dir, ctx, dry_run)}")
        elif kind == "config-file":
            print(f"  {apply_config_file(entry, project_dir, dry_run)}")
        else:
            print(f"  ! unknown kind: {kind}")

    print()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--harness", required=True, help="Harness name (e.g. claude, cursor)")
    ap.add_argument("--project-dir", required=True, type=Path)
    ap.add_argument("--project-name", required=True)
    ap.add_argument("--stack", default="python-fastapi")
    ap.add_argument("--description", default="")
    ap.add_argument("--critical-rules", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    return install_harness(
        args.harness,
        Path(args.project_dir).resolve(),
        args.project_name,
        args.stack,
        args.description,
        args.critical_rules,
        args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
