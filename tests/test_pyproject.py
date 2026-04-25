"""Tests for pyproject.toml (Chunk 38).

The repo ships as a script set + skill catalog, but adopts pyproject.toml
to declare metadata + dev dependencies so:
  - CI can use `pip install -e ".[test]"` instead of bare `pip install
    pytest jinja2`.
  - setup-python's `cache: pip` works (it hashes pyproject.toml).
  - Python tooling (ruff/mypy/etc.) can be added to extras when adopted.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _load_pyproject() -> dict:
    if sys.version_info >= (3, 11):
        import tomllib
        return tomllib.loads(PYPROJECT.read_text())
    pytest.skip("tomllib requires Python 3.11+")


def test_pyproject_exists() -> None:
    assert PYPROJECT.exists()


def test_pyproject_is_valid_toml() -> None:
    _load_pyproject()  # raises on invalid TOML


def test_project_metadata_has_required_fields() -> None:
    project = _load_pyproject()["project"]
    assert project["name"] == "workforce-cc"
    assert "version" in project
    assert "description" in project
    assert "requires-python" in project
    # Must align with the CI matrix (3.11 / 3.12 / 3.13).
    assert ">=3.11" in project["requires-python"]


def test_runtime_dependencies_include_jinja2() -> None:
    """scaffold.py and harness_install.py both need Jinja2."""
    deps = _load_pyproject()["project"]["dependencies"]
    assert any("Jinja2" in d or "jinja2" in d for d in deps)


def test_test_extra_includes_pytest() -> None:
    extras = _load_pyproject()["project"]["optional-dependencies"]
    assert "test" in extras
    assert any("pytest" in d for d in extras["test"])


def test_dev_extra_inherits_test() -> None:
    extras = _load_pyproject()["project"]["optional-dependencies"]
    assert "dev" in extras
    # Dev should pull in the test extra so `pip install -e ".[dev]"` is enough.
    assert any("workforce-cc[test]" in d or "test" in d for d in extras["dev"])


def test_pytest_config_mirrors_pytest_ini() -> None:
    """pyproject.toml's [tool.pytest.ini_options] should match pytest.ini —
    the project ships with both so either source works."""
    pyproj = _load_pyproject()
    assert "tool" in pyproj
    assert "pytest" in pyproj["tool"]
    pytest_cfg = pyproj["tool"]["pytest"]["ini_options"]
    assert "tests" in pytest_cfg["testpaths"]
    # filterwarnings must include the existing 'error' default + jinja2 ignore.
    assert any("error" in fw for fw in pytest_cfg["filterwarnings"])


def test_setuptools_packages_is_empty() -> None:
    """The repo ships as a script set, not a Python package — declaring
    packages = [] tells setuptools not to look for importable packages
    (otherwise it tries to package agents/, catalogs/, etc., which fails)."""
    pyproj = _load_pyproject()
    assert pyproj["tool"]["setuptools"]["packages"] == []


def test_classifiers_match_supported_python_versions() -> None:
    classifiers = _load_pyproject()["project"]["classifiers"]
    for version in ["3.11", "3.12", "3.13"]:
        assert any(version in c for c in classifiers), f"missing classifier for Python {version}"
    assert any("MIT" in c for c in classifiers)


def test_readme_and_license_referenced() -> None:
    project = _load_pyproject()["project"]
    assert project["readme"] == "README.md"
    assert "LICENSE" in str(project["license"])
    # And the actual files exist.
    assert (REPO_ROOT / "README.md").exists()
    assert (REPO_ROOT / "LICENSE").exists()
