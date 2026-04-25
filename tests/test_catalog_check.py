"""Tests for scripts/catalog_check.py."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SYNC_SCRIPT = REPO_ROOT / "scripts" / "catalog_sync.py"
CHECK_SCRIPT = REPO_ROOT / "scripts" / "catalog_check.py"
CATALOG_DIR = REPO_ROOT / "catalogs" / "ecc"


def _build_fake_upstream(tmp_path: Path) -> Path:
    src = tmp_path / "fake-ecc"
    (src / "agents").mkdir(parents=True)
    (src / "agents" / "alpha.md").write_text(
        '---\nname: alpha\ndescription: Alpha agent.\n---\n\n# Alpha\n'
    )
    (src / "agents" / "beta.md").write_text(
        '---\nname: beta\ndescription: Beta agent.\n---\n\n# Beta\n'
    )
    return src


def _run_check(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )


@pytest.fixture
def populated_catalog(tmp_path: Path):
    backup = tmp_path / "backup"
    shutil.copytree(CATALOG_DIR, backup)
    src = _build_fake_upstream(tmp_path)
    sync = subprocess.run(
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


def test_validate_seed_index_passes() -> None:
    """The empty seed index that ships in this PR must pass validation."""
    result = _run_check("validate")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VALIDATE OK" in result.stdout


def test_validate_after_sync_passes(populated_catalog) -> None:
    result = _run_check("validate")
    assert result.returncode == 0, result.stdout + result.stderr


def test_validate_detects_orphan_body(populated_catalog) -> None:
    """A body file with no matching index entry must be flagged."""
    orphan = CATALOG_DIR / "bodies" / "agent" / "ecc.agent.orphan.md"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_text("# orphan\n")

    result = _run_check("validate")
    assert result.returncode != 0
    assert "orphan body" in result.stdout


def test_validate_detects_missing_body(populated_catalog) -> None:
    """An index entry with no body file on disk must be flagged."""
    index = json.loads((CATALOG_DIR / "index.json").read_text())
    index["entries"][0]["source_path"] = "bodies/agent/missing.md"
    (CATALOG_DIR / "index.json").write_text(json.dumps(index, indent=2))

    result = _run_check("validate")
    assert result.returncode != 0
    assert "body file missing" in result.stdout


def test_validate_detects_duplicate_id(populated_catalog) -> None:
    index = json.loads((CATALOG_DIR / "index.json").read_text())
    index["entries"][0]["id"] = index["entries"][1]["id"]
    (CATALOG_DIR / "index.json").write_text(json.dumps(index, indent=2))

    result = _run_check("validate")
    assert result.returncode != 0
    assert "duplicate id" in result.stdout


def test_validate_json_output(populated_catalog) -> None:
    result = _run_check("--json", "validate")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["catalog"] == "ecc"
    assert payload["ok"] is True
    assert payload["failures"] == []


def test_drift_no_changes(tmp_path: Path, populated_catalog) -> None:
    """If upstream hasn't changed, drift returns 0."""
    src = populated_catalog
    result = _run_check("drift", "--from", str(src))
    assert result.returncode == 0, result.stdout
    assert "DRIFT OK" in result.stdout


def test_drift_detects_changed_upstream(tmp_path: Path, populated_catalog) -> None:
    src = populated_catalog
    upstream_file = src / "agents" / "alpha.md"
    upstream_file.write_text(upstream_file.read_text() + "\n# UPDATED\n")

    result = _run_check("drift", "--from", str(src))
    assert result.returncode != 0
    assert "DRIFT in catalog" in result.stdout
    assert "ecc.agent.alpha" in result.stdout


def test_drift_detects_missing_upstream(tmp_path: Path, populated_catalog) -> None:
    src = populated_catalog
    (src / "agents" / "alpha.md").unlink()

    result = _run_check("drift", "--from", str(src))
    assert result.returncode != 0
    assert "MISSING upstream" in result.stdout


def test_drift_json_output(populated_catalog) -> None:
    src = populated_catalog
    upstream_file = src / "agents" / "beta.md"
    upstream_file.write_text(upstream_file.read_text() + "\n# UPDATED\n")

    result = _run_check("--json", "drift", "--from", str(src))
    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["catalog"] == "ecc"
    assert any(d["id"] == "ecc.agent.beta" for d in payload["drifted"])
