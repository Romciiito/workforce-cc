"""Tests for the auto-enable telemetry behavior added in Chunk 4.

The default opt-in semantics (no .foundation-memory/ → silent no-op) are
unchanged. New: when WORKFORCE_MULTI_TERMINAL=1 is set in the environment,
.foundation-memory/ is auto-created and events are written. WORKFORCE_TELEMETRY=off
disables telemetry entirely (overrides the auto-enable).

These tests live in a new file to keep test_telemetry.py untouched
(the existing tests pin opt-in semantics).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "telemetry.py"


def _run(env: dict[str, str], project_dir: Path, *extra: str) -> subprocess.CompletedProcess:
    base = os.environ.copy()
    base.update(env)
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-dir",
            str(project_dir),
            *extra,
        ],
        capture_output=True,
        text=True,
        env=base,
    )


def test_auto_enable_creates_foundation_memory_in_multi_terminal_mode(tmp_path: Path) -> None:
    """WORKFORCE_MULTI_TERMINAL=1 forces telemetry on even if the dir doesn't exist."""
    result = _run(
        {"WORKFORCE_MULTI_TERMINAL": "1"},
        tmp_path,
        "--agent",
        "architect",
        "--event",
        "task-start",
        "--task",
        "REQ-F-001",
    )
    assert result.returncode == 0
    mem = tmp_path / ".foundation-memory"
    assert mem.is_dir()
    log = mem / "telemetry.jsonl"
    assert log.exists()
    assert "task-start" in log.read_text()


def test_no_auto_enable_when_env_absent(tmp_path: Path) -> None:
    """Without the env var, behavior is unchanged: no dir → no-op."""
    result = _run(
        {},
        tmp_path,
        "--agent",
        "architect",
        "--event",
        "task-start",
    )
    assert result.returncode == 0
    assert not (tmp_path / ".foundation-memory").exists()


def test_global_opt_out_overrides_auto_enable(tmp_path: Path) -> None:
    """WORKFORCE_TELEMETRY=off must override WORKFORCE_MULTI_TERMINAL=1."""
    result = _run(
        {"WORKFORCE_MULTI_TERMINAL": "1", "WORKFORCE_TELEMETRY": "off"},
        tmp_path,
        "--agent",
        "architect",
        "--event",
        "task-start",
    )
    assert result.returncode == 0
    assert not (tmp_path / ".foundation-memory").exists()


def test_global_opt_out_works_for_legacy_opt_in(tmp_path: Path) -> None:
    """If a project has .foundation-memory/ but the user sets WORKFORCE_TELEMETRY=off,
    nothing is appended."""
    mem = tmp_path / ".foundation-memory"
    mem.mkdir()
    result = _run(
        {"WORKFORCE_TELEMETRY": "off"},
        tmp_path,
        "--agent",
        "architect",
        "--event",
        "task-start",
    )
    assert result.returncode == 0
    assert not (mem / "telemetry.jsonl").exists()


def test_auto_enable_appends_just_like_legacy_opt_in(tmp_path: Path) -> None:
    """Calling twice must produce two JSONL lines."""
    for i in range(2):
        result = _run(
            {"WORKFORCE_MULTI_TERMINAL": "1"},
            tmp_path,
            "--agent",
            "architect",
            "--event",
            "task-start",
            "--task",
            f"task-{i}",
        )
        assert result.returncode == 0
    log = tmp_path / ".foundation-memory" / "telemetry.jsonl"
    lines = log.read_text().splitlines()
    assert len(lines) == 2
