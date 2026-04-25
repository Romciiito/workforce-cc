"""Tests for catalogs/mcp/ + scripts/mcp_query.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = REPO_ROOT / "catalogs" / "mcp" / "index.json"
SCHEMA_PATH = REPO_ROOT / "catalogs" / "mcp-schema.json"
SCRIPT = REPO_ROOT / "scripts" / "mcp_query.py"


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=cwd or REPO_ROOT,
        check=False,
    )


# ── Catalog file integrity ───────────────────────────────────────────────────


def test_index_file_exists() -> None:
    assert INDEX_PATH.exists()


def test_schema_file_exists() -> None:
    assert SCHEMA_PATH.exists()


def test_index_has_servers_array() -> None:
    data = json.loads(INDEX_PATH.read_text())
    assert "servers" in data
    assert isinstance(data["servers"], list)
    assert len(data["servers"]) >= 4


def test_every_server_has_required_fields() -> None:
    data = json.loads(INDEX_PATH.read_text())
    for s in data["servers"]:
        for field in ["id", "category", "summary", "config"]:
            assert field in s, f"server {s.get('id')} missing field: {field}"
        assert "command" in s["config"], f"server {s['id']} missing config.command"


def test_server_ids_are_unique() -> None:
    data = json.loads(INDEX_PATH.read_text())
    ids = [s["id"] for s in data["servers"]]
    assert len(ids) == len(set(ids)), f"duplicate ids: {[i for i in ids if ids.count(i) > 1]}"


def test_categories_are_in_schema_enum() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    allowed = set(schema["properties"]["servers"]["items"]["properties"]["category"]["enum"])
    data = json.loads(INDEX_PATH.read_text())
    for s in data["servers"]:
        assert s["category"] in allowed, f"server {s['id']} has invalid category: {s['category']}"


# ── Script behavior ──────────────────────────────────────────────────────────


def test_list_returns_all_servers() -> None:
    result = _run("list")
    assert result.returncode == 0
    assert "github" in result.stdout
    assert "postgres" in result.stdout


def test_list_filter_by_category() -> None:
    result = _run("list", "--category", "database")
    assert result.returncode == 0
    assert "postgres" in result.stdout
    # github is vcs, must not appear under database filter
    assert "github" not in result.stdout


def test_list_filter_by_stack_includes_universal_servers() -> None:
    """A server with no 'stacks' list applies to every stack — must be in the result."""
    result = _run("list", "--stack", "python-fastapi")
    assert result.returncode == 0
    assert "github" in result.stdout  # universal
    assert "postgres" in result.stdout  # explicitly listed for python-fastapi


def test_list_json_output() -> None:
    result = _run("--json", "list")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert any(s["id"] == "github" for s in payload)


def test_show_existing_server() -> None:
    result = _run("show", "github")
    assert result.returncode == 0
    assert "github" in result.stdout
    assert "vcs" in result.stdout


def test_show_unknown_server_fails() -> None:
    result = _run("show", "no-such-server")
    assert result.returncode == 1


def test_emit_prints_json_snippet() -> None:
    result = _run("emit", "github")
    assert result.returncode == 0
    snippet = json.loads(result.stdout)
    assert "github" in snippet
    assert "command" in snippet["github"]


def test_emit_resolves_placeholders() -> None:
    result = _run("emit", "github", "--placeholders", "GITHUB_TOKEN=ghp_test123")
    assert result.returncode == 0
    snippet = json.loads(result.stdout)
    env = snippet["github"]["env"]
    assert env["GITHUB_PERSONAL_ACCESS_TOKEN"] == "ghp_test123"


def test_emit_apply_merges_into_settings(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    result = _run(
        "emit",
        "github",
        "--apply",
        "--project-dir",
        str(project),
        "--placeholders",
        "GITHUB_TOKEN=ghp_test",
    )
    assert result.returncode == 0
    settings = json.loads((project / ".claude" / "settings.local.json").read_text())
    assert "mcpServers" in settings
    assert "github" in settings["mcpServers"]
    assert settings["mcpServers"]["github"]["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] == "ghp_test"


def test_emit_apply_idempotent(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _run("emit", "github", "--apply", "--project-dir", str(project))
    result = _run("emit", "github", "--apply", "--project-dir", str(project))
    assert result.returncode == 0
    assert "already configured" in result.stdout


def test_emit_apply_preserves_existing_settings(tmp_path: Path) -> None:
    """--apply must not blow away other keys in settings.local.json."""
    project = tmp_path / "project"
    settings_path = project / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({
        "permissions": {"allow": ["Bash(git:*)"]},
        "mcpServers": {"existing": {"command": "stub"}},
    }))

    _run("emit", "github", "--apply", "--project-dir", str(project))
    settings = json.loads(settings_path.read_text())
    assert settings["permissions"]["allow"] == ["Bash(git:*)"]
    assert "existing" in settings["mcpServers"]
    assert "github" in settings["mcpServers"]


def test_emit_unknown_server_fails(tmp_path: Path) -> None:
    result = _run("emit", "nope")
    assert result.returncode == 1
