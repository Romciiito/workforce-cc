"""Tests for install.sh --profile and the hook dispatcher.

Existing test_install_script.py asserts the legacy --only behavior — those
tests must keep passing. This file adds coverage for the new --profile
flag, --dry-run, the hook dispatcher, and the per-profile beacon file.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"
DISPATCHER = REPO_ROOT / "hooks" / "dispatcher.sh"


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


# ── Profile JSON validation ────────────────────────────────────────────────


@pytest.mark.parametrize("name", ["full", "foundation", "workforce", "minimal"])
def test_profile_json_is_well_formed(name: str) -> None:
    path = REPO_ROOT / "profiles" / f"{name}.json"
    assert path.exists(), f"profiles/{name}.json missing"
    data = json.loads(path.read_text())
    assert data["name"] == name
    assert isinstance(data["skills"], list)
    assert isinstance(data["agent_packs"], list)


def test_minimal_profile_has_no_agents_and_no_hooks() -> None:
    data = json.loads((REPO_ROOT / "profiles" / "minimal.json").read_text())
    assert data["agent_packs"] == []
    assert data.get("hooks", []) == []
    assert data["skills"] == ["sync"]


def test_foundation_profile_excludes_workforce_pack() -> None:
    data = json.loads((REPO_ROOT / "profiles" / "foundation.json").read_text())
    assert "workforce" not in data["agent_packs"]
    assert "foundation" in data["agent_packs"]
    assert "_shared" in data["agent_packs"]
    assert "orchestrators" in data["agent_packs"]


def test_workforce_profile_excludes_foundation_pack() -> None:
    data = json.loads((REPO_ROOT / "profiles" / "workforce.json").read_text())
    assert "foundation" not in data["agent_packs"]
    assert "workforce" in data["agent_packs"]


# ── --profile install behavior ──────────────────────────────────────────────


def test_install_profile_minimal(tmp_path: Path) -> None:
    """--profile minimal → only sync skill, no agent packs."""
    result = _run_install(tmp_path, "--profile", "minimal")
    assert result.returncode == 0, result.stderr or result.stdout

    skills = tmp_path / ".claude" / "skills"
    agents = tmp_path / ".claude" / "agents"
    assert (skills / "sync").is_symlink()
    assert not (skills / "foundation").exists()
    assert not (skills / "workforce").exists()
    # Empty agent_packs → nothing in agents/
    if agents.exists():
        assert list(agents.iterdir()) == []


def test_install_profile_foundation(tmp_path: Path) -> None:
    """--profile foundation → foundation+sync skills, _shared+orchestrators+foundation packs."""
    result = _run_install(tmp_path, "--profile", "foundation")
    assert result.returncode == 0, result.stderr or result.stdout

    skills = tmp_path / ".claude" / "skills"
    agents = tmp_path / ".claude" / "agents"
    assert (skills / "foundation").is_symlink()
    assert (skills / "sync").is_symlink()
    assert not (skills / "workforce").exists()

    # Foundation pack agents present
    assert (agents / "idea-refiner.md").is_file()
    assert (agents / "foundation-orchestrator.md").is_file()
    # Workforce pack NOT present
    assert not (agents / "scanner.md").exists()
    assert not (agents / "vision-keeper.md").exists()
    # Orchestrators always present
    assert (agents / "intent-validator.md").is_file()
    assert (agents / "conductor.md").is_file()


def test_install_profile_workforce(tmp_path: Path) -> None:
    result = _run_install(tmp_path, "--profile", "workforce")
    assert result.returncode == 0

    skills = tmp_path / ".claude" / "skills"
    agents = tmp_path / ".claude" / "agents"
    assert (skills / "workforce").is_symlink()
    assert not (skills / "foundation").exists()
    assert (agents / "scanner.md").is_file()
    assert not (agents / "idea-refiner.md").exists()
    assert (agents / "intent-validator.md").is_file()


def test_install_profile_full_matches_legacy_both(tmp_path: Path) -> None:
    """--profile full should produce the same install as legacy default (--only both)."""
    result = _run_install(tmp_path, "--profile", "full")
    assert result.returncode == 0

    skills = tmp_path / ".claude" / "skills"
    agents = tmp_path / ".claude" / "agents"
    for s in ["foundation", "workforce", "sync"]:
        assert (skills / s).is_symlink()
    for a in ["intent-validator.md", "conductor.md", "alignment-guard.md", "scanner.md", "idea-refiner.md"]:
        assert (agents / a).is_file()


def test_install_profile_writes_beacon(tmp_path: Path) -> None:
    """--profile <name> must write ~/.workforce-profile so the hook dispatcher knows the profile."""
    result = _run_install(tmp_path, "--profile", "foundation")
    assert result.returncode == 0
    beacon = tmp_path / ".workforce-profile"
    assert beacon.exists()
    assert beacon.read_text().strip() == "foundation"


def test_install_legacy_only_does_not_write_beacon(tmp_path: Path) -> None:
    """Without --profile, no beacon — legacy installs use the dispatcher's 'full' fallback."""
    result = _run_install(tmp_path)
    assert result.returncode == 0
    assert not (tmp_path / ".workforce-profile").exists()


