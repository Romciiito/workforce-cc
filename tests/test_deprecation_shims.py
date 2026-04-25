"""Tests for the deprecation strategy in Chunk 8.

Covers:
1. Each legacy orchestrator file has a deprecation header pointing to the
   new role (in-place; not yet moved to agents/deprecated/).
2. install.sh walks agents/orchestrators/ alongside the three legacy packs.
3. scripts/migrate_legacy_orchestrators.py rewrites legacy installed
   agents into shims, idempotently and reversibly.
4. agents/deprecated/README.md documents the migration policy.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"
MIGRATE_SCRIPT = REPO_ROOT / "scripts" / "migrate_legacy_orchestrators.py"

LEGACY_AGENTS = {
    "agents/foundation/foundation-orchestrator.md": "conductor",
    "agents/workforce/workforce-orchestrator.md": "conductor",
    "agents/workforce/vision-keeper.md": "intent-validator",
    "agents/foundation/output-validator.md": "alignment-guard",
}


# ── 1. Deprecation headers in source legacy files ────────────────────────────


@pytest.mark.parametrize("rel_path, new_role", LEGACY_AGENTS.items())
def test_legacy_agent_has_deprecation_header(rel_path: str, new_role: str) -> None:
    body = (REPO_ROOT / rel_path).read_text()
    assert "## ⚠ Deprecation notice" in body, (
        f"{rel_path}: missing '## ⚠ Deprecation notice' section"
    )
    assert new_role in body, f"{rel_path}: deprecation must point at {new_role}"


@pytest.mark.parametrize("rel_path, _", LEGACY_AGENTS.items())
def test_legacy_agent_deprecation_mentions_migration_path(rel_path: str, _: str) -> None:
    body = (REPO_ROOT / rel_path).read_text()
    assert "Migration path" in body or "stays in service" in body, (
        f"{rel_path}: deprecation header must explain migration path / coexistence"
    )


def test_deprecated_readme_exists_and_documents_policy() -> None:
    readme = REPO_ROOT / "agents" / "deprecated" / "README.md"
    assert readme.exists()
    body = readme.read_text()
    # Must list all four legacy agents.
    for legacy in ["foundation-orchestrator", "workforce-orchestrator", "vision-keeper", "output-validator"]:
        assert legacy in body, f"agents/deprecated/README.md missing reference to {legacy}"
    # Must explicitly say files are NOT yet moved.
    assert "still in place" in body or "not yet" in body.lower() or "header-only" in body.lower()
    # Must document the gating conditions for the physical move.
    assert "When does the physical move" in body or "physical move" in body.lower()


# ── 2. install.sh walks agents/orchestrators/ ────────────────────────────────


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


def test_install_deploys_orchestrator_agents(tmp_path: Path) -> None:
    """The new three orchestrator agents must land in ~/.claude/agents/."""
    result = _run_install(tmp_path)
    assert result.returncode == 0, result.stderr or result.stdout

    agents = tmp_path / ".claude" / "agents"
    for name in ["intent-validator.md", "conductor.md", "alignment-guard.md"]:
        assert (agents / name).is_file(), f"orchestrator agent not installed: {name}"


def test_install_collision_check_ignores_readme(tmp_path: Path) -> None:
    """README.md files in agent directories must not trigger the collision check."""
    result = _run_install(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_install_only_workforce_still_includes_orchestrators(tmp_path: Path) -> None:
    """Orchestrators are skill-agnostic; they install regardless of --only mode."""
    result = _run_install(tmp_path, "--only", "workforce")
    assert result.returncode == 0
    agents = tmp_path / ".claude" / "agents"
    for name in ["intent-validator.md", "conductor.md", "alignment-guard.md"]:
        assert (agents / name).is_file()


def test_install_uninstalls_orchestrators(tmp_path: Path) -> None:
    install_result = _run_install(tmp_path)
    assert install_result.returncode == 0
    uninstall_result = _run_install(tmp_path, "--uninstall")
    assert uninstall_result.returncode == 0
    agents = tmp_path / ".claude" / "agents"
    for name in ["intent-validator.md", "conductor.md", "alignment-guard.md"]:
        assert not (agents / name).exists(), f"uninstall left {name} behind"


# ── 3. migrate_legacy_orchestrators.py ───────────────────────────────────────


def _run_migrate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(MIGRATE_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _seed_legacy_install(target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename in [
        "foundation-orchestrator.md",
        "workforce-orchestrator.md",
        "vision-keeper.md",
        "output-validator.md",
    ]:
        (target_dir / filename).write_text(
            f"---\nname: {filename.replace('.md','')}\n"
            f"description: Original legacy agent.\nmodel: sonnet\n---\n\n# Body\n"
        )


def test_migrate_dry_run_does_not_modify_files(tmp_path: Path) -> None:
    target = tmp_path / "agents"
    _seed_legacy_install(target)
    before = (target / "foundation-orchestrator.md").read_text()
    result = _run_migrate("--target-dir", str(target))
    assert result.returncode == 0
    assert "would rewrite" in result.stdout.lower()
    after = (target / "foundation-orchestrator.md").read_text()
    assert before == after


def test_migrate_apply_rewrites_files(tmp_path: Path) -> None:
    target = tmp_path / "agents"
    _seed_legacy_install(target)
    result = _run_migrate("--target-dir", str(target), "--apply")
    assert result.returncode == 0
    body = (target / "foundation-orchestrator.md").read_text()
    assert "DEPRECATED" in body
    assert "conductor" in body
    assert "workforce-cc-shim:v1" in body


def test_migrate_creates_backup(tmp_path: Path) -> None:
    target = tmp_path / "agents"
    _seed_legacy_install(target)
    original = (target / "foundation-orchestrator.md").read_text()
    _run_migrate("--target-dir", str(target), "--apply")
    backup = target / ".workforce-backup" / "foundation-orchestrator.md.bak"
    assert backup.exists()
    assert backup.read_text() == original


def test_migrate_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "agents"
    _seed_legacy_install(target)
    _run_migrate("--target-dir", str(target), "--apply")
    body_after_first = (target / "foundation-orchestrator.md").read_text()
    result = _run_migrate("--target-dir", str(target), "--apply")
    assert result.returncode == 0
    assert "already shimmed" in result.stdout.lower()
    body_after_second = (target / "foundation-orchestrator.md").read_text()
    assert body_after_first == body_after_second


def test_migrate_restore_restores_originals(tmp_path: Path) -> None:
    target = tmp_path / "agents"
    _seed_legacy_install(target)
    original = (target / "foundation-orchestrator.md").read_text()
    _run_migrate("--target-dir", str(target), "--apply")
    restored = _run_migrate("--target-dir", str(target), "--restore")
    assert restored.returncode == 0
    assert (target / "foundation-orchestrator.md").read_text() == original


def test_migrate_skips_files_not_present(tmp_path: Path) -> None:
    target = tmp_path / "agents"
    target.mkdir()
    # Only one of the four legacy agents is installed.
    (target / "foundation-orchestrator.md").write_text(
        "---\nname: foundation-orchestrator\ndescription: x\nmodel: sonnet\n---\n# Body\n"
    )
    result = _run_migrate("--target-dir", str(target), "--apply")
    assert result.returncode == 0
    # Only one rewrite should happen.
    assert "Rewrote 1" in result.stdout or "rewrote 1" in result.stdout.lower() or "1 legacy agent" in result.stdout
    assert "not installed" in result.stdout.lower()


def test_migrate_rejects_nonexistent_target(tmp_path: Path) -> None:
    nonexistent = tmp_path / "does-not-exist"
    result = _run_migrate("--target-dir", str(nonexistent))
    assert result.returncode != 0
