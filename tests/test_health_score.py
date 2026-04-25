"""Tests for scripts/health_score.py.

Most asserts target the scoring logic (max bounds, status strings) rather
than exact integers, so future tweaks to score weights don't break the
suite — but each test pins enough to catch a real regression.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HEALTH_SCRIPT = REPO_ROOT / "scripts" / "health_score.py"


def _load_health_module():
    name = "health_score"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, HEALTH_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _run_health(project_dir: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(HEALTH_SCRIPT), "--project-dir", str(project_dir), "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_empty_dir_returns_low_scores(tmp_path: Path) -> None:
    out = _run_health(tmp_path)
    assert out["max"] == 50
    # Each dimension has a documented floor; total stays bounded.
    assert 0 < out["total"] < 20
    assert out["vision_status"] == "vision.md missing"
    assert out["docs_status"].startswith("0/7 docs present")
    assert out["security_status"] == "security-model.md missing"
    assert out["agents_status"] == ".claude/agents/ missing"
    assert out["workplan_status"] == "workplan.md missing"


def test_full_docs_lift_doc_score(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("# CLAUDE\n")
    (tmp_path / "vision.md").write_text(
        "# Vision\n\n## Non-negotiables\nx\n\n## Out of scope\ny\n"
    )
    (tmp_path / "security-model.md").write_text(
        "# Security\n- [x] item one\n- [x] item two\n"
    )
    docs = tmp_path / "docs" / "claude"
    docs.mkdir(parents=True)
    for name in ["architecture.md", "development.md", "design-decisions.md", "env-vars.md"]:
        (docs / name).write_text(f"# {name}\n")

    out = _run_health(tmp_path)
    assert out["docs"] >= 8, out["docs_status"]
    assert "7/7" in out["docs_status"]
    assert out["security"] == 10  # all items checked
    assert out["vision"] == 9  # both required sections present


def test_partial_security_checklist_returns_proportional_score(tmp_path: Path) -> None:
    (tmp_path / "security-model.md").write_text(
        "- [x] one\n- [x] two\n- [ ] three\n- [ ] four\n"
    )
    out = _run_health(tmp_path)
    # 2/4 checked → ~5/10 with floor of 3
    assert 3 <= out["security"] <= 6
    assert "2/4 Phase 0 items checked" in out["security_status"]


def test_agents_dir_present_lifts_agent_score(tmp_path: Path) -> None:
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    expected = [
        "backend-developer.md",
        "frontend-developer.md",
        "devops-engineer.md",
        "test-writer.md",
        "code-reviewer.md",
        "debugger.md",
    ]
    for name in expected:
        (agents / name).write_text("real content, no placeholders")

    out = _run_health(tmp_path)
    assert out["agents"] == 10
    assert "6/6 agents" in out["agents_status"]


def test_generic_unrendered_agents_dock_the_score(tmp_path: Path) -> None:
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "backend-developer.md").write_text("hello {{ project_name }}")
    (agents / "frontend-developer.md").write_text("legit content")

    out = _run_health(tmp_path)
    assert "1 generic" in out["agents_status"]
    assert out["agents"] < 10


def test_count_feature_commits_is_zero_outside_git(tmp_path: Path) -> None:
    """A non-git project should not crash and should count zero stale commits."""
    (tmp_path / "vision.md").write_text("# v\n## Non-negotiables\n## Out of scope\n")
    out = _run_health(tmp_path)
    assert out["vision"] >= 7
    # Specifically: no stale flag.
    assert "feature commits" not in out["vision_status"]


def test_run_git_returns_empty_when_git_missing(monkeypatch, tmp_path: Path) -> None:
    """If git itself isn't on PATH, helpers should degrade gracefully."""
    health = _load_health_module()

    def _explode(*_a, **_kw):
        raise FileNotFoundError("git")

    monkeypatch.setattr(health.subprocess, "run", _explode)
    assert health.run_git(["log"], tmp_path) == ""
    assert health.count_feature_commits_since(tmp_path / "vision.md", tmp_path) == 0


def test_count_feature_commits_rejects_garbage_hash(monkeypatch, tmp_path: Path) -> None:
    """Defense-in-depth: a bogus 'hash' must not be passed back into git."""
    health = _load_health_module()
    calls: list[list[str]] = []

    def fake_run_git(args, cwd):
        calls.append(args)
        # First call asks for the last commit hash — return something nasty.
        if args[0] == "log" and "-1" in args:
            return "--oops; rm -rf /"
        return ""

    monkeypatch.setattr(health, "run_git", fake_run_git)
    result = health.count_feature_commits_since(tmp_path / "x.md", tmp_path)
    assert result == 0
    # We must not have made the second log call with the bad value.
    assert len(calls) == 1
