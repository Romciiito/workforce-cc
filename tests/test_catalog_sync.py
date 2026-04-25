"""Tests for scripts/catalog_sync.py."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "catalog_sync.py"
CATALOG_DIR = REPO_ROOT / "catalogs" / "ecc"


def _build_fake_upstream(tmp_path: Path) -> Path:
    """Build a minimal fake everything-claude-code clone with 1 agent + 1 skill + 1 command."""
    src = tmp_path / "fake-ecc"
    (src / "agents").mkdir(parents=True)
    (src / "skills").mkdir(parents=True)
    (src / "commands").mkdir(parents=True)

    (src / "agents" / "test-reviewer.md").write_text(
        '---\n'
        'name: test-reviewer\n'
        'description: A reviewer that finds bugs.\n'
        'tools: Read, Write\n'
        '---\n\n'
        '# Reviewer\n'
    )
    (src / "skills" / "demo-skill.md").write_text(
        '---\n'
        'name: demo-skill\n'
        'description: A demo skill.\n'
        '---\n\n'
        '# Demo\n'
    )
    (src / "commands" / "do-thing.md").write_text(
        '---\n'
        'name: do-thing\n'
        'description: A command.\n'
        '---\n\n'
        '# Do thing\n'
    )
    return src


def _run_sync(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )


@pytest.fixture
def isolated_catalog(tmp_path: Path):
    """Snapshot + restore catalogs/ecc/ around the test."""
    backup = tmp_path / "backup"
    shutil.copytree(CATALOG_DIR, backup)
    try:
        yield
    finally:
        shutil.rmtree(CATALOG_DIR)
        shutil.copytree(backup, CATALOG_DIR)


def test_dry_run_does_not_modify_catalog(tmp_path: Path, isolated_catalog) -> None:
    src = _build_fake_upstream(tmp_path)
    before_index = (CATALOG_DIR / "index.json").read_text()
    before_bodies = sorted(p.name for p in (CATALOG_DIR / "bodies").rglob("*"))

    result = _run_sync("--from", str(src), "--dry-run")
    assert result.returncode == 0, result.stderr

    after_index = (CATALOG_DIR / "index.json").read_text()
    after_bodies = sorted(p.name for p in (CATALOG_DIR / "bodies").rglob("*"))
    assert before_index == after_index
    assert before_bodies == after_bodies


def test_sync_writes_index_and_bodies(tmp_path: Path, isolated_catalog) -> None:
    src = _build_fake_upstream(tmp_path)
    result = _run_sync("--from", str(src))
    assert result.returncode == 0, result.stderr

    index = json.loads((CATALOG_DIR / "index.json").read_text())
    assert index["source"]["repo"] == "affaan-m/everything-claude-code"
    assert index["source"]["license"] == "MIT"
    assert len(index["entries"]) == 3

    by_kind = {e["kind"] for e in index["entries"]}
    assert by_kind == {"agent", "skill", "command"}

    for entry in index["entries"]:
        body = CATALOG_DIR / entry["source_path"]
        assert body.exists(), f"missing body: {entry['source_path']}"
        assert entry["upstream_sha"]
        assert f"kind:{entry['kind']}" in entry["tags"]
        assert "source:ecc" in entry["tags"]


def test_sync_only_specified_kinds(tmp_path: Path, isolated_catalog) -> None:
    src = _build_fake_upstream(tmp_path)
    result = _run_sync("--from", str(src), "--kinds", "agent")
    assert result.returncode == 0

    index = json.loads((CATALOG_DIR / "index.json").read_text())
    kinds = {e["kind"] for e in index["entries"]}
    assert kinds == {"agent"}


def test_sync_rejects_missing_source(tmp_path: Path) -> None:
    result = _run_sync("--from", str(tmp_path / "does-not-exist"))
    assert result.returncode != 0
    assert "not a directory" in result.stderr


def test_entry_id_format_is_stable(tmp_path: Path, isolated_catalog) -> None:
    src = _build_fake_upstream(tmp_path)
    result = _run_sync("--from", str(src))
    assert result.returncode == 0

    index = json.loads((CATALOG_DIR / "index.json").read_text())
    ids = sorted(e["id"] for e in index["entries"])
    assert ids == sorted([
        "ecc.agent.test-reviewer",
        "ecc.command.do-thing",
        "ecc.skill.demo-skill",
    ])


def test_overrides_preserved_across_sync(tmp_path: Path, isolated_catalog) -> None:
    """Custom tags / stacks declared in _overrides.json must survive sync."""
    src = _build_fake_upstream(tmp_path)
    overrides = {
        "ecc.agent.test-reviewer": {
            "tags": ["domain:security", "owner:trung"],
            "stacks": ["python-fastapi"],
        }
    }
    (CATALOG_DIR / "_overrides.json").write_text(json.dumps(overrides))

    result = _run_sync("--from", str(src))
    assert result.returncode == 0

    index = json.loads((CATALOG_DIR / "index.json").read_text())
    entry = next(e for e in index["entries"] if e["id"] == "ecc.agent.test-reviewer")
    assert "domain:security" in entry["tags"]
    assert "owner:trung" in entry["tags"]
    assert entry["stacks"] == ["python-fastapi"]
    # Auto-tags survive too.
    assert "kind:agent" in entry["tags"]
    assert "source:ecc" in entry["tags"]


def test_seed_index_matches_schema_keys() -> None:
    """The seed index.json (committed in this PR) must have the correct top-level keys."""
    seed = json.loads((CATALOG_DIR / "index.json").read_text())
    assert "source" in seed
    assert "entries" in seed
    assert "repo" in seed["source"]
    assert "license" in seed["source"]
