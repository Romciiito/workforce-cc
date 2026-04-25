"""Tests for docs/decisions/ ADR catalog (Chunk 26).

The ADRs are documentation of architectural decisions made during the
rebuild. These tests assert structural invariants — README index matches
the file set, every ADR has the required sections, IDs are sequential.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DECISIONS_DIR = REPO_ROOT / "docs" / "decisions"

ADR_FILE_RE = re.compile(r"^(\d{3})-[a-z0-9-]+\.md$")
REQUIRED_SECTIONS = ["## Context", "## Decision", "## Consequences", "## Alternatives considered"]


def _adr_files() -> list[Path]:
    return sorted(p for p in DECISIONS_DIR.glob("*.md") if ADR_FILE_RE.match(p.name))


def test_decisions_dir_exists() -> None:
    assert DECISIONS_DIR.is_dir()


def test_readme_indexes_every_adr() -> None:
    readme = (DECISIONS_DIR / "README.md").read_text()
    for adr in _adr_files():
        assert adr.name in readme, f"docs/decisions/README.md missing entry for {adr.name}"


def test_readme_lists_status_for_every_adr() -> None:
    readme = (DECISIONS_DIR / "README.md").read_text()
    table_section = readme[readme.index("## Catalog"):]
    for adr in _adr_files():
        # Status column must be present (Accepted / Superseded / Reverted).
        adr_line = next(line for line in table_section.splitlines() if adr.name in line)
        assert any(status in adr_line for status in ["Accepted", "Superseded", "Reverted"]), (
            f"README index for {adr.name} missing a status"
        )


@pytest.mark.parametrize("adr_path", _adr_files())
def test_adr_has_required_sections(adr_path: Path) -> None:
    body = adr_path.read_text()
    for section in REQUIRED_SECTIONS:
        assert section in body, f"{adr_path.name} missing required section: {section}"


@pytest.mark.parametrize("adr_path", _adr_files())
def test_adr_has_status_line(adr_path: Path) -> None:
    body = adr_path.read_text()
    assert re.search(r"\*\*Status\*\*:.*?(Accepted|Superseded|Reverted)", body), (
        f"{adr_path.name} missing **Status**: line"
    )


@pytest.mark.parametrize("adr_path", _adr_files())
def test_adr_lists_sources(adr_path: Path) -> None:
    """Every ADR cites the borrowed patterns it draws on (or notes 'original')."""
    body = adr_path.read_text()
    assert "## Sources" in body or "Sources" in body, (
        f"{adr_path.name} should have a ## Sources section attributing borrowed patterns"
    )


def test_adr_ids_are_sequential() -> None:
    files = _adr_files()
    expected = [f"{i:03d}" for i in range(1, len(files) + 1)]
    actual = [ADR_FILE_RE.match(p.name).group(1) for p in files]
    assert expected == actual, (
        f"ADR ids must be sequential 001..{len(files):03d}; got {actual}"
    )


def test_at_least_eight_adrs_exist() -> None:
    """Chunk 26 establishes the catalog with eight ADRs covering the load-bearing
    architectural choices made over Chunks 1-25."""
    assert len(_adr_files()) >= 8


def test_first_adr_is_three_orchestrator_roles() -> None:
    """ADR 001 is the central architectural choice; the catalog leads with it."""
    adr_001 = DECISIONS_DIR / "001-three-orchestrator-roles.md"
    assert adr_001.exists()
    body = adr_001.read_text()
    for role in ["Intent Validator", "Conductor", "Alignment Guard"]:
        assert role in body


def test_adr_006_documents_engineer_with_judgment() -> None:
    adr = DECISIONS_DIR / "006-engineer-with-judgment.md"
    assert adr.exists()
    body = adr.read_text()
    # Must reference the three sources we explicitly borrowed from.
    for source in ["claude-code-system-prompts", "agent-dispatch", "leaked Claude Code"]:
        assert source in body, f"ADR 006 missing source citation: {source}"
