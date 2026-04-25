"""Tests for skills/security/SKILL.md and the install integration.

/security is the security-focused sibling of /perf: spawn one engineer
(security-analyst), surface its findings, exit. No orchestration spine.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "security" / "SKILL.md"
INSTALL_SH = REPO_ROOT / "install.sh"


def _body() -> str:
    return SKILL_PATH.read_text()


# ── SKILL.md structural checks ──────────────────────────────────────────────


def test_skill_md_exists() -> None:
    assert SKILL_PATH.exists()


def test_skill_md_has_correct_frontmatter() -> None:
    body = _body()
    assert body.startswith("---\n")
    assert re.search(r"^name:\s*security\s*$", body, re.MULTILINE)


def test_skill_md_triggers_on_security_phrases() -> None:
    body = _body()
    for trigger in ["/security", "threat model", "OWASP", "auth review"]:
        assert trigger in body, f"SKILL.md missing trigger phrase: {trigger}"


def test_skill_md_only_spawns_security_analyst() -> None:
    body = _body()
    assert "security-analyst" in body
    assert "only security-analyst" in body.lower() or "Spawn only" in body


def test_skill_md_documents_when_not_to_use() -> None:
    body = _body()
    assert "When NOT to trigger" in body or "when not to trigger" in body.lower()


def test_skill_md_writes_no_files_directly() -> None:
    body = _body()
    rules = body[body.index("## Rules"):]
    assert "Never write" in rules and "security-model.md" in rules


def test_skill_md_handles_missing_context() -> None:
    body = _body()
    # security-analyst needs at least spec.md OR architecture.md OR src/.
    for needed in ["spec.md", "architecture.md"]:
        assert needed in body
    # Greenfield redirect to /foundation.
    assert "/foundation" in body


def test_skill_md_redirects_fix_requests_to_workforce() -> None:
    body = _body()
    assert "Never recommend a specific code-side fix" in body or "fixing is a different agent" in body
    # /workforce + backend-developer + code-reviewer is the recommended path.
    assert "/workforce" in body


def test_skill_md_warns_against_softening_critical() -> None:
    """Anti-pattern: rounding CRITICAL down because the fix is expensive."""
    body = _body()
    assert "CRITICAL" in body
    # Must explicitly forbid rounding down.
    assert "Never round CRITICAL" in body or "round CRITICAL down" in body.lower()


# ── Profile + install integration ──────────────────────────────────────────


def test_profile_schema_allows_security_skill() -> None:
    schema = json.loads((REPO_ROOT / "profiles" / "schema.json").read_text())
    enum = schema["properties"]["skills"]["items"]["enum"]
    assert "security" in enum


@pytest.mark.parametrize("profile", ["full", "foundation", "workforce"])
def test_profile_includes_security_skill(profile: str) -> None:
    p = json.loads((REPO_ROOT / "profiles" / f"{profile}.json").read_text())
    assert "security" in p["skills"], f"profile {profile} should include security skill"


def test_minimal_profile_excludes_security() -> None:
    p = json.loads((REPO_ROOT / "profiles" / "minimal.json").read_text())
    assert "security" not in p["skills"]
    assert p["skills"] == ["sync"]


def _run_install(home: Path, *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    return subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        capture_output=True, text=True, cwd=REPO_ROOT, env=env, check=False,
    )


def test_install_full_profile_links_security_skill(tmp_path: Path) -> None:
    result = _run_install(tmp_path, "--profile", "full")
    assert result.returncode == 0, result.stderr or result.stdout
    assert (tmp_path / ".claude" / "skills" / "security").is_symlink()


def test_install_legacy_both_includes_security(tmp_path: Path) -> None:
    result = _run_install(tmp_path)
    assert result.returncode == 0
    assert (tmp_path / ".claude" / "skills" / "security").is_symlink()


def test_install_minimal_does_not_link_security(tmp_path: Path) -> None:
    result = _run_install(tmp_path, "--profile", "minimal")
    assert result.returncode == 0
    assert not (tmp_path / ".claude" / "skills" / "security").exists()


def test_install_status_line_lists_security(tmp_path: Path) -> None:
    result = _run_install(tmp_path)
    assert result.returncode == 0
    assert "/security" in result.stdout
