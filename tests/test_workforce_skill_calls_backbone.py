"""Tests that skills/workforce/SKILL.md correctly delegates to the backbone.

After Chunk 7, /workforce has Phase 0.5 (conditional intent-validator)
between scan and orchestrator-assessment, and Phase 4.5 (conditional
alignment-guard) before the health record update. Existing phases
(0, 1, 1.5, 2, 3, 4, 5) keep their current behavior.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "workforce" / "SKILL.md"


def _body() -> str:
    return SKILL_PATH.read_text()


def test_skill_md_exists() -> None:
    assert SKILL_PATH.exists()


def test_phase_0_5_conditional_intent_validation_present() -> None:
    body = _body()
    assert "PHASE 0.5" in body
    assert "INTENT VALIDATION" in body
    assert "intent-validator" in body
    # Must say "conditional" because /workforce only runs intent-validation
    # when the request is vague.
    assert "conditional" in body.lower()


def test_phase_0_5_documents_trigger_heuristic() -> None:
    body = _body()
    section_match = re.search(r"### PHASE 0\.5.*?(?=\n### PHASE )", body, re.DOTALL)
    assert section_match
    section = section_match.group(0)
    # Trigger heuristic is the load-bearing part of this phase — must be documented.
    assert "Trigger heuristic" in section or "trigger heuristic" in section.lower()
    # Must mention vision.md as one of the inputs to the trigger decision.
    assert "vision.md" in section


def test_phase_4_5_alignment_guard_present() -> None:
    body = _body()
    assert "PHASE 4.5" in body
    assert "alignment-guard" in body


def test_phase_4_5_runs_only_with_intent_md() -> None:
    body = _body()
    section_match = re.search(r"### PHASE 4\.5.*?(?=\n### PHASE )", body, re.DOTALL)
    assert section_match
    section = section_match.group(0)
    # The phase must explicitly require intent.md.
    assert "intent.md" in section


def test_phase_4_5_documents_three_outcomes() -> None:
    body = _body()
    section_match = re.search(r"### PHASE 4\.5.*?(?=\n### PHASE )", body, re.DOTALL)
    assert section_match
    section = section_match.group(0)
    for status in ["PASS", "PASS-WITH-NOTES", "BLOCK"]:
        assert status in section


def test_phase_4_5_does_not_auto_revert_on_block() -> None:
    body = _body()
    section_match = re.search(r"### PHASE 4\.5.*?(?=\n### PHASE )", body, re.DOTALL)
    assert section_match
    section = section_match.group(0)
    # Critical: workforce is conservative — alignment-guard is non-mutating.
    assert "non-mutating" in section.lower() or "not auto-revert" in section.lower() or "does not auto-revert" in section.lower()


def test_skill_references_backbone_doc() -> None:
    body = _body()
    assert "_backbone/BACKBONE.md" in body or "skills/_backbone" in body


def test_skill_references_workforce_paths_helper() -> None:
    body = _body()
    assert "workforce_paths.py" in body


def test_phase_ordering_preserved() -> None:
    body = _body()
    phases = [
        "### PHASE 0",
        "### PHASE 0.5",
        "### PHASE 1",
        "### PHASE 1.5",
        "### PHASE 2",
        "### PHASE 3",
        "### PHASE 4",
        "### PHASE 4.5",
        "### PHASE 5",
    ]
    positions = []
    for phase in phases:
        idx = body.find(phase)
        assert idx >= 0, f"missing phase header: {phase}"
        positions.append((phase, idx))
    sorted_positions = sorted(positions, key=lambda p: p[1])
    assert positions == sorted_positions, (
        "Phase headings out of order. Expected: "
        + ", ".join(p[0] for p in phases)
        + "; got: "
        + ", ".join(p[0] for p in sorted_positions)
    )


def test_legacy_phase_0_scan_still_present() -> None:
    body = _body()
    assert "scanner" in body
    assert "project-snapshot.md" in body


def test_legacy_phase_1_orchestrator_still_present() -> None:
    body = _body()
    assert "workforce-orchestrator" in body
    assert "workforce-plan.md" in body


def test_rules_section_documents_conditionality() -> None:
    body = _body()
    rules_match = re.search(r"## Rules\b.*", body, re.DOTALL)
    assert rules_match
    rules = rules_match.group(0)
    assert "Phase 0.5" in rules
    assert "conditional" in rules.lower()
    assert "Phase 4.5" in rules
