"""Tests for `pipeline_runner.py dispatch-wave` — parses a dispatch.md and
spawns every engineer in the chosen wave.

This is the missing link between conductor[dispatch] (which writes
.workforce/dispatch.md) and the multi-terminal world (where each
engineer needs to be spawned separately). Before this chunk the user
had to read dispatch.md by eye and run `pipeline_runner spawn` per
engineer. With dispatch-wave, one command launches a whole wave.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PR_SCRIPT = REPO_ROOT / "scripts" / "pipeline_runner.py"


def _load():
    name = "pipeline_runner"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, PR_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _make_dispatch_md(tmp_path: Path) -> Path:
    """Build a dispatch.md that conforms to skills/_backbone/dispatch.template.md."""
    path = tmp_path / "dispatch.md"
    path.write_text(
        """# Dispatch — test run

## Run summary
Two waves: parallel analysis then synthesis.

## Run id

.workforce/runs/2026-04-25T17-00-00Z

## Wave order
1. architect, security-analyst
2. workplan-builder

## Tasks

### Task 1 — architect
- **Territory**: docs/claude/architecture.md
- **Inputs**: intent.md, spec.md, security-model.md
- **Outputs**: architecture.md
- **Verification**: `test -f architecture.md && grep -q '## Components' architecture.md`
- **Success criteria**:
  - Every REQ-F mapped to a component
  - Failure-mode analysis covers all external deps
- **Escalation**: write BLOCKED.md if security-model.md is missing

### Task 2 — security-analyst
- **Territory**: security-model.md
- **Inputs**: spec.md, brainstorm.md
- **Outputs**: security-model.md
- **Verification**: `grep -c '## Phase 0' security-model.md`
- **Success criteria**:
  - 5+ Phase 0 items
  - OWASP Top 10 coverage
- **Escalation**: BLOCKED.md if spec.md missing

### Task 3 — workplan-builder
- **Territory**: workplan.md, claude-rules.md
- **Inputs**: architecture.md, security-model.md, requirements.md
- **Outputs**: workplan.md, claude-rules.md
- **Verification**: `test -f workplan.md`
- **Success criteria**:
  - Phase 0 contains all security items
  - Phase 1+ has measurable Done definitions
- **Escalation**: BLOCKED.md if any input missing
"""
    )
    return path


# ── parser unit tests ────────────────────────────────────────────────────────


def test_parse_extracts_run_id(tmp_path: Path) -> None:
    pr = _load()
    parsed = pr.parse_dispatch_md(_make_dispatch_md(tmp_path))
    assert parsed["run_id"] == ".workforce/runs/2026-04-25T17-00-00Z"


def test_parse_extracts_two_waves(tmp_path: Path) -> None:
    pr = _load()
    parsed = pr.parse_dispatch_md(_make_dispatch_md(tmp_path))
    assert len(parsed["waves"]) == 2
    assert "architect" in parsed["waves"][0]
    assert "security-analyst" in parsed["waves"][0]
    assert "workplan-builder" in parsed["waves"][1]


def test_parse_extracts_three_tasks_with_required_fields(tmp_path: Path) -> None:
    pr = _load()
    parsed = pr.parse_dispatch_md(_make_dispatch_md(tmp_path))
    assert len(parsed["tasks"]) == 3
    architect_task = next(
        t for t in parsed["tasks"].values() if t["engineer"] == "architect"
    )
    assert architect_task["inputs"] == ["intent.md", "spec.md", "security-model.md"]
    assert architect_task["outputs"] == ["architecture.md"]
    assert "architecture.md" in architect_task["verification"]


def test_parse_handles_missing_run_id(tmp_path: Path) -> None:
    pr = _load()
    path = tmp_path / "dispatch.md"
    path.write_text(
        "# Dispatch\n\n## Wave order\n1. architect\n\n## Tasks\n\n### Task 1 — architect\n"
        "- **Inputs**: spec.md\n- **Outputs**: architecture.md\n"
    )
    parsed = pr.parse_dispatch_md(path)
    assert parsed["run_id"] is None


def test_parse_rejects_missing_file(tmp_path: Path) -> None:
    pr = _load()
    with pytest.raises(SystemExit):
        pr.parse_dispatch_md(tmp_path / "does-not-exist.md")


# ── CLI tests ────────────────────────────────────────────────────────────────


def test_dispatch_wave_dry_run_lists_engineers(tmp_path: Path) -> None:
    dispatch = _make_dispatch_md(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(PR_SCRIPT),
            "dispatch-wave",
            "--from",
            str(dispatch),
            "--wave",
            "1",
            "--dry-run",
            "--mode",
            "print",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "would spawn architect" in result.stdout
    assert "would spawn security-analyst" in result.stdout
    # Wave 2 task must not appear when wave=1 is selected.
    assert "would spawn workplan-builder" not in result.stdout


def test_dispatch_wave_2_lists_only_workplan_builder(tmp_path: Path) -> None:
    dispatch = _make_dispatch_md(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(PR_SCRIPT),
            "dispatch-wave",
            "--from",
            str(dispatch),
            "--wave",
            "2",
            "--dry-run",
            "--mode",
            "print",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "would spawn workplan-builder" in result.stdout
    assert "would spawn architect" not in result.stdout


def test_dispatch_wave_out_of_range_fails(tmp_path: Path) -> None:
    dispatch = _make_dispatch_md(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(PR_SCRIPT),
            "dispatch-wave",
            "--from",
            str(dispatch),
            "--wave",
            "99",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "out of range" in result.stderr


def test_dispatch_wave_print_mode_prints_payload_summary(tmp_path: Path) -> None:
    """In print mode, the engineer's inputs/outputs and status_file must appear."""
    dispatch = _make_dispatch_md(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(PR_SCRIPT),
            "dispatch-wave",
            "--from",
            str(dispatch),
            "--wave",
            "1",
            "--dry-run",
            "--mode",
            "print",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "intent.md" in result.stdout
    assert "spec.md" in result.stdout
    assert "architecture.md" in result.stdout
    assert ".workforce/status/architect.json" in result.stdout


def test_dispatch_wave_help_documents_flags() -> None:
    result = subprocess.run(
        [sys.executable, str(PR_SCRIPT), "dispatch-wave", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    for flag in ["--from", "--wave", "--mode", "--dry-run"]:
        assert flag in result.stdout


def test_dispatch_wave_appears_in_main_help() -> None:
    """The new subcommand must surface in the top-level --help."""
    result = subprocess.run(
        [sys.executable, str(PR_SCRIPT), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "dispatch-wave" in result.stdout
