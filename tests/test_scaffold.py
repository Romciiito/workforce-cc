"""Tests for scripts/scaffold.py.

The scaffold script writes many files via Jinja2 templates. These tests
verify the contract — a minimal happy path per stack — without locking
in template wording, so the templates can evolve freely.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD_SCRIPT = REPO_ROOT / "scripts" / "scaffold.py"
TEMPLATES_DIR = REPO_ROOT / "templates"

_JINJA_AVAILABLE = importlib.util.find_spec("jinja2") is not None
pytestmark = pytest.mark.skipif(not _JINJA_AVAILABLE, reason="jinja2 not installed")


def _run_scaffold(project_dir: Path, stack: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCAFFOLD_SCRIPT),
            "--project-dir",
            str(project_dir),
            "--stack",
            stack,
            "--project-name",
            "Acme",
            "--description",
            "An acme thing",
            "--templates-dir",
            str(TEMPLATES_DIR),
        ],
        capture_output=True,
        text=True,
        check=True,
    )


def test_scaffold_creates_core_files_for_python_fastapi(tmp_path: Path) -> None:
    proj = tmp_path / "acme"
    proj.mkdir()
    _run_scaffold(proj, "python-fastapi")

    # Always-overwritten / always-created files
    assert (proj / "CLAUDE.md").exists()
    claude = (proj / "CLAUDE.md").read_text()
    assert "Acme" in claude
    assert (proj / "decisions.md").exists()
    assert (proj / "workplan.md").exists()

    for doc in ["architecture.md", "development.md", "design-decisions.md", "env-vars.md"]:
        assert (proj / "docs" / "claude" / doc).exists(), doc

    assert (proj / "tools" / ".gitkeep").exists()

    # CI for python stack
    workflows = list((proj / ".github" / "workflows").glob("*.yml"))
    assert any("ci-python" in w.name for w in workflows)
    assert any("deploy-staging" in w.name for w in workflows)


def test_scaffold_writes_settings_with_stack_specific_perms(tmp_path: Path) -> None:
    proj = tmp_path / "acme"
    proj.mkdir()
    _run_scaffold(proj, "python-fastapi")

    settings = json.loads((proj / ".claude" / "settings.local.json").read_text())
    perms = settings["permissions"]["allow"]
    assert any("python3" in p for p in perms)
    assert any("uvicorn" in p for p in perms)


def test_scaffold_nextjs_picks_node_perms_and_node_ci(tmp_path: Path) -> None:
    proj = tmp_path / "acme"
    proj.mkdir()
    _run_scaffold(proj, "nextjs-fullstack")

    settings = json.loads((proj / ".claude" / "settings.local.json").read_text())
    perms = settings["permissions"]["allow"]
    assert any("npm" in p for p in perms)
    assert not any("uvicorn" in p for p in perms)

    workflows = list((proj / ".github" / "workflows").glob("*.yml"))
    assert any("ci-nextjs" in w.name for w in workflows)


def test_scaffold_does_not_overwrite_existing_workplan(tmp_path: Path) -> None:
    proj = tmp_path / "acme"
    proj.mkdir()
    (proj / "workplan.md").write_text("# DO NOT REPLACE\n")
    _run_scaffold(proj, "python-fastapi")
    assert (proj / "workplan.md").read_text() == "# DO NOT REPLACE\n"


def test_scaffold_overwrites_claude_md_every_run(tmp_path: Path) -> None:
    proj = tmp_path / "acme"
    proj.mkdir()
    (proj / "CLAUDE.md").write_text("# stale stub\n")
    _run_scaffold(proj, "python-fastapi")
    refreshed = (proj / "CLAUDE.md").read_text()
    assert refreshed != "# stale stub\n"
    assert "Acme" in refreshed


def test_scaffold_creates_stack_dirs_from_structure_json(tmp_path: Path) -> None:
    proj = tmp_path / "acme"
    proj.mkdir()
    _run_scaffold(proj, "python-fastapi")

    structure = json.loads(
        (TEMPLATES_DIR / "stacks" / "python-fastapi" / "structure.json").read_text()
    )
    for d in structure.get("dirs", []):
        assert (proj / d).is_dir(), f"missing scaffolded dir: {d}"


def test_python_stack_renders_ci_python_workflow(tmp_path: Path) -> None:
    """Regression: ci-python.yml.jinja referenced env_prefix but scaffold.py
    didn't define it, so render silently failed and only deploy-staging.yml
    landed on disk."""
    proj = tmp_path / "acme"
    proj.mkdir()
    result = _run_scaffold(proj, "python-fastapi")
    assert "WARNING" not in result.stderr, result.stderr

    workflows = {p.name for p in (proj / ".github" / "workflows").glob("*.yml")}
    assert "ci-python.yml" in workflows
    ci = (proj / ".github" / "workflows" / "ci-python.yml").read_text()
    # env_prefix must be substituted, not left as-is.
    assert "{{" not in ci
    assert "ACME_DATABASE_URL" in ci


def test_derive_env_prefix_normalises_project_name() -> None:
    name = "scaffold"
    if name in sys.modules:
        module = sys.modules[name]
    else:
        spec = importlib.util.spec_from_file_location(name, SCAFFOLD_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[name] = module
        spec.loader.exec_module(module)

    assert module.derive_env_prefix("Acme") == "ACME"
    assert module.derive_env_prefix("My Cool App") == "MY_COOL_APP"
    assert module.derive_env_prefix("acme-corp") == "ACME_CORP"
    assert module.derive_env_prefix("123-numeric-start") == "APP"
    assert module.derive_env_prefix("") == "APP"
    assert module.derive_env_prefix("!!!") == "APP"


def test_every_stack_has_structure_json() -> None:
    """Lock the catalog: every stack referenced by scaffold.py must ship a structure file."""
    name = "scaffold"
    if name in sys.modules:
        module = sys.modules[name]
    else:
        spec = importlib.util.spec_from_file_location(name, SCAFFOLD_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[name] = module
        spec.loader.exec_module(module)
    for stack in module.STACK_PERMISSIONS.keys():
        structure = TEMPLATES_DIR / "stacks" / stack / "structure.json"
        assert structure.exists(), f"missing structure.json for stack: {stack}"
