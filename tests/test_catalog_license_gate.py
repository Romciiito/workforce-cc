"""Tests for the license-allowlist gate added to catalog_check.py (Chunk 28).

Pattern from build-your-own-x's curation discipline: every entry's
upstream license must be redistributable. The gate runs as part of
`catalog_check.py validate`, ahead of the structural checks.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "catalog_check.py"
CATALOG_DIR = REPO_ROOT / "catalogs" / "ecc"


def _load():
    name = "catalog_check"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _run_validate(catalog: str = "ecc") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "validate", "--catalog", catalog],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


@pytest.fixture
def isolated_catalog(tmp_path: Path):
    """Snapshot + restore catalogs/ecc/ around the test."""
    backup = tmp_path / "backup"
    shutil.copytree(CATALOG_DIR, backup)
    try:
        yield
    finally:
        shutil.rmtree(CATALOG_DIR)
        shutil.copytree(backup, CATALOG_DIR)


# ── allowlist constant ──────────────────────────────────────────────────────


def test_allowlist_includes_common_redistributable_licenses() -> None:
    cc = _load()
    for license_name in ["MIT", "Apache-2.0", "BSD-3-Clause", "CC0-1.0", "ISC"]:
        assert license_name in cc.ALLOWED_LICENSES


def test_allowlist_excludes_non_redistributable_licenses() -> None:
    cc = _load()
    for license_name in ["GPL-3.0", "AGPL-3.0", "proprietary", "All-Rights-Reserved", "(c)"]:
        assert license_name not in cc.ALLOWED_LICENSES


# ── seed catalog passes ─────────────────────────────────────────────────────


def test_seed_ecc_catalog_passes_license_gate() -> None:
    """The catalogs/ecc/ that ships in the repo must pass the gate."""
    result = _run_validate("ecc")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VALIDATE OK" in result.stdout


# ── failure modes ───────────────────────────────────────────────────────────


def test_validate_fails_when_license_missing(isolated_catalog) -> None:
    """If source.license is missing from index.json, validation must fail."""
    index = json.loads((CATALOG_DIR / "index.json").read_text())
    del index["source"]["license"]
    (CATALOG_DIR / "index.json").write_text(json.dumps(index, indent=2))

    result = _run_validate()
    assert result.returncode != 0
    assert "license" in result.stdout.lower()


def test_validate_fails_on_disallowed_license(isolated_catalog) -> None:
    """A license not on the allowlist must trigger validation failure."""
    index = json.loads((CATALOG_DIR / "index.json").read_text())
    index["source"]["license"] = "GPL-3.0"
    (CATALOG_DIR / "index.json").write_text(json.dumps(index, indent=2))

    result = _run_validate()
    assert result.returncode != 0
    assert "GPL-3.0" in result.stdout
    assert "allowlist" in result.stdout.lower()


def test_validate_fails_when_LICENSE_file_missing(isolated_catalog) -> None:
    """Missing LICENSE file alongside the index must fail."""
    (CATALOG_DIR / "LICENSE").unlink()
    result = _run_validate()
    assert result.returncode != 0
    assert "LICENSE" in result.stdout


def test_validate_json_output_includes_license_failures(isolated_catalog) -> None:
    """The --json mode must surface license failures in the failures list."""
    index = json.loads((CATALOG_DIR / "index.json").read_text())
    index["source"]["license"] = "Proprietary"
    (CATALOG_DIR / "index.json").write_text(json.dumps(index, indent=2))

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json", "validate", "--catalog", "ecc"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any("license" in f.lower() or "Proprietary" in f for f in payload["failures"])


def test_check_license_helper_returns_empty_for_valid_catalog(isolated_catalog) -> None:
    """Direct unit test of _check_license: valid catalog → no failures."""
    cc = _load()
    index = json.loads((CATALOG_DIR / "index.json").read_text())
    failures = cc._check_license("ecc", index)
    assert failures == []


def test_check_license_helper_lists_allowed_when_rejecting(isolated_catalog) -> None:
    """When license is on the disallowed list, the error message lists allowed
    licenses so the operator knows what to use."""
    cc = _load()
    bad_index = {
        "source": {"license": "WTFPL", "repo": "x/y"},
        "entries": [],
    }
    failures = cc._check_license("ecc", bad_index)
    assert any("WTFPL" in f for f in failures)
    assert any("Allowed" in f or "allowlist" in f.lower() for f in failures)
