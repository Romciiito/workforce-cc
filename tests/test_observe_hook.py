"""Tests for hooks/observe.sh — the post-tool-use observation hook.

Same env-var contract as governance.sh and scripts/telemetry.py:
WORKFORCE_TELEMETRY=off → no-op, WORKFORCE_MULTI_TERMINAL=1 → auto-enable.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "hooks" / "observe.sh"
DISPATCHER = REPO_ROOT / "hooks" / "dispatcher.sh"


def _run(env: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    base = os.environ.copy()
    base.update(env)
    return subprocess.run(
        ["bash", str(HOOK), *args],
        capture_output=True,
        text=True,
        env=base,
    )


def test_no_op_when_memory_dir_absent_and_no_multi_terminal(tmp_path: Path) -> None:
    """Without .foundation-memory/ and without WORKFORCE_MULTI_TERMINAL=1,
    the hook must silently do nothing."""
    project = tmp_path / "project"
    project.mkdir()
    result = _run(
        {"WORKFORCE_PROJECT_DIR": str(project)},
        "Bash", "success", "git status",
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert not (project / ".foundation-memory").exists()


def test_auto_enables_under_multi_terminal(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    result = _run(
        {
            "WORKFORCE_PROJECT_DIR": str(project),
            "WORKFORCE_MULTI_TERMINAL": "1",
        },
        "Bash", "success", "git status",
    )
    assert result.returncode == 0
    log = project / ".foundation-memory" / "observations.jsonl"
    assert log.exists()
    record = json.loads(log.read_text().strip())
    assert record["tool"] == "Bash"
    assert record["result"] == "success"
    assert "git status" in record["details"]


def test_writes_when_memory_dir_pre_exists(tmp_path: Path) -> None:
    project = tmp_path / "project"
    mem = project / ".foundation-memory"
    mem.mkdir(parents=True)
    result = _run(
        {"WORKFORCE_PROJECT_DIR": str(project)},
        "Edit", "success", "scripts/scaffold.py:23",
    )
    assert result.returncode == 0
    log = mem / "observations.jsonl"
    assert log.exists()
    record = json.loads(log.read_text().strip())
    assert record["tool"] == "Edit"
    assert "scaffold.py" in record["details"]


def test_global_opt_out_overrides_multi_terminal(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    result = _run(
        {
            "WORKFORCE_PROJECT_DIR": str(project),
            "WORKFORCE_MULTI_TERMINAL": "1",
            "WORKFORCE_TELEMETRY": "off",
        },
        "Bash", "success", "anything",
    )
    assert result.returncode == 0
    assert not (project / ".foundation-memory").exists()


def test_records_failed_calls(tmp_path: Path) -> None:
    project = tmp_path / "project"
    mem = project / ".foundation-memory"
    mem.mkdir(parents=True)
    _run(
        {"WORKFORCE_PROJECT_DIR": str(project)},
        "Bash", "failed", "git push to archived repo",
    )
    record = json.loads((mem / "observations.jsonl").read_text().strip())
    assert record["result"] == "failed"


def test_records_engineer_when_env_var_set(tmp_path: Path) -> None:
    project = tmp_path / "project"
    mem = project / ".foundation-memory"
    mem.mkdir(parents=True)
    _run(
        {
            "WORKFORCE_PROJECT_DIR": str(project),
            "WORKFORCE_ENGINEER": "architect",
            "WORKFORCE_RUN_ID": ".workforce/runs/2026-04-25T17-00-00Z",
        },
        "Read", "success", "spec.md",
    )
    record = json.loads((mem / "observations.jsonl").read_text().strip())
    assert record["engineer"] == "architect"
    assert record["run_id"] == ".workforce/runs/2026-04-25T17-00-00Z"


def test_appends_one_line_per_call(tmp_path: Path) -> None:
    project = tmp_path / "project"
    mem = project / ".foundation-memory"
    mem.mkdir(parents=True)
    for i in range(3):
        _run(
            {"WORKFORCE_PROJECT_DIR": str(project)},
            "Bash", "success", f"call-{i}",
        )
    lines = (mem / "observations.jsonl").read_text().splitlines()
    assert len(lines) == 3
    for line in lines:
        json.loads(line)  # each line valid JSON


def test_details_truncated_at_280_chars(tmp_path: Path) -> None:
    project = tmp_path / "project"
    mem = project / ".foundation-memory"
    mem.mkdir(parents=True)
    long_details = "x" * 1000
    _run(
        {"WORKFORCE_PROJECT_DIR": str(project)},
        "Bash", "success", long_details,
    )
    record = json.loads((mem / "observations.jsonl").read_text().strip())
    assert len(record["details"]) <= 280


def test_full_profile_lists_observe_in_dispatcher(tmp_path: Path) -> None:
    """The dispatcher's `list` subcommand must include observe under full profile."""
    (tmp_path / ".workforce-profile").write_text("full\n")
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    result = subprocess.run(
        ["bash", str(DISPATCHER), "list"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "observe" in result.stdout


def test_dispatcher_fire_observe_writes_observation(tmp_path: Path) -> None:
    """End-to-end: dispatcher.sh fire observe writes a JSONL line."""
    (tmp_path / ".workforce-profile").write_text("full\n")
    project = tmp_path / "project"
    mem = project / ".foundation-memory"
    mem.mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["WORKFORCE_PROJECT_DIR"] = str(project)
    result = subprocess.run(
        ["bash", str(DISPATCHER), "fire", "observe", "Bash", "success", "ls -la"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    record = json.loads((mem / "observations.jsonl").read_text().strip())
    assert record["tool"] == "Bash"
    assert "ls -la" in record["details"]
