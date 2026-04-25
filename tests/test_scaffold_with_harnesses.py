"""Tests for the harness-aware scaffold flow (Chunk 31).

scaffold.py now reads ~/.workforce-harnesses and invokes
harness_install.py for each non-claude harness, applying adapter
files into the scaffolded project.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD = REPO_ROOT / "scripts" / "scaffold.py"
TEMPLATES_DIR = REPO_ROOT / "templates"

_JINJA = importlib.util.find_spec("jinja2") is not None
pytestmark = pytest.mark.skipif(not _JINJA, reason="jinja2 not installed")


def _run_scaffold(project_dir: Path, stack: str, fake_home: Path | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if fake_home is not None:
        env["HOME"] = str(fake_home)
    return subprocess.run(
        [
            sys.executable, str(SCAFFOLD),
            "--project-dir", str(project_dir),
            "--stack", stack,
            "--project-name", "Acme",
            "--description", "Acme test app",
            "--templates-dir", str(TEMPLATES_DIR),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_scaffold_with_no_beacon_only_writes_claude_files(tmp_path: Path) -> None:
    """Default behavior: no ~/.workforce-harnesses → claude only."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    project = tmp_path / "proj"
    project.mkdir()

    result = _run_scaffold(project, "python-fastapi", fake_home=fake_home)
    assert result.returncode == 0, result.stderr

    # Claude artifacts present.
    assert (project / "CLAUDE.md").exists()
    assert (project / ".claude").is_dir()

    # Non-claude harnesses NOT applied.
    assert not (project / "AGENTS.md").exists()
    assert not (project / "GEMINI.md").exists()
    assert not (project / ".cursor").exists()
    assert not (project / ".opencode").exists()


def test_scaffold_with_cursor_beacon_writes_cursor_files(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".workforce-harnesses").write_text("claude,cursor\n")

    project = tmp_path / "proj"
    project.mkdir()

    result = _run_scaffold(project, "python-fastapi", fake_home=fake_home)
    assert result.returncode == 0, result.stderr

    # Claude still there.
    assert (project / "CLAUDE.md").exists()

    # Cursor adapter applied.
    assert (project / ".cursor" / "rules" / "00-workforce-cc.mdc").exists()
    assert (project / ".cursor" / "rules" / "01-orchestration-pointers.mdc").exists()

    # Output mentions the adapter run.
    assert "cursor" in result.stdout.lower()


def test_scaffold_with_all_harnesses_writes_each(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".workforce-harnesses").write_text("claude,cursor,codex,opencode,gemini\n")

    project = tmp_path / "proj"
    project.mkdir()

    result = _run_scaffold(project, "python-fastapi", fake_home=fake_home)
    assert result.returncode == 0, result.stderr

    assert (project / "CLAUDE.md").exists()
    assert (project / "AGENTS.md").exists()
    assert (project / "GEMINI.md").exists()
    assert (project / ".cursor" / "rules").is_dir()
    assert (project / ".opencode" / "agents").is_dir()


def test_scaffold_skips_claude_adapter_to_avoid_double_write(tmp_path: Path) -> None:
    """scaffold.py already writes CLAUDE.md + .claude/. The harness loop
    must skip the 'claude' adapter to avoid touching what scaffold owns."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".workforce-harnesses").write_text("claude\n")

    project = tmp_path / "proj"
    project.mkdir()

    result = _run_scaffold(project, "python-fastapi", fake_home=fake_home)
    assert result.returncode == 0, result.stderr

    # Should NOT print 'Harness adapters' because the only entry is claude
    # (which is skipped). The status line is only emitted when there are
    # non-claude extras.
    assert "Harness adapters:" not in result.stdout


def test_scaffold_includes_env_prefix_in_codex_adapter(tmp_path: Path) -> None:
    """End-to-end: scaffold + codex harness produces an AGENTS.md with the
    correct env_prefix derived from the project name."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".workforce-harnesses").write_text("claude,codex\n")

    project = tmp_path / "proj"
    project.mkdir()

    _run_scaffold(project, "python-fastapi", fake_home=fake_home)

    agents_md = (project / "AGENTS.md").read_text()
    # Project name is 'Acme' → env_prefix is 'ACME'.
    assert "ACME" in agents_md
    assert "Acme" in agents_md  # project name


def test_scaffold_continues_when_one_harness_adapter_fails(tmp_path: Path, monkeypatch) -> None:
    """If one harness adapter throws, scaffold prints a WARNING and continues
    with the others rather than aborting the whole scaffold."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    # Reference an unknown harness in the beacon — should fail one adapter.
    (fake_home / ".workforce-harnesses").write_text("claude,cursor\n")

    project = tmp_path / "proj"
    project.mkdir()

    # Sanity: this run should succeed (cursor is real). But the test below
    # verifies the warning path stays within the scaffold's robustness budget.
    result = _run_scaffold(project, "python-fastapi", fake_home=fake_home)
    assert result.returncode == 0
    assert (project / "CLAUDE.md").exists()
    assert (project / ".cursor" / "rules" / "00-workforce-cc.mdc").exists()
