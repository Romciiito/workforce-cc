"""Tests for skills/perf/SKILL.md and the install integration.

/perf is the lightweight equivalent of /sync for performance: spawns
only the performance-analyst engineer, surfaces top findings, exits.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "perf" / "SKILL.md"
INSTALL_SH = REPO_ROOT / "install.sh"


def _body() -> str:
    return SKILL_PATH.read_text()


# ── SKILL.md structural checks ──────────────────────────────────────────────


def test_skill_md_exists() -> None:
    assert SKILL_PATH.exists()


def test_skill_md_has_frontmatter() -> None:
    body = _body()
    assert body.startswith("---\n")
    # name: perf
    assert re.search(r"^name:\s*perf\s*$", body, re.MULTILINE)


def test_skill_md_triggers_on_perf_phrases() -> None:
    body = _body()
    for trigger in ["/perf", "perf check", "why is this slow", "pre-launch"]:
        assert trigger in body, f"SKILL.md missing trigger phrase: {trigger}"


def test_skill_md_only_spawns_performance_analyst() -> None:
    body = _body()
    assert "performance-analyst" in body
    # The discipline: no orchestration spine, no other engineers.
    assert "only performance-analyst" in body.lower() or "spawn only" in body.lower()


def test_skill_md_documents_when_not_to_use() -> None:
    body = _body()
    # Without this section, operators reach for /perf in every situation.
    assert "When NOT to trigger" in body or "when not to" in body.lower()


def test_skill_md_writes_no_files_directly() -> None:
    body = _body()
    rules = body[body.index("## Rules"):]
    assert "Never write performance-model.md yourself" in rules
    # Must explicitly forbid spawning other agents.
    assert "Spawn only performance-analyst" in rules or "no alignment-guard" in rules


def test_skill_md_handles_missing_architecture() -> None:
    body = _body()
    assert "architecture.md" in body
    # Edge case: greenfield project — must redirect to /foundation.
    assert "/foundation" in body


def test_skill_md_redirects_fix_requests_to_workforce() -> None:
    body = _body()
    # /perf is diagnosis-only; fixes need /workforce or debugger.
    assert "Never recommend a specific code change" in body or "fixing is a different agent" in body


# ── Profile integration ─────────────────────────────────────────────────────


def test_profiles_full_includes_perf() -> None:
    full = json.loads((REPO_ROOT / "profiles" / "full.json").read_text())
    assert "perf" in full["skills"]


def test_profiles_workforce_includes_perf() -> None:
    """workforce profile gets /perf because audit users often want it."""
    wf = json.loads((REPO_ROOT / "profiles" / "workforce.json").read_text())
    assert "perf" in wf["skills"]


def test_profiles_minimal_excludes_perf() -> None:
    """minimal profile must stay minimal — only /sync."""
    mini = json.loads((REPO_ROOT / "profiles" / "minimal.json").read_text())
    assert mini["skills"] == ["sync"]
    assert "perf" not in mini["skills"]


def test_schema_allows_perf_skill() -> None:
    schema = json.loads((REPO_ROOT / "profiles" / "schema.json").read_text())
    enum = schema["properties"]["skills"]["items"]["enum"]
    assert "perf" in enum


# ── install.sh integration ──────────────────────────────────────────────────


def _run_install(home: Path, *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    return subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        check=False,
    )


def test_install_full_profile_links_perf_skill(tmp_path: Path) -> None:
    result = _run_install(tmp_path, "--profile", "full")
    assert result.returncode == 0, result.stderr or result.stdout
    perf_link = tmp_path / ".claude" / "skills" / "perf"
    assert perf_link.is_symlink()


def test_install_legacy_both_includes_perf(tmp_path: Path) -> None:
    """The legacy default (--only both) must also pick up /perf so existing
    users get the new skill on next install."""
    result = _run_install(tmp_path)  # default == both
    assert result.returncode == 0
    perf_link = tmp_path / ".claude" / "skills" / "perf"
    assert perf_link.is_symlink()


def test_install_minimal_does_not_link_perf(tmp_path: Path) -> None:
    result = _run_install(tmp_path, "--profile", "minimal")
    assert result.returncode == 0
    perf_link = tmp_path / ".claude" / "skills" / "perf"
    assert not perf_link.exists()
