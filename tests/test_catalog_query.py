"""Tests for scripts/catalog_query.py."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
QUERY_SCRIPT = REPO_ROOT / "scripts" / "catalog_query.py"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "catalog_sync.py"
CATALOG_DIR = REPO_ROOT / "catalogs" / "ecc"


def _build_fake_upstream(tmp_path: Path) -> Path:
    src = tmp_path / "fake-ecc"
    (src / "agents").mkdir(parents=True)
    (src / "skills").mkdir(parents=True)
    (src / "agents" / "alpha.md").write_text(
        '---\nname: alpha\ndescription: Alpha agent.\n---\n# A\n'
    )
    (src / "agents" / "beta.md").write_text(
        '---\nname: beta\ndescription: Beta agent.\n---\n# B\n'
    )
    (src / "skills" / "gamma.md").write_text(
        '---\nname: gamma\ndescription: Gamma skill.\n---\n# G\n'
    )
    return src


@pytest.fixture
def populated_catalog(tmp_path: Path):
    backup = tmp_path / "backup"
    shutil.copytree(CATALOG_DIR, backup)
    src = _build_fake_upstream(tmp_path)
    subprocess.run(
        [sys.executable, str(SYNC_SCRIPT), "--from", str(src)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )
    try:
        yield src
    finally:
        shutil.rmtree(CATALOG_DIR)
        shutil.copytree(backup, CATALOG_DIR)


def _run_query(*args: str, project_dir: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(QUERY_SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=project_dir or REPO_ROOT,
        check=False,
    )


def test_list_returns_all_entries(populated_catalog) -> None:
    result = _run_query("list")
    assert result.returncode == 0
    assert "ecc.agent.alpha" in result.stdout
    assert "ecc.agent.beta" in result.stdout
    assert "ecc.skill.gamma" in result.stdout


def test_list_filter_by_kind(populated_catalog) -> None:
    result = _run_query("list", "--kind", "agent")
    assert result.returncode == 0
    assert "ecc.agent.alpha" in result.stdout
    assert "ecc.skill.gamma" not in result.stdout


def test_list_filter_by_tag(populated_catalog) -> None:
    result = _run_query("list", "--tag", "kind:agent")
    assert result.returncode == 0
    assert "ecc.agent.alpha" in result.stdout


def test_list_json_output(populated_catalog) -> None:
    result = _run_query("--json", "list")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert any(e["id"] == "ecc.agent.alpha" for e in payload)


def test_show_existing_entry(populated_catalog) -> None:
    result = _run_query("show", "ecc.agent.alpha")
    assert result.returncode == 0
    assert "ecc.agent.alpha" in result.stdout
    assert "agent" in result.stdout


def test_show_unknown_entry_fails(populated_catalog) -> None:
    result = _run_query("show", "ecc.agent.no-such-thing")
    assert result.returncode == 1
    assert "no catalog entry" in result.stderr.lower()


def test_show_json_output(populated_catalog) -> None:
    result = _run_query("--json", "show", "ecc.agent.alpha")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["id"] == "ecc.agent.alpha"
    assert payload["kind"] == "agent"


def test_enable_writes_project_allowlist(populated_catalog, tmp_path: Path) -> None:
    project = tmp_path / "myproject"
    project.mkdir()
    result = _run_query(
        "enable", "ecc.agent.alpha", "--project-dir", str(project),
    )
    assert result.returncode == 0
    allowlist = json.loads(
        (project / "catalogs" / "workforce" / "enabled.json").read_text()
    )
    assert "ecc.agent.alpha" in allowlist["enabled"]


def test_enable_unknown_entry_fails(populated_catalog, tmp_path: Path) -> None:
    project = tmp_path / "myproject"
    project.mkdir()
    result = _run_query(
        "enable", "ecc.agent.nope", "--project-dir", str(project),
    )
    assert result.returncode == 1


def test_enable_idempotent(populated_catalog, tmp_path: Path) -> None:
    project = tmp_path / "myproject"
    project.mkdir()
    _run_query("enable", "ecc.agent.alpha", "--project-dir", str(project))
    result = _run_query("enable", "ecc.agent.alpha", "--project-dir", str(project))
    assert result.returncode == 0
    assert "already enabled" in result.stdout


def test_disable_moves_entry_from_enabled_to_declined(populated_catalog, tmp_path: Path) -> None:
    project = tmp_path / "myproject"
    project.mkdir()
    _run_query("enable", "ecc.agent.alpha", "--project-dir", str(project))
    _run_query("disable", "ecc.agent.alpha", "--project-dir", str(project))
    allowlist = json.loads(
        (project / "catalogs" / "workforce" / "enabled.json").read_text()
    )
    assert "ecc.agent.alpha" not in allowlist["enabled"]
    assert "ecc.agent.alpha" in allowlist["declined"]


def test_enabled_lists_project_allowlist(populated_catalog, tmp_path: Path) -> None:
    project = tmp_path / "myproject"
    project.mkdir()
    _run_query("enable", "ecc.agent.alpha", "--project-dir", str(project))
    _run_query("enable", "ecc.skill.gamma", "--project-dir", str(project))
    result = _run_query("enabled", "--project-dir", str(project))
    assert result.returncode == 0
    assert "ecc.agent.alpha" in result.stdout
    assert "ecc.skill.gamma" in result.stdout


def test_enabled_json_output(populated_catalog, tmp_path: Path) -> None:
    project = tmp_path / "myproject"
    project.mkdir()
    _run_query("enable", "ecc.agent.alpha", "--project-dir", str(project))
    result = _run_query("--json", "enabled", "--project-dir", str(project))
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "ecc.agent.alpha" in payload["enabled"]


def test_enabled_falls_back_to_repo_template_when_no_project_allowlist(populated_catalog, tmp_path: Path) -> None:
    """If a project has no allowlist file, enabled should report the empty default."""
    project = tmp_path / "myproject"
    project.mkdir()
    result = _run_query("enabled", "--project-dir", str(project))
    assert result.returncode == 0
    # The repo's template allowlist is empty by default.
    assert "No catalog entries" in result.stdout or result.stdout.strip() == ""
