"""Tests for skills/_backbone/.

The backbone is a documentation skill, not a runtime skill. These tests
assert structural invariants: BACKBONE.md references the three orchestrator
roles, the four templates exist with their required headings, and the
documented schemas match what the artifact contract enforces.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKBONE_DIR = REPO_ROOT / "skills" / "_backbone"


def _load(name: str) -> str:
    path = BACKBONE_DIR / name
    assert path.exists(), f"missing backbone file: {path}"
    return path.read_text()


def test_backbone_md_exists() -> None:
    assert (BACKBONE_DIR / "BACKBONE.md").exists()


def test_backbone_md_references_three_orchestrator_roles() -> None:
    body = _load("BACKBONE.md")
    for role in ["intent-validator", "conductor", "alignment-guard"]:
        assert role in body, f"BACKBONE.md must reference {role}"


def test_backbone_md_references_conductor_submodes() -> None:
    body = _load("BACKBONE.md")
    for sub in ["dispatch", "monitor", "integrate"]:
        assert sub in body, f"BACKBONE.md must reference conductor sub-mode: {sub}"


def test_backbone_md_references_alignment_guard_modes() -> None:
    body = _load("BACKBONE.md")
    for mode in ["vision", "cross-check"]:
        assert mode in body, f"BACKBONE.md must reference alignment-guard mode: {mode}"


def test_backbone_md_references_engineer_pools() -> None:
    body = _load("BACKBONE.md")
    assert "engineer pool" in body.lower()
    # Both /foundation and /workforce engineer pools must be mentioned.
    assert "/foundation" in body
    assert "/workforce" in body


def test_backbone_md_references_artifact_contract() -> None:
    body = _load("BACKBONE.md")
    assert "artifact-contract.md" in body or "docs/artifact-contract.md" in body


def test_backbone_md_documents_workforce_dir_separation() -> None:
    body = _load("BACKBONE.md")
    assert ".workforce/" in body
    assert "project root" in body


def test_intent_template_has_six_required_sections() -> None:
    body = _load("intent.template.md")
    for heading in [
        "## What it is",
        "## Who it's for",
        "## Concrete success",
        "## Constraints",
        "## Out of scope",
        "## Open questions",
    ]:
        assert heading in body, f"intent.template.md missing heading: {heading}"


def test_dispatch_template_has_six_required_task_fields() -> None:
    body = _load("dispatch.template.md")
    for field in ["Territory", "Inputs", "Outputs", "Verification", "Success criteria", "Escalation"]:
        assert field in body, f"dispatch.template.md missing required task field: {field}"


def test_dispatch_template_documents_iteration_cap() -> None:
    body = _load("dispatch.template.md")
    assert "Iteration" in body
    # 3-iteration cap inherited from agent-dispatch convergence loop.
    assert "3" in body or "max 3" in body.lower()


def test_integration_template_has_required_sections() -> None:
    body = _load("integration.template.md")
    for heading in [
        "## Run summary",
        "## Artifacts produced",
        "## Cross-cuts",
        "## Blocked items",
        "## Next dispatch",
    ]:
        assert heading in body, f"integration.template.md missing heading: {heading}"


def test_alignment_report_template_has_three_status_values() -> None:
    body = _load("alignment-report.template.md")
    for status in ["PASS", "PASS-WITH-NOTES", "BLOCK"]:
        assert status in body


def test_alignment_report_template_has_self_critique_checklist() -> None:
    body = _load("alignment-report.template.md")
    assert "Self-critique" in body or "self-critique" in body
    # Must mention the canonical checks.
    for check in ["Verification avoidance", "first 80%", "Confirmation bias", "Three-reviewer"]:
        assert check in body, f"alignment-report.template.md self-critique missing: {check}"


def test_alignment_report_template_documents_severity_rules() -> None:
    body = _load("alignment-report.template.md")
    # The mechanical mapping must be present.
    assert "HIGH" in body and "MEDIUM" in body and "LOW" in body
    assert "BLOCK" in body
    assert "PASS-WITH-NOTES" in body
