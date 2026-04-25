"""Tests for skills/harness/SKILL.md and the install integration.

/harness is a slim wrapper around scripts/harness_install.py that lets
operators re-apply or add harness adapters to an existing project
without re-running install.sh globally.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "harness" / "SKILL.md"
INSTALL_SH = REPO_ROOT / "install.sh"


def _body() -> str:
    return SKILL_PATH.read_text()


# ── SKILL.md structural checks ──────────────────────────────────────────────


def test_skill_md_exists() -> None:
    assert SKILL_PATH.exists()


def test_skill_md_has_correct_frontmatter() -> None:
    body = _body()
    assert body.startswith("---\n")
    assert re.search(r"^name:\s*harness\s*$", body, re.MULTILINE)


def test_skill_md_documents_three_resolution_sources() -> None:
    """Args > beacon > default."""
    body = _body()
    # Skill arguments override beacon override default.
    assert "Skill arguments" in body
    assert ".workforce-harnesses" in body
    assert "Default" in body


def test_skill_md_references_harness_install_py() -> None:
    body = _body()
    assert "harness_install.py" in body


def test_skill_md_references_dry_run() -> None:
    body = _body()
    assert "--dry-run" in body or "dry-run" in body.lower()


def test_skill_md_documents_when_not_to_use() -> None:
    body = _body()
    assert "When NOT to" in body or "when not to" in body.lower()


def test_skill_md_idempotency_documented() -> None:
    """Re-running /harness must be safe — required for the 'switch
    profile, refresh adapters' use case."""
    body = _body()
    assert "idempotent" in body.lower() or "re-running" in body.lower() or "re-render" in body.lower()


def test_skill_md_beacon_update_is_opt_in() -> None:
    """Adding a harness via /harness must NOT silently rewrite the global
    beacon — that's a global-scope change for what looked like a
    project-scope command."""
    body = _body()
    assert "opt-in" in body.lower() or "(y/n)" in body or "confirmation" in body.lower()


def test_skill_md_handles_missing_foundation_path() -> None:
    body = _body()
    assert "foundation-path" in body
    # Edge case: install.sh wasn't run.
    assert "wasn't run" in body or "not been run" in body.lower() or "install.sh" in body


# ── Profile + install integration ───────────────────────────────────────────


def test_profile_schema_allows_harness_skill() -> None:
    schema = json.loads((REPO_ROOT / "profiles" / "schema.json").read_text())
    enum = schema["properties"]["skills"]["items"]["enum"]
    assert "harness" in enum


@pytest.mark.parametrize("profile", ["full", "foundation", "workforce"])
def test_profile_includes_harness_skill(profile: str) -> None:
    """full/foundation/workforce all carry /harness; minimal stays sync-only."""
    p = json.loads((REPO_ROOT / "profiles" / f"{profile}.json").read_text())
    assert "harness" in p["skills"], f"profile {profile} should include harness skill"


def test_minimal_profile_excludes_harness() -> None:
    """Minimal stays minimal — only /sync."""
    p = json.loads((REPO_ROOT / "profiles" / "minimal.json").read_text())
    assert "harness" not in p["skills"]
    assert p["skills"] == ["sync"]


def _run_install(home: Path, *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    return subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        capture_output=True, text=True, cwd=REPO_ROOT, env=env, check=False,
    )


def test_install_full_profile_links_harness_skill(tmp_path: Path) -> None:
    result = _run_install(tmp_path, "--profile", "full")
    assert result.returncode == 0, result.stderr or result.stdout
    assert (tmp_path / ".claude" / "skills" / "harness").is_symlink()


def test_install_legacy_both_includes_harness(tmp_path: Path) -> None:
    """Legacy default install gets /harness too (back-compat for existing users)."""
    result = _run_install(tmp_path)
    assert result.returncode == 0
    assert (tmp_path / ".claude" / "skills" / "harness").is_symlink()


def test_install_minimal_does_not_link_harness(tmp_path: Path) -> None:
    result = _run_install(tmp_path, "--profile", "minimal")
    assert result.returncode == 0
    assert not (tmp_path / ".claude" / "skills" / "harness").exists()


def test_install_status_line_lists_harness(tmp_path: Path) -> None:
    result = _run_install(tmp_path)
    assert result.returncode == 0
    assert "/harness" in result.stdout
