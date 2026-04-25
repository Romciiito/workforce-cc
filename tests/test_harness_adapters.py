"""Tests for the multi-harness adapter framework (Chunk 30).

Covers:
  - Each harness directory has a valid manifest.json + README.md.
  - Manifests conform to manifest-schema.json (key fields).
  - scripts/harness_install.py renders adapters into a tmp project.
  - install.sh --harnesses flag persists ~/.workforce-harnesses beacon.
  - profiles/<name>.json declares a 'harnesses' array (default ['claude']).
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
HARNESSES_DIR = REPO_ROOT / "harnesses"
SCRIPT = REPO_ROOT / "scripts" / "harness_install.py"
INSTALL_SH = REPO_ROOT / "install.sh"

ALL_HARNESSES = ["claude", "cursor", "codex", "opencode", "gemini"]

_JINJA = importlib.util.find_spec("jinja2") is not None


# ── manifest sanity ─────────────────────────────────────────────────────────


def test_harnesses_dir_has_readme_and_schema() -> None:
    assert (HARNESSES_DIR / "README.md").exists()
    assert (HARNESSES_DIR / "manifest-schema.json").exists()


@pytest.mark.parametrize("harness", ALL_HARNESSES)
def test_each_harness_has_manifest_and_readme(harness: str) -> None:
    h_dir = HARNESSES_DIR / harness
    assert (h_dir / "manifest.json").exists(), f"{harness}: missing manifest.json"
    assert (h_dir / "README.md").exists(), f"{harness}: missing README.md"


@pytest.mark.parametrize("harness", ALL_HARNESSES)
def test_manifest_has_required_fields(harness: str) -> None:
    manifest = json.loads((HARNESSES_DIR / harness / "manifest.json").read_text())
    assert manifest["name"] == harness
    assert "description" in manifest and manifest["description"]
    assert "writes" in manifest and isinstance(manifest["writes"], list) and manifest["writes"]
    assert "supports" in manifest


@pytest.mark.parametrize("harness", ALL_HARNESSES)
def test_manifest_writes_entries_are_well_formed(harness: str) -> None:
    manifest = json.loads((HARNESSES_DIR / harness / "manifest.json").read_text())
    for entry in manifest["writes"]:
        assert "kind" in entry
        assert "target" in entry
        assert entry["kind"] in {"rules-file", "agents-dir", "settings", "config-file"}


@pytest.mark.parametrize("harness", ALL_HARNESSES)
def test_manifest_template_sources_exist(harness: str) -> None:
    """Every rules-file source path must resolve to a real file in the repo."""
    manifest = json.loads((HARNESSES_DIR / harness / "manifest.json").read_text())
    for entry in manifest["writes"]:
        if entry["kind"] != "rules-file":
            continue
        source = entry.get("source")
        if not source:
            continue
        path = REPO_ROOT / source
        assert path.exists(), f"{harness}: source missing — {source}"


def test_only_claude_supports_full_orchestration() -> None:
    """All non-claude harnesses are context-only by design."""
    claude = json.loads((HARNESSES_DIR / "claude" / "manifest.json").read_text())
    assert claude["supports"]["orchestration"] == "full"
    for harness in ["cursor", "codex", "opencode", "gemini"]:
        m = json.loads((HARNESSES_DIR / harness / "manifest.json").read_text())
        assert m["supports"]["orchestration"] == "context-only", (
            f"{harness} should be context-only — full orchestration is claude-only"
        )


# ── profile schema includes harnesses ───────────────────────────────────────


def test_profile_schema_lists_harnesses_field() -> None:
    schema = json.loads((REPO_ROOT / "profiles" / "schema.json").read_text())
    assert "harnesses" in schema["properties"]
    enum = schema["properties"]["harnesses"]["items"]["enum"]
    assert set(enum) == set(ALL_HARNESSES)


@pytest.mark.parametrize("profile", ["full", "foundation", "workforce", "minimal"])
def test_each_profile_declares_harnesses(profile: str) -> None:
    """All four profiles should ship with a 'harnesses' array. Default is ['claude']."""
    p = json.loads((REPO_ROOT / "profiles" / f"{profile}.json").read_text())
    assert "harnesses" in p, f"profile {profile}.json missing 'harnesses' field"
    assert isinstance(p["harnesses"], list)
    assert "claude" in p["harnesses"], (
        f"profile {profile}.json must include 'claude' (the legacy default)"
    )


# ── harness_install.py renders correctly ────────────────────────────────────


@pytest.mark.skipif(not _JINJA, reason="jinja2 not installed")
def test_claude_adapter_writes_CLAUDE_md(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--harness", "claude",
            "--project-dir", str(project),
            "--project-name", "Acme",
            "--stack", "python-fastapi",
            "--description", "Test app",
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (project / "CLAUDE.md").exists()
    body = (project / "CLAUDE.md").read_text()
    assert "Acme" in body
    assert "ACME" in body  # env_prefix derived
    # Settings + agents directory both populated.
    assert (project / ".claude" / "settings.local.json").exists()
    assert (project / ".claude" / "agents" / "intent-validator.md").exists()


@pytest.mark.skipif(not _JINJA, reason="jinja2 not installed")
def test_cursor_adapter_writes_two_mdc_files(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--harness", "cursor",
            "--project-dir", str(project),
            "--project-name", "Acme",
            "--stack", "python-fastapi",
            "--description", "Test app",
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    rules = project / ".cursor" / "rules"
    assert (rules / "00-workforce-cc.mdc").exists()
    assert (rules / "01-orchestration-pointers.mdc").exists()
    body = (rules / "00-workforce-cc.mdc").read_text()
    # Recommends switching to Claude Code for orchestration.
    assert "Claude Code" in body or "claude code" in body.lower()


@pytest.mark.skipif(not _JINJA, reason="jinja2 not installed")
def test_codex_adapter_writes_AGENTS_md(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--harness", "codex",
            "--project-dir", str(project),
            "--project-name", "Acme",
            "--stack", "python-fastapi",
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (project / "AGENTS.md").exists()
    assert "Acme" in (project / "AGENTS.md").read_text()


@pytest.mark.skipif(not _JINJA, reason="jinja2 not installed")
def test_opencode_adapter_writes_under_dot_opencode(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--harness", "opencode",
            "--project-dir", str(project),
            "--project-name", "Acme",
            "--stack", "python-fastapi",
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (project / ".opencode" / "agents" / "workforce-cc.md").exists()


@pytest.mark.skipif(not _JINJA, reason="jinja2 not installed")
def test_gemini_adapter_writes_GEMINI_md(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--harness", "gemini",
            "--project-dir", str(project),
            "--project-name", "Acme",
            "--stack", "python-fastapi",
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (project / "GEMINI.md").exists()


def test_harness_install_rejects_unknown_harness(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--harness", "no-such-harness",
            "--project-dir", str(tmp_path),
            "--project-name", "Acme",
        ],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "unknown" in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(not _JINJA, reason="jinja2 not installed")
def test_harness_install_dry_run_does_not_write(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--harness", "claude",
            "--project-dir", str(project),
            "--project-name", "Acme",
            "--stack", "python-fastapi",
            "--dry-run",
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "would write" in result.stdout.lower()
    assert not (project / "CLAUDE.md").exists()


# ── install.sh flag integration ─────────────────────────────────────────────


def _run_install(home: Path, *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    return subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        capture_output=True, text=True, cwd=REPO_ROOT, env=env, check=False,
    )


def test_install_default_writes_claude_only_beacon(tmp_path: Path) -> None:
    result = _run_install(tmp_path)
    assert result.returncode == 0, result.stderr or result.stdout
    beacon = tmp_path / ".workforce-harnesses"
    assert beacon.exists()
    assert beacon.read_text().strip() == "claude"


def test_install_harnesses_flag_overrides_profile(tmp_path: Path) -> None:
    """--harnesses claude,cursor must override the profile's default ['claude']."""
    result = _run_install(tmp_path, "--profile", "full", "--harnesses", "claude,cursor")
    assert result.returncode == 0, result.stderr or result.stdout
    beacon = (tmp_path / ".workforce-harnesses").read_text().strip()
    assert beacon == "claude,cursor"