def test_install_unknown_profile_fails(tmp_path: Path) -> None:
    result = _run_install(tmp_path, "--profile", "no-such-profile")
    assert result.returncode != 0
    assert "profile not found" in result.stdout.lower() or "profile not found" in result.stderr.lower()


# ── --dry-run ────────────────────────────────────────────────────────────────


def test_install_dry_run_does_not_write(tmp_path: Path) -> None:
    result = _run_install(tmp_path, "--profile", "minimal", "--dry-run")
    assert result.returncode == 0
    assert "Dry-run" in result.stdout
    # Nothing under ~/.claude/ should have been created.
    assert not (tmp_path / ".claude" / "skills" / "sync").exists()
    assert not (tmp_path / ".workforce-profile").exists()


def test_install_dry_run_lists_planned_actions(tmp_path: Path) -> None:
    result = _run_install(tmp_path, "--profile", "foundation", "--dry-run")
    assert result.returncode == 0
    assert "would" in result.stdout.lower()


# ── Uninstall removes the beacon ─────────────────────────────────────────────


def test_uninstall_removes_profile_beacon(tmp_path: Path) -> None:
    install = _run_install(tmp_path, "--profile", "foundation")
    assert install.returncode == 0
    assert (tmp_path / ".workforce-profile").exists()

    uninstall = _run_install(tmp_path, "--uninstall")
    assert uninstall.returncode == 0
    assert not (tmp_path / ".workforce-profile").exists()


# ── Hook dispatcher ──────────────────────────────────────────────────────────


