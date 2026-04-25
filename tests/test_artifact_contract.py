"""Tests for docs/artifact-contract.md.

These tests parse the contract document and assert structural invariants.
The contract is the single source of truth for every artifact in the
workforce-cc system; new artifacts must be declared here before being
referenced anywhere else.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT = REPO_ROOT / "docs" / "artifact-contract.md"

# Match `### \`<name>\`` headings — these are the artifact declarations.
ARTIFACT_HEADING_RE = re.compile(r"^### `([^`]+)`\s*$", re.MULTILINE)
OWNER_LINE_RE = re.compile(r"^- \*\*Owner\*\*:\s*(.+)$", re.MULTILINE)
READERS_LINE_RE = re.compile(r"^- \*\*Readers\*\*:\s*(.+)$", re.MULTILINE)


def _contract_text() -> str:
    return CONTRACT.read_text()


def _split_into_artifact_sections() -> list[tuple[str, str]]:
    """Return [(artifact_name, section_body), ...] from the contract."""
    text = _contract_text()
    matches = list(ARTIFACT_HEADING_RE.finditer(text))
    sections = []
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((name, text[start:end]))
    return sections


def test_contract_file_exists() -> None:
    assert CONTRACT.exists(), "docs/artifact-contract.md is required"


def test_contract_declares_minimum_required_artifacts() -> None:
    """All four orchestration artifacts plus the engineer essentials must appear."""
    sections = _split_into_artifact_sections()
    names = {name for name, _ in sections}
    required = {
        "intent.md",
        "dispatch.md",
        "integration.md",
        "alignment-report.md",
        "BLOCKED.md",
        "status/<engineer>.json",
        "runs/<ts>/<engineer>/approach.md",
        "brainstorm.md",
        "spec.md",
        "architecture.md",
        "stack-decision.md",
        "validation-report.md",
        "requirements.md",
        "security-model.md",
        "market-analysis.md",
        "workplan.md",
        "vision.md",
        "WORKFORCE.md",
        "project-snapshot.md",
        "decisions.md",
        "claude-rules.md",
    }
    missing = required - names
    assert not missing, f"Contract missing required artifacts: {sorted(missing)}"


def test_every_artifact_has_owner_and_readers() -> None:
    """Single-writer invariant: every artifact must declare exactly one Owner and a Readers line."""
    sections = _split_into_artifact_sections()
    failures = []
    for name, body in sections:
        if not OWNER_LINE_RE.search(body):
            failures.append(f"{name}: missing Owner line")
        if not READERS_LINE_RE.search(body):
            failures.append(f"{name}: missing Readers line")
    assert not failures, "\n".join(failures)


def test_orchestration_artifacts_documented_under_workforce() -> None:
    """The four orchestration artifacts must reference .workforce/ in the directory layout."""
    text = _contract_text()
    layout_block = re.search(
        r"## Project-side directory layout.*?(?=\n## )", text, re.DOTALL
    )
    assert layout_block, "Project-side directory layout section missing"
    block = layout_block.group(0)
    for artifact in ["intent.md", "dispatch.md", "integration.md", "alignment-report.md"]:
        assert artifact in block, f"{artifact} not shown in directory layout"
    assert ".workforce/" in block


def test_intent_md_required_headings_listed() -> None:
    """intent.md must list six specific section headings."""
    sections = dict(_split_into_artifact_sections())
    body = sections["intent.md"]
    for heading in [
        "## What it is",
        "## Who it's for",
        "## Concrete success",
        "## Constraints",
        "## Out of scope",
        "## Open questions",
    ]:
        assert heading in body, f"intent.md schema missing heading: {heading}"


def test_alignment_report_status_values_documented() -> None:
    sections = dict(_split_into_artifact_sections())
    body = sections["alignment-report.md"]
    for status in ["PASS", "PASS-WITH-NOTES", "BLOCK"]:
        assert status in body, f"alignment-report.md must document status: {status}"


def test_status_file_schema_documents_required_fields() -> None:
    sections = dict(_split_into_artifact_sections())
    body = sections["status/<engineer>.json"]
    for field in ["state", "ts", "engineer", "run_id", "artifacts"]:
        assert field in body, f"status/<engineer>.json schema missing field: {field}"
    for state in ["RUNNING", "BLOCKED", "DONE"]:
        assert state in body, f"status/<engineer>.json must document state: {state}"


def test_no_duplicate_artifact_declarations() -> None:
    """Each artifact must appear exactly once in the contract."""
    sections = _split_into_artifact_sections()
    names = [name for name, _ in sections]
    duplicates = [n for n in names if names.count(n) > 1]
    assert not duplicates, f"Duplicate artifact declarations: {set(duplicates)}"