def test_install_unknown_harness_fails(tmp_path: Path) -> None:
    result = _run_install(tmp_path, "--harnesses", "claude,no-such-harness")
    assert result.returncode != 0
    assert "unknown harness" in (result.stdout + result.stderr).lower()


def test_install_uninstalls_harness_beacon(tmp_path: Path) -> None:
    install_result = _run_install(tmp_path, "--harnesses", "claude,cursor")
    assert install_result.returncode == 0
    assert (tmp_path / ".workforce-harnesses").exists()
    uninstall_result = _run_install(tmp_path, "--uninstall")
    assert uninstall_result.returncode == 0
    assert not (tmp_path / ".workforce-harnesses").exists()


def test_install_dry_run_does_not_write_beacon(tmp_path: Path) -> None:
    result = _run_install(tmp_path, "--harnesses", "claude,cursor", "--dry-run")
    assert result.returncode == 0
    assert not (tmp_path / ".workforce-harnesses").exists()


def test_install_status_line_shows_harnesses(tmp_path: Path) -> None:
    result = _run_install(tmp_path, "--harnesses", "claude,cursor", "--dry-run")
    assert result.returncode == 0
    assert "Harnesses" in result.stdout
    assert "claude" in result.stdout
    assert "cursor" in result.stdout


def test_install_help_documents_harnesses_flag() -> None:
    result = subprocess.run(
        ["bash", str(INSTALL_SH), "--help"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0
    assert "--harnesses" in result.stdout
