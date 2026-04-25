"""Tests for scripts/pipeline_runner.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_SCRIPT = REPO_ROOT / "scripts" / "pipeline_runner.py"


def _load_pipeline():
    name = "pipeline_runner"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, PIPELINE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_classify_routes_known_keywords() -> None:
    pipeline = _load_pipeline()
    # The matcher iterates buckets in insertion order and returns the first
    # bucket whose keyword appears as a substring. Tests must use phrases
    # that don't accidentally match an earlier bucket — e.g. "build" hits
    # frontend because it contains the substring "ui".
    assert pipeline.classify("- [ ] write the API endpoint") == "backend"
    assert pipeline.classify("- [ ] render dashboard page") == "frontend"
    assert pipeline.classify("- [ ] set up docker registry") == "devops"
    assert pipeline.classify("- [ ] add coverage reporting") == "testing"
    assert pipeline.classify("- [ ] schedule cron job") == "worker"
    assert pipeline.classify("- [ ] ship react native expo release") == "mobile"


def test_classify_falls_back_to_backend_for_unknown() -> None:
    pipeline = _load_pipeline()
    assert pipeline.classify("- [ ] mysterious task") == "backend"


def test_read_current_phase_picks_first_in_progress(tmp_path: Path) -> None:
    pipeline = _load_pipeline()
    workplan = tmp_path / "workplan.md"
    workplan.write_text(
        "## Phase 0\n"
        "- [x] done thing\n"
        "## Phase 1\n"
        "- [ ] build api\n"
        "- [ ] build ui\n"
        "## Phase 2\n"
        "- [ ] later\n"
    )
    lines = pipeline.read_current_phase(workplan)
    assert any("- [ ] build api" in line for line in lines)
    assert any("- [ ] build ui" in line for line in lines)
    assert not any("Phase 2" in line for line in lines)


def test_read_current_phase_returns_empty_if_no_open_tasks(tmp_path: Path) -> None:
    pipeline = _load_pipeline()
    workplan = tmp_path / "workplan.md"
    workplan.write_text("## Phase 0\n- [x] done\n## Phase 1\n- [x] also done\n")
    assert pipeline.read_current_phase(workplan) == []


def test_plan_ranks_tracks_by_open_task_count(tmp_path: Path) -> None:
    pipeline = _load_pipeline()
    workplan = tmp_path / "workplan.md"
    workplan.write_text(
        "## Phase 1\n"
        "- [ ] build api endpoint\n"
        "- [ ] build api auth\n"
        "- [ ] build api migration\n"
        "- [ ] build ui dashboard\n"
        "- [ ] add e2e test\n"
    )
    ranked = pipeline.plan(workplan, max_tracks=4)
    # backend should top the ranking (3 tasks), frontend (1), testing (1)
    assert ranked[0] == ("backend", 3)
    track_names = [t for t, _ in ranked]
    assert "frontend" in track_names
    assert "testing" in track_names


def test_plan_clips_to_max_tracks(tmp_path: Path) -> None:
    pipeline = _load_pipeline()
    workplan = tmp_path / "workplan.md"
    workplan.write_text(
        "## Phase 1\n"
        "- [ ] api task\n"
        "- [ ] ui task\n"
        "- [ ] docker task\n"
        "- [ ] e2e test\n"
    )
    ranked = pipeline.plan(workplan, max_tracks=2)
    assert len(ranked) == 2


def test_opening_prompt_mentions_track_and_project() -> None:
    pipeline = _load_pipeline()
    prompt = pipeline.opening_prompt("backend", "myapp")
    assert "backend agent" in prompt
    assert "myapp" in prompt
    assert "workplan.md" in prompt


def test_plan_cli_smoke(tmp_path: Path) -> None:
    workplan = tmp_path / "workplan.md"
    workplan.write_text(
        "## Phase 1\n- [ ] build api\n- [ ] build ui\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(PIPELINE_SCRIPT),
            "plan",
            "--workplan",
            str(workplan),
            "--project",
            "myapp",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "RANKED TRACKS" in result.stdout
    assert "backend" in result.stdout
    assert "frontend" in result.stdout


def test_plan_cli_handles_no_open_tasks(tmp_path: Path) -> None:
    workplan = tmp_path / "workplan.md"
    workplan.write_text("## Phase 1\n- [x] done\n")
    result = subprocess.run(
        [
            sys.executable,
            str(PIPELINE_SCRIPT),
            "plan",
            "--workplan",
            str(workplan),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "No parallelizable work" in result.stdout
