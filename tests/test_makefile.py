"""Tests for Makefile (Chunk 39).

The Makefile is convenience, not magic — but its targets must:
  1. Exist (every documented target is in the file).
  2. Be syntactically valid (`make -n` doesn't fail).
  3. Have a help description (so `make help` is useful).
  4. Match the operations documented in README.md.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = REPO_ROOT / "Makefile"

# Every target documented in the file via the "## description" pattern.
EXPECTED_TARGETS = {
    "help",
    "test", "test-fast", "test-quiet",
    "install-dev", "install", "install-all", "install-minimal",
    "install-dry-run", "uninstall",
    "catalog-sync", "catalog-validate", "catalog-list", "catalog-drift",
    "mcp-list",
    "harness-apply", "harness-apply-all",
    "lint", "lint-bash", "lint-py",
    "clean",
    "status",
}


def _body() -> str:
    return MAKEFILE.read_text()


def test_makefile_exists() -> None:
    assert MAKEFILE.exists()


def test_make_is_available() -> None:
    """If `make` isn't on the path, the Makefile-driven tests below skip."""
    assert shutil.which("make") is not None, "make not installed in test env"


def test_default_goal_is_help() -> None:
    """Running `make` without a target should show help, not silently no-op."""
    body = _body()
    assert ".DEFAULT_GOAL := help" in body or ".DEFAULT_GOAL = help" in body


@pytest.mark.parametrize("target", sorted(EXPECTED_TARGETS))
def test_target_declared_with_description(target: str) -> None:
    """Every target in EXPECTED_TARGETS must have a `## description` comment."""
    body = _body()
    pattern = re.compile(rf"^{re.escape(target)}:.*?##\s+\S", re.MULTILINE)
    assert pattern.search(body), (
        f"target {target!r} missing or has no '## description' comment in Makefile"
    )


@pytest.mark.parametrize("target", sorted(EXPECTED_TARGETS))
def test_target_in_phony_declaration(target: str) -> None:
    """Each target should be marked .PHONY (it's a task, not a real file)."""
    body = _body()
    # .PHONY: <target> on its own line, allowing multiple targets per line.
    pattern = re.compile(rf"^\.PHONY:.*?\b{re.escape(target)}\b", re.MULTILINE)
    assert pattern.search(body), f"target {target!r} not declared .PHONY"


def test_make_help_lists_all_targets() -> None:
    """`make help` must surface every target in EXPECTED_TARGETS."""
    result = subprocess.run(
        ["make", "help"], capture_output=True, text=True, cwd=REPO_ROOT, check=False,
    )
    assert result.returncode == 0, result.stderr
    output = result.stdout
    for target in sorted(EXPECTED_TARGETS):
        assert target in output, f"`make help` did not list target: {target}"


def test_make_dry_run_is_clean() -> None:
    """`make -n test` must print the test command without errors."""
    result = subprocess.run(
        ["make", "-n", "test"], capture_output=True, text=True, cwd=REPO_ROOT, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "pytest" in result.stdout


def test_make_lint_py_succeeds() -> None:
    """`make lint-py` smoke-compiles every script — should be fast and clean."""
    result = subprocess.run(
        ["make", "lint-py"], capture_output=True, text=True, cwd=REPO_ROOT, check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    # Spot-check a few script names appear.
    for script in ["pipeline_runner.py", "scaffold.py", "harness_install.py"]:
        assert script in result.stdout


def test_make_catalog_validate_succeeds() -> None:
    """`make catalog-validate` must run cleanly against the seed ecc catalog."""
    result = subprocess.run(
        ["make", "catalog-validate"], capture_output=True, text=True, cwd=REPO_ROOT, check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_make_mcp_list_succeeds() -> None:
    result = subprocess.run(
        ["make", "mcp-list"], capture_output=True, text=True, cwd=REPO_ROOT, check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "github" in result.stdout


def test_catalog_sync_target_requires_ecc_path() -> None:
    """Running `make catalog-sync` without ECC_PATH set must fail loudly."""
    import os
    env = os.environ.copy()
    env.pop("ECC_PATH", None)
    result = subprocess.run(
        ["make", "catalog-sync"], capture_output=True, text=True, cwd=REPO_ROOT, env=env, check=False,
    )
    assert result.returncode != 0
    assert "ECC_PATH" in result.stdout + result.stderr
