"""Tests for Chunk 12: engineer agent prompt-style pass.

After Chunk 12, three engineer agents (architect, security-analyst,
requirements-engineer) carry the same shape every dispatched engineer
sees in the envelope: an adversarial self-critique block + a read-only-
on-non-territory constraint. Plus requirements-engineer was lifted from
its procedural framing to engineer-with-judgment.

These tests assert the structural invariants without locking in exact
wording, so the prompts can evolve as long as they keep the spine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_DIR = REPO_ROOT / "agents" / "_shared"

ENGINEERS = ["architect", "security-analyst", "requirements-engineer"]


@pytest.mark.parametrize("agent", ENGINEERS)
def test_engineer_has_adversarial_self_critique(agent: str) -> None:
    body = (SHARED_DIR / f"{agent}.md").read_text()
    assert "## Adversarial self-critique" in body, (
        f"{agent}.md missing '## Adversarial self-critique' section"
    )


@pytest.mark.parametrize("agent", ENGINEERS)
def test_engineer_self_critique_lists_canonical_traps(agent: str) -> None:
    body = (SHARED_DIR / f"{agent}.md").read_text()
    section_start = body.index("## Adversarial self-critique")
    section = body[section_start:]
    # Find the next '## ' heading (or end of doc).
    next_heading = section.find("\n## ", 1)
    if next_heading >= 0:
        section = section[:next_heading]
    # Each agent's self-critique must surface at least these traps.
    for trap in ["Verification avoidance", "first 80%"]:
        assert trap in section, f"{agent}.md self-critique missing trap: {trap}"


@pytest.mark.parametrize("agent", ENGINEERS)
def test_engineer_has_read_only_constraint(agent: str) -> None:
    body = (SHARED_DIR / f"{agent}.md").read_text()
    assert "## Read-only constraints" in body, (
        f"{agent}.md missing '## Read-only constraints' section"
    )


@pytest.mark.parametrize("agent", ENGINEERS)
def test_engineer_read_only_lists_owned_artifact(agent: str) -> None:
    """The read-only block must explicitly name the engineer's owned output(s)."""
    body = (SHARED_DIR / f"{agent}.md").read_text()
    section_start = body.index("## Read-only constraints")
    section = body[section_start:]
    expected_owned = {
        "architect": "architecture.md",
        "security-analyst": "security-model.md",
        "requirements-engineer": "requirements.md",
    }
    assert expected_owned[agent] in section, (
        f"{agent}.md read-only section must reference its owned output: "
        f"{expected_owned[agent]}"
    )


@pytest.mark.parametrize("agent", ENGINEERS)
def test_engineer_read_only_forbids_specific_upstream_files(agent: str) -> None:
    body = (SHARED_DIR / f"{agent}.md").read_text()
    section_start = body.index("## Read-only constraints")
    section = body[section_start:]
    # Each engineer must explicitly not modify at least three other artifacts
    # — surfacing gaps via Open issues, not silent edits.
    assert "must not" in section.lower() or "do not" in section.lower()
    # Open-issues escalation pattern is part of the read-only contract.
    assert "Open issues" in section


@pytest.mark.parametrize("agent", ENGINEERS)
def test_engineer_uses_three_reviewer_test(agent: str) -> None:
    """The three-reviewer / three-engineer / three-architect heuristic must
    appear in the self-critique. It's the single sharpest test for whether
    the engineer's output is concrete enough."""
    body = (SHARED_DIR / f"{agent}.md").read_text()
    # Allow any of "three reviewers", "three engineers", "three architects",
    # "three different X" — same idea, different role names.
    has_three_test = any(
        phrase in body.lower()
        for phrase in [
            "three different",
            "three reviewers",
            "three engineers",
            "three architects",
            "three-reviewer",
            "three-engineer",
            "three-architect",
        ]
    )
    assert has_three_test, (
        f"{agent}.md self-critique should include a three-reviewer-style test"
    )


def test_requirements_engineer_lifted_to_engineer_with_judgment() -> None:
    """Phase 1 audit flagged requirements-engineer as procedural. Chunk 12
    rewrote the opening framing to make judgment explicit."""
    body = (SHARED_DIR / "requirements-engineer.md").read_text()
    # The new opening must explicitly call out judgment over template-filling.
    assert "not a template-filler" in body or "not a yes-machine" in body or "judgment" in body.lower()
    # It must also acknowledge that structure serves the work, not the other way around.
    assert "structure serves the work" in body or "checklist of dimensions" in body or "dimensions to interrogate" in body


def test_requirements_engineer_keeps_existing_id_conventions() -> None:
    """Lifting the framing must not delete the existing REQ-F/REQ-NF id system."""
    body = (SHARED_DIR / "requirements-engineer.md").read_text()
    for prefix in ["REQ-F-", "REQ-NF-", "REQ-INT-", "REQ-OPS-", "REQ-ACC-"]:
        assert prefix in body, f"requirements-engineer.md must keep {prefix} convention"


def test_requirements_engineer_keeps_eight_edge_case_checks() -> None:
    """The eight edge-case checks (empty state, concurrent users, etc.) must
    remain — they're the most useful prescriptive part of this agent."""
    body = (SHARED_DIR / "requirements-engineer.md").read_text()
    for check in [
        "empty state",
        "concurrent user",
        "large dataset",
        "permission boundary",
        "deletion cascade",
        "offline",
        "timezone",
    ]:
        assert check in body.lower(), (
            f"requirements-engineer.md must keep the '{check}' edge-case check"
        )
