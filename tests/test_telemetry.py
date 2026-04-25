"""Tests for scripts/telemetry.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TELEMETRY_SCRIPT = REPO_ROOT / "scripts" / "telemetry.py"


def _run(project_dir: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(TELEMETRY_SCRIPT),
            "--project-dir",
            str(project_dir),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=True,
    )


def test_no_op_when_memory_dir_absent(tmp_path: Path) -> None:
    """telemetry must silently do nothing if the project hasn't opted in."""
    result = _run(
        tmp_path,
        "--agent",
        "backend-developer",
        "--event",
        "task-start",
        "--task",
        "REQ-F-001",
    )
    assert result.returncode == 0
    assert not (tmp_path / ".foundation-memory").exists()
    assert result.stdout == ""


def test_appends_jsonl_when_memory_dir_present(tmp_path: Path) -> None:
    mem = tmp_path / ".foundation-memory"
    mem.mkdir()

    _run(
        tmp_path,
        "--agent",
        "backend-developer",
        "--event",
        "task-complete",
        "--task",
        "Build /users",
        "--duration-sec",
        "12.5",
        "--note",
        "all green",
    )

    log = mem / "telemetry.jsonl"
    assert log.exists()
    record = json.loads(log.read_text().strip())
    assert record["agent"] == "backend-developer"
    assert record["event"] == "task-complete"
    assert record["task"] == "Build /users"
    assert record["duration_sec"] == 12.5
    assert record["note"] == "all green"
    assert "ts" in record


def test_records_append_one_per_line(tmp_path: Path) -> None:
    mem = tmp_path / ".foundation-memory"
    mem.mkdir()

    for i in range(3):
        _run(
            tmp_path,
            "--agent",
            "test-writer",
            "--event",
            "task-start",
            "--task",
            f"task-{i}",
        )

    lines = (mem / "telemetry.jsonl").read_text().splitlines()
    assert len(lines) == 3
    for line in lines:
        json.loads(line)  # each line must be valid JSON


def test_invalid_event_rejected(tmp_path: Path) -> None:
    mem = tmp_path / ".foundation-memory"
    mem.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            str(TELEMETRY_SCRIPT),
            "--project-dir",
            str(tmp_path),
            "--agent",
            "x",
            "--event",
            "nope",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
