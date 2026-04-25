"""Smoke tests for install.sh.

The installer is bash, so these tests run it end-to-end against fake HOME
directories and assert observable filesystem state.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"


def _run_install(home: Path, *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    return subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        check=False,
    )


def test_help_flag_prints_usage_block(tmp_path: Path) -> None:
    result = _run_install(tmp_path, "--help")
    assert result.returncode == 0
    assert "Unified installer" in result.stdout


def test_install_creates_symlinks_and_copies_agents(tmp_path: Path) -> None:
    result = _run_install(tmp_path)
    assert result.returncode == 0, result.stderr or result.stdout

    skills = tmp_path / ".claude" / "skills"
    agents = tmp_path / ".claude" / "agents"

    assert (skills / "foundation").is_symlink()
    assert (skills / "workforce").is_symlink()
    assert (skills / "sync").is_symlink()

    # Per-pack agents must all land in ~/.claude/agents/ with their original names.
    for name in ["foundation-orchestrator.md", "workforce-orchestrator.md", "scanner.md"]:
        assert (agents / name).is_file(), f"expected agent: {name}"

    # Beacon file is written.
    beacon = tmp_path / ".foundation-path"
    assert beacon.exists()
    assert beacon.read_text().strip() == str(REPO_ROOT)


def test_install_only_workforce_skips_foundation_skill(tmp_path: Path) -> None:
    result = _run_install(tmp_path, "--only", "workforce")
    assert result.returncode == 0, result.stderr or result.stdout

    skills = tmp_path / ".claude" / "skills"
    assert (skills / "workforce").is_symlink()
    assert (skills / "sync").is_symlink()
    assert not (skills / "foundation").exists()


def test_uninstall_cleans_up_what_install_added(tmp_path: Path) -> None:
    install_result = _run_install(tmp_path)
    assert install_result.returncode == 0

    uninstall_result = _run_install(tmp_path, "--uninstall")
    assert uninstall_result.returncode == 0

    skills = tmp_path / ".claude" / "skills"
    agents = tmp_path / ".claude" / "agents"
    assert not (skills / "foundation").exists()
    assert not (skills / "workforce").exists()
    assert not (skills / "sync").exists()
    assert not (agents / "foundation-orchestrator.md").exists()
    assert not (tmp_path / ".foundation-path").exists()


def test_collision_check_fires_on_duplicate_filenames(tmp_path: Path) -> None:
    """If a duplicate filename slips into two packs, install should hard-fail."""
    fake_repo = tmp_path / "fake-repo"
    shutil.copytree(REPO_ROOT, fake_repo, ignore=shutil.ignore_patterns(".git"))

    # Plant a duplicate: same filename in _shared and foundation.
    duplicate = fake_repo / "agents" / "_shared" / "foundation-orchestrator.md"
    duplicate.write_text("---\nname: bogus\n---\n\nstub\n")

    home = tmp_path / "home"
    env = os.environ.copy()
    env["HOME"] = str(home)
    result = subprocess.run(
        ["bash", str(fake_repo / "install.sh")],
        capture_output=True,
        text=True,
        cwd=fake_repo,
        env=env,
        check=False,
    )
    assert result.returncode != 0
    assert "collision" in result.stdout.lower() or "collision" in result.stderr.lower()
    assert "foundation-orchestrator.md" in result.stdout + result.stderr
