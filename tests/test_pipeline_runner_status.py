"""Tests for the new `status`, `blocked-scan`, `render-envelope`, `spawn-payload` subcommands of pipeline_runner.py.

These are additive subcommands. The existing `plan` and `spawn` subcommands
(and their tests in test_pipeline_runner.py) remain unchanged.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PR_SCRIPT = REPO_ROOT / "scripts" / "pipeline_runner.py"
SP_SCRIPT = REPO_ROOT / "scripts" / "spawn_payload.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def runner():
    return _load("pipeline_runner", PR_SCRIPT)


@pytest.fixture
def payload_module():
    return _load("spawn_payload", SP_SCRIPT)


def _make_status_dir(tmp_path: Path) -> Path:
    status = tmp_path / ".workforce" / "status"
    status.mkdir(parents=True)
    return status


def _write_status(status_dir: Path, engineer: str, state: str, **extra) -> None:
    (status_dir / f"{engineer}.json").write_text(json.dumps({
        "state": state,
        "ts": "2026-04-25T17:00:00+00:00",
        "engineer": engineer,
        "run_id": ".workforce/runs/test",
        **extra,
    }))


def test_status_table_handles_empty_status_dir(runner, tmp_path: Path) -> None:
    table = runner.status_table([])
    assert "No engineers" in table


def test_status_records_read_in_order(runner, tmp_path: Path) -> None:
    status = _make_status_dir(tmp_path)
    _write_status(status, "architect", "DONE", artifacts=["architecture.md"])
    _write_status(status, "security-analyst", "RUNNING")

    records = runner.read_status(tmp_path)
    engineers = [r["engineer"] for r in records]
    assert "architect" in engineers
    assert "security-analyst" in engineers


def test_all_done_returns_true_only_when_every_expected_is_done(runner, tmp_path: Path) -> None:
    status = _make_status_dir(tmp_path)
    _write_status(status, "architect", "DONE", artifacts=["architecture.md"])
    _write_status(status, "security-analyst", "RUNNING")

    records = runner.read_status(tmp_path)
    assert runner.all_done(records, expected_engineers=["architect"]) is True
    assert runner.all_done(records, expected_engineers=["architect", "security-analyst"]) is False


def test_blocked_engineers_only_returns_blocked(runner, tmp_path: Path) -> None:
    status = _make_status_dir(tmp_path)
    _write_status(status, "architect", "DONE", artifacts=["architecture.md"])
    _write_status(status, "requirements-engineer", "BLOCKED", reason="missing input: spec.md")

    records = runner.read_status(tmp_path)
    blocked = runner.blocked_engineers(records)
    assert len(blocked) == 1
    assert blocked[0]["engineer"] == "requirements-engineer"


def test_status_cli_returns_nonzero_when_engineer_blocked(tmp_path: Path) -> None:
    status = _make_status_dir(tmp_path)
    _write_status(status, "architect", "BLOCKED", reason="missing input")

    result = subprocess.run(
        [sys.executable, str(PR_SCRIPT), "status", "--project-dir", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "BLOCKED" in result.stdout


def test_status_cli_json_output(tmp_path: Path) -> None:
    status = _make_status_dir(tmp_path)
    _write_status(status, "architect", "DONE", artifacts=["architecture.md"])

    result = subprocess.run(
        [sys.executable, str(PR_SCRIPT), "status", "--project-dir", str(tmp_path), "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "records" in payload
    assert payload["all_done"] in (True, False)
    assert payload["blocked"] == []


def test_status_cli_with_expect_passes_when_all_done(tmp_path: Path) -> None:
    status = _make_status_dir(tmp_path)
    _write_status(status, "architect", "DONE", artifacts=["architecture.md"])
    _write_status(status, "security-analyst", "DONE", artifacts=["security-model.md"])

    result = subprocess.run(
        [
            sys.executable,
            str(PR_SCRIPT),
            "status",
            "--project-dir",
            str(tmp_path),
            "--expect",
            "architect,security-analyst",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "WAVE COMPLETE" in result.stdout


def test_blocked_scan_finds_blocked_md(tmp_path: Path) -> None:
    runs = tmp_path / ".workforce" / "runs" / "2026-04-25T17-00-00Z" / "architect"
    runs.mkdir(parents=True)
    blocked = runs / "BLOCKED.md"
    blocked.write_text("# Blocked — architect\n\n## Why blocked\nmissing input\n")

    result = subprocess.run(
        [sys.executable, str(PR_SCRIPT), "blocked-scan", "--project-dir", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1  # blocked items present
    assert "architect/BLOCKED.md" in result.stdout
    assert "missing input" in result.stdout


def test_blocked_scan_returns_zero_when_no_blocked_files(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(PR_SCRIPT), "blocked-scan", "--project-dir", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "No BLOCKED" in result.stdout


def test_render_envelope_cli_smokes_through(tmp_path: Path, payload_module) -> None:
    payload_path = tmp_path / "payload.json"
    p = payload_module.SpawnPayload(
        run_id=".workforce/runs/x",
        engineer="architect",
        inputs=["intent.md"],
        outputs=["architecture.md"],
        status_file=".workforce/status/architect.json",
    )
    payload_path.write_text(p.to_json())

    result = subprocess.run(
        [
            sys.executable,
            str(PR_SCRIPT),
            "render-envelope",
            "--payload",
            str(payload_path),
            "--project",
            "Acme",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "architect" in result.stdout
    assert "Acme" in result.stdout
    assert "intent.md" in result.stdout


def test_spawn_payload_cli_print_mode_does_not_block(tmp_path: Path, payload_module) -> None:
    """spawn-payload --mode=print just prints instructions; must not hang."""
    payload_path = tmp_path / "payload.json"
    p = payload_module.SpawnPayload(
        run_id=".workforce/runs/x",
        engineer="architect",
        inputs=["intent.md"],
        outputs=["architecture.md"],
        status_file=".workforce/status/architect.json",
    )
    payload_path.write_text(p.to_json())

    result = subprocess.run(
        [
            sys.executable,
            str(PR_SCRIPT),
            "spawn-payload",
            "--payload",
            str(payload_path),
            "--mode",
            "print",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "architect" in result.stdout


def test_legacy_subcommands_unchanged() -> None:
    """The legacy `plan` and `spawn` subcommands must still appear in --help.

    This is a regression guard — Chunk 4 must be strictly additive.
    """
    result = subprocess.run(
        [sys.executable, str(PR_SCRIPT), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    for cmd in ["plan", "spawn", "render-envelope", "spawn-payload", "status", "blocked-scan"]:
        assert cmd in result.stdout, f"--help missing subcommand: {cmd}"