def _run_dispatcher(home: Path, env_extra: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env.update(env_extra)
    return subprocess.run(
        ["bash", str(DISPATCHER), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_dispatcher_list_uses_profile_beacon(tmp_path: Path) -> None:
    """When ~/.workforce-profile = 'foundation', dispatcher.sh list returns governance only."""
    (tmp_path / ".workforce-profile").write_text("foundation\n")
    result = _run_dispatcher(tmp_path, {}, "list")
    assert result.returncode == 0
    enabled = result.stdout.strip().splitlines()
    assert "governance" in enabled


def test_dispatcher_list_minimal_profile_returns_no_hooks(tmp_path: Path) -> None:
    (tmp_path / ".workforce-profile").write_text("minimal\n")
    result = _run_dispatcher(tmp_path, {}, "list")
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_dispatcher_list_full_profile_returns_all_hooks(tmp_path: Path) -> None:
    (tmp_path / ".workforce-profile").write_text("full\n")
    result = _run_dispatcher(tmp_path, {}, "list")
    assert result.returncode == 0
    enabled = set(result.stdout.strip().splitlines())
    assert "governance" in enabled
    assert "config-protection" in enabled


def test_dispatcher_disabled_hooks_env_filters(tmp_path: Path) -> None:
    (tmp_path / ".workforce-profile").write_text("full\n")
    result = _run_dispatcher(
        tmp_path,
        {"WORKFORCE_DISABLED_HOOKS": "config-protection"},
        "list",
    )
    assert result.returncode == 0
    enabled = set(result.stdout.strip().splitlines())
    assert "governance" in enabled
    assert "config-protection" not in enabled


def test_dispatcher_fire_unknown_hook_is_silent(tmp_path: Path) -> None:
    """Firing a hook that's not enabled / not present must be a silent no-op (exit 0)."""
    (tmp_path / ".workforce-profile").write_text("minimal\n")
    result = _run_dispatcher(tmp_path, {}, "fire", "governance", "agent", "event")
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_dispatcher_fire_governance_writes_jsonl(tmp_path: Path) -> None:
    """When governance is enabled and telemetry is on, fire writes a JSONL line."""
    (tmp_path / ".workforce-profile").write_text("full\n")
    project = tmp_path / "project"
    project.mkdir()
    mem = project / ".foundation-memory"
    mem.mkdir()  # opt-in to telemetry

    result = _run_dispatcher(
        tmp_path,
        {"WORKFORCE_PROJECT_DIR": str(project)},
        "fire",
        "governance",
        "alignment-guard",
        "block",
        "HIGH: scope creep",
    )
    assert result.returncode == 0, result.stderr

    log = mem / "governance.jsonl"
    assert log.exists()
    record = json.loads(log.read_text().strip())
    assert record["agent"] == "alignment-guard"
    assert record["event"] == "block"
    assert "scope creep" in record["reason"]


def test_dispatcher_fire_governance_telemetry_opt_out(tmp_path: Path) -> None:
    """WORKFORCE_TELEMETRY=off must prevent the governance hook from writing."""
    (tmp_path / ".workforce-profile").write_text("full\n")
    project = tmp_path / "project"
    project.mkdir()

    result = _run_dispatcher(
        tmp_path,
        {
            "WORKFORCE_PROJECT_DIR": str(project),
            "WORKFORCE_TELEMETRY": "off",
            "WORKFORCE_MULTI_TERMINAL": "1",
        },
        "fire",
        "governance",
        "alignment-guard",
        "pass",
    )
    assert result.returncode == 0
    assert not (project / ".foundation-memory").exists()


def test_dispatcher_fire_config_protection_blocks_eslintrc(tmp_path: Path) -> None:
    (tmp_path / ".workforce-profile").write_text("full\n")
    result = _run_dispatcher(
        tmp_path,
        {},
        "fire",
        "config-protection",
        ".eslintrc.json",
    )
    assert result.returncode != 0
    assert "config-protection: blocking write" in result.stderr


def test_dispatcher_fire_config_protection_allows_normal_files(tmp_path: Path) -> None:
    (tmp_path / ".workforce-profile").write_text("full\n")
    result = _run_dispatcher(
        tmp_path,
        {},
        "fire",
        "config-protection",
        "src/auth.py",
    )
    assert result.returncode == 0


def test_dispatcher_fire_config_protection_allows_with_override(tmp_path: Path) -> None:
    (tmp_path / ".workforce-profile").write_text("full\n")
    result = _run_dispatcher(
        tmp_path,
        {"WORKFORCE_ALLOW_CONFIG_EDIT": "1"},
        "fire",
        "config-protection",
        ".eslintrc.json",
    )
    assert result.returncode == 0


def test_dispatcher_resolves_profile_via_env_var_override(tmp_path: Path) -> None:
    """WORKFORCE_HOOK_PROFILE must override the beacon file."""
    (tmp_path / ".workforce-profile").write_text("foundation\n")
    result = _run_dispatcher(tmp_path, {"WORKFORCE_HOOK_PROFILE": "minimal"}, "list")
    assert result.returncode == 0
    assert result.stdout.strip() == ""
