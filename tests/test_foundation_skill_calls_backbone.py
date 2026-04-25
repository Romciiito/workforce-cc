"""Tests that skills/foundation/SKILL.md correctly delegates to the backbone.

After Chunk 6, /foundation has Phase -1 (intent-validator) before Phase 0
and Phase 3.6 (alignment-guard) before Phase 4. The original phases
(0, 1A, 1B, 1B.5, 1C, 2, 3, 3.5, 4) all remain in place; only the gates
were added. These tests assert the new gates exist and the rules section
references them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "foundation" / "SKILL.md"


def _body() -> str:
    return SKILL_PATH.read_text()


def test_skill_md_exists() -> None:
    assert SKILL_PATH.exists()


def test_phase_minus_one_intent_validation_present() -> None:
    body = _body()
    assert "PHASE -1" in body
    assert "INTENT VALIDATION" in body
    assert "intent-validator" in body


def test_phase_minus_one_blocks_until_intent_md_exists() -> None:
    body = _body()
    # The Phase -1 section must explicitly say it's blocking.
    phase_match = re.search(r"## PHASE -1.*?(?=\n## PHASE )", body, re.DOTALL)
    assert phase_match, "PHASE -1 section not found or has no closing"
    section = phase_match.group(0)
    assert "blocking" in section.lower() or "Blocking" in section
    assert ".workforce/intent.md" in section


def test_phase_minus_one_documents_three_modes() -> None:
    body = _body()
    phase_match = re.search(r"## PHASE -1.*?(?=\n## PHASE )", body, re.DOTALL)
    assert phase_match
    section = phase_match.group(0)
    for mode in ["Mode A", "Mode B", "Mode C"]:
        assert mode in section, f"PHASE -1 must document {mode}"


def test_phase_3_point_6_alignment_guard_present() -> None:
    body = _body()
    assert "PHASE 3.6" in body
    assert "ALIGNMENT GUARD" in body or "alignment-guard" in body


def test_phase_3_point_6_documents_three_outcomes() -> None:
    body = _body()
    phase_match = re.search(r"## PHASE 3\.6.*?(?=\n## PHASE )", body, re.DOTALL)
    assert phase_match
    section = phase_match.group(0)
    for status in ["PASS", "PASS-WITH-NOTES", "BLOCK"]:
        assert status in section, f"PHASE 3.6 must document outcome: {status}"


def test_phase_3_point_6_blocks_phase_4() -> None:
    body = _body()
    # The rule must explicitly forbid Phase 4 invocation when alignment-report=BLOCK.
    assert re.search(
        r"`agent-generator`.*BLOCK|BLOCK.*`agent-generator`",
        body,
        re.DOTALL | re.IGNORECASE,
    ), "Phase 4 must be gated on alignment-report.md PASS"


def test_skill_references_backbone_doc() -> None:
    body = _body()
    assert "_backbone/BACKBONE.md" in body or "skills/_backbone" in body


def test_skill_references_workforce_paths_helper() -> None:
    body = _body()
    assert "workforce_paths.py" in body, (
        "SKILL.md must reference scripts/workforce_paths.py for canonical .workforce/ paths"
    )


def test_phase_ordering_preserved() -> None:
    """Phase headings must appear in the correct order in the document."""
    body = _body()
    # Required phase markers (subset; not every sub-phase needs to be locked).
    phases = [
        "## PHASE -1",
        "## PHASE 0",
        "## PHASE 1A",
        "## PHASE 1B",
        "## PHASE 1B.5",
        "## PHASE 1C",
        "## PHASE 2",
        "## PHASE 3",
        "## PHASE 3.5",
        "## PHASE 3.6",
        "## PHASE 4",
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


def test_legacy_phase_0_brainstorm_still_present() -> None:
    """Phase 0 brainstorm must remain — Chunk 6 is additive."""
    body = _body()
    assert "DEEP BRAINSTORM" in body
    assert "brainstorm.md" in body
    assert "Socratic" in body or "socratic" in body


def test_output_validator_phase_1b_5_still_present() -> None:
    """Per the plan: output-validator and alignment-guard coexist for one release."""
    body = _body()
    assert "PHASE 1B.5" in body
    assert "output-validator" in body


def test_rules_section_references_blocking_phase_minus_one() -> None:
    body = _body()
    rules_match = re.search(r"## Rules\b.*", body, re.DOTALL)
    assert rules_match
    rules = rules_match.group(0)
    assert "Phase -1" in rules and ("blocking" in rules.lower() or "Blocking" in rules)
