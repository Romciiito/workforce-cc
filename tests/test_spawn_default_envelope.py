"""Tests for Chunk 11: pipeline_runner.spawn defaults to envelope rendering.

The `spawn` subcommand now renders the engineer task envelope by default.
The legacy one-liner is still available via --prompt-style=legacy or the
shorthand --legacy-prompt. Existing tests in test_pipeline_runner.py
remain green because they test the `opening_prompt()` function directly,
which is preserved for legacy callers.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PR_SCRIPT = REPO_ROOT / "scripts" / "pipeline_runner.py"


def _load_module():
    name = "pipeline_runner"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, PR_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_synthesise_payload_for_track_returns_valid_payload() -> None:
    pr = _load_module()
    payload = pr.synthesise_payload_for_track("backend", "myapp")
    assert payload.engineer == "backend"
    assert payload.run_id.startswith(".workforce/runs/")
    assert "workplan.md" in payload.inputs
    assert payload.status_file == ".workforce/status/backend.json"
    assert payload.deadline_min == 30


def test_spawn_default_uses_envelope(tmp_path: Path) -> None:
    """`spawn --track <name> --mode print` defaults to envelope rendering."""
    result = subprocess.run(
        [
            sys.executable,
            str(PR_SCRIPT),
            "spawn",
            "--track",
            "backend",
            "--project",
            "myapp",
            "--mode",
            "print",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    # The envelope mentions the engineer-with-judgment framing — adversarial
    # self-critique, approach.md before output, BLOCKED.md schema. The legacy
    # one-liner has none of these.
    assert "Adversarial self-critique" in out
    assert "approach.md" in out
    assert "BLOCKED.md" in out


def test_spawn_legacy_prompt_flag_uses_legacy_oneliner(tmp_path: Path) -> None:
    """--legacy-prompt is the shorthand for the pre-Chunk-11 behavior."""
    result = subprocess.run(
        [
            sys.executable,
            str(PR_SCRIPT),
            "spawn",
            "--track",
            "backend",
            "--project",
            "myapp",
            "--mode",
            "print",
            "--legacy-prompt",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=10,
    )
    assert result.returncode == 0
    out = result.stdout
    # Legacy: the simple one-liner mentions backend agent, project, workplan.md.
    assert "backend agent" in out
    assert "myapp" in out
    # And critically, it does NOT include the envelope-specific sections.
    assert "Adversarial self-critique" not in out
    assert "approach.md" not in out


def test_spawn_explicit_prompt_style_legacy(tmp_path: Path) -> None:
    """--prompt-style=legacy is the explicit form."""
    result = subprocess.run(
        [
            sys.executable,
            str(PR_SCRIPT),
            "spawn",
            "--track",
            "backend",
            "--project",
            "myapp",
            "--mode",
            "print",
            "--prompt-style",
            "legacy",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=10,
    )
    assert result.returncode == 0
    assert "backend agent" in result.stdout
    assert "Adversarial self-critique" not in result.stdout


def test_spawn_explicit_prompt_style_envelope(tmp_path: Path) -> None:
    """--prompt-style=envelope is the explicit form (same as default)."""
    result = subprocess.run(
        [
            sys.executable,
            str(PR_SCRIPT),
            "spawn",
            "--track",
            "backend",
            "--project",
            "myapp",
            "--mode",
            "print",
            "--prompt-style",
            "envelope",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=10,
    )
    assert result.returncode == 0
    assert "Adversarial self-critique" in result.stdout


def test_spawn_envelope_includes_track_in_status_file(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(PR_SCRIPT),
            "spawn",
            "--track",
            "frontend",
            "--mode",
            "print",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=10,
    )
    assert result.returncode == 0
    assert ".workforce/status/frontend.json" in result.stdout


def test_spawn_help_documents_prompt_style() -> None:
    result = subprocess.run(
        [sys.executable, str(PR_SCRIPT), "spawn", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--prompt-style" in result.stdout
    assert "envelope" in result.stdout
    assert "--legacy-prompt" in result.stdout


def test_legacy_opening_prompt_function_still_exists() -> None:
    """The opening_prompt() helper is preserved as the legacy mode's
    implementation. Existing tests rely on it directly."""
    pr = _load_module()
    prompt = pr.opening_prompt("backend", "myapp")
    assert "backend agent" in prompt
    assert "myapp" in prompt
    assert "workplan.md" in prompt
