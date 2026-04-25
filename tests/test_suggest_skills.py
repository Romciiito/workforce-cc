"""Tests for scripts/suggest_skills.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SUGGEST_SCRIPT = REPO_ROOT / "scripts" / "suggest_skills.py"


def test_known_stack_returns_catalog_entries(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            str(SUGGEST_SCRIPT),
            "--stack",
            "python-fastapi",
            "--skills-dir",
            str(skills_dir),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    names = {entry["name"] for entry in payload}
    assert "postgres-pro" in names
    assert all(entry["status"] == "missing" for entry in payload)


def test_installed_skills_are_marked(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    pg = skills_dir / "postgres-pro"
    pg.mkdir(parents=True)
    (pg / "SKILL.md").write_text("---\nname: postgres-pro\n---\n")
    result = subprocess.run(
        [
            sys.executable,
            str(SUGGEST_SCRIPT),
            "--stack",
            "python-fastapi",
            "--skills-dir",
            str(skills_dir),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    statuses = {entry["name"]: entry["status"] for entry in payload}
    assert statuses["postgres-pro"] == "installed"
    assert statuses["docker-expert"] == "missing"


def test_unknown_stack_prints_friendly_message(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            str(SUGGEST_SCRIPT),
            "--stack",
            "no-such-stack",
            "--skills-dir",
            str(skills_dir),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "No skill recommendations" in result.stdout


def test_skills_dir_missing_is_treated_as_empty(tmp_path: Path) -> None:
    """If the skills dir does not exist, every catalog entry must be 'missing'."""
    result = subprocess.run(
        [
            sys.executable,
            str(SUGGEST_SCRIPT),
            "--stack",
            "python-fastapi",
            "--skills-dir",
            str(tmp_path / "does-not-exist"),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert all(entry["status"] == "missing" for entry in payload)
