"""Tests for scripts/workforce_paths.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "workforce_paths.py"


def _load():
    name = "workforce_paths"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_orchestration_artifacts_route_to_workforce_dir(tmp_path: Path) -> None:
    wp = _load()
    target = wp.write_path(tmp_path, "intent.md")
    assert target == tmp_path / ".workforce" / "intent.md"
    assert target.parent.is_dir()


def test_engineer_outputs_route_to_project_root(tmp_path: Path) -> None:
    wp = _load()
    for name in ["architecture.md", "vision.md", "brainstorm.md", "spec.md", "WORKFORCE.md"]:
        assert wp.write_path(tmp_path, name) == tmp_path / name


def test_runs_and_status_paths_are_orchestration(tmp_path: Path) -> None:
    wp = _load()
    runs_path = wp.write_path(tmp_path, "runs/2026-04-25T12-00-00/architect/approach.md")
    assert runs_path.parent.is_dir()
    assert ".workforce" in runs_path.parts
    assert "runs" in runs_path.parts

    status_path = wp.write_path(tmp_path, "status/architect.json")
    assert ".workforce" in status_path.parts
    assert "status" in status_path.parts


def test_is_orchestration_artifact_classification() -> None:
    wp = _load()
    # Orchestration
    assert wp.is_orchestration_artifact("intent.md")
    assert wp.is_orchestration_artifact("dispatch.md")
    assert wp.is_orchestration_artifact("integration.md")
    assert wp.is_orchestration_artifact("alignment-report.md")
    assert wp.is_orchestration_artifact("runs/2026/x/approach.md")
    assert wp.is_orchestration_artifact("status/architect.json")
    # Engineer outputs
    assert not wp.is_orchestration_artifact("architecture.md")
    assert not wp.is_orchestration_artifact("vision.md")
    assert not wp.is_orchestration_artifact("workplan.md")
    assert not wp.is_orchestration_artifact("WORKFORCE.md")


def test_workforce_dir_creates_gitignore_on_first_call(tmp_path: Path) -> None:
    wp = _load()
    wf = wp.workforce_dir(tmp_path)
    assert wf == tmp_path / ".workforce"
    gitignore = wf / ".gitignore"
    assert gitignore.exists()
    body = gitignore.read_text()
    assert "runs/" in body
    assert "status/" in body


def test_workforce_dir_idempotent(tmp_path: Path) -> None:
    """Calling it twice must not overwrite a user-modified .gitignore."""
    wp = _load()
    wf = wp.workforce_dir(tmp_path)
    custom = "# custom user content\nruns/\nstatus/\nmy-extra-rule\n"
    (wf / ".gitignore").write_text(custom)
    wp.workforce_dir(tmp_path)  # second call
    assert (wf / ".gitignore").read_text() == custom


def test_read_prefers_workforce_over_root(tmp_path: Path) -> None:
    """If both exist, .workforce/ wins. This is the migration path."""
    wp = _load()
    (tmp_path / "intent.md").write_text("legacy")
    wf = wp.workforce_dir(tmp_path)
    (wf / "intent.md").write_text("new")
    found = wp.read(tmp_path, "intent.md")
    assert found == wf / "intent.md"
    assert found.read_text() == "new"


def test_read_falls_back_to_root_for_legacy_projects(tmp_path: Path) -> None:
    """Existing projects with root-level vision.md / WORKFORCE.md must still be readable."""
    wp = _load()
    (tmp_path / "WORKFORCE.md").write_text("legacy health record")
    found = wp.read(tmp_path, "WORKFORCE.md")
    assert found == tmp_path / "WORKFORCE.md"


def test_read_returns_none_when_missing(tmp_path: Path) -> None:
    wp = _load()
    assert wp.read(tmp_path, "intent.md") is None


def test_cli_read_prints_resolved_path(tmp_path: Path) -> None:
    (tmp_path / "vision.md").write_text("v")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--project-dir", str(tmp_path), "read", "vision.md"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == str(tmp_path / "vision.md")


def test_cli_read_prints_empty_when_missing(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--project-dir", str(tmp_path), "read", "intent.md"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == ""


def test_cli_write_path_creates_dirs(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-dir",
            str(tmp_path),
            "write-path",
            "runs/run-1/architect/approach.md",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    target = Path(result.stdout.strip())
    assert target.parent.is_dir()


def test_cli_is_orchestration_exit_codes(tmp_path: Path) -> None:
    yes = subprocess.run(
        [sys.executable, str(SCRIPT), "is-orchestration", "intent.md"],
        capture_output=True,
        text=True,
    )
    assert yes.returncode == 0
    no = subprocess.run(
        [sys.executable, str(SCRIPT), "is-orchestration", "architecture.md"],
        capture_output=True,
        text=True,
    )
    assert no.returncode == 1
