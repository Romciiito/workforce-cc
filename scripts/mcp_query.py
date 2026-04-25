#!/usr/bin/env python3
"""
mcp_query.py — list, filter, and emit MCP server configurations from
catalogs/mcp/index.json for a project.

Subcommands
-----------

    mcp_query.py list [--category <cat>] [--stack <stack>]
    mcp_query.py show <id>
    mcp_query.py emit <id> [--project-dir .] [--placeholders KEY=VALUE ...]
        Print the JSON snippet to add under .claude/settings.local.json's
        mcpServers map. With --apply, write it directly into the file.

Pattern: identical to scripts/catalog_query.py but for MCP server configs
rather than agent/skill/command bodies.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = REPO_ROOT / "catalogs" / "mcp" / "index.json"

PLACEHOLDER_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def load_index() -> dict:
    if not INDEX_PATH.exists():
        raise SystemExit(f"ERROR: MCP catalog not found at {INDEX_PATH}")
    return json.loads(INDEX_PATH.read_text())


def find_server(server_id: str) -> Optional[dict]:
    for s in load_index().get("servers", []):
        if s["id"] == server_id:
            return s
    return None


def resolve_placeholders(value, mapping: dict[str, str]):
    if isinstance(value, str):
        return PLACEHOLDER_RE.sub(lambda m: mapping.get(m.group(1), m.group(0)), value)
    if isinstance(value, list):
        return [resolve_placeholders(v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: resolve_placeholders(v, mapping) for k, v in value.items()}
    return value


# ── Subcommands ──────────────────────────────────────────────────────────────


def cmd_list(category: Optional[str], stack: Optional[str], as_json: bool) -> int:
    servers = load_index().get("servers", [])
    if category:
        servers = [s for s in servers if s.get("category") == category]
    if stack:
        servers = [s for s in servers if not s.get("stacks") or stack in s.get("stacks", [])]
    if as_json:
        print(json.dumps(servers, indent=2))
        return 0
    if not servers:
        print("No MCP servers match those filters.")
        return 0
    print(f"{len(servers)} MCP server(s):")
    print(f"{'ID':<24} {'CATEGORY':<14} SUMMARY")
    print("─" * 80)
    for s in servers:
        print(f"{s['id']:<24} {s.get('category', '?'):<14} {s.get('summary', '')[:40]}")
    return 0


def cmd_show(server_id: str, as_json: bool) -> int:
    s = find_server(server_id)
    if not s:
        print(f"ERROR: no MCP server with id '{server_id}'", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps(s, indent=2))
        return 0
    print(f"id:        {s['id']}")
    print(f"category:  {s.get('category')}")
    print(f"summary:   {s.get('summary')}")
    if s.get("stacks"):
        print(f"stacks:    {', '.join(s['stacks'])}")
    print(f"command:   {s['config'].get('command')}")
    if s["config"].get("args"):
        print(f"args:      {' '.join(s['config']['args'])}")
    if s["config"].get("env"):
        print("env:")
        for k, v in s["config"]["env"].items():
            print(f"  {k}: {v}")
    if s.get("use_when"):
        print("use when:")
        for line in s["use_when"]:
            print(f"  - {line}")
    return 0


def cmd_emit(server_id: str, project_dir: Path, placeholders: dict[str, str], apply: bool) -> int:
    s = find_server(server_id)
    if not s:
        print(f"ERROR: no MCP server with id '{server_id}'", file=sys.stderr)
        return 1

    resolved_config = resolve_placeholders(s["config"], placeholders)
    snippet = {server_id: resolved_config}

    if not apply:
        # Print the JSON snippet ready to be merged into mcpServers.
        print(json.dumps(snippet, indent=2))
        return 0

    # --apply: merge into <project_dir>/.claude/settings.local.json
    settings_path = project_dir.resolve() / ".claude" / "settings.local.json"
    settings: dict = {}
    if settings_path.exists():
        settings = json.loads(settings_path.read_text())
    settings.setdefault("mcpServers", {})
    if server_id in settings["mcpServers"]:
        print(f"= {server_id} (already configured in {settings_path})")
        return 0
    settings["mcpServers"][server_id] = resolved_config
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"+ added {server_id} to {settings_path}")
    return 0


def parse_kv(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--placeholders entries must be KEY=VALUE; got: {item!r}")
        k, v = item.split("=", 1)
        out[k] = v
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--json", action="store_true", help="JSON output for list/show")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list")
    p_list.add_argument("--category")
    p_list.add_argument("--stack")

    p_show = sub.add_parser("show")
    p_show.add_argument("server_id")

    p_emit = sub.add_parser("emit", help="Print or apply the JSON snippet for one server")
    p_emit.add_argument("server_id")
    p_emit.add_argument("--project-dir", type=Path, default=Path.cwd())
    p_emit.add_argument("--apply", action="store_true",
                        help="Merge into <project>/.claude/settings.local.json")
    p_emit.add_argument(
        "--placeholders",
        nargs="*",
        default=[],
        help="KEY=VALUE pairs to substitute for ${KEY} placeholders in the config",
    )

    args = ap.parse_args(argv)

    if args.cmd == "list":
        return cmd_list(args.category, args.stack, args.json)
    if args.cmd == "show":
        return cmd_show(args.server_id, args.json)
    if args.cmd == "emit":
        return cmd_emit(
            args.server_id,
            args.project_dir,
            parse_kv(args.placeholders),
            args.apply,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
